# ADR 0033: Streaming Session Pipeline via Chunked TTS over WebSocket

## Status

Accepted

## Context

The MVP started from a turn-based, full-request/response pipeline — record a full user turn, wait for the complete STT → dialogue → TTS chain, then play back the response — with real streaming deliberately deferred to a later phase, to keep the first implementation simple and to measure the gateway's real latency first. That latency has since proven too slow for the desired conversational feel: waiting for an entire reply to be generated and synthesized before any audio plays back makes each Turn feel like a pause-and-resume exchange rather than a phone call.

STT, dialogue generation, and TTS all run against the university-hosted EFRE-Direkt gateway (ADR 0011), selected per call by model name (ADR 0018) rather than by separate service endpoints. The dialogue-generation leg supports standard OpenAI-compatible token streaming (`stream=True`). The TTS leg is assumed whole-text-in only, with no confirmed partial/streaming synthesis mode. The STT leg has no partial-output mode at all — Whisper-style transcription needs the full utterance before it can return anything, so it is necessarily one blocking call per Turn no matter how the rest of the pipeline is shaped.

## Decision

We will stream the dialogue model's token output, buffer it into sentence/clause-sized chunks (splitting on sentence-ending punctuation, with a max-length fallback at a word boundary for long unpunctuated runs), synthesize each chunk via one TTS call as soon as it is ready, and stream each chunk's resulting audio to the client immediately over a persistent per-Session WebSocket connection. Client playback can then start on the first chunk while later chunks are still being generated and synthesized. STT stays as it was: one blocking call per Turn, since there is nothing to stream it from.

We reinterpret ADR 0016's "one retry, then graceful Session end" per pipeline leg for this shape. STT keeps its rule unchanged. For dialogue generation: if the stream fails before any chunk has been sent to the client, we retry the whole request once; if it fails after at least one chunk was already sent (and possibly already played), we do not retry — a fresh completion would diverge from audio the user already heard — and end the Session gracefully instead. For TTS: each chunk gets its own retry (one per chunk, not one per Turn, since a Turn now involves several TTS calls); a chunk that still fails after its retry ends the Session gracefully rather than silently producing a reply with a missing gap.

## Consequences

This cuts perceived per-Turn latency, addressing the Echtzeitfähigkeit shortfall the turn-based pipeline left unresolved, and turns the live conversation loop into something closer to a real phone call. In exchange, the pipeline gains real complexity: a sentence-chunking heuristic that can misfire on abbreviations or decimals, a stateful per-Session WebSocket connection instead of a stateless request/response endpoint, N TTS calls per Turn instead of 1 (more load against the TTS model), and finer-grained, per-leg failure handling instead of one linear retry chain. STT's blocking, non-streaming nature remains an accepted limitation of the underlying transcription model, not something this decision solves — the conversational feel improves for the dialogue-generation and speech-synthesis legs, not for the initial transcription step of each Turn.
