# ADR 0064: A Per-User Session History, With Ownership as the Query

## Context

F-13 and F-48 need a User's stored Sessions as a series.

## Decision

`GET /api/sessions` returns the caller's own Sessions, newest first, paginated (default 20, cap 100).

- **Ownership is the `WHERE` clause** (`subject_id = caller.sub`), not a check afterwards. There is no id to guess.
- Each row carries its Measurements **without `detail_json`** (curves are too large and no cross-Session view plots them), plus the focus-goal-tagged feedback points with their text.
- It omits the wrap-up text, but carries `has_feedback` and, where false, `feedback_status`. Here `status` is the Session's outcome (`completed`/`aborted`).
- The order is total: `started_at DESC, session_id DESC`.
- Related rows are eager-loaded, so a page is a fixed number of queries.

## Consequences

One request serves both the history and the progress view. Offset pagination would misbehave under concurrent writes; keyset pagination is the fix if that ever matters.
