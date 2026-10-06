"""One call's STT → dialogue → TTS pass per Turn, with the guards a small model
needs (ADR 0037, 0038). One retry per leg, then a clean end (ADR 0016, 0033)."""

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from typing import NamedTuple

from kugelaudio.exceptions import KugelAudioError
from openai import OpenAIError

from shared.clients import llm
from shared.feedback.acoustics import analyze
from shared.language_packs import LanguagePack, get_pack, is_phantom, signals_closing
from shared.turn import Turn
from backend.clients import stt, tts
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.call_notes import CallNotes
from backend.session.chunking import sentence_chunks
from backend.session.heard import Cut, SpokenReply
from backend.session.history import History
from backend.session.measuring import attach_measurements
from backend.session.pickup import PickupWatch
from backend.session import repetition
from backend.session import reply_checks as checks
from backend.session.prompting import build_system_prompt, opening_instruction
from backend.session import nudges
from backend.session.nudges import (
    ECHO_NUDGE, INTERRUPTED_MARK, REGENERATE_NUDGE, REPEAT_OPENING_NUDGE, RESUME_NUDGE,
    strip_interrupted_mark,
)
from backend.session.events import AudioChunk, Failed, StateChanged, TurnCompleted, TurnEvent

logger = logging.getLogger(__name__)


_END_CALL_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)

# Messages read verbatim beside the notes: the last three exchanges (ADR 0071).
HISTORY_WINDOW = 6


def _signals_closing(user_text: str, pack: LanguagePack) -> bool:
    return signals_closing(pack, user_text)


def _asks_to_repeat(user_text: str, pack: LanguagePack) -> bool:
    """Relaxes the repetition guards for one turn (ADR 0038)."""
    return bool(pack.repeat_request_re.search(user_text))


class _ReplyFilters(NamedTuple):
    """`guard`: opening checks and the one re-ask, first attempt of a normal Turn.
    `filter_repeats`: drop already-said and cut-off sentences, never on a
    requested repeat or a goodbye."""

    guard: bool
    filter_repeats: bool
    said: frozenset[str]
    cut_off: str


_NO_FILTERS = _ReplyFilters(guard=False, filter_repeats=False, said=frozenset(), cut_off="")


class _ReplyProgress:
    """State threaded through one reply's synthesis."""

    def __init__(self) -> None:
        self.chunk_seq = 0
        self.spoke_yet = False
        self.ends_call = False
        # The voiced text and its audio, which a barge-in cuts.
        self.spoken = SpokenReply()
        # Once in the history, a late barge-in must not re-finalize the turn.
        self.committed = False
        # A Turn the user closed: the reply ends the call, marker or not (ADR 0037).
        self.closing = False
        # The first repeat request in a row: repeating is the answer (ADR 0038).
        self.allow_repetition = False
        # Chunks the guards emptied. An empty reply because of these is the model
        # with nothing new, not an LLM failure (ADR 0038).
        self.suppressed = 0
        self.first_suppressed: tuple[str, str] | None = None
        self.filters = _NO_FILTERS


def _strip_end_marker(text_chunk: str, progress: _ReplyProgress) -> str:
    """Cut at the marker: a mid-chunk marker dragged the next sentence past the goodbye."""
    match = _END_CALL_RE.search(text_chunk)
    if not match:
        return text_chunk
    progress.ends_call = True
    return text_chunk[:match.start()].strip()


def _empty_reply_is_an_ending(turn: Turn, progress: _ReplyProgress) -> bool:
    """A wordless reply is a hang-up, not a failure, when it was the marker alone
    or the guards emptied it."""
    if progress.ends_call:
        logger.info("Turn %d reply was the end marker alone; ending the call", turn.seq)
        return True
    if progress.suppressed:
        logger.info("Turn %d reply was nothing but repeats; ending the call", turn.seq)
        progress.ends_call = True
        return True
    return False


# Stray CJK/Hangul from the small model, which TTS mispronounces.
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
    progress.suppressed += 1
    if progress.first_suppressed is None:
        progress.first_suppressed = (repetition.first_sentence(text), nudge)


class _RegenerateReply(Exception):
    """Raised before any audio to re-ask once (ADR 0038); `nudge` quotes `opening`."""

    def __init__(self, opening: str, nudge: str = REGENERATE_NUDGE):
        super().__init__(opening)
        self.opening = opening
        self.nudge = nudge


class SessionOrchestrator:  # pylint: disable=too-many-instance-attributes  # one call's state
    """One per Session. A barge-in can leave a Turn open for the next utterance (ADR 0035)."""

    def __init__(self, persona: Persona, scenario: Scenario):
        # Monotonic: offsets must not jump if the system clock is adjusted.
        self._started = time.monotonic()
        self._language_id = persona.language_id
        self._pack = get_pack(persona.language_id)
        self._voice = persona.voice
        self._hard = persona.hard
        self._scenario = scenario
        # Public so a test can wait for a refresh.
        self.notes = CallNotes(persona, scenario)
        self._playback_started = False
        self._pickup = PickupWatch(self._pack.pickup_prompts, enabled=not scenario.reverse)
        # To spot the Persona re-introducing itself (ADR 0038).
        self._first_name = persona.name.split()[0].lower() if persona.name else ""
        self._repeat_requests_in_a_row = 0
        self.history = History(build_system_prompt(persona, scenario, self._pack))
        self.turns: list[Turn] = []
        self._reopen_turn: Turn | None = None
        # Set by note_barge_in() just before the turn generator is torn down.
        self._barge_in_played_ms: int | None = None
        # The last committed reply, revisable by a barge-in that lands between
        # turns, since audio streams ahead of playback (ADR 0035).
        self._revisable: tuple[Turn, _ReplyProgress] | None = None
        # Read by session_ws: a barge-in over the goodbye must not revive the call.
        self.ended = False

    def _elapsed_ms(self) -> int:
        return round((time.monotonic() - self._started) * 1000)

    def start_playback(self) -> None:
        """t=0 is when the client starts playing. Ignored after the first call: a
        second activate would skew every later offset."""
        if self._playback_started:
            logger.info("Ignoring a second session.activate; the clock is already running")
            return
        self._playback_started = True
        # Shift the timeline so the first synthesized chunk sits at zero.
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
        """Modelled from synthesized audio, since the server never learns when
        playback finished. Keeps model latency out of reaction time (ADR 0051)."""
        now = self._elapsed_ms()
        if turn.persona_offset_ms is None:
            turn.persona_offset_ms = now
        turn.persona_end_ms = max(now, turn.persona_end_ms or now) + tts.duration_ms(audio)
        # Never trimmed by a barge-in; F-51 reads it.
        turn.persona_dispatched_end_ms = turn.persona_end_ms

    def _new_or_reopened_turn(self) -> tuple[Turn, bool]:
        # A stale position from a barge-in whose teardown never ran must not carry over.
        self._barge_in_played_ms = None
        self._revisable = None
        reopening = self._reopen_turn is not None
        turn = self._reopen_turn if reopening else Turn(seq=len(self.turns) + 1)
        if not reopening:
            self.turns.append(turn)
        self._reopen_turn = turn
        return turn, reopening

    async def run_opening_turn(self) -> AsyncIterator[TurnEvent]:
        """Since ADR 0110 only a reverse opens this way: the Persona picks up."""
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

    def _persona_has_opened(self) -> bool:
        """Whether the Persona has opened, ignoring "Hallo?" prompts. Read off the
        history, which a barge-in trims and drops."""
        return any(
            not self._pickup.is_prompt(strip_interrupted_mark(reply))
            for reply in self.history.replies()
        )

    def pickup_prompt_delay(self) -> float | None:
        due = self._pickup.delay_ms(self.turns, self._elapsed_ms(), self._playback_started)
        return None if due is None else due / 1000

    def note_user_speaking(self) -> None:
        """A prompt now would talk over the user, so the silence restarts."""
        self._pickup.note_speaking(self._elapsed_ms())

    async def run_pickup_prompt(self) -> AsyncIterator[TurnEvent]:
        """A fixed "Hallo?" into a silent line (ADR 0110), a Turn of its own. It goes
        into the history but is not the opening, which is still owed."""
        turn, _ = self._new_or_reopened_turn()
        progress = _ReplyProgress()
        line = self._pickup.next_line()
        try:
            async with contextlib.aclosing(self._speak(turn, line, progress)) as spoken:
                async for event in spoken:
                    yield event
                    if isinstance(event, Failed):
                        return
            turn.persona_text = turn.persona_text.strip()
            self.history.add_reply(turn.persona_text)
            progress.committed = True
            self._reopen_turn = None
            yield TurnCompleted(turn_seq=turn.seq, ends_call=False)
            self._revisable = (turn, progress)
            yield StateChanged(state="listening")
        except (asyncio.CancelledError, GeneratorExit):
            self._finalize_interrupted(turn, progress)
            raise

    async def run_turn(
        self, audio_bytes: bytes, filename: str, content_type: str | None
    ) -> AsyncIterator[TurnEvent]:
        turn, reopening = self._new_or_reopened_turn()
        progress = _ReplyProgress()
        # Measured alongside the STT round trip; Praat finishes first (ADR 0048).
        acoustics = asyncio.create_task(asyncio.to_thread(analyze, audio_bytes))
        # The audio arrives when the user stops talking, so this is the end. Written
        # only once the transcript proves speech, or a phantom stretches the window.
        ended_ms = self._elapsed_ms()
        try:
            yield StateChanged(state="thinking")

            user_text = await self._transcribe_with_retry(audio_bytes, filename, content_type)
            if user_text is None:
                yield Failed(code="stt_failed", message="Transcription failed after one retry.")
                return
            if is_phantom(self._pack, user_text):
                # A VAD misfire transcribed as a phantom: no reply, no history,
                # and a Turn opened for it is taken back (ADR 0071).
                logger.info("Turn %d: transcript is a Whisper phantom (%d chars); no Turn", turn.seq, len(user_text))
                if not reopening:
                    self.turns.pop()
                    self._reopen_turn = None
                yield StateChanged(state="listening")
                return

            turn.user_end_ms = ended_ms
            # A reopened turn appends to its question.
            if reopening and turn.user_text:
                turn.user_text = f"{turn.user_text} {user_text}".strip()
                self.history.extend_question(turn.user_text)
            else:
                turn.user_text = user_text
                self.history.add_question(user_text)
            await attach_measurements(turn, acoustics, ended_ms)
            if turn.user_offset_ms is None:
                turn.user_offset_ms = ended_ms
            closing = _signals_closing(turn.user_text, self._pack)
            # Repeating is the answer only for the first request in a row (ADR 0038).
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
            # A barge-in; aclosing makes this run even between yields.
            self._finalize_interrupted(turn, progress)
            raise
        finally:
            acoustics.cancel()

    def _messages_for_turn(self, closing: bool, interrupted: Turn | None = None) -> list[dict[str, str]]:
        """The system prompt, the notes, the last HISTORY_WINDOW messages, and this
        turn's nudge (ADR 0071). Until the Persona has opened in an ordinary call
        the nudge is the opening instruction (ADR 0110)."""
        view = [self.history.system(), *self.notes.message(), *self.history.recent(HISTORY_WINDOW)]
        if not self._scenario.reverse and not self._persona_has_opened():
            nudge: nudges.TurnNudge | None = nudges.TurnNudge(opening_instruction(self._pack))
        else:
            nudge = nudges.for_turn(
                closing=closing,
                interrupted=interrupted is not None and view[-1]["role"] == "user",
                repeat_requests=self._repeat_requests_in_a_row,
                previous_reply=self.history.previous_reply(),
                replies=len(self.history.replies()),
                reverse=self._scenario.reverse,
                hard=self._hard,
                call_goal=self._scenario.call_goal,
            )
        if nudge is None:
            return view
        message = {"role": "system", "content": nudge.content}
        if nudge.before_last:
            return [*view[:-1], message, view[-1]]
        return [*view, message]

    def _schedule_state_refresh(self, turn: Turn) -> None:
        """Called on commit and again after a trim: the notes record only what was heard."""
        self.notes.refresh(turn)

    def _discard_state_refresh(self, turn: Turn) -> None:
        self.notes.discard(turn)

    def close(self) -> None:
        self.notes.close()

    def _interrupted_previous_turn(self) -> Turn | None:
        """The Turn whose reply the user talked over, if it is the model's last reply."""
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
        """One retry on an LLM error or empty completion. May raise `_RegenerateReply`."""
        for llm_attempt in range(2):
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

                # An empty completion is treated as a failure, not an empty reply.
                logger.warning("LLM returned an empty reply (attempt %d)", llm_attempt + 1)
                if llm_attempt == 1:
                    yield Failed(
                        code="llm_failed",
                        message="Language model returned an empty reply.",
                    )
                    return
            except OpenAIError as e:
                logger.error("LLM request failed (attempt %d): %s", llm_attempt + 1, e)
                # Retry only before any audio went out (ADR 0033).
                if progress.spoke_yet or llm_attempt == 1:
                    yield Failed(code="llm_failed", message=str(e))
                    return
                turn.persona_text = ""

    async def _stream_reply_with_regeneration(
        self,
        turn: Turn,
        messages: list[dict[str, str]],
        progress: _ReplyProgress,
    ) -> AsyncIterator[TurnEvent]:
        """Plus one regeneration for a bad opening, caught before any audio. Exempt:
        a nudged closing and a requested repeat."""
        normal = not progress.closing and not progress.allow_repetition
        said = frozenset(checks.said_sentences(self.history.replies())) if normal else frozenset()
        cut_off = self._cut_off_sentence() if normal else ""
        for regeneration in range(2):
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
        """Commits the finished reply and decides whether it ends the call."""
        async with contextlib.aclosing(
            self._stream_reply_with_regeneration(turn, messages, progress)
        ) as events:
            async for event in events:
                yield event
                if isinstance(event, Failed):
                    return

        turn.persona_text = turn.persona_text.strip()
        if turn.persona_text and turn.persona_offset_ms is None:
            # Words with no audio: placed as an instant so the transcript stays in order.
            turn.persona_offset_ms = turn.persona_end_ms = self._elapsed_ms()
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
            # Revisable by a late barge-in over the tail still playing (ADR 0035).
            self._revisable = (turn, progress)
            yield StateChanged(state="listening")

    async def _speak_fallback_closing(self, turn: Turn, progress: _ReplyProgress) -> AsyncIterator[TurnEvent]:
        """A guaranteed sign-off for a backstopped ending (ADR 0038)."""
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
        """Trims now if the reply is committed, else stashes the position (ADR 0035)."""
        if self._revisable is not None:
            self._revise_committed_reply(*self._revisable, played_ms)
        else:
            self._barge_in_played_ms = played_ms

    def note_late_barge_in(self, played_ms: int | None) -> None:
        """Trims the committed reply, if any."""
        if self._revisable is not None:
            self._revise_committed_reply(*self._revisable, played_ms)

    def _revise_committed_reply(
        self, turn: Turn, progress: _ReplyProgress, played_ms: int | None
    ) -> None:
        """History and transcript trimmed in step, only ever shrinking: a stale
        re-entry recomputes the full text and must leave it alone (ADR 0035)."""
        self._revisable = None
        if not progress.committed or not turn.persona_text:
            return
        if not self.history.last_reply_is(turn.persona_text):
            return
        cut = progress.spoken.cut(played_ms)
        if not cut.heard:
            turn.persona_text = ""
            self.history.drop_reply()
            self._reopen_turn = turn
            self._trim_persona_window(turn, played_ms)
            self._discard_state_refresh(turn)
            return
        if len(cut.heard) >= len(turn.persona_text):
            return
        # Never the text (ADR 0066).
        logger.info("Turn %d reply trimmed to the heard part (%d of %d characters)",
                    turn.seq, len(cut.heard), len(turn.persona_text))
        self._commit_heard(turn, cut, played_ms, self.history.revise_reply)

    def _commit_heard(
        self, turn: Turn, cut: Cut, played_ms: int | None, write: Callable[[str], None]
    ) -> None:
        """`write` appends (still generating) or revises (already committed)."""
        turn.persona_unheard = cut.unheard
        turn.persona_text = cut.heard
        turn.persona_interrupted = True
        # The dash tells the model the line was cut off; the words match the transcript.
        write(f"{cut.heard}{INTERRUPTED_MARK}")
        self._reopen_turn = None
        self._trim_persona_window(turn, played_ms)
        self._schedule_state_refresh(turn)

    @staticmethod
    def _trim_persona_window(turn: Turn, played_ms: int | None) -> None:
        """Shrinks the heard window; `persona_dispatched_end_ms` stays for F-51."""
        if played_ms is None or turn.persona_offset_ms is None or turn.persona_end_ms is None:
            return
        turn.persona_end_ms = max(
            turn.persona_offset_ms, min(turn.persona_end_ms, turn.persona_offset_ms + played_ms)
        )

    def _finalize_interrupted(self, turn: Turn, progress: _ReplyProgress) -> None:
        """Commits only what the client played; if nothing was heard, the Turn stays open."""
        played_ms = self._barge_in_played_ms
        self._barge_in_played_ms = None
        if progress.committed:
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
        """The chunk as it will be spoken. An unprompted end marker is vetoed while
        the reply still presses (ADR 0037)."""
        text_chunk = _strip_end_marker(text_chunk, progress)
        text_chunk = _strip_foreign_script(text_chunk)
        text_chunk = strip_interrupted_mark(text_chunk)
        if progress.filters.filter_repeats and text_chunk:
            text_chunk = self._drop_repeats(turn, text_chunk, progress)
        if progress.ends_call and not progress.closing:
            if checks.still_pressing(f"{turn.persona_text} {text_chunk}", self._pack):
                logger.info("Turn %d: unprompted [CALL_END] on a reply that is still pressing; ignored", turn.seq)
                progress.ends_call = False
        return text_chunk

    def _drop_repeats(self, turn: Turn, text_chunk: str, progress: _ReplyProgress) -> str:
        """Drops already-said sentences (ADR 0038) and the cut-off one resumed (ADR 0035)."""
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
        interrupted = self._interrupted_previous_turn()
        return repetition.last_sentence(interrupted.persona_text) if interrupted is not None else ""

    def _guard_opening(self, turn: Turn, text_chunk: str, progress: _ReplyProgress) -> str:
        """Checks on the first chunk: drops an echo of the user and a lower-case
        continuation of the cut-off sentence (ADR 0035); a re-greeting or repeated
        opening raises `_RegenerateReply` (ADR 0038)."""
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
        # Before the opening a greeting is correct, even after a "Hallo?".
        if self._persona_has_opened() and checks.reintroduces(
                text_chunk, replies, self._pack, self._first_name):
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
        """Each sentence-sized chunk goes to TTS as it arrives (ADR 0033, 0044)."""
        first_chunk = True
        # aclosing, or the HTTP stream stays open until GC when left early.
        async with contextlib.aclosing(sentence_chunks(llm.stream_reply(messages))) as reply:
            async for text_chunk in reply:
                guarding = first_chunk
                if guarding:
                    # Scrubbed first: the model copies the cut-off dash, which the
                    # compared history lines do not carry.
                    text_chunk = strip_interrupted_mark(text_chunk)
                    text_chunk = self._guard_opening(turn, text_chunk, progress)

                text_chunk = self._clean_chunk(turn, text_chunk, progress)

                if guarding:
                    # Stay armed until a chunk with words; an emptied chunk was not heard.
                    first_chunk = not text_chunk.strip()

                if text_chunk:
                    # aclosing: a barge-in must reset the pooled TTS socket now (ADR 0044).
                    async with contextlib.aclosing(self._speak(turn, text_chunk, progress)) as spoken:
                        async for event in spoken:
                            yield event
                            if isinstance(event, Failed):
                                return

                if progress.ends_call:
                    break

        if progress.filters.guard and progress.first_suppressed is not None and not progress.spoke_yet:
            raise _RegenerateReply(*progress.first_suppressed)

    async def _speak(self, turn: Turn, text_chunk: str, progress: _ReplyProgress) -> AsyncIterator[TurnEvent]:
        """A failure ends the Turn; there is no fallback (ADR 0103)."""
        voiced = False
        stream = tts.synthesize_stream(text_chunk, self._voice, self._language_id)
        try:
            async for wav in stream:
                if not voiced:
                    voiced = True
                    # Only once audio exists, or a silent stream leaves unheard text.
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
                # Where its audio ends, for a later barge-in (ADR 0035).
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
            # Deterministically: an abandoned stream must reset the socket now (ADR 0044).
            await stream.aclose()

    async def _transcribe_with_retry(
        self, audio_bytes: bytes, filename: str, content_type: str | None
    ) -> str | None:
        for attempt in range(2):
            try:
                return await stt.transcribe(audio_bytes, filename, content_type, self._language_id)
            except OpenAIError as e:
                logger.error("STT request failed (attempt %d): %s", attempt + 1, e)
        return None
