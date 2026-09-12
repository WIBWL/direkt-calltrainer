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
`test_session_history.py`, `test_focus_goals.py`, `test_pressure_segments.py`,
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
| Storage consent: the gate on the write path, version staleness, withdrawal deletes | F-49, F-31, ADR 0031, ADR 0034, ADR 0066 | `test_consent.py` |
| Six-month retention: the boundary, the per-account suspension, idempotence | F-49, ADR 0031, ADR 0066, ADR 0067 | `test_retention.py` |
| Focus goals: the five-goal limit at the backend, "no focus" as a decision, the catalogue, that deleting trainings leaves the selection alone, and the role and call types stored beside it | F-62, ADR 0031, ADR 0041, ADR 0066, ADR 0076 | `test_focus_goals.py` |
| Data rights: overview counts, export completeness and scoping, deleting one training | F-49, F-31, ADR 0050, ADR 0064, ADR 0066 | `test_data_rights.py` |
| Spoken content stays out of the log unless explicitly switched on | F-49, ADR 0039, ADR 0066 | `test_transcript_logging.py` |
| Deep links into the client-side router survive a reload, without swallowing unknown API paths | F-31, ADR 0009, ADR 0064 | `test_spa_routing.py` |
| Setup screen: persona/scenario REST endpoints (+ auth gate, deactivated rows withheld) | F-43, F-44, F-15, F-31, F-50, F-01/03/04, ADR 0001, ADR 0009, ADR 0026, ADR 0041, ADR 0043, ADR 0045, ADR 0058, ADR 0072 | `test_setup_api.py` |
| Session read route: `extern_id`, ownership (404 for foreign and unknown alike), wire shape | F-09, F-12, F-42, ADR 0031, ADR 0034, ADR 0050, ADR 0057 | `test_api.py` |
| Session history: ownership as the query, total order under pagination, what the listing withholds | F-13, F-48, F-31, F-50, ADR 0009, ADR 0031, ADR 0051, ADR 0052, ADR 0057, ADR 0064 | `test_session_history.py` |
| Measurements over the demanding stretches of a call: the per-utterance facts that survive it, the split from the wrap-up's marks, and that the whole-call figures never move | F-62, F-13, ADR 0048, ADR 0051, ADR 0064, ADR 0081 | `test_pressure_segments.py` |
| Session write path: one row plus utterances, one transaction | F-12, ADR 0026, ADR 0034 | `test_save_session.py` |
| Cascade delete: the Session subtree goes, reference data stays, used reference rows are undeletable | ADR 0026, ADR 0034, ADR 0052 | `test_cascade_delete.py` |
| Migration chain in both directions, naming convention, FK indexes | ADR 0027, ADR 0052, ADR 0053 | `test_migrations.py` |
| Seed idempotency and deactivation | ADR 0041 | `test_seed.py` |
| No test reaches the development database | ADR 0034 | `test_database_isolation.py` |
| Persona & scenario library: row mapping + seeded content | F-01, F-03, F-04, R-07..R-10, R-12, ADR 0041, ADR 0043, ADR 0045, ADR 0064 | `test_persona_scenario_library.py` |
| User-authored Scenarios: ownership, tenant visibility, sharing | F-34, F-59, R-58, ADR 0024, ADR 0050, ADR 0058, ADR 0059, ADR 0060, ADR 0064 | `test_authored_content.py` |
| PDF text extraction for an authored Scenario | F-58, ADR 0024, ADR 0058, ADR 0059 | `test_scenario_documents.py` |
| Follow-up Scenario drafted on request from a Session's feedback (the played case and the wrap-up carried forward, what the model is still not given, the route's refusals and idempotency, that it is stored once as the User's own private Scenario, and that it leaves the library when its Session does) | F-60, F-10, ADR 0011, ADR 0031, ADR 0043, ADR 0050, ADR 0051, ADR 0058, ADR 0059, ADR 0066, ADR 0067, ADR 0069, ADR 0070 | `test_followup_scenario.py` |
| Reverse of a finished Session (the row it writes, the briefing, idempotency, the refusals, and what a deletion and the retention sweep take) | F-61, ADR 0043, ADR 0050, ADR 0051, ADR 0059, ADR 0066, ADR 0067, ADR 0070 | `test_reverse.py` |
| Tenant resolution (org claim → e-mail domain → default) | R-58, ADR 0060 | `test_tenants.py` |
| Sanitising authored Scenario text before it reaches the prompt | ADR 0024, ADR 0059 | `test_authored_text.py` |
| Counterpart behaviour (LLM system prompt) | F-01, F-03, F-04, F-12, R-12, ADR 0043, ADR 0045, ADR 0033/0037/0038 | `test_system_prompt.py` |
| The swapped casting a reverse runs under (prompt, opening, call-state notes, settlement check, per-turn anti-repeat nudge) | F-61, ADR 0038, ADR 0043, ADR 0045, ADR 0070, ADR 0071, ADR 0073 | `test_reverse_prompt.py` |
| Live session loop & state model (+ what a Turn's acoustics record) | F-46, F-01, F-12, F-52, R-52, ADR 0033, ADR 0047, ADR 0048 | `test_session_pipeline.py` |
| Streaming TTS chunking | ADR 0033 | `test_chunking.py` |
| Closing-intent detection (both language packs) | ADR 0037, ADR 0043, F-01 | `test_closing_intent.py` |
| A goodbye without the marker ends the call, and its own farewell is not doubled by the fallback line; a reply that only presses does not end it | ADR 0037 (amendment) | `test_call_end_marker.py` |
| Repetition guard, re-introduction regeneration + guaranteed sign-off | ADR 0038, ADR 0043 | `test_repetition_guard.py` |
| `[CALL_END]` marker + foreign-script scrub | ADR 0033 | `test_call_end_marker.py` |
| Barge-in / eager interruption (incl. the note-barge-in ordering contract, a late interrupt over a committed reply's tail, the `[unterbrochen]` transcript marker, and the cut-off dash + one-Turn nudge that keep the model in the conversation afterwards) | ADR 0035 | `test_barge_in.py`, `test_barge_in_ordering.py` |
| The startup backend checks: the wrap-up model is checked at boot when it is a separate model, and not when it is the same one; the check asks the way its callers do | ADR 0016, ADR 0074 | `test_startup_checks.py` |
| The caller's notes and the history window: the model reads notes + the last three exchanges, the guards and the Transcript keep the full record; background refresh, refresh-on-trim, failure keeps stale notes. And the other shape: with the notes off the model is handed the whole conversation and no summarisation request is made | ADR 0071, ADR 0075 | `test_call_state.py` |
| Whisper phantom transcripts ("*Titelm*", "Vielen Dank.") are no Turn | ADR 0071 | `test_stt_phantom.py` |
| Pipeline fault tolerance (retry → graceful end) | ADR 0016, ADR 0033 | `test_pipeline_failure.py` |
| TTS backend selection & fallback | ADR 0040 | `test_tts_fallback.py` |
| A KugelAudio stream left before `final` drops the pooled socket and re-warms; the orchestrator closes an abandoned stream at once (the one-chunk audio offset after a barge-in) | ADR 0044 (amendment) | `test_tts_stream_reset.py` |
| What the TTS backend is handed (German thousands separator + ordinals) | ADR 0033, ADR 0044 | `test_speech_text.py` |
| WebSocket wire protocol & handshake (+ token in `session.start`) | F-46, F-50, ADR 0009, ADR 0033, ADR 0035 | `test_websocket_protocol.py` |
| Centralized logging (session-tagged, kept for the whole run) | ADR 0039, ADR 0055 | `test_logging.py` |
| Persistence schema (ORM metadata) and the invariants the database enforces (unique measurement/turn) | ADR 0025/0026/0029/0032/0051/0053, F-09, F-12, F-14 | `test_persistence_schema.py` |
| Session statistics: what each metric divides by, and what suppresses it | F-08, F-24, F-35, F-36, F-41, F-51, F-53, F-63, F-65, ADR 0047, ADR 0048, ADR 0051, ADR 0082, ADR 0083, ADR 0085, ADR 0086, ADR 0089 | `test_metrics.py` |
| Praat measurement against synthetic waveforms: the pitch curve's grid, its unit, and what is refused rather than guessed | F-35, F-37, F-51, ADR 0047, ADR 0048 | `test_acoustics.py` |
| Pitch contour factors: range vs movement, terminal contours per utterance, development across the call, what is refused, the five-step reading and the seams between the user's turns | F-35, ADR 0004, ADR 0051 | `test_intonation.py` |
| Overlapping speech: the rule order that keeps a backchannel from counting, terminal overlap, hard vs soft, and the provisional traffic light | F-51, ADR 0035, ADR 0036, ADR 0051 | `test_interruptions.py` |
| Scenario suggestions: call types and focus goals steer them, voice goals do not, a suggested Scenario keeps its own origin, and the offers after a call | F-62, F-64, ADR 0072, ADR 0076, ADR 0087 | `test_recommendations.py` |
| Hesitation sounds read off the pitch contour: a held flat stretch counts, running speech and short vowels do not, and a failed measurement suppresses the figure | F-51, ADR 0048, ADR 0084 | `test_hesitations.py` |
| Async wrap-up job status (queued → running → done/failed), and every path that can strand it | F-09, F-10, ADR 0019, ADR 0032, ADR 0034, ADR 0050 | `test_feedback_job_status.py` |
| Wrap-up prompt & phase block (F-42), and the thinking-mode call it is asked with | F-09, F-42, F-43, ADR 0004, ADR 0011, ADR 0043, ADR 0049, ADR 0051, ADR 0056 | `test_wrapup_prompt.py` |
| Documented gaps (current-state guards) | F-56 | `test_documented_gaps.py` |
| The live call may not depend on the analysis of a finished one: no `backend.feedback` import but `acoustics`, and no ORM | ADR 0033, ADR 0034, ADR 0049 | `test_module_dependencies.py` |

## Not covered here

* **The post-call wrap-up** (F-10) — implemented in `backend/feedback/`
  (ADR 0047–0051). Only the prompt is covered (`test_wrapup_prompt.py`, its job
  status in `test_feedback_job_status.py`, and the wire round trip in
  `test_api.py`); the generated text itself is not asserted, since it is model
  output. `metrics.py` is covered by `test_metrics.py` and `acoustics.py` by
  `test_acoustics.py` since the pitch curve was added.
* **Frontend** (React hooks, in-browser Silero VAD / ADR 0036, streamed audio
  playback) — no JS test runner is configured. VAD confirmed-speech filtering
  is a browser-only concern.
* **Real backend connectivity** — `scripts/check_backends.py` already does a
  live OK/FAIL probe against the configured STT/LLM/TTS models.
* **Whether the model actually follows the frame** — every prompt test here
  asserts the *text handed to* the model. That the model then behaves (uses
  the case, raises an objection once, ends at the right moment) is only
  observable in real calls.
