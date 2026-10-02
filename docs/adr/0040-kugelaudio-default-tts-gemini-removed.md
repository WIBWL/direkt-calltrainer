# ADR 0040: TTS Defaults to KugelAudio with a DiReKT Fallback; Gemini Removed

## Status

Accepted (partially supersedes ADR 0021's TTS half — see below)

**Status update (ADR 0103):** both halves of this ADR have since been
undone, in opposite directions. The DiReKT fallback and the flag that forced it
— `DEBUG`, renamed `SKIP_KUGELAUDIO` along the way — are **gone**: KugelAudio is
the only speech output, and a failure ends the Turn instead of being answered
in another voice, because the fallback hid the outage it was meant to survive
(a pilot ran all day in the slower voice with a green boot log). The Gemini
removal decided below was reversed by ADR 0074 and then decided again, for
good, by ADR 0103. What survives from this ADR is the reasoning for KugelAudio
being the voice at all.

## Context

TTS previously toggled between the DiReKT gateway's Voxtral model and KugelAudio via a static `TTS_BACKEND` env var — an either-or choice made once at deploy time, with no runtime fallback if the chosen backend failed. Separately, an undocumented `LLM_BACKEND=gemini` escape hatch let dialogue generation run against Google Gemini's OpenAI-compatible endpoint instead of DiReKT; it was never the default and, in practice, was never adopted.

## Decision

KugelAudio is now the TTS default, tried on every synthesis call; a failure (`KugelAudioError`, timeout, or connection error) falls back automatically to the DiReKT gateway's TTS model for that call, and a `DEBUG` flag forces the DiReKT fallback unconditionally (e.g. for local development without KugelAudio credentials). STT and dialogue generation keep exactly one backend each, with no fallback — ADR 0017 still holds, this is not a general provider-abstraction layer, just one hardcoded try/fallback specific to TTS. The Gemini escape hatch is removed entirely, along with its config and env vars.

## Consequences

Losing KugelAudio no longer silently breaks every call in production — TTS keeps working via the fallback, at the cost of a brief failed request before falling back on each affected call while the outage lasts, and of needing both providers' credentials configured simultaneously (KugelAudio unless `DEBUG` is set). Removing Gemini deletes dead configuration surface that was never exercised in practice; reintroducing an alternate LLM backend would need to be designed fresh rather than resurrected from this env toggle. This makes ADR 0021's description of TTS as a "separately self-hosted local model" stale — TTS is now primarily a third-party hosted API (KugelAudio), with the DiReKT model retained only as its fallback.
