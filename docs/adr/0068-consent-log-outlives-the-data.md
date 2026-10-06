# ADR 0068: The Consent Log Outlives the Data It Permitted

## Context

Withdrawal deletes a User's Sessions. Deleting the consent rows too would destroy the only evidence that they were asked, answered, and that the answer was honoured.

## Decision

No deletion path, sweep or export touches the `consent` history. The export carries only the current decision. Rows hold the `sub` in clear text, because hashing a UUID from a known set is reversible by anyone who can read the realm.

## Consequences

Each account's decisions remain answerable after deletion. A withdrawn account still leaves identifying rows, so the product says "your trainings are deleted", never "all your data".
