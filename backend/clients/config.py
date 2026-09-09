"""One place where every pipeline-backend environment variable is read — once,
at import, into a module-level constant, never from inside a function elsewhere.

Required variables have no default and throw before the app can listen: a wrong
or missing value should fail now, not surface later as a 403 that looks like bad
credentials. STT and the LLM have one backend each, no fallback (ADR 0011); TTS
defaults to KugelAudio with the DiReKT model as fallback (ADR 0040), or the
DiReKT model always under SKIP_KUGELAUDIO.
"""

import os

from dotenv import load_dotenv
from kugelaudio import KugelAudio
from openai import AsyncOpenAI

load_dotenv()


def _required_env(name: str) -> str:
    """Read a variable that must be set, or throw. No default: a fallback that
    happens to look right just moves the failure to the first request."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required (see .env.example)")
    return value


def _flag(name: str) -> bool:
    """An optional on/off variable, default off. `.env` turns a blank line into
    an empty string rather than an absent name, so both read as off here."""
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


# The DiReKT model gateway (ADR 0011). A named constant because `lifespan` in
# app.py checks this same URL at boot.
DIREKT_URL = _required_env("DIREKT_URL")
DIREKT_API_KEY = _required_env("DIREKT_API_KEY")

CLIENT = AsyncOpenAI(base_url=f"{DIREKT_URL}/v1", api_key=DIREKT_API_KEY)

# Optional, default off. When truthy, TTS skips KugelAudio and uses the DiReKT
# model on every call -- which is what lets the app run without KugelAudio
# credentials at all.
#
# Named for the leg it moves, like GEMINI below. It was called DEBUG, which said
# nothing about TTS and read like a general verbosity switch: the one thing an
# operator might plausibly set on a whim, while it silently swaps a hosted voice
# for a fallback that measures 2-3x slower (ADR 0040).
SKIP_KUGELAUDIO = _flag("SKIP_KUGELAUDIO")

# Optional, default off, and deliberately its own switch rather than a second
# meaning for another: it decides whether what people say aloud is written into
# the log file.
#
# Off, the pipeline logs how long an utterance was and nothing about what was
# in it. On, it logs the text — which is personal data, sitting in a file that
# no deletion path reaches (ADR 0066). That is defensible while diagnosing a
# model, and indefensible in a running pilot, so it is opt-in, named for what
# it does, and announced at boot (`app.py`'s lifespan) so it cannot be left on
# unnoticed.
LOG_TRANSCRIPTS = _flag("LOG_TRANSCRIPTS")

# STT config.
STT_CLIENT = CLIENT
STT_MODEL = _required_env("STT_MODEL")

# LLM config. One switch, GEMINI, and everything else follows from it.
#
# Off (the default), dialogue generation runs on the shared DiReKT client above,
# exactly as ADR 0011 says and byte-for-byte as it was measured. On, all of it
# moves to Google's OpenAI-compatible endpoint (ADR 0074), which reverses the
# removal in ADR 0040 -- the gateway has served nothing but `Qwen3-4B-AWQ` since
# the trial phase ended (docs/research/model-parameters.md), and the model is
# the binding quality limit. STT and TTS never follow: they stay on the gateway
# and KugelAudio, so the switch moves one leg and not the pipeline.
#
# This is still not the provider abstraction ADR 0017 declined. There is no
# registry and no runtime choice -- one boolean, read once, and no fallback
# either way.
GEMINI = _flag("GEMINI")

# Two models, not one, and the split is the point (ADR 0074). A live reply sits
# between the user finishing a sentence and hearing one back, so it wants the
# fastest model that can hold a role; the wrap-up (ADR 0049), the follow-up
# draft (F-60) and the PDF summary (F-58) all run where nothing is waiting --
# the RQ worker, or a request whose spinner is expected -- and want the best
# writer available, because their German is what the User reads. The split also
# spends a scarce quota where it is scarce: a Turn costs two requests, a
# finished Session one.
#
# Measured 2026-09-08 (docs/research/model-parameters.md), which is what
# `.env.example` recommends from: `gemini-3.5-flash-lite` at `minimal` answers
# in 0.70 s and `gemini-3.8-flash` at `low` in 2.98 s, defaulting to `medium`
# and higher still -- a good writer and a poor conversation partner. On the free
# tier `3.8-flash` also 429s at a quota of 20 requests, which a handful of
# finished Sessions exhausts, so even the feedback leg wants `3.5-flash` until
# somebody puts a paid key behind it.
if GEMINI:
    # Required together, and named in `.env` rather than defaulted here, for the
    # same reason STT_MODEL and TTS_MODEL are: which model runs is a deployment
    # fact, and one buried in Python is one nobody checks before wondering why a
    # call feels slow.
    #
    # GEMINI_REASONING_EFFORT sits with them because it is not independent of
    # them. Its floor belongs to the model, Google does not expose it, and a
    # value underneath it is HTTP 400 INVALID_ARGUMENT whose message names no
    # parameter -- it surfaces as a Turn that fails for no visible reason.
    # Change the live model without changing this and that is what you get.
    LLM_CLIENT = AsyncOpenAI(
        base_url=_required_env("GEMINI_URL"), api_key=_required_env("GEMINI_API_KEY")
    )
    LLM_MODEL = _required_env("GEMINI_LIVE_MODEL")
    LLM_FEEDBACK_MODEL = _required_env("GEMINI_FEEDBACK_MODEL")
    LLM_REASONING_EFFORT = _required_env("GEMINI_REASONING_EFFORT")
else:
    # LLM_MODEL is required here and nowhere else: with GEMINI on it would be a
    # gateway model name that nothing reads, and a stale one is worse than none.
    LLM_CLIENT = CLIENT
    LLM_MODEL = LLM_FEEDBACK_MODEL = _required_env("LLM_MODEL")
    # The gateway has a real off switch (`enable_thinking: False`), so there is
    # no level to pick and nothing reads this.
    LLM_REASONING_EFFORT = ""

# TTS config: KugelAudio is the default; TTS_MODEL (the DiReKT model) is only the
# fallback, or always under SKIP_KUGELAUDIO.
TTS_MODEL = _required_env("TTS_MODEL")
if SKIP_KUGELAUDIO:
    # No KugelAudio client under SKIP_KUGELAUDIO, so its credentials aren't required.
    KUGELAUDIO_CLIENT = None
    KUGELAUDIO_MODEL = None
else:
    # region="eu" pins to api.eu.kugelaudio.com; the EU endpoint is used because
    # the app is deployed in the EU (ADR 0020).
    KUGELAUDIO_CLIENT = KugelAudio(api_key=_required_env("KUGELAUDIO_API_KEY"), region="eu")
    KUGELAUDIO_MODEL = _required_env("KUGELAUDIO_MODEL")
