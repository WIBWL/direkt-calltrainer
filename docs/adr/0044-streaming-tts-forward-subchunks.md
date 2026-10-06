# ADR 0044: Forward KugelAudio's Audio Sub-Chunks; No Persistent Streaming Session

## Context

KugelAudio's batch call reached first audio in about 0.9 s, its `stream_async` in about 0.28 s. Its persistent `streaming_session` was slower to first audio (about 1.1 s), because the SDK defers synthesis until `flush`.

## Decision

- Each sentence-sized chunk is synthesized with one `stream_async` call over a pooled EU connection. Each audio frame is forwarded to the client at once as a small WAV `turn.audio.chunk`.
- A KugelAudio failure ends the Turn with `tts_failed`. There is no fallback (ADR 0103).
- **Never leave a stream short of its `final` frame.** Frames carry no request id, so an abandoned stream (after a barge-in) leaves stale audio on the socket, and every later chunk would be spoken one request late. On any exit without `final`, the pooled connection is dropped and re-warmed in the background. Only one request runs at a time.

## Consequences

The Persona is heard about half a second sooner per Turn. The wire carries about 100 small frames per Turn. KugelAudio is billed per chunk, which needs revisiting under real load.
