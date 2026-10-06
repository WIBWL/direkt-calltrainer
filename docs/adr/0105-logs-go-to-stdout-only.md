# ADR 0105: Logs Go to Stdout Only, JSON in the Images

## Context

A log file inside a container with no volume is read by nobody. The host's log shipper collects stdout.

## Decision

- One handler, on stdout, configured once at startup. It replaces any handlers already installed (gunicorn adds its own).
- `LOG_FORMAT` is `json` in the images (one object per line, with `session` and any `exception` inline) or `pretty` locally (coloured, with the Session id in brackets).
- The Session id comes from a `contextvar` that follows the connection's tasks.
- There is no log file.
- No spoken content is logged, at any level (ADR 0066).

## Consequences

One call's lines are selected by a query on `session`. Anyone who wants a local log redirects the output.
