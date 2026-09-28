"""Overlapping speech, classified (F-51, focus goal "Aktives Zuhören").
Pure functions over a stored timeline, so they can be re-run on old Sessions.
A Persona's end is modelled from *dispatched* audio; `turn.interrupted` is the
reliable sign it lost words. Backchannels under 500 ms never arrive (ADR 0036).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# --- Configuration ---------------------------------------------------------
# Every threshold here is a decision, so each carries where it comes from and
# how much weight it can bear. Only the first is anchored in the literature;
# the rest are working values meant to be calibrated once the pilot has data.

# How close to the end of a Persona line a user may start without it being an
# overlap at all. Stivers et al. (2009, PNAS) measured modal gaps around 200 ms
# between turns across ten languages, with substantial overlap either side of
# zero: starting inside this window is ordinary turn-taking, not interruption.
TERMINAL_WINDOW_MS = 200

# How much Persona audio must still have been outstanding for a trimmed reply
# to count as a hard interruption. Guards the case where the reply was cut with
# a hair's worth left, which is a rounding artefact rather than an event.
# Heuristic, calibratable.
YIELD_WINDOW_MS = 500

# Below this, a user utterance that costs the Persona nothing is read as a
# listening signal rather than a bid for the floor. Heuristic, calibratable,
# and today largely pre-empted by ADR 0036's client-side VAD threshold.
BACKCHANNEL_MAX_MS = 1000

# Where the traffic light changes, in hard interruptions per call. A count, not
# a rate per Persona turn: with 6-9 turns one interruption already hit the top
# step. PROVISIONAL, invented working values -- hence "orientation", not verdict.
GREEN_MAX_COUNT = 0
YELLOW_MAX_COUNT = 2

# The metric a Finding of this kind points at, and the `finding.category` it
# carries. Named here rather than spelled out at each site: the writer
# (persistence.py), the backfill script and anything reading them later have to
# agree on the string, and a typo would simply match nothing.
COUNT_KEY = "interruptions"
FINDING_CATEGORY = "hard_interruption"

# The text behind the info icon, kept here so it is maintained in one place
# alongside the thresholds it explains. Short on purpose: a long note beside a
# figure is read by nobody, and the three sentences that matter are what counts,
# what does not, and how far the number can be trusted.
EXPLANATION = (
    "Gezählt wird nur, wenn Sie einsetzen, während Ihr Gegenüber noch etwas zu "
    "sagen hatte. Hörsignale wie „mhm“ und ein Einsatz kurz vor dem Satzende "
    "zählen nicht mit: Sprecherwechsel überlappen sich normalerweise um etwa "
    "200 Millisekunden (Stivers et al., 2009). Ab wann eine Überlappung als "
    "Unterbrechung empfunden wird, ist von Person zu Person verschieden, "
    "deshalb ist das hier eine Orientierung und kein Urteil."
)


class TrafficLight(str, Enum):
    """The three-step reading of the count, governed by ADR 0078. The colours
    point, they do not grade (ADR 0078's sixth condition): green = nothing needs
    attention today (not "well done"), yellow = worth a second look, red = look
    here first.
    """

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


LABELS: dict[TrafficLight, str] = {
    TrafficLight.GREEN: "im üblichen Rahmen",
    TrafficLight.YELLOW: "erhöht",
    TrafficLight.RED: "deutlich erhöht",
}


def light_steps() -> list[dict[str, str | None]]:
    """The three steps written out, so the interface can show the whole scale.
    Built from the constants so a recalibration reaches the legend too. Same
    shape as `intonation.liveliness_steps`: `step`, `label`, `range`, `light`.
    """
    return [
        _step(TrafficLight.GREEN, _step_label(0, GREEN_MAX_COUNT)),
        _step(TrafficLight.YELLOW, _step_label(GREEN_MAX_COUNT + 1, YELLOW_MAX_COUNT)),
        _step(TrafficLight.RED, f"ab {YELLOW_MAX_COUNT + 1}"),
    ]


def _step(light: TrafficLight, span: str) -> dict[str, str | None]:
    return {
        "step": light.value,
        "label": LABELS[light],
        "range": span,
        "light": light.value,
    }


def _step_label(low: int, high: int) -> str:
    return str(low) if low == high else f"{low} bis {high}"


class Kind(str, Enum):
    """What one overlapping start was. Only HARD produces a Finding."""

    BACKCHANNEL = "backchannel"
    TERMINAL = "terminal"
    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True)
class Segment:
    """One utterance on the Session's timeline, as this module needs it. Not
    `calls.Utterance`: that module imports this one, so it would be a cycle.
    """

    speaker: str          # "user" or "persona"
    offset_ms: int
    duration_ms: int
    # True on a Persona segment whose reply was trimmed back to the part the
    # user actually heard (ADR 0035). The single reliable trace that the
    # Persona had more to say.
    interrupted: bool = False
    # How long this segment's audio would have run had nobody cut in. Equal to
    # `duration_ms` on everything except a trimmed Persona reply; None where
    # the caller does not know it, which falls back to the same.
    dispatched_ms: int | None = None

    @property
    def end_ms(self) -> int:
        """Where this segment stops being heard. On a trimmed Persona segment
        that is the played position the client reported, not the end of the
        audio (which is `dispatched_end_ms`)."""
        return self.offset_ms + self.duration_ms

    @property
    def dispatched_end_ms(self) -> int:
        """Where this segment's audio would have stopped; what "the Persona
        still had this much to say" is measured against. Not `end_ms`, which is
        cut back to the heard part and would measure only the barge-in delay."""
        return self.offset_ms + (self.duration_ms if self.dispatched_ms is None else self.dispatched_ms)


@dataclass(frozen=True)
class Event:
    """One overlapping start, classified."""

    kind: Kind
    # Where the user began speaking, on the Session's timeline. This is what a
    # Finding's offset points at and what the transcript is scrolled to.
    offset_ms: int
    # How much Persona audio was still outstanding at that moment.
    remaining_ms: int
    duration_ms: int      # how long the user's utterance ran


@dataclass(frozen=True)
class Report:
    """What one Session's overlaps amount to."""

    events: tuple[Event, ...]
    persona_turns: int
    # (start, end) of every segment, for the call's length.
    spans: tuple[tuple[int, int], ...] = ()

    @property
    def hard(self) -> tuple[Event, ...]:
        """The interruptions proper: the Persona had more to say and lost it."""
        return tuple(e for e in self.events if e.kind is Kind.HARD)

    @property
    def soft(self) -> tuple[Event, ...]:
        """Overlaps that cost the Persona nothing. Reported, not counted."""
        return tuple(e for e in self.events if e.kind is Kind.SOFT)

    @property
    def backchannels(self) -> tuple[Event, ...]:
        """Short signals given while the other side kept the floor. Reported
        beside the interruptions, never offset against them -- that would invent
        a trade nothing supports.
        """
        return tuple(e for e in self.events if e.kind is Kind.BACKCHANNEL)

    @property
    def call_ms(self) -> int:
        """How long the call ran, first segment to last. Context for the count
        only; kept out of the traffic light on purpose (see the thresholds).
        """
        if not self.spans:
            return 0
        return max(end for _, end in self.spans) - min(start for start, _ in self.spans)

    def detail(self) -> dict:
        """Everything stored with the measurement besides its value, for the live
        path and the backfill alike. The light is deliberately **not** stored: a
        reading is derived on every read (ADR 0091), by `readings.py` from
        `hard_offsets_ms`, so a recalibration reaches old Sessions.
        """
        return {
            "persona_turns": self.persona_turns,
            "call_ms": self.call_ms,
            "soft_count": len(self.soft),
            "backchannel_count": len(self.backchannels),
            "hard_offsets_ms": [event.offset_ms for event in self.hard],
        }

    @property
    def light(self) -> TrafficLight:
        """The provisional live reading, on the count (see `TrafficLight`).
        `persona_turns` travels as context, never as a divisor. Not stored --
        see `detail`.
        """
        return light_for(len(self.hard))


def light_for(count: int) -> TrafficLight:
    """Which step a count of hard interruptions lands on. The only place the
    comparison is written, for the live path and `readings.py` alike, so a
    recalibration reaches old and new calls alike (ADR 0091)."""
    if count <= GREEN_MAX_COUNT:
        return TrafficLight.GREEN
    if count <= YELLOW_MAX_COUNT:
        return TrafficLight.YELLOW
    return TrafficLight.RED


def classify(timeline: tuple[Segment, ...]) -> Report:
    """Find every overlapping user start and say what it was. First rule wins,
    and the order must not change: a backchannel is checked first so that good
    listening is never counted as interruption.
    """
    persona = [s for s in timeline if s.speaker == "persona"]
    events: list[Event] = []

    for user in (s for s in timeline if s.speaker == "user"):
        overlapped = _overlapped(user, persona)
        if overlapped is None:
            continue
        # Against the dispatched end, never the heard one: see `Segment`.
        remaining = overlapped.dispatched_end_ms - user.offset_ms
        events.append(Event(
            kind=_kind(user, overlapped, remaining),
            offset_ms=user.offset_ms,
            remaining_ms=remaining,
            duration_ms=user.duration_ms,
        ))

    return Report(
        events=tuple(events),
        persona_turns=len(persona),
        spans=tuple((s.offset_ms, s.end_ms) for s in timeline),
    )


def _overlapped(user: Segment, persona: list[Segment]) -> Segment | None:
    """The Persona segment the user started inside of (the last, if windows abut).
    Tested against the *dispatched* end, never the heard one: the heard end sits
    just after the user's start on a different clock, so VAD padding error would
    push the start outside and the hardest interruptions would vanish unnoticed.
    """
    inside = [p for p in persona if p.offset_ms <= user.offset_ms < p.dispatched_end_ms]
    return inside[-1] if inside else None


def finding_description(event: Event) -> str:
    """The Finding's text for one hard interruption. One place for both writers
    (`session.persistence` and `scripts/backfill_interruptions.py`).
    """
    return (
        f"Sie haben zu sprechen begonnen, während Ihr Gegenüber noch "
        f"{round(event.remaining_ms / 1000, 1)} Sekunden zu sagen hatte."
    )


def _kind(user: Segment, persona: Segment, remaining_ms: int) -> Kind:
    """Which of the four an overlap is. Order matters; see `classify`."""
    # 1. A short utterance the Persona did not lose anything over. The user was
    #    signalling that they were listening.
    if user.duration_ms < BACKCHANNEL_MAX_MS and not persona.interrupted:
        return Kind.BACKCHANNEL

    # 2. Started as the line was ending anyway. Ordinary turn-taking.
    if remaining_ms <= TERMINAL_WINDOW_MS:
        return Kind.TERMINAL

    # 3. The Persona was cut off with real audio still outstanding: it had more
    #    to say and did not get to say it. This is the event the goal is about.
    if persona.interrupted and remaining_ms >= YIELD_WINDOW_MS:
        return Kind.HARD

    # 4. Started well inside the line, but nothing was lost: everything the
    #    Persona had to say was heard. Competing overlap, low weight.
    return Kind.SOFT
