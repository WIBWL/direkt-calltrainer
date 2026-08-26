"""Session orchestration: STT -> LLM -> TTS pipeline and retry policy."""

import asyncio
import logging
import re
from collections.abc import AsyncIterator

from kugelaudio.exceptions import KugelAudioError
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
    """Builds the LLM system prompt."""
    language = _LANGUAGE_NAMES_EN[persona.language_id]
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
        "seem resolved, or the user signals the call is over — a goodbye, "
        "a wrap-up like \"das reicht mir\"/\"das wär's\", or any other "
        "natural way people end a phone call — end it yourself: add one "
        "brief, friendly closing line (e.g. thank them, say goodbye), then "
        "finish your reply with exactly this marker on its own and nothing "
        "after it: [CALL_END]. Only include that marker when the call "
        "should truly end — never otherwise, and never explain or mention "
        "the marker itself.\n"
        f"Reply exclusively in {language}, every single time regardless of "
        "what language the user writes in, in short, realistic sentences "
        "the way people actually talk on the phone. Stay true to the role "
        "without exaggerating into caricature. Output only what the "
        "persona would say — no meta-commentary, no stage directions."
    )


_END_CALL_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

# Closing detection, per Schegloff & Sacks (1973) "Opening Up Closings": a
# call typically ends via a terminal exchange (an explicit farewell), often
# preceded by a pre-closing turn — a short "okay"/"alright"-type utterance
# that occupies the floor without raising anything new. We treat the first
# as a strong signal anywhere in the turn; the second only counts when it's
# essentially the whole (short, question-free) turn, so it doesn't fire on
# an aside like "Danke, aber ich habe noch eine Frage."
_TERMINAL_FAREWELL_RE: dict[str, re.Pattern[str]] = {
    "de": re.compile(
        r"\b(auf wiederh(?:ö|oe)ren|auf wiedersehen|tsch(?:ü|ue)ss+|tschau|ciao|"
        r"mach'?s gut|bis (bald|dann|sp(?:ä|ae)ter)|"
        r"(sch(?:ö|oe)nen|guten) (tag|abend)( noch)?)\b",
        re.IGNORECASE,
    ),
}
_PRE_CLOSING_RE: dict[str, re.Pattern[str]] = {
    "de": re.compile(
        r"^(alles klar|passt( so)?|(das )?(w(?:ä|ae)r'?s|reicht( mir)?( so)?|"
        r"kl(?:ä|ae)rt (alles|es|die sache))|(vielen )?dank(e)?( sch(?:ö|oe)n)?|"
        r"(super|gut|okay|ok)[,.]? dann)\b",
        re.IGNORECASE,
    ),
}
_MAX_CHARS_FOR_PRE_CLOSING = 40

_CLOSING_NUDGE = (
    "The user just signaled the call is over. End it now: add one brief, "
    "friendly closing line, then finish your reply with exactly this "
    "marker and nothing after it: [CALL_END]."
)


def _sounds_like_closing(text: str, language_id: str) -> bool:
    """True for an explicit farewell anywhere in the turn, or a short
    pre-closing wrap-up with no new question (see module comment above)."""
    text = text.strip()
    terminal = _TERMINAL_FAREWELL_RE.get(language_id)
    if terminal is not None and terminal.search(text):
        return True
    pre_closing = _PRE_CLOSING_RE.get(language_id)
    if pre_closing is None or "?" in text or len(text) > _MAX_CHARS_FOR_PRE_CLOSING:
        return False
    return bool(pre_closing.match(text))


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
    turn: Turn, pending: "asyncio.Task[bytes | None] | None", progress: _ReplyProgress
) -> AsyncIterator[TurnEvent]:
    """Awaits+yields the pipelined TTS task's events, if there is one."""
    if pending is None:
        return
    audio = await pending
    if audio is None:
        yield Failed(code="tts_failed", message="Synthesis failed after one retry.")
        return
    if not progress.spoke_yet:
        yield StateChanged(state="speaking")
        progress.spoke_yet = True
    progress.chunk_seq += 1
    yield AudioChunk(turn_seq=turn.seq, chunk_seq=progress.chunk_seq, audio=audio)


class SessionOrchestrator:
    """Owns one session's LLM message history and Turn-by-Turn Transcript;
    drives one STT -> LLM -> TTS pass per turn."""

    def __init__(self, persona: Persona, scenario: Scenario):
        self._language_id = persona.language_id
        self._voice = persona.voice
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": _build_system_prompt(persona, scenario)},
        ]
        self.turns: list[Turn] = []

    async def run_opening_turn(self) -> AsyncIterator[TurnEvent]:
        """Have the Persona speak first: a freshly generated, varied call opener."""
        turn = Turn(seq=len(self.turns) + 1)
        self.turns.append(turn)

        yield StateChanged(state="thinking")
        kickoff_messages = [*self._messages, {"role": "user", "content": _OPENING_INSTRUCTION}]
        async for event in self._generate_reply(turn, kickoff_messages):
            yield event

    async def run_turn(
        self, audio_bytes: bytes, filename: str, content_type: str | None
    ) -> AsyncIterator[TurnEvent]:
        """Run one turn: transcribe, stream a reply, synthesize+yield it chunk by chunk."""
        turn = Turn(seq=len(self.turns) + 1)
        self.turns.append(turn)

        yield StateChanged(state="thinking")

        user_text = await self._transcribe_with_retry(audio_bytes, filename, content_type)
        if user_text is None:
            yield Failed(code="stt_failed", message="Transcription failed after one retry.")
            return
        turn.user_text = user_text
        self._messages.append({"role": "user", "content": user_text})

        closing = _sounds_like_closing(user_text, self._language_id)
        messages = self._messages
        if closing:
            messages = [*messages, {"role": "system", "content": _CLOSING_NUDGE}]

        async for event in self._generate_reply(turn, messages, force_end_call=closing):
            yield event

    async def _generate_reply(
        self, turn: Turn, messages: list[dict[str, str]], force_end_call: bool = False
    ) -> AsyncIterator[TurnEvent]:
        """Drive one reply attempt plus one retry on an LLM error.
        Appends the finished reply to history and yields events."""
        progress = _ReplyProgress()
        for llm_attempt in range(2):  # initial attempt + one retry
            try:
                async for event in self._stream_and_synthesize(turn, messages, progress):
                    yield event
                    if isinstance(event, Failed):
                        return
                break  # streamed to completion without an LLM-side error
            except OpenAIError as e:
                logger.error("LLM request failed (attempt %d): %s", llm_attempt + 1, e)
                # Audio for part of this reply was already played
                if progress.spoke_yet or llm_attempt == 1:
                    yield Failed(code="llm_failed", message=str(e))
                    return
                turn.persona_text = ""  # retrying from scratch

        turn.persona_text = turn.persona_text.strip()
        self._messages.append({"role": "assistant", "content": turn.persona_text})

        # force_end_call backstops [CALL_END]: a small model won't always
        # include the marker even when told to (confirmed in testing).
        ends_call = progress.ends_call or force_end_call
        yield TurnCompleted(turn_seq=turn.seq, ends_call=ends_call)
        if not ends_call:
            yield StateChanged(state="listening")

    async def _stream_and_synthesize(
        self, turn: Turn, messages: list[dict[str, str]], progress: _ReplyProgress
    ) -> AsyncIterator[TurnEvent]:
        """Stream one LLM completion, synthesizing+yielding it chunk by chunk,
        pipelined one chunk deep so synthesis overlaps generation instead of blocking it."""
        pending: asyncio.Task[bytes | None] | None = None
        try:
            async for text_chunk in sentence_chunks(llm.stream_reply(messages)):
                text_chunk = _strip_end_marker(text_chunk, progress)
                text_chunk = _strip_foreign_script(text_chunk)

                if text_chunk:
                    turn.persona_text += text_chunk + " "
                    async for event in _drain_if_pending(turn, pending, progress):
                        yield event
                    pending = asyncio.create_task(self._synthesize_with_retry(text_chunk))

                if progress.ends_call:
                    break  # nothing meaningful should follow the marker

            async for event in _drain_if_pending(turn, pending, progress):
                yield event
        except OpenAIError:
            if pending is not None:
                pending.cancel()
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
