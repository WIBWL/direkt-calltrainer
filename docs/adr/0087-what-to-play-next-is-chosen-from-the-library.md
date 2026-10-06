# ADR 0087: What to Play Next Is Chosen From the Library

## Context

After a call, the follow-up and the reverse both write something and take most of a minute. The plainest next step, another existing call, was missing.

## Decision

`GET /api/scenarios/{id}/next?persona=…` offers at most two existing Scenarios:

1. **The same Scenario in the other language**, with a Persona of that language. Never for a reverse.
2. **Another Scenario** with the same partner: the best profile suggestion (ADR 0076) that isn't the one just played, unplayed first. Without a profile, an unplayed Scenario of the same category. Each offer names its reason.

There is no model call. One press starts the call and skips the microphone check. It needs no stored Session, so it works without consent. The logic is a pure backend function. The app keeps the last pairing past the end of the call to request it.

## Consequences

The offers appear only right after a call; a reload loses them. Offering a Scenario by the wrap-up's tagged weaknesses is possible now but not built.
