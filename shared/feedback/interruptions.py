"""Overlapping speech, classified (F-51). A Persona's end is modelled from the
dispatched audio; `interrupted` is the reliable sign it lost words."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Only TERMINAL_WINDOW_MS is from the literature; the rest are working values
# to calibrate once the pilot has data.

# Stivers et al. (2009): turns typically overlap or gap by ~200 ms.
TERMINAL_WINDOW_MS = 200

# Less outstanding audio than this is a rounding artefact, not an interruption.
YIELD_WINDOW_MS = 500

# Shorter utterances that cost the Persona nothing read as backchannels.
BACKCHANNEL_MAX_MS = 1000

# A count, not a rate per Persona turn: one interruption in 6-9 turns already
# hit the top step. Provisional.
GREEN_MAX_COUNT = 0
YELLOW_MAX_COUNT = 2

COUNT_KEY = "interruptions"
FINDING_CATEGORY = "hard_interruption"

EXPLANATION = (
    "Gezählt wird nur, wenn Sie einsetzen, während Ihr Gegenüber noch etwas zu "
    "sagen hatte. Hörsignale wie „mhm“ und ein Einsatz kurz vor dem Satzende "
    "zählen nicht mit: Sprecherwechsel überlappen sich normalerweise um etwa "
    "200 Millisekunden (Stivers et al., 2009). Ab wann eine Überlappung als "
    "Unterbrechung empfunden wird, ist von Person zu Person verschieden, "
    "deshalb ist das hier eine Orientierung und kein Urteil."
)


class TrafficLight(str, Enum):
    """Directs attention, does not grade (ADR 0078): green = nothing needs
    attention, yellow = worth a second look, red = look here first."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


LABELS: dict[TrafficLight, str] = {
    TrafficLight.GREEN: "im üblichen Rahmen",
    TrafficLight.YELLOW: "erhöht",
    TrafficLight.RED: "deutlich erhöht",
}


def light_steps() -> list[dict[str, str | None]]:
    """The whole scale, built from the constants (ADR 0078)."""
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
    BACKCHANNEL = "backchannel"
    TERMINAL = "terminal"
    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True)
class Segment:
    """Not `calls.Utterance`, which imports this module."""

    speaker: str
    offset_ms: int
    duration_ms: int
    interrupted: bool = False
    dispatched_ms: int | None = None

    @property
    def end_ms(self) -> int:
        """Where it stops being heard; trimmed on a cut Persona reply."""
        return self.offset_ms + self.duration_ms

    @property
    def dispatched_end_ms(self) -> int:
        """Where the audio would have stopped. "Still had this much to say" is
        measured against this; `end_ms` would measure only barge-in delay."""
        return self.offset_ms + (self.duration_ms if self.dispatched_ms is None else self.dispatched_ms)


@dataclass(frozen=True)
class Event:
    kind: Kind
    offset_ms: int
    remaining_ms: int
    duration_ms: int


@dataclass(frozen=True)
class Report:
    events: tuple[Event, ...]
    persona_turns: int
    spans: tuple[tuple[int, int], ...] = ()

    @property
    def hard(self) -> tuple[Event, ...]:
        return tuple(e for e in self.events if e.kind is Kind.HARD)

    @property
    def soft(self) -> tuple[Event, ...]:
        return tuple(e for e in self.events if e.kind is Kind.SOFT)

    @property
    def backchannels(self) -> tuple[Event, ...]:
        """Reported beside the interruptions, never offset against them."""
        return tuple(e for e in self.events if e.kind is Kind.BACKCHANNEL)

    @property
    def call_ms(self) -> int:
        """Context only; never part of the light."""
        if not self.spans:
            return 0
        return max(end for _, end in self.spans) - min(start for start, _ in self.spans)

    def detail(self) -> dict:
        """The stored detail. Never the light: it is derived on read (ADR 0091)."""
        return {
            "persona_turns": self.persona_turns,
            "call_ms": self.call_ms,
            "soft_count": len(self.soft),
            "backchannel_count": len(self.backchannels),
            "hard_offsets_ms": [event.offset_ms for event in self.hard],
        }

    @property
    def light(self) -> TrafficLight:
        return light_for(len(self.hard))


def light_for(count: int) -> TrafficLight:
    """The only place the comparison is written (ADR 0091)."""
    if count <= GREEN_MAX_COUNT:
        return TrafficLight.GREEN
    if count <= YELLOW_MAX_COUNT:
        return TrafficLight.YELLOW
    return TrafficLight.RED


def classify(timeline: tuple[Segment, ...]) -> Report:
    """First rule wins, and the order must not change: backchannels come first
    so good listening is never counted as interruption."""
    persona = [s for s in timeline if s.speaker == "persona"]
    events: list[Event] = []

    for user in (s for s in timeline if s.speaker == "user"):
        overlapped = _overlapped(user, persona)
        if overlapped is None:
            continue
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
    """The Persona segment the user started inside (the last, if windows abut).
    Against the dispatched end: the heard end is on another clock, and VAD error
    would let the hardest interruptions vanish."""
    inside = [p for p in persona if p.offset_ms <= user.offset_ms < p.dispatched_end_ms]
    return inside[-1] if inside else None


def finding_description(event: Event) -> str:
    """The Finding's text for one hard interruption."""
    return (
        f"Sie haben zu sprechen begonnen, während Ihr Gegenüber noch "
        f"{round(event.remaining_ms / 1000, 1)} Sekunden zu sagen hatte."
    )


def _kind(user: Segment, persona: Segment, remaining_ms: int) -> Kind:
    # 1. Short, and the Persona lost nothing: a listening signal.
    if user.duration_ms < BACKCHANNEL_MAX_MS and not persona.interrupted:
        return Kind.BACKCHANNEL

    # 2. Started as the line was ending anyway. Ordinary turn-taking.
    if remaining_ms <= TERMINAL_WINDOW_MS:
        return Kind.TERMINAL

    # 3. Cut off with real audio outstanding.
    if persona.interrupted and remaining_ms >= YIELD_WINDOW_MS:
        return Kind.HARD

    # 4. Overlapped, but nothing was lost.
    return Kind.SOFT
