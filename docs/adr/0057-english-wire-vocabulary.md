# ADR 0057: English Wire Vocabulary

## Status

Accepted

## Context

ADR 0026 made table and column names English throughout, keyed to the domain glossary in `CONTEXT.md`. Nothing in that ADR discusses the JSON the backend actually sends the frontend — that split was implemented separately, in `backend/api/sessions.py`, `backend/session/persistence.py` and `backend/feedback/generator.py`, and only ever documented in prose, in `CLAUDE.md`: "the wire stays German". Concretely, `turn.speaker` (`'user'`/`'persona'`) was translated to a wire key `sprecher` (`'nutzer'`/`'persona'`); `feedback_point.kind` (`'strength'`/`'improvement'`) became `art` (`'staerke'`/`'verbesserung'`); `feedback.summary` became `zusammenfassung`; `feedback.phase_language` became `phasensprache`; and `metric_type.key`/`.name`/`.unit` became `schluessel`/`bezeichnung`/`einheit` on the `Measurement`/`MetricType`-derived dataclasses in `backend/feedback/metrics.py`, whose *key values themselves* (`redeanteil`, `tempo`, `lautstaerke`, …) were also German. `frontend/src/protocol.ts` mirrored all of it, so every consumer on both sides carried two names for the same thing.

This bought nothing once the team decided the identifier vocabulary should be English end to end: it added a translation step in three backend modules, a second identifier for every field to keep in sync, and drift risk between the two vocabularies that `tests/test_api.py` had to pin down explicitly (`test_speaker_is_translated_back_to_the_wire_vocabulary`). It also meant `_SPRECHER`/`_PUNKT_ART` (`sessions.py`), `_SPEAKER` (`persistence.py`) and `_POINT_KIND` (`generator.py`) existed purely to map one English constant to its German twin.

## Decision

The wire matches the schema. `frontend/src/protocol.ts`'s field names and enum-like values are now identical to the ORM's: `speaker` (`'user'`/`'persona'`), `kind` (`'strength'`/`'improvement'`), `summary`, `phase_language`, `scenario`, `measurements`, `key`/`name`/`unit`/`value` (on a measurement), `points`, `transcript`, `duration_ms`. The three translation maps this made necessary are deleted; `backend/api/sessions.py` now passes the ORM's values straight through, and `backend/session/persistence.py` reads `Utterance.speaker` directly instead of looking it up.

The LLM wrap-up's JSON contract changes the same way: `backend/feedback/generator.py`'s `_Wrapup` model and its prompt now require `summary`, `phase_language`, `strengths`, `improvements` instead of `zusammenfassung`, `phasensprache`, `staerken`, `verbesserungen`.

`backend/feedback/metrics.py`'s metric *keys* are English too (`talk_share`, `pace`, `word_count`, `reaction_time`, `pauses`, `loudness`, `questions`, and the inactive `concreteness`, `phase_appropriate_language`, `congruence`), matched by `backend/db/provision.py` the same way a renamed Persona/Scenario key is: the old key is deactivated and the new one inserted, per the seed-reconciliation mechanism ADR 0041 already established — no data migration needed, since historical `Measurement` rows keep working through their `metric_type_id` foreign key regardless of what the current seed calls that metric.

German stays exactly where ADR 0026 already put it: in genuinely user-facing content. A metric's *identifier* is English; its display `name` (e.g. "Redeanteil") is not, because that is what `FeedbackView.tsx` renders and what the wrap-up prompt is told to "use as they are written". Persona/Scenario prose, the wrap-up's own written language, and this documentation are unaffected.

## Consequences

`sessions.py`, `persistence.py` and `generator.py` each lose a translation map and a docstring explaining a boundary that no longer exists — the code is shorter and there is exactly one vocabulary to reason about, not two. `protocol.ts` now reads as a direct mirror of the Python models, which is what a newcomer expects by default. The wire-shape asymmetry between the WebSocket's `session.ended` transcript (`speaker`/`text`/`offset_ms`) and the REST endpoint's `turns` (`speaker`/`start_offset_ms`/`duration_ms`/`transcript`) survives this change — it was never about vocabulary, and unifying it is a separate concern.

The cost is a one-time churn: every place that read a German wire key or a German metric key — `frontend/src/protocol.ts` and its consumers, `tests/test_api.py`, `tests/test_wrapup_prompt.py`, `tests/conftest.py`'s `METRIC_KEY` — needed updating in the same change, and a wrap-up generated before this ADR still has its narrative in German (unaffected, since that content is data, not schema) but any *stored* raw model response referencing the old key names is a historical artifact, not a compatibility concern (the wrap-up is stored parsed, not as raw JSON).
