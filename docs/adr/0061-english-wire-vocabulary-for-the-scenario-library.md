# ADR 0061: English Wire Vocabulary for the Scenario Library

## Status

Accepted. Extends ADR 0057 to the surface ADR 0058 and ADR 0060 added.

## Context

ADR 0057 made the wire vocabulary English end to end — `frontend/src/protocol.ts`
and the Session/Feedback JSON now mirror the ORM's own field names and enum-like
values, with the translation maps deleted. It was scoped to the surfaces that
existed then (`backend/api/sessions.py`, `backend/session/persistence.py`,
`backend/feedback/generator.py`, `backend/feedback/metrics.py`).

The Scenario library and authoring surface landed **after** ADR 0057 — user
authoring in ADR 0058, tenant sharing in ADR 0060 — and was written German on
the wire, matching an earlier convention. `backend/api/scenarios.py`'s docstring
and `CLAUDE.md` both recorded it as a deliberate exception: `sichtbarkeit`,
`herkunft`, `geteilt`, `kurzbeschreibung`, `fallfakten`, `zusammengefasst`, the
route paths `/sichtbarkeit` and `/dokument`, the endpoint `/api/unternehmen`, and
enum values `privat` / `eigen` / `vorlage`, all mirrored a second time in
`frontend/src/scenarioLibrary.ts` and its consumers.

This bought the same nothing ADR 0057 already argued against: a second
identifier for every field, a `to_library()` translation method, a `_SICHTBARKEIT`
map, and a `_detail()` ternary — all bridging one vocabulary to another for a
single client that ships in the same image as the backend.

## Decision

The Scenario library wire matches the schema, exactly as ADR 0057 did elsewhere.

| German (was) | English (now) |
|---|---|
| `herkunft` | `origin` |
| `herkunft` values `vorlage` / `eigen` / `unternehmen` | `origin` values `builtin` / `own` / `tenant` |
| `geteilt` | `shared` |
| `sichtbarkeit` | `visibility` (now identical to the column) |
| `sichtbarkeit` values `privat` / `unternehmen` | `visibility` values `private` / `tenant` (`VISIBILITY_*`) |
| `kurzbeschreibung`, `szenariotyp`, `beschreibung`, `fallfakten`, `anrufziel`, `erfolgsbedingung` | `short_description`, `scenario_type`, `description`, `case_facts`, `call_goal`, `success_condition` |
| `seiten`, `zusammengefasst` (PDF response) | `pages`, `summarised` |
| `PUT /api/scenarios/{id}/sichtbarkeit` | `PUT /api/scenarios/{id}/visibility` |
| `POST /api/scenarios/dokument`, form field `datei` | `POST /api/scenarios/document`, form field `file` |
| `GET /api/unternehmen` | `GET /api/tenant` |

`_SICHTBARKEIT` and the `_detail()` visibility ternary are deleted —
`body.visibility` and `scenario.visibility` are already the schema values.
`ScenarioInput.to_library()` shrinks to the one field that is genuinely not a
column: the card field **`name`**, which is the `title` column. `name` is kept
(not renamed to `title`) because it is what the sibling Persona card and the
`Scenario` value object already call it, and it is not German.

The frontend follows: `Herkunft` → `Origin`, `Sichtbarkeit` → `Visibility`,
`getUnternehmen` → `getTenant`, the `LibraryFilter` union
(`all` / `standard` / `own` / `tenant`), and the four `.card-badge-*` CSS
classes.

Two judgement calls:
- **`/api/tenant`, not `/api/company`** — `CONTEXT.md`'s glossary makes "Tenant"
  the term and lists "company" under _Avoid_ for code. The endpoint returns a
  display *name* that the UI still labels as the company, but the identifier is
  `tenant`.
- German stays where ADR 0026/0057 already keep it: user-facing text. The editor
  field **labels** and hints, the PDF status notes, the 409 detail string
  ("Ohne Unternehmen …"), the badge text ("Individuell", "Individuell · geteilt")
  and the seed content are unchanged.

## Consequences

`backend/api/scenarios.py` loses a map, a method body and a ternary; the wire is
one vocabulary again. The churn is the familiar one-time cost — every consumer of
a renamed key updated in the same change: `scenarioLibrary.ts` and its four
components, `index.css`, and `tests/test_authored_content.py` /
`test_setup_api.py` / `test_scenario_documents.py` / `test_api.py`.

No data migration: the wire rename touches no column. Historical ADRs 0058-0060
keep their German identifiers in prose — they record what was decided then; this
ADR records the correction.
