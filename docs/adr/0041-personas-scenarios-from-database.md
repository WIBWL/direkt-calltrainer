# ADR 0041: Personas and Scenarios Loaded from the Database

## Status

Accepted

## Context

A Session is configured with one Persona and one Scenario, selected separately per Session (ADR 0001, ADR 0015), and the conversation is built from that pairing on the fly. Today both are hardcoded lists in `backend/personas.py` and `backend/scenarios.py`; the `persona` and `scenario` reference tables from ADR 0026 exist but are only seeded from those modules, so code is the source of truth and the database a downstream copy. That inverts the direction the product needs — the library is meant to grow (ADR 0002), and its content should not require a deployment to change.

## Decision

We will make the `persona` and `scenario` tables the source of truth. `/api/personas` and `/api/scenarios` serve the selection from them, and at Session start the orchestrator loads the two selected rows and assembles the LLM system prompt from them together with the predefined prompt frame that stays in `backend/session/orchestrator.py` — the call rules, the opening instruction, the example exchange, the `[CALL_END]` marker — since that frame does not vary with the selection. Seeding reverses direction accordingly: `scripts/seed_reference_data.py` carries the initial content, and the hardcoded lists go away. `backend/personas.py` and `backend/scenarios.py` remain, reduced to the value types the rest of the backend passes around, so that `backend/session/` keeps depending on those types alone and never on database access.

## Consequences

Personas and Scenarios can be added or reworded without a deployment, and every Session picks up whatever is current at its start. In exchange, the database moves onto the Session's start path: ADR 0034 already requires it at the end of a Session to persist the transcript, but a Session that cannot reach the database can now no longer even begin, and running the app locally requires a migrated and seeded database rather than only a running one. The Persona fields the schema does not carry yet — the Language and the TTS voice, including the KugelAudio voice id that ADR 0040 made the default backend's — need columns of their own before the hardcoded lists can be dropped.
