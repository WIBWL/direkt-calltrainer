"""Session/Turn orchestration: the STT -> LLM -> TTS pipeline and its retry policy."""

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from difflib import SequenceMatcher

from kugelaudio.exceptions import KugelAudioError
from langdetect import LangDetectException, detect
from openai import OpenAIError

from backend.clients import llm, stt, tts
from backend.languages import LANGUAGE_NAMES_EN
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.chunking import sentence_chunks
from backend.session.models import AudioChunk, Failed, StateChanged, Turn, TurnCompleted, TurnEvent

logger = logging.getLogger("calltrainer")

# Sent once, ahead of the first Turn, to have the Persona open the call
# instead of waiting for the user — an ad-hoc instruction rather than
# persistent history, so it never resurfaces once the real conversation
# starts. English, like the system prompt (see personas.py) — instructions
# get followed more reliably in English than in the target reply language.
_OPENING_INSTRUCTION = (
    "The call is starting now: you are the one calling, and you speak first. "
    "Open the conversation yourself with 1-2 short, realistic sentences: a "
    "greeting, who you are, and — briefly — what you're calling about (the "
    "question/concern from your role above). Invent plausible details as you "
    "go — different every time. Start directly with the spoken line itself, "
    "e.g. \"Hi, this is...\" — no announcement before it like \"Here is the "
    "opening\", no quotation marks around it, no meta-commentary or stage "
    "directions. Reply with only that opening line."
)

# Sent as a one-off corrective nudge (not persisted) if the reply's first
# chunk wasn't detected as the expected Language.
_LANGUAGE_CORRECTION = "Your last reply wasn't in {language}. From now on, reply exclusively in {language}."

# Sent as a one-off corrective nudge if the reply's first chunk looked like a
# near-duplicate of an *earlier* Persona reply. The system prompt's
# anti-repetition instruction alone wasn't reliable enough in testing — a
# small model can end up reciting the same recap/objection block essentially
# verbatim, sometimes with a gap of a turn or two rather than back-to-back —
# so this is a deterministic backstop. Checked against every earlier reply,
# not just the immediately preceding one, since the repeated block doesn't
# always resurface on the very next Turn.
_REPETITION_CORRECTION = (
    "That reply repeated something you already said earlier in this call, "
    "almost word for word. Say something different this time: react "
    "specifically to the user's last message instead of repeating yourself."
)
_SIMILARITY_THRESHOLD = 0.6
_MIN_CHARS_FOR_SIMILARITY_CHECK = 30  # too short to compare meaningfully below this


def _similar_enough(text_lower: str, reply: str) -> bool:
    if len(reply) < _MIN_CHARS_FOR_SIMILARITY_CHECK:
        return False
    return SequenceMatcher(None, text_lower, reply.lower()).ratio() > _SIMILARITY_THRESHOLD


def _too_similar_to_previous(text: str, previous_replies: list[str]) -> bool:
    if len(text) < _MIN_CHARS_FOR_SIMILARITY_CHECK:
        return False
    text_lower = text.lower()
    return any(_similar_enough(text_lower, reply) for reply in previous_replies)


# Emitted by the Persona at the end of a reply to end the call naturally (see
# personas.py's instruction) — matched case/whitespace-insensitively since a
# small model won't always reproduce it byte-for-byte, stripped before the
# text ever reaches the Transcript or TTS.
_END_CALL_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

# Relying on the system prompt's closing instruction alone wasn't reliable
# enough in testing (a small model buries it under the persona's other
# instructions, e.g. its typical objections) — so a farewell from the user is
# additionally detected deterministically here and reinforced with a one-off,
# high-priority nudge right before that Turn's reply is generated.
_FAREWELL_PATTERNS: dict[str, re.Pattern[str]] = {
    # (?:ö|oe) etc. rather than just the umlaut: STT output is usually proper
    # German spelling, but tolerating the ASCII transliteration too is cheap
    # insurance against STT edge cases.
    "de": re.compile(
        r"\b(auf wiederh(?:ö|oe)ren|auf wiedersehen|tsch(?:ü|ue)ss+|tschau|mach'?s gut|"
        r"bis (bald|dann|sp(?:ä|ae)ter)|einen (sch(?:ö|oe)nen tag|sch(?:ö|oe)nen abend))\b",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(goodbye|bye( now| bye)?|see you|take care|have a (good|nice|great) (day|one))\b",
        re.IGNORECASE,
    ),
}
_FAREWELL_NUDGE = (
    "The user just said goodbye. End the call now: add one brief, friendly "
    "closing line, then finish your reply with exactly this marker and "
    "nothing after it: [CALL_END]."
)


def _sounds_like_farewell(text: str, language_id: str) -> bool:
    pattern = _FAREWELL_PATTERNS.get(language_id)
    return pattern is not None and bool(pattern.search(text))


class _NeedsCorrection(Exception):
    """Internal control-flow signal: the reply's first chunk needs a
    corrective retry (wrong Language, or too similar to the previous reply)
    — carries the one-off nudge message to retry with."""

    def __init__(self, correction: str):
        super().__init__(correction)
        self.correction = correction


_MIN_CHARS_FOR_LANGUAGE_CHECK = 20  # langdetect is unreliable (and overconfident) below this


def _looks_like_expected_language(text: str, language_id: str) -> bool:
    if len(text) < _MIN_CHARS_FOR_LANGUAGE_CHECK:
        return True  # too short to classify reliably — don't block on it
    try:
        return detect(text) == language_id
    except LangDetectException:
        return True


class _ReplyProgress:
    """Mutable state shared across one reply's pipelined TTS chunks."""

    def __init__(self) -> None:
        self.chunk_seq = 0
        self.spoke_yet = False
        self.ends_call = False


def _strip_end_marker(text_chunk: str, progress: _ReplyProgress) -> str:
    """Strips the [CALL_END] marker if present, flagging progress.ends_call."""
    if not _END_CALL_RE.search(text_chunk):
        return text_chunk
    progress.ends_call = True
    return _END_CALL_RE.sub("", text_chunk).strip()


# A small model occasionally leaks a handful of Chinese/Japanese/Korean
# characters into an otherwise German/English reply — confirmed happening in
# testing. _looks_like_expected_language (whole-chunk statistical
# classification via langdetect, and only checked on the reply's first chunk)
# doesn't reliably catch this: a few foreign characters mixed into an
# otherwise-correct-language chunk usually aren't enough to flip langdetect's
# overall verdict away from "de"/"en". Stripped from every chunk
# unconditionally instead of retried — German/English text never legitimately
# contains these scripts (no false-positive risk), and unlike a language
# retry this doesn't need to happen before any audio has been sent, so it can
# apply to later chunks too, not just the first.
_FOREIGN_SCRIPT_RE = re.compile(
    "["
    "\u3000-\u303f"  # CJK punctuation
    "\u3040-\u30ff"  # Hiragana + Katakana
    "\u3400-\u4dbf"  # CJK Unified Ideographs Extension A
    "\u4e00-\u9fff"  # CJK Unified Ideographs
    "\uac00-\ud7a3"  # Hangul syllables
    "]+"
)


def _strip_foreign_script(text_chunk: str) -> str:
    return _FOREIGN_SCRIPT_RE.sub("", text_chunk).strip()


async def _drain_if_pending(
    turn: Turn, pending: tuple[str, "asyncio.Task[bytes | None]"] | None, progress: _ReplyProgress
) -> AsyncIterator[TurnEvent]:
    """Awaits+yields the pipelined TTS task's events, if there is one."""
    if pending is None:
        return
    async for event in _emit_pending(turn, pending, progress):
        yield event


async def _emit_pending(
    turn: Turn, pending: tuple[str, "asyncio.Task[bytes | None]"], progress: _ReplyProgress
) -> AsyncIterator[TurnEvent]:
    """Await one pipelined TTS task and yield its AudioChunk, or a Failed
    event if synthesis didn't succeed after its own retry."""
    audio = await pending[1]
    if audio is None:
        yield Failed(code="tts_failed", message="Synthesis failed after one retry.")
        return
    if not progress.spoke_yet:
        yield StateChanged(state="speaking")
        progress.spoke_yet = True
    progress.chunk_seq += 1
    yield AudioChunk(turn_seq=turn.seq, chunk_seq=progress.chunk_seq, audio=audio)


class SessionOrchestrator:
    """Owns one Session's conversation state: the LLM message history and the
    Turn-by-Turn Transcript. `run_opening_turn`/`run_turn` each drive one
    STT -> LLM -> TTS pass and apply ADR 0017's retry-then-graceful-end
    policy, reinterpreted per-leg for the streaming pipeline (ADR 0026)."""

    def __init__(self, persona: Persona, scenario: Scenario, language_id: str):
        self._language_id = language_id
        # English name for the LLM prompt (see personas.py/_OPENING_INSTRUCTION
        # for why) — distinct from LANGUAGES' German-facing UI display name.
        self._language_name = LANGUAGE_NAMES_EN[language_id]
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": persona.as_system_prompt(scenario, self._language_name)},
        ]
        self._persona_replies: list[str] = []
        self.turns: list[Turn] = []

    async def run_opening_turn(self) -> AsyncIterator[TurnEvent]:
        """Have the Persona speak first: a freshly generated, varied call opener."""
        turn = Turn(seq=len(self.turns) + 1)
        self.turns.append(turn)

        yield StateChanged(state="thinking")
        # Sent as a "user" turn, not another system message: some
        # OpenAI-compatible backends (e.g. Gemini) map only user/assistant
        # messages into their native request format and reject a request
        # whose messages are all system-role as having no content at all.
        kickoff_messages = [*self._messages, {"role": "user", "content": _OPENING_INSTRUCTION}]
        async for event in self._generate_reply(turn, kickoff_messages):
            yield event

    async def run_turn(
        self, audio_bytes: bytes, filename: str, content_type: str | None
    ) -> AsyncIterator[TurnEvent]:
        """Run one Turn: transcribe, stream a reply, synthesize+yield it chunk by chunk."""
        turn = Turn(seq=len(self.turns) + 1)
        self.turns.append(turn)

        yield StateChanged(state="thinking")

        user_text = await self._transcribe_with_retry(audio_bytes, filename, content_type)
        if user_text is None:
            yield Failed(code="stt_failed", message="Transcription failed after one retry.")
            return
        turn.user_text = user_text
        self._messages.append({"role": "user", "content": user_text})

        farewell = _sounds_like_farewell(user_text, self._language_id)
        messages = self._messages
        if farewell:
            messages = [*messages, {"role": "system", "content": _FAREWELL_NUDGE}]

        async for event in self._generate_reply(turn, messages, force_end_call=farewell):
            yield event

    async def _generate_reply(
        self, turn: Turn, messages: list[dict[str, str]], force_end_call: bool = False
    ) -> AsyncIterator[TurnEvent]:
        """Drive one reply attempt (plus, per ADR 0017/0026, one retry — also
        covering a reply that needs a correction, i.e. came back in the wrong
        Language or repeated the previous reply). Appends the finished reply
        to persistent history and yields the Turn's completion/state events.

        `force_end_call` makes ending the call deterministic once a farewell
        was detected (see `_sounds_like_farewell`) — the LLM still writes the
        closing line, but the call actually ending no longer depends on it
        reliably including the [CALL_END] marker, which a small model won't
        always do even when explicitly told to (confirmed in testing)."""
        progress = _ReplyProgress()
        already_retried = False
        attempt_messages = messages
        for llm_attempt in range(2):  # initial attempt + one retry
            try:
                skip_check = already_retried
                async for event in self._stream_and_synthesize(turn, attempt_messages, progress, skip_check):
                    yield event
                    if isinstance(event, Failed):
                        return
                break  # streamed to completion without an LLM-side error
            except (OpenAIError, _NeedsCorrection) as e:
                needs_correction = isinstance(e, _NeedsCorrection)
                if needs_correction:
                    already_retried = True
                else:
                    logger.error("LLM request failed (attempt %d): %s", llm_attempt + 1, e)
                # Audio for part of this reply was already sent/played — a
                # fresh completion would diverge from what the user just heard,
                # so we don't retry past that point (ADR 0026) or past the one
                # retry attempt ADR 0017 allows.
                if progress.spoke_yet or llm_attempt == 1:
                    yield Failed(code="llm_failed", message=str(e) or "Reply needed a correction.")
                    return
                turn.persona_text = ""  # retrying from scratch
                if needs_correction:
                    attempt_messages = [*messages, {"role": "user", "content": e.correction}]

        turn.persona_text = turn.persona_text.strip()
        self._messages.append({"role": "assistant", "content": turn.persona_text})
        self._persona_replies.append(turn.persona_text)

        ends_call = progress.ends_call or force_end_call
        yield TurnCompleted(turn_seq=turn.seq, ends_call=ends_call)
        if not ends_call:
            yield StateChanged(state="listening")

    def _check_first_chunk_once(self, checked: bool, text_chunk: str) -> bool:
        """Runs the Language + repetition checks on the first chunk only
        (checked=False means "not checked yet"). Returns True (now checked)
        or raises `_NeedsCorrection` with a one-off nudge to retry with."""
        if checked:
            return True
        if not _looks_like_expected_language(text_chunk, self._language_id):
            logger.warning("Reply looked like the wrong language, retrying with a correction")
            raise _NeedsCorrection(_LANGUAGE_CORRECTION.format(language=self._language_name))
        if _too_similar_to_previous(text_chunk, self._persona_replies):
            logger.warning("Reply looked too similar to the previous one, retrying with a correction")
            raise _NeedsCorrection(_REPETITION_CORRECTION)
        return True

    async def _stream_and_synthesize(
        self, turn: Turn, messages: list[dict[str, str]], progress: _ReplyProgress, skip_check: bool
    ) -> AsyncIterator[TurnEvent]:
        """Stream one LLM completion, synthesizing+yielding it chunk by chunk,
        pipelined one chunk deep: each chunk's TTS call is fired off
        immediately and only awaited once the *next* chunk's text has
        arrived, so synthesis overlaps with the LLM generating what comes
        after it instead of blocking it — pure serial dead time otherwise.

        Raises `_NeedsCorrection` if `skip_check` is False and the first
        chunk fails the Language/repetition checks (the retry attempt passes
        True, since that budget is spent after one correction), and lets
        `OpenAIError` from the LLM call propagate — both handled by the
        caller's retry loop. A TTS failure is not retried at this level;
        it's yielded as `Failed` directly. `finally` (rather than `except`)
        cancels the pipelined TTS task so a barge-in interrupt — delivered as
        `asyncio.CancelledError` on the Task wrapping this whole generator,
        not as one of the exceptions above — doesn't leave it orphaned;
        cancelling an already-awaited (done) task here is a no-op."""
        pending: tuple[str, asyncio.Task[bytes | None]] | None = None
        checked = skip_check
        try:
            async for text_chunk in sentence_chunks(llm.stream_reply(messages)):
                checked = self._check_first_chunk_once(checked, text_chunk)
                text_chunk = _strip_end_marker(text_chunk, progress)
                text_chunk = _strip_foreign_script(text_chunk)

                if text_chunk:
                    turn.persona_text += text_chunk + " "
                    async for event in _drain_if_pending(turn, pending, progress):
                        yield event
                    pending = (text_chunk, asyncio.create_task(self._synthesize_with_retry(text_chunk)))

                if progress.ends_call:
                    break  # nothing meaningful should follow the marker

            async for event in _drain_if_pending(turn, pending, progress):
                yield event
        finally:
            if pending is not None:
                pending[1].cancel()

    async def _transcribe_with_retry(
        self, audio_bytes: bytes, filename: str, content_type: str | None
    ) -> str | None:
        """Transcribe with one retry on failure; None if both attempts fail."""
        for attempt in range(2):  # initial attempt + one retry
            try:
                return await stt.transcribe(audio_bytes, filename, content_type, self._language_id)
            except OpenAIError as e:
                logger.error("STT request failed (attempt %d): %s", attempt + 1, e)
        return None

    async def _synthesize_with_retry(self, text: str) -> bytes | None:
        """Synthesize one chunk with one retry on failure; None if both attempts fail."""
        for attempt in range(2):  # initial attempt + one retry
            try:
                return await tts.synthesize(text, self._language_id)
            except (OpenAIError, KugelAudioError) as e:
                logger.error("TTS request failed (attempt %d): %s", attempt + 1, e)
        return None
