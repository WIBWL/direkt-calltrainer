# ADR 0109: Who May Cause Model Work, and How Much

## Status

Accepted (amends ADR 0009's "no role check")

## Context

Every route that reaches the LLM, Whisper or KugelAudio sat behind a login, and nothing more: any account the realm would issue a `calltrainer-frontend` token to could use the app, in the shared DiReKT realm, with no bound on how much it spent. One account — or one stolen token — could hold any number of calls open, keep a call running indefinitely, send 16 MB audio frames to Whisper, and have 20 MB of PDF text summarised as often as it liked.

A security review also found that work reached the backend *before* the login check. FastAPI reads a route's declared body before it resolves any dependency, so an anonymous client could make the backend parse any body — a multipart upload spooled to disk, and, under Starlette 0.35, form fields buffered in memory without limit. A WebSocket could be opened and left silent forever. And one crafted PDF, parsed by pure-Python pypdf on the backend's one event loop, froze every live call.

## Decision

**A role, not just a login.** A caller needs the client role `calltrainer-user` on `calltrainer-frontend` (`resource_access.calltrainer-frontend.roles`, `REQUIRED_ROLE` in `backend/auth.py`). A client role, not a realm role: in a realm shared with other services, a realm role of that name is anybody's to hand out. `require_user` answers **403** without it — not 401, which the SPA answers by sending the User round the login again, which cannot help. The socket's handshake refuses with an `error` frame (`not_admitted`) and close code 1008. The SPA reads the role from the access token and shows a "not admitted" screen with a logout button instead of the app (`utils/access.ts`, `NoAccessView`); the backend's check is the one that counts.

**Caps per account** (`backend/limits.py`, counted per `sub`):

| Cap | Value | Where |
|---|---|---|
| Calls open at once | 2 | `/ws/session`, refused with `too_many_calls` |
| Length of a call | 30 minutes | ended between turns as `completed`, with a `time_limit` frame |
| One turn's audio | 4 MiB (~2 min of 16 kHz WAV) | skipped, the client told to listen again; never sent to Whisper |
| PDF fact lists | 20 per hour, every request | `POST /api/scenarios/document`, 429 |
| Reverses and follow-ups | 20 per hour together, only a drafted one | the two routes, 429 before the model is asked |

Two calls rather than one: a call's slot is freed only once its socket is gone, and a reload can open the next socket before the server has noticed the last one drop. The call ends *between* turns, never mid-reply, so a turn in flight can overrun the limit by its own length. A stored reverse or follow-up costs nothing and is returned past the budget.

The counters live in the process. The backend runs **one** gunicorn worker (the Dockerfile says so); a second would multiply every cap by the process count. Moving them to Redis is the step for the day that changes.

**Nothing anonymous reaches the work.**

- `backend/body_limit.py` refuses a body over 1 MB (21 MB on the upload route) with 413 — on the declared `Content-Length` before a byte is read, and by counting a chunked one as it arrives. It sits inside the CORS middleware, so the refusal reaches the SPA as one.
- The upload route no longer declares `files`: it parses its form itself, after `require_user` has run.
- A socket that does not send `session.start` within 10 seconds is closed. The backend image's worker class (`backend/gunicorn_worker.py`) lowers uvicorn's WebSocket frame ceiling from 16 MB to just above one turn, which bounds that first, unauthenticated frame too.

**The PDF is read in a child process** (`backend/pdf_text.py`): `python -m backend.pdf_text`, fed the bytes on stdin, killed after 30 seconds, under a 1 GiB address-space ceiling (Linux; macOS refuses the limit), at most two at a time. A crash, an out-of-memory or an overrun is a German "could not be read" like any other unusable file. A request carries at most ten documents.

**The SPA's page sends a Content-Security-Policy** (`frontend/docker/render-config.sh`, written at container start because it names the API and Keycloak hosts): scripts only from its own origin plus `'wasm-unsafe-eval'` for the VAD, connections only to itself, the API and its socket, and Keycloak, `frame-ancestors 'none'`. HSTS, `nosniff`, `Referrer-Policy` and `Permissions-Policy` stay with Traefik's middleware (ADR 0107). The same image now serves `.mjs` as JavaScript: nginx's `mime.types` has no entry for it, and the browser refused the VAD's onnxruntime glue.

The web stack was raised past the published advisories at the same time: FastAPI 0.142 / Starlette 1.7, gunicorn 26 (request smuggling), PyJWT 2.15 (unbounded JWKS fetches on an unknown `kid`), pypdf 6.19, python-dotenv 1.2.

## Consequences

Every account needs the role before it can do anything: an administrator assigns `calltrainer-user` in the real realm (docs/deployment.md), best through a group. The development realm grants it to `alice`, `bob` and `carol`; `dave` has none, to see the refusal.

A token's roles are read when it is issued, so a role granted or withdrawn takes effect at the next token refresh — within `accessTokenLifespan` — not at once. A call already running is not re-checked; the 30-minute limit is what ends it.

The caps are numbers nobody has measured against real use. Raising one is a change to `backend/limits.py`, deliberately not a setting (ADR 0106).
