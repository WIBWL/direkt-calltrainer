"""Session orchestration: STT -> LLM -> TTS pipeline and retry policy."""

import asyncio
import contextlib
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

logger = logging.getLogger(__name__)

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
        "If your concern has been concretely addressed — a clear answer, or "
        "a specific commitment with an actual action, amount, or timeframe "
        "(like the refund example above) — or the user signals the call is "
        "over — a goodbye, a wrap-up like \"das reicht mir\"/\"das wär's\", "
        "or any other natural way people end a phone call — end it "
        "yourself: add one brief, friendly closing line (e.g. thank them, "
        "say goodbye), then finish your reply with exactly this marker on "
        "its own and nothing after it: [CALL_END]. Never end the call "
        "while you still consider your concern unresolved, are still "
        "pressing for information, or have only gotten a vague reassurance "
        "with no specifics (\"ich kümmere mich darum\", \"ich stelle das "
        "klar\") — a frustrated reply, or an empty promise with no actual "
        "content, is not by itself a reason to hang up; keep pushing for "
        "specifics instead, the way a real caller would. Only include the "
        "marker when the call should truly end — never otherwise, never in the "
        "same reply as a question or a statement that the issue isn't "
        "resolved yet, and never explain or mention the marker itself.\n"
        f"Reply exclusively in {language}, every single time regardless of "
        "what language the user writes in, in short, realistic sentences "
        "the way people actually talk on the phone. Stay true to the role "
        "without exaggerating into caricature. Output only what the "
        "persona would say — no meta-commentary, no stage directions."
    )


_END_CALL_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

# Catches an explicit farewell or a request to postpone/continue elsewhere --
# the two categories of user signal the persona's own judgment (the system
# prompt above) was observed to miss. Deliberately narrow and regex-based,
# not an LLM classifier: that approach's own chain-of-thought reasoning
# would occasionally degenerate into a non-sequitur and land on the wrong
# verdict (confirmed in testing). A missed signal here just costs one extra
# turn; a false one cuts the call short mid-conversation, which is worse.
_FAREWELL_RE = re.compile(r"\b(tschüss|auf wiederhören|auf wiedersehen|wiederhören|ciao)\b", re.IGNORECASE)
_POSTPONE_RE = re.compile(
    r"(ein andere[rs]? mal|andermal|anders (fortsetzen|weiterführen|weitermachen)|"
    r"später (nochmal|weiter|zurückrufen)|melde mich (nochmal|später|wieder)|"
    r"rufe? (sie |dich )?(nochmal|später|zurück)|keine zeit (mehr|gerade)|"
    r"muss (jetzt |gleich )?(auflegen|los|schluss machen)|gespräch (beenden|abbrechen))",
    re.IGNORECASE,
)


def _signals_closing(user_text: str) -> bool:
    """True if the user's message is an explicit farewell or a request to
    postpone/continue the call elsewhere."""
    return bool(_FAREWELL_RE.search(user_text) or _POSTPONE_RE.search(user_text))


_CLOSING_NUDGE = (
    "The user just signaled the call is over. End it now: add one brief, "
    "friendly closing line, then finish your reply with exactly this "
    "marker and nothing after it: [CALL_END]."
)

# Said in place of trusting the model's own reply to have included a
# goodbye -- for a backstopped ending (a repeat, or the model ending
# unprompted) that trust hasn't been earned (confirmed in testing).
_FALLBACK_CLOSING_LINE = "Vielen Dank für Ihre Zeit. Auf Wiederhören."


class _ReplyProgress:
    """Mutable state shared across one reply's pipelined TTS chunks."""

    def __init__(self) -> None:
        self.chunk_seq = 0
        self.spoke_yet = False
        self.ends_call = False
        self.spoken_text = ""


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


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _has_repeated_sentence(text: str) -> bool:
    """True if the same non-trivial sentence appears twice in text -- a
    sign of degenerate generation within a single reply."""
    seen = set()
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip().lower()
        if len(sentence) < 15:
            continue
        if sentence in seen:
            return True
        seen.add(sentence)
    return False


async def _drain_if_pending(
    turn: Turn,
    pending: "tuple[str, asyncio.Task[bytes | None]] | None",
    progress: _ReplyProgress,
) -> AsyncIterator[TurnEvent]:
    """Awaits+yields the pipelined TTS task's events, if there is one."""
    if pending is None:
        return
    text, task = pending
    audio = await task
    if audio is None:
        yield Failed(code="tts_failed", message="Synthesis failed after one retry.")
        return
    if not progress.spoke_yet:
        yield StateChanged(state="speaking")
        progress.spoke_yet = True
    progress.chunk_seq += 1
    progress.spoken_text += text + " "
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
        self._reopen_turn: Turn | None = None

    def _new_or_reopened_turn(self) -> tuple[Turn, bool]:
        """Reuses a still-open turn from a prior barge-in, else creates a
        fresh one; marks it unresolved so an early interruption still counts."""
        reopening = self._reopen_turn is not None
        turn = self._reopen_turn if reopening else Turn(seq=len(self.turns) + 1)
        if not reopening:
            self.turns.append(turn)
        self._reopen_turn = turn
        return turn, reopening

    async def run_opening_turn(self) -> AsyncIterator[TurnEvent]:
        """Have the Persona speak first: a freshly generated, varied call opener."""
        turn, _ = self._new_or_reopened_turn()
        progress = _ReplyProgress()
        try:
            yield StateChanged(state="thinking")
            kickoff_messages = [*self._messages, {"role": "user", "content": _OPENING_INSTRUCTION}]
            async with contextlib.aclosing(self._generate_reply(turn, kickoff_messages, progress)) as replies:
                async for event in replies:
                    yield event
            self._reopen_turn = None
        except (asyncio.CancelledError, GeneratorExit):
            self._finalize_interrupted(turn, progress)
            raise

    async def run_turn(
        self, audio_bytes: bytes, filename: str, content_type: str | None
    ) -> AsyncIterator[TurnEvent]:
        """Run one turn: transcribe, stream a reply, synthesize+yield it chunk by chunk."""
        turn, reopening = self._new_or_reopened_turn()
        progress = _ReplyProgress()
        try:
            yield StateChanged(state="thinking")

            user_text = await self._transcribe_with_retry(audio_bytes, filename, content_type)
            if user_text is None:
                yield Failed(code="stt_failed", message="Transcription failed after one retry.")
                return

            # A still-open turn from a barge-in gets the new text appended
            # onto its question instead of starting a fresh turn.
            if reopening and turn.user_text:
                turn.user_text = f"{turn.user_text} {user_text}".strip()
                self._messages[-1]["content"] = turn.user_text
            else:
                turn.user_text = user_text
                self._messages.append({"role": "user", "content": user_text})
            closing = _signals_closing(turn.user_text)

            messages = self._messages
            if closing:
                messages = [*messages, {"role": "system", "content": _CLOSING_NUDGE}]

            async with contextlib.aclosing(
                self._generate_reply(turn, messages, progress, force_end_call=closing)
            ) as replies:
                async for event in replies:
                    yield event
            self._reopen_turn = None
        except (asyncio.CancelledError, GeneratorExit):
            # User barged in; aclosing above ensures this runs even if
            # cancellation landed between yields, not inside a network await.
            self._finalize_interrupted(turn, progress)
            raise

    async def _attempt_reply_with_retry(
        self, turn: Turn, messages: list[dict[str, str]], progress: _ReplyProgress
    ) -> AsyncIterator[TurnEvent]:
        """One reply attempt plus one retry on an LLM error. Yields the reply's
        events; yields a Failed event and stops if it can't be delivered."""
        for llm_attempt in range(2):  # initial attempt + one retry
            try:
                stream = self._stream_and_synthesize(turn, messages, progress)
                async with contextlib.aclosing(stream) as chunks:
                    async for event in chunks:
                        yield event
                        if isinstance(event, Failed):
                            return
                return  # streamed to completion without an LLM-side error
            except OpenAIError as e:
                logger.error("LLM request failed (attempt %d): %s", llm_attempt + 1, e)
                # Audio for part of this reply was already played
                if progress.spoke_yet or llm_attempt == 1:
                    yield Failed(code="llm_failed", message=str(e))
                    return
                turn.persona_text = ""  # retrying from scratch

    async def _generate_reply(
        self, turn: Turn, messages: list[dict[str, str]], progress: _ReplyProgress, force_end_call: bool = False
    ) -> AsyncIterator[TurnEvent]:
        """Drive one reply attempt plus one retry on an LLM error.
        Appends the finished reply to history and yields events."""
        async with contextlib.aclosing(self._attempt_reply_with_retry(turn, messages, progress)) as events:
            async for event in events:
                yield event
                if isinstance(event, Failed):
                    return

        turn.persona_text = turn.persona_text.strip()
        repeated_reply = bool(turn.persona_text) and (
            self._repeats_last_reply(turn.persona_text) or _has_repeated_sentence(turn.persona_text)
        )
        self._messages.append({"role": "assistant", "content": turn.persona_text})

        # force_end_call backstops [CALL_END]: a small model won't always
        # include the marker even when told to (confirmed in testing).
        ends_call = progress.ends_call or force_end_call or repeated_reply
        if ends_call:
            logger.info(
                "Turn %d ends the call (model marker=%s, closing-intent check=%s, repeated reply=%s)",
                turn.seq,
                progress.ends_call,
                force_end_call,
                repeated_reply,
            )
            # Only the closing-intent path actually asked the model for a
            # goodbye (_CLOSING_NUDGE); a repeat or an unprompted ending
            # didn't, so it can't be trusted to have included one.
            if repeated_reply or (progress.ends_call and not force_end_call):
                async for event in self._speak_fallback_closing(turn, progress):
                    yield event
        yield TurnCompleted(turn_seq=turn.seq, ends_call=ends_call)
        if not ends_call:
            yield StateChanged(state="listening")

    async def _speak_fallback_closing(self, turn: Turn, progress: _ReplyProgress) -> AsyncIterator[TurnEvent]:
        """Synthesizes a guaranteed sign-off for a backstopped ending,
        instead of trusting the Persona's own reply to have included one."""
        audio = await self._synthesize_with_retry(_FALLBACK_CLOSING_LINE)
        if audio is None:
            return
        if not progress.spoke_yet:
            yield StateChanged(state="speaking")
            progress.spoke_yet = True
        progress.chunk_seq += 1
        yield AudioChunk(turn_seq=turn.seq, chunk_seq=progress.chunk_seq, audio=audio)
        turn.persona_text = f"{turn.persona_text} {_FALLBACK_CLOSING_LINE}".strip()
        self._messages[-1]["content"] = turn.persona_text

    def _repeats_last_reply(self, text: str) -> bool:
        """True if text matches the persona's most recent reply verbatim
        (mod case/whitespace) -- a sign it's stuck repeating itself."""
        for message in reversed(self._messages):
            if message["role"] == "assistant":
                return message["content"].strip().lower() == text.strip().lower()
        return False

    def _finalize_interrupted(self, turn: Turn, progress: _ReplyProgress) -> None:
        """Commits only the words actually sent as audio (unheard ones stay
        unsaid); else discards everything and leaves the turn open to reopen."""
        if progress.spoke_yet:
            turn.persona_text = progress.spoken_text.strip()
            self._messages.append({"role": "assistant", "content": turn.persona_text})
            self._reopen_turn = None
        else:
            turn.persona_text = ""

    async def _stream_and_synthesize(
        self, turn: Turn, messages: list[dict[str, str]], progress: _ReplyProgress
    ) -> AsyncIterator[TurnEvent]:
        """Stream one LLM completion, synthesizing+yielding it chunk by chunk,
        pipelined one chunk deep so synthesis overlaps generation instead of blocking it."""
        pending: tuple[str, asyncio.Task[bytes | None]] | None = None
        try:
            async for text_chunk in sentence_chunks(llm.stream_reply(messages)):
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
        except (OpenAIError, asyncio.CancelledError, GeneratorExit):
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
