# CLAUDE.md

Calltrainer: a User takes a simulated call from a Persona in a Scenario, then gets a wrap-up and measured statistics. Domain terms are in `CONTEXT.md`, decisions in `docs/adr/` (each states the current decision; edit it in place, see ADR 0000), and the architecture in `docs/arc42.md`.

@README.md

## Where things live

There is one uv workspace (ADR 0108). `shared` imports neither of the other packages, and `backend` and `worker` never import each other.

- `shared/`: `db/` (models, session, seed data, migrations), `feedback/` (metric inventory `metrics.py`; `acoustics.py`, the only Praat importer; `calls.py`/`stored.py`/`rows.py`, a call into and out of the DB; `segments.py`; `jobs.py`, `queue.py`), `clients/llm.py`, `turn.py`, `language_packs.py`, `env.py` (the only settings reader).
- `backend/`: `app.py`, `api/` (one router per resource; `served.py` builds a stored Session's wire shapes; `_loading.py` does the ownership read), `session/` (the live call), `feedback/readings.py` + `explanations.py`, `clients/` (STT, TTS), domain modules (`library`, `consent`, `deletion`, `retention`, `focus`, `recommendations`, `followups`, `reversals`, `tenants`, `authored_text`, `documents`/`pdf_text`), guards (`limits.py`, `body_limit.py`, `gunicorn_worker.py`), `scripts/`.
- `worker/`: `generator.py` (the wrap-up), `segments.py`.
- `frontend/src/`: `App.tsx`, `trainingFlow.ts` (the pure transition table; `advance` is the only caller of `setScreen`), `protocol.ts` (wire types), one API module per resource (`api.ts` is transport only), `hooks/` (the live call), `utils/` (`metrics.ts` holds a metric's display facts; `reportOutline.ts`/`progressOutline.ts` decide what the pages and PDFs say), one `index.css`.
- Tests sit beside each package. Each test file's docstring names its F-xx/ADR.

## Traps and invariants

Each of these has broken something before, or would break it silently.

- **Consent gates storage** inside the write transaction, under a per-subject advisory lock, and **fails closed** (ADR 0066).
- **Spoken content is never logged** at any level; log lengths instead. `test_transcript_logging.py` pins this.
- **Audio is never stored** (ADR 0048), so a new acoustic metric cannot be backfilled.
- **There are no backups.** Whoever adds them must add a retention policy to ADR 0066 in the same change.
- **Deletion goes through `deletion.remove`** (ADR 0102). The consent log is never deleted (ADR 0068). Say "your trainings are deleted", not "all your data".
- **No figure carries a target, score or judgement** (ADR 0004/0051/0065). Traffic lights must meet ADR 0078's seven conditions. Nothing is measured against the Persona. `loudness` is never compared across calls.
- **Ownership answers 404, never 403** (ADR 0050). The client sees `extern_id`, never a primary key.
- **Model work needs the client role `calltrainer-user`** (403 / `not_admitted`) **and stays under `backend/limits.py`'s caps**, which are counted in the backend's **one** gunicorn process. Routes read them as `limits.X` (ADR 0109).
- FastAPI parses a declared body before auth, so upload routes parse `request.form()` themselves. A PDF is only read through `pdf_text.read_pdf` (child process).
- **The model never reads** a Scenario's `briefing`, a reverse's `reverse_brief`, `scenario.category`, or a follow-up's purpose. Authored text is sanitised at the write boundary (ADR 0059).
- **The provision sweep deactivates only seed rows** (`created_by IS NULL`). `test_seed.py` pins this.
- **KugelAudio's pooled socket:** never leave `stream_async` short of its `final` frame; one request at a time (ADR 0044). There is no TTS fallback.
- **English schema and wire, German only in user-facing content** (ADR 0057). `status` means the Session's outcome on the listing and the job status on the detail route.
- **The caller opens the transaction**; domain functions take the session and never commit. `session_scope()` is synchronous, so call it via `asyncio.to_thread` from async code (ADR 0099).
- **The turn loop imports nothing from the analysis except `acoustics`, and never the ORM** (ADR 0090). `test_module_dependencies.py` pins this and the package boundaries.
- **The wrap-up is queued by name** (`JOB_FUNCTION` in `shared/feedback/queue.py`). Moving the generator fails every job silently; `test_job_name.py` pins it.
- **Every setting is required and read through `shared/env.py`**; never use `os.environ` directly (ADR 0106). Test fixtures claim `POSTGRES_URL`/`REDIS_URL` with unusable values.
- **Frontend live call:** `useBargeIn` reads the socket and playback through a ref, because the VAD wires its callbacks once. Dropping `interrupt()`'s return value corrupts the transcript. Only `callAccepted` reaches the call screen.
- **SPA and API are two hosts** (ADR 0107). A response header the SPA reads must be in `expose_headers`. A new host the SPA talks to must be added to the CSP in `frontend/docker/render-config.sh`. `default.conf` maps `.mjs`, without which the VAD fails. No test covers the nginx config.
- **UI:** never nest `<button>` in `<a>`. `--color-brand-accent` is for the wordmark only. Keep one `index.css` (ADR 0092), guarded by `stylesheet.test.ts`.
- **A metric's display facts live in `utils/metrics.ts`**, pinned to the backend inventory by `test_metrics.py`. Every active metric needs an explanation in `readings.py`/`explanations.py` (ADR 0098).
- **The User picks up first**; only a reverse is pre-warmed (ADR 0110). A `hard` Persona gets `ANTI_REPEAT_NUDGE_HARD`.
- **Follow-up and reverse stay two routes** with parallel test files (ADR 0100).
- **Focus goals are a setting**: no consent guard, and `deletion.py` never touches them (ADR 0076).
- **Deployment** runs on the DiReKT Hetzner host from `direkt-infrastructure`. The privacy statement still awaits the DPO's review.

## How we work

- **Schema:** never name a constraint by hand (the naming convention handles it, ADR 0053); pass bare names to `op.create_check_constraint`/`op.drop_constraint`. Every foreign key gets `index=True` (ADR 0052). Write `CHECK` constraints into migrations by hand. Use `DateTime(timezone=True)` and write it with `datetime.now(UTC)`. Foreign keys into reference tables carry no `ondelete`. Column defaults are Python-side only. Migrations are tested both ways on an empty DB only.
- **Dependencies:** add each to the `pyproject.toml` of the package that imports it, then run `uv lock`. A dependency in the wrong package fails only in the image.
- **Lint:** flake8 and pylint stay clean. A deliberate exception is written `# pylint: disable=X  # reason`. `duplicate-code` is disabled per file with a reason; never globally. Frontend ESLint runs only the two hook rules (ADR 0094).
- **Frontend tests** render no components; they pin hooks, pure tables and the sentences a screen says.
- **Comments:** only local traps, workarounds and non-obvious invariants, one line each with an ADR pointer instead of reasoning. No history, no restating the code.
- There is no LLM mock. To exercise the generator offline, stub `shared.clients.llm.complete`.

## Agent skills

- Issues: GitHub Issues (`WIBWL/direkt-calltrainer`) via `gh`; see `docs/agents/issue-tracker.md`.
- Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`; see `docs/agents/triage-labels.md`.
- Domain docs: `CONTEXT.md` + `docs/adr/`; see `docs/agents/domain.md`.
