# ADR 0100: The Follow-Up and the Reverse Stay Two Routes, Sharing What Must Not Drift

## Context

`POST …/follow-up` and `POST …/reverse` share their shape (404, 409, 503, idempotent through a UNIQUE column). Reviews kept proposing one driver for both.

## Decision

- **They stay two routes.** Their differences are the features: different preconditions, different drafting, different columns and payloads. A shared driver would carry each difference as a parameter.
- **Shared, because it must not drift:** the ownership read (`owned_session`), the length precondition (`MIN_USER_UTTERANCES`, pinned to the client's `MIN_USER_TURNS`), `llm.JSON_ANSWER_NEVER`, and `authored_text.fit`.
- **Their two test files are written alike**, so a difference between the routes shows up as a difference between the files.
- A third route of this kind reopens the question.

## Consequences

A change to one route is carried to the other by hand where the shared pieces don't reach; the parallel tests catch a forgotten one.
