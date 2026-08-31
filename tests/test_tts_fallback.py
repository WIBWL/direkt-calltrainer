"""TTS backend selection: KugelAudio by default, EFRE model as fallback.

Covers ADR 0040:
  * normal path -> KugelAudio
  * KugelAudio error -> transparently falls back to the EFRE TTS model
  * DEBUG=True -> always the EFRE model, KugelAudio is never called
And the PCM16 -> WAV wrapping KugelAudio output needs.
"""

import io
import wave

import pytest
from kugelaudio.exceptions import KugelAudioError

from backend.clients import tts
from backend.personas import PersonaVoice

# tts._synthesize* are the internal backend legs this module deliberately spies on.
# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access

# A Persona's voice pair (ADR 0040/0041): the KugelAudio id and the EFRE
# fallback voice. Built here rather than read from the library, which is
# database-backed since ADR 0041.
VOICE = PersonaVoice(tts_voice="de_male", kugelaudio_voice_id=1885)


@pytest.fixture
def spy_backends(monkeypatch):
    calls = {"kugelaudio": 0, "efre": 0}

    async def fake_kugelaudio(_text, _voice, _language_id):
        calls["kugelaudio"] += 1
        return b"KUGEL-WAV"

    async def fake_efre(_text, _voice):
        calls["efre"] += 1
        return b"EFRE-WAV"

    monkeypatch.setattr(tts, "_synthesize_kugelaudio", fake_kugelaudio)
    monkeypatch.setattr(tts, "_synthesize", fake_efre)
    return calls


async def test_default_path_uses_kugelaudio(spy_backends, monkeypatch):
    monkeypatch.setattr(tts, "DEBUG", False)
    out = await tts.synthesize("Hallo.", VOICE, "de")
    assert out == b"KUGEL-WAV"
    assert spy_backends == {"kugelaudio": 1, "efre": 0}


async def test_falls_back_to_efre_when_kugelaudio_fails(spy_backends, monkeypatch):
    monkeypatch.setattr(tts, "DEBUG", False)

    async def boom(_text, _voice, _language_id):
        spy_backends["kugelaudio"] += 1
        raise KugelAudioError("kugelaudio down")

    monkeypatch.setattr(tts, "_synthesize_kugelaudio", boom)

    out = await tts.synthesize("Hallo.", VOICE, "de")
    assert out == b"EFRE-WAV"
    assert spy_backends == {"kugelaudio": 1, "efre": 1}


async def test_debug_mode_always_uses_efre_and_never_calls_kugelaudio(spy_backends, monkeypatch):
    monkeypatch.setattr(tts, "DEBUG", True)
    out = await tts.synthesize("Hallo.", VOICE, "de")
    assert out == b"EFRE-WAV"
    assert spy_backends == {"kugelaudio": 0, "efre": 1}


def test_pcm16_to_wav_produces_a_valid_mono_16bit_wav():
    pcm = b"\x01\x02" * 1000
    blob = tts._pcm16_to_wav(pcm, sample_rate=24000)
    with wave.open(io.BytesIO(blob), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 24000
        assert w.readframes(w.getnframes()) == pcm
