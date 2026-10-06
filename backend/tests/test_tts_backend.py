"""KugelAudio with no fallback, and the PCM16-to-WAV wrapping (ADR 0103)."""

import io
import wave

import pytest
from kugelaudio.exceptions import KugelAudioError

from backend.clients import tts
from backend.personas import PersonaVoice

# tts's internals are the unit here.
# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access

# A Persona's voice (ADR 0041/0103), built here rather than read from the
# library, which is database-backed since ADR 0041.
VOICE = PersonaVoice(kugelaudio_voice_id=1885)


class _FakeStreamingTTS:
    """Stands in for `KUGELAUDIO_CLIENT.tts`: the SDK object both paths use."""

    def __init__(self, chunks=(), error: Exception | None = None):
        self._chunks = chunks
        self._error = error
        self.requests = 0
        self.connects = 0

    async def stream_async(self, **_kwargs):
        self.requests += 1
        for chunk in self._chunks:
            yield chunk
        if self._error is not None:
            raise self._error
        yield {"final": True}

    async def connect_async(self, _model):
        """Lets the re-warm task an unfinished stream schedules finish cleanly."""
        self.connects += 1

    async def _close_ws_connection(self):
        pass


class _Chunk:
    def __init__(self, audio: bytes, sample_rate: int = 24000):
        self.audio = audio
        self.sample_rate = sample_rate


@pytest.fixture
def kugelaudio(monkeypatch):
    def install(chunks=(), error=None):
        fake = _FakeStreamingTTS(chunks, error)
        # `_pooled_request` tells audio frames from the `final` one by
        # isinstance, so the stand-in has to be the type it asks about.
        monkeypatch.setattr(tts, "AudioChunk", _Chunk)
        monkeypatch.setattr(tts, "KUGELAUDIO_CLIENT", type("C", (), {"tts": fake})())
        return fake

    return install


async def test_the_one_shot_path_returns_kugelaudio_audio(kugelaudio):
    fake = kugelaudio(chunks=[_Chunk(b"\x01\x02" * 100)])
    out = await tts.synthesize("Hallo.", VOICE, "de")
    assert fake.requests == 1
    with wave.open(io.BytesIO(out), "rb") as w:
        assert w.readframes(w.getnframes()) == b"\x01\x02" * 100


async def test_a_failing_kugelaudio_is_not_answered_in_another_voice(kugelaudio):
    kugelaudio(error=KugelAudioError("kugelaudio down"))
    with pytest.raises(KugelAudioError):
        await tts.synthesize("Hallo.", VOICE, "de")


async def test_an_empty_stream_is_a_failure(kugelaudio):
    kugelaudio(chunks=[])
    with pytest.raises(KugelAudioError):
        await tts.synthesize("Hallo.", VOICE, "de")


async def test_the_streaming_path_yields_a_wav_per_chunk(kugelaudio):
    kugelaudio(chunks=[_Chunk(b"\x01\x02" * 10), _Chunk(b"\x03\x04" * 10)])
    pieces = [piece async for piece in tts.synthesize_stream("Hallo.", VOICE, "de")]
    assert len(pieces) == 2
    with wave.open(io.BytesIO(pieces[1]), "rb") as w:
        assert w.readframes(w.getnframes()) == b"\x03\x04" * 10


async def test_the_streaming_path_raises_after_audio_as_well(kugelaudio):
    kugelaudio(chunks=[_Chunk(b"\x01\x02" * 10)], error=KugelAudioError("mid-stream"))
    with pytest.raises(KugelAudioError):
        async for _ in tts.synthesize_stream("Hallo.", VOICE, "de"):
            pass


async def test_a_transport_failure_arrives_as_a_kugelaudio_error(kugelaudio):
    kugelaudio(error=OSError("connection reset"))
    with pytest.raises(KugelAudioError):
        async for _ in tts.synthesize_stream("Hallo.", VOICE, "de"):
            pass


def test_pcm16_to_wav_produces_a_valid_mono_16bit_wav():
    pcm = b"\x01\x02" * 1000
    blob = tts._pcm16_to_wav(pcm, sample_rate=24000)
    with wave.open(io.BytesIO(blob), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 24000
        assert w.readframes(w.getnframes()) == pcm
