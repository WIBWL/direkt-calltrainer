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
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.chunking import sentence_chunks
from backend.session.models import AudioChunk, Failed, StateChanged, Turn, TurnCompleted, TurnEvent

logger = logging.getLogger("calltrainer")

_LANGUAGE_NAMES_EN: dict[str, str] = {"de": "German"}

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

_EXAMPLE_EXCHANGE = (
    "Example of the tone and pacing to aim for (illustrative only — invent "
    "your own content that fits YOUR actual scenario and character; never "
    "reuse this text or its specifics):\n"
    '[Caller opens] "Guten Tag, hier ist Frau Beck von der Buchhaltung, ich '
    'habe eine Frage zu unserer letzten Rechnung, da stimmt glaube ich was '
    'nicht."\n'
    '[Other person] "Guten Tag Frau Beck, worum geht es denn genau?"\n'
    '[Caller] "Wir wurden für März doppelt belastet, einmal am 3. und '
    'einmal am 17. Können Sie sich das mal anschauen?"\n'
    '[Other person] "Das schaue ich mir an. Können Sie mir die '
    'Rechnungsnummer nennen?"\n'
    '[Caller] "Die habe ich gerade nicht griffbereit, aber es war ein '
    'Betrag über 480 Euro. Ehrlich gesagt ist das schon das zweite Mal in '
    'diesem Jahr, dass bei uns was mit der Abrechnung nicht stimmt." (one '
    "objection, raised once, naturally — never repeated again later)\n"
    '[Other person] "Verstehe, das tut mir leid. Ich erstatte Ihnen den '
    'doppelten Betrag noch heute."\n'
    '[Caller] "Gut, das reicht mir erstmal. Dann klären wir den Rest, '
    'sobald ich die Nummer habe. Danke Ihnen, einen schönen Tag noch. '
    '[CALL_END]" (ends naturally as soon as the concern is addressed — no '
    "recap of everything said before ending)\n"
    "Notice: every caller line adds new, concrete information instead of "
    "restating an earlier one; the objection appears exactly once; the call "
    "ends the moment the concern is actually resolved."
)


def _build_system_prompt(persona: Persona, scenario: Scenario) -> str:
    """Builds the LLM system prompt for one Session: the given Persona's
    character, the given Scenario's call context, and the behavioral
    instructions (anti-repetition, confabulation, call-ending marker) that
    apply regardless of which Persona/Scenario it is — this is where the two
    are combined, not on either data class itself."""
    return (
        "You are playing a character in a phone-call training exercise. "
        "You are the one who called — you initiated this call because you "
        "have a specific question, concern, or problem you want addressed. "
        "The user is the person you called (e.g. support/sales), not the "
        "other way around: never ask the user what their question or "
        "problem is, and never wait for them to explain why they're "
        "calling — you're the one with something to discuss.\n"
        f"Context of the call: {scenario.description}\n"
        f"Your role: {persona.role}.\n"
        f"Character traits: {persona.traits}.\n"
        f"Behavior: {persona.behavior}.\n"
        "Stay in character and improvise like a real person on a real call: "
        "when asked for specifics (e.g. \"which points were still open?\", "
        "\"what do you offer?\", \"why would that help me?\"), invent "
        "concrete, plausible details on the spot — a product name, a "
        "number, a prior concern — instead of staying vague or deflecting. "
        "This is a live conversation, not a scripted FAQ; ground your "
        "answers in believable specifics that fit the context.\n"
        "Never repeat yourself. This is the single most common mistake to "
        "avoid: before every reply, re-read your own previous lines in "
        "this call and check whether you are about to say the same thing "
        "again — the same question, recap, or objection — even reworded. "
        "If so, drop it and say something new instead.\n"
        f"{_EXAMPLE_EXCHANGE}\n"
        "If, based on the conversation so far, your questions and concerns "
        "seem resolved, or the user says goodbye, end the call naturally: "
        "add one brief, friendly closing line (e.g. thank them, say "
        "goodbye), then finish your reply with exactly this marker on its "
        "own and nothing after it: [CALL_END]. Only include that marker "
        "when the call should truly end — never otherwise, and never "
        "explain or mention the marker itself.\n"
        f"Reply exclusively in {_LANGUAGE_NAMES_EN[persona.language_id]}, "
        "in short, realistic sentences the way people actually talk on "
        "the phone. Stay true to the role without exaggerating into "
        "caricature. Output only what the persona would say — no "
        "meta-commentary, no stage directions."
    )


_LANGUAGE_CORRECTION = "Your last reply wasn't in {language}. From now on, reply exclusively in {language}."

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


_END_CALL_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

_FAREWELL_PATTERNS: dict[str, re.Pattern[str]] = {
    "de": re.compile(
        r"\b(auf wiederh(?:ö|oe)ren|auf wiedersehen|tsch(?:ü|ue)ss+|tschau|mach'?s gut|"
        r"bis (bald|dann|sp(?:ä|ae)ter)|einen (sch(?:ö|oe)nen tag|sch(?:ö|oe)nen abend))\b",
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


class _ReplyProgress:  # pylint: disable=too-few-public-methods
    """Mutable state shared across one reply's pipelined TTS chunks — a
    plain data holder by design, not a candidate for more methods."""

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

    def __init__(self, persona: Persona, scenario: Scenario):
        # A Persona has exactly one Language/voice (see personas.py) — no
        # per-Session choice, so both are derived from the Persona rather
        # than passed in separately.
        self._language_id = persona.language_id
        self._language_name = _LANGUAGE_NAMES_EN[persona.language_id]
        self._voice = persona.voice
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": _build_system_prompt(persona, scenario)},
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
        it's yielded as `Failed` directly."""
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
        except (OpenAIError, _NeedsCorrection):
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
                return await tts.synthesize(text, self._voice, self._language_id)
            except (OpenAIError, KugelAudioError) as e:
                logger.error("TTS request failed (attempt %d): %s", attempt + 1, e)
        return None
