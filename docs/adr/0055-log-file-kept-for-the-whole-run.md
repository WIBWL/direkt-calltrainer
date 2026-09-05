# ADR 0055: Log File Kept for the Whole Run, Not Truncated per Session

## Status

Accepted — revises the per-Session truncation decided in ADR 0039.

## Context

ADR 0039 had the log file (`logs/calltrainer.log`) truncated at the start of every Session, so it always held exactly the current or most recently ended call. That made it useless for anything that spans calls: comparing two runs, catching an error that only shows up on the *next* Session, or reviewing what happened across a development session without copying the file aside between calls. In practice the file was cleared out from under you constantly, and the interesting history was already gone by the time you looked.

The concurrency concern that motivated truncation (a second Session's start clobbering a first that is still in progress) is already handled another way: ADR 0039's own `contextvars` Session id is stamped on every line, so lines from different calls stay separable in one file.

## Decision

The log file is opened once per process in `w` mode — fresh on every `docker compose up`, reload, or `uvicorn` start — and then **appended to for the rest of that run**. Nothing truncates it between Sessions; `reset_session_log()` is removed along with its call in `session_ws.py`. One file per run holds every Session since the last restart, and the per-line Session id is how one call's lines are told from another's (`grep "[session <id>]"`).

Growth within a run is left unbounded and unrotated: a restart is the reset, and development runs are short enough that the file stays small. A long-lived deployment would need log rotation, which is out of scope here (as multi-session monitoring already was in ADR 0039).

The Feedback worker (ADR 0018/0019) writes its own `logs/worker.log` rather than sharing the app's file. Both containers mount the same `logs/` directory and each opens its log in `w` mode at startup, so a shared path would mean whichever process booted second truncated the other's log.

## Consequences

The log now answers "what happened earlier today" and "what did the previous call do differently", not just "what is the live call doing". The file survives across calls, so iterating on turn-taking or barge-in no longer means losing the prior attempt's trace the moment the next call connects.

The trade-off is that the file grows for as long as the process runs and is only bounded by restarting it. That is acceptable for the project's development use and matches how the console output already behaves. ADR 0039's console handlers, color scheme, gunicorn-handler handling and Session-id tagging are all unchanged.
