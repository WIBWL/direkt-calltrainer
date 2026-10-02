"""Generating the post-call wrap-up in the async worker (ADR 0049, 0018/0019).
The model interprets measured statistics, never produces or grades figures
(ADR 0051). One call writes all six fields, incl. phase_language (ADR 0056),
tone_fit (ADR 0079) and pressure_turns (ADR 0081, read by `segments.py`).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session as DbSession

from backend.clients import llm
from backend.db import models as db_models
from backend.db.seed_data import FOCUS_GOALS
from backend.db.session import session_scope
from backend.feedback import jobs, metrics, segments, stored

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES_EN = {"de": "German", "en": "English"}

# The two wrap-ups written here rather than by the model, which answered them
# in the prompt's English (ADR 0011). Keyed by the prompt's language name;
# unknown languages fall back to German, the pilot's language.
_NOTHING_SAID = {
    "German": "In diesem Training wurde nicht gesprochen. Es gibt daher nichts auszuwerten.",
    "English": "Nothing was said in this training, so there is nothing to review.",
}
_NO_WRAPUP = {
    "German": "Für dieses Gespräch konnte kein Feedback erzeugt werden.",
    "English": "No feedback could be written for this call.",
}


def _in_language(texts: dict[str, str], language: str) -> str:
    """One of the tables above, in `language` or in German."""
    return texts.get(language, texts["German"])


class _Point(BaseModel):
    text: str
    turn_id: int | None = None
    # Which of F-62's focus goals the point is about (ADR 0080). An unknown
    # key is dropped at storage (`_goal_ids`), not rejected here: the
    # observation is worth more than its tag.
    goal: str = ""


class _Wrapup(BaseModel):
    """Strengths and improvements as two lists, not one list with a label, so
    they cannot compete for one budget (the model would spend it on improvements
    plus a token strength).
    """

    summary: str
    # F-42. Defaulted rather than required: it is the newest thing the prompt
    # asks for and the one a small model is likeliest to drop, and losing a
    # whole wrap-up over a missing paragraph would be the wrong trade.
    phase_language: str = ""
    # Whether the register suited the occasion. Defaulted on the same grounds.
    tone_fit: str = ""
    # The partner's utterances where the trainee was under pressure (ADR 0081).
    # Ids, never shown; they decide the segment measurements' stretches.
    # `None` = nobody judged (key missing, or fallback); `[]` = judged, nothing
    # pressing. Keep the two apart -- `turn.pressed` stores NULL vs False, and
    # collapsing them broke `scripts/inspect_pressure_segments.py` once.
    pressure_turns: list[int] | None = None
    strengths: list[_Point] = []
    improvements: list[_Point] = []

    @property
    def points(self) -> list[tuple[str, _Point]]:
        """Every point as (kind, point), strengths first -- the display order."""
        return [(db_models.POINT_STRENGTH, p) for p in self.strengths] + [
            (db_models.POINT_IMPROVEMENT, p) for p in self.improvements
        ]


def generate_feedback(session_id: int) -> None:
    """Job entry point: build and store one Session's Feedback.

    Synchronous, because RQ jobs are; the LLM client underneath is async, so
    the event loop lives only for the duration of this call.
    """
    asyncio.run(_generate(session_id))


async def _generate(session_id: int) -> None:
    # The whole job sits inside one failure boundary: the post-call screen
    # polls on this job's status, so anything that raises has to close the row.
    session_exists = False
    try:
        with session_scope() as db:
            session = db.get(db_models.Session, session_id)
            if session is None:
                raise LookupError(f"Session {session_id} does not exist")
            session_exists = True
            jobs.mark(db, session_id, db_models.JOB_RUNNING)
            dossier, valid_turns = _dossier(session)
            language = _LANGUAGE_NAMES_EN.get(session.language_code, session.language_code)
            # Read inside the transaction, like everything else here: the model
            # call below runs with no database handle open (ADR 0070).
            reverse = session.scenario.reverse

        # A call with nothing in it is answered here: O5 asks the model for
        # this sentence, but it is the one case where there is nothing to
        # write and no reason to spend a model call finding that out.
        wrapup = (
            _Wrapup(summary=_in_language(_NOTHING_SAID, language))
            if not valid_turns
            else await _ask(dossier, language, reverse)
        )

        with session_scope() as db:
            _store(db, session_id, wrapup, valid_turns)
            segments.store(db, session_id, wrapup.pressure_turns)
            jobs.mark(db, session_id, db_models.JOB_DONE)
        logger.info("Feedback stored for session %d (%d points)", session_id, len(wrapup.points))
    except Exception as e:
        logger.exception("Feedback generation failed for session %d", session_id)
        # `jobs.mark` creates the row where it finds none, so a Session that
        # does not exist must not reach it.
        if session_exists:
            try:
                with session_scope() as db:
                    jobs.mark(db, session_id, db_models.JOB_FAILED, str(e))
            except Exception:  # pylint: disable=broad-exception-caught
                # Re-raising here would lose the original error; the client
                # falls back to its own timeout instead.
                logger.exception("Could not mark feedback job failed for session %d", session_id)
        raise


# --- Prompt ---------------------------------------------------------------


def _dossier(session: db_models.Session) -> tuple[str, set[int]]:
    """The Session as the model sees it, plus the Turn ids it is allowed to cite.
    Statistics (no target ranges, ADR 0051; loudness described, not quoted) and
    the timestamped transcript. In a reverse the partner is labelled `Agent`,
    since the prompt's rules on who is judged key on that label (ADR 0070).
    """
    reverse = session.scenario.reverse
    lines = _occasion(session.scenario)
    lines.append("Measured statistics for this call (established fact):")
    # Whole-call rows only: the segment rows (ADR 0081) from a previous run
    # would otherwise show the same metric three times with three values.
    lines += [
        f"    {m.metric_type.name}: {float(m.value):.1f} {m.metric_type.unit or ''}".rstrip()
        for m in stored.whole_call(session)
        if m.metric_type.key != metrics.LOUDNESS_KEY
    ]
    course = _loudness_course(session)
    if course:
        lines.append(f"    {course}")

    casting = _casting(reverse)
    if reverse:
        lines.append(
            f"In this call the trainee was the one who rang; the {casting.partner} "
            "answered the phone on the company's side."
        )
    lines.append("Transcript, timestamped from the start of the call:")
    turn_ids: set[int] = set()
    for turn in stored.ordered_turns(session):
        if turn.speaker == db_models.SPEAKER_USER:
            speaker = "User"
        else:
            speaker = casting.partner
        lines.append(
            f'    [turn_id={turn.turn_id}] {_timestamp(turn.start_offset_ms)} '
            f'{speaker}: "{turn.transcript}"'
        )
        turn_ids.add(turn.turn_id)
    return "\n".join(lines), turn_ids


def _occasion(scenario: db_models.Scenario) -> list[str]:
    """What kind of call this was, for tone_fit (ADR 0079), from the Scenario's
    English prompt fields. The success criterion is withheld -- a result, not an
    occasion -- and since migration `3ce81b27af40` it sits inside `call_goal`,
    so it is cut off there (`_goal_without_criterion`), never the whole goal.
    """
    lines = [
        "The occasion of this call (established fact, not something to assess):",
        f"    Situation: {scenario.description}",
    ]
    wanted = _goal_without_criterion(scenario)
    if wanted:
        lines.append(f"    What the caller wanted: {wanted}")
    lines.append("")
    return lines


# Where the merged `call_goal` stops being the goal and starts being the
# criterion. A seed convention rather than a schema one: all 17 seeded goals end
# on this sentence, and `tests/test_wrapup_prompt.py` checks that against the
# real seed, so the split cannot quietly stop working when one is reworded.
_SETTLEMENT_MARKER = "The matter is settled when"


def _goal_without_criterion(scenario: db_models.Scenario) -> str:
    """The call goal without the sentence saying when it counts as met. An
    authored goal has none and goes in whole; a goal that is only the criterion
    yields "" and its line is left out.
    """
    head, marker, _ = (scenario.call_goal or "").partition(_SETTLEMENT_MARKER)
    return (head if marker else scenario.call_goal or "").strip()


def _loudness_course(session: db_models.Session) -> str | None:
    """F-37's loudness as a sentence, or None if the call has no curve. A sentence
    from the chart's own function, not the dB span, which the model would quote as
    a level. Whole-call row only: segment rows carry a `curve_db` of their own.
    """
    for measurement in stored.whole_call(session):
        if measurement.metric_type.key != metrics.LOUDNESS_KEY:
            continue
        curve = (measurement.detail_json or {}).get("curve_db")
        if curve:
            return metrics.describe_loudness_course(curve)
    return None


def _timestamp(offset_ms: int) -> str:
    """A position on the Session's timeline, as mm:ss."""
    seconds = round(offset_ms / 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _phase_rules(reverse: bool) -> str:
    """What each of F-42's three phases looks like, from the trainee's side. The
    registers (warm, factual, warm) are the same in a reverse; what each phase is
    made of differs, e.g. stating the concern instead of receiving it (ADR 0070).
    """
    if reverse:
        return (
            "H1. Opening: greeting, giving their own name, and saying what "
            "they are calling about. Warm but clear, because the person who "
            "picked up knows nothing yet. Look for whether the trainee named "
            "themselves, put the concern in a sentence or two instead of "
            "circling it, and said what they wanted out of the call.\n"
            "H2. Core business: the actual matter is worked on. Factual and "
            "specific, because a concern nobody can place does not get "
            "handled. Look for the facts, figures and dates the trainee "
            "brought, for whether they reacted to what was offered instead of "
            "repeating their demand unchanged, and for whether they let the "
            "other side finish. Where the call got difficult, look for "
            "whether the trainee stayed level and kept pressing on the matter "
            "rather than on the person.\n"
            "H3. Closing: confirming what was agreed, then saying goodbye. "
            "Warm again, back to the person. Look for a check that the "
            "trainee actually has what they rang for -- who does what, and by "
            "when -- before the goodbye, and for a sign-off that is more than "
            "the bare word.\n"
        )
    return (
        "H1. Opening: greeting, giving their own name, a little small talk. "
        "Warm and personal, because the caller wants to feel liked and taken "
        "seriously. Look for warmth, for the trainee naming themselves and "
        "being concrete, and for 'I' rather than 'we'.\n"
        "H2. Core business: the actual matter is worked on. Factual, precise "
        "and competent, because the caller now wants their time and their "
        "autonomy respected. Look for plain, specific language, and for "
        "active listening -- letting the caller finish, acknowledging, "
        "summarising back what they said. Where the caller got annoyed, look "
        "for whether the trainee let them keep face and stayed level instead "
        "of matching the irritation.\n"
        "H3. Closing: confirming the solution, then saying goodbye. Warm "
        "again, back to the person. Look for a check that everything is "
        "settled before the goodbye, and for a sign-off that is more than "
        "the bare word.\n"
    )


@dataclass(frozen=True)
class _Casting:
    """Who was on which end of the line (ADR 0070). One record, because the
    prompt's rules name the simulated side by the transcript's own label, so
    the two must be the same word.
    """

    # The transcript's label for the simulated side.
    partner: str
    # The person the trainee spoke to, as a sentence refers to them.
    other: str
    # What the summary opens on: the concern the call was about, named from
    # whichever side brought it.
    wanted: str


_ORDINARY = _Casting(partner="Caller", other="the caller", wanted="the caller wanted")
_REVERSED = _Casting(partner="Agent", other="the agent", wanted="the trainee rang about")


def _casting(reverse: bool) -> _Casting:
    return _REVERSED if reverse else _ORDINARY


def _goal_ids(db: DbSession) -> dict[str, int]:
    """Catalogue key to row id, read from the table the foreign key points into.
    Deactivated goals are included (the statement stays true, ADR 0076); the
    habit goals are excluded, since no single call can show them.
    """
    return {
        goal.key: goal.focus_goal_id
        for goal in db.query(db_models.FocusGoal)
        if goal.key not in _NEVER_ASSIGNED
    }


# Goals about the training habit rather than about a call -- the catalogue's
# `habit` group. Rule A6 tells the model not to assign them; this is the same
# rule where it cannot be ignored.
_NEVER_ASSIGNED = frozenset(goal["id"] for goal in FOCUS_GOALS if goal["group"] == "habit")


def _goal_catalogue() -> str:
    """The focus goals as the prompt lists them, one key and title per line, from
    `seed_data.FOCUS_GOALS`. Written out in full so the model copies a key rather
    than inventing one; the German titles stay untranslated (one wording only).
    """
    return "".join(f"    {goal['id']}: {goal['title']}\n" for goal in FOCUS_GOALS)


def _worked_example(reverse: bool) -> str:
    """The accepted point, shown rather than described. Mirrored for a reverse
    (ADR 0070): the model follows an example's direction, and the ordinary one
    is a trainee who *answered* a call.
    """
    if reverse:
        return (
            "Specific -- write points like this: 'At 02:14 you asked whether "
            "the matter could be looked at soon, and let „ich melde mich“ "
            "stand as the answer -- a promise with no date, where you had "
            "come for one. Something like „Bis wann genau kann ich mit einer "
            "Rückmeldung rechnen?“ would have made that hard to leave "
            "open.'\n"
        )
    return (
        "Specific -- write points like this: 'At 02:14 the caller asked when "
        "they would hear back, and you answered that you would look into it "
        "and see what could be done -- a process, where they had asked for a "
        "date. Something like „I will come back to you by Friday with a firm "
        "appointment“ would have given them something to hold on to.'\n"
    )


def _messages(dossier: str, language: str, reverse: bool = False) -> list[dict[str, str]]:
    """The prompt. English per ADR 0043; the Feedback itself is in `language`.
    `reverse` (ADR 0070) swaps only the partner label, the person addressed and
    the phase block. Rules are numbered under headings, with the three most often
    broken repeated at the end, because a small model (ADR 0011) loses the rest.
    """
    # The same labels `_dossier` wrote, from the same record.
    casting = _casting(reverse)
    partner, other = casting.partner, casting.other
    system = (
        "# Role\n"
        "You are a communication coach. You review one training phone call "
        "and write feedback for the trainee, addressing them directly as "
        '"you".\n'
        "\n"
        "# The material\n"
        "The user message contains everything you are allowed to use: a "
        "transcript with timestamps and turn ids, and statistics measured "
        "from the trainee's speech. Nothing else exists.\n"
        f"M1. Turns marked 'User' are the trainee. Turns marked '{partner}' "
        "are a simulated conversation partner: never the subject of your "
        "feedback, never praised, never criticised, never addressed.\n"
        "M2. Quote only from 'User' turns.\n"
        "M3. The statistics were measured across the whole call. Treat them "
        "as established fact. Their labels are German because that is how "
        "they appear in the material; use them as they are written.\n"
        "\n"
        "# Rules about facts\n"
        "F1. Never estimate, recompute, or invent a figure. No speaking "
        "rates, no counts, no durations beyond the ones given to you. If a "
        "number is not in the material, it does not go in your answer.\n"
        "F2. No target range is given for any statistic, because none has "
        "been established for this group of users. Do not judge a figure "
        "against a norm, do not call one too high, too low, too fast or too "
        "slow, and do not invent a range of your own. Report the figure and "
        f"say what it would mean for {other}, or leave it out.\n"
        f"F3. The {partner} is a machine and needs time to answer. Gaps between "
        "the timestamps are therefore mostly that machine thinking, not the "
        "trainee hesitating. Never read a jump in the timestamps as a "
        "silence, a delay, or an awkward pause on the trainee's part. The "
        "only waiting the trainee is responsible for is what the "
        "Reaktionszeit and Sprechpausen statistics already measure.\n"
        "F4. Never assert anything about the call that the transcript or the "
        "statistics do not show. No motives, no mood, no background.\n"
        "F5. The summary and the phase_language block carry no figures at "
        "all, and above all never one in brackets after a statement "
        "('sachlich (62 %)'). Say the observation in words. Every figure "
        "already stands next to this text on the screen, with what it was "
        "measured from, and one dropped into a sentence reads as the "
        "verdict on it that F2 forbids. Figures belong in a strength, in "
        "an improvement, or where G2 allows one in tone_fit.\n"
        "\n"
        "# How to build a point\n"
        "Your job is to interpret: say what the statistics and the transcript "
        "mean for how this person came across, and what they could do "
        "differently. Every point is assembled from named parts, in this "
        "order.\n"
        "P1. Evidence. The trainee's own words, quoted verbatim from a 'User' "
        "turn, or the measured figure the point rests on -- with the "
        "timestamp of the moment it happened, in the form the material writes "
        "it.\n"
        f"P2. Effect. What those words did to {other} at that point in the "
        "call.\n"
        "P3. Alternative -- improvements only. One sentence the trainee could "
        "have said instead, written out in full, in quotation marks, about "
        "what this call was actually about. A sentence they could read aloud, "
        "not a description of a better approach. It is the last thing in the "
        "text.\n"
        "A strength is P1 + P2 and stops there. An improvement is P1 + P2 + "
        "P3. Keep each point to one to three sentences.\n"
        "\n"
        "# The test each point has to pass\n"
        "T1. Move the finished point, word for word, into the feedback for a "
        "completely different call. If it still fits, it is too general: "
        "rewrite it around the quotation, or drop it.\n"
        "T2. Each point must stand on an observation of its own. Where two "
        "would rest on the same moment or the same statistic, keep the better "
        "one and drop the other. Never restate a point in different words to "
        "lengthen a list.\n"
        "T3. There is no target number of points and no expected balance "
        "between the two kinds. Report every strength the call genuinely "
        "shows and every improvement that rests on its own evidence, however "
        "many that is and whichever list ends up longer. Two well-founded "
        "points are worth more than five padded ones, and either list may be "
        "empty.\n"
        "\n"
        "# The shape of a point\n"
        "Both examples below are about some other call. Copy the shape, never "
        "the content.\n"
        "Too general -- reject a point like this: 'You came across as "
        "friendly and explained things clearly.' It names no moment, no "
        "words, and no consequence, and it would fit any call ever recorded.\n"
        f"{_worked_example(reverse)}"
        "\n"
        "# The goal on a point\n"
        "Every point carries a `goal`: which of the trainee's possible focus "
        "goals it is about. It is what lets somebody see later that the same "
        "thing came up in four of their last eight calls, so it decides "
        "nothing about this wrap-up and everything about whether the point can "
        "be found again.\n"
        "Pick exactly one key from this list, copied character for "
        "character:\n"
        f"{_goal_catalogue()}"
        "A1. The key is an identifier. Never translate it, never invent one, "
        "never write the German title instead.\n"
        "A2. Pick by what the point is *about*, not by which words appear in "
        "it. A point about talking over the caller is active_listening even if "
        "it never uses the word listening.\n"
        "A3. One key, the closest one. Where two would fit, take the one the "
        "point spends most of its words on. Do not split a point in two to "
        "give each half a goal.\n"
        "A4. Write an empty string when nothing on the list fits. That is a "
        "normal answer and a better one than a key that nearly fits: a wrong "
        "key puts this point into somebody's count of a weakness they do not "
        "have. Never force a fit.\n"
        "A5. The goal never changes what the point says. Write the point "
        "first, on its own merits, then label it. If you find yourself "
        "rewording a point so it matches a key, delete the key instead.\n"
        "A6. training_regularity and training_variety are about how often and "
        "how widely somebody trains, which is nothing a single call can show. "
        "Never assign either.\n"
        "\n"
        "# The phase_language block\n"
        "A separate piece of feedback, about one thing only: whether the way "
        "the trainee spoke changed with the phase of the call. A service call "
        "runs through three phases in this order, and the register is meant "
        "to move with them -- warm, then factual, then warm again. Someone "
        "who stays in a single register throughout comes across as less "
        "empathetic even when every answer was correct, and that is the "
        "observation this block exists to make.\n"
        f"{_phase_rules(reverse)}"
        "H4. Work the phase boundaries out yourself from the transcript. They "
        "are consecutive stretches of turns and none of them has a fixed "
        "length. If a phase never happened -- a call that broke off has no "
        "closing -- say so plainly instead of describing one that was not "
        "there (F4).\n"
        "H5. The end of a call shapes what the caller remembers of the whole "
        "of it far more than the middle does. Give the closing more of your "
        "text than the other two phases, and where the closing is the weakest "
        "of the three, make it the phase your suggestion is about.\n"
        "H6. This block is about register, not about results. Whether the "
        "matter was actually solved belongs in strengths and improvements.\n"
        "H7. Every other rule still holds here: quote the trainee's own words "
        "with the timestamp (P1), never grade the call (N1), never measure a "
        f"figure against a norm (F2), and never make the {partner} the subject "
        "(M1).\n"
        "H8. No figures in this block either, exactly as in the summary "
        "(F5). What is observed here is a change of register across the "
        "call, and no number carries that: a percentage dropped into the "
        "paragraph turns a description into a reckoning.\n"
        "\n"
        "# The tone_fit block\n"
        "A separate piece of feedback, about one thing only: whether the way "
        "the trainee sounded suited the occasion this particular call was. "
        "The occasion is given to you at the top of the material. It is the "
        "one question the measurements cannot answer, because the same lively "
        "delivery that carries a sales call is the wrong answer to somebody "
        "who rang up angry, and no measured figure knows which of the two this "
        "was.\n"
        "G1. Start from the occasion, not from the figures. Say in your own "
        "words what this call asked for in the way of tone, and why that "
        "follows from the situation rather than from a general rule about "
        "phone calls.\n"
        "G2. Then say how the trainee actually sounded, and back it with the "
        "transcript: what they said, in their own words, with the timestamp "
        "(P1). Where a given figure supports it you may name that figure, but "
        "the quotation is what carries the observation and the figure is never "
        "on its own.\n"
        "G3. Then say plainly whether the two fit, and where they did not, "
        "which moment shows it. 'Fitting' is not a grade and there is no scale "
        "here: you are describing a relation between a situation and a "
        "delivery, not scoring one against the other.\n"
        "G4. A call where the tone did suit the occasion is a normal and "
        "frequent answer. Say so and show why, in the same detail. Do not "
        "manufacture a mismatch to have something to report.\n"
        "G5. There is no correct register for a kind of call, and you must not "
        "imply one exists. Two people can handle the same complaint well "
        "sounding quite different. What you may say is what this trainee's "
        "delivery would do to this caller in this situation.\n"
        "G6. This block is about how it sounded, not about what was said or "
        "whether the matter was solved. Wording, argument and outcome belong "
        "in strengths and improvements.\n"
        "G7. Do not repeat the phase_language block. That one is about a "
        "change across the call; this one is about the call set against its "
        "occasion. If the only thing you have to say here is that the register "
        "moved or did not move, you have not answered this question.\n"
        "\n"
        "# The pressure_turns list\n"
        "Not feedback, and nobody reads it: a list of ids the application uses "
        "to measure how the trainee spoke while they were under pressure, "
        "against how they spoke the rest of the time.\n"
        f"R1. List the id of every {partner} utterance that put the trainee "
        "under pressure: an objection, a complaint, a refusal, a demand, a "
        "challenge to something they said, or asking again for something they "
        "have already asked for and not been given.\n"
        f"R2. Do not list a {partner} utterance that merely asks something "
        "neutrally, answers, agrees, greets or says goodbye. A question is not "
        "pressure by itself.\n"
        "R3. This describes what the partner did, not how the trainee "
        "handled it. An utterance goes on the list whether the trainee dealt "
        "with it well or badly.\n"
        "R4. An empty list is a normal and frequent answer. A call where "
        "nobody pushed back has no pressure in it, and inventing some would "
        "make the application measure two stretches that are the same stretch.\n"
        "R5. Ids copied character for character from the material, as in O3. "
        "Never guess one, never count one out yourself, and never list a 'User' "
        "id.\n"
        "\n"
        "# Never\n"
        "N1. No score, grade, rating, percentage, or star of any kind, and no "
        "word that works as one ('solid overall', 'a strong call').\n"
        "N2. No advice without a quotation or a figure behind it.\n"
        "N3. No markdown, no headings, no bullet characters, no line breaks "
        "inside the JSON strings.\n"
        "N4. No text of any kind before or after the JSON object.\n"
        "N5. Never write a turn id inside a text value, and never the "
        "word 'turn' with a number after it. The material prefixes "
        "every line with its id so that you can fill in the turn_id field "
        "(O3); in the text a moment is named by its timestamp and nothing "
        "else.\n"
        "\n"
        "# Output\n"
        "Answer with a single JSON object and nothing else -- no prose, no "
        "explanation, no markdown fence.\n"
        "O1. Use exactly these six keys, spelled exactly like this, in this "
        "order, all six always present: summary, phase_language, tone_fit, "
        "pressure_turns, strengths, improvements. The keys are identifiers, "
        "not text: never translate them, never add a key.\n"
        f"O2. Every value you write is in {language}. The keys stay as they "
        "are.\n"
        "O3. turn_id is the id of the utterance the point concerns, copied "
        "character for character from the material, or null. If you cannot "
        "find the id in the material, write null. Never guess one, never "
        "count one out yourself.\n"
        "O4. Inside a string, mark quoted words with the typographic "
        f"quotation marks of {language} (for example „like this“) or with "
        "single quotes. Never a straight double quote: forget the backslash "
        "in front of one and the whole answer is unreadable.\n"
        "O5. If no utterances are listed under the transcript heading, write "
        "a summary saying that there is nothing to review, leave all three "
        "lists empty, and make phase_language and tone_fit empty strings.\n"
        "O6. phase_language is a single paragraph of four to six sentences of "
        f"plain {language} prose: no headings, no bullet characters, no line "
        "breaks, and no phase name used as a label -- name a phase inside a "
        "sentence. Walk the three phases in the order they happened, say for "
        "each one how the trainee actually sounded and quote the words that "
        "show it, then finish with the single change that would help most, "
        "written out as a sentence they could say aloud.\n"
        "O7. tone_fit is a single paragraph of three to five sentences of "
        f"plain {language} prose, following G1 to G3 in that order: what this "
        "occasion asked for in the way of tone, how the trainee actually "
        "sounded with a quoted moment, and whether the two fit. No headings, "
        "no bullet characters, no line breaks.\n"
        "\n"
        "Shape:\n"
        # "what the caller wanted" names the trainee in a reverse and the
        # machine everywhere else, so the one word that flips is spelled out
        # rather than left to be read either way.
        f'{{"summary": "2-4 sentences: what {casting.wanted}, how the '
        'trainee handled it, and where the call ended up", '
        '"phase_language": "one paragraph on how the register moved through '
        'opening, core business and closing, ending in the sentence to say '
        'instead", '
        '"tone_fit": "one paragraph on whether the way the trainee sounded '
        'suited this occasion, built from G1, G2 and G3", '
        f'"pressure_turns": [<ids of the {partner} utterances that put the '
        'trainee under pressure, built from R1 and R2, empty where nobody '
        'pushed back>], '
        '"strengths": [{"text": "one thing the trainee did well, built from '
        'P1 and P2", "turn_id": <id, or null>, "goal": "<one key from the '
        'list, or an empty string>"}], '
        '"improvements": [{"text": "one thing to do differently, built from '
        'P1, P2 and P3, ending in the sentence to say instead", '
        '"turn_id": <id, or null>, "goal": "<one key from the list, or an '
        'empty string>"}]}\n'
        "\n"
        "# Before you answer, check silently\n"
        "Every point quotes this call or a given figure with its timestamp; "
        "every improvement ends in a full sentence to say; no figure appears "
        "that was not given to you; neither the summary nor phase_language "
        "carries a figure or a bracketed number (F5, H8); no point would "
        "survive being moved to "
        "another call; phase_language covers all three phases or names the one "
        "the call never reached, and gives the closing the most room; tone_fit "
        "names what this occasion asked for before it says anything about how "
        "the trainee sounded, and would not fit a call about some other "
        "matter; every goal is a key off the list or an empty string, and no "
        f"point was reworded to match one; every id in pressure_turns is a "
        f"{partner} id from the material and stands for a moment the trainee "
        "was actually pushed.\n"
        "\n"
        f"The six keys stay in English. Every value is written in {language}. "
        "Your entire answer is the JSON object, starting with { and ending "
        "with }."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": dossier or "(The call contains no utterances.)"},
    ]


# --- Model call and validation --------------------------------------------


async def _ask(dossier: str, language: str, reverse: bool = False) -> _Wrapup:
    """One attempt plus one retry, then a narrative-only fallback (ADR 0049).
    Thinking mode: German prose from an English brief on a 4B model (ADR 0011)
    needs the revision pass, and time is free in the worker (ADR 0018/0019).
    """
    messages = _messages(dossier, language, reverse)
    raw = ""
    for attempt in range(2):  # initial attempt + one retry
        raw = await llm.complete(messages, think=True)
        try:
            return _Wrapup.model_validate_json(llm.json_object(raw))
        except (ValidationError, ValueError) as e:
            logger.warning("Wrap-up did not validate (attempt %d): %s", attempt + 1, e)
    logger.warning("Falling back to a narrative-only wrap-up")
    return _Wrapup(summary=_unfenced_text(raw, language))


def _unfenced_text(raw: str, language: str) -> str:
    """The model's prose, for the fallback (ADR 0049). A reply that still looks
    like (truncated) JSON is replaced by the fixed sentence: stored raw, it would
    reach the User as their summary and, having a Feedback row, never be
    requeued by `scripts/requeue_feedback.py`.
    """
    stripped = llm.without_fenced_blocks(raw).strip()
    if not stripped or _looks_like_json(stripped):
        return _in_language(_NO_WRAPUP, language)
    return stripped


def _looks_like_json(text: str) -> bool:
    """Whether this is the model's failed structure rather than its prose.
    Deliberately crude: a leading brace or bracket, or a schema key in JSON
    quotes near the start."""
    if text[:1] in ("{", "["):
        return True
    fields: tuple[str, ...] = tuple(_Wrapup.model_fields)
    return any(f'"{field}"' in text[:200] for field in fields)


# --- Storage --------------------------------------------------------------


# `_dossier` prefixes every line with `[turn_id=12]` so a point can cite it
# in the turn_id field (O3); a 4B model (ADR 0011) copies it into the prose
# too, where P1 asked for the timestamp. N5 forbids it, this takes it back
# out. Marker shapes only -- cutting "in Turn 12" out of a sentence would
# leave it ungrammatical, so that form stays N5's job.
_TURN_MARKER_RE = re.compile(
    r"""
    \s*                                                    # its leading space
    (?:
        [\[(] \s* turn [ _-]? (?:id)? \s* [:=#]? \s* \d+ \s* [\])]  # [turn_id=12]
      | \b turn [ _-]? id \s* [:=#]? \s* \d+                   # turn_id=12
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _without_turn_markers(text: str) -> str:
    """One text value with the transcript's id markers taken back out."""
    cleaned = _TURN_MARKER_RE.sub("", text)
    # It takes its own space with it: close the gap it leaves behind.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.;:!?])", r"\1", cleaned)
    return cleaned.strip()


def _store(db: DbSession, session_id: int, wrapup: _Wrapup, turn_ids: set[int]) -> None:
    """Replace this Session's Feedback with the generated one. A citation of a
    foreign Turn is dropped, the point kept; every text passes
    `_without_turn_markers` here, once, for both screens that read it.
    """
    # Through the ORM, not a bulk delete. The database would carry the points
    # along by itself (feedback_point.feedback_id is ON DELETE CASCADE), but
    # going through the ORM keeps the identity map in step with what was
    # deleted, which a bulk delete in the middle of this transaction would not.
    previous = db.query(db_models.Feedback).filter_by(session_id=session_id).one_or_none()
    if previous is not None:
        db.delete(previous)
        db.flush()
    feedback = db_models.Feedback(
        session_id=session_id,
        summary=_without_turn_markers(wrapup.summary),
        # NULL rather than "" where the model gave us nothing: the frontend
        # leaves the block out entirely then, which is honest about a call
        # nobody analysed for its phases. An empty paragraph would not be.
        phase_language=_without_turn_markers(wrapup.phase_language) or None,
        tone_fit=_without_turn_markers(wrapup.tone_fit) or None,
        score=None,  # ADR 0004: qualitative only, no score in the MVP
        created_at=datetime.now(UTC),
    )
    goal_ids = _goal_ids(db)
    feedback.points = [
        db_models.FeedbackPoint(
            position=index,
            kind=kind,
            text=_without_turn_markers(point.text),
            turn_id=point.turn_id if point.turn_id in turn_ids else None,
            # Unknown keys become NULL rather than raising. The model is asked
            # for one of the catalogue's keys and will occasionally invent one,
            # and a wrap-up is worth more than its tags.
            focus_goal_id=goal_ids.get(point.goal),
        )
        for index, (kind, point) in enumerate(wrapup.points)
    ]
    db.add(feedback)
