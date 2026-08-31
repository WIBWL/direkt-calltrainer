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

No network access, credentials, database or browser is needed: the three
pipeline backends (STT / LLM / TTS) are faked (`tests/conftest.py`), and the
REST layer is driven through an in-process ASGI transport. Dummy env vars are
set in `conftest.py` before any backend module is imported.

## Traceability matrix

| Area | Feature / ADR | Test file |
|---|---|---|
| Setup screen: persona/scenario REST endpoints | F-43, F-44, F-15, F-01/03/04, ADR 0001, ADR 0006/0022 | `test_setup_api.py` |
| Persona & scenario libraries (data) | F-01, F-03, F-04, R-07, R-08, R-09, R-10, ADR 0006, ADR 0022 | `test_persona_scenario_library.py` |
| Counterpart behaviour (LLM system prompt) | F-01, F-03, F-04, F-12, R-12, ADR 0006, ADR 0033/0037/0038 | `test_system_prompt.py` |
| Live session loop & state model | F-46, F-01, F-12, F-52, R-52, ADR 0033 | `test_session_pipeline.py` |
| Streaming TTS chunking | ADR 0033 | `test_chunking.py` |
| Closing-intent detection | ADR 0037, F-01 | `test_closing_intent.py` |
| Repetition guard + guaranteed sign-off | ADR 0038 | `test_repetition_guard.py` |
| `[CALL_END]` marker + foreign-script scrub | ADR 0033 | `test_call_end_marker.py` |
| Barge-in / eager interruption | ADR 0035 | `test_barge_in.py` |
| Pipeline fault tolerance (retry → graceful end) | ADR 0016, ADR 0033 | `test_pipeline_failure.py` |
| TTS backend selection & fallback | ADR 0040 | `test_tts_fallback.py` |
| WebSocket wire protocol & handshake | F-46, ADR 0033, ADR 0035 | `test_websocket_protocol.py` |
| Centralized / per-session logging | ADR 0039 | `test_logging.py` |
| Persistence schema (ORM metadata) | ADR 0025/0026/0029/0030/0032, F-09, F-12, F-14 | `test_persistence_schema.py` |
| Documented gaps (current-state guards) | ADR 0034, F-09/10, F-13/48, F-53, F-56, ADR 0018/0019 | `test_documented_gaps.py` |

## Not covered here

* **Paraverbal analysis** (F-35–F-38, F-40, F-51, F-24, dashboard F-53) and
  **AI feedback** (F-09, F-10) — not implemented yet (ADR 0018/0019 worker is
  unbuilt). `test_documented_gaps.py` guards their absence so this suite flags
  the day they land.
* **Frontend** (React hooks, in-browser Silero VAD / ADR 0036, streamed audio
  playback) — no JS test runner is configured. VAD confirmed-speech filtering
  is a browser-only concern.
* **Real backend connectivity** — `scripts/check_backends.py` already does a
  live OK/FAIL probe against the configured STT/LLM/TTS models.
