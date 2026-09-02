# ADR 0021: STT and TTS Run as Separately Self-Hosted Local Models

## Status

Accepted (TTS half superseded by ADR 0040 — TTS now defaults to the hosted KugelAudio API, not a self-hosted model; STT's move onto the shared DiReKT gateway, see ADR 0011, is not otherwise documented)

## Context

ADR 0011 assumed the DiReKT gateway would serve STT, dialogue generation, and TTS through one endpoint. In practice, DiReKT provides API access for the dialogue/reasoning model only. The STT model (`openai/whisper-large-v3-turbo`) and TTS model (`mistralai/Voxtral-4B-TTS-2603`) are Hugging Face models that must be run and hosted by the project itself.

## Decision

We will run STT and TTS as separately hosted model servers — plain vLLM for Whisper (`vllm serve openai/whisper-large-v3-turbo --task transcription`), and the separate `vllm-omni` package for Voxtral TTS (`vllm-omni serve mistralai/Voxtral-4B-TTS-2603 --omni`) — each exposing an OpenAI-compatible endpoint, the same interface style as DiReKT. The backend is configured with three independent base URLs (`LLM_URL`, `STT_URL`, `TTS_URL`) instead of one shared gateway, and calls each with its own OpenAI client.

## Consequences

The application-level call pattern barely changes, since all three targets stay OpenAI-compatible — ADR 0017 (no provider-abstraction layer) still holds, these are direct calls per capability, just against different base URLs now. The project takes on hosting and GPU capacity for two more models that DiReKT does not provide, which still needs a concrete home (see ADR 0020 — the university server, if it has sufficient GPU capacity, is the natural candidate, but this is not yet confirmed for STT/TTS specifically). Data residency for audio now depends on wherever these two servers actually run, separately from the dialogue-generation leg covered by ADR 0011.
