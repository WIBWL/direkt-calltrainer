"""Play every seeded Scenario against every Persona and write the transcripts.

An inspection tool, not a test. It cannot say whether a Scenario is *good*; it
says which pairings are obviously broken, so the ones worth listening to by hand
are a short list instead of all of them. Deliberately not under `tests/`: that
suite is network-free by construction (`tests/conftest.py` fakes the pipeline
and claims the POSTGRES_* names with unusable values before the backend is
imported, and `test_database_isolation.py` guards that ordering), and a
non-deterministic run has no honest pass/fail anyway.

What is real and what is not:

  * The LLM leg is real, and so is everything around it -- prompt assembly
    (ADR 0045), the repetition guards (ADR 0038), closing detection (ADR 0037)
    and the `[CALL_END]` marker. That is where Scenario content lives.
  * STT is stubbed and returns the scripted probe, so no audio is synthesised
    only to be recognised again.
  * TTS is stubbed and returns silence sized from the text, so the timeline
    stays plausible without a second round trip per chunk.
  * The acoustic analysis is stubbed to "not measurable", which is a path the
    orchestrator already handles and never treats as fatal.

So this exercises the dialogue, not the audio path. `scripts/check_backends.py`
covers STT and TTS.

The trainee is scripted in `scripts/scenario_probes.py`: five turns, four of
them the same everywhere, the fourth written per Scenario to satisfy that
Scenario's `success_condition`. Read that module's docstring before changing a
probe; a probe that trips `signals_closing` ends the call early and looks like a
clean short run.

Usage:
    docker compose exec app python scripts/play_scenarios.py
    docker compose exec app python scripts/play_scenarios.py --only closing-recap-mismatch
    docker compose exec app python scripts/play_scenarios.py --persona thomas-brandt-ceo

Output goes to logs/scenario-runs/<timestamp>/, which compose mounts from the
repository, so the files land next to the checkout. One Markdown file per
pairing, carrying the rendered system prompt and the transcript, plus a
summary.md with one row each.

Exit codes: 2 if the probes fail their own check or the selection is empty (no
LLM call is made in either case), 1 if a run failed outright (a leg gave up past
its retry), 0 otherwise. Red flags are findings for a human, not verdicts, so
they do not change the exit code.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# A script, not a package: the project root has to be on the search path
# before anything under backend/ can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# pylint: disable=wrong-import-position
from backend import library  # noqa: E402
from backend.clients import llm, stt, tts  # noqa: E402
from backend.feedback.acoustics import AcousticsError  # noqa: E402
from backend.personas import Persona  # noqa: E402
from backend.scenarios import Scenario  # noqa: E402
from backend.session import orchestrator as orch  # noqa: E402
from backend.session.language_packs import get_pack, signals_closing  # noqa: E402
from backend.session.models import Failed, TurnCompleted  # noqa: E402
from scripts.scenario_probes import (  # noqa: E402
    CONCRETE,
    FAREWELL,
    VAGUE,
    PROBE_PURPOSE,
    check_probes,
    probes_for,
)

logger = logging.getLogger("play_scenarios")

# The literal the orchestrator ends a call on. Matched against the *raw* model
# output, which is why the recorder below keeps it: `_strip_end_marker` removes
# it before TTS, so `turn.persona_text` no longer carries it.
END_MARKER_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

# Rough speech rate for the stubbed TTS, so persona_end_ms advances by something
# plausible instead of a constant. Only the report's timings depend on it.
_MS_PER_CHAR = 66

# Function words common enough that a whole call in that language is certain to
# contain several. A crude signal, not a language detector: it only has to catch
# a Persona answering wholly in the wrong language.
#
# Judged over the whole call rather than per reply, and against a count rather
# than a single hit: one German sentence can easily miss any given word
# ("Brandt hier, bei uns bleibt seit drei Tagen alles liegen" contains none of
# the obvious ones), which made the per-reply version cry wolf.
_LANGUAGE_MARKERS = {
    "de": re.compile(
        r"\b(ich|nicht|und|das|der|ist|sind|sie|wir|uns|noch|haben|ein|eine|einen|"
        r"f[uü]r|mit|auf|sich|was|wie|dass|aber|bei|von|im|am|es|hier|dann|schon|nur)\b",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(the|and|that|you|have|with|this|for|not|will|are|was|from|about|"
        r"there|would|which|been|they|your)\b",
        re.IGNORECASE,
    ),
}

# Below this many distinct marker words across the whole call, with enough text
# to judge by, the reply language is doubtful.
_MIN_LANGUAGE_MARKERS = 3
_MIN_TEXT_TO_JUDGE = 200

# extern_id -> seed slug, filled by `_load_slugs`. The probe sets and the output
# filenames are keyed by the slug; the value objects carry only the extern_id.
_SCENARIO_SLUGS: dict[str, str] = {}
_PERSONA_SLUGS: dict[str, str] = {}


@dataclass
class TurnRecord:
    """One user probe and the reply it drew."""

    slot: int
    user_text: str
    reply: str
    # The model emitted [CALL_END] itself: it considers its own matter settled.
    model_ended: bool = False
    # `signals_closing` matched the probe, so `force_end_call` was set and the
    # call would have ended even if the model said nothing of the kind.
    forced: bool = False
    # What the orchestrator concluded, which folds in the two above plus the
    # repetition guards.
    ended: bool = False
    failure: str | None = None


@dataclass
class RunRecord:
    """One Persona x Scenario pairing."""

    persona: Persona
    scenario: Scenario
    system_prompt: str
    opening: str = ""
    used_fallback_probe: bool = False
    turns: list[TurnRecord] = field(default_factory=list)
    failure: str | None = None

    @property
    def label(self) -> str:
        """How this pairing is named in the console output."""
        return f"{self.scenario.name} / {self.persona.name}"

    @property
    def replies(self) -> list[str]:
        """Everything the Persona said, opening first."""
        return [self.opening, *(t.reply for t in self.turns)]


class _Pipeline:
    """The stubs, and the tap on the LLM.

    STT hands back whatever probe is due. TTS returns silence. The LLM is not
    replaced, only wrapped, so the raw stream can be kept: `[CALL_END]` is
    stripped before it reaches the Turn, and telling a model that ended the call
    itself from one that was ended by the user's goodbye is the whole point of
    the report.
    """

    def __init__(self) -> None:
        self.next_user_text = ""
        self.raw_reply = ""
        # Captured before `_stubbed` rebinds the name, or the wrapper below
        # would call itself.
        self._real_stream_reply = llm.stream_reply

    async def transcribe(self, *_args, **_kwargs) -> str:
        """Whatever probe is due, in place of recognising synthesised speech."""
        return self.next_user_text

    async def stream_reply(self, messages):
        """The real call, with the raw text kept for the [CALL_END] check."""
        self.raw_reply = ""
        async for chunk in self._real_stream_reply(messages):
            self.raw_reply += chunk
            yield chunk

    async def synthesize_stream(self, text, *_args, **_kwargs):
        """Silence, sized from the text so the timeline stays plausible."""
        yield b"\0" * max(1, len(text))

    async def synthesize(self, text, *_args, **_kwargs) -> bytes:
        """Silence for the fallback closing line."""
        return b"\0" * max(1, len(text))

    @staticmethod
    def duration_ms(audio: bytes) -> int:
        """How long that silence would have taken to say."""
        return len(audio) * _MS_PER_CHAR

    @staticmethod
    def analyze(_audio: bytes):
        """Always "not measurable"."""
        # A path the orchestrator already handles: the Turn simply carries no
        # measurements and the call continues (`_attach_measurements`).
        raise AcousticsError("harness: no real audio to measure")


@contextmanager
def _stubbed(pipeline: _Pipeline):
    """Swap the pipeline's edges for the duration of a run.

    `analyze` is patched on the orchestrator module, not on
    `backend.feedback.acoustics`: the orchestrator imported the name directly,
    so rebinding it at its source would not reach the call site.
    """
    saved = {
        (stt, "transcribe"): stt.transcribe,
        (tts, "synthesize_stream"): tts.synthesize_stream,
        (tts, "synthesize"): tts.synthesize,
        (tts, "duration_ms"): tts.duration_ms,
        (orch, "analyze"): orch.analyze,
        (llm, "stream_reply"): llm.stream_reply,
    }
    stt.transcribe = pipeline.transcribe
    tts.synthesize_stream = pipeline.synthesize_stream
    tts.synthesize = pipeline.synthesize
    tts.duration_ms = pipeline.duration_ms
    orch.analyze = pipeline.analyze
    # Wrapped, not replaced: the real call still happens, the raw text is kept.
    llm.stream_reply = pipeline.stream_reply
    try:
        yield
    finally:
        for (module, name), original in saved.items():
            setattr(module, name, original)


async def _drain(events) -> tuple[bool, str | None]:
    """Consume one turn's events; returns (ends_call, failure code)."""
    ended, failure = False, None
    async for event in events:
        if isinstance(event, TurnCompleted):
            ended = event.ends_call
        elif isinstance(event, Failed):
            failure = f"{event.code}: {event.message}"
    return ended, failure


async def play(persona: Persona, scenario: Scenario) -> RunRecord:
    """One pairing, five probes, or fewer if the call ends early."""
    pack = get_pack(persona.language_id)
    probes, used_fallback = probes_for(scenario_key_of(scenario), persona.language_id)
    session = orch.SessionOrchestrator(persona, scenario)
    run = RunRecord(
        persona=persona,
        scenario=scenario,
        system_prompt=orch._build_system_prompt(persona, scenario, pack),  # pylint: disable=protected-access
        used_fallback_probe=used_fallback,
    )

    pipeline = _Pipeline()
    with _stubbed(pipeline):
        # Wrapping rather than replacing: the real call still happens.
        saved_stream = orch.llm.stream_reply
        orch.llm.stream_reply = pipeline.stream_reply
        try:
            _, failure = await _drain(session.run_opening_turn())
            run.opening = session.turns[-1].persona_text if session.turns else ""
            if failure:
                run.failure = failure
                return run
            session.start_playback()

            for slot, probe in enumerate(probes):
                pipeline.next_user_text = probe
                ended, failure = await _drain(session.run_turn(b"\0" * 64, "turn.wav", "audio/wav"))
                record = TurnRecord(
                    slot=slot,
                    user_text=probe,
                    reply=session.turns[-1].persona_text,
                    model_ended=bool(END_MARKER_RE.search(pipeline.raw_reply)),
                    forced=signals_closing(pack, probe),
                    ended=ended,
                    failure=failure,
                )
                run.turns.append(record)
                if failure:
                    run.failure = failure
                    break
                if ended:
                    break
        finally:
            orch.llm.stream_reply = saved_stream
    return run


def scenario_key_of(scenario: Scenario) -> str | None:
    """The seed slug a probe set is keyed by.

    Looked up by `extern_id`, which is what the value object carries as `id`
    (ADR 0050). Matching on the title instead would be silently wrong the first
    time a Scenario is renamed: the run would drop to the fallback probe and
    still look like a reasonable run. An authored Scenario has no slug and gets
    the fallback on purpose.
    """
    return _SCENARIO_SLUGS.get(scenario.id)


def _numbers(text: str) -> set[str]:
    """Digit groups worth looking for in a reply, separators removed.

    Two digits or more only: "three people" and "eight steps" are spelled out in
    these cases anyway, and a lone digit matches far too easily.
    """
    return {re.sub(r"[.,\s]", "", n) for n in re.findall(r"\d[\d.,]*\d", text)}


def _flow_flags(run: RunRecord) -> list[str]:
    """How the call ran: where it ended and why.

    `ended` without `model_ended` and without `forced` means neither the model
    nor the user closed it, which leaves the repetition guards (ADR 0038) as the
    only thing that could have.
    """
    found: list[str] = []
    by_slot = {t.slot: t for t in run.turns}
    if any(t.ended for t in run.turns[:2]):
        found.append("bricht bei Sonde 1 oder 2 ab")
    vague = by_slot.get(VAGUE)
    if vague is not None and (vague.ended or vague.model_ended):
        found.append("gibt sich mit der vagen Zusage zufrieden")
    if run.turns and not any(t.model_ended for t in run.turns):
        found.append("sagt nie selbst [CALL_END], endet nur über den Backstop")
    if any(t.ended and not t.model_ended and not t.forced for t in run.turns):
        found.append("Wiederholungswächter hat abgebrochen")
    return found


def _content_flags(run: RunRecord) -> list[str]:
    """What was said: the case facts, the language, and the probe used."""
    found: list[str] = []
    spoken = " ".join(run.replies)

    wanted = _numbers(run.scenario.case_facts)
    if wanted and not wanted & _numbers(spoken):
        found.append("nennt keine Zahl aus den Fallfakten")

    marker = _LANGUAGE_MARKERS.get(run.persona.language_id)
    if marker is not None and len(spoken) >= _MIN_TEXT_TO_JUDGE:
        distinct = {m.group().lower() for m in marker.finditer(spoken)}
        if len(distinct) < _MIN_LANGUAGE_MARKERS:
            found.append(f"womöglich nicht auf {run.persona.language_id}")

    if run.used_fallback_probe:
        found.append("generische Sonde 4 (kein eigener Eintrag)")
    return found


def flags_for(run: RunRecord) -> list[str]:
    """The mechanical red flags. None of them judges quality.

    Deliberately absent: whether the Persona closed once its `success_condition`
    was met. That turned out to be uniform across the whole library, so it is a
    systemic observation (`_systemic_markdown`) and not a per-row finding.
    """
    if run.failure:
        return [f"LAUF ABGEBROCHEN ({run.failure})"]
    return _flow_flags(run) + _content_flags(run)


def closing_slot(run: RunRecord) -> int | None:
    """The probe after which the model closed the call itself, or None.

    Kept apart from the flags on purpose. Whether a Persona closes because its
    own `success_condition` was met, or only once the user says goodbye, turned
    out to be uniform across the whole library rather than a property of any one
    Scenario, so it belongs in the summary as one observation and not on every
    row as a finding. `_systemic_markdown` counts it.
    """
    for turn in run.turns:
        if turn.model_ended:
            return turn.slot
    return None


def _run_markdown(run: RunRecord, flags: list[str]) -> str:
    lines = [
        f"# {run.scenario.name}",
        "",
        f"- Persona: **{run.persona.name}** ({run.persona.language_id})",
        f"- Kategorie: {run.scenario.category or 'ohne'}",
        f"- Kurzbeschreibung: {run.scenario.short_description}",
        "",
        "## Flaggen",
        "",
    ]
    lines += [f"- {f}" for f in flags] or ["- keine"]
    lines += ["", "## System-Prompt", "", "```", run.system_prompt, "```", "", "## Verlauf", ""]
    lines += [f"**Persona (Eröffnung):** {run.opening}", ""]
    for turn in run.turns:
        marks = []
        if turn.model_ended:
            marks.append("[CALL_END] vom Modell")
        if turn.forced:
            marks.append("Backstop (signals_closing)")
        if turn.ended:
            marks.append("Anruf beendet")
        suffix = f"  _{', '.join(marks)}_" if marks else ""
        lines += [
            f"**Nutzer, Sonde {turn.slot + 1}** ({PROBE_PURPOSE[turn.slot]}): {turn.user_text}",
            "",
            f"**Persona:** {turn.reply}{suffix}",
            "",
        ]
        if turn.failure:
            lines += [f"> Fehler: {turn.failure}", ""]
    return "\n".join(lines)


def _summary_markdown(results: list[tuple[RunRecord, list[str]]], started: datetime) -> str:
    lines = [
        "# Szenario-Durchlauf",
        "",
        f"Gestartet {started.isoformat(timespec='seconds')}, {len(results)} Paarungen.",
        "",
        "Flaggen sind mechanische Auffälligkeiten, kein Qualitätsurteil. Ein Szenario",
        "ohne Flagge ist nicht geprüft, es ist nur nicht offensichtlich kaputt.",
        "",
        "| Szenario | Persona | Turns | Schließt bei | Flaggen |",
        "|---|---|---|---|---|",
    ]
    for run, flags in results:
        cell = "; ".join(flags) if flags else "-"
        slot = closing_slot(run)
        closes = f"Sonde {slot + 1}" if slot is not None else "nie"
        lines.append(
            f"| {run.scenario.name} | {run.persona.name} | {len(run.turns)} "
            f"| {closes} | {cell} |"
        )
    return "\n".join(lines) + "\n" + _systemic_markdown(results)


def _systemic_markdown(results: list[tuple[RunRecord, list[str]]]) -> str:
    """Observations that hold across the library rather than per Scenario.

    A finding that fires on nearly every pairing says nothing about which
    Scenario to look at, which is what the per-row flags are for. It can still
    be the most important thing in the run, so it is stated once, here rather
    than on every row where it would bury the findings that do discriminate.
    """
    total = len(results)
    if not total:
        return ""
    satisfied = sum(1 for r, _ in results if closing_slot(r) == CONCRETE)
    farewell = sum(1 for r, _ in results if closing_slot(r) == FAREWELL)
    never = sum(1 for r, _ in results if closing_slot(r) is None)
    return "\n".join([
        "",
        "## Systemische Beobachtung",
        "",
        "Wann beendet die Persona den Anruf von sich aus (`[CALL_END]`)?",
        "",
        "| | |",
        "|---|---|",
        f"| bei erfüllter Erfolgsbedingung (Sonde 4) | {satisfied} von {total} |",
        f"| erst auf die Verabschiedung (Sonde 5) | {farewell} von {total} |",
        f"| nie, Ende über Backstop oder Wiederholungswächter | {never} von {total} |",
        "",
        "Der Prompt verlangt den ersten Fall ausdrücklich (`Once it has been"
        " given you are done ... and end the call`, backend/session/"
        "orchestrator.py). Eine niedrige Zahl dort ist ein Befund über den"
        " Prompt-Rahmen und das Modell, nicht über einzelne Szenarien.",
        "",
    ])


def _load_library() -> tuple[list[Persona], list[Scenario]]:
    """The seeded built-ins, read the way the app reads them (ADR 0041).

    A subject that owns nothing and a tenant id that matches none: the built-ins
    are `public`, so `_visible_to`'s first branch returns them and neither of
    the other two can add anything (ADR 0058, ADR 0060).

    The same trip fills the slug maps. The value objects carry `extern_id` as
    `id` and not the `key` slug, and the slug is what the probe sets and the
    output filenames are keyed by.
    """
    scenarios = [s for s in library.list_scenarios("__harness__", -1) if s.created_by is None]
    _load_slugs()
    return library.list_personas(), scenarios


def _load_slugs() -> None:
    """extern_id -> seed slug, for both tables, straight from the database."""
    # Imported here rather than at module scope: only this function needs the
    # ORM, and the script is importable without a database for its own checks.
    # pylint: disable=import-outside-toplevel
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    with session_scope() as db:
        for model, target in (
            (models.Scenario, _SCENARIO_SLUGS),
            (models.Persona, _PERSONA_SLUGS),
        ):
            for extern_id, key in db.execute(select(model.extern_id, model.key)).all():
                if key:
                    target[str(extern_id)] = key


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", action="append", metavar="SCENARIO_KEY",
                        help="Nur dieses Szenario (mehrfach angebbar).")
    parser.add_argument("--persona", action="append", metavar="PERSONA_KEY",
                        help="Nur diese Persona (mehrfach angebbar).")
    parser.add_argument("--out", metavar="DIR",
                        help="Zielverzeichnis (Vorgabe: logs/scenario-runs/<Zeitstempel>).")
    return parser.parse_args()


def _select(personas, scenarios, args):
    if args.persona:
        wanted = set(args.persona)
        personas = [p for p in personas if p.id in wanted or _persona_key(p) in wanted]
    if args.only:
        wanted = set(args.only)
        scenarios = [s for s in scenarios if scenario_key_of(s) in wanted]
    return personas, scenarios


async def _main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args()

    problems = check_probes()
    if problems:
        print("Sondenprüfung fehlgeschlagen, kein LLM-Aufruf gemacht:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    personas, scenarios = _load_library()
    personas, scenarios = _select(personas, scenarios, args)
    if not personas or not scenarios:
        print("Auswahl ist leer.", file=sys.stderr)
        return 2

    started = datetime.now(UTC)
    out = Path(args.out) if args.out else (
        Path("logs/scenario-runs") / started.strftime("%Y%m%d-%H%M%S")
    )
    out.mkdir(parents=True, exist_ok=True)

    results = await _play_all(personas, scenarios, out)
    (out / "summary.md").write_text(_summary_markdown(results, started), encoding="utf-8")
    print(f"\nGeschrieben nach {out}")
    return 1 if any(run.failure for run, _ in results) else 0


async def _play_all(personas, scenarios, out: Path) -> list[tuple[RunRecord, list[str]]]:
    """Every pairing in turn, one file each, progress and flags to the console.

    Sequential on purpose: the gateway serves one model, and a run that hammers
    it in parallel would measure queueing rather than the dialogue.
    """
    results: list[tuple[RunRecord, list[str]]] = []
    total = len(personas) * len(scenarios)
    pairings = ((s, p) for s in scenarios for p in personas)
    for index, (scenario, persona) in enumerate(pairings, start=1):
        print(f"[{index}/{total}] {scenario.name} / {persona.name}", flush=True)
        run = await play(persona, scenario)
        flags = flags_for(run)
        results.append((run, flags))
        name = f"{_persona_key(persona)}__{scenario_key_of(scenario) or 'unknown'}.md"
        (out / name).write_text(_run_markdown(run, flags), encoding="utf-8")
        for flag in flags:
            print(f"    ! {flag}", flush=True)
    return results


def _persona_key(persona: Persona) -> str:
    """The seed slug, or a filename-safe stand-in for a row that has none."""
    return _PERSONA_SLUGS.get(persona.id) or persona.name.lower().replace(" ", "-")


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
