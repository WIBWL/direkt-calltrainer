# ADR 0090: The Live Call Does Not Depend on the Analysis of a Finished One

## Status

Accepted. Moves the two readings of a finished Session out of `backend/session/models.py` into `backend/feedback/calls.py`, and states which way the dependency between those two packages may run from now on. Pinned by `tests/test_module_dependencies.py`.

## Context

`backend/session/models.py` is what the turn loop writes into while somebody is on the phone: `Turn` is the accumulator the orchestrator fills in as a call runs. `backend/feedback/` reads a call that is over.

It also held the two readings of a *finished* Session — `utterances()`, which puts what was said on a timeline, and `conversation()`, which folds the same Turns into the facts every derivation works from. Keeping the fold there put its result type, `Conversation`, in `metrics.py`, its consumer. So the nineteen-field record that is the entire interface between the two packages was owned by neither: each field's comment sat in one file and the code that filled it in another.

The cost was measurable rather than aesthetic. Importing the live-call module pulled in:

```
backend.db.base, backend.db.models,          ← the ORM, for two string constants
backend.feedback.{acoustics, hesitations,
                  interruptions, intonation, metrics},
backend.session.language_packs,
numpy, parselmouth, sqlalchemy
```

The in-memory module the WebSocket turn loop runs on loaded the whole database schema to name one result type.

The second symptom is in `feedback/segments.py`, whose `_turns_from_rows` describes itself as "the inverse of `session/models.py::utterances`": the analysis package reconstructs the *live-call* type from stored rows so that it can reuse the one fold. That comment pointed across a package seam in the wrong direction.

## Decision

**`Conversation`, `conversation()`, `utterances()`, `Utterance`, `facts()` and `timeline()` live in `backend/feedback/calls.py`.** The package that reads a finished call owns both the record and the fold that produces it, next to the field comments that were already there.

**`backend/session/models.py` may import from `backend/feedback/` only `acoustics`, and nothing else.**

### Why `Turn` stays where it is

It is the accumulator a running call fills in — the orchestrator appends to `turn.pauses`, sets `persona_end_ms`, flips `user_acoustics_complete` — so it belongs to the live path. Moving it into the analysis package to keep the fold company would point the dependency back the way it came, which is the thing this ADR exists to stop.

### Why `acoustics` is the one exception

It measures audio *during* the call (`session/measuring.py` calls it on a worker thread alongside the STT round trip, ADR 0047/0048) and imports nothing from either package. The live path depending on it points the right way; it is filed under `feedback/` for where its output is read, not for when it runs.

### Why a test and not a convention

The rule returns as one convenient import, and the cost is paid in the module whose failures are the hardest in the application to see. `tests/test_module_dependencies.py` checks it twice: the direct imports read off the source with `ast`, and the transitive closure in a subprocess — the second one in a subprocess on purpose, because `sys.modules` is process-wide and by the time any test runs the suite has imported half the backend.

## Consequences

The dependency is now enforced by Python itself as well as by the test: putting the old import back is a hard `ImportError: cannot import name 'Conversation' from partially initialized module`, where before it was a latent structural problem that ran fine. The test still earns its place for what the interpreter will not catch — transitive creep through a third module, and the ORM rule.

The import closure of the live-call module is now `backend.feedback.acoustics`, `numpy` and `parselmouth`.

`segments.py`'s "inverse of" comment now points at `calls.utterances`, one module over inside its own package.

**`Turn` still does two jobs, deliberately.** `segments.py` continues to rebuild live-call `Turn`s from stored rows to reuse the derivations, and that is the remaining shallowness here. It was left because a segment is *a slice of the same call*: it has to go through the same fold, and giving the analysis a second input type is how a second definition of speaking pace gets written, differing from the first by accident. Whoever removes it has to keep one fold.

The move was mechanical — every moved definition is byte-identical to its predecessor bar `Conversation`'s docstring, which no longer names the module it used to sit beside.
