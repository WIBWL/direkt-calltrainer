# ADR 0103: One OpenAI-Compatible Gateway, One Voice, and No Switches Between Them

## Context

Three switches had each moved one pipeline leg to a second backend: Gemini for dialogue, a gateway TTS fallback, and call-state notes keyed to the backend. Every request shape existed twice, the second untested. The privacy statement names only the gateway and KugelAudio. The TTS fallback hid outages by speaking in a different, slower voice.

## Decision

One backend per leg, no alternatives, no switches.

- **STT and dialogue** run on the OpenAI-compatible gateway at `DIREKT_URL`, with `STT_MODEL` and `LLM_MODEL`. One client, one request shape. `LLM_MODEL` serves both the live reply and everything written after the call.
- **Speech output** is KugelAudio only. A failure ends the Turn (ADR 0033).
- **Call-state notes** are always kept (ADR 0071).
- A Persona's voice is the single column `kugelaudio_voice_id`.
- **Nothing runs in thinking mode.** On the current model the reasoning pass overran the token budget and the context window. `llm.complete` keeps its `think` parameter for a model that needs it.

## Consequences

The quality ceiling is the gateway's model, so the guards written against small models (ADR 0037/0038/0071/0073) stay load-bearing. A second vendor means pointing `.env` at it for the whole deployment, after the privacy statement names it. A KugelAudio outage breaks calls visibly instead of degrading them silently. The request shape belongs to the model: changing `LLM_MODEL` is a change to measure, not just an `.env` edit.
