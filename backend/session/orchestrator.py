"""Session/Turn orchestration: the STT -> LLM -> TTS pipeline and its retry policy."""

import asyncio
import logging
from collections.abc import AsyncIterator

from kugelaudio.exceptions import KugelAudioError
from langdetect import LangDetectException, detect
from openai import OpenAIError

from backend.clients import llm, stt, tts
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.chunking import sentence_chunks
from backend.session.models import AudioChunk, Failed, StateChanged, Turn, TurnCompleted, TurnEvent

logger = logging.getLogger("calltrainer")

# Sent once, ahead of the first Turn, to have the Persona open the call
# instead of waiting for the user — an ad-hoc instruction rather than
# persistent history, so it never resurfaces once the real conversation starts.
_OPENING_INSTRUCTION = (
    "Der Anruf beginnt jetzt und du bist zuerst am Zug. Eröffne das Gespräch von "
    "dir aus mit 1-2 kurzen, realistischen Sätzen passend zu deiner Rolle und dem "
    "Kontext (z. B. eine Begrüßung, wer du bist, worum es dir geht). Erfinde dabei "
    "passende Details — bei jedem Anruf andere. Antworte ausschließlich mit dieser "
    "Eröffnung, ohne Meta-Kommentare oder Regieanweisungen."
)

# Sent as a one-off corrective nudge (not persisted) if the reply's first
# chunk wasn't detected as the expected Language.
_LANGUAGE_CORRECTION = "Deine letzte Antwort war nicht auf {language}. Antworte ab jetzt ausschließlich auf {language}."


class _WrongLanguage(Exception):
    """Internal control-flow signal: the reply's first chunk wasn't in the
    expected Language — raised to reuse the existing per-leg retry loop."""


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


def _check_language_once(checked: bool, text_chunk: str, language_id: str) -> bool:
    """Checks the first chunk only (checked=False means "not checked yet").
    Returns True (now checked) or raises `_WrongLanguage`."""
    if checked:
        return True
    if not _looks_like_expected_language(text_chunk, language_id):
        logger.warning("Reply looked like the wrong language, retrying with a correction")
        raise _WrongLanguage()
    return True


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

    def __init__(self, persona: Persona, scenario: Scenario, language_id: str, language_name: str):
        self._language_id = language_id
        self._language_name = language_name
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": persona.as_system_prompt(scenario, language_name)},
        ]
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

        async for event in self._generate_reply(turn, self._messages):
            yield event

    async def _generate_reply(self, turn: Turn, messages: list[dict[str, str]]) -> AsyncIterator[TurnEvent]:
        """Drive one reply attempt (plus, per ADR 0017/0026, one retry — also
        covering a reply that comes back in the wrong Language). Appends the
        finished reply to persistent history and yields the Turn's
        completion/state events."""
        progress = _ReplyProgress()
        language_retried = False
        attempt_messages = messages
        for llm_attempt in range(2):  # initial attempt + one retry
            try:
                skip_language_check = language_retried
                async for event in self._stream_and_synthesize(turn, attempt_messages, progress, skip_language_check):
                    yield event
                    if isinstance(event, Failed):
                        return
                break  # streamed to completion without an LLM-side error
            except (OpenAIError, _WrongLanguage) as e:
                wrong_language = isinstance(e, _WrongLanguage)
                if wrong_language:
                    language_retried = True
                else:
                    logger.error("LLM request failed (attempt %d): %s", llm_attempt + 1, e)
                if progress.spoke_yet:
                    # Audio for part of this reply was already sent/played — a
                    # fresh completion would diverge from what the user just
                    # heard, so we don't retry past this point (ADR 0026).
                    yield Failed(code="llm_failed", message=str(e) or "Reply was in the wrong language.")
                    return
                if llm_attempt == 1:
                    yield Failed(code="llm_failed", message=str(e) or "Reply was in the wrong language.")
                    return
                turn.persona_text = ""  # retrying from scratch
                if wrong_language:
                    correction = _LANGUAGE_CORRECTION.format(language=self._language_name)
                    attempt_messages = [*messages, {"role": "user", "content": correction}]

        turn.persona_text = turn.persona_text.strip()
        self._messages.append({"role": "assistant", "content": turn.persona_text})

        yield TurnCompleted(turn_seq=turn.seq)
        yield StateChanged(state="listening")

    async def _stream_and_synthesize(
        self, turn: Turn, messages: list[dict[str, str]], progress: _ReplyProgress, skip_language_check: bool
    ) -> AsyncIterator[TurnEvent]:
        """Stream one LLM completion, synthesizing+yielding it chunk by chunk,
        pipelined one chunk deep: each chunk's TTS call is fired off
        immediately and only awaited once the *next* chunk's text has
        arrived, so synthesis overlaps with the LLM generating what comes
        after it instead of blocking it — pure serial dead time otherwise.

        Raises `_WrongLanguage` if `skip_language_check` is False and the
        first chunk isn't in the expected Language (the retry attempt passes
        True, since the Language budget is spent after one correction), and
        lets `OpenAIError` from the LLM call propagate — both handled by the
        caller's retry loop. A TTS failure is not retried at this level; it's
        yielded as `Failed` directly."""
        pending: tuple[str, asyncio.Task[bytes | None]] | None = None
        checked = skip_language_check
        try:
            async for text_chunk in sentence_chunks(llm.stream_reply(messages)):
                checked = _check_language_once(checked, text_chunk, self._language_id)

                turn.persona_text += text_chunk + " "
                if pending is not None:
                    async for event in _emit_pending(turn, pending, progress):
                        yield event
                pending = (text_chunk, asyncio.create_task(self._synthesize_with_retry(text_chunk)))

            if pending is not None:
                async for event in _emit_pending(turn, pending, progress):
                    yield event
        except (OpenAIError, _WrongLanguage):
            if pending is not None:
                pending[1].cancel()
            raise

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
