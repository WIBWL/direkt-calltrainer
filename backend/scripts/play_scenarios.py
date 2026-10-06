"""Plays every seeded Scenario against every Persona and writes the transcripts to
logs/scenario-runs/<timestamp>/. Only the LLM is real; STT returns the scripted
probe (see scenario_probes.py), TTS silence. Exit 2: bad probes or empty
selection; 1: a run failed.

    python -m backend.scripts.play_scenarios [--only <scenario>] [--persona <persona>]"""
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

from shared.clients import llm
from shared.feedback.acoustics import AcousticsError
from shared.language_packs import get_pack, signals_closing
from backend import library
from backend.clients import stt, tts
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session import orchestrator as orch
from backend.session.prompting import build_system_prompt
from backend.session.events import Failed, TurnCompleted
from backend.scripts.scenario_probes import (
    CONCRETE,
    FAREWELL,
    SETTLE,
    VAGUE,
    PROBE_PURPOSE,
    check_probes,
    probes_for,
)

logger = logging.getLogger("play_scenarios")

# Matched against the raw model output: it is stripped before TTS.
END_MARKER_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

# Rough speech rate for the stubbed TTS; only the report's timings depend on it.
_MS_PER_CHAR = 66

# A crude wrong-language check, counted over the whole call.
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

_MIN_LANGUAGE_MARKERS = 3
_MIN_TEXT_TO_JUDGE = 200

# extern_id -> seed slug, filled by `_load_slugs`.
_SCENARIO_SLUGS: dict[str, str] = {}
_PERSONA_SLUGS: dict[str, str] = {}


@dataclass
class TurnRecord:
    slot: int
    user_text: str
    reply: str
    # The model emitted [CALL_END] itself.
    model_ended: bool = False
    # `signals_closing` matched the probe and forced the end.
    forced: bool = False
    # The orchestrator's conclusion, repetition guards included.
    ended: bool = False
    failure: str | None = None


@dataclass
class RunRecord:
    persona: Persona
    scenario: Scenario
    system_prompt: str
    opening: str = ""
    used_fallback_probe: bool = False
    turns: list[TurnRecord] = field(default_factory=list)
    failure: str | None = None

    @property
    def label(self) -> str:
        return f"{self.scenario.name} / {self.persona.name}"

    @property
    def replies(self) -> list[str]:
        return [self.opening, *(t.reply for t in self.turns)]


class _Pipeline:
    """STT hands back the due probe, TTS silence; the LLM is wrapped to keep the
    raw stream, since who ended the call is the point of the report."""

    def __init__(self) -> None:
        self.next_user_text = ""
        self.raw_reply = ""
        # Captured before `_stubbed` rebinds the name.
        self._real_stream_reply = llm.stream_reply

    async def transcribe(self, *_args, **_kwargs) -> str:
        return self.next_user_text

    async def stream_reply(self, messages):
        self.raw_reply = ""
        async for chunk in self._real_stream_reply(messages):
            self.raw_reply += chunk
            yield chunk

    async def synthesize_stream(self, text, *_args, **_kwargs):
        yield b"\0" * max(1, len(text))

    async def synthesize(self, text, *_args, **_kwargs) -> bytes:
        return b"\0" * max(1, len(text))

    @staticmethod
    def duration_ms(audio: bytes) -> int:
        return len(audio) * _MS_PER_CHAR

    @staticmethod
    def analyze(_audio: bytes):
        raise AcousticsError("harness: no real audio to measure")


@contextmanager
def _stubbed(pipeline: _Pipeline):
    """`analyze` is patched on the orchestrator, which imported the name directly."""
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
    llm.stream_reply = pipeline.stream_reply
    try:
        yield
    finally:
        for (module, name), original in saved.items():
            setattr(module, name, original)


async def _drain(events) -> tuple[bool, str | None]:
    """Returns (ends_call, failure code)."""
    ended, failure = False, None
    async for event in events:
        if isinstance(event, TurnCompleted):
            ended = event.ends_call
        elif isinstance(event, Failed):
            failure = f"{event.code}: {event.message}"
    return ended, failure


async def play(persona: Persona, scenario: Scenario) -> RunRecord:
    pack = get_pack(persona.language_id)
    probes, used_fallback = probes_for(scenario_key_of(scenario), persona.language_id)
    session = orch.SessionOrchestrator(persona, scenario)
    run = RunRecord(
        persona=persona,
        scenario=scenario,
        system_prompt=build_system_prompt(persona, scenario, pack),
        used_fallback_probe=used_fallback,
    )

    pipeline = _Pipeline()
    with _stubbed(pipeline):
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
    """By `extern_id`, not title; authored Scenarios get the fallback probe."""
    return _SCENARIO_SLUGS.get(scenario.id)


def _numbers(text: str) -> set[str]:
    """Two digits or more: a lone digit matches far too easily."""
    return {re.sub(r"[.,\s]", "", n) for n in re.findall(r"\d[\d.,]*\d", text)}


def _flow_flags(run: RunRecord) -> list[str]:
    """`ended` without `model_ended` or `forced` means the repetition guards closed it."""
    found: list[str] = []
    by_slot = {t.slot: t for t in run.turns}
    if any(t.ended for t in run.turns[:2]):
        found.append("ends at probe 1 or 2")
    vague = by_slot.get(VAGUE)
    if vague is not None and (vague.ended or vague.model_ended):
        found.append("accepts the vague promise")
    if run.turns and not any(t.model_ended for t in run.turns):
        found.append("never emits [CALL_END] itself, ends only through the backstop")
    if any(t.ended and not t.model_ended and not t.forced for t in run.turns):
        found.append("ended by the repetition guard")
    return found


def _content_flags(run: RunRecord) -> list[str]:
    found: list[str] = []
    spoken = " ".join(run.replies)

    wanted = _numbers(run.scenario.case_facts)
    if wanted and not wanted & _numbers(spoken):
        found.append("mentions no figure from the case facts")

    marker = _LANGUAGE_MARKERS.get(run.persona.language_id)
    if marker is not None and len(spoken) >= _MIN_TEXT_TO_JUDGE:
        distinct = {m.group().lower() for m in marker.finditer(spoken)}
        if len(distinct) < _MIN_LANGUAGE_MARKERS:
            found.append(f"possibly not in {run.persona.language_id}")

    if run.used_fallback_probe:
        found.append("generic probe 4 (no entry of its own)")
    return found


def flags_for(run: RunRecord) -> list[str]:
    """Mechanical red flags; none judges quality."""
    if run.failure:
        return [f"RUN FAILED ({run.failure})"]
    return _flow_flags(run) + _content_flags(run)


def closing_slot(run: RunRecord) -> int | None:
    """The probe after which the model closed the call itself, or None."""
    for turn in run.turns:
        if turn.model_ended:
            return turn.slot
    return None


def _run_markdown(run: RunRecord, flags: list[str]) -> str:
    lines = [
        f"# {run.scenario.name}",
        "",
        f"- Persona: **{run.persona.name}** ({run.persona.language_id})",
        f"- Category: {run.scenario.category or 'none'}",
        f"- Short description: {run.scenario.short_description}",
        "",
        "## Flags",
        "",
    ]
    lines += [f"- {f}" for f in flags] or ["- none"]
    lines += ["", "## System prompt", "", "```", run.system_prompt, "```", "", "## Conversation", ""]
    lines += [f"**Persona (opening):** {run.opening}", ""]
    for turn in run.turns:
        marks = []
        if turn.model_ended:
            marks.append("[CALL_END] from the model")
        if turn.forced:
            marks.append("Backstop (signals_closing)")
        if turn.ended:
            marks.append("call ended")
        suffix = f"  _{', '.join(marks)}_" if marks else ""
        lines += [
            f"**User, probe {turn.slot + 1}** ({PROBE_PURPOSE[turn.slot]}): {turn.user_text}",
            "",
            f"**Persona:** {turn.reply}{suffix}",
            "",
        ]
        if turn.failure:
            lines += [f"> Error: {turn.failure}", ""]
    return "\n".join(lines)


def _summary_markdown(results: list[tuple[RunRecord, list[str]]], started: datetime) -> str:
    lines = [
        "# Scenario run",
        "",
        f"Started {started.isoformat(timespec='seconds')}, {len(results)} pairings.",
        "",
        "Flags are mechanical anomalies, not a judgement of quality. A scenario",
        "without a flag has not been checked; it is merely not obviously broken.",
        "",
        "| Scenario | Persona | Turns | Closes at | Flags |",
        "|---|---|---|---|---|",
    ]
    for run, flags in results:
        cell = "; ".join(flags) if flags else "-"
        slot = closing_slot(run)
        closes = f"probe {slot + 1}" if slot is not None else "never"
        lines.append(
            f"| {run.scenario.name} | {run.persona.name} | {len(run.turns)} "
            f"| {closes} | {cell} |"
        )
    return "\n".join(lines) + "\n" + _systemic_markdown(results)


def _systemic_markdown(results: list[tuple[RunRecord, list[str]]]) -> str:
    """Observations uniform across the library, stated once."""
    total = len(results)
    if not total:
        return ""
    satisfied = sum(1 for r, _ in results if closing_slot(r) in (CONCRETE, SETTLE))
    farewell = sum(1 for r, _ in results if closing_slot(r) == FAREWELL)
    never = sum(1 for r, _ in results if closing_slot(r) is None)
    return "\n".join([
        "",
        "## Systemic observation",
        "",
        "When does the persona end the call on its own (`[CALL_END]`)?",
        "",
        "| | |",
        "|---|---|",
        f"| once the success condition is met (probe 4 or 5) | {satisfied} of {total} |",
        f"| only at the farewell (probe 6) | {farewell} of {total} |",
        f"| never, ended by the backstop or the repetition guard | {never} of {total} |",
        "",
        "The prompt asks for the first case explicitly (`Once it has been"
        " given you are done ... and end the call`, backend/session/"
        "orchestrator.py). A low count there is a finding about the prompt"
        " frame and the model, not about individual scenarios.",
        "",
    ])


def _load_library() -> tuple[list[Persona], list[Scenario]]:
    """The built-ins as the app reads them: a subject owning nothing sees only `public` rows."""
    scenarios = [s for s in library.list_scenarios("__harness__", -1) if s.created_by is None]
    _load_slugs()
    return library.list_personas(), scenarios


def _load_slugs() -> None:
    # pylint: disable=import-outside-toplevel
    from sqlalchemy import select

    from shared.db import models
    from shared.db.session import session_scope

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
                        help="Only this scenario (may be repeated).")
    parser.add_argument("--persona", action="append", metavar="PERSONA_KEY",
                        help="Only this persona (may be repeated).")
    parser.add_argument("--out", metavar="DIR",
                        help="Output directory (default: logs/scenario-runs/<timestamp>).")
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
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args()

    problems = check_probes()
    if problems:
        print("Probe check failed, no LLM call was made:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    personas, scenarios = _load_library()
    personas, scenarios = _select(personas, scenarios, args)
    if not personas or not scenarios:
        print("The selection is empty.", file=sys.stderr)
        return 2

    started = datetime.now(UTC)
    out = Path(args.out) if args.out else (
        Path("logs/scenario-runs") / started.strftime("%Y%m%d-%H%M%S")
    )
    out.mkdir(parents=True, exist_ok=True)

    results = await _play_all(personas, scenarios, out)
    (out / "summary.md").write_text(_summary_markdown(results, started), encoding="utf-8")
    print(f"\nResults saved to {out}")
    return 1 if any(run.failure for run, _ in results) else 0


async def _play_all(personas, scenarios, out: Path) -> list[tuple[RunRecord, list[str]]]:
    """Sequential: in parallel the run would measure the gateway's queueing."""
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
    return _PERSONA_SLUGS.get(persona.id) or persona.name.lower().replace(" ", "-")


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
