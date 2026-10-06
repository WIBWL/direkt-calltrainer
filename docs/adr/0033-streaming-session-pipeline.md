# ADR 0033: Streaming Session Pipeline via Chunked TTS over WebSocket

## Context

Waiting for the full reply to be generated and synthesized made each Turn feel like walkie-talkie. STT needs the whole utterance; the LLM streams tokens.

## Decision

The LLM's token stream is cut into sentence-sized chunks, with a word-boundary fallback for long runs. Each chunk is synthesized as soon as it is ready and streamed to the client over a per-Session WebSocket, so playback starts on the first chunk. STT stays one blocking call per Turn.

ADR 0016's retry applies per leg:

- **STT:** one retry.
- **LLM:** retried once only if no chunk has been sent yet. Otherwise the call ends, because a new completion would diverge from what was heard.
- **TTS:** one retry per chunk. Then the call ends, rather than speaking a reply with a gap.

## Consequences

Perceived latency drops sharply. The pipeline is stateful, makes N TTS calls per Turn, and the chunking can misfire on abbreviations.
