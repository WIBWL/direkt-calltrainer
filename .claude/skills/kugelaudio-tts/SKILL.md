---
name: kugelaudio-tts
description: Build a correct, low-latency KugelAudio TTS integration — the streaming-session model, flush semantics, the latency levers that actually matter, audio formats, and how to write text that synthesises well. Use when touching backend/clients/tts.py, the Session audio pipeline (orchestrator, session_ws), or the persona system prompt.
---

# KugelAudio TTS integration

> Hand-written from the official docs (2026-08-31), because KugelAudio's own
> `kugelaudio-skills install` command is not in the released Python package
> (`kugelaudio==1.9.0`, the latest). Re-generate from the real thing if a later
> release ships the CLI. Sources are linked at the bottom; measured numbers for
> *this* deployment are in `test/model-parameters.md`.

## Model

Use **`kugel-3`** for all text-to-speech. It is the only current model
(`ka.models.list()` returns just `kugel-3`): 39 languages, 24 kHz native,
10 000-char max input, streaming in and out, voice cloning, IPA, word
timestamps, `<break>` support. Legacy ids (`kugel-2.5`, `kugel-2-turbo`,
`kugel-2`, `kugel-1*`) are accepted for compatibility but deprecated and **not
faster** — "turbo" is a misnomer here (measured: `kugel-3` beats
`kugel-2-turbo` on full-synthesis time, ties on time-to-first-audio).

`kugel-agent-1` (`wss://api.kugelaudio.com/v1/realtime`) is a *different
product* — a full speech-to-speech agent with its own STT and turn detection.
This project does its own STT (EFRE Whisper) and VAD, so it wants the **TTS
streaming API**, not the realtime agent.

## The four mistakes that cause bad latency

From `streaming/chunking-and-latency`, verbatim intent:

1. **Per-segment `flush=true`.** Every flush is a fresh model prefill and pays
   the full model time-to-first-audio (TTFA). Flush after every sentence → you
   pay it N times per turn instead of once.
2. **One session per sentence.** A new WebSocket handshake *plus* a fresh
   prefill, every sentence. Keep one session open for the whole assistant turn.
3. **Client-side sentence buffering before `send`.** The server already buffers
   tokens and chunks at sentence boundaries. Pre-buffering just adds latency.
4. **`send(text, flush=true)` per word "for lower latency".** The opposite —
   word-granular flushing is the worst possible TTFA.

## Latency levers, in priority order

From `latency`:

1. **Pre-connect at startup.** `await client.tts.connect_async("kugel-3")` once,
   at process start. Takes the TCP+TLS+WebSocket handshake (~300–600 ms) off the
   first user-facing request. Called "the single biggest fix".
2. **Set `language` explicitly** (ISO-639-1, e.g. `"de"`). Omitting it triggers
   auto-detection (~150 ms) and can produce wrong normalisations on short text.
3. **Server-side chunking + a single end-of-turn flush** (see below).
4. **Don't force extra prefills** — no mid-turn `flush`.
5. **Closest region + native sample rate.** `region="eu"` (or an `eu-` key
   prefix) pins to `api.eu.kugelaudio.com`. Keep `sample_rate=24000` — other
   rates only add resampling, they don't speed up inference.

Do NOT tune around published millisecond numbers — KugelAudio deliberately
doesn't publish them (they depend on region/voice/load). The *ordering* is
stable; measure absolute numbers against your own endpoint, pre-connected,
timing from after the connection opens, p50 **and** p95.

## The streaming-session model (native `/ws/tts/stream`)

One session = **one assistant turn** (one persona utterance). The WebSocket is
reused across turns; each turn is the synthesis and billing unit.

```python
async with client.tts.streaming_session(voice_id=VOICE, model_id="kugel-3",
                                         language="de") as session:
    async for token in llm_stream:                 # raw LLM tokens
        async for chunk in session.send(token):    # no flush
            forward(chunk.audio)                    # 24 kHz mono PCM16
    async for chunk in session.flush():            # exactly once, at turn end
        forward(chunk.audio)
```

* The server's text buffer accumulates tokens and hands a **sentence-sized**
  chunk to the model at a natural boundary (or after a 500 ms stale-buffer
  fallback). Within a turn the model's KV cache and voice conditioning carry
  across chunks, so prosody stays continuous — **you do not control when
  synthesis starts, the server does.**
* **Raw LLM tokens are fine** as long as you `send` without `flush`. The
  "word-level is bad" rule is about *flushing* per word, not *sending*.
* The native API has **no client-side chunk control.** `chunk_length_schedule`
  and `auto_mode` exist only on the ElevenLabs-compat layer, where they are
  "accepted for compatibility" and ignored — the native buffer decides.
  Unknown WebSocket fields are dropped with a warning.
* **Idle auto-flush at 5 s.** If you stream text and then send nothing (and no
  `flush`) for 5 s, the server ends the turn — a `warning` frame, the buffered
  text synthesised, then `final` + `session_closed`. WebSocket pings do **not**
  reset this timer. If the upstream LLM stalls >5 s mid-reply, the rest of the
  reply becomes a second, separately-billed turn.

### If you're feeding chunks bigger than raw tokens

Pick the **largest** chunk you can. Best → worst TTFA per emitted segment:

| Granularity | Verdict |
|---|---|
| Full turn in one `send` | Best possible — use when the whole text is ready |
| Sentence-level | Recommended for streamed LLM output |
| ≥ 20-character chunks | Acceptable fallback |
| Clause-level (comma/semicolon) | Avoid — each pays model TTFA |
| Word / sub-word | Don't — worst shape |

## Barge-in

`await session.cancel_current()` — abandons the current turn, drops buffered
text, keeps the socket open. The server replies `{"interrupted": true}` **instead
of** `final`/`session_closed`.

* Stop local playback **immediately** on the call — don't wait for the ack. A
  few in-flight audio frames may still arrive.
* The next `session.send()` starts a new turn instantly (config resends
  automatically).
* Python SDK quiet timeout for the ack is 30 s (5 s in JS/Java).
* Code that only handles `final` will hang on a barge-in path — handle
  `interrupted` too.

## SDK specifics (`kugelaudio==1.9.0`, verified against source)

These matter for a correct implementation and aren't obvious from the prose docs:

* **`session.send(text)` (no flush) does a ~50 ms poll for audio, then returns.**
  If the buffered text hasn't crossed a sentence boundary, `send()` yields
  nothing and returns immediately; once the server starts generating it blocks
  and streams that chunk's audio. So feeding *one raw token per `send()`* rate-
  limits you to ~20 sends/s. **Feed sentence-sized chunks** (the skill's #2,
  "recommended for streamed LLM output") — fewer `send()` calls, and each
  complete sentence triggers synthesis right away. Still no `flush` until the
  turn ends.
* **`streaming_session().__aexit__` calls `close()`, which discards audio still
  in flight.** Always run `session.flush()` to completion (it receives up to
  `session_closed`) *before* leaving the `async with` — the flush drains
  everything, so the discard is then a no-op. Never rely on `__aexit__` to
  deliver tail audio.
* **`close()` vs `end_session()`:** `close()` shuts the WebSocket;
  `end_session()` ends the turn but keeps the socket, saving the
  ~200–300 ms handshake on the next turn. Reuse one `StreamingSession` for the
  whole call, `close()` once at the end.
* **`connect_async()` pools a connection for `stream()` / `stream_async()`, not
  for `streaming_session()`** — a persistent `streaming_session` is its own warm
  connection; don't expect `prewarm()` to help it.
* **`await session.cancel_current()`** clears `session._last_word_timestamps`
  and resets `_config_sent`; capture anything you need from the cancelled turn
  *before* calling it (or via the `on_word_timestamps` callback, which fires as
  frames arrive). On a dead socket it self-heals — sets `_ws = None` so the next
  `send()` reconnects.
* **`region="eu"`** is a `KugelAudio(...)` constructor kwarg (or an `eu-` API
  key prefix). This pilot is Würzburg-hosted → use it.
* **Word timestamps:** `streaming_session(word_timestamps=True,
  on_word_timestamps=cb)`. Each `WordTimestamp` has `word`, `start_ms`,
  `end_ms`, `char_start`, `char_end`, `score` (always 1.0). Frames arrive
  *after* their audio (zero playback delay). Use them to know which words were
  actually voiced when a barge-in lands.

## Turn-end frames

Graceful end emits, in order:

* `final` — `{final, total_audio_seconds, total_text_chunks, total_audio_chunks}`,
  right after the last audio frame. **Key "playback done" / hang-up on this.**
* `session_closed` — carries `usage` (`audio_seconds`, `characters`,
  `cost_cents` in EUR, `model_id`; `cost_cents` may be `null` with
  `cost_unavailable: true`). **Key billing on this.**

`cancel` emits neither — only `interrupted`.

## Config parameters (streaming session / config message)

| Param | Default | Notes |
|---|---|---|
| `voice_id` | — | required; unknown id → `NotFoundError` |
| `model_id` | `kugel-3` | |
| `cfg_scale` | `2.0` | clamped `[1.2, 2.5]`; higher tracks the reference voice tighter, can add artefacts. `2.0` was fastest and the documented sweet spot. |
| `temperature` | SDK sends none → server default (docs' example config shows `0.4`) | lower = more consistent delivery |
| `sample_rate` | `24000` | native; do not change for latency |
| `normalize` | `true` | numbers/dates/currency → spoken words |
| `language` | — | **always set it** (ISO-639-1); `de` supported |
| `speed` | `1.0` | range `0.8`–`1.2`, WSOLA pitch-preserving; out-of-range → 400 |
| `flush_timeout_ms` | `500` | server auto-flush after N ms without new text |
| `max_buffer_length` | `1000` | force-flush above this many buffered chars |

Config is **sticky** across turns on a connection. `update_settings(...)`
changes `{cfg_scale, temperature, max_new_tokens, language, normalize, speed}`
**for the next turn**. Identity fields (`voice_id`, `model_id`, `sample_rate`,
`output_format`, `dictionary_ids`) need `update_config()` between turns, after
`end_session()`.

Client: `KugelAudio(api_key, region="eu"|None, api_url=None, tts_url=None,
timeout=60.0, keepalive_ping_interval=20.0)`. Use `await KugelAudio.create(...)`
+ `stream_async()` for pooled connections; `await client.aclose()` to release.

## Audio formats

Native `output_format`: `pcm_8000`, `pcm_16000`, `pcm_22050`, `pcm_24000`,
`ulaw_8000`, `alaw_8000`. WAV / MP3 are **not native** — only through the
ElevenLabs-compat proxy. Send `sample_rate` **or** `output_format`, never both
(conflict → 400).

* Browser playback (this project): `pcm_24000`, or raw PCM (`chunk.audio`,
  `chunk.sample_rate`) wrapped to WAV client/server-side.
* Telephony: `ulaw_8000` (G.711, 1 byte/sample).

## Writing text for speech

Give a variant of this to the LLM that generates the spoken lines, and strip
anything that slips through before synthesis:

* **No markdown** (`**`, `*`, `#`, `-`, bullet points) — read out literally.
* **No emoji** — garbled or vocalised.
* **Numbers as digits** ("Sie haben 3 Nachrichten") — `normalize` speaks them.
* **Short, punctuation-terminated sentences** — lets the server chunk and
  stream earlier.
* `!`, ALL-CAPS and `?!` are **deliberate prosody cues** (energetic delivery) —
  use sparingly, on purpose.
* Punctuation *is* the prosody control: `,` brief pause · `.` falling
  intonation · `…` long trailing pause · `—` abrupt / interruption · `?` rising
  · newline = paragraph-level pause.

### The three honoured SSML tags

Everything else (`<speak>`, `<emphasis>`, `<phoneme>`, `<say-as>`, `<audio>`) is
left in the output verbatim.

* `<break time="300ms"/>` · `<break strength="medium"/>` · `<break/>` (200 ms).
  Durations snap: `0` → none, `1–299` → 200 ms, `300–449` → 400 ms, `450+` →
  500 ms; `weak`/`medium` → 200 ms, `strong` → 500 ms. Chain tags for longer
  silence. Works inline in streaming. Not inside `<spell>`.
* `<spell>D8239014</spell>` — reads each character; auto-groups every 4 with
  500 ms pauses (reset by space `.` `-` `@`); `group="2"` for pairs, `group="0"`
  off. Keep terminal punctuation **outside** the tag. No nesting, no `<break>`
  inside. `@` localises ("at" / "ät" / "arobase").
* `<prosody rate="slow|medium|fast">…</prosody>` or a numeric `0.8`–`1.2`.
  Overrides the global `speed` within the span. No nesting; on streaming it must
  open and close within a single message.

### Pronunciation

Inline IPA between slashes with real IPA characters: `Willkommen bei /ˈkuːɡl̩/`.
For recurring fixes use a pronunciation dictionary
(`client.dictionaries.create(...)` + `entries.add(word=..., ipa=...)`), applied
via `dictionary_ids` (or the project's active dictionaries by default; `[]`
disables them for a request).

## How this maps to the Calltrainer repo (as of ADR 0044)

* **`backend/clients/tts.py::synthesize_stream`** — the live path. One
  `stream_async` call per sentence-sized chunk from `session/chunking.py`, over
  the `prewarm()`-pooled connection, yielding each `AudioChunk` as a standalone
  WAV. `SessionOrchestrator._speak` forwards each straight out as
  `turn.audio.chunk`. `synthesize()` (buffered) is kept for the health check
  and the fixed fallback-closing line only.
* **Why not a persistent `streaming_session`?** Measured slower to first audio
  with `kugelaudio==1.9.0` — `send()`'s ~50 ms poll defers synthesis to the
  final `flush`, which lands at end-of-reply. `stream_async` per chunk pays N
  model prefills (worse *total* time, irrelevant to the user) but each chunk's
  first-audio is ~0.28 s and chunks 2..N overlap playback. See ADR 0044. If a
  later SDK delivers audio mid-`send()`, revisit — the call site is one method.
* **`region="eu"`** is set on `KUGELAUDIO_CLIENT` (`backend/clients/config.py`).
* **Barge-in:** closing the Turn generator abandons the in-flight `stream_async`
  iterator; `_finalize_interrupted` commits only chunks that produced audio.
  (`cancel_current()` would only matter with a persistent session.)
* **Failure:** KugelAudio failing *before* a chunk's first audio → that chunk
  falls back to one EFRE batch call (retried once). Failing *after* → the Turn
  ends `tts_failed` (ADR 0044).
* **Still open — persona prompt:** `orchestrator._build_system_prompt` has no
  "write for speech" rules. Add the no-markdown / no-emoji / prosody-punctuation
  block above so persona lines synthesise cleanly. The dialogue model
  occasionally emits `—`, quotes, and stage directions.
* **Chattiness:** ~90–110 `turn.audio.chunk` messages per Turn now (was ~3–5).
  Fine at ~150 ms audio each; if it ever matters, coalesce small `AudioChunk`s
  in `synthesize_stream` *after* yielding the first one immediately.

## Sources

- https://docs.kugelaudio.com/latency.md
- https://docs.kugelaudio.com/models.md
- https://docs.kugelaudio.com/streaming/overview.md
- https://docs.kugelaudio.com/streaming/turn-lifecycle.md
- https://docs.kugelaudio.com/streaming/chunking-and-latency.md
- https://docs.kugelaudio.com/streaming/barge-in.md
- https://docs.kugelaudio.com/api-reference/realtime.md
- https://docs.kugelaudio.com/api-reference/tts/stream-input.md
- https://docs.kugelaudio.com/api-reference/tts/audio-formats.md
- https://docs.kugelaudio.com/sdks/python/streaming.md
- https://docs.kugelaudio.com/sdks/python/generate.md
- https://docs.kugelaudio.com/sdks/python/configuration.md
- https://docs.kugelaudio.com/guides/regions.md
- https://docs.kugelaudio.com/integrations/pipecat.md
- https://docs.kugelaudio.com/integrations/elevenlabs-proxy.md
- https://docs.kugelaudio.com/prompting/overview.md · breaks · spell · speed · pronunciation
- https://docs.kugelaudio.com/features/text-processing.md
