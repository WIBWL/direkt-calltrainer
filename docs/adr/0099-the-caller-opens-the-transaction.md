# ADR 0099: The Caller Opens the Transaction, a Domain Function Takes It

## Status

Accepted.

## Context

`session_scope()` (`backend/db/session.py`) is the one way to reach the database, and it is opened in fifteen modules. Two conventions have grown side by side.

Most domain modules take an open session as their first argument and never commit: `consent.current`, `consent.record_decision`, `consent.lock_subject`, everything in `focus.py`, `deletion.py` and `retention.py`, `jobs.latest`. The route, the worker job or the script opens the scope around them. That is what lets ADR 0066's two load-bearing guarantees hold at all: the consent answer and the Session INSERT commit together under one advisory lock, and a withdrawal and the deletion it triggers are one transaction. Neither could be written if either function opened its own.

`library.py` does the opposite. Each of its eleven public functions opens and commits its own scope, and a route that needs two of them — the listing, which reads the library, the played Scenarios and the focus selection — runs three transactions for one answer.

The cost of having two conventions showed up once already. The rule for whether a stuck wrap-up job may be retried was written twice, in the retry route and in `scripts/requeue_feedback.py`, and the copies had drifted: one guarded a naive timestamp, the other a missing one. Part of why it was copied rather than called is that there was no agreed shape to call: a function taking a job row, a function taking a session id and opening its own scope, and a route holding a scope open were all equally plausible.

## Decision

**A domain function takes the open session; opening, committing and rolling back belong to its caller** — a route, the worker job, a script, the startup sweep. The function does not commit, so it can be composed with anything else the caller has to commit together with it.

**A module may add one scope-opening entry point where a caller genuinely has no transaction to lend it**, and that entry point only wraps the session-taking function: `consent.allows_storage(subject_id)` without `db`, `retention.sweep_now()`, `jobs.mark_failed(...)` for the live path after a call, `recommendations.for_subject(...)` for the listing. It says so in its docstring. Logic lives in the session-taking function, never only in the wrapper.

**Rules that decide something are pure functions over rows**, not over ids that make them look something up. `jobs.is_live` takes the job row and `jobs.retry_blocked` the Session with its jobs loaded, which is why a route and a script can both ask them without agreeing on who opens what.

**`library.py` stays as it is, as the one recorded exception.** Every one of its functions is a self-contained read or write that commits nothing anyone else has to commit with it, and converting them would move a scope into every Scenario route and every test that seeds a library for no defect fixed. The first time a library function has to commit together with something else, it gets a session-taking form under this decision, and its scope-opening form becomes the wrapper.

## Consequences

New domain code has one shape to follow, and a review can check it: a `with session_scope()` inside a domain module is either a documented wrapper or `library.py`.

The listing still costs three short transactions. They read reference data and the caller's own rows, so there is no consistency between them to lose; if that changes, the listing is the place to open one scope and pass it down.

Nothing enforces this mechanically. A structural test was considered and not written: telling a wrapper from a function that merely opens a scope in passing would need either a naming rule nobody else follows or a list of exempt functions that is itself a second place to update.
