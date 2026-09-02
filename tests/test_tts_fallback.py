"""TTS backend selection: KugelAudio by default, DiReKT model as fallback.

Covers ADR 0040:
  * normal path -> KugelAudio
  * KugelAudio error -> transparently falls back to the DiReKT TTS model
  * DEBUG=True -> always the DiReKT model, KugelAudio is never called
And the PCM16 -> WAV wrapping KugelAudio output needs.
"""

import io
import wave

import pytest
from kugelaudio.exceptions import KugelAudioError

from backend.clients import tts
from backend.personas import PERSONAS

# tts._synthesize* are the internal backend legs this module deliberately spies on.
# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access

VOICE = PERSONAS[0].voice


@pytest.fixture
def spy_backends(monkeypatch):
    calls = {"kugelaudio": 0, "direkt": 0}

    async def fake_kugelaudio(_text, _voice, _language_id):
        calls["kugelaudio"] += 1
        return b"KUGEL-WAV"

    async def fake_direkt(_text, _voice):
        calls["direkt"] += 1
        return b"DIREKT-WAV"

    monkeypatch.setattr(tts, "_synthesize_kugelaudio", fake_kugelaudio)
    monkeypatch.setattr(tts, "_synthesize", fake_direkt)
    return calls


async def test_default_path_uses_kugelaudio(spy_backends, monkeypatch):
    monkeypatch.setattr(tts, "DEBUG", False)
    out = await tts.synthesize("Hallo.", VOICE, "de")
    assert out == b"KUGEL-WAV"
    assert spy_backends == {"kugelaudio": 1, "direkt": 0}


async def test_falls_back_to_direkt_when_kugelaudio_fails(spy_backends, monkeypatch):
    monkeypatch.setattr(tts, "DEBUG", False)

    async def boom(_text, _voice, _language_id):
        spy_backends["kugelaudio"] += 1
        raise KugelAudioError("kugelaudio down")

    monkeypatch.setattr(tts, "_synthesize_kugelaudio", boom)

    out = await tts.synthesize("Hallo.", VOICE, "de")
    assert out == b"DIREKT-WAV"
    assert spy_backends == {"kugelaudio": 1, "direkt": 1}


async def test_debug_mode_always_uses_direkt_and_never_calls_kugelaudio(spy_backends, monkeypatch):
    monkeypatch.setattr(tts, "DEBUG", True)
    out = await tts.synthesize("Hallo.", VOICE, "de")
    assert out == b"DIREKT-WAV"
    assert spy_backends == {"kugelaudio": 0, "direkt": 1}


def test_pcm16_to_wav_produces_a_valid_mono_16bit_wav():
    pcm = b"\x01\x02" * 1000
    blob = tts._pcm16_to_wav(pcm, sample_rate=24000)
    with wave.open(io.BytesIO(blob), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 24000
        assert w.readframes(w.getnframes()) == pcm
