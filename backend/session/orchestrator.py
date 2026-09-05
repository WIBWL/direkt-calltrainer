"""One Session's conversation: the STT → dialogue → TTS pass per Turn.

`SessionOrchestrator` owns the LLM message history and the Turn list for one
call. The guards around the pipeline exist because Qwen3-4B misbehaves in
specific, tested ways — copying the English prompt example (ADR 0043), ending
calls too eagerly or not at all (ADR 0037), looping or restating a demand the
user has already met (ADR 0038); each guard's own comment names what it
catches. Repetition is fought on three fronts (ADR 0038): the system prompt
forbids re-introducing, every turn carries a nudge quoting the persona's own
last reply, and a reply that *opens* by greeting again is caught before it is
spoken and regenerated once; the verbatim/oscillation/restatement checks stay
as the backstop that ends a call the model has stopped moving forward. When
the user asks to hear something again, the guards ease off once -- the persona
is nudged to say it again, shorter -- then snap back if asked twice. Retry
policy: one retry per leg, then end the Session cleanly (ADR 0016, ADR 0033).
"""

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator

from kugelaudio.exceptions import KugelAudioError
from openai import OpenAIError

from backend.clients import llm, stt, tts
from backend.feedback.acoustics import AcousticsError, Pause, TurnAcoustics, analyze
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.chunking import sentence_chunks
from backend.session.language_packs import LanguagePack, get_pack
from backend.session.models import AudioChunk, Failed, StateChanged, Turn, TurnCompleted, TurnEvent

logger = logging.getLogger(__name__)


def _opening_instruction(pack: LanguagePack) -> str:
    """Asks the Persona for the line that opens the call.

    The openers come from the language pack rather than the frame: a single
    English example here was copied verbatim into every call, German ones
    included."""
    return (
        "The call is starting now: you are the one calling, and you speak "
        "first. Open the conversation yourself with 1-2 short, realistic "
        "sentences: a greeting, who you are, and — briefly — what you're "
        "calling about (the question/concern from your role above). Invent "
        "plausible details as you go.\n"
        "Real callers do not all open a call the same way. These show the "
        "range of how an opening can be built — where the greeting sits, "
        "where the name sits, how the reason is introduced. Do not reuse "
        "their wording, and do not settle on one of these shapes as your "
        "default:\n"
        f"{pack.opening_examples}\n"
        "Start directly with the spoken line itself — no announcement before "
        "it like \"Here is the opening\", no quotation marks around it, no "
        "meta-commentary or stage directions. Reply with only that opening "
        "line."
    )


def _case_block(scenario: Scenario) -> str:
    """The case the Scenario carries (ADR 0045), or nothing.

    Each of the three is optional on its own: a Scenario predating ADR 0045,
    or a user-authored one (ADR 0024), can leave any of them blank, and an
    empty field must not produce a dangling heading. The success condition
    carries a usage rule with it: handed over bare, the model read it out as a
    demand every Turn instead of weighing the call against it."""
    parts = []
    if scenario.case_facts:
        parts.append(f"Facts of the case: {scenario.case_facts}")
    if scenario.call_goal:
        parts.append(f"What you want from this call: {scenario.call_goal}")
    if scenario.success_condition:
        parts.append(
            f"You consider the matter settled when: {scenario.success_condition}"
        )
        # Bare, this was recited as a demand every Turn and never weighed
        # against what the user had already conceded.
        parts.append(
            "That condition is yours to check silently, never to read out: "
            "before each reply, hold what the user has actually said so far "
            "against it, and never restate a demand you have already made. "
            "The moment it is met, say so plainly in your own words and "
            "close the call -- asking once more to be sure is exactly the "
            "wrong move."
        )
    return "".join(f"{part}\n" for part in parts)


def _objections_block(persona: Persona) -> str:
    """The Persona's typical objections (R-12, ADR 0045), or nothing.

    Framed as a repertoire rather than an agenda: the same model that copied a
    single opening example into every call will work a list through end to end
    if it is handed one."""
    if not persona.objections:
        return ""
    listed = "; ".join(persona.objections)
    return (
        f"Objections you tend to raise: {listed}. These are the shapes your "
        "pushback takes, not lines to recite — put them in your own words, and "
        "only where the conversation actually gives you the opening. Raise at "
        "most one per reply, never work through them as a list, and drop the "
        "ones the user has already answered.\n"
    )


def _improvisation_rule(scenario: Scenario) -> str:
    """How much the Persona may make up.

    With a case (ADR 0045) improvisation is bounded: fill the gaps the facts
    leave, never overwrite them. Without one the Scenario has nothing to point
    at, so the original instruction stands."""
    if scenario.case_facts:
        return (
            "Stay in character and improvise like a real person on a real "
            "call, but use the facts of the case above as given: quote them "
            "when you are asked, invent only what they leave open — a name, a "
            "date, a detail nobody has pinned down — and never contradict "
            "them or replace a figure they already state. Do not recite them "
            "unprompted either; they are what you know, not what you came to "
            "read out. Give at most one or two of them in a single reply, and "
            "only the ones the user's last question actually calls for — "
            "never the whole case at once, not even when you are asked what "
            "this is about. A figure you have already stated once in this "
            "call does not get stated again unless you are asked for it "
            "again.\n"
        )
    return (
        "Stay in character and improvise like a real person on a real call: "
        "when asked for specifics (e.g. \"which points were still open?\", "
        "\"what do you offer?\", \"why would that help me?\"), invent "
        "concrete, plausible details on the spot — a product name, a "
        "number, a prior concern — instead of staying vague or deflecting. "
        "This is a live conversation, not a scripted FAQ; ground your "
        "answers in believable specifics that fit the context.\n"
    )


def _build_system_prompt(persona: Persona, scenario: Scenario, pack: LanguagePack) -> str:
    """Builds the LLM system prompt.

    Instructions are English throughout; only the Persona's language decides
    what the model speaks, and only `pack` carries what has to follow it
    (ADR 0043)."""
    return (
        "You are playing a character in a phone-call training exercise. "
        "You are the one who called — you initiated this call because you "
        "have a specific question, concern, or problem you want addressed. "
        "The user is the person you called (e.g. support/sales), not the "
        "other way around: never ask the user what their question or "
        "problem is, and never wait for them to explain why they're "
        "calling — you're the one with something to discuss.\n"
        f"Context of the call: {scenario.description}\n"
        f"{_case_block(scenario)}"
        f"Your name: {persona.name}. Introduce yourself by that name and "
        "use it whenever you say who you are — never invent a different one.\n"
        f"Your role: {persona.role}.\n"
        f"Character traits: {persona.traits}.\n"
        f"Behavior: {persona.behavior}.\n"
        f"{_objections_block(persona)}"
        f"{_improvisation_rule(scenario)}"
        "Never repeat yourself. This is the single most common mistake to "
        "avoid: before every reply, re-read your own previous lines in "
        "this call and check whether you are about to say the same thing "
        "again — the same question, recap, or objection — even reworded. "
        "If so, drop it and say something new instead. Re-asking something "
        "the user has already answered is the same mistake: if part of the "
        "answer was unclear, ask about that part only, never the whole "
        "question over again.\n"
        "You have already opened this call and said who you are. Do not greet "
        "the user again, do not give your name again, and do not lay out your "
        "reason for calling as though you were raising it for the first time — "
        "they have heard all of that. Continue from where the conversation "
        "actually is.\n"
        f"{pack.example_exchange}\n"
        "Before every reply, check first whether what you came for has "
        "already been given. A clear answer, or a specific commitment with an "
        "actual action, amount, or timeframe (a refund, a callback, a fixed "
        "date, a figure) counts — including one that arrived piece by piece "
        "across several replies, and including one you had to ask twice to "
        "get. Once it has been given you are done: do not ask again to make "
        "sure, and do not put your demand one more time. Accept it out loud "
        "in your own words, say that this works for you, thank them for the "
        "accommodation, and end the call. The same applies when the user "
        "signals the call is over — a goodbye, a wrap-up like "
        f"{pack.user_closing_examples}, or any other natural way people end "
        "a phone call.\n"
        "To end it: add one brief, friendly closing line (accept what you "
        "were given, thank them, say goodbye), then finish your reply with "
        "exactly this marker on its own and nothing after it: [CALL_END]. "
        "Never end the call "
        "while you still consider your concern unresolved, are still "
        "pressing for information, or have only gotten a vague reassurance "
        f"with no specifics ({pack.vague_reassurance_examples}) — a "
        "frustrated reply, or an empty promise with no actual "
        "content, is not by itself a reason to hang up; keep pushing for "
        "specifics instead, the way a real caller would. But once the "
        "specifics are actually on the table, carrying on is the same "
        "mistake in the other direction. Only include the "
        "marker when the call should truly end — never otherwise, never in the "
        "same reply as a question or a statement that the issue isn't "
        "resolved yet, and never explain or mention the marker itself.\n"
        f"Reply exclusively in {pack.name_en}, every single time regardless of "
        "what language the user writes in, in short, realistic sentences "
        "the way people actually talk on the phone. Stay true to the role "
        "without exaggerating into caricature. Output only what the "
        "persona would say — no meta-commentary, no stage directions."
    )


_END_CALL_RE = re.compile(r"\[\s*call[_\s]?end\s*\]", re.IGNORECASE)


def _signals_closing(user_text: str, pack: LanguagePack) -> bool:
    """True if the user's message is an explicit farewell or a request to
    postpone/continue the call elsewhere. Matched against the user's own
    speech, so the patterns come from the language pack, not from here."""
    return bool(pack.farewell_re.search(user_text) or pack.postpone_re.search(user_text))


def _asks_to_repeat(user_text: str, pack: LanguagePack) -> bool:
    """True if the user asked the persona to say something again — its name,
    the last line, the question. Repeating is then the right answer, so the
    turn drops the anti-repeat nudge and the re-introduction guard, and a
    repeat of the *immediately previous* reply no longer ends the call
    (ADR 0038). It is not a licence to parrot: `_CLARIFY_NUDGE` asks for the
    same content reworded shorter, and a verbatim repeat of an *older* reply
    still counts as a loop."""
    return bool(pack.repeat_request_re.search(user_text))


_CLOSING_NUDGE = (
    "The user just signaled the call is over. End it now: add one brief, "
    "friendly closing line, then finish your reply with exactly this "
    "marker and nothing after it: [CALL_END]."
)


# Carried on every turn past the opening (ADR 0038). presence_penalty does not
# stop a 4B model re-emitting a whole reply when the call stalls, and the
# system prompt's standing "never repeat yourself" is too far up-context to
# bite -- quoting the actual previous reply right before the model answers is
# what measurably moves it.
_ANTI_REPEAT_NUDGE = (
    'Your previous reply in this call was:\n"{previous}"\n'
    "Say something genuinely different now: react to what the user just said, "
    "press a point you have not pressed yet, give ground, or ask a new "
    "question — in new words. Do not repeat or reword that reply, and do not "
    "greet or introduce yourself again."
)

# Sent when a reply was caught opening with a greeting again and is being
# regenerated (ADR 0038). The rejected opening is quoted so the retry has
# something concrete to steer away from.
_REGENERATE_NUDGE = (
    'You just started your reply with:\n"{opening}"\n'
    "That restarts the call — you have already greeted the user and said who "
    "you are. Answer again without any greeting or self-introduction: pick up "
    "the conversation where it stands and respond to the user's last message."
)

# The user asked to hear the last reply again (ADR 0038). Given half a chance
# the 4B model reads its previous line back verbatim -- and a wall of text is
# no clearer the second time -- so the ask is for the same content, reworded
# shorter.
_CLARIFY_NUDGE = (
    "The user did not catch your previous reply. Say the same thing again, but "
    "reworded: shorter, plainer words, one or two sentences. Do not read your "
    "previous reply back word for word, and do not greet or introduce yourself."
)

# They have asked more than once now. A third rendering of the same content,
# however worded, is not helping -- find out what is unclear or move on.
_CLARIFY_AGAIN_NUDGE = (
    "The user still did not follow, even after you rephrased. Do not put it a "
    "third time. Ask which part is unclear, or give the single most important "
    "point in one sentence and carry the call forward."
)


async def _attach_measurements(
    turn: Turn, acoustics: asyncio.Task[TurnAcoustics], ended_ms: int
) -> None:
    """Record the Turn's paraverbal measurements, on the Session's timeline (ADR 0048).

    The audio arrived once the user had stopped talking, so `ended_ms` is where
    this fragment ends and the measured duration is what walks it back to its
    start. A Turn reopened after a barge-in is measured once per fragment, and
    each fragment is placed by its own arrival -- which is why the pauses can
    be rebased here and never need a per-fragment origin later.

    Never fatal: unlike STT, dialogue generation and TTS, this leg is not one
    the conversation depends on, so a Turn that cannot be measured simply
    carries no measurements and the call continues.
    """
    try:
        measured = await acoustics
    except AcousticsError as e:
        logger.info("Turn %d not measured: %s", turn.seq, e)
        turn.user_acoustics_complete = False
        return
    except Exception:  # pylint: disable=broad-exception-caught
        # Deliberately catch-all: `analyze` runs Praat in a worker thread and
        # can surface anything from the C extension. Per the docstring this leg
        # is never load-bearing, so any failure here is logged and the Turn
        # just carries no measurements -- it must not break the call.
        logger.exception("Paraverbal analysis failed for turn %d", turn.seq)
        turn.user_acoustics_complete = False
        return
    started_ms = max(0, ended_ms - measured.duration_ms)
    if turn.user_offset_ms is None:
        turn.user_offset_ms = started_ms
    turn.user_speech_ms += measured.phonation_ms
    turn.pauses.extend(Pause(started_ms + p.offset_ms, p.duration_ms) for p in measured.pauses)
    turn.loudness_db.extend(measured.loudness_db)


# A barge-in's reported playback position and the server's per-chunk audio
# tally are two independent clocks (client wall-time vs. summed WAV durations),
# so an utterance the user heard in full can land a little short of its
# checkpoint. This slack keeps that from dropping it (ADR 0035).
_BARGE_IN_GRACE_MS = 300

# ...and a chunk the user got most of the way through, they got the sense of.
# Without this, cutting in a second before a sentence ends discards the whole
# sentence, the turn reopens, and the next reply re-delivers everything from
# the top -- which reads in the transcript as if the persona was never
# interrupted at all (ADR 0035).
_HEARD_FRACTION = 0.65


class _ReplyProgress:
    """Mutable state threaded through one reply's synthesis: chunks sent, whether
    any was, whether the reply ends the call, the voiced text (for barge-in)."""

    def __init__(self) -> None:
        self.chunk_seq = 0
        self.spoke_yet = False
        self.ends_call = False
        self.spoken_text = ""
        # Cumulative playback length of the audio dispatched so far, and a
        # snapshot of `spoken_text` at the end of each fully-synthesized chunk.
        # On a barge-in these say which utterances fit inside the playback
        # window the client reports it actually heard (ADR 0035).
        self.audio_ms = 0
        self.checkpoints: list[tuple[int, str]] = []


def _strip_end_marker(text_chunk: str, progress: _ReplyProgress) -> str:
    """Strip the `[CALL_END]` marker before TTS and flag `progress.ends_call`.
    Loose regex (whitespace, case, `_`) — the model doesn't always emit it exactly."""
    if not _END_CALL_RE.search(text_chunk):
        return text_chunk
    progress.ends_call = True
    return _END_CALL_RE.sub("", text_chunk).strip()


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


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


class _RegenerateReply(Exception):
    """Raised out of the reply stream before any audio has gone out, to have
    `_generate_reply` re-ask the model once (ADR 0038). Only for a reply that
    *opens* by greeting again — the after-the-fact checks handle the rest, and
    those can safely end the call because the reply was already spoken."""

    def __init__(self, opening: str):
        super().__init__(opening)
        self.opening = opening


def _first_sentence(text: str) -> str:
    """The first sentence of a chunk of text, for comparing openings."""
    return _SENTENCE_SPLIT_RE.split(text.strip(), maxsplit=1)[0].strip()


def _word_set(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _word_overlap(a: str, b: str) -> float:
    """Jaccard overlap of the two texts' word sets — 0.0 when either is empty."""
    wa, wb = _word_set(a), _word_set(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# First sentence of a reply shares at least this fraction of its words with the
# opening's — the model is reading its own introduction back out (ADR 0038).
_REINTRO_OVERLAP = 0.6

# Below this many words a reply's opening is an acknowledgement ("Ja, genau."),
# not an introduction, whatever greeting token it happens to contain.
_MIN_REINTRO_WORDS = 3

# Below this, a whole reply repeating an earlier one is more likely a natural
# short acknowledgement than the model looping (ADR 0038).
_MIN_LOOP_REPLY_CHARS = 30


# Below this, a shared sentence means shared filler ("Ja, genau.", "Ich
# verstehe.") rather than shared content, so short ones are not compared.
_MIN_SENTENCE_LEN = 15


def _long_sentences(text: str) -> list[str]:
    """The sentences of one reply worth comparing: normalised, filler dropped."""
    sentences = (sentence.strip().lower() for sentence in _SENTENCE_SPLIT_RE.split(text))
    return [sentence for sentence in sentences if len(sentence) >= _MIN_SENTENCE_LEN]


def _has_repeated_sentence(text: str) -> bool:
    """True if a non-trivial sentence repeats within one reply — the model
    looping (ADR 0038). Short fragments ("Ja.", "Okay.") don't count."""
    sentences = _long_sentences(text)
    return len(sentences) != len(set(sentences))


# ADR 0038's verbatim check never fires on the failure below it: the Persona
# varies its opening sentence and carries the same block underneath it
# unchanged, Turn after Turn, so no two replies are ever wholly identical --
# the gap ADR 0038's own Consequences name. What separates a restatement from
# a caller legitimately quoting a figure twice is not *whether* a sentence
# came back but *how much* of the reply is old: a reply that repeats its
# opening and then says seven new things has moved the call on, one that is
# four fifths its predecessor has not. Measured against a real call, those two
# cases sit at 25% and 80%.
_RESTATEMENT_SHARE = 0.5


class SessionOrchestrator:
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
            {"role": "system", "content": _build_system_prompt(persona, scenario, self._pack)},
        ]
        self.turns: list[Turn] = []
        self._reopen_turn: Turn | None = None
        # Set by note_barge_in() just before the turn generator is torn down, so
        # _finalize_interrupted knows how much of the reply the client played.
        self._barge_in_played_ms: int | None = None

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
                {"role": "user", "content": _opening_instruction(self._pack)},
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
        # the utterance's end; _attach_measurements walks it back to its start.
        ended_ms = self._elapsed_ms()
        turn.user_end_ms = ended_ms
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
            await _attach_measurements(turn, acoustics, ended_ms)
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

            messages = self._messages_for_turn(closing)

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

    def _messages_for_turn(self, closing: bool) -> list[dict[str, str]]:
        """The history plus this turn's transient nudge -- never stored: the
        closing push when the user has said goodbye (ADR 0037); a "say it
        again, reworded shorter" push when the user asked to hear something
        again (ADR 0038), firmer once they have asked twice; otherwise a
        standing reminder quoting the persona's own last reply so it does not
        come back reworded (ADR 0038)."""
        if closing:
            nudge = _CLOSING_NUDGE
        elif self._repeat_requests_in_a_row >= 2:
            nudge = _CLARIFY_AGAIN_NUDGE
        elif self._repeat_requests_in_a_row == 1:
            nudge = _CLARIFY_NUDGE
        elif self._previous_reply():
            nudge = _ANTI_REPEAT_NUDGE.format(previous=self._previous_reply())
        else:
            return self._messages
        return [*self._messages, {"role": "system", "content": nudge}]

    async def _attempt_reply_with_retry(
        self,
        turn: Turn,
        messages: list[dict[str, str]],
        progress: _ReplyProgress,
        guard_reintroduction: bool = False,
    ) -> AsyncIterator[TurnEvent]:
        """One reply attempt plus one retry on an LLM error. Yields the reply's
        events; yields a Failed event and stops if it can't be delivered. May
        raise `_RegenerateReply` before the first audio (ADR 0038)."""
        for llm_attempt in range(2):  # initial attempt + one retry
            try:
                stream = self._stream_and_synthesize(
                    turn, messages, progress, guard_reintroduction=guard_reintroduction
                )
                async with contextlib.aclosing(stream) as chunks:
                    async for event in chunks:
                        yield event
                        if isinstance(event, Failed):
                            return
                return  # streamed to completion without an LLM-side error
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
        for regeneration in range(2):  # first pass + one regeneration
            guard = not force_end_call and not allow_repetition and regeneration == 0
            try:
                async with contextlib.aclosing(
                    self._attempt_reply_with_retry(turn, messages, progress, guard_reintroduction=guard)
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
                    {"role": "system", "content": _REGENERATE_NUDGE.format(opening=restart.opening)},
                ]
                # Nothing was spoken, so only the marker flag can have moved.
                turn.persona_text = ""
                progress.ends_call = False

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
            _has_repeated_sentence(turn.persona_text) or
            self._repeats_earlier_reply(turn.persona_text, exclude_last=allow_repetition) or
            (not allow_repetition and self._repeats_last_reply(turn.persona_text))
        )
        restates = spoke and not allow_repetition and self._restates_previous_reply(turn.persona_text)
        self._messages.append({"role": "assistant", "content": turn.persona_text})

        # force_end_call backstops [CALL_END]: a small model won't always
        # include the marker even when told to (confirmed in testing).
        ends_call = progress.ends_call or force_end_call or repeated_reply or restates
        if ends_call:
            logger.info(
                "Turn %d ends the call (model marker=%s, closing-intent check=%s, "
                "repeated reply=%s, restated reply=%s)",
                turn.seq,
                progress.ends_call,
                force_end_call,
                repeated_reply,
                restates,
            )
            # Only the closing-intent path actually asked the model for a
            # goodbye (_CLOSING_NUDGE); a repeat or an unprompted ending
            # didn't, so it can't be trusted to have included one.
            if repeated_reply or restates or (progress.ends_call and not force_end_call):
                async for event in self._speak_fallback_closing(turn, progress):
                    yield event
        yield TurnCompleted(turn_seq=turn.seq, ends_call=ends_call)
        if not ends_call:
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
        whitespace) — the cross-Turn form of `_has_repeated_sentence` (ADR 0038)."""
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
        if len(candidate) < _MIN_LOOP_REPLY_CHARS:
            return False
        earlier = [m["content"] for m in self._messages if m["role"] == "assistant"]
        if exclude_last:
            earlier = earlier[:-1]
        return any(content.strip().lower() == candidate for content in earlier)

    def _restates_previous_reply(self, text: str) -> bool:
        """True if most of this reply was already in its predecessor — the
        partial form of `_repeats_last_reply` (ADR 0038).

        A share of the reply, not a count of sentences: repeating one figure
        while adding new content is a real caller, repeating four fifths of
        the last reply is the loop the guard is for."""
        sentences = set(_long_sentences(text))
        if not sentences:
            return False
        carried = len(set(_long_sentences(self._previous_reply())) & sentences)
        return carried / len(sentences) > _RESTATEMENT_SHARE

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
        words = _word_set(opener)
        if len(words) < _MIN_REINTRO_WORDS:
            return False
        if not self._pack.regreeting_re.match(opener):
            return False
        # A greeting at the very start of a reply is already the tell; pair it
        # with the persona naming itself again, or the opening's own wording
        # carried straight over, so a greeting mirrored back at a late-greeting
        # user is the only thing that slips through.
        if self._first_name and self._first_name in words:
            return True
        return _word_overlap(opener, earlier[0]) >= _REINTRO_OVERLAP

    def note_barge_in(self, played_ms: int | None) -> None:
        """How much of the in-flight reply the client reports it actually played
        before the user cut in. Recorded here rather than passed through the
        generator teardown, which cannot carry an argument (ADR 0035)."""
        self._barge_in_played_ms = played_ms

    def _finalize_interrupted(self, turn: Turn, progress: _ReplyProgress) -> None:
        """Barge-in cleanup (ADR 0035). Commit the utterances whose audio the
        client played through -- in full, or most of the way (`_HEARD_FRACTION`)
        -- and close the Turn. If nothing was heard, discard the reply and leave
        the Turn open so the next utterance continues the same question.

        "Dispatched as audio" is not "heard": the server streams chunks ahead of
        playback and the client cuts the current one off mid-word, so committing
        everything sent put sentences into the history the user never got, and
        the next reply picked up from text that was never spoken aloud.
        """
        played_ms = self._barge_in_played_ms
        self._barge_in_played_ms = None
        if not progress.spoke_yet:
            turn.persona_text = ""
            return
        heard = self._heard_text(progress, played_ms)
        if heard:
            turn.persona_text = heard
            self._messages.append({"role": "assistant", "content": heard})
            self._reopen_turn = None
        else:
            turn.persona_text = ""

    @staticmethod
    def _heard_text(progress: _ReplyProgress, played_ms: int | None) -> str:
        """The reply text the client actually heard: the checkpoint text of the
        last chunk whose audio the client played to its end, or at least
        `_HEARD_FRACTION` of the way through (checkpoints carry the *cumulative*
        audio length, so consecutive ones bracket each chunk). `None` — an older
        client that sends no position — falls back to every dispatched chunk."""
        if played_ms is None:
            return progress.spoken_text.strip()
        budget = played_ms + _BARGE_IN_GRACE_MS
        heard = ""
        chunk_start = 0
        for chunk_end, text in progress.checkpoints:
            got_enough = chunk_end - chunk_start > 0 and (
                budget >= chunk_start + _HEARD_FRACTION * (chunk_end - chunk_start)
            )
            if chunk_end <= budget or got_enough:
                heard = text
            chunk_start = chunk_end
        return heard

    async def _stream_and_synthesize(
        self,
        turn: Turn,
        messages: list[dict[str, str]],
        progress: _ReplyProgress,
        guard_reintroduction: bool = False,
    ) -> AsyncIterator[TurnEvent]:
        """Stream one LLM completion; feed each sentence-sized chunk to TTS and
        forward its audio sub-chunks to the client as they are generated.

        When `guard_reintroduction` is set, the first chunk is checked against
        the call so far *before* it is synthesized: a reply opening with a
        fresh greeting raises `_RegenerateReply` here, and no audio goes out
        (ADR 0038)."""
        first_chunk = guard_reintroduction
        async for text_chunk in sentence_chunks(llm.stream_reply(messages)):
            if first_chunk:
                first_chunk = False
                if self._reintroduces(text_chunk):
                    raise _RegenerateReply(_first_sentence(text_chunk))

            text_chunk = _strip_end_marker(text_chunk, progress)
            text_chunk = _strip_foreign_script(text_chunk)

            if text_chunk:
                turn.persona_text += text_chunk + " "
                async for event in self._speak(turn, text_chunk, progress):
                    yield event
                    if isinstance(event, Failed):
                        return

            if progress.ends_call:
                break  # nothing meaningful should follow the marker

    async def _speak(self, turn: Turn, text_chunk: str, progress: _ReplyProgress) -> AsyncIterator[TurnEvent]:
        """Synthesize one chunk and forward its audio as KugelAudio produces it,
        piece by piece (ADR 0044). A failure past the fallback ends the Turn."""
        voiced = False
        try:
            async for wav in tts.synthesize_stream(text_chunk, self._voice, self._language_id):
                if not voiced:
                    voiced = True
                    progress.spoken_text += text_chunk + " "
                if not progress.spoke_yet:
                    yield StateChanged(state="speaking")
                    progress.spoke_yet = True
                progress.chunk_seq += 1
                self._note_persona_audio(turn, wav)
                progress.audio_ms += tts.duration_ms(wav)
                yield AudioChunk(turn_seq=turn.seq, chunk_seq=progress.chunk_seq, audio=wav)
            if voiced:
                # This chunk is fully synthesized: mark where its audio ends on
                # the reply's playback clock, so a later barge-in can tell
                # whether the user heard all of it (ADR 0035).
                progress.checkpoints.append((progress.audio_ms, progress.spoken_text.strip()))
        except (KugelAudioError, OpenAIError, TimeoutError, OSError) as e:
            logger.error("TTS synthesis failed: %s", e)
            yield Failed(code="tts_failed", message=str(e))

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
