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
# No `too-many-lines` exception any more: cutting the seams out -- the system
# prompt to prompting.py, the per-turn pushes to nudges.py, the heard-text
# record to heard.py, the verdicts to reply_checks.py -- brought this back
# under pylint's 1000-line ceiling on its own. What is left is one call's
# control flow, and carving it further would split a single flow across files
# to buy lines. If the ceiling is reached again, that is the warning doing its
# job rather than something to mute.

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from typing import NamedTuple

from kugelaudio.exceptions import KugelAudioError
from openai import OpenAIError

from backend.clients import llm, stt, tts
from backend.feedback.acoustics import analyze
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.call_notes import CallNotes
from backend.session.chunking import sentence_chunks
from backend.session.heard import Cut, SpokenReply
from backend.session.history import History
from backend.session.measuring import attach_measurements
from backend.session import repetition
from backend.session import reply_checks as checks
from backend.session.prompting import build_system_prompt, opening_instruction
from backend.session import nudges
from backend.session.nudges import (
    ECHO_NUDGE, INTERRUPTED_MARK, REGENERATE_NUDGE, REPEAT_OPENING_NUDGE, RESUME_NUDGE,
    strip_interrupted_mark,
)
from backend.session.language_packs import LanguagePack, get_pack, is_phantom, signals_closing
from backend.session.models import AudioChunk, Failed, StateChanged, Turn, TurnCompleted, TurnEvent

logger = logging.getLogger(__name__)


_END_CALL_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

# How many history messages the model reads verbatim beside the caller's notes
# (ADR 0071): the last three exchanges. Everything before them reaches the model
# only as its notes.
#
# The notes are always kept. They are a compression built for a model that
# could not read its own transcript, and for a while a second backend that
# could read one turned them off (ADR 0075); with one backend left (ADR 0103)
# there is nothing to switch between, and what they cost is one background
# request per exchange.
HISTORY_WINDOW = 6


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


class _ReplyProgress:
    """Mutable state threaded through one reply's synthesis: chunks sent, whether
    any was, whether the reply ends the call, the voiced text (for barge-in),
    what the filters took out, and the filters themselves."""

    def __init__(self) -> None:
        self.chunk_seq = 0
        self.spoke_yet = False
        self.ends_call = False
        # The voiced text and the audio behind it, which a barge-in cuts
        # (ADR 0035).
        self.spoken = SpokenReply()
        # Set once the finished reply is in the history: past that point a late
        # barge-in (over the tail still playing) must not re-finalize the turn.
        self.committed = False
        # True on a Turn the user closed and the closing nudge asked to end
        # (ADR 0037). The reply then ends the call whether or not it carried
        # [CALL_END], and a marker it did carry is taken at its word; elsewhere
        # the marker is the model's own idea and is vetoed on a reply that is
        # still pressing. One flag: it was two, `trust_marker` here and a
        # `force_end_call` argument through two frames, always set to the same
        # value.
        self.closing = False
        # True on the first Turn in a row where the user asked to hear something
        # again (ADR 0038): repeating the previous reply is then the answer.
        self.allow_repetition = False
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


def _empty_reply_is_an_ending(turn: Turn, progress: _ReplyProgress) -> bool:
    """Whether a reply that spoke no words is a caller hanging up rather than a
    failed completion. Both ways it is end the call, and `_generate_reply`
    speaks the fallback sign-off, since nothing was said.

    The marker and nothing else: alone, or first in the chunk, which drags the
    rest of it along (`_strip_end_marker`). Taking it at its word is what
    ADR 0037 asks for on a Turn the closing nudge sent; answering a goodbye
    with a pipeline error was the alternative, and it stored the Session as
    aborted. Or the guards emptied the reply: a caller with nothing left to
    say (ADR 0038)."""
    if progress.ends_call:
        logger.info("Turn %d reply was the end marker alone; ending the call", turn.seq)
        return True
    if progress.suppressed:
        logger.info("Turn %d reply was nothing but repeats; ending the call", turn.seq)
        progress.ends_call = True
        return True
    return False


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
        self._scenario = scenario
        # The caller's notes: what the model reads in place of the history
        # beyond the last few exchanges (ADR 0071). Public so a test can wait
        # for a refresh.
        self.notes = CallNotes(persona, scenario)
        # Whether `session.activate` has already rebased the clock. See there.
        self._playback_started = False
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
        self.history = History(build_system_prompt(persona, scenario, self._pack))
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

        Ignored after the first time. `session.activate` is a client message
        and both receive loops pass it straight through, so a second one --
        a reconnect, a replay, a client that sends it twice -- would rebase the
        session clock in the middle of a call while the Turns already written
        kept their older, larger offsets. Every offset, reaction time, pause
        and overlap after that is wrong, and wrong in a way that still looks
        plausible (ADR 0051).

        Until this point the clock has been measuring the server's own head
        start. The opening Turn is generated as soon as the socket connects,
        which is well before the user asks for it (ADR 0042), so everything
        already on the timeline is offset by however long they spent on the
        setup and mic-check screens. Left uncorrected that wait becomes the
        user's first reaction time, and the Transcript's timestamps start
        counting from a moment nobody was in the call yet.
        """
        if self._playback_started:
            logger.info("Ignoring a second session.activate; the clock is already running")
            return
        self._playback_started = True
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
                if turn.persona_dispatched_end_ms is not None:
                    turn.persona_dispatched_end_ms = max(0, turn.persona_dispatched_end_ms - shift)
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
        # The same instant, kept in a field a barge-in never trims: F-51 reads
        # it to say how much the Persona still had to say (see `Turn`).
        turn.persona_dispatched_end_ms = turn.persona_end_ms

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
        """Have the Persona speak first: a freshly generated, varied call opener.

        In a reverse (ADR 0070) it speaks first here too -- it is the one
        picking up the phone -- and the instruction, not this Turn, is what
        makes it say only that.
        """
        turn, _ = self._new_or_reopened_turn()
        progress = _ReplyProgress()
        try:
            yield StateChanged(state="thinking")
            kickoff_messages = [
                *self.history.messages,
                {
                    "role": "user",
                    "content": opening_instruction(self._pack, self._scenario.reverse),
                },
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
        # Written onto the Turn only once the transcript proves somebody spoke:
        # a phantom pops a fresh Turn but leaves a reopened one standing, and
        # its user window would then end at a cough, stretching the utterance
        # that F-51 reads off the timeline by the whole dead time before it.
        ended_ms = self._elapsed_ms()
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

            turn.user_end_ms = ended_ms
            # A still-open turn from a barge-in gets the new text appended
            # onto its question instead of starting a fresh turn.
            if reopening and turn.user_text:
                turn.user_text = f"{turn.user_text} {user_text}".strip()
                self.history.extend_question(turn.user_text)
            else:
                turn.user_text = user_text
                self.history.add_question(user_text)
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
            progress.closing = closing
            progress.allow_repetition = self._repeat_requests_in_a_row == 1

            async with contextlib.aclosing(
                self._generate_reply(turn, messages, progress)
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

        "The call so far" is the caller's notes plus the last
        `HISTORY_WINDOW` messages verbatim (ADR 0071), because a 4B model
        misreads the raw history past a handful of exchanges -- it attributed
        its own case to the user and asked about it for eight Turns.
        `self.history` stays the full record, for the guards, the barge-in
        trims and the Transcript.

        The nudge is never stored, and which one it is is `nudges.for_turn`'s."""
        view = [self.history.system(), *self.notes.message(), *self.history.recent(HISTORY_WINDOW)]
        nudge = nudges.for_turn(
            closing=closing,
            interrupted=interrupted is not None and view[-1]["role"] == "user",
            repeat_requests=self._repeat_requests_in_a_row,
            previous_reply=self.history.previous_reply(),
            replies=len(self.history.replies()),
            reverse=self._scenario.reverse,
            call_goal=self._scenario.call_goal,
        )
        if nudge is None:
            return view
        message = {"role": "system", "content": nudge.content}
        if nudge.before_last:
            return [*view[:-1], message, view[-1]]
        return [*view, message]

    def _schedule_state_refresh(self, turn: Turn) -> None:
        """Refresh the caller's notes from this Turn's exchange (ADR 0071).
        Called when a reply is committed and again when a barge-in trims it --
        the notes must only ever record what the user heard."""
        self.notes.refresh(turn)

    def _discard_state_refresh(self, turn: Turn) -> None:
        """The reply was dropped whole: the notes go back to before it."""
        self.notes.discard(turn)

    def close(self) -> None:
        """The Session is over: a refresh still in flight has no reader."""
        self.notes.close()

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
                if _empty_reply_is_an_ending(turn, progress):
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
    ) -> AsyncIterator[TurnEvent]:
        """The reply stream (one LLM attempt plus one retry on error), plus one
        regeneration if it opened by greeting again (ADR 0038) — caught before
        any audio, so the restart costs only an extra completion. Exempt: a
        nudged closing (asked for a fresh goodbye) and a turn where the user
        asked to hear something again (a greeting may be the answer)."""
        normal = not progress.closing and not progress.allow_repetition
        # Computed once: neither changes between the attempt and its re-ask.
        said = frozenset(checks.said_sentences(self.history.replies())) if normal else frozenset()
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
    ) -> AsyncIterator[TurnEvent]:
        """Drive the reply and append the finished text to history, yielding
        events. Gives up on a `Failed` leg."""
        async with contextlib.aclosing(
            self._stream_reply_with_regeneration(turn, messages, progress)
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
        # Read against the replies before this one joins them.
        ending = checks.ending(
            turn.persona_text,
            self.history.replies(),
            marker=progress.ends_call,
            closing=progress.closing,
            allow_repetition=progress.allow_repetition,
            pack=self._pack,
        )
        self.history.add_reply(turn.persona_text)
        progress.committed = True

        if ending.ends:
            self.ended = True
            logger.info(
                "Turn %d ends the call (model marker=%s, closing-intent check=%s, "
                "repeated reply=%s, restated reply=%s, said goodbye=%s)",
                turn.seq,
                ending.marker,
                ending.closing,
                ending.repeated,
                ending.restates,
                ending.said_goodbye,
            )
            if ending.needs_fallback:
                async for event in self._speak_fallback_closing(turn, progress):
                    yield event
        yield TurnCompleted(turn_seq=turn.seq, ends_call=ending.ends)
        if not ending.ends:
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
        self.history.revise_reply(turn.persona_text)

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
        if not self.history.last_reply_is(turn.persona_text):
            return
        cut = progress.spoken.cut(played_ms)
        if not cut.heard:
            # Nothing heard: drop the reply, keep the turn open to continue it.
            turn.persona_text = ""
            self.history.drop_reply()
            self._reopen_turn = turn
            self._trim_persona_window(turn, played_ms)
            self._discard_state_refresh(turn)
            return
        if len(cut.heard) >= len(turn.persona_text):
            return  # heard all of it, or a stale re-entry -- nothing to trim
        # Same rule as the pipeline's (clients/stt.py): the trimmed line is
        # spoken content, and the log file is outside every deletion path
        # (ADR 0066). The length says the trim happened and by how much, which
        # is the whole of what this line is read for.
        logger.info("Turn %d reply trimmed to the heard part (%d of %d characters)",
                    turn.seq, len(cut.heard), len(turn.persona_text))
        self._commit_heard(turn, cut, played_ms, self.history.revise_reply)

    def _commit_heard(
        self, turn: Turn, cut: Cut, played_ms: int | None, write: Callable[[str], None]
    ) -> None:
        """Make the heard part of a cut reply the Turn's and the history's line.

        `write` is how it enters the history: appended for a reply still being
        generated, revised in place for one already committed. Everything else
        is the same on both paths, which is why it is written once.
        """
        turn.persona_unheard = cut.unheard
        turn.persona_text = cut.heard
        turn.persona_interrupted = True
        # The dash tells the model this line was cut off (see nudges.py); the
        # words themselves are exactly the Transcript's, still in step.
        write(f"{cut.heard}{INTERRUPTED_MARK}")
        self._reopen_turn = None
        self._trim_persona_window(turn, played_ms)
        self._schedule_state_refresh(turn)  # the notes must not know the unheard part

    @staticmethod
    def _trim_persona_window(turn: Turn, played_ms: int | None) -> None:
        """Cut the Persona's speaking window back to what the client played.

        The window is modelled from audio *dispatched* (`_note_persona_audio`),
        which after a barge-in runs past anything anybody heard -- by the whole
        reply where none of it was played. F-53's Redeanteil is the share of
        that time, so leaving it would report speech the user never got. Only
        ever shrinks, and only with a position to shrink to.

        `persona_dispatched_end_ms` is deliberately left where it was. F-51
        needs the untrimmed end to say how much the Persona still had to say,
        and when this trimmed the one field both of them read, that measurement
        quietly became the browser's voice-detection delay instead."""
        if played_ms is None or turn.persona_offset_ms is None or turn.persona_end_ms is None:
            return
        turn.persona_end_ms = max(
            turn.persona_offset_ms, min(turn.persona_end_ms, turn.persona_offset_ms + played_ms)
        )

    def _finalize_interrupted(self, turn: Turn, progress: _ReplyProgress) -> None:
        """Barge-in cleanup (ADR 0035). Commit only what the client played --
        `SpokenReply.cut` -- and close the Turn; if nothing was heard, discard the
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
        cut = progress.spoken.cut(played_ms)
        if cut.heard:
            self._commit_heard(turn, cut, played_ms, self.history.add_reply)
        else:
            self._trim_persona_window(turn, played_ms)
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
        if progress.ends_call and not progress.closing:
            if checks.still_pressing(f"{turn.persona_text} {text_chunk}", self._pack):
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
        replies = self.history.replies()
        if checks.reintroduces(text_chunk, replies, self._pack, self._first_name):
            raise _RegenerateReply(repetition.first_sentence(text_chunk))
        repeated = checks.repeats_earlier_opening(text_chunk, replies)
        if repeated is not None:
            raise _RegenerateReply(repeated, REPEAT_OPENING_NUDGE)
        return text_chunk

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
        # aclosing for the same reason the inner loop has it: this generator is
        # left early on the end marker and on a Failed leg, and the HTTP stream
        # underneath then stays open until the garbage collector gets to it. No
        # data is at stake here -- each completion is its own response, unlike
        # the pooled TTS socket of ADR 0044's amendment -- only a connection
        # held for nothing.
        async with contextlib.aclosing(sentence_chunks(llm.stream_reply(messages))) as reply:
            async for text_chunk in reply:
                guarding = first_chunk
                if guarding:
                    # Scrubbed before the guards read it, not after: the model
                    # copies the cut-off dash back from the history verbatim,
                    # while `_repeats_earlier_opening` compares against history
                    # lines that have had it removed. The dash alone made the
                    # two look different, and the copied "Ich will--" that
                    # ADR 0038's amendment was built for walked past the guard.
                    text_chunk = strip_interrupted_mark(text_chunk)
                    text_chunk = self._guard_opening(turn, text_chunk, progress)

                text_chunk = self._clean_chunk(turn, text_chunk, progress)

                if guarding:
                    # An echo is often the whole first chunk (one sentence, past
                    # the first-chunk floor), so the opening checks stay armed
                    # until a chunk with words in it has been seen. Read *after*
                    # the scrub, not before it: a chunk the filters empty is not
                    # a chunk the user heard, and disarming on it let the first
                    # spoken chunk -- a re-greeting, an echo -- past
                    # `_guard_opening` entirely.
                    first_chunk = not text_chunk.strip()

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
                    progress.spoken.voice(text_chunk)
                if not progress.spoke_yet:
                    yield StateChanged(state="speaking")
                    progress.spoke_yet = True
                progress.chunk_seq += 1
                self._note_persona_audio(turn, wav)
                progress.spoken.add_audio(tts.duration_ms(wav))
                yield AudioChunk(turn_seq=turn.seq, chunk_seq=progress.chunk_seq, audio=wav)
            if voiced:
                # Chunk fully synthesized: record where its audio ends so a
                # later barge-in can measure how much of it played (ADR 0035).
                progress.spoken.finish_chunk(text_chunk)
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
