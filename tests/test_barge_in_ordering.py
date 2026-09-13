"""The order in which a barge-in reaches the orchestrator (ADR 0035).

`SessionOrchestrator._finalize_interrupted` reads `_barge_in_played_ms` to
decide how much of the reply the user actually heard. `note_barge_in()` is what
puts it there, and `_run_turn_interruptible` is the only caller -- so the
contract between them is an ordering one: **note_barge_in must land before the
turn generator is finalized**, or the finalizer sees `None` and falls back to
committing every chunk that was ever dispatched, including the ones the client
never played.

tests/test_barge_in.py exercises the orchestrator side of that contract by
calling `note_barge_in()` by hand and then closing the generator. Nothing
exercises the caller's side, which is where the ordering is actually decided --
and it is decided differently depending on where the forwarding task happened
to be suspended when the interrupt arrived. These two tests are the same
barge-in twice, distinguished only by that.
"""

# pylint: disable=duplicate-code
# Fixture data is repeated per test module on purpose: a test carrying its own
# Turns shows what it ran against when it fails, and sharing them would let a
# change made for one test quietly alter another.

from __future__ import annotations

import asyncio
import json

from backend.api.session_ws import _run_turn_interruptible
from backend.session.models import AudioChunk, StateChanged
from backend.session.nudges import INTERRUPTED_MARK
from backend.session.orchestrator import SessionOrchestrator

# pylint: disable=missing-function-docstring,protected-access

_PLAYED_MS = 1234


class _Ws:
    """A socket that reports a barge-in once the reply is under way."""

    def __init__(self, *, parked: asyncio.Event, block_send: asyncio.Event | None = None):
        self._parked = parked
        self._block_send = block_send
        self.sent: list = []

    async def send_json(self, data):
        self.sent.append(data)

    async def send_bytes(self, data):
        self.sent.append(bytes(data))
        if self._block_send is not None:
            # Park the forwarding task in the *send*, rather than in the
            # generator, so the interrupt finds it here instead.
            self._parked.set()
            await self._block_send.wait()

    async def receive_text(self):
        await self._parked.wait()
        return json.dumps({"type": "turn.interrupt", "played_ms": _PLAYED_MS})


def _reply(order: list[str], *, park_in_generator: asyncio.Event | None):
    """One turn's events. Records when it is finalized, so the test can compare
    that moment against when note_barge_in was called."""

    async def gen():
        try:
            yield StateChanged(state="speaking")
            yield AudioChunk(turn_seq=1, chunk_seq=1, audio=b"aud")
            if park_in_generator is not None:
                # Where a real turn spends most of its time: awaiting the TTS
                # gateway for the next chunk. A barge-in usually lands here.
                park_in_generator.set()
                await asyncio.sleep(30)
            else:
                await asyncio.sleep(30)
            yield AudioChunk(turn_seq=1, chunk_seq=2, audio=b"more")
        except (asyncio.CancelledError, GeneratorExit):
            order.append("finalize")
            raise

    return gen()


async def test_barge_in_is_recorded_before_the_turn_is_finalized_mid_generator():
    """The interrupt arrives while the turn is waiting on the TTS gateway.

    This is the common case -- synthesis is a network round trip, forwarding a
    chunk to the socket is not -- so it is where a barge-in most often lands.
    """
    order: list[str] = []
    parked = asyncio.Event()
    ws = _Ws(parked=parked)
    events = _reply(order, park_in_generator=parked)

    outcome = await _run_turn_interruptible(
        ws, events, lambda: None, lambda ms: order.append("barge_in")
    )

    assert outcome == "interrupted"
    assert order == ["barge_in", "finalize"], (
        "the played-through position must reach the orchestrator before the "
        f"turn is finalized, but the order was {order}"
    )


async def test_barge_in_is_recorded_before_the_turn_is_finalized_mid_send():
    """The same interrupt, arriving while the turn is parked in the socket send
    instead. The orchestrator's contract does not change with the suspension
    point, so this must produce the same order as the test above."""
    order: list[str] = []
    parked = asyncio.Event()
    block_send = asyncio.Event()
    ws = _Ws(parked=parked, block_send=block_send)
    events = _reply(order, park_in_generator=None)

    outcome = await _run_turn_interruptible(
        ws, events, lambda: None, lambda ms: order.append("barge_in")
    )
    block_send.set()

    assert outcome == "interrupted"
    assert order == ["barge_in", "finalize"], (
        f"same contract, same order expected, but got {order}"
    )


class _RealTurnWs:
    """A socket for the end-to-end case: counts the chunks the server actually
    dispatched, parks synthesis once three are out, and only then reports the
    barge-in -- so the turn is waiting on the TTS gateway when it arrives."""

    def __init__(self, tts_fake, *, played_ms: int):
        self._tts = tts_fake
        self._played_ms = played_ms
        self.audio_sent = 0
        self.sent: list = []

    async def send_json(self, data):
        self.sent.append(data)

    async def send_bytes(self, data):
        self.sent.append(bytes(data))
        self.audio_sent += 1
        if self.audio_sent == 3:
            # The next synthesis will park, which is where the interrupt lands.
            self._tts.hang = asyncio.Event()

    async def receive_text(self):
        while self.audio_sent < 3:
            await asyncio.sleep(0)
        # Let the turn advance into that parked synthesis before interrupting.
        for _ in range(50):
            await asyncio.sleep(0)
        return json.dumps({"type": "turn.interrupt", "played_ms": self._played_ms})


async def test_only_the_heard_sentence_is_committed_when_the_turn_is_cut_mid_synthesis(
    persona, scenario, fake_pipeline, monkeypatch
):
    """The whole point of ADR 0035, through the real orchestrator and the real
    interrupt path.

    Three sentences go out as audio; the client reports it played 700 ms which,
    with the 300 ms grace, covers exactly the first one. The other two were
    streamed ahead and never heard, so they must not enter the history --
    otherwise the next reply picks up from words the persona never spoke aloud.
    """
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 1000)
    s1 = "Der erste Satz meiner Antwort ist inhaltlich vollstaendig und lang genug fuer seinen eigenen Chunk."
    s2 = "Der zweite Satz folgt unmittelbar darauf und ist ebenfalls lang genug fuer einen eigenen Chunk hier."
    s3 = "Den dritten Satz hoert der Nutzer schon nicht mehr, obwohl der Server ihn laengst verschickt hatte."
    s4 = "Und der vierte Satz wird nie fertig synthetisiert, weil die Synthese genau hier stehen bleibt jetzt."
    assert min(len(s1), len(s2), len(s3), len(s4)) >= 80

    fake_pipeline.stt.transcripts = ["Bitte erklaeren Sie mir das."]
    fake_pipeline.llm.replies = [f"{s1} {s2} {s3} {s4}"]

    orch = SessionOrchestrator(persona, scenario)
    events = orch.run_turn(b"a", "turn.webm", "audio/webm")
    ws = _RealTurnWs(fake_pipeline.tts, played_ms=700)

    outcome = await _run_turn_interruptible(
        ws, events, orch.start_playback, orch.note_barge_in
    )
    fake_pipeline.tts.hang.set()  # release the parked synthesis

    assert outcome == "interrupted"
    assert ws.audio_sent >= 3, "the server had streamed three chunks ahead"
    assert orch.turns[0].persona_text == s1
    assert s2 not in orch.turns[0].persona_text, "streamed ahead but never heard"
    assert s3 not in orch.turns[0].persona_text, "streamed ahead but never heard"
    assert orch._messages[-1] == {"role": "assistant", "content": s1 + INTERRUPTED_MARK}


class _TailWs:
    """Interrupts while the `turn.completed` frame is going out -- i.e. after the
    reply has already been committed to the history."""

    def __init__(self):
        self.sent: list = []
        self._completed = asyncio.Event()

    async def send_json(self, data):
        self.sent.append(data)
        if data.get("type") == "turn.completed":
            self._completed.set()
            await asyncio.sleep(0.05)  # the frame is still in flight

    async def send_bytes(self, data):
        self.sent.append(bytes(data))

    async def receive_text(self):
        await self._completed.wait()
        # 0.7s + 0.3s grace = exactly the first sentence.
        return json.dumps({"type": "turn.interrupt", "played_ms": 700})


async def test_a_barge_in_on_the_tail_trims_the_committed_reply_to_what_was_heard(
    persona, scenario, fake_pipeline, monkeypatch
):
    """A barge-in that arrives after the reply is already finished.

    The server streams ahead of playback, so when it finishes a turn the client
    is still playing the tail of it -- and a user who talks over that tail sends
    the interrupt *after* _generate_reply has committed the reply to history.
    The Transcript must still show only what was played, so the history and
    persona_text are trimmed to the heard part *together* -- never one without
    the other (ADR 0035). The reply is committed exactly once, and the finished
    turn stays closed.
    """
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 1000)
    s1 = "Der erste Satz meiner Antwort ist inhaltlich vollstaendig und lang genug fuer seinen eigenen Chunk."
    s2 = "Der zweite Satz folgt unmittelbar darauf und ist ebenfalls lang genug fuer einen eigenen Chunk hier."
    fake_pipeline.stt.transcripts = ["Bitte erklaeren Sie mir das."]
    fake_pipeline.llm.replies = [f"{s1} {s2}"]

    orch = SessionOrchestrator(persona, scenario)
    events = orch.run_turn(b"a", "turn.webm", "audio/webm")
    ws = _TailWs()

    await _run_turn_interruptible(ws, events, orch.start_playback, orch.note_barge_in)

    assistant = [m for m in orch._messages if m["role"] == "assistant"]
    assert len(assistant) == 1, f"the reply was committed {len(assistant)}x"
    assert assistant[0]["content"] == s1 + INTERRUPTED_MARK, "only the heard sentence, in the history"
    assert orch.turns[0].persona_text == s1, "and the same in the Transcript"
    assert orch._reopen_turn is None, "a finished turn is closed, not left open"


class _AfterListeningWs:
    """Interrupts only once the whole turn event stream is out (the last frame
    is `state: listening`) -- i.e. the turn generator has fully returned, not
    just committed. The teardown then has nothing to finalize, so the trim has
    to happen off `note_barge_in` itself."""

    def __init__(self):
        self.sent: list = []
        self._done = asyncio.Event()

    async def send_json(self, data):
        self.sent.append(data)
        if data.get("type") == "state" and data.get("value") == "listening":
            self._done.set()
            await asyncio.sleep(0.02)

    async def send_bytes(self, data):
        self.sent.append(bytes(data))

    async def receive_text(self):
        await self._done.wait()
        return json.dumps({"type": "turn.interrupt", "played_ms": 700})


async def test_a_barge_in_after_the_turn_generator_returned_still_trims(
    persona, scenario, fake_pipeline, monkeypatch
):
    """The reply finished *and* the generator returned before the interrupt --
    so `_finalize_interrupted` never runs. `note_barge_in` sees the reply is
    already revisable and trims it there (ADR 0035). This is the common
    real-world case: a short reply is fully synthesised and forwarded in a
    second or two, long before the client finishes playing it."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 1000)
    s1 = "Der erste Satz meiner Antwort ist inhaltlich vollstaendig und lang genug fuer seinen eigenen Chunk."
    s2 = "Der zweite Satz folgt unmittelbar darauf und ist ebenfalls lang genug fuer einen eigenen Chunk hier."
    fake_pipeline.stt.transcripts = ["Bitte erklaeren Sie mir das."]
    fake_pipeline.llm.replies = [f"{s1} {s2}"]

    orch = SessionOrchestrator(persona, scenario)
    events = orch.run_turn(b"a", "turn.webm", "audio/webm")
    ws = _AfterListeningWs()

    outcome = await _run_turn_interruptible(ws, events, orch.start_playback, orch.note_barge_in)

    assert outcome in ("interrupted", "ok")  # depends on which task the wait saw first
    assistant = [m for m in orch._messages if m["role"] == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["content"] == s1 + INTERRUPTED_MARK, "history trimmed to the heard sentence"
    assert orch.turns[0].persona_text == s1, "Transcript trimmed to match"
