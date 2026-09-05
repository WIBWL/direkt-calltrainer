# Model & Parameter Tuning — STT, LLM, TTS

Investigation into the concrete models behind the Session pipeline: which
parameters to set and to what values, backed by live measurements against the
real endpoints (not the mock).

**Date of measurements:** 2026‑08‑31, over VPN into the gateway's network
(the `llm.efre-direkt.de` LiteLLM gateway and the KugelAudio API were both
reachable). All latency figures are wall‑clock round trips from this machine;
absolute numbers will be lower on the deployment server, but the *relative*
comparisons hold.

**Priority: latency.** Perceived speed is the top objective. Where a choice
trades quality for latency, latency wins; where it is neutral, quality
improvements are taken for free.

---

## Changes applied 2026‑08‑31

| File | Change | Why |
|---|---|---|
| `.env` / `.env.example` | `KUGELAUDIO_MODEL`: `kugel-2-turbo` → `kugel-3` | Measured (n=12): `kugel-3` matches turbo on time‑to‑first‑audio and is **faster on full synthesis** (839 ms vs 890 ms first chunk, 1136 ms vs 1356 ms mid). `kugel-2-turbo` is a deprecated id (`ka.models.list()` returns only `kugel-3`). The "turbo is faster" intuition does not hold here. |
| `backend/clients/tts.py` + `backend/session/orchestrator.py` | **New `synthesize_stream`** — `stream_async` per sentence chunk, **each `AudioChunk` forwarded to the client as it arrives** instead of buffering the chunk into one WAV. The one‑chunk‑deep `asyncio.Task` pipeline (`_drain_if_pending`) is removed. Full write‑up: **ADR 0044**. | First‑audio for a Turn's first chunk: **~0.9 s → ~0.28 s** (p50, measured). End‑to‑end (STT + LLM + TTS) a Turn's first audio went **~1.5 s → ~1.0 s** in live testing. A persistent `streaming_session` was measured *slower* (~1.1 s) with this SDK — see ADR 0044. |
| `backend/clients/config.py` | `KugelAudio(..., region="eu")` | Pins to `api.eu.kugelaudio.com`; the EU endpoint is used because the app is deployed in the EU (ADR 0020). Region-to-region RTT was not measured. |
| `backend/app.py` | `await tts.prewarm()` in `lifespan` | `connect_async()` pools the `stream_async` WebSocket at startup — removes ~300–600 ms of cold start from the **first** Turn of the process. Best‑effort, no‑op under `DEBUG`. |
| `backend/clients/llm.py` | `temperature 0.7, top_p 0.8, presence_penalty 1.5, top_k 20, min_p 0`; `max_tokens 250 → 180` | Qwen3's documented non‑thinking sampling. Latency‑neutral on the forward pass, but tighter sampling produced **shorter, more on‑task replies** — fewer tokens to generate and synthesise. `frequency_penalty 0.5` was the weakest anti‑repetition option tested. |
| `backend/session/chunking.py` | First chunk flushed at the first sentence end past a **25‑char** floor (later chunks keep the 80‑char minimum) | The first chunk sets the whole Turn's perceived latency. A ~40‑char opening sentence reaches TTS ~0.2–0.3 s sooner than waiting for an 80‑char buffer, and the LLM produces 40 chars before 80. The floor still stops a bare "Ja." / "Guten Tag." firing its own TTS call. |
| `backend/session/orchestrator.py` | `_OPENING_INSTRUCTION` example `"Hi, this is…"` → `"Guten Tag, hier ist…"` | With the English example the model opened the call in English **8/8**; German example → **0/8**. (Quality, not latency — but free and low‑risk.) |

All the big TTS latency wins are now in (ADR 0044). What remains
([Open items](#open-items)) is smaller: the persona "write for speech" prompt
block, the STT silence guard, and — only if load ever demands it — revisiting
the persistent‑session path.

---

## TL;DR

The **model choice is not open** — only three of the models the gateway lists
are still served (see [Available models](#available-models)), so this is a
parameter‑tuning exercise, not a model bake‑off.

| Leg | Model (fixed) | Biggest finding | Recommended change |
|---|---|---|---|
| LLM | `Qwen3-4B-AWQ` (only option) | `enable_thinking:false` is already set and is **essential** (without it: 3.2 s to first token and an empty reply). Sampling params were **unset** → the server ran at `temperature 1.0 / top_p 1.0`, looser than Qwen3's own recommendation, producing longer/driftier replies. | ✅ `temperature 0.7, top_p 0.8, top_k 20, min_p 0`, `presence_penalty 1.5` (replaces `frequency_penalty`), `max_tokens 180`. ✅ German opener example. ⬜ a larger model (e.g. `DeepSeek-V4-Flash`, if served again) would fix what prompt+params can't. |
| STT | `whisper-large-v3-turbo` (only option) | Fast (~0.8 s, RTF ≪ 1). `language`, `temperature`, `prompt`, `response_format` do **nothing useful or actively harm**. Hallucinates a fixed phrase on silence; drops spoken numbers. | ✅ No change (already correct — `json`, `language="de"`, no `prompt`). ⬜ Silence/hallucination guard. |
| TTS | KugelAudio `kugel-3` + `Voxtral-4B-TTS-2603` (fallback) | "turbo is faster" is **false** — `kugel-3` matches `kugel-2-turbo` on first‑audio and beats it on full synthesis (n=12). The old batch call cost **~0.9 s to first audio**. Voxtral fallback is ~2–3× slower than KugelAudio. | ✅ `kugel-3`, `region="eu"`, `prewarm()`, early first chunk. ✅ **`synthesize_stream` forwards each `AudioChunk` — first audio ~0.9 s → ~0.28 s** (ADR 0044). Persistent `streaming_session` measured *slower* with this SDK. |

---

## Method

* Each configuration was called **N = 2–12 times** against the live endpoint;
  latency is reported as p50 (and mean ± σ where useful), not single shots.
* The LLM was driven with the **real system prompt**
  (`backend.session.orchestrator._build_system_prompt(PERSONAS[0], SCENARIOS[0])`,
  ≈ 1.5 k tokens) and realistic mid‑call German user turns, streamed, measuring
  time‑to‑first‑token (TTFT) and total time.
* Quality was scored heuristically per reply: language (German vs
  code‑switching), length, `<think>` leakage, spurious `[CALL_END]`, and
  sentence repetition.
* STT was driven with `test/sample.wav` (12.1 s of German TTS speech) plus
  synthesised silence/noise and truncated clips.
* TTS was measured for a typical chunk from the app's chunker
  (`backend/session/chunking.py`, 80–250 chars) and for a one‑word chunk.
* Scripts live in the scratchpad, not the repo; this document is the artefact.

---

## Available models

`GET https://llm.efre-direkt.de/v1/models` returns six ids:

```
Kimi-K2.7-Code   whisper-large-v3-turbo   Voxtral-4B-TTS-2603
GLM-5.2-NVFP4    DeepSeek-V4-Flash-0731   Qwen3-4B-AWQ
```

…but only three are still served. `DeepSeek-V4-Flash-0731`, `GLM-5.2-NVFP4` and
`Kimi-K2.7-Code` all return:

```
HTTP 403  {'error': 'model use not permitted'}
```

These larger models were available for free during a Hetzner trial phase that
has since ended; `test/sample_benchmark_results.txt` (2026‑08‑09) shows Kimi and
DeepSeek working then. They still appear in `/v1/models` but the backends are
gone, so this is not a transient error. The gateway is a **LiteLLM proxy** in
front of vLLM; the key is restricted to `llm_api_routes` only (no `/health`,
`/version`).

**Consequence:** dialogue generation is locked to `Qwen3-4B-AWQ`, a 4‑billion‑
parameter model. Several quality issues below (weak instruction‑following on the
`[CALL_END]` protocol, occasional code‑switching) are inherent to a model that
small and would most likely be fixed by `DeepSeek-V4-Flash-0731` at `low`
reasoning effort. **If a larger model becomes available again, moving dialogue
generation onto it is the single highest‑leverage change available.** Everything
else here is making the most of Qwen3‑4B.

---

## LLM — `Qwen3-4B-AWQ`

### Current call (`backend/clients/llm.py`)

```python
LLM_CLIENT.chat.completions.create(
    model=LLM_MODEL, messages=messages, stream=True,
    max_tokens=250,
    frequency_penalty=0.5,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
```

Everything not listed falls back to **vLLM defaults**: `temperature 1.0`,
`top_p 1.0`, `top_k 0` (off), `min_p 0`, `presence_penalty 0`,
`repetition_penalty 1.0`.

### `enable_thinking: false` — mandatory, keep it

| Config | TTFT | Visible reply |
|---|---|---|
| `enable_thinking: false` (current) | **0.09 s** (warm), 0.45 s cold | full German reply, 15–45 words |
| no toggle (thinking on) | **3.16 s** | **empty** — the whole 250‑token budget is spent on English `reasoning_content`, which the streaming `delta.content` never surfaces |

Qwen3 thinking mode is catastrophic here: multi‑second first‑token latency and
no usable output within any sane token budget. The current code is right; this
note is so nobody "cleans up" the `extra_body`.

**Where thinking *is* used:** `llm.complete(think=True)` for the PDF fact
extraction (F‑58, `backend/documents.py`). That call is off the live path — the
user is waiting on a spinner in the Scenario editor, not on audio — and it is
not streamed, so neither failure mode above applies. It sets **no `max_tokens`**
(the fact list is bounded by a character cap, and the reasoning trace needs
unpredictable room); the answer is validated as a whole, and if the document is
too large to fit the context the gateway 400s and the caller falls back to the
raw text. Sampling follows Qwen3's thinking‑mode card: `temperature 0.6,
top_p 0.95, top_k 20, min_p 0`. The wrap‑up generator deliberately stays
non‑thinking (its own tuning, ADR 0056).

### Sampling parameters

Qwen3's model card gives explicit **non‑thinking** recommendations:
`Temperature = 0.7, TopP = 0.8, TopK = 20, MinP = 0`, and *"DO NOT use greedy
decoding"*. The app currently sets none of these, so it runs at `1.0 / 1.0`.

Observed effect of tightening to the recommended values:

* **Opening line, language:** with a tighter distribution the opener is more
  consistently German and on‑format (see the prompt fix below — the dominant
  factor there is the prompt, not sampling).
* **Persona consistency:** at `temperature 0.3` replies became near‑identical
  across runs (verbatim repeats between independent sessions) — too flat for a
  training partner. `0.7` keeps variety while staying focused. `1.0` (today's
  value) drifts: on an ambiguous turn only **3/8** replies stayed on task vs
  **8/8** at `0.7`.

**Recommendation:** `temperature 0.7, top_p 0.8`, and `top_k 20, min_p 0` via
`extra_body`.

### Repetition control — `presence_penalty`, not `frequency_penalty`

ADR 0038 documents degenerate repetition (the model repeating its previous
reply, or a sentence within a reply). The current mitigation is
`frequency_penalty 0.5`. Qwen3's card instead recommends **`presence_penalty`
0–2** (*"If you encounter significant endless repetitions, set the
`presence_penalty` to 1.5"*).

Cross‑turn test — persona has already objected "too expensive", user gives a
neutral turn, does the persona re‑raise the same objection?

| Setting | Re‑raises the objection |
|---|---|
| nothing | 0 / 8 |
| `frequency_penalty 0.5` (current) | **3 / 8** |
| `presence_penalty 1.5` | 0 / 8 |
| `repetition_penalty 1.1` (`extra_body`) | 1 / 8 |
| `presence_penalty 1.0` + `frequency_penalty 0.3` | 0 / 8 |

`frequency_penalty 0.5` alone was the **weakest** option in this test. Note
`presence_penalty 1.5` occasionally pulls system‑prompt phrasing into the reply
("Ich habe einen konkreten Grund für diesen Anruf" — a paraphrase of the
`behavior` text); `1.0` is a safer default.

**Recommendation:** replace `frequency_penalty 0.5` with `presence_penalty 1.5`
(matches the card), or `presence_penalty 1.0` if the system‑prompt‑echo effect
shows up in practice. Keep the in‑code repetition guard (ADR 0038) regardless —
sampling reduces the rate, it does not eliminate it.

> **Follow‑up (2026‑09‑03).** The 0/8 above was a single cross‑turn objection
> probe. In longer stalling calls `presence_penalty 1.5` does **not** stop the
> model re‑emitting a whole paragraph verbatim once the conversation has
> nothing new in it (reproduced live, ~4‑in‑7 stalling turns), and it does not
> stop the persona re‑reading its own introduction on turn 1–2. Fixed in the
> ADR 0038 amendment — prompt block + a per‑turn nudge quoting the persona's
> last reply + regenerate‑before‑speaking for a re‑greeting — not by a
> parameter change. The sampling values here are unchanged and still correct.

### `max_tokens`

`250` is fine. It is a **safety cap, not a target** — normal replies use
15–45 words (≈ 20–60 tokens); the cap is only hit on the rare rambling
"frustrated" turn, where truncation is acceptable. Do **not** lower it to
"encourage" brevity — brevity comes from the prompt, and a low cap just cuts
sentences mid‑word (observed at `max_tokens 120`). Keep it. (vLLM's own default
is `16`, so this parameter must stay set.)

### `seed`

vLLM honours `seed`: same seed → byte‑identical output, different seed →
different. Not wanted in production (variety is the point) but useful for the
test suite and for A/B‑ing prompt changes deterministically.

### Latency

With thinking off, Qwen3‑4B on this gateway is **not a latency concern**:
TTFT ≈ 0.09 s once warm, full short reply in 0.4–1.0 s. The first request after
a cold start pays ≈ 0.4 s to prefill the long system prompt, then the prefix is
cached server‑side.

### Known issues that are **prompt**, not parameter, problems

1. **English opener leak.** `_OPENING_INSTRUCTION` contains the literal example
   `e.g. "Hi, this is..."`. Qwen3‑4B copies it: **8/8** openings started with
   "Hi, …" ("Hi, das ist Herr Meier von der Geschäftsführung…"), 3/8 were
   half‑English. Swapping the example to German (`e.g. "Guten Tag, hier ist…"`)
   → **0/8** code‑switching. This aligns with ADR 0043 (language‑keyed prompt
   examples). **Fix the example** — ideally key it by `language_id` like the
   other language‑bound constants.

2. **`[CALL_END]` over‑eagerness.** On an ambiguous "that's clear then, but…"
   turn where the persona should keep pushing, it still appends `[CALL_END]` in
   **~2/8 (temp 0.7)** replies — ending the call while the user is still
   engaged. This is the exact failure ADR 0037 rejected an LLM classifier for,
   now coming from the dialogue model itself. Mitigations tried:
   * lower temperature — helps marginally, costs persona variety;
   * *"ignore `[CALL_END]` if the reply also contains `?`"* — **rejected**:
     4/8 *legitimate* endings also carry a trailing question, so the guard
     breaks more than it fixes.
   No clean fix at this model size. Documented as a known limitation; strongest
   argument for moving to a larger model if one becomes available.

---

## STT — `whisper-large-v3-turbo`

Only STT model available. It is **fast and accurate**; almost every knob is
inert.

### Latency

0.44–0.97 s for anything from 0.3 s to 12 s of audio — RTF far below 1, flat in
input length. **Not a bottleneck.** (The blocking nature of STT per Turn, ADR
0033, stands, but the wait is short.)

### Parameters — what actually does something

| Parameter | Finding | Recommendation |
|---|---|---|
| `language` | `"de"`, unset, and even **`"en"`** produce byte‑identical output and identical latency on clear German audio. vLLM auto‑detects regardless. | Keep `language="de"` — correct intent, harmless, and may matter on borderline audio. |
| `temperature` | `0.0 / 0.2 / 0.5` → identical output. Decoding is effectively greedy. | Leave unset (default 0). |
| `response_format` | `json` works. **`text` is broken** — it returns a JSON *string*, not plain text. `verbose_json` returns segments **but `no_speech_prob` is `null`** (not populated by this build). | Keep the SDK default (`json`). Do **not** rely on `no_speech_prob`. |
| `prompt` | **Actively harmful.** A spelling‑hint prompt turned "Meier" into "Meijer" and dropped the leading "Guten Tag". Matches a known unresolved vLLM bug. | **Never set `prompt`.** |

### Silence / noise → confident hallucination

VAD misfires (ADR 0036) will occasionally send a near‑silent Turn. Whisper does
not return empty — it invents:

| Input | Transcript (3/3 runs) |
|---|---|
| 0.3 s / 0.5 s / 2 s silence | `"Vielen Dank."` |
| 1 s low‑level noise | `"Amen."` |

`"Vielen Dank."` is a mild closing signal — a hallucinated one could nudge the
persona toward ending the call. The only usable signal is weak:
`avg_logprob ≈ -0.34` for the hallucination vs `-0.05…-0.23` for real speech,
and `compression_ratio` `0.62` vs `0.87–0.95`.

**Recommended guard (needs its own small design):** after transcription, treat a
Turn as *empty / no‑op* (return to listening, no persona reply, no history
entry) when the transcript is short **and** low‑confidence — e.g. request
`response_format="verbose_json"` and drop the Turn when
`len(text) < ~15` and `avg_logprob < -0.5`, or maintain a tiny blocklist of the
handful of known hallucination phrases (`"Vielen Dank."`, `"Amen."`,
`"Untertitel…"`, …). Primary defence stays client‑side: the VAD `minSpeechMs`
threshold.

### Numbers get dropped

"…Angebot **über 12.400 Euro** angefragt" transcribed as "…Angebot **über
Euro** angefragt" in *every* configuration — the amount vanishes. Phone numbers
are mangled too ("0931 8765432" → "093318765432"). A turbo‑model weakness, not
tunable. Relevant to the pricing Scenario and to F‑40 (concreteness); worth a
note in the Session summary UI that spoken figures may not survive transcription.

---

## TTS

### KugelAudio (default backend)

Current call: `tts.generate_async(text, model_id="kugel-2-turbo",
voice_id=1885, language="de")` — everything else default (`cfg_scale 2.0`,
`sample_rate 24000`, `speed 1.0`, `normalize True`).

**Voice 1885** is a custom voice literally named *"Thomas Brandt"* — MALE,
CONVERSATIONAL, *"40s, native German, clear, warm, confident, professional"* —
i.e. purpose‑built for the persona. Keep it.

**Model id — "turbo is faster" does not hold.** `ka.models.list()` returns only
**`kugel-3`**; `kugel-2-turbo` still works (legacy ids accepted) but is
deprecated. Full per‑model latency, **n = 12, p50**:

| Model id | stream TTFA (first chunk) | stream TTFA (mid chunk) | stream full synth (first) | stream full synth (mid) | batch total (first) |
|---|---|---|---|---|---|
| **`kugel-3`** | 298 ms | **257 ms** | **839 ms** | **1136 ms** | 852 ms |
| `kugel-2.5` | 319 ms | 305 ms | 1003 ms | 1505 ms | 844 ms |
| `kugel-2-turbo` (was default) | 291 ms | 295 ms | 890 ms | 1356 ms | 910 ms |
| `kugel-2` | 259 ms | 303 ms | 898 ms | 1399 ms | 1118 ms |
| `kugel-1-turbo` | 267 ms | 295 ms | 838 ms | 1204 ms | 896 ms |

Time‑to‑first‑audio is within noise for every model (259–319 ms). On **full
synthesis** — which matters because later chunks queue behind the current one —
`kugel-3` is the fastest of the supported models and clearly beats
`kugel-2-turbo` (‑50 ms first chunk, ‑220 ms mid chunk). `kugel-1-turbo` is
marginally quicker on TTFA but is two generations older.

**Applied:** `KUGELAUDIO_MODEL=kugel-3`.

**`cfg_scale`:** clamped to `[1.2, 2.5]`, default `2.0`. `2.0` was both the
documented sweet spot and the fastest (`1.3` and `2.5` were slower). Leave
default.

**`sample_rate` / `output_format`:** `24000` is native; other rates just add
resampling and don't speed up inference (confirmed — 16 kHz was no faster).
Leave default; the app's PCM16→WAV wrap is fine.

**`speed`:** no latency effect, `1.0` is natural. Leave default.

### KugelAudio: batch vs streaming — the latency win (done, ADR 0044)

| Path (first audio, p50) | latency |
|---|---|
| `generate_async` per chunk (old), first chunk | **0.90 s** |
| `generate_async`, one‑word chunk | 0.65 s |
| `stream_async` per chunk, forwarding each `AudioChunk` | **0.28 s** |
| persistent `streaming_session`, `send()` per sentence + one `flush()` | **1.11 s** |
| `generate_async` per sentence, 3‑sentence turn, realistic LLM gap | 0.81 s |

**Implemented:** `synthesize_stream` — one `stream_async` per sentence chunk,
each `AudioChunk` forwarded straight to the client, over the `prewarm()`‑pooled
connection, `region="eu"`. The one‑chunk‑deep `asyncio.Task` pipeline is gone
(`stream_async` already overlaps generation and playback). First chunk of a
Turn: **~0.9 s → ~0.28 s**; end‑to‑end Turn first‑audio **~1.5 s → ~1.0 s**
live.

**Rejected — persistent `streaming_session`.** KugelAudio's own guidance
("keep one session per Turn, `flush` once, pay the model TTFA once") optimises
*total* Turn time, not first‑audio, and with `kugelaudio==1.9.0` it was
measurably **worse** to first audio (1.11 s): `session.send()` polls ~50 ms for
audio then returns, so with the LLM emitting a sentence every ~200 ms the
server holds synthesis until the closing `flush`, which lands at end‑of‑reply.
`stream_async` per chunk pays N prefills (worse total time, but the audio plays
out over seconds anyway) and each chunk's first audio is ~0.28 s. If a later
SDK delivers audio mid‑`send()`, the persistent path is worth re‑measuring —
the call site is one method.

### Voxtral‑4B‑TTS‑2603 (DiReKT fallback)

| Metric | Voxtral | KugelAudio `kugel-3` |
|---|---|---|
| ~105‑char chunk, total synth | ~3.6 s (RTF ≈ 0.7) | ~1.2 s (RTF ≈ 0.25) |
| one‑word chunk | ~1.1 s | ~0.65 s |
| output | 24 kHz WAV/PCM/MP3 | 24 kHz PCM |

Voxtral is ~2–3× slower per chunk and its latency scales worse with length. It
is a correct *fallback* (ADR 0040) but noticeably degrades the conversational
feel while active — fine as an availability net, not something to switch to.

* Voices: `de_male` (current), `de_female`, `casual_male` work. `male`,
  `formal_male`, `male_1` → **HTTP 500** (invalid voice → server error, not a
  4xx). The hard‑coded `de_male` is safe.
* `response_format`: keep `wav` (the code does). `pcm` returns headerless,
  `mp3` works and is ~5× smaller if bandwidth ever matters.
* `language`: `"de"`, `"German"`, and unset all produce output; keep `"de"`.

---

## What was changed vs. what is still open

All the changes in the table at the top are **applied** and live‑tested. The
TTS streaming rework is written up as **ADR 0044**; the LLM sampling and
opening‑line fixes have no ADR (they're parameter changes).

**STT — no code change, and do not:** add a `prompt` argument, or switch
`response_format` away from `json`.

---

## Open items

1. **Move to `DeepSeek-V4-Flash-0731` if it is served again.** Biggest single
   *quality* lever; would likely resolve the `[CALL_END]` over‑eagerness and
   code‑switching that Qwen3‑4B cannot be prompted out of. Its thinking‑toggle
   is `chat_template_kwargs: {"thinking": false}` / `reasoning_effort: "low"`,
   not Qwen3's `enable_thinking`. Note: `DeepSeek-V4-Flash` at `low` effort was
   as fast as Qwen3 in the 2026‑08‑09 benchmark (`test/sample_benchmark_results.txt`),
   so this is not a speed sacrifice — re‑measure if it comes back.
2. **Persona "write for speech" prompt block.** `_build_system_prompt` has no
   rule against markdown / emoji / stage directions; the dialogue model
   occasionally emits `—`, quotes, `[...]`. Add the KugelAudio prompt block
   (see the `kugelaudio-tts` skill).
3. **STT hallucination guard** — small, self‑contained; decide verbose_json +
   `avg_logprob` threshold vs a phrase blocklist.
5. **Number/figure transcription loss** — no fix; note it in the Session summary
   UI and keep it in mind for the pricing Scenario.

---

## Sources

* [Qwen3‑4B model card — best practices / sampling](https://huggingface.co/Qwen/Qwen3-4B)
* [vLLM `SamplingParams` defaults](https://docs.vllm.ai/en/latest/api/vllm/sampling_params.html)
* [vLLM Speech‑to‑Text API](https://docs.vllm.ai/en/latest/serving/online_serving/speech_to_text/)
* [vLLM issue #35276 — Whisper `prompt` causes hallucination](https://github.com/vllm-project/vllm/issues/35276)
* [DeepSeek‑V4‑Flash — vLLM recipe](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash)
* [GLM‑5.2 — vLLM recipe](https://recipes.vllm.ai/zai-org/GLM-5.2)
* [Voxtral‑4B‑TTS‑2603 — vLLM recipe](https://recipes.vllm.ai/mistralai/Voxtral-4B-TTS-2603) · [model card](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603)
* [KugelAudio docs — models](https://docs.kugelaudio.com/models.md) · [generate params](https://docs.kugelaudio.com/sdks/python/generate) · [streaming & latency](https://docs.kugelaudio.com/streaming/chunking-and-latency.md) · [latency methodology](https://docs.kugelaudio.com/latency.md)
