# ADR 0067: Stored Sessions Expire After Six Months, Unless the User Says Otherwise

## Context

Deletion paths that a User has to trigger are not a retention period. ADR 0065 would like pilot data for distributions.

## Decision

- A stored Session is deleted six months after it was recorded. The period is pinned by a test.
- The default is deletion. `retention_preference` holds a row only for Users who switched the sweep off. Off suspends the sweep entirely; switching it back on deletes nothing immediately.
- The sweep runs inside the app, at startup and daily, and asks Postgres each time, so a missed run only delays deletion. Failures never stop the loop.
- The profile leads with the date the oldest training falls due, not with the switch.

## Consequences

The system forgets on its own. Because the switch exists, the guarantee is "six months unless you decided otherwise". Pilot measurements thin out at six months; keeping them would need a separate consent purpose. The consent log and focus goals are not swept.
