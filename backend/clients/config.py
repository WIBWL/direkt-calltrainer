"""The backend's own pipeline settings: STT on the gateway, TTS on KugelAudio (ADR 0103)."""

from kugelaudio import KugelAudio

from shared.clients.config import CLIENT
from shared.env import required

STT_CLIENT = CLIENT
STT_MODEL = required("STT_MODEL")

KUGELAUDIO_CLIENT = KugelAudio(api_key=required("KUGELAUDIO_API_KEY"), region="eu")
KUGELAUDIO_MODEL = required("KUGELAUDIO_MODEL")
