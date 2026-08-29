"""Text-to-speech client call."""

import io
import logging
import wave

from kugelaudio.exceptions import KugelAudioError

from backend.clients.config import CLIENT, DEBUG, KUGELAUDIO_CLIENT, KUGELAUDIO_MODEL, TTS_MODEL
from backend.personas import PersonaVoice

logger = logging.getLogger(__name__)


async def synthesize(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    """Synthesize one chunk of text to speech: KugelAudio by default,
    falling back to the EFRE model if it fails or DEBUG is set.

    KugelAudio wants the bare language code ("de", "en") here, not a full
    locale tag -- it rejects "de-DE"/"en-GB" with "Invalid request", which
    then degrades silently into the EFRE fallback voice.
    """
    if not DEBUG:
        try:
            return await _synthesize_kugelaudio(text, voice, language_id)
        except (KugelAudioError, TimeoutError, OSError) as e:
            logger.warning("KugelAudio TTS failed, falling back to EFRE: %s", e)
    return await _synthesize(text, voice)


async def _synthesize(text: str, voice: PersonaVoice) -> bytes:
    logger.info("Synthesizing speech via TTS (%s, voice=%s): %r", TTS_MODEL, voice.tts_voice, text)
    speech = await CLIENT.audio.speech.create(
        model=TTS_MODEL,
        voice=voice.tts_voice,
        input=text,
        response_format="wav",
    )
    return speech.content


async def _synthesize_kugelaudio(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    logger.info(
        "Synthesizing speech via KugelAudio (%s, voice=%s, language=%s): %r",
        KUGELAUDIO_MODEL, voice.kugelaudio_voice_id, language_id, text,
    )
    response = await KUGELAUDIO_CLIENT.tts.generate_async(
        text=text,
        model_id=KUGELAUDIO_MODEL,
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
