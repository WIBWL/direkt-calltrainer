"""Text-to-speech client call."""

import io
import logging
import wave

from backend.clients.config import TTS_BACKEND, TTS_CLIENT, TTS_MODEL
from backend.personas import PersonaVoice

logger = logging.getLogger("calltrainer")


async def synthesize(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    """Synthesize one chunk of text reply to speech."""
    if TTS_BACKEND == "kugelaudio":
        return await _synthesize_kugelaudio(text, voice, language_id)
    return await _synthesize(text, voice)


async def _synthesize(text: str, voice: PersonaVoice) -> bytes:
    logger.info("Synthesizing speech via TTS (%s, voice=%s): %r", TTS_MODEL, voice.tts_voice, text)
    speech = await TTS_CLIENT.audio.speech.create(
        model=TTS_MODEL,
        voice=voice.tts_voice,
        input=text,
        response_format="wav",
    )
    return speech.content


async def _synthesize_kugelaudio(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    logger.info(
        "Synthesizing speech via KugelAudio (%s, voice=%s, language=%s): %r",
        TTS_MODEL, voice.kugelaudio_voice_id, language_id, text,
    )
    response = await TTS_CLIENT.tts.generate_async(
        text=text,
        model_id=TTS_MODEL,
        voice_id=voice.kugelaudio_voice_id,
        language=language_id,
    )
    # KugelAudio returns headerless PCM16 (response.audio)
    return _pcm16_to_wav(response.audio, response.sample_rate)


def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.Wave_write(buf) as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()
