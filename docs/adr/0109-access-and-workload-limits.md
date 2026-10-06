# ADR 0109: Who May Cause Model Work, and How Much

## Context

Any realm account could use the app without bound, in a realm shared with other services. Work also reached the backend before the login check: FastAPI parses a declared body before resolving dependencies, a socket could idle forever, and one crafted PDF parsed on the event loop froze every live call.

## Decision

- **A client role:** `calltrainer-user` on `calltrainer-frontend`. Without it, `require_user` answers 403 and the socket handshake refuses with `not_admitted`; the SPA shows `NoAccessView`. It is a client role because a realm role is anybody's to hand out in a shared realm.
- **Caps per account** (`backend/limits.py`, per `sub`): 2 open calls; 30 minutes per call (ended between turns); 4 MiB of audio per turn (never sent to Whisper); 20 PDF fact lists per hour; 20 reverses and follow-ups per hour together (only drafted ones count). The counters live in the backend's **one** gunicorn worker process; a second process would multiply them.
- **Nothing anonymous reaches the work:** `body_limit.py` refuses bodies over 1 MB (21 MB on the upload) before reading them; the upload route parses its form itself after auth; a socket without `session.start` within 10 s is closed; the WebSocket frame ceiling is just above one turn.
- **PDFs are read in a child process**, killed after 30 s, with a memory ceiling where the OS allows it, two at a time and at most ten per request.
- **The SPA sends a CSP** naming only itself, the API and its socket, and Keycloak, plus `'wasm-unsafe-eval'` for the VAD. nginx serves `.mjs` as JavaScript.

## Consequences

Every account needs the role assigned before use. Role changes take effect at the next token refresh, and a running call is not re-checked. The caps are unmeasured and live in code, not settings.
