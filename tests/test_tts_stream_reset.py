"""A KugelAudio stream left before its `final` frame resets the pooled socket
(ADR 0044 amendment).

`stream_async` reads frames off the shared connection until `final`, with no
request id to tell requests apart. A barge-in abandons the stream mid-way, so
that request's remaining audio and its `final` stay queued -- and every later
stream yields the previous request's audio as its own: a one-chunk offset that
persists for the life of the socket. Live, that was the persona's last sentence
arriving at the start of the next Turn, every Turn. So an unfinished stream
drops the pooled connection and re-warms a fresh one in the background, and
the orchestrator closes an abandoned stream at once rather than leaving it to
the garbage collector.
"""

import asyncio

import pytest
from kugelaudio.exceptions import KugelAudioError

from backend.clients import tts
from backend.personas import PersonaVoice
from backend.session.models import AudioChunk as TurnAudio
from backend.session.orchestrator import SessionOrchestrator

# pylint: disable=missing-function-docstring,protected-access

VOICE = PersonaVoice(kugelaudio_voice_id=1885)


class _Chunk:
    """Stands in for kugelaudio.models.AudioChunk (matched by isinstance)."""

    def __init__(self, audio: bytes):
        self.audio = audio
        self.sample_rate = 24000


class _StreamingTTS:
    def __init__(self, frames, fail=None):
        self.frames = frames
        self.fail = fail
        self.requests = 0
        self.closed = 0
        self.connected = 0

    async def stream_async(self, **_kwargs):
        self.requests += 1
        if self.fail is not None:
            raise self.fail
        for frame in self.frames:
            yield frame

    async def _close_ws_connection(self):
        self.closed += 1

    async def connect_async(self, _model="kugel-3"):
        self.connected += 1


class _Client:
    def __init__(self, streaming):
        self.tts = streaming


@pytest.fixture
def kugel(monkeypatch):
    """A fake pooled KugelAudio client behind `synthesize_stream`."""
    streaming = _StreamingTTS([_Chunk(b"\x00\x01" * 100), _Chunk(b"\x02\x03" * 100), {"final": True}])
    monkeypatch.setattr(tts, "AudioChunk", _Chunk)
    monkeypatch.setattr(tts, "KUGELAUDIO_CLIENT", _Client(streaming))
    return streaming


async def _settle():
    """Let the background re-warm task run."""
    if tts._background:
        await asyncio.gather(*tts._background, return_exceptions=True)


async def test_a_stream_left_before_final_drops_the_pooled_socket_and_rewarms(kugel):
    stream = tts.synthesize_stream("Ein Satz.", VOICE, "de")
    first = await anext(stream)
    assert first.startswith(b"RIFF"), "one WAV piece was produced"

    await stream.aclose()  # the barge-in
    await _settle()

    assert kugel.closed == 1, "the poisoned socket is dropped"
    assert kugel.connected == 1, "and a fresh one is warmed off the critical path"


async def test_a_stream_read_to_its_final_frame_keeps_the_socket(kugel):
    pieces = [piece async for piece in tts.synthesize_stream("Ein Satz.", VOICE, "de")]
    await _settle()

    assert len(pieces) == 2
    assert kugel.closed == 0 and kugel.connected == 0


async def test_a_stream_failing_before_audio_raises_and_drops_the_socket(kugel):
    kugel.fail = KugelAudioError("kugelaudio down")

    with pytest.raises(KugelAudioError):
        async for _ in tts.synthesize_stream("Ein Satz.", VOICE, "de"):
            pass
    await _settle()

    assert kugel.closed == 1, "no `final` was read, so the socket is not trusted"


async def test_the_orchestrator_closes_an_abandoned_stream_before_the_teardown_returns(
    persona, scenario, fake_pipeline, monkeypatch
):
    """The reset lives in the stream's `finally`, which only runs when the
    stream is closed. Left to the garbage collector that happens *later*,
    possibly after the next chunk has already been synthesized on the poisoned
    socket; the orchestrator therefore closes the stream itself."""
    closed = []

    async def recording_stream(text, _voice, _language_id):
        try:
            yield b"AUDIO:" + text.encode()
            yield b"AUDIO:more"
        finally:
            closed.append(text)

    monkeypatch.setattr(tts, "synthesize_stream", recording_stream)
    fake_pipeline.stt.transcripts = ["Worum geht es?"]
    fake_pipeline.llm.replies = ["Es geht um die Exportfunktion, die seit elf Tagen nicht funktioniert."]

    orch = SessionOrchestrator(persona, scenario)
    gen = orch.run_turn(b"a", "turn.webm", "audio/webm")
    async for event in gen:
        if isinstance(event, TurnAudio):
            break  # the first piece went out; the user barges in
    assert not closed, "the stream is still open at this point"

    await gen.aclose()

    assert closed == ["Es geht um die Exportfunktion, die seit elf Tagen nicht funktioniert."]


async def test_the_one_shot_path_drops_the_socket_too(kugel):
    """ADR 0044's invariant is about the pooled connection, and the one-shot
    request uses the same one.

    It had no `final` check and no reset, and while KugelAudio still had a
    fallback behind it (ADR 0040) that was invisible: the failure was answered
    in the other voice and everything looked healthy -- while the abandoned
    request's frames waited on the shared socket for the next call in the
    process, which then heard the end of somebody else's goodbye and was a
    chunk out of step from there on.
    """
    kugel.frames = [_Chunk(b"\x00\x01" * 100)]  # audio, then the stream dies
    kugel.fail = None

    async def dying_stream(**_kwargs):
        yield _Chunk(b"\x00\x01" * 100)
        raise KugelAudioError("connection reset mid-stream")

    kugel.stream_async = dying_stream

    with pytest.raises(KugelAudioError):
        await tts.synthesize("Auf Wiederhoeren.", VOICE, "de")
    await _settle()

    assert kugel.closed == 1, "the socket nobody finished reading is dropped"


async def test_the_one_shot_path_keeps_a_finished_socket(kugel):
    """The other direction, so the reset cannot simply be made unconditional:
    a stream read to its `final` frame leaves the connection usable."""
    out = await tts.synthesize("Auf Wiederhoeren.", VOICE, "de")
    await _settle()

    assert out.startswith(b"RIFF")
    assert kugel.closed == 0


async def test_two_sessions_cannot_stream_on_the_pooled_socket_at_once(kugel):
    """One request at a time on the shared connection.

    The frames carry no request id, and `websockets` refuses two concurrent
    `recv()` calls on one connection outright -- a ConcurrencyError, which is a
    RuntimeError and is caught nowhere along the TTS path: one call would end on
    `tts_failed` and the other be stored as an aborted Session and logged as a
    client that had gone away. ADR 0044 treated low concurrency as a cost
    argument; it is a precondition.
    """
    in_flight = 0
    overlap = 0

    async def counting_stream(**_kwargs):
        nonlocal in_flight, overlap
        in_flight += 1
        overlap = max(overlap, in_flight)
        try:
            await asyncio.sleep(0)
            yield _Chunk(b"\x00\x01" * 100)
            await asyncio.sleep(0)
            yield {"final": True}
        finally:
            in_flight -= 1

    kugel.stream_async = counting_stream

    async def one_call():
        return [piece async for piece in tts.synthesize_stream("Ein Satz.", VOICE, "de")]

    results = await asyncio.gather(one_call(), one_call(), one_call())

    assert overlap == 1, "the requests were serialised, not interleaved"
    assert all(r for r in results), "and every one of them got its audio"
