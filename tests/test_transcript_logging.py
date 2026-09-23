"""Spoken content stays out of the log, with no way to put it back (ADR 0066).

The log file is outside every deletion path this application has: a transcript
written there survives a withdrawn consent and a deleted training, and no route
can reach it. It was going in at INFO on every Turn, so this is a leak that was
running rather than a feature that was missing — which is why it gets a test of
its own rather than a line in the deletion suite.

It was closed by default and re-openable through `LOG_TRANSCRIPTS` for a while.
That switch is gone: a default is not a guarantee, and the one thing it bought —
reading a model's actual words while diagnosing it — is bought again by the leg
that fails, which logs its own error. So these tests no longer pin a default;
they pin that the text has nowhere to go.

Records are captured by a handler attached to the module's own logger rather
than through `caplog`. `configure_logging()` clears the root handlers when the
backend is first imported, which takes pytest's with it — under the full suite
`caplog` then saw nothing, and the assertion that matters most here ("the text
is absent") passed for the worst possible reason. A handler on the logger being
tested cannot be cleared out from under it by import order.
"""
import logging

import pytest

from backend.clients import stt
from backend.personas import PersonaVoice

SPOKEN = "Mein Name ist Alice Example und ich rufe wegen Vertrag 4711 an."


class _FakeTranscription:
    """The shape the gateway returns: an object carrying `.text`."""

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeSTT:
    """Stands in for the gateway client; returns `SPOKEN` verbatim."""

    class audio:  # pylint: disable=invalid-name
        class transcriptions:  # pylint: disable=invalid-name
            @staticmethod
            async def create(**_kwargs):
                """Return the fixed transcript, ignoring the request."""
                return _FakeTranscription(SPOKEN)


class _Recorder(logging.Handler):
    """Collects formatted messages from one logger."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())

    @property
    def text(self) -> str:
        """Everything captured so far, as one searchable string."""
        return "\n".join(self.messages)


@pytest.fixture
def logged():
    """Everything `stt` logs during the test, down to DEBUG: the claim is that
    the text is nowhere in the log, not that it sits under a quieter level."""
    recorder = _Recorder()
    stt.logger.addHandler(recorder)
    previous = stt.logger.level
    stt.logger.setLevel(logging.DEBUG)
    try:
        yield recorder
    finally:
        stt.logger.removeHandler(recorder)
        stt.logger.setLevel(previous)


@pytest.fixture
def stt_client(monkeypatch):
    """Replace the gateway client so no request leaves the process."""
    monkeypatch.setattr(stt, "STT_CLIENT", _FakeSTT)


async def test_the_transcript_does_not_reach_the_log(
    stt_client, logged  # pylint: disable=unused-argument
) -> None:
    """Silence about content, at every level. Anything else means the pilot
    writes what people said into a file nobody can delete from."""
    result = await stt.transcribe(b"audio", "turn.wav", "audio/wav", "de")

    assert result == SPOKEN, "the caller still gets the text; only the log does not"
    assert logged.messages, "nothing was captured — the test would pass vacuously"
    assert SPOKEN not in logged.text
    assert "Alice Example" not in logged.text
    assert "4711" not in logged.text


async def test_the_length_is_still_logged(
    stt_client, logged  # pylint: disable=unused-argument
) -> None:
    """Suppressing the content must not cost the signal that made the line
    worth having: an empty or absurdly short transcript is how a VAD misfire
    and a silent hallucination show up."""
    await stt.transcribe(b"audio", "turn.wav", "audio/wav", "de")

    assert str(len(SPOKEN)) in logged.text


# --- The other half of the pipeline -----------------------------------------
#
# One rule for the whole pipeline, and until the switch existed only the STT leg
# kept it. The TTS leg logged the Persona's line unconditionally, once per
# chunk, so the whole Persona side of every call went into the file. It is
# generated text rather than recorded speech, but it carries the name and the
# facts the user has just said back to them, and the file is outside every
# deletion path all the same.

SPOKEN_BY_PERSONA = "Guten Tag Frau Example, es geht um Vertrag 4711."
_VOICE = PersonaVoice(kugelaudio_voice_id=1)


class _Chunk:
    """Stands in for kugelaudio.models.AudioChunk (matched by isinstance)."""

    def __init__(self) -> None:
        self.audio = b"\x00\x01" * 100
        self.sample_rate = 24000


class _StreamingTTS:
    """One chunk of audio and the `final` frame, so nothing is reset."""

    async def stream_async(self, **_kwargs):
        """The pooled streaming request."""
        yield _Chunk()
        yield {"final": True}

    async def connect_async(self, _model="kugel-3"):
        """The re-warm's call, so its background task finishes quietly."""

    async def _close_ws_connection(self):
        """The reset's call."""


@pytest.fixture
def tts_logged(monkeypatch):
    """Everything `tts` logs while synthesizing one chunk through KugelAudio."""
    from backend.clients import tts  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(tts, "AudioChunk", _Chunk)
    monkeypatch.setattr(tts, "KUGELAUDIO_CLIENT", type("C", (), {"tts": _StreamingTTS()})())
    recorder = _Recorder()
    tts.logger.addHandler(recorder)
    previous = tts.logger.level
    tts.logger.setLevel(logging.DEBUG)
    try:
        yield tts, recorder
    finally:
        tts.logger.removeHandler(recorder)
        tts.logger.setLevel(previous)


async def test_the_persona_line_does_not_reach_the_log(tts_logged) -> None:
    """One synthesized chunk says how much was spoken and not a word of it —
    including at DEBUG, which is where that line now sits, because it fires per
    chunk rather than per Turn."""
    _tts, logged = tts_logged

    async for _piece in _tts.synthesize_stream(SPOKEN_BY_PERSONA, _VOICE, "de"):
        pass

    assert logged.messages, "nothing was captured — the test would pass vacuously"
    assert SPOKEN_BY_PERSONA not in logged.text
    assert "Example" not in logged.text and "4711" not in logged.text
    assert str(len(SPOKEN_BY_PERSONA)) in logged.text, "the length still says what was synthesized"


def test_there_is_no_switch_to_turn_it_back_on() -> None:
    """The point of removing `LOG_TRANSCRIPTS` was that a default is not a
    guarantee. A reader who puts it back in `.env` must get nothing, and a
    module that grows the name again should fail here rather than quietly."""
    from backend.clients import config, tts  # pylint: disable=import-outside-toplevel
    from backend.session import orchestrator  # pylint: disable=import-outside-toplevel

    for module in (config, stt, tts, orchestrator):
        assert not hasattr(module, "LOG_TRANSCRIPTS"), f"{module.__name__} reads the switch again"
