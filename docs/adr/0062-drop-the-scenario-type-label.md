# ADR 0062: Drop the scenario_type Label

## Status

Accepted. Removes a column added by the initial schema (as `typ`) and renamed by
ADR 0057's migration (`5a7e1c9f4b02`).

## Context

`scenario.scenario_type` was a free-text label (`String(60)`, e.g. "Offer &
Pricing Call") carried on every Scenario row and exposed as the optional
"Kategorie" field in the authoring editor.

Nothing consumed it:

- **Not the prompt.** `backend/session/orchestrator.py` builds the system prompt
  from `description` and the three case fields (ADR 0045); `scenario_type` was
  never read. `backend/scenarios.py` said so in a comment.
- **Not the selection card.** `_card()` in `backend/api/scenarios.py` returns
  `name`, `short_description`, `origin`, `shared` — not the type.
- **Not a filter.** The four library chips (Alle / Standard / Individuell /
  `<Unternehmen>`) run on `origin` and `shared` (ADR 0060).

The seed comment tied it to F-03 ("Szenario-Typen"), but F-03 is about the
library covering several call contexts — short support cases, consultative
project talks, pricing calls — which the seeded Scenarios do on their own. A
label on the row was not what implemented it, and an author-typed value was
never validated against any vocabulary.

## Decision

Remove the column and the field. `scenario_type` is dropped from
`backend/db/models.py`, the migration chain (`e4a9c07b2f31`), the `Scenario`
value object, `ScenarioInput` / `_detail()` / `_SCENARIO_FIELDS` / `FIELD_LIMITS`,
the seed rows and upsert, and the frontend `ScenarioDraft` / editor field.

The ADR 0061 wire-vocabulary table keeps its row in prose — it records what was
renamed then. The wire simply carries one field fewer now.

While here, the six unused Persona caps (`name`, `role_label`, `role`, `traits`,
`behavior`, `training_goal`) are dropped from `FIELD_LIMITS` too. Personas are
curated, not authored (ADR 0058), so no request model ever read them — only a
seed-length test did, kept alive against a Persona-authoring feature that does
not exist. `FIELD_LIMITS` is now exactly the six authorable Scenario fields.
Persona seed text still runs through `clean()` on the way in, and a test still
asserts that is a no-op — that guard never needed the caps.

## Consequences

One data migration, dropping a column with no dependants. An authored Scenario
that had a category value loses it; there is no reader that would miss it. The
authoring form is one field shorter.
