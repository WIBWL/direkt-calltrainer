"""Spoken content stays out of the log unless it is asked for (ADR 0066).

The log file is outside every deletion path this application has: a transcript
written there survives a withdrawn consent and a deleted training, and no route
can reach it. It was going in at INFO on every Turn, so this is a leak that was
running rather than a feature that was missing — which is why it gets a test of
its own rather than a line in the deletion suite.

`LOG_TRANSCRIPTS` is read at import into module-level names, so these tests
patch those names rather than the environment: setting the variable after the
fact would change nothing, and a test that did it would pass while proving the
opposite of what it claims.

Records are captured by a handler attached to this module's own logger rather
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
    """Everything `stt` logs during the test."""
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


async def test_the_transcript_does_not_reach_the_log_by_default(
    stt_client, logged, monkeypatch  # pylint: disable=unused-argument
) -> None:
    """The default has to be silence about content. Anything else means the
    pilot writes what people said into a file nobody can delete from."""
    monkeypatch.setattr(stt, "LOG_TRANSCRIPTS", False)

    result = await stt.transcribe(b"audio", "turn.wav", "audio/wav", "de")

    assert result == SPOKEN, "the caller still gets the text; only the log does not"
    assert logged.messages, "nothing was captured — the test would pass vacuously"
    assert SPOKEN not in logged.text
    assert "Alice Example" not in logged.text
    assert "4711" not in logged.text


async def test_the_length_is_still_logged(
    stt_client, logged, monkeypatch  # pylint: disable=unused-argument
) -> None:
    """Suppressing the content must not cost the signal that made the line
    worth having: an empty or absurdly short transcript is how a VAD misfire
    and a silent hallucination show up."""
    monkeypatch.setattr(stt, "LOG_TRANSCRIPTS", False)

    await stt.transcribe(b"audio", "turn.wav", "audio/wav", "de")

    assert str(len(SPOKEN)) in logged.text


async def test_the_switch_really_does_switch(
    stt_client, logged, monkeypatch  # pylint: disable=unused-argument
) -> None:
    """The opt-in has to work, or someone diagnosing a model will reach for a
    quick `print` and leave it in."""
    monkeypatch.setattr(stt, "LOG_TRANSCRIPTS", True)

    await stt.transcribe(b"audio", "turn.wav", "audio/wav", "de")

    assert SPOKEN in logged.text


def test_the_switch_is_off_unless_it_is_set(monkeypatch) -> None:
    """Read from the environment the same way the other flags are, and off for anything
    that is not an explicit yes — including the empty value .env ships.

    The reload is restored in a `finally`, not left to monkeypatch: undoing the
    environment variable does not re-read it, so without this the module would
    keep whichever value the last iteration set for the rest of the session.
    """
    # Imported inside: re-reading the module-level flag needs a fresh import.
    import importlib  # pylint: disable=import-outside-toplevel

    from backend.clients import config  # pylint: disable=import-outside-toplevel

    try:
        for value, expected in (("", False), ("false", False), ("no", False),
                                ("true", True), ("1", True), ("yes", True)):
            monkeypatch.setenv("LOG_TRANSCRIPTS", value)
            reloaded = importlib.reload(config)
            assert reloaded.LOG_TRANSCRIPTS is expected, f"{value!r} should be {expected}"
    finally:
        monkeypatch.delenv("LOG_TRANSCRIPTS", raising=False)
        importlib.reload(config)


# --- The other half of the pipeline -----------------------------------------
#
# The switch is one rule for the whole pipeline, and until now only the STT leg
# was pinned to it. The TTS leg logged the Persona's line unconditionally, once
# per chunk, so the whole Persona side of every call went into the file with the
# switch off -- while `config.py` promised that off means "how long an utterance
# was and nothing about what was in it". It is generated text rather than
# recorded speech, but it carries the name and the facts the user has just said
# back to them, and the file is outside every deletion path all the same.

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


async def test_the_persona_line_does_not_reach_the_log_by_default(tts_logged, monkeypatch) -> None:
    """One chunk synthesized with the switch off says how much was spoken and
    not a word of it."""
    tts, logged = tts_logged
    monkeypatch.setattr(tts, "LOG_TRANSCRIPTS", False)

    async for _piece in tts.synthesize_stream(SPOKEN_BY_PERSONA, _VOICE, "de"):
        pass

    assert logged.messages, "nothing was captured — the test would pass vacuously"
    assert SPOKEN_BY_PERSONA not in logged.text
    assert "Example" not in logged.text and "4711" not in logged.text
    assert str(len(SPOKEN_BY_PERSONA)) in logged.text, "the length still says what was synthesized"


async def test_the_persona_line_is_logged_when_it_is_asked_for(tts_logged, monkeypatch) -> None:
    """The switch has to actually switch, or the test above would pass against
    a line that was simply deleted."""
    tts, logged = tts_logged
    monkeypatch.setattr(tts, "LOG_TRANSCRIPTS", True)

    async for _piece in tts.synthesize_stream(SPOKEN_BY_PERSONA, _VOICE, "de"):
        pass

    assert SPOKEN_BY_PERSONA in logged.text
