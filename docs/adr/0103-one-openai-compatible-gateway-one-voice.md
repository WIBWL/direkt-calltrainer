# ADR 0103: One OpenAI-Compatible Gateway, One Voice, and No Switches Between Them

## Status

Accepted (supersedes ADR 0074; amends ADR 0040 and ADR 0075; restores ADR 0011 to both model legs). **Amended on 2026-10-02** — see the amendment at the end: the post-call texts no longer run in thinking mode.

## Context

Three switches had accumulated in `backend/clients/config.py`, each moving one leg of the pipeline to a second backend:

* `GEMINI` (ADR 0074) moved dialogue generation to Google's OpenAI-compatible endpoint, with five further variables behind it — a URL, a key, a live model, a feedback model and a thinking level — and a second request shape in `llm._backend_kwargs`.
* `SKIP_KUGELAUDIO` (ADR 0040) moved speech output to the gateway's own TTS model, which was also KugelAudio's automatic fallback on any failure.
* `CALL_STATE_NOTES` in the orchestrator was `not GEMINI`: the caller's notes (ADR 0071) are a compression written for a model that cannot read its own transcript, so ADR 0075 switched them off on the backend that can.

Each was defensible where it was written, and together they cost more than they bought. The configuration surface was eleven variables to describe two backends. Every request shape existed twice, and the second one was exercised by a `.env` line rather than by a test — `tests/conftest.py` had to *assign* `GEMINI=""` to stop a developer's own environment deciding which half of the code the suite covered. The privacy statement names the gateway and KugelAudio and nobody else, so the Gemini path was never usable where real Sessions are stored (ADR 0074 says so under its own consequences, and that precondition was never met). And the TTS fallback actively hid the failure it was there to survive: a dead KugelAudio produced a working call in a different voice, 2–3× slower, with a green boot log — which is what ADR 0044's amendment and the boot check's `_check_tts` had each already worked around.

## Decision

One backend per leg, named in `.env`, with no alternative and no switch.

**STT and dialogue generation** run on the OpenAI-compatible endpoint `DIREKT_URL` names, with `STT_MODEL` and `LLM_MODEL` as the two model names. Pointing them at a different gateway is an `.env` edit — the API is the contract, not the vendor — but it is not a second code path: there is one client, one set of sampling parameters, one request shape. `LLM_MODEL` is now the model for the spoken reply *and* for everything written after the call. The two-model split ADR 0074 introduced goes with it; it existed because one vendor metered requests per model and per minute, and `.env.example` already shipped the same name for both, so the split was not in force in practice either.

**Speech output** runs on KugelAudio and nothing else. A failure raises `KugelAudioError` and ends the Turn, which is the answer the caller already handles (ADR 0033). `tts._synthesize` and `synthesize`'s fallback branch are gone, and with them the boot check's reason for reaching into a private function to make sure it was really KugelAudio that answered.

**The caller's notes are always kept.** With no second backend there is nothing for `CALL_STATE_NOTES` to select, and what it selected against is the gateway's 4B model, which is the one still in service.

**The Persona's voice is one column.** `persona.tts_voice` held the retired backend's voice name and is dropped (migration `b3f07c5a91d4`); `kugelaudio_voice_id` is the whole of it. It stays nullable, because a Persona without a voice is one that has not been finished, and `active` is what says so.

`GEMINI`, `GEMINI_API_KEY`, `GEMINI_URL`, `GEMINI_LIVE_MODEL`, `GEMINI_REASONING_EFFORT`, `GEMINI_FEEDBACK_MODEL`, `SKIP_KUGELAUDIO` and `TTS_MODEL` are removed from `.env`, `.env.example` and the code. So is the duplicated `VITE_OIDC_ISSUER`: the SPA now reads the backend's own `OIDC_ISSUER` and `OIDC_CLIENT_ID` through a widened `envPrefix` in `frontend/vite.config.ts`, because one value under two names is a pair that can disagree, and the way it disagrees is every request answering 401.

## Consequences

The quality ceiling is the gateway's again, and `docs/research/model-parameters.md` still records that it serves nothing but `Qwen3-4B-AWQ`. Every guard written against that model — the call-state notes (ADR 0071), the repetition guards (ADR 0038), the closing-intent regexes (ADR 0037), the settlement check (ADR 0073) — is load-bearing rather than re-examinable, which is the state ADR 0074 set out to change. Reopening that is a decision about a *deployment*, and what it needs first is the same thing it needed before: the privacy statement naming the processor, and the DPO review covering it. Reintroducing it as a switch is exactly what this ADR declines; the endpoint and the model name are in `.env`, and a second vendor on the dialogue leg means pointing them there, once, deliberately, for everybody on that deployment.

Losing KugelAudio now breaks calls instead of degrading them quietly. That is the point: the boot check says `TTS FAILED (kugel-3)`, `scripts/check_backends.py` exits non-zero, and a Turn that cannot be synthesised ends as `tts_failed` rather than being spoken in a voice the User did not choose. The operational cost is real and is accepted — the alternative was a pilot that ran all day in the fallback voice without anyone noticing, which is what happened.

`ADR 0017` still holds and is no longer strained: there is no provider abstraction, no registry, no runtime selection, and now no boolean either.

## Status update (September 2026)

`OIDC_CLIENT_ID` is gone from `.env` again: the client is named `calltrainer-frontend` in every realm, so the SPA carries it as a constant in `frontend/src/oidcConfig.ts`. Only `OIDC_ISSUER` is still read through the widened `envPrefix`. The model names stay in `.env` as decided above.

## Amendment, 2026-10-02: nothing written after the call runs in thinking mode

"One set of sampling parameters, one request shape" held, and that was the problem: the shape was Qwen3-4B's, and the name in `.env` became `gemma-4-26B-A4B-it` once the gateway stopped serving Qwen3 to the project's key. The Consequences above say the gateway "serves nothing but `Qwen3-4B-AWQ`"; that is no longer so, and what follows is what the first other model did with a request nobody had re-measured.

ADR 0011 put the post-call texts in thinking mode because a 4B model writing German from an English brief needed the revision pass, and time is free in the worker. On Gemma the pass is 6 500 to 10 000 tokens long. The wrap-up's budget is 4 000 (`llm._MAX_FEEDBACK_TOKENS`), so both attempts ended inside the trace with nothing after it, the fallback was stored, and four of the first five calls on the new model got a wrap-up with no points — after 2:35 min each in a queue that runs one job at a time. The follow-up draft and the reverse briefing carry no cap and did finish, in 160 and 185 seconds, behind a button somebody is watching.

**Decided:** the wrap-up, the follow-up draft, the reverse briefing and the PDF fact list are all asked with thinking off. Each then answers in 10 to 14 seconds with JSON that validates. `llm.complete` keeps its `think` parameter and `_strip_reasoning` — a model that needs the pass may come back — but no caller passes it, and four tests that pinned thinking mode now pin its absence. The live reply is untouched; it never thought.

**Rejected: a larger cap.** The model's context is 16 384 tokens and the wrap-up prompt for a 21-Turn call is 5 056 of them. The one thinking run that completed used 15 705 and took up to 246 s against a 240 s request timeout. A longer call would fail on the window or on the clock, so the cap that fits today's call is the bug again next week.

**What it costs** is whatever the trace bought, and that is only partly known: the thinking run named two improvement points where the other named one, and the German was not compared at all. The measurements, and the list of what they do not show, are the 2026-10-02 addendum in `docs/research/model-parameters.md`. The general lesson is the one the Consequences already drew and this ADR then walked into: the request shape belongs to the model, so a changed `LLM_MODEL` is a change to measure, not an `.env` edit.
