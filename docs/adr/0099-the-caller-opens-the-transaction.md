# ADR 0099: The Caller Opens the Transaction, a Domain Function Takes It

## Context

Most domain modules took an open session and never committed, which is what makes ADR 0066's guarantees possible. Others opened their own scope, so logic was copied instead of composed.

## Decision

- **A domain function takes the open session and never commits**; its caller (a route, the worker, a script, the startup sweep) opens the scope.
- A module may add one scope-opening wrapper where a caller has no transaction to lend. Logic lives in the session-taking function, never only in the wrapper.
- Rules that decide something are pure functions over rows, not over ids.
- `library.py` keeps opening its own scopes, as the one recorded exception, until a library function has to commit together with something else.
- `session_scope()` is synchronous; async code calls it through `asyncio.to_thread`.

## Consequences

New domain code has one shape to follow. Nothing enforces it mechanically.
