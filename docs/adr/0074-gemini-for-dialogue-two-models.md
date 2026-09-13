# ADR 0074: Dialogue Generation May Run on Gemini, Under One Switch and on Two Models

## Status

Accepted (reverses ADR 0040's removal of the Gemini path; narrows ADR 0011 to STT)

## Context

ADR 0011 put STT and dialogue generation on the university-hosted DiReKT gateway, and ADR 0040 removed an undocumented `LLM_BACKEND=gemini` escape hatch as dead configuration that had never been adopted — noting that reintroducing an alternate LLM backend "would need to be designed fresh rather than resurrected from this env toggle."

Since then the gateway's model choice has collapsed. `docs/research/model-parameters.md` records that only `Qwen3-4B-AWQ` is still served: `DeepSeek-V4-Flash-0731`, `GLM-5.2-NVFP4` and `Kimi-K2.7-Code` return `403 model use not permitted` since a Hetzner trial phase ended, and the gateway operators have not restored them. A 4-billion-parameter model is now the binding limit on quality, and a long list of workarounds exists only because of it: the call-state notes that replace the history (ADR 0071), the repetition guards (ADR 0038), the regex closing-intent detection (ADR 0037), the settlement check (ADR 0073). Each was written against a transcript in which that model did the wrong thing.

Two properties of the alternatives shaped what follows. First, a large hosted model is not uniformly better here: measured on 2026-09-08, `gemini-3.8-flash` takes 2.98 s to its first token at `low` thinking and defaults to `medium`, while `gemini-3.5-flash-lite` at `minimal` answers in 0.70 s. Three seconds of silence before the persona speaks is not a phone call, and latency is the stated priority for the live path. Second, free-tier quotas are counted in requests per minute, and a live Turn costs two of them (the reply plus the call-state notes) against one for a whole finished Session.

## Decision

One boolean, `GEMINI`, moves dialogue generation to Google's OpenAI-compatible endpoint. Off — the default — every request is byte-for-byte what was measured against the gateway. STT and TTS never follow it: they stay on the gateway and KugelAudio, so the switch moves one leg and not the pipeline.

With it on, two models are used, not one. `GEMINI_LIVE_MODEL` (default `gemini-3.5-flash-lite`, at `GEMINI_REASONING_EFFORT` = `minimal`) generates the spoken reply and the call-state notes — everything on the call's clock. `GEMINI_FEEDBACK_MODEL` (default `gemini-3.5-flash`) writes the wrap-up (ADR 0049), the follow-up draft (F-60) and the PDF summary (F-58) — everything where nothing is waiting. The default is not the strongest model on offer: `gemini-3.8-flash` is capped at 20 requests on the free tier, which a handful of finished Sessions exhausts, and a wrap-up that 429s is one the User never sees. It is the documented upgrade on a paid key. `backend/clients/llm.py::complete` takes a `live` flag for the one caller that is a completion by shape but not by nature.

`_backend_kwargs` is the single place that knows the two backends differ. Qwen3's thinking switch travels in `chat_template_kwargs`, a vLLM passthrough; Gemini takes `reasoning_effort` instead and silently ignores what it does not know, so sending the vLLM form would leave thinking on rather than fail. `top_k`/`min_p` are dropped for Gemini for the same reason, and `presence_penalty` is withheld because Gemini honours it and Qwen3's recommended 1.5 is a dose meant for a 4B model that repeats paragraphs (ADR 0038).

This remains outside what ADR 0017 declined. There is no registry, no runtime selection and no fallback: one boolean, read once at import.

## Consequences

The quality ceiling moves, and the workarounds built under it become re-examinable rather than permanent. ADR 0071's call-state notes are the first candidate: they exist because a 4B model lost the thread after three exchanges, they cost one background request per exchange, and they hand the model a summary in place of the conversation — on a model that reads its own history well, that is a loss twice over. That first candidate has since been acted on in ADR 0075. The rest are not removed on the strength of this ADR, and no switch is left behind to invite it: each guard has to be retired against transcripts of its own, in a change that also moves its tests.

The cost is a second vendor on the dialogue leg, with the consequences ADR 0066 tracks: the user's transcript reaches Google, which is a processor the privacy statement does not name. **Switching `GEMINI` on in a deployment that stores real Sessions requires that statement to be updated and the DPO review to cover it.** The switch is safe for development against dev users; it is not, by itself, a decision that the pilot may use it.

Two failure modes are specific enough to name. A thinking level below what the live model supports is `HTTP 400 INVALID_ARGUMENT`, whose message names no parameter — it surfaces as a Turn that fails for no visible reason, which is why the level and the model are set together and logged with every request. And the free tier meters per model and per minute, while a Turn spends two requests — the spoken reply and the call-state notes. Retiring the notes halves that, which ADR 0075 does.
