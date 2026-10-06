# ADR 0091: A Measurement Is Stored; a Reading Is Derived on Every Read

## Context

A measurement is computed once and kept, because the audio is gone. A reading (the step, its words and colour) rests on unvalidated thresholds that will be recalibrated. Readings were hard-coded per metric in a route module, so a new metric could ship silently unexplained.

## Decision

- `backend/feedback/readings.py` holds one entry per metric that says anything beyond its figure: a required `explanation`, an optional `steps` function, and an optional `derive`. The detail route names no metric key.
- **No step or colour is ever stored.** Both traffic lights are derived on read, so a recalibration reaches every stored Session, and figure and legend always agree. A stale stored colour is overwritten.
- The export serves `detail_json` raw: what is held, not what is concluded.

## Consequences

A test pins that every active metric is explained, a scale sits only beside an explanation, and a scale colours every step or none. A Session measured before a reading's input existed gets no step.
