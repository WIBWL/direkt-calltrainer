"""Text-to-speech client call."""

import io
import logging
import wave

from backend.clients.config import (
    CLIENT,
    KUGELAUDIO_CLIENT,
    KUGELAUDIO_MODEL,
    KUGELAUDIO_VOICE_ID,
    TTS_BACKEND,
    TTS_MODEL,
    TTS_VOICE,
)

logger = logging.getLogger("calltrainer")


async def synthesize(text: str, language_id: str) -> bytes:
    """Synthesize one chunk of reply text (e.g. one sentence) to speech, as a WAV file."""
    if TTS_BACKEND == "kugelaudio":
        return await _synthesize_kugelaudio(text, language_id)
    return await _synthesize_efre(text)


async def _synthesize_efre(text: str) -> bytes:
    logger.info("Synthesizing speech via TTS (%s, voice=%s): %r", TTS_MODEL, TTS_VOICE, text)
    speech = await CLIENT.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text,
        response_format="wav",
    )
    return speech.content


async def _synthesize_kugelaudio(text: str, language_id: str) -> bytes:
    # Only ever called when TTS_BACKEND == "kugelaudio", which is exactly
    # when config.py populates these (see its comment) — asserts here just
    # narrow the type for the calls below, not a real runtime possibility.
    assert KUGELAUDIO_CLIENT is not None
    assert KUGELAUDIO_MODEL is not None

    logger.info(
        "Synthesizing speech via KugelAudio (%s, voice=%s, language=%s): %r",
        KUGELAUDIO_MODEL, KUGELAUDIO_VOICE_ID, language_id, text,
    )
    response = await KUGELAUDIO_CLIENT.tts.generate_async(
        text=text,
        model_id=KUGELAUDIO_MODEL,
        voice_id=KUGELAUDIO_VOICE_ID,
        language=language_id,
    )
    # KugelAudio returns raw headerless PCM16 (response.audio) — wrap it as a
    # WAV file so the client's decodeAudioData() can play it, same as the
    # ready-made WAV the EFRE-DiReKT leg returns directly.
    return _pcm16_to_wav(response.audio, response.sample_rate)


def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    # wave.Wave_write directly, not the wave.open() factory: open()'s return
    # type is ambiguous between Wave_read/Wave_write (mode is just a string),
    # which linters can't narrow, even with an explicit annotation.
    with wave.Wave_write(buf) as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()
