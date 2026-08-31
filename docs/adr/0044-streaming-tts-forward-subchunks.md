# ADR 0044: Forward KugelAudio's Audio Sub-Chunks; No Persistent Streaming Session

## Status

Accepted (refines ADR 0033's TTS leg; builds on ADR 0040)

## Context

ADR 0033 made the Session pipeline stream: the dialogue model's tokens are
buffered into sentence-sized chunks (`backend/session/chunking.py`) and each
chunk is synthesized with one TTS call, so audio playback can begin before the
whole reply exists. Under ADR 0040 that call is KugelAudio's, via the SDK's
`generate_async` — a *batch* call that returns a chunk's audio only once the
whole chunk is synthesized.

Measured against the live KugelAudio API (EU endpoint), `generate_async`'s time
to first audio for the first chunk of a Turn is ~0.9 s (p50), against ~0.28 s
for the same text through the SDK's `stream_async`, which yields audio frames
as the model produces them. On the perceived critical path — STT (~0.8 s,
blocking) then the first dialogue chunk (~0.3–0.5 s) then TTS — that ~0.6 s is
roughly a third of the delay before the Persona is heard. End-to-end the change
took a Turn's first-audio from ~1.5 s to ~1.0 s in testing.

KugelAudio's own guidance points at a persistent `streaming_session`: keep one
WebSocket open for the whole Turn, feed the token stream in, and `flush` once —
paying the model's first-audio cost a single time per Turn instead of once per
chunk. Measured with `kugelaudio==1.9.0`, this was **slower** to first audio
(~1.1 s p50), not faster: the SDK's `session.send()` does a ~50 ms poll for
audio and returns, so with the LLM producing a sentence every ~200 ms the
server defers synthesis until the final `flush`, which lands at the end of the
reply. The persistent session wins on *total* Turn time (one prefill, not N),
but total time is not what the user waits on — the audio plays out over several
seconds regardless of when synthesis finished.

The Whisper STT leg (ADR 0033) still has no partial-output mode and stays one
blocking call per Turn.

## Decision

`backend/clients/tts.py` gains `synthesize_stream(text, voice, language_id)`,
an async iterator over WAV pieces. It calls KugelAudio `stream_async` once per
already-chunked text segment, over the connection `prewarm()` pools
(`reuse_connection=True`), and yields each `AudioChunk` wrapped as a standalone
WAV. `SessionOrchestrator._stream_and_synthesize` forwards each piece straight
out as a `turn.audio.chunk` wire message instead of buffering a chunk's audio
into one blob.

We keep **one `stream_async` call per sentence-sized chunk**, not a persistent
`streaming_session`. Each call is a fresh model prefill, but the second and
later chunks' synthesis overlaps playback of the earlier ones, so only the
first chunk's first-audio cost is on the critical path. If the SDK's
`send()`/`flush()` timing changes so that a persistent session delivers audio
mid-Turn, revisiting this is a contained change — the call site is one method.

The KugelAudio client is constructed with `region="eu"`
(`backend/clients/config.py`): the pilot is hosted on the Würzburg campus
(ADR 0020), so the EU endpoint is the nearest and shaves round-trip latency
from every synthesis call.

The one-shot `synthesize()` (buffered) stays for the startup health check and
the fixed fallback-closing line (ADR 0038), where first-audio latency is
irrelevant.

Failure handling follows ADR 0016 / ADR 0033 per this shape: if KugelAudio
fails **before** a chunk has produced any audio, that chunk falls back to one
EFRE Voxtral batch call (ADR 0040), retried once; if it fails **after** audio
for the chunk has already been sent, the Turn ends with `tts_failed` — a fresh
synthesis would diverge from what the user already heard. Barge-in (ADR 0035)
is unchanged in contract: closing the Turn generator abandons the in-flight
`stream_async` iterator, and only chunks that produced at least one audio piece
are committed to the transcript.

## Consequences

The Persona is heard about half a second sooner per Turn, which is the single
largest latency cut available on the pipeline short of a faster STT model. The
wire protocol is unchanged in shape but chattier — ~90–110 small
`turn.audio.chunk` messages per Turn instead of ~3–5 — each a valid short WAV
the existing gapless-playback client (ADR 0033) already handles; at ~150 ms of
audio per piece this is comfortable headroom, not a concern, but it is more
frames and more `decodeAudioData` calls than before.

KugelAudio is now billed one synthesis request per sentence chunk rather than
per Turn, and the model does N prefills per Turn instead of one. Against a
hosted third-party API at pilot scale (low concurrency) this is an accepted
cost; it would deserve reconsideration under real load, at which point the
persistent-session path — or KugelAudio shipping a lower `send()` poll — is the
lever.

`synthesize_stream`'s per-chunk EFRE fallback keeps ADR 0040's "lose KugelAudio,
keep talking" property, but a mid-utterance KugelAudio failure now ends the
Turn rather than silently finishing it on EFRE, because the streamed audio
already committed to a voice and pace that a batch EFRE call would break.

The orchestrator's one-chunk-deep synthesis pipeline (`_drain_if_pending`, the
`asyncio.Task` per chunk) is gone: `stream_async` already overlaps generation
and playback, so the extra machinery earned nothing once audio was forwarded
sub-chunk by sub-chunk.
