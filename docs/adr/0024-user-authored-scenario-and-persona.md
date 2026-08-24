# ADR 0024: User-Authored Scenario Context and Personas (Post-MVP)

## Status

Accepted

## Context

Session setup today means picking from the curated Persona library (ADR 0002) via cards (ADR 0015) and choosing a Scenario, kept to a minimal required flow (ADR 0013). ADR 0005 already anticipates one form of user-driven customization: an optional, Session-scoped document upload for context (F-26, SHOULD; F-45), stored on the external Data Platform — distinct from the ruled-out automatic CRM/domain-knowledge integration (C-05; R-45, R-46).

The product should go further than file upload alone: the user should also be able to type free-text instructions that shape the Scenario directly — how the conversation should unfold, and what opening line or question the simulated counterpart starts with — and to author their own Persona via free-text instructions describing how the AI counterpart should behave, rather than only selecting from the curated library. None of this is needed for the MVP; it targets the roadmap toward the finished product.

## Decision

We will extend Scenario and Persona configuration (ADR 0001) to accept user-authored input, as a post-MVP capability:

- **Scenario**: in addition to uploading files as context (already covered by ADR 0005), the user can enter free-text instructions describing how the conversation should proceed and what opening question the simulated counterpart starts with.
- **Persona**: the user can author a custom Persona via free-text behavior instructions, as an addition to the curated Persona library (ADR 0002), not a replacement for it.

Both remain optional, advanced-tier configuration, kept out of the required minimal setup flow per ADR 0013 — not part of the MVP.

## Consequences

Advanced users gain more control over Session realism and the counterpart's behavior without complicating the minimal MVP setup, since this is deferred beyond MVP. Uploaded files keep routing to the Data Platform; free-text Scenario and Persona input will need storage of its own in the Session schema (ADR 0010), not yet designed. User-authored Personas raise open questions left for a future ADR: whether they appear in the same card-based library UI (ADR 0015) or as a separate "my personas" space, whether they need any moderation or validation before being used as system-prompt content, and how they interact with Language as an independent Session parameter (ADR 0022). Feeding raw user-supplied text (files and free text) toward the LLM as context or persona definition also widens the prompt-injection surface, which needs to be addressed at implementation time.
