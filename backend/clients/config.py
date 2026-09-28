"""The live call's own pipeline variables, read once at import: speech
recognition on the gateway and speech output on KugelAudio (ADR 0011, ADR 0103).
The gateway itself and the LLM are `shared/clients/config.py`, which the worker
reads too."""

from kugelaudio import KugelAudio

from shared.clients.config import CLIENT, required_env

# STT config: the gateway's client, another model.
STT_CLIENT = CLIENT
STT_MODEL = required_env("STT_MODEL")

# TTS config: KugelAudio, and nothing else (ADR 0103). region="eu" pins to
# api.eu.kugelaudio.com; the EU endpoint is used because the app is deployed in
# the EU (ADR 0020).
KUGELAUDIO_CLIENT = KugelAudio(api_key=required_env("KUGELAUDIO_API_KEY"), region="eu")
KUGELAUDIO_MODEL = required_env("KUGELAUDIO_MODEL")
