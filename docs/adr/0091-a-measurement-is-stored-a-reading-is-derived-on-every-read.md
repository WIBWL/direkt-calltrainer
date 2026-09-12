# ADR 0091: A Measurement Is Stored; a Reading Is Derived on Every Read

## Status

Accepted. Names a distinction ADR 0077 and ADR 0078 already relied on without stating it, and gives it a module: `backend/feedback/readings.py`. Pinned by `tests/test_metric_readings.py`.

## Context

Two things about a metric look alike on screen and are not alike at all.

A **measurement** is computed once, when the call ends, and kept. It is what ADR 0051 governs: one figure per stretch of call, written by `metrics.py`, never recomputed, because the audio it came from is discarded (ADR 0048).

A **reading** is the step of a scale that figure lands on — "monoton", "erhöht" — plus the words and the colour that go with it. Every threshold behind one is a working value that nothing has validated for this population, which is exactly why ADR 0078 lets them exist only under seven conditions.

The distinction had already paid for itself once without being written down. When F-35's reading moved off the semitone range onto the pitch variation quotient (ADR 0077), every stored Session picked up the new scale on its next read, or lost its step where the new input had never been measured — no migration, on data whose audio is long gone. That was possible only because the step was never stored.

What was written down instead was three tables inside `backend/api/sessions.py`, an HTTP route module: which metrics carry an explanation, which carry a scale, and an `if`-chain on metric key deriving the step. Each is a list of *which metrics have this*, kept in the one place that has no business holding a list of metrics — while `metrics.py` opens with "adding a metric is one entry here, not a change spread over a seed and an analysis path".

The failure that follows is quiet: give a new metric a scale and a reading, and it measures, stores and serves correctly while arriving on the wire with no explanation, no scale and no step. Nothing fails. It is the same hole that `frontend/src/utils/metrics.ts` was built to close on the other side of the wire.

There is a second reason it does not belong in a route. ADR 0078's fifth condition is that colour and wording are served *from beside the threshold*, never mapped in the frontend. They were — but the decision about which metrics get one was being made two packages away from the constants it describes.

## Decision

**`backend/feedback/readings.py` holds one entry per metric that says anything beyond its figure**, and the detail route names no metric key at all.

An entry carries an `explanation` (required), a `steps` function (optional) and a `derive` function (optional). The route asks `readings.notes()`, `readings.scales()` and `readings.served_detail(key, detail)`.

### Why the explanation is required and the scale is not

ADR 0078 allows a scale only beside the population its boundaries came from, so a scale with no explanation next to it is a threshold the User cannot argue with. The reverse is fine and is the normal case: `run_length` is explained at length and deliberately carries no step, because a correlation is not a boundary.

### Why not a field on `MetricDef`

That would make the "one entry per metric" claim literally true, and it was rejected: `metrics.py` owns what happens when a call ends, this owns what happens when somebody opens a page, and those are different times with different rules. A figure that is wrong is wrong forever; a step that is wrong is wrong until the next read.

### `steps` is a function, not a value

So that a recalibration reaches the legend without anything in this module being touched.

## Consequences

The detail route lost fifty-seven lines and every metric key it used to name. `api/sessions.py`'s job is now to read rows and serve them.

`tests/test_metric_readings.py` pins ADR 0078's shape structurally rather than by care: every key answers to a real metric in the inventory, a scale sits only beside an explanation, every step is written out in words with a span, and a scale carries a colour on **every** step or on **none** — half a traffic light being worse than none, since the uncoloured steps then read as the absence of a finding rather than as a scale with no direction.

`tests/test_intonation.py` used to import `_served_detail`, a private helper of an HTTP route module, to test a phonetics derivation. It now imports the public function. That import was the symptom: the test wanted the domain function and the only way to reach it was through the route.

`GET /api/me/export` still serves `detail_json` raw, and deliberately: an export is a copy of what is held, not of what is concluded from it. That is now said in `served_detail`'s own docstring so it is not "fixed" later.

There is **one caller**. This buys layering and coverage, not leverage across call sites, and the deletion test comes back "moves complexity" as much as "concentrates" it. It was still worth doing for the coverage: a new metric can no longer be silently unexplained.

A Session measured before a reading's input existed gets no step, which stays the honest answer — reading one off a figure the scale was withdrawn from would reinstate that scale under a new name.
