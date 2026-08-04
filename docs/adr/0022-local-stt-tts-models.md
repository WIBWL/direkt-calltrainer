# ADR 0022: STT and TTS Run as Separately Self-Hosted Local Models

## Status

Accepted

## Context

ADR 0011 assumed the EFRE-Direkt gateway would serve STT, dialogue generation, and TTS through one endpoint. In practice, EFRE-Direkt provides API access for the dialogue/reasoning model only. The STT model (`openai/whisper-large-v3-turbo`) and TTS model (`mistralai/Voxtral-4B-TTS-2603`) are Hugging Face models that must be run and hosted by the project itself.

## Decision

We will run STT and TTS as separately hosted model servers — plain vLLM for Whisper (`vllm serve openai/whisper-large-v3-turbo --task transcription`), and the separate `vllm-omni` package for Voxtral TTS (`vllm-omni serve mistralai/Voxtral-4B-TTS-2603 --omni`) — each exposing an OpenAI-compatible endpoint, the same interface style as EFRE-Direkt. The backend is configured with three independent base URLs (`LLM_URL`, `STT_URL`, `TTS_URL`) instead of one shared gateway, and calls each with its own OpenAI client.

## Consequences

The application-level call pattern barely changes, since all three targets stay OpenAI-compatible — ADR 0018 (no provider-abstraction layer) still holds, these are direct calls per capability, just against different base URLs now. The project takes on hosting and GPU capacity for two more models that EFRE-Direkt does not provide, which still needs a concrete home (see ADR 0021 — the university server, if it has sufficient GPU capacity, is the natural candidate, but this is not yet confirmed for STT/TTS specifically). Data residency for audio now depends on wherever these two servers actually run, separately from the dialogue-generation leg covered by ADR 0011.
