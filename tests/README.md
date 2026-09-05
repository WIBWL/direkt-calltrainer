# Test suite

Feature-traceable tests for the Calltrainer backend. Every test file names the
`F-xx` features (`docs/features.md`), `R-xx` requirements
(`docs/initial_requirements.md`) and ADRs (`docs/adr/`) it exercises, in its
module docstring and per-test docstrings.

## Running

```bash
pip install -r requirements.txt
pytest
```

Two kinds of test live side by side. Most need no network access, credentials,
database or browser: the three pipeline backends (STT / LLM / TTS) are faked
(`tests/conftest.py`), and the REST layer is driven through an in-process ASGI
transport. Dummy env vars are set in `conftest.py` before any backend module is
imported. Keycloak auth (ADR 0009) is bypassed by an autouse `_override_auth`
fixture that overrides `require_user`; `test_auth.py` verifies the real token
logic against a throwaway RSA key and a stubbed JWKS.

The database tests (`test_migrations.py`, `test_seed.py`, `test_save_session.py`,
`test_cascade_delete.py`, `test_feedback_job_status.py`, `test_api.py`,
`test_setup_api.py`, and the second half of `test_persistence_schema.py`) each
create a throwaway database on the server named in `.env`, migrate it and drop
it afterwards. Postgres has to be running for them (`docker compose up -d db`);
the development database is never touched, and without a reachable server they
skip rather than fail — so look at the skip count, not only at the colour.
`conftest.py` assigns the `POSTGRES_*` names unusable values before the backend
is imported, so a test that does not ask for a database cannot reach the real
one by accident; `test_database_isolation.py` guards that ordering. Inside the
app container this is the only thing standing between the suite and the compose
database, because `env_file` puts the real settings into the environment first.

Personas and Scenarios live in the database since ADR 0041, so the suite owns
its own value objects (`TEST_PERSONAS` / `TEST_SCENARIOS` in `conftest.py`) and
the `fake_library` fixture serves them wherever the code would otherwise read
the database. What the *shipped* library contains is a separate question,
asserted against `scripts/seed_reference_data.py` — which ADR 0041 makes the
source of that content, and which imports without a database.

## Traceability matrix

| Area | Feature / ADR | Test file |
|---|---|---|
| Keycloak bearer-token verification | F-31, F-50, ADR 0009 | `test_auth.py` |
| Setup screen: persona/scenario REST endpoints (+ auth gate, deactivated rows withheld) | F-43, F-44, F-15, F-31, F-50, F-01/03/04, ADR 0001, ADR 0009, ADR 0026, ADR 0041, ADR 0043, ADR 0045 | `test_setup_api.py` |
| Session read route: `extern_id`, ownership (404 for foreign and unknown alike), wire shape | F-09, F-12, F-42, ADR 0031, ADR 0034, ADR 0050, ADR 0057 | `test_api.py` |
| Session write path: one row plus utterances, one transaction | F-12, ADR 0026, ADR 0034 | `test_save_session.py` |
| Cascade delete: the Session subtree goes, reference data stays, used reference rows are undeletable | ADR 0026, ADR 0034, ADR 0052 | `test_cascade_delete.py` |
| Migration chain in both directions, naming convention, FK indexes | ADR 0027, ADR 0052, ADR 0053 | `test_migrations.py` |
| Seed idempotency and deactivation | ADR 0041 | `test_seed.py` |
| No test reaches the development database | ADR 0034 | `test_database_isolation.py` |
| Persona & scenario library: row mapping + seeded content | F-01, F-03, F-04, R-07..R-10, R-12, ADR 0041, ADR 0043, ADR 0045 | `test_persona_scenario_library.py` |
| Counterpart behaviour (LLM system prompt) | F-01, F-03, F-04, F-12, R-12, ADR 0043, ADR 0045, ADR 0033/0037/0038 | `test_system_prompt.py` |
| Live session loop & state model | F-46, F-01, F-12, F-52, R-52, ADR 0033 | `test_session_pipeline.py` |
| Streaming TTS chunking | ADR 0033 | `test_chunking.py` |
| Closing-intent detection (both language packs) | ADR 0037, ADR 0043, F-01 | `test_closing_intent.py` |
| Repetition guard, re-introduction regeneration + guaranteed sign-off | ADR 0038, ADR 0043 | `test_repetition_guard.py` |
| `[CALL_END]` marker + foreign-script scrub | ADR 0033 | `test_call_end_marker.py` |
| Barge-in / eager interruption | ADR 0035 | `test_barge_in.py` |
| Pipeline fault tolerance (retry → graceful end) | ADR 0016, ADR 0033 | `test_pipeline_failure.py` |
| TTS backend selection & fallback | ADR 0040 | `test_tts_fallback.py` |
| WebSocket wire protocol & handshake (+ token in `session.start`) | F-46, F-50, ADR 0009, ADR 0033, ADR 0035 | `test_websocket_protocol.py` |
| Centralized logging (session-tagged, kept for the whole run) | ADR 0039, ADR 0055 | `test_logging.py` |
| Persistence schema (ORM metadata) and the invariants the database enforces (unique measurement/turn) | ADR 0025/0026/0029/0032/0051/0053, F-09, F-12, F-14 | `test_persistence_schema.py` |
| Async wrap-up job status (queued → running → done/failed) | F-09, F-10, ADR 0019, ADR 0032, ADR 0034, ADR 0050 | `test_feedback_job_status.py` |
| Wrap-up prompt & phase block (F-42) | F-09, F-42, ADR 0004, ADR 0049, ADR 0051, ADR 0056 | `test_wrapup_prompt.py` |
| Documented gaps (current-state guards) | F-13/48, F-53, F-56, ADR 0006/0009 | `test_documented_gaps.py` |

## Not covered here

* **Paraverbal measurement and the post-call wrap-up** (F-10, F-37, F-51,
  F-53) — implemented in `backend/feedback/` (ADR 0047–0051). Only the
  wrap-up prompt is covered (`test_wrapup_prompt.py`, its job status in
  `test_feedback_job_status.py`, and the wire round trip in `test_api.py`);
  feature tests for `metrics.py` and `acoustics.py` are still owed. The cross-session dashboard (F-53) is still unbuilt.
* **Frontend** (React hooks, in-browser Silero VAD / ADR 0036, streamed audio
  playback) — no JS test runner is configured. VAD confirmed-speech filtering
  is a browser-only concern.
* **Real backend connectivity** — `scripts/check_backends.py` already does a
  live OK/FAIL probe against the configured STT/LLM/TTS models.
* **Whether the model actually follows the frame** — every prompt test here
  asserts the *text handed to* the model. That the model then behaves (uses
  the case, raises an objection once, ends at the right moment) is only
  observable in real calls.
