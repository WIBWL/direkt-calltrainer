# ADR 0112: The Dashboard Reads One Client-Side Load and Adds No Endpoint

## Context

The progress view aggregates a User's whole history, three screens deep plus a PDF. The obvious shape, a `GET /api/progress` route, keeps being proposed.

## Decision

- **The dashboard reads `GET /api/sessions` only.** Everything above that is pure functions in the browser (`progressStats`, `goalMentions`, `progressOutline`). A second route would be the first place the numbers could disagree.
- **No aggregate table:** six months of retention keeps the volume small, and a stored total would have to follow every deletion.
- **The selection** (period, occasion) filters the loaded list and lives in the URL. Defaults stay out of the URL.
- **One load for all three screens** (`ProgressContext`), up to ten pages of a hundred. Beyond that the screen says it is truncated.

## Consequences

Correctness is a property of pure functions over one payload, which the specs pin without rendering. The listing is load-bearing for two features; anything new is a field on it or a pure function over it.
