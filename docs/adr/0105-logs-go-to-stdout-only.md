# ADR 0105: Logs Go to Stdout Only, JSON in the Images

## Status

Accepted (supersedes ADR 0055; amends ADR 0039)

## Context

ADR 0039 and 0055 had each process write colored lines to the console and a plain copy to a log file (`logs/calltrainer.log`, `logs/worker.log`), opened fresh per run. In the deployment that file ends up inside a container with no volume, where nobody reads it, while the host's log shipper (Alloy, in `direkt-infrastructure`) collects what the containers write to stdout — which arrived wrapped in ANSI color codes. The dataplatform writes stdout only: pretty in development, JSON in production.

## Decision

One handler, on stdout. `LOG_FORMAT` picks its shape and is required like every other setting (ADR 0106):

* `json` — one object per line with `time`, `level`, `logger`, `session`, `message` and, for an error, `exception` (the traceback inside the one line). The images set it (`ENV LOG_FORMAT=json` in the `Dockerfile`).
* `pretty` — ADR 0039's colored lines, the Session id in brackets. `.env.example` sets it.

There is no log file, so there is no `logs/` directory and nothing to rotate.

## Consequences

The Session id is a field of its own in the JSON, so one call's lines are selected by a query rather than by `grep "[session <id>]"`. What was in the file is now in `docker compose logs`/Grafana in deployment and in the terminal in development; a developer who wants it kept redirects the process's output. The rule that no spoken content is logged (`test_transcript_logging.py`) is unchanged.
