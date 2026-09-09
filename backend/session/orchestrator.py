"""One Session's conversation: the STT → dialogue → TTS pass per Turn.

`SessionOrchestrator` owns the LLM message history and the Turn list for one
call. The guards around the pipeline exist because Qwen3-4B misbehaves in
specific, tested ways — copying the English prompt example (ADR 0043), ending
calls too eagerly or not at all (ADR 0037), looping or restating a demand the
user has already met (ADR 0038); each guard's own comment names what it
catches. Repetition is fought on three fronts (ADR 0038): the system prompt
forbids re-introducing, every turn carries a nudge quoting the persona's own
last reply, and a reply that *opens* by greeting again -- or with a sentence
the persona has already said -- is caught before it is spoken and regenerated
once; the verbatim/oscillation/restatement checks stay as the backstop that
ends a call the model has stopped moving forward. When
the user asks to hear something again, the guards ease off once -- the persona
is nudged to say it again, shorter -- then snap back if asked twice. Retry
policy: one retry per leg, then end the Session cleanly (ADR 0016, ADR 0033).
"""
# pylint: disable=too-many-lines  # what is left after the seams were cut: the
# prose lives in prompting.py (the system prompt) and nudges.py (the per-turn
# pushes, each with the comment naming the observed failure it catches), the
# pure helpers in heard.py and measuring.py. This is one call's control flow,
# and carving it further would split a single flow across files to buy lines.

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import NamedTuple

from kugelaudio.exceptions import KugelAudioError
from openai import OpenAIError

from backend.clients import llm, stt, tts
from backend.clients.config import GEMINI
from backend.feedback.acoustics import analyze
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.chunking import sentence_chunks
from backend.session.heard import heard_text
from backend.session.measuring import attach_measurements
from backend.session import repetition
from backend.session.prompting import (
    STATE_MAX_TOKENS, build_state_prompt, build_system_prompt, opening_instruction,
)
from backend.session.nudges import (
    ANTI_REPEAT_NUDGE, CLARIFY_AGAIN_NUDGE, CLARIFY_NUDGE, CLOSING_NUDGE, ECHO_NUDGE,
    GENERIC_CRITERION, INTERRUPTED_MARK, INTERRUPTED_NUDGE, REGENERATE_NUDGE,
    REPEAT_OPENING_NUDGE, RESUME_NUDGE, SETTLEMENT_CHECK, SETTLEMENT_CHECK_AFTER_REPLIES,
    STATE_NOTES_FRAME, strip_interrupted_mark,
)
from backend.session.language_packs import LanguagePack, get_pack, is_phantom, signals_closing
from backend.session.models import AudioChunk, Failed, StateChanged, Turn, TurnCompleted, TurnEvent

logger = logging.getLogger(__name__)


_END_CALL_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

# How many history messages the model reads verbatim while the notes are kept
# (ADR 0071): the last three exchanges. Everything before them reaches the model
# only as its notes.
HISTORY_WINDOW = 6

# Whether the caller's notes are kept at all (ADR 0075 narrows ADR 0071).
#
# Not a preference and not a vendor check in disguise: the notes are a
# compression built for a model that could not read its own transcript, and the
# two backends here differ in exactly that. Where the model can be handed the
# conversation, handing it a five-line summary instead is a loss twice over --
# the summary is rewritten from the previous summary rather than from the
# history, so a distortion has no source left to be corrected against, and it
# costs one background request per exchange to throw the detail away.
CALL_STATE_NOTES = not GEMINI


def _signals_closing(user_text: str, pack: LanguagePack) -> bool:
    """True if the user's message is an explicit farewell or a request to
    postpone/continue the call elsewhere. Matched against the user's own
    speech, so the whole check lives in the language pack, not here."""
    return signals_closing(pack, user_text)


def _asks_to_repeat(user_text: str, pack: LanguagePack) -> bool:
    """True if the user asked the persona to say something again — its name,
    the last line, the question. Repeating is then the right answer, so the
    turn drops the anti-repeat nudge and the re-introduction guard, and a
    repeat of the *immediately previous* reply no longer ends the call
    (ADR 0038). It is not a licence to parrot: `_CLARIFY_NUDGE` asks for the
    same content reworded shorter, and a verbatim repeat of an *older* reply
    still counts as a loop."""
    return bool(pack.repeat_request_re.search(user_text))


class _ReplyFilters(NamedTuple):
    """What one reply attempt is checked against before a chunk is spoken:
    `guard` -- the opening checks and the one re-ask, first attempt on a normal
    Turn only; `filter_repeats` -- sentences already said (ADR 0038) and the
    sentence the user cut off (ADR 0035) are dropped, any attempt on a normal
    Turn, never on a requested repeat or a goodbye."""

    guard: bool
    filter_repeats: bool
    said: frozenset[str]
    cut_off: str


_NO_FILTERS = _ReplyFilters(guard=False, filter_repeats=False, said=frozenset(), cut_off="")


class _ReplyProgress:  # pylint: disable=too-many-instance-attributes  # one reply's state bag, by design
    """Mutable state threaded through one reply's synthesis: chunks sent, whether
    any was, whether the reply ends the call, the voiced text (for barge-in),
    what the filters took out, and the filters themselves."""

    def __init__(self) -> None:
        self.chunk_seq = 0
        self.spoke_yet = False
        self.ends_call = False
        self.spoken_text = ""
        # Audio ms dispatched so far, plus per fully-synthesized chunk:
        # (audio ms at its end, `spoken_text` through it, this chunk's text).
        # A barge-in reads these to place and measure the cut (ADR 0035).
        self.audio_ms = 0
        self.checkpoints: list[tuple[int, str, str]] = []
        # Set once the finished reply is in the history: past that point a late
        # barge-in (over the tail still playing) must not re-finalize the turn.
        self.committed = False
        # True on a Turn the closing nudge asked to end (ADR 0037): its
        # [CALL_END] is taken at its word. Elsewhere the marker is the model's
        # own idea and is vetoed on a reply that is still pressing (ADR 0037).
        self.trust_marker = False
        # Chunks the guards emptied (an echo of the user, sentences already
        # said, the cut-off sentence picked back up). A reply that ends up
        # empty *because* of these is the model with nothing new to say, not
        # an LLM failure (ADR 0038); the first one, and the nudge that names
        # it, is what a re-ask of such a reply is built on.
        self.suppressed = 0
        self.first_suppressed: tuple[str, str] | None = None
        # Set per attempt by _stream_reply_with_regeneration.
        self.filters = _NO_FILTERS


def _strip_end_marker(text_chunk: str, progress: _ReplyProgress) -> str:
    """Cut the chunk at the `[CALL_END]` marker and flag `progress.ends_call`.
    Loose regex (whitespace, case, `_`) — the model doesn't always emit it
    exactly. Everything after the marker goes with it: the chunker only flushes
    at a sentence end, so a marker mid-chunk drags the model's next sentence
    along, and merely deleting the marker had that sentence read out after the
    goodbye."""
    match = _END_CALL_RE.search(text_chunk)
    if not match:
        return text_chunk
    progress.ends_call = True
    return text_chunk[:match.start()].strip()


# The small model occasionally slips a stray CJK / Hangul character into a
# German reply; left in, TTS mispronounces it or glitches. Scrubbed before synthesis.
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


def _note_suppressed(progress: _ReplyProgress, text: str, nudge: str) -> None:
    """A chunk the filters emptied: counted, the first kept with its nudge."""
    progress.suppressed += 1
    if progress.first_suppressed is None:
        progress.first_suppressed = (repetition.first_sentence(text), nudge)


class _RegenerateReply(Exception):
    """Raised out of the reply stream before any audio has gone out, to have
    `_generate_reply` re-ask the model once (ADR 0038). Only for what a reply
    *opens* with -- a fresh greeting, or a sentence already said in this call
    -- since that is all that can be judged before the first chunk is spoken;
    the after-the-fact checks handle the rest, and those can safely end the
    call because the reply was already spoken. `nudge` is the instruction the
    retry gets, quoting `opening`."""

    def __init__(self, opening: str, nudge: str = REGENERATE_NUDGE):
        super().__init__(opening)
        self.opening = opening
        self.nudge = nudge


class SessionOrchestrator:  # pylint: disable=too-many-instance-attributes  # one call's state
    """One instance per Session. Holds the LLM message history and the Turn
    list, driving one STT → dialogue → TTS pass per Turn. A barge-in can leave a
    Turn open (`_reopen_turn`) for the next utterance to continue (ADR 0035)."""

    def __init__(self, persona: Persona, scenario: Scenario):
        # Monotonic, not wall-clock: these offsets locate utterances relative
        # to each other on the Session's timeline, and must not jump if the
        # system clock is adjusted mid-call.
        self._started = time.monotonic()
        self._language_id = persona.language_id
        self._pack = get_pack(persona.language_id)
        self._voice = persona.voice
        # Kept for the call-state notes (ADR 0071), which name the caller and
        # weigh the call against the Scenario's goal and success condition.
        self._persona = persona
        self._scenario = scenario
        # The caller's notes: what the model reads in place of the history
        # beyond the last few exchanges (ADR 0071). Refreshed in the background
        # after every completed exchange, so a refresh never sits on the path
        # to the next reply; empty until the first exchange has completed.
        self._state = ""
        self._state_task: asyncio.Task[None] | None = None
        # Only its first name is used, to spot the persona re-introducing
        # itself ("hier ist Thomas ...") a second time (ADR 0038).
        self._first_name = persona.name.split()[0].lower() if persona.name else ""
        # Consecutive turns on which the user asked to hear something again
        # (ADR 0038): the second one gets a firmer nudge than the first.
        self._repeat_requests_in_a_row = 0
        # The authenticated caller is not held here: the Session is written by
        # backend/api/session_ws.py, which already has the AuthContext, so the
        # `sub` goes straight from the handshake to `session.subject_id`
        # (ADR 0009, ADR 0031) without a second copy living on the dialogue.
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": build_system_prompt(persona, scenario, self._pack)},
        ]
        self.turns: list[Turn] = []
        self._reopen_turn: Turn | None = None
        # Set by note_barge_in() just before the turn generator is torn down, so
        # _finalize_interrupted knows how much of the reply the client played.
        self._barge_in_played_ms: int | None = None
        # The last committed reply (turn + its progress), kept revisable for a
        # barge-in that reaches the server only after the turn finished here --
        # audio is streamed ahead of playback, so its `turn.interrupt` lands
        # between turns (ADR 0035). Cleared once revised or the next turn starts.
        self._revisable: tuple[Turn, _ReplyProgress] | None = None
        # Set the moment a reply ends the call. Read by session_ws: a barge-in
        # over the tail of that reply must end the Session all the same, not
        # revive it -- one such interrupt ran a whole further Turn, and a
        # further goodbye, on a call whose history already ended (ADR 0035).
        self.ended = False

    def _elapsed_ms(self) -> int:
        """Milliseconds since the Session started."""
        return round((time.monotonic() - self._started) * 1000)

    def start_playback(self) -> None:
        """The client has begun playing the opening line; t=0 is now.

        Until this point the clock has been measuring the server's own head
        start. The opening Turn is generated as soon as the socket connects,
        which is well before the user asks for it (ADR 0042), so everything
        already on the timeline is offset by however long they spent on the
        setup and mic-check screens. Left uncorrected that wait becomes the
        user's first reaction time, and the Transcript's timestamps start
        counting from a moment nobody was in the call yet.
        """
        # The audio synthesized so far begins playing now, so the timeline is
        # shifted to put its first chunk at zero. Spacing is preserved rather
        # than each window being zeroed: only the opening Turn can be here
        # today, but that is then not load-bearing if pre-warming ever reaches
        # further than one Turn (ADR 0042).
        offsets = [t.persona_offset_ms for t in self.turns if t.persona_offset_ms is not None]
        if offsets:
            shift = min(offsets)
            for turn in self.turns:
                if turn.persona_offset_ms is not None:
                    turn.persona_offset_ms -= shift
                if turn.persona_end_ms is not None:
                    turn.persona_end_ms = max(0, turn.persona_end_ms - shift)
        self._started = time.monotonic()

    def _note_persona_audio(self, turn: Turn, audio: bytes) -> None:
        """Extend the Persona's speaking window by one synthesized chunk.

        The window has to be modelled: the server learns when it *sent* a chunk,
        never when the client finished playing it. Chunks play back to back, so
        a chunk ready before the previous one has finished extends the window
        rather than starting a new one; one that arrives after a stall starts
        from now. This is what the user's reaction time is counted from, and
        what keeps the model's own latency out of it (ADR 0051).
        """
        now = self._elapsed_ms()
        if turn.persona_offset_ms is None:
            turn.persona_offset_ms = now
        turn.persona_end_ms = max(now, turn.persona_end_ms or now) + tts.duration_ms(audio)

    def _new_or_reopened_turn(self) -> tuple[Turn, bool]:
        """Reuses a still-open turn from a prior barge-in, else creates a
        fresh one; marks it unresolved so an early interruption still counts."""
        # A stale position from a barge-in whose teardown never reached
        # _finalize_interrupted (the generator finished first) must not carry
        # into this turn's interruption.
        self._barge_in_played_ms = None
        self._revisable = None  # the previous reply is past revising now
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
            kickoff_messages = [
                *self._messages,
                {"role": "user", "content": opening_instruction(self._pack)},
            ]
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
        # Measured on a worker thread alongside the STT round trip, not after
        # it: Praat is local and fast, the gateway is neither, so the analysis
        # is finished by the time the transcript comes back (ADR 0048).
        acoustics = asyncio.create_task(asyncio.to_thread(analyze, audio_bytes))
        # The audio arrives once the user has stopped talking, so this marks
        # the utterance's end; attach_measurements walks it back to its start.
        ended_ms = self._elapsed_ms()
        turn.user_end_ms = ended_ms
        try:
            yield StateChanged(state="thinking")

            user_text = await self._transcribe_with_retry(audio_bytes, filename, content_type)
            if user_text is None:
                yield Failed(code="stt_failed", message="Transcription failed after one retry.")
                return
            if is_phantom(self._pack, user_text):
                # A VAD misfire transcribed as "*Titelm*" or "Vielen Dank." once
                # became a Turn and derailed the call (ADR 0071). Nothing was
                # said: no reply, no history, and a Turn opened for it is
                # taken back -- a reopened one just stays open.
                logger.info("Turn %d: transcript is a Whisper phantom (%d chars); no Turn", turn.seq, len(user_text))
                if not reopening:
                    self.turns.pop()
                    self._reopen_turn = None
                yield StateChanged(state="listening")
                return

            # A still-open turn from a barge-in gets the new text appended
            # onto its question instead of starting a fresh turn.
            if reopening and turn.user_text:
                turn.user_text = f"{turn.user_text} {user_text}".strip()
                self._messages[-1]["content"] = turn.user_text
            else:
                turn.user_text = user_text
                self._messages.append({"role": "user", "content": user_text})
            await attach_measurements(turn, acoustics, ended_ms)
            if turn.user_offset_ms is None:
                turn.user_offset_ms = ended_ms  # unmeasured: the end is all we know
            closing = _signals_closing(turn.user_text, self._pack)
            # The user asked to hear something again -- repeating the previous
            # reply is then the answer, not a loop, but only for the first such
            # turn in a row; a second re-dump is a loop like any other (ADR 0038).
            if _asks_to_repeat(turn.user_text, self._pack):
                self._repeat_requests_in_a_row += 1
            else:
                self._repeat_requests_in_a_row = 0

            interrupted = self._interrupted_previous_turn()
            messages = self._messages_for_turn(closing, interrupted)
            progress.trust_marker = closing

            async with contextlib.aclosing(
                self._generate_reply(
                    turn, messages, progress, force_end_call=closing,
                    allow_repetition=self._repeat_requests_in_a_row == 1,
                )
            ) as replies:
                async for event in replies:
                    yield event
            self._reopen_turn = None
        except (asyncio.CancelledError, GeneratorExit):
            # User barged in; aclosing above ensures this runs even if
            # cancellation landed between yields, not inside a network await.
            self._finalize_interrupted(turn, progress)
            raise
        finally:
            acoustics.cancel()  # no-op once awaited; releases the audio otherwise

    def _messages_for_turn(self, closing: bool, interrupted: Turn | None = None) -> list[dict[str, str]]:
        """What the model reads for this reply: the system prompt, the call so
        far, and this turn's transient nudge.

        How much of "the call so far" depends on the backend. With the notes
        kept (ADR 0071) it is the summary plus the last `HISTORY_WINDOW`
        messages verbatim, because a 4B model misreads the raw history past a
        handful of exchanges -- it attributed its own case to the user and
        asked about it for eight Turns. Without them (ADR 0075) it is the
        history itself, which is both cheaper and less lossy on a model that
        can read it. `self._messages` stays the full record either way, for the
        guards, the barge-in trims and the Transcript.

        The nudge, never stored: the closing push when the user has said
        goodbye (ADR 0037); the "you were cut off here" push when the user
        talked over the previous reply (ADR 0035), which outranks everything
        but the goodbye because it is the one the model is most lost without;
        a "say it again, reworded shorter" push when the user asked to hear
        something again (ADR 0038), firmer once they have asked twice;
        otherwise a standing reminder quoting the persona's own last reply so
        it does not come back reworded (ADR 0038), followed by the settlement
        check that reads the call against the Scenario's success condition.

        The settlement check rides on that standing nudge alone. On a closing
        turn the call is already ending, and on a repeat-request turn the user
        asked to hear something again, which is not a moment to weigh the
        matter settled."""
        if CALL_STATE_NOTES:
            notes = [{"role": "system", "content": STATE_NOTES_FRAME + self._state}] if self._state else []
            view = [self._messages[0], *notes, *self._messages[1:][-HISTORY_WINDOW:]]
        else:
            # The whole call, unbounded on purpose: a Session is one phone call,
            # so the record cannot outgrow a context measured in six figures.
            view = list(self._messages)
        if closing:
            nudge = CLOSING_NUDGE
        elif interrupted is not None and view[-1]["role"] == "user":
            # Between the dashed line and the user's message, so the message
            # is what the model sees last (see nudges.py for why this one
            # is placed differently from the rest).
            return [*view[:-1], {"role": "system", "content": INTERRUPTED_NUDGE}, view[-1]]
        elif self._repeat_requests_in_a_row >= 2:
            nudge = CLARIFY_AGAIN_NUDGE
        elif self._repeat_requests_in_a_row == 1:
            nudge = CLARIFY_NUDGE
        elif self._previous_reply():
            nudge = (
                ANTI_REPEAT_NUDGE.format(previous=self._previous_reply()) +
                self._settlement_check()
            )
        else:
            return view
        return [*view, {"role": "system", "content": nudge}]

    def _settlement_check(self) -> str:
        """The reminder that the call may end now, phrased around this
        Scenario's success condition where it has one (ADR 0073).

        Withheld over the first exchanges. Measured over the seeded library,
        this check on the opening exchanges is where it does damage and nothing
        else: nine of ten premature hang-ups landed on the user's very first
        reply, where the persona has only just said what it wants and the
        trainee cannot yet have met a condition. Asking whether the matter is
        settled there is a question with one possible answer, and the model
        answered it wrong. It cannot cost a real closing either: the persona
        opens the call and states its case, so the earliest turn on which a
        condition can honestly be met is the one this lets through.
        """
        replies = sum(1 for m in self._messages if m["role"] == "assistant")
        if replies < SETTLEMENT_CHECK_AFTER_REPLIES:
            return ""
        criterion = self._scenario.success_condition.strip() or GENERIC_CRITERION
        return SETTLEMENT_CHECK.format(criterion=criterion)

    def _schedule_state_refresh(self, turn: Turn) -> None:
        """Refresh the caller's notes from this Turn's exchange, in the
        background (ADR 0071). Called when a reply is committed and again when
        a barge-in trims it -- the notes must only ever record what the user
        heard -- so a refresh still running for the same exchange is replaced.

        A no-op where the notes are not kept (ADR 0075): nothing reads
        `self._state` there, and this is the request that would be spent
        filling it."""
        if not CALL_STATE_NOTES:
            return
        if not turn.user_text or not turn.persona_text:
            return
        if self._state_task is not None and not self._state_task.done():
            self._state_task.cancel()
        self._state_task = asyncio.create_task(self._refresh_state(turn.user_text, turn.persona_text))

    async def _refresh_state(self, user_text: str, persona_text: str) -> None:
        """One summarisation call; a failure keeps the previous notes, since
        stale notes beat none and the call must not depend on this leg."""
        messages = build_state_prompt(self._state, user_text, persona_text, self._persona, self._scenario)
        try:
            notes = await llm.complete(messages, max_tokens=STATE_MAX_TOKENS)
        except (OpenAIError, TimeoutError, OSError) as e:
            logger.warning("Call-state notes not refreshed: %s", e)
            return
        if notes.strip():
            self._state = notes.strip()

    async def flush_state(self) -> None:
        """Wait for a pending notes refresh -- for tests and for nothing else;
        the live path never waits on it."""
        if self._state_task is not None:
            await asyncio.gather(self._state_task, return_exceptions=True)

    def close(self) -> None:
        """The Session is over: a refresh still in flight has no reader."""
        if self._state_task is not None and not self._state_task.done():
            self._state_task.cancel()

    def _interrupted_previous_turn(self) -> Turn | None:
        """The Turn whose Persona reply the user talked over, if that reply is
        the one the model last gave (ADR 0035) -- else None. The current Turn is
        already on the list, so the previous reply belongs to the last earlier
        Turn with Persona text; a reopened Turn has none and is skipped by the
        same rule, which is right: its dropped reply left the history too."""
        for turn in reversed(self.turns[:-1]):
            if turn.persona_text:
                return turn if turn.persona_interrupted else None
        return None

    async def _attempt_reply_with_retry(
        self,
        turn: Turn,
        messages: list[dict[str, str]],
        progress: _ReplyProgress,
    ) -> AsyncIterator[TurnEvent]:
        """One reply attempt plus one retry on an LLM error or empty completion.
        Yields the reply's events; yields a Failed event and stops if it can't be
        delivered. May raise `_RegenerateReply` before the first audio (ADR 0038)."""
        for llm_attempt in range(2):  # initial attempt + one retry
            try:
                stream = self._stream_and_synthesize(turn, messages, progress)
                async with contextlib.aclosing(stream) as chunks:
                    async for event in chunks:
                        yield event
                        if isinstance(event, Failed):
                            return
                if turn.persona_text.strip():
                    return
                if progress.suppressed:
                    # The model produced text, and all of it was a repeat -- of
                    # the user's line or of its own -- that the guards took out.
                    # That is a caller with nothing left to say, not a failed
                    # completion: end with the sign-off rather than an error.
                    logger.info("Turn %d reply was nothing but repeats; ending the call", turn.seq)
                    progress.ends_call = True
                    return

                # A completion can finish cleanly without producing any usable text.
                # Treat that like an LLM failure: otherwise the Turn would complete
                # successfully with an empty Persona reply in the conversation history.
                logger.warning("LLM returned an empty reply (attempt %d)", llm_attempt + 1)
                if llm_attempt == 1:
                    yield Failed(
                        code="llm_failed",
                        message="Language model returned an empty reply.",
                    )
                    return
            except OpenAIError as e:
                logger.error("LLM request failed (attempt %d): %s", llm_attempt + 1, e)
                # Retry only before any audio has gone out (ADR 0033): a fresh
                # completion would diverge from what the user already heard.
                if progress.spoke_yet or llm_attempt == 1:
                    yield Failed(code="llm_failed", message=str(e))
                    return
                turn.persona_text = ""  # retry from scratch

    async def _stream_reply_with_regeneration(
        self,
        turn: Turn,
        messages: list[dict[str, str]],
        progress: _ReplyProgress,
        force_end_call: bool,
        allow_repetition: bool,
    ) -> AsyncIterator[TurnEvent]:
        """The reply stream (one LLM attempt plus one retry on error), plus one
        regeneration if it opened by greeting again (ADR 0038) — caught before
        any audio, so the restart costs only an extra completion. Exempt: a
        nudged closing (asked for a fresh goodbye) and a turn where the user
        asked to hear something again (a greeting may be the answer)."""
        normal = not force_end_call and not allow_repetition
        # Computed once: neither changes between the attempt and its re-ask.
        said = frozenset(self._said_sentences()) if normal else frozenset()
        cut_off = self._cut_off_sentence() if normal else ""
        for regeneration in range(2):  # first pass + one regeneration
            progress.filters = _ReplyFilters(
                guard=normal and regeneration == 0, filter_repeats=normal, said=said, cut_off=cut_off,
            )
            try:
                async with contextlib.aclosing(
                    self._attempt_reply_with_retry(turn, messages, progress)
                ) as events:
                    async for event in events:
                        yield event
                return
            except _RegenerateReply as restart:
                logger.info(
                    "Turn %d reply restarted the call (%r); regenerating once",
                    turn.seq, restart.opening,
                )
                messages = [
                    *messages,
                    {"role": "system", "content": restart.nudge.format(opening=restart.opening)},
                ]
                # Nothing was spoken, so only the marker flag and the
                # suppression tally can have moved.
                turn.persona_text = ""
                progress.ends_call = False
                progress.suppressed = 0
                progress.first_suppressed = None

    async def _generate_reply(
        self,
        turn: Turn,
        messages: list[dict[str, str]],
        progress: _ReplyProgress,
        force_end_call: bool = False,
        allow_repetition: bool = False,
    ) -> AsyncIterator[TurnEvent]:
        """Drive the reply and append the finished text to history, yielding
        events. Gives up on a `Failed` leg."""
        async with contextlib.aclosing(
            self._stream_reply_with_regeneration(turn, messages, progress, force_end_call, allow_repetition)
        ) as events:
            async for event in events:
                yield event
                if isinstance(event, Failed):
                    return

        turn.persona_text = turn.persona_text.strip()
        if turn.persona_text and turn.persona_offset_ms is None:
            # Words with no audio behind them (synthesis failed): place them on
            # the timeline as an instant, so the Transcript still reads in order.
            turn.persona_offset_ms = turn.persona_end_ms = self._elapsed_ms()
        spoke = bool(turn.persona_text)
        # When the user asked for a repeat, repeating or restating the
        # *immediately previous* reply is the answer, not a loop -- but a
        # verbatim repeat of an *older* reply, and a sentence stuttered inside
        # one reply, still are (ADR 0038).
        repeated_reply = spoke and (
            repetition.has_repeated_sentence(turn.persona_text) or
            self._repeats_earlier_reply(turn.persona_text, exclude_last=allow_repetition) or
            (not allow_repetition and self._repeats_last_reply(turn.persona_text))
        )
        restates = spoke and not allow_repetition and self._restates_previous_reply(turn.persona_text)
        self._messages.append({"role": "assistant", "content": turn.persona_text})
        progress.committed = True

        # force_end_call backstops [CALL_END]: a small model won't always
        # include the marker even when told to (confirmed in testing).
        #
        # said_goodbye is the mirror of ADR 0037's veto, and it catches an
        # obedient model rather than a careless one. The prompt forbids the
        # marker in a reply that also says the matter is not settled -- so a
        # reply that voices a reservation *and* signs off ("...sonst muessen
        # wir eskalieren. Ich danke Ihnen. Auf Wiederhoeren.") withholds the
        # marker exactly as instructed, and the call then hung on a persona
        # that had audibly hung up. The same `farewell_re` that already
        # overrules `_still_pressing` decides here, so both directions read the
        # goodbye the same way.
        said_goodbye = spoke and not progress.ends_call and bool(
            self._pack.farewell_re.search(turn.persona_text)
        )
        ends_call = progress.ends_call or force_end_call or repeated_reply or restates or said_goodbye
        if ends_call:
            self.ended = True
            logger.info(
                "Turn %d ends the call (model marker=%s, closing-intent check=%s, "
                "repeated reply=%s, restated reply=%s, said goodbye=%s)",
                turn.seq,
                progress.ends_call,
                force_end_call,
                repeated_reply,
                restates,
                said_goodbye,
            )
            # Only the closing-intent path actually asked the model for a
            # goodbye (CLOSING_NUDGE); a repeat or an unprompted ending
            # didn't, so it can't be trusted to have included one. said_goodbye
            # is deliberately absent from this list -- it *is* the goodbye, and
            # appending the fallback line would say it twice.
            if repeated_reply or restates or (progress.ends_call and not force_end_call):
                async for event in self._speak_fallback_closing(turn, progress):
                    yield event
        yield TurnCompleted(turn_seq=turn.seq, ends_call=ends_call)
        if not ends_call:
            self._schedule_state_refresh(turn)
            # Audio was streamed ahead of playback, so the client is still
            # speaking this reply's tail and a barge-in over it reaches the
            # server only now, between turns -- keep the reply revisable so that
            # late interrupt can still trim it to what was heard (ADR 0035).
            self._revisable = (turn, progress)
            yield StateChanged(state="listening")

    async def _speak_fallback_closing(self, turn: Turn, progress: _ReplyProgress) -> AsyncIterator[TurnEvent]:
        """Synthesizes a guaranteed sign-off for a backstopped ending,
        instead of trusting the Persona's own reply to have included one."""
        try:
            audio = await tts.synthesize(
                self._pack.fallback_closing_line, self._voice, self._language_id
            )
        except (KugelAudioError, OpenAIError, TimeoutError, OSError) as e:
            logger.warning("Fallback closing line could not be synthesized: %s", e)
            return
        if not progress.spoke_yet:
            yield StateChanged(state="speaking")
            progress.spoke_yet = True
        progress.chunk_seq += 1
        self._note_persona_audio(turn, audio)
        yield AudioChunk(turn_seq=turn.seq, chunk_seq=progress.chunk_seq, audio=audio)
        turn.persona_text = f"{turn.persona_text} {self._pack.fallback_closing_line}".strip()
        self._messages[-1]["content"] = turn.persona_text

    def _previous_reply(self) -> str:
        """The Persona's last reply, or "" on the opening Turn. Call before the
        current reply has been appended to history."""
        for message in reversed(self._messages):
            if message["role"] == "assistant":
                return message["content"]
        return ""

    def _repeats_last_reply(self, text: str) -> bool:
        """True if this reply repeats its predecessor verbatim (modulo case and
        whitespace) — the cross-Turn form of `repetition.has_repeated_sentence` (ADR 0038)."""
        return bool(text.strip()) and self._previous_reply().strip().lower() == text.strip().lower()

    def _repeats_earlier_reply(self, text: str, exclude_last: bool = False) -> bool:
        """True if this reply reproduces one the persona gave further back than
        the previous Turn, verbatim modulo case and whitespace — an A-B-A-B
        oscillation, which `_repeats_last_reply` walks straight past because the
        repeat is two Turns back (ADR 0038).

        A trivially short reply ("Ja, genau.") can recur across the call without
        being a loop, so only substantial ones count here — unlike
        `_repeats_last_reply`, where an exact back-to-back repeat is degenerate
        at any length.

        `exclude_last` drops the immediately previous reply from the search:
        when the user asked to hear it again, reproducing *that* one is the
        answer, but reproducing one from further back is still a loop.
        """
        candidate = text.strip().lower()
        if len(candidate) < repetition.MIN_LOOP_REPLY_CHARS:
            return False
        earlier = [m["content"] for m in self._messages if m["role"] == "assistant"]
        if exclude_last:
            earlier = earlier[:-1]
        return any(content.strip().lower() == candidate for content in earlier)

    def _restates_previous_reply(self, text: str) -> bool:
        """True if most of this reply was already in its predecessor — the
        partial form of `_repeats_last_reply` (ADR 0038)."""
        return repetition.restates(text, self._previous_reply())

    def _assistant_lines(self) -> list[str]:
        """Every reply the persona has given so far, oldest first. `[0]` is the
        opening line once it exists; empty on the opening Turn itself."""
        return [m["content"] for m in self._messages if m["role"] == "assistant"]

    def _reintroduces(self, first_chunk: str) -> bool:
        """Whether a reply *opens* by greeting or re-introducing after the call
        is already under way — the model restarting the call instead of
        continuing it (ADR 0038). Judged on the first chunk, before it is
        spoken, so `_generate_reply` can regenerate rather than end the call.

        Narrow on purpose: a greeting at the very start of the reply, plus
        either the persona's own name or the opening's wording carried over.
        A late "Guten Tag" mirrored back at a user who greeted first is the
        one legitimate case, and it still costs only a regeneration."""
        earlier = self._assistant_lines()
        if not earlier:  # the opening Turn — greeting is correct here
            return False
        opener = first_chunk.strip()
        words = repetition.word_set(opener)
        if len(words) < repetition.MIN_REINTRO_WORDS:
            return False
        if not self._pack.regreeting_re.match(opener):
            return False
        # A greeting at the very start of a reply is already the tell; pair it
        # with the persona naming itself again, or the opening's own wording
        # carried straight over, so a greeting mirrored back at a late-greeting
        # user is the only thing that slips through.
        if self._first_name and self._first_name in words:
            return True
        return repetition.word_overlap(opener, earlier[0]) >= repetition.REINTRO_OVERLAP

    def note_barge_in(self, played_ms: int | None) -> None:
        """How much of the reply the client played before the user cut in. Trim
        now if it is already committed (`_revisable` set -- the teardown will
        find nothing left); else stash it for `_finalize_interrupted` (ADR 0035)."""
        if self._revisable is not None:
            self._revise_committed_reply(*self._revisable, played_ms)
        else:
            self._barge_in_played_ms = played_ms

    def note_late_barge_in(self, played_ms: int | None) -> None:
        """A barge-in that reached the server only after the turn's event loop
        had returned (its reply's tail still playing on the client): trim the
        committed reply, or nothing if there is none to trim (ADR 0035)."""
        if self._revisable is not None:
            self._revise_committed_reply(*self._revisable, played_ms)

    def _revise_committed_reply(
        self, turn: Turn, progress: _ReplyProgress, played_ms: int | None
    ) -> None:
        """Trim a reply already in the history and the Transcript back to the
        part the client played (ADR 0035) -- both in step, so the model never
        reads more than the user heard. Only ever shrinks: a stale re-entry
        (the teardown re-running this with no played position of its own)
        recomputes the full text and must leave the trimmed reply alone."""
        self._revisable = None
        if not progress.committed or not turn.persona_text:
            return
        last = self._messages[-1] if self._messages else {}
        if last.get("role") != "assistant" or last.get("content") != turn.persona_text:
            return
        heard = heard_text(progress.checkpoints, progress.spoken_text, played_ms)
        if not heard:
            # Nothing heard: drop the reply, keep the turn open to continue it.
            turn.persona_text = ""
            self._messages.pop()
            self._reopen_turn = turn
            return
        if len(heard) >= len(turn.persona_text):
            return  # heard all of it, or a stale re-entry -- nothing to trim
        logger.info("Turn %d reply trimmed to the heard part: %r", turn.seq, heard)
        turn.persona_text = heard
        turn.persona_interrupted = True
        # The dash tells the model this line was cut off (see nudges.py); the
        # words themselves are exactly the Transcript's, still in step.
        self._messages[-1]["content"] = f"{heard}{INTERRUPTED_MARK}"
        self._reopen_turn = None
        self._schedule_state_refresh(turn)  # the notes must not know the unheard part

    def _finalize_interrupted(self, turn: Turn, progress: _ReplyProgress) -> None:
        """Barge-in cleanup (ADR 0035). Commit only what the client played --
        `heard_text` -- and close the Turn; if nothing was heard, discard the
        reply and leave the Turn open for the next utterance to continue it.
        "Dispatched as audio" is not "heard": the server streams ahead, so
        committing everything sent put lines in the history the user never got.
        """
        played_ms = self._barge_in_played_ms
        self._barge_in_played_ms = None
        if progress.committed:
            # Already in the history (server streams ahead) -- trim it and the
            # Transcript back to what was heard, in step (ADR 0035).
            self._revise_committed_reply(turn, progress, played_ms)
            return
        if not progress.spoke_yet:
            turn.persona_text = ""
            return
        heard = heard_text(progress.checkpoints, progress.spoken_text, played_ms)
        if heard:
            turn.persona_text = heard
            turn.persona_interrupted = True
            self._messages.append({"role": "assistant", "content": f"{heard}{INTERRUPTED_MARK}"})
            self._reopen_turn = None
            self._schedule_state_refresh(turn)
        else:
            turn.persona_text = ""

    def _clean_chunk(self, turn: Turn, text_chunk: str, progress: _ReplyProgress) -> str:
        """One chunk as it will be spoken: the end marker cut off and flagged,
        stray script and a copied cut-off dash scrubbed, repeats dropped, and
        an unprompted end marker vetoed while the reply is still pressing (ADR
        0037) -- the model ended a call mid-demand ("Ich will wissen, wann
        ..."), which was heard as hanging up."""
        text_chunk = _strip_end_marker(text_chunk, progress)
        text_chunk = _strip_foreign_script(text_chunk)
        text_chunk = strip_interrupted_mark(text_chunk)  # copied from the history (nudges.py)
        if progress.filters.filter_repeats and text_chunk:
            text_chunk = self._drop_repeats(turn, text_chunk, progress)
        if progress.ends_call and not progress.trust_marker:
            if self._still_pressing(f"{turn.persona_text} {text_chunk}"):
                logger.info("Turn %d: unprompted [CALL_END] on a reply that is still pressing; ignored", turn.seq)
                progress.ends_call = False
        return text_chunk

    def _drop_repeats(self, turn: Turn, text_chunk: str, progress: _ReplyProgress) -> str:
        """Sentences already said in this call (ADR 0038), and the sentence the
        user cut off last Turn picked back up from the top (ADR 0035), taken
        out before the chunk is spoken. A chunk emptied by this counts as
        suppressed, with the nudge that names why."""
        filters = progress.filters
        kept, dropped = repetition.drop_said_sentences(text_chunk, filters.said)
        if dropped:
            logger.info("Turn %d reply repeated %d sentence(s) already said; dropped", turn.seq, len(dropped))
            if not kept:
                _note_suppressed(progress, dropped[0], REPEAT_OPENING_NUDGE)
        if filters.cut_off and kept:
            kept, resumed = repetition.drop_resumed_sentences(kept, filters.cut_off)
            if resumed:
                logger.info("Turn %d reply picked the cut-off sentence back up from the top; dropped", turn.seq)
                if not kept:
                    _note_suppressed(progress, resumed[0], RESUME_NUDGE)
        return kept

    def _cut_off_sentence(self) -> str:
        """The sentence the user talked over last Turn, or "" -- what this
        reply must not pick back up in any form (ADR 0035)."""
        interrupted = self._interrupted_previous_turn()
        return repetition.last_sentence(interrupted.persona_text) if interrupted is not None else ""

    def _said_sentences(self) -> set[str]:
        """Every content sentence the persona has said so far, normalised."""
        return repetition.said_sentences(strip_interrupted_mark(line) for line in self._assistant_lines())

    def _still_pressing(self, text: str) -> bool:
        """Whether a reply ends on a demand or a question rather than a
        goodbye. A farewell anywhere in the reply wins outright: half of the
        legitimate endings measured in docs/research/model-parameters.md finish
        on a trailing question ("Auf Wiederhören. Darf ich mich melden?"), so
        the farewell decides, not the last sentence's shape."""
        if self._pack.farewell_re.search(text):
            return False
        last = repetition.last_sentence(text)
        return last.endswith("?") or bool(self._pack.still_pressing_re.search(last))

    def _guard_opening(self, turn: Turn, text_chunk: str, progress: _ReplyProgress) -> str:
        """The checks on how a reply *opens*, run on its first chunk before any
        of it is spoken. A verbatim read-back of the user's line is dropped
        (seen on the Turn after a barge-in, ADR 0035); so is a start in
        mid-sentence -- lower-case, the tail of the sentence the user cut off
        (ADR 0035). Then, if guarding, a fresh greeting or a sentence already
        said raises `_RegenerateReply` (ADR 0038). Returns the chunk to speak,
        possibly empty; a chunk emptied here counts as suppressed."""
        filters = progress.filters
        if turn.user_text:
            stripped = repetition.strip_echoed_prefix(text_chunk, turn.user_text)
            if stripped != text_chunk:
                logger.info("Turn %d reply opened by reading the user's line back; dropped", turn.seq)
                if not stripped.strip():
                    _note_suppressed(progress, text_chunk, ECHO_NUDGE)
                text_chunk = stripped
        if filters.cut_off and text_chunk[:1].islower():
            logger.info("Turn %d reply continued the cut-off sentence; dropped its tail", turn.seq)
            rest = repetition.without_first_sentence(text_chunk)
            if not rest:
                _note_suppressed(progress, text_chunk, RESUME_NUDGE)
            text_chunk = rest
        if not filters.guard or not text_chunk.strip():
            return text_chunk
        if self._reintroduces(text_chunk):
            raise _RegenerateReply(repetition.first_sentence(text_chunk))
        repeated = self._repeats_earlier_opening(text_chunk)
        if repeated is not None:
            raise _RegenerateReply(repeated, REPEAT_OPENING_NUDGE)
        return text_chunk

    def _repeats_earlier_opening(self, first_chunk: str) -> str | None:
        """The first sentence of `first_chunk` if the persona has already said
        exactly that sentence earlier in the call, else None (ADR 0038). The
        pre-synthesis form of `_repeats_earlier_reply` / `_repeats_last_reply`:
        after two barge-ins the history holds short cut-off lines that a 4B
        model reproduces readily, and an exact repeat spoken out loud can only
        be answered by ending the call, so it is caught here and regenerated
        once instead. Short openers ("Ja, genau.") recur naturally and don't count."""
        opening = repetition.first_sentence(first_chunk)
        if len(opening) < repetition.MIN_LOOP_REPLY_CHARS:
            return None
        candidate = opening.lower()
        for line in self._assistant_lines():
            if repetition.first_sentence(strip_interrupted_mark(line)).lower() == candidate:
                return opening
        return None

    async def _stream_and_synthesize(
        self,
        turn: Turn,
        messages: list[dict[str, str]],
        progress: _ReplyProgress,
    ) -> AsyncIterator[TurnEvent]:
        """Stream one LLM completion; feed each sentence-sized chunk to TTS and
        forward its audio sub-chunks to the client as they are generated.

        Every chunk passes `progress.filters` first (ADR 0035, ADR 0038). Under
        `guard` a reply that opens by re-greeting or repeating raises
        `_RegenerateReply` before any audio -- as does a reply that the filters
        emptied *entirely* (an echo, a re-said sentence, the cut-off sentence
        picked back up): the model is re-asked once with the nudge that names
        what it did, and no audio goes out."""
        first_chunk = True
        async for text_chunk in sentence_chunks(llm.stream_reply(messages)):
            if first_chunk:
                text_chunk = self._guard_opening(turn, text_chunk, progress)
                # An echo is often the whole first chunk (one sentence, past the
                # first-chunk floor), so the opening checks stay armed until a
                # chunk with words in it has been seen.
                first_chunk = not text_chunk.strip()

            text_chunk = self._clean_chunk(turn, text_chunk, progress)

            if text_chunk:
                # aclosing, not a bare loop: closing this generator on a
                # barge-in must close _speak, and with it the KugelAudio
                # stream, *now* -- left to the garbage collector, the pooled
                # socket is reset only later, maybe after the next chunk
                # already went out on it (ADR 0044 amendment).
                async with contextlib.aclosing(self._speak(turn, text_chunk, progress)) as spoken:
                    async for event in spoken:
                        yield event
                        if isinstance(event, Failed):
                            return

            if progress.ends_call:
                break  # nothing meaningful should follow the marker

        if progress.filters.guard and progress.first_suppressed is not None and not progress.spoke_yet:
            raise _RegenerateReply(*progress.first_suppressed)

    async def _speak(self, turn: Turn, text_chunk: str, progress: _ReplyProgress) -> AsyncIterator[TurnEvent]:
        """Synthesize one chunk and forward its audio as KugelAudio produces it,
        piece by piece (ADR 0044). A failure past the fallback ends the Turn."""
        voiced = False
        stream = tts.synthesize_stream(text_chunk, self._voice, self._language_id)
        try:
            async for wav in stream:
                if not voiced:
                    voiced = True
                    # Only commit Persona text once TTS has actually produced audio.
                    # Otherwise a silent TTS stream would leave an unheard reply in the Turn.
                    turn.persona_text += text_chunk + " "
                    progress.spoken_text += text_chunk + " "
                if not progress.spoke_yet:
                    yield StateChanged(state="speaking")
                    progress.spoke_yet = True
                progress.chunk_seq += 1
                self._note_persona_audio(turn, wav)
                progress.audio_ms += tts.duration_ms(wav)
                yield AudioChunk(turn_seq=turn.seq, chunk_seq=progress.chunk_seq, audio=wav)
            if voiced:
                # Chunk fully synthesized: record where its audio ends so a
                # later barge-in can measure how much of it played (ADR 0035).
                progress.checkpoints.append(
                    (progress.audio_ms, progress.spoken_text.strip(), text_chunk.strip())
                )
            else:
                logger.error("TTS synthesis returned no audio")
                yield Failed(
                    code="tts_failed",
                    message="Text-to-speech returned no audio.",
                )
        except (KugelAudioError, OpenAIError, TimeoutError, OSError) as e:
            logger.error("TTS synthesis failed: %s", e)
            yield Failed(code="tts_failed", message=str(e))
        finally:
            # Closed here, deterministically, not by the garbage collector
            # later: a stream abandoned by a barge-in has to reset the pooled
            # KugelAudio socket *before* the next chunk is synthesized (tts.py).
            await stream.aclose()

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
