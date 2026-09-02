# ADR 0039: Centralized Logging — Colored Console, Per-Session-Truncated File, Not Committed

## Status

Accepted

## Context

Logging had grown organically per module with inconsistent formatting, no way to correlate lines from concurrent WebSocket Sessions, and no persisted output — only the console, easy to lose once a call ends. Separately, `gunicorn` (the production process manager) attaches its own default handler to the root logger before the application module is even imported, which silently defeated a first, naive `configure_logging()` that skipped setup whenever it found the root logger already had a handler.

## Decision

A single `configure_logging()` call, made once at process startup, clears whatever is already on the root logger and installs two handlers: a colored console handler (severity-colored for warnings/errors; a distinct color per pipeline-stage logger — session, orchestrator, LLM, STT, TTS — otherwise) and a plain file handler writing to `logs/` (gitignored, never committed). A `contextvars`-based Session id is attached to every log record automatically, propagated through whichever asyncio tasks a connection spawns, with no need to thread it through call signatures. The log file is truncated at the start of every new Session, so it always holds exactly the current (or most recently ended) conversation rather than a running history.

## Consequences

A live call's logs are easy to correlate and visually scan by pipeline stage without manual grepping, and gunicorn's pre-existing handler no longer silently defeats the setup. The deliberate trade-off is that the log file holds no history across Sessions by design — useful for iterating on a single live call during development, but two Sessions running concurrently would have the second one's start clobber the first one's still-in-progress log, and nothing is kept once a new call begins. This is acceptable for the project's current single-session-at-a-time development use; it would need revisiting before this logging serves any multi-session production monitoring need.
