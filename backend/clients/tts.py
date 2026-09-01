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
    falling back to the EFRE model if it fails or DEBUG is set."""
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


def duration_ms(wav_bytes: bytes) -> int:
    """Playback length of one synthesized chunk.

    Both backends deliver WAV -- KugelAudio's headerless PCM is wrapped above --
    so the header is always there to read. 0 for anything unreadable: the
    caller uses this to place the Persona on the Session's timeline (ADR 0048),
    which must not be able to fail a call.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wav:
            return round(wav.getnframes() * 1000 / wav.getframerate())
    except (wave.Error, ZeroDivisionError, EOFError):
        logger.warning("Synthesized chunk has no readable WAV header; timing it as 0 ms")
        return 0
