"""Generating the post-call wrap-up (ADR 0049).

The model is given the transcript and the statistics already measured, and is
asked to interpret them -- never to produce numbers of its own, and never to
judge one against a norm nobody measured (ADR 0051). Its citations are checked
against the Session, which is what ADR 0004's "traceable" and F-10's "Bezug auf
konkrete Gesprächsstellen" require.

It writes four things, not three: F-42's phase_language paragraph comes out of
the same call as the summary and the two lists. One call rather than a second
one of its own, because the phases are read off the same transcript and a
second round trip would buy nothing but latency and a second way to fail.

The wrap-up is all this job produces. It used to draft the follow-up Scenario
too, once the wrap-up was stored — that now happens only when the User asks for
it, from a route of its own (ADR 0069's amendment, `backend/followups.py`), so
the job has one model call and one thing that can fail.

Runs in the async worker (ADR 0018/0019), not in the live path.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session as DbSession

from backend.clients import llm
from backend.db import models as db_models
from backend.db.session import session_scope
from backend.feedback import jobs, metrics

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES_EN = {"de": "German", "en": "English"}

# The two wrap-ups written here rather than by the model, keyed by the same
# English language name the prompt is built with. O2 asks the model to answer
# in the Session's language and a 4B model (ADR 0011) still hands back the
# English of the rule it is following -- which is exactly what a User saw when
# a call they broke off immediately came back summarised as "nothing to
# review". Neither path reaches the model, so neither can be got wrong.
#
# German for a language we do not know: the pilot runs in German, and a
# sentence in the wrong language beats a KeyError on the one screen that is
# meant to say why there is nothing to read.
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


class _Wrapup(BaseModel):
    """Strengths and improvements as two lists, not one list with a label.

    Asked for separately so they cannot compete for a single budget: given one
    list and any notion of "enough points", the model spends the count on
    improvements and tops it up with a token strength, which lets the quota
    decide the feedback instead of the call.
    """

    summary: str
    # F-42. Defaulted rather than required: it is the newest thing the prompt
    # asks for and the one a small model is likeliest to drop, and losing a
    # whole wrap-up over a missing paragraph would be the wrong trade.
    phase_language: str = ""
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
            jobs.mark(db, session_id, db_models.JOB_DONE)
        logger.info("Feedback stored for session %d (%d points)", session_id, len(wrapup.points))
    except Exception as e:  # pylint: disable=broad-exception-caught
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

    Two blocks: the call's measured statistics and the transcript on its
    timeline, both rendered as plain statements of fact so the model's job is
    visibly to explain the numbers rather than to produce them (ADR 0049).

    No target ranges are supplied, because none were measured (ADR 0051). The
    model is told as much, so it reports a figure it cannot place instead of
    inventing the norm we declined to invent.

    Loudness is the exception: described rather than measured, see below.

    In a reverse (ADR 0070) the simulated side is labelled `Agent` rather than
    `Caller`, and the material says outright that the trainee did the calling.
    The label is not cosmetic: every rule in the prompt about who may be quoted
    and who may not be judged is written against these words, so leaving the
    machine called "Caller" while the trainee *was* the caller is exactly the
    confusion that would put the feedback on the wrong person.
    """
    reverse = session.scenario.reverse
    lines = ["Measured statistics for this call (established fact):"]
    lines += [
        f"    {m.metric_type.name}: {float(m.value):.1f} {m.metric_type.unit or ''}".rstrip()
        for m in session.measurements
        if m.metric_type.key != metrics.LOUDNESS_KEY
    ]
    course = _loudness_course(session)
    if course:
        lines.append(f"    {course}")

    if reverse:
        lines.append(
            "In this call the trainee was the one who rang; the Agent answered "
            "the phone on the company's side."
        )
    lines.append("Transcript, timestamped from the start of the call:")
    turn_ids: set[int] = set()
    for turn in sorted(session.turns, key=lambda t: t.seq_index):
        if turn.speaker == db_models.SPEAKER_USER:
            speaker = "User"
        else:
            speaker = "Agent" if reverse else "Caller"
        lines.append(
            f'    [turn_id={turn.turn_id}] {_timestamp(turn.start_offset_ms)} '
            f'{speaker}: "{turn.transcript}"'
        )
        turn_ids.add(turn.turn_id)
    return "\n".join(lines), turn_ids


def _loudness_course(session: db_models.Session) -> str | None:
    """F-37's loudness as a sentence, or None if the call has no curve.

    The stored value is a dB span (95th percentile minus 5th). Handed over as a
    number, the wrap-up quotes it as a level -- above a chart that deliberately
    shows none. What goes in instead is what that chart says, from the same
    curve and the same parameters, so text and picture cannot contradict.
    """
    for measurement in session.measurements:
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
    """What each of F-42's three phases looks like, from the trainee's side.

    The three registers -- warm, factual, warm -- hold in both castings, and
    the observation the block exists to make is the same one. What differs is
    what each phase is *made of*: someone answering a call opens by receiving a
    concern, someone making one opens by stating it, and the closing that has
    to be checked is a solution offered in the first case and a commitment
    obtained in the second (ADR 0070).
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


def _wanted(reverse: bool) -> str:
    """What the summary opens on: the concern the call was about, named from
    whichever side brought it."""
    return "the trainee rang about" if reverse else "the caller wanted"


def _worked_example(reverse: bool) -> str:
    """The accepted point, shown rather than described.

    Mirrored for a reverse (ADR 0070) because a model shown an example runs in
    its direction: the specific one below is a trainee who *answered* a call,
    and left as it is it invites feedback written for the wrong side of the
    conversation.
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

    `reverse` (ADR 0070) swaps who was on which end of the line. Three things
    move with it and nothing else: the label the simulated side carries in the
    transcript, the words naming the person the trainee was talking *to*, and
    the phase block, whose three registers were written for someone answering a
    call and describe something different for someone making one. Every rule
    about evidence, norms and scores is the same feedback either way, so it is
    written once.

    "Be concrete" is itself an abstraction, and a small model (ADR 0011)
    answers an abstract brief with the safest thing it can say -- a generality
    nobody can dispute. So the brief names the parts a point is made of, shows
    a rejected and an accepted one, and gives the model a test to throw its
    own points out with. The limits of ADR 0049 and ADR 0051 are unchanged.

    The phase_language section (F-42) is the one part not built out of points.
    It asks for prose about a *change* over the call -- warm in the opening,
    factual through the core business, warm again at the close -- which is a
    shape no single figure carries, so it is deliberately not a Measurement.
    N1 still applies to it: describing a register is not grading one.

    Form follows from the same fact. A small model loses a rule that sits in
    the middle of a paragraph, so each rule is numbered and lives under the
    heading for the decision it governs, and the three it breaks most often --
    output language, untranslated keys, nothing outside the JSON -- are
    repeated at the very end, where recency is worth most. The rules about
    quotation marks exist because a verbatim quote is the one thing in this
    task that can break the JSON.
    """
    # The transcript's own label for the simulated side, and the phrase for the
    # person the trainee spoke to. Both are read straight out of the material,
    # so they have to be the words `_dossier` actually wrote.
    partner = "Agent" if reverse else "Caller"
    other = "the agent" if reverse else "the caller"
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
        "O1. Use exactly these four keys, spelled exactly like this, in this "
        "order, all four always present: summary, phase_language, "
        "strengths, improvements. The keys are identifiers, not text: never "
        "translate them, never add a key.\n"
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
        "a summary saying that there is nothing to review, leave both "
        "lists empty, and make phase_language an empty string.\n"
        "O6. phase_language is a single paragraph of four to six sentences of "
        f"plain {language} prose: no headings, no bullet characters, no line "
        "breaks, and no phase name used as a label -- name a phase inside a "
        "sentence. Walk the three phases in the order they happened, say for "
        "each one how the trainee actually sounded and quote the words that "
        "show it, then finish with the single change that would help most, "
        "written out as a sentence they could say aloud.\n"
        "\n"
        "Shape:\n"
        # "what the caller wanted" names the trainee in a reverse and the
        # machine everywhere else, so the one word that flips is spelled out
        # rather than left to be read either way.
        f'{{"summary": "2-4 sentences: what {_wanted(reverse)}, how the '
        'trainee handled it, and where the call ended up", '
        '"phase_language": "one paragraph on how the register moved through '
        'opening, core business and closing, ending in the sentence to say '
        'instead", '
        '"strengths": [{"text": "one thing the trainee did well, built from '
        'P1 and P2", "turn_id": <id, or null>}], '
        '"improvements": [{"text": "one thing to do differently, built from '
        'P1, P2 and P3, ending in the sentence to say instead", '
        '"turn_id": <id, or null>}]}\n'
        "\n"
        "# Before you answer, check silently\n"
        "Every point quotes this call or a given figure with its timestamp; "
        "every improvement ends in a full sentence to say; no figure appears "
        "that was not given to you; no point would survive being moved to "
        "another call; phase_language covers all three phases or names the one "
        "the call never reached, and gives the closing the most room.\n"
        "\n"
        f"The four keys stay in English. Every value is written in {language}. "
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

    A response that never validates still produces Feedback -- the summary
    without its evidence links -- because showing the user nothing is worse.

    Asked in thinking mode: this is the one call that writes paragraphs of
    German prose, from an English brief (ADR 0043) on a 4B model (ADR 0011),
    where agreement and word order come apart in a single pass. The trace is
    the revision pass, and it is free in the worker (ADR 0018/0019).
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
    """The model's prose, for the fallback: readable even though it isn't JSON."""
    stripped = llm.without_fenced_blocks(raw).strip()
    return stripped or _in_language(_NO_WRAPUP, language)


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
    """Replace this Session's Feedback with the generated one.

    A point citing a Turn that is not this Session's is stored without the
    citation rather than dropped: the observation may still be sound, but a
    reference the user could follow to the wrong place must not survive.

    Every text value passes `_without_turn_markers` on the way in: written
    once, read on two screens, so the cleanup belongs here.
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
        score=None,  # ADR 0004: qualitative only, no score in the MVP
        created_at=datetime.now(UTC),
    )
    feedback.points = [
        db_models.FeedbackPoint(
            position=index,
            kind=kind,
            text=_without_turn_markers(point.text),
            turn_id=point.turn_id if point.turn_id in turn_ids else None,
        )
        for index, (kind, point) in enumerate(wrapup.points)
    ]
    db.add(feedback)
