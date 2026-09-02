"""Generating the post-call wrap-up (ADR 0049).

The model is given the transcript and the statistics already measured, and is
asked to interpret them -- never to produce numbers of its own, and never to
judge one against a norm nobody measured (ADR 0051). Its citations are checked
against the Session, which is what ADR 0004's "traceable" and F-10's "Bezug auf
konkrete Gesprächsstellen" require.

Runs in the async worker (ADR 0018/0019), not in the live path.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session as DbSession

from backend.clients import llm
from backend.db import models as db_models
from backend.db.session import session_scope

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES_EN = {"de": "German"}

# The wrap-up's own vocabulary -> the schema's. The model is prompted in German
# and answers with "staerke"/"verbesserung" (the same words the frontend reads
# back out of the API), while feedback_point.kind is English and constrained to
# POINT_KINDS. backend/api/sessions.py holds the inverse.
_POINT_KIND = {"staerke": db_models.POINT_STRENGTH,
               "verbesserung": db_models.POINT_IMPROVEMENT}
# A fenced ```json block is the most common way a small model wraps structured
# output despite being told not to; unwrap it rather than failing the parse.
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class _Punkt(BaseModel):
    text: str
    turn_id: int | None = None


class _Wrapup(BaseModel):
    """Strengths and improvements as two lists, not one list with a label.

    Asked for separately so they cannot compete for a single budget: given one
    list and any notion of "enough points", the model spends the count on
    improvements and tops it up with a token strength, which lets the quota
    decide the feedback instead of the call.
    """

    zusammenfassung: str
    staerken: list[_Punkt] = []
    verbesserungen: list[_Punkt] = []

    @property
    def punkte(self) -> list[tuple[str, _Punkt]]:
        """Every point as (art, point), strengths first -- the display order."""
        return [("staerke", p) for p in self.staerken] + [
            ("verbesserung", p) for p in self.verbesserungen
        ]


def generate_feedback(session_id: int) -> None:
    """Job entry point: build and store one Session's Feedback.

    Synchronous, because RQ jobs are; the LLM client underneath is async, so
    the event loop lives only for the duration of this call.
    """
    asyncio.run(_generate(session_id))


async def _generate(session_id: int) -> None:
    with session_scope() as db:
        session = db.get(db_models.Session, session_id)
        if session is None:
            raise LookupError(f"Session {session_id} does not exist")
        _mark(db, session_id, "running")
        dossier, valid_turns = _dossier(session)
        language = _LANGUAGE_NAMES_EN.get(session.sprache_code, session.sprache_code)

    try:
        wrapup = await _ask(dossier, language)
    except Exception as e:
        logger.exception("Feedback generation failed for session %d", session_id)
        with session_scope() as db:
            _mark(db, session_id, "failed", str(e))
        raise

    with session_scope() as db:
        _store(db, session_id, wrapup, valid_turns)
        _mark(db, session_id, "done")
    logger.info("Feedback stored for session %d (%d points)", session_id, len(wrapup.punkte))


# --- Prompt ---------------------------------------------------------------


def _dossier(session: db_models.Session) -> tuple[str, set[int]]:
    """The Session as the model sees it, plus the Turn ids it is allowed to cite.

    Two blocks: the call's measured statistics and the transcript on its
    timeline, both rendered as plain statements of fact so the model's job is
    visibly to explain the numbers rather than to produce them (ADR 0049).

    No target ranges are supplied, because none were measured (ADR 0051). The
    model is told as much, so it reports a figure it cannot place instead of
    inventing the norm we declined to invent.
    """
    lines = ["Measured statistics for this call (established fact):"]
    lines += [
        f"    {m.metric_type.name}: {float(m.value):.1f} {m.metric_type.unit or ''}".rstrip()
        for m in session.measurements
    ]

    lines.append("Transcript, timestamped from the start of the call:")
    turn_ids: set[int] = set()
    for turn in sorted(session.turns, key=lambda t: t.seq_index):
        speaker = "User" if turn.speaker == db_models.SPEAKER_USER else "Caller"
        lines.append(
            f'    [turn_id={turn.turn_id}] {_timestamp(turn.start_offset_ms)} '
            f'{speaker}: "{turn.transcript}"'
        )
        turn_ids.add(turn.turn_id)
    return "\n".join(lines), turn_ids


def _timestamp(offset_ms: int) -> str:
    """A position on the Session's timeline, as mm:ss."""
    seconds = round(offset_ms / 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _messages(dossier: str, language: str) -> list[dict[str, str]]:
    """The prompt. English per ADR 0043; the Feedback itself is in `language`.

    "Be concrete" is itself an abstraction, and a small model (ADR 0011)
    answers an abstract brief with the safest thing it can say -- a generality
    nobody can dispute. So the brief names the parts a point is made of, shows
    a rejected and an accepted one, and gives the model a test to throw its
    own points out with. The limits of ADR 0049 and ADR 0051 are unchanged.

    Form follows from the same fact. A small model loses a rule that sits in
    the middle of a paragraph, so each rule is numbered and lives under the
    heading for the decision it governs, and the three it breaks most often --
    output language, untranslated keys, nothing outside the JSON -- are
    repeated at the very end, where recency is worth most. The rules about
    quotation marks exist because a verbatim quote is the one thing in this
    task that can break the JSON.
    """
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
        "M1. Turns marked 'User' are the trainee. Turns marked 'Caller' are a "
        "simulated conversation partner: never the subject of your feedback, "
        "never praised, never criticised, never addressed.\n"
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
        "say what it would mean for the caller, or leave it out.\n"
        "F3. The Caller is a machine and needs time to answer. Gaps between "
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
        "P2. Effect. What those words did to the caller at that point in the "
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
        "Specific -- write points like this: 'At 02:14 the caller asked when "
        "they would hear back, and you answered that you would look into it "
        "and see what could be done -- a process, where they had asked for a "
        "date. Something like „I will come back to you by Friday with a firm "
        "appointment“ would have given them something to hold on to.'\n"
        "\n"
        "# Never\n"
        "N1. No score, grade, rating, percentage, or star of any kind, and no "
        "word that works as one ('solid overall', 'a strong call').\n"
        "N2. No advice without a quotation or a figure behind it.\n"
        "N3. No markdown, no headings, no bullet characters, no line breaks "
        "inside the JSON strings.\n"
        "N4. No text of any kind before or after the JSON object.\n"
        "\n"
        "# Output\n"
        "Answer with a single JSON object and nothing else -- no prose, no "
        "explanation, no markdown fence.\n"
        "O1. Use exactly these three keys, spelled exactly like this, in this "
        "order, all three always present: zusammenfassung, staerken, "
        "verbesserungen. The keys are identifiers, not text: never translate "
        "them, never add a key.\n"
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
        "a zusammenfassung saying that there is nothing to review, and leave "
        "both lists empty.\n"
        "\n"
        "Shape:\n"
        '{"zusammenfassung": "2-4 sentences: what the caller wanted, how the '
        'trainee handled it, and where the call ended up", '
        '"staerken": [{"text": "one thing the trainee did well, built from '
        'P1 and P2", "turn_id": <id, or null>}], '
        '"verbesserungen": [{"text": "one thing to do differently, built from '
        'P1, P2 and P3, ending in the sentence to say instead", '
        '"turn_id": <id, or null>}]}\n'
        "\n"
        "# Before you answer, check silently\n"
        "Every point quotes this call or a given figure with its timestamp; "
        "every improvement ends in a full sentence to say; no figure appears "
        "that was not given to you; no point would survive being moved to "
        "another call.\n"
        "\n"
        f"The three keys stay in English. Every value is written in {language}. "
        "Your entire answer is the JSON object, starting with { and ending "
        "with }."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": dossier or "(The call contains no utterances.)"},
    ]


# --- Model call and validation --------------------------------------------


async def _ask(dossier: str, language: str) -> _Wrapup:
    """One attempt plus one retry, then a narrative-only fallback (ADR 0049).

    A response that never validates still produces Feedback -- the summary
    without its evidence links -- because showing the user nothing is worse.
    """
    messages = _messages(dossier, language)
    raw = ""
    for attempt in range(2):  # initial attempt + one retry
        raw = await llm.complete(messages)
        try:
            return _Wrapup.model_validate_json(_unwrap(raw))
        except (ValidationError, ValueError) as e:
            logger.warning("Wrap-up did not validate (attempt %d): %s", attempt + 1, e)
    logger.warning("Falling back to a narrative-only wrap-up")
    return _Wrapup(zusammenfassung=_unfenced_text(raw))


def _unwrap(raw: str) -> str:
    """The JSON object out of whatever the model wrapped it in."""
    fenced = _FENCE_RE.search(raw)
    candidate = fenced.group(1) if fenced else raw
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the response")
    return candidate[start:end + 1]


def _unfenced_text(raw: str) -> str:
    """The model's prose, for the fallback: readable even though it isn't JSON."""
    stripped = _FENCE_RE.sub("", raw).strip()
    return stripped or "Für dieses Gespräch konnte kein Feedback erzeugt werden."


# --- Storage --------------------------------------------------------------


def _store(db: DbSession, session_id: int, wrapup: _Wrapup, turn_ids: set[int]) -> None:
    """Replace this Session's Feedback with the generated one.

    A point citing a Turn that is not this Session's is stored without the
    citation rather than dropped: the observation may still be sound, but a
    reference the user could follow to the wrong place must not survive.
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
        summary=wrapup.zusammenfassung,
        score=None,  # ADR 0004: qualitative only, no score in the MVP
        created_at=datetime.now(),
    )
    feedback.points = [
        db_models.FeedbackPoint(
            position=index,
            kind=_POINT_KIND[art],
            text=punkt.text,
            turn_id=punkt.turn_id if punkt.turn_id in turn_ids else None,
        )
        for index, (art, punkt) in enumerate(wrapup.punkte)
    ]
    db.add(feedback)


def _mark(db: DbSession, session_id: int, status: str, fehlertext: str | None = None) -> None:
    """Move the Session's feedback job to `status` (ADR 0032)."""
    job = (
        db.query(db_models.AnalysisJob)
        .filter_by(session_id=session_id, kind="feedback")
        .order_by(db_models.AnalysisJob.job_id.desc())
        .first()
    )
    if job is None:
        job = db_models.AnalysisJob(session_id=session_id, kind="feedback", attempts=0)
        db.add(job)
    job.status = status
    job.error_text = fehlertext
    job.updated_at = datetime.now()
    if status == "running":
        job.attempts += 1
