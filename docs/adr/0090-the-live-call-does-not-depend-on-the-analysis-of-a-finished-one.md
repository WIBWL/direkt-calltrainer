# ADR 0090: The Live Call Does Not Depend on the Analysis of a Finished One

## Context

The live-call module held the readings of a finished call, so importing the turn loop pulled in the ORM, the analysis modules and SQLAlchemy.

## Decision

- `Conversation`, `conversation()`, `utterances()` and their helpers live in the analysis package (`shared/feedback/calls.py`).
- The turn loop imports nothing from the analysis except `acoustics`, which measures during the call and imports neither side. It never imports the ORM.
- A test checks direct imports by AST and the transitive closure in a subprocess.
- `Turn` stays in the live path as the call's accumulator. Segments rebuild `Turn`s from stored rows so that there is still one fold.

## Consequences

The live path's import closure is `acoustics`, numpy and parselmouth. A violation is a hard import error or a test failure.
