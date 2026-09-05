# ADR 0063: Scenario Field Limits Served From One Source

## Status

Accepted. Refines ADR 0059 (§3, the length caps) and follows ADR 0061's line of
removing a second copy of something the backend already owns.

## Context

`backend/authored_text.py`'s `FIELD_LIMITS` is the maximum length the Scenario
authoring API enforces per field (ADR 0059 §3). The editor needs the same
numbers to set `maxLength` on its inputs and to reject an over-long field before
a round trip.

It carried them as a hand-kept copy: `FIELD_LIMITS` in
`frontend/src/scenarioLibrary.ts`, with a comment saying "Mirrors
backend/authored_text.py". The two drifted the first time the backend numbers
were tuned — the frontend still allowed 240 characters where the backend had
dropped to 150, so the form accepted input the save then rejected with a generic
"Ein Feld ist zu lang". ADR 0059 also spelled the numbers into its own prose,
a third copy.

## Decision

One source: `backend/authored_text.py`. `GET /api/scenarios/field-limits`
returns the current caps, keyed by the same field names as `ScenarioDraft`
(so the `title` column is reported as the card field `name`, matching the rest
of the wire — ADR 0061). The editor fetches it when it opens and uses it for
every input's `maxLength`.

`frontend/src/scenarioLibrary.ts` keeps a `FALLBACK_FIELD_LIMITS` constant used
only if that request fails. It does not need to be exact — the server is still
the one that validates — so its drift is harmless. ADR 0059 §3 no longer quotes
specific numbers.

The endpoint is behind the same bearer token as the rest of `/api`, and is
declared before `/{extern_id}` so the literal path wins.

## Consequences

One request when the editor opens, for six integers. The form's `maxLength` now
always matches what the API will accept; tuning a limit is a one-line change in
`authored_text.py` with nothing else to update. A test
(`test_authored_content.py`) pins the endpoint to `FIELD_LIMITS` and checks the
`title` → `name` renaming.

Not done: a build-time codegen step that would remove even the fallback. The
frontend build stage is Node-only (no Python), so it cannot read the Python
constant; a runtime fetch is the pragmatic equivalent.
