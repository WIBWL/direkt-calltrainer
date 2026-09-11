"""Overlapping speech, classified (F-51, focus goal "Aktives Zuhören").

Pure functions over one Session's timeline: no database, no audio, no model
call, so the whole classification can be tested against constructed timings and
can be re-run over Sessions that were stored long ago.

The question this answers is narrow. Not "was the user rude", which nobody can
read off a timeline, but "how often did they start speaking while the Persona
still had something to say, and did the Persona lose words over it". Everything
else is left to the wrap-up's prose.

Three things about this architecture shape the rules, and none of them is
obvious from the timeline alone:

* A Persona utterance's end is **modelled from the audio that was sent**, not
  observed. The server never learns when the client finished playing, and a
  barge-in does not shorten that window (`orchestrator._note_persona_audio`).
  So "the Persona stopped within half a second" cannot be read off the data:
  the window runs on regardless. What *is* observable is whether the reply was
  trimmed back to the heard part, which is precisely the event of interest --
  the Persona had more to say and did not get to say it.
* Short backchannels never reach the server at all. ADR 0036 raised the
  client's VAD threshold to 500 ms of sustained speech, and anything below that
  is absorbed in the browser. The backchannel rule below is therefore a second
  net rather than the primary one, and it is kept because losing it would mean
  punishing good listening the day that threshold changes.
* The user's own start is derived from the arrival of their recording minus its
  measured duration, so it carries the VAD's padding as error, a few hundred
  milliseconds at most.

Empirically, across the Sessions stored when this was written, the depth of the
eleven overlapping starts fell into a clean gap: three at 34, 58 and 158 ms,
then nothing until 696 ms. TERMINAL_WINDOW_MS sits in that gap.
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

# Where the traffic light changes, in hard interruptions per call.
#
# Counts and not a share, deliberately. A rate divided by Persona turns was
# tried first and produced nonsense at the length these calls actually run: with
# six to nine Persona turns, a single interruption already gives 0.11 to 0.17,
# so any interruption at all landed on the top step and green was unreachable
# except at exactly zero. A count says the same thing without the arithmetic
# pretending to a precision the denominator cannot carry.
#
# PROVISIONAL, and the weakest numbers in this module: nothing has established
# how many interruptions a call of this kind usually holds, so these are
# invented working values. They are why the interface has to speak of an
# orientation rather than a verdict. See the note on `TrafficLight`.
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
    """The three-step reading of the count.

    Governed by ADR 0078, which says what a light on a Kennzahl may claim and
    under which conditions. This one was built before that ADR existed and was
    described here as an unrecorded exception; it is now one of two instances of
    a written pattern, and it meets the conditions: the colour sits on a named
    step, the whole scale travels with it (`steps()`), the step is written out
    in words, the interface says "Einschätzung", and none of it reaches the
    progress view.

    What the colours claim, per ADR 0078's sixth condition. They point, they do
    not grade:

        green    Nothing here needs your attention today. Not "well done".
        yellow   Worth a second look at how the call went.
        red      This is where to look first.

    The weak part is not the pattern but the numbers: GREEN_MAX_COUNT and
    YELLOW_MAX_COUNT are invented working values with nothing behind them, which
    is why the wording stays at an orientation. Nothing else in this module
    depends on the class, so it can be removed by deleting it and its two
    constants.
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
    """The three steps, written out, so the interface can show the scale the
    colour comes from.

    A boundary the user cannot see is a judgement they cannot argue with, which
    is the worst form for a threshold that nothing has validated to take. Built
    from the constants rather than written twice, so a recalibration reaches the
    legend as well as the logic.

    The shape is shared with `intonation.liveliness_steps`: `step` is the
    machine-readable name, `label` how it is said, `range` where it applies and
    `light` a colour where the scale has a direction, null where it has none.
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
    """One utterance on the Session's timeline, as this module needs it.

    Its own type rather than the session layer's `Utterance`: that one carries
    the transcript and lives in a module which imports from this package, so
    reaching for it would close an import cycle. This is also exactly the four
    fields the classification reads, which keeps the test fixtures honest.
    """

    speaker: str          # "user" or "persona"
    offset_ms: int
    duration_ms: int
    # True on a Persona segment whose reply was trimmed back to the part the
    # user actually heard (ADR 0035). The single reliable trace that the
    # Persona had more to say.
    interrupted: bool = False

    @property
    def end_ms(self) -> int:
        """Where this segment stops. For a Persona segment that is the end of
        the audio that was *sent*, not of what was heard (see the module
        docstring)."""
        return self.offset_ms + self.duration_ms


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
    # (start, end) of every segment, for the call's length. Kept rather than a
    # single duration so the report stays a description of the timeline it was
    # built from.
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
        """Short signals given while the other side kept the floor.

        Reported alongside the interruptions and never against them. They are
        listening made audible, which is the other half of the goal this metric
        serves, and a figure that only ever counted the failures would describe
        an attentive call and an absent one identically.

        They are not offset against the count either. That would invent a trade
        ("two signals make up for one interruption") which nothing supports.
        """
        return tuple(e for e in self.events if e.kind is Kind.BACKCHANNEL)

    @property
    def call_ms(self) -> int:
        """How long the call ran, from the first segment to the last.

        Context for the count and nothing more: the figure is per call, and how
        long that call was is exactly what a reader needs to weigh it. It stays
        out of the traffic light on purpose -- dividing by it was tried and put
        a single interruption on the top step of a short call.
        """
        if not self.spans:
            return 0
        return max(end for _, end in self.spans) - min(start for start, _ in self.spans)

    def detail(self) -> dict:
        """Everything that travels with the measurement besides its value.

        One function rather than a dict built at each write site: the live path
        and the backfill script both store this, and when they were written
        separately the second silently lacked two of the fields, which showed up
        as blank context in the interface.

        Nothing in here enters the figure or the traffic light. It is what lets
        a reader weigh the count: how long the call ran, how many replies there
        were to cut into, and how much listening was audible.
        """
        return {
            "persona_turns": self.persona_turns,
            "call_ms": self.call_ms,
            "soft_count": len(self.soft),
            "backchannel_count": len(self.backchannels),
            "light": self.light.value,
            "hard_offsets_ms": [event.offset_ms for event in self.hard],
        }

    @property
    def light(self) -> TrafficLight:
        """The provisional reading, on the count. See `TrafficLight`.

        `persona_turns` is kept on this report and travels in the measurement's
        detail as context -- three interruptions in a four-turn call and three
        in a forty-turn call are different situations, and a reader can see
        that for themselves. It is deliberately not divided into the figure:
        that was tried and produced a scale on which one interruption was
        already the top step (see the note on the thresholds above).
        """
        count = len(self.hard)
        if count <= GREEN_MAX_COUNT:
            return TrafficLight.GREEN
        if count <= YELLOW_MAX_COUNT:
            return TrafficLight.YELLOW
        return TrafficLight.RED


def classify(timeline: tuple[Segment, ...]) -> Report:
    """Find every overlapping user start and say what it was.

    The rules are applied in order and the first match wins, so a short
    utterance that cost the Persona nothing is a backchannel before it can be
    anything else. That order is the part that must not be rearranged: it is
    what keeps good listening from being counted as interruption.
    """
    persona = [s for s in timeline if s.speaker == "persona"]
    events: list[Event] = []

    for user in (s for s in timeline if s.speaker == "user"):
        overlapped = _overlapped(user, persona)
        if overlapped is None:
            continue
        remaining = overlapped.end_ms - user.offset_ms
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
    """The Persona segment the user started inside of, if any.

    The last one, in the event of several: Persona windows are modelled from
    dispatched audio and can abut, and the user started inside the one that was
    still running.
    """
    inside = [p for p in persona if p.offset_ms <= user.offset_ms < p.end_ms]
    return inside[-1] if inside else None


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
