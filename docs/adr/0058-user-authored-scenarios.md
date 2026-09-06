# ADR 0058: User-Authored Scenarios

## Status

Accepted and implemented. This is the storage and API design that ADR 0024
(*User-Authored Scenario Context and Personas*) accepted in principle and left
open — "free-text Scenario and Persona input will need storage of its own in the
Session schema, not yet designed". It closes that for **Scenarios** (F-34, F-58).

Companions built on top of this decision:

- **ADR 0059** — authored Scenario text is information, not instructions (the
  prompt-injection surface ADR 0024 flagged).
- **ADR 0060** — the tenant model and company sharing (R-58 / F-59).

**Only Scenarios, not Personas.** ADR 0024 anticipated authored Personas too; a
product decision overrode that — a Persona is a curated character with a fixed
voice and language (ADR 0043), not something a User hand-writes. The `persona`
table carries the same authored-content columns for schema symmetry (one
migration, one mental model), but nothing writes them and there is no persona
editor.

## Context

Session setup picks a Scenario from the curated library (ADR 0002, ADR 0015).
ADR 0041 already made the `scenario` table the source of truth, so authored rows
have a place to live; ADR 0050 gives a Session an unguessable `extern_id` while
its primary key stays internal; ADR 0031 records whose row it is as a plain
Keycloak `sub` string with no foreign key (there is still no user table).

What was undecided: how an authored Scenario is stored next to the built-ins,
how the client addresses it, who may edit it, and how a User gets the text in
(typed, and F-58: from an uploaded document).

## Decision

### One table, not two

Authored and built-in Scenarios share the `scenario` table. `session.scenario_id`
stays an ordinary foreign key, `/api/scenarios` stays one query, and the mapping
in `backend/library.py` does not change shape. Two tables would need a
polymorphic foreign key from `session`. The cost — every catalogue query now
carries an author/visibility filter — is paid in one place, `library.py`.

### `created_by` + `extern_id` address the row

The `scenario` table (and `persona`, for symmetry) gains:

| Column | Meaning |
|---|---|
| `created_by` `String(64)`, nullable, indexed | Keycloak `sub` of the author. `NULL` = shipped built-in. No foreign key, for the same reason `session.subject_id` has none (ADR 0031). |
| `extern_id` `Uuid`, unique | The id the client uses (ADR 0050). Backfilled onto the seed rows. |
| `visibility` `String(12)`, CHECK-enforced (ADR 0053) | `private` on creation; `public` for a built-in. ADR 0060 adds `tenant`. |
| `created_at` / `updated_at` | DB-defaulted. |

`key` (the hand slug) becomes **nullable** — it does not fit an authored row.
The client sends `extern_id` in `session.start`, never the slug; a sequential
primary key never leaves the backend (ADR 0050).

### CRUD under `/api/scenarios`, owner-scoped server-side

- `POST /api/scenarios` — lands `private`, `created_by` = the verified `sub`.
- `GET /api/scenarios/{extern_id}` — full detail (the prompt fields) **only for
  the caller's own rows**; a built-in or another User's is a 404. Those fields
  are the answer key to the exercise (ADR 0043, ADR 0045).
- `PATCH` / `DELETE` — author only; delete is soft (`active = False`), because a
  past Session references the row — the same rule retired seed rows follow.
- The list endpoint returns the union the caller may see, each row badged, with
  a "Mine" filter. One shared library, not a separate "my scenarios" space —
  this settles the open ADR 0024 UI question.

A 404 and a 403 are the **same answer** here: distinguishing them would let a
caller probe for rows by id (ADR 0050's reasoning). `library.py` scopes every
read and write by the verified `sub`; the client never supplies an owner.

### The situation is required

An authored Scenario with no `beschreibung` (situation) has nothing for the
model to establish. The API and the editor both require it. Only the *case*
fields (facts, goal, success condition) may be blank — ADR 0045: blank means
"improvise". (ADR 0059 restates this.)

### A document becomes a fact list for one field (F-58)

`POST /api/scenarios/dokument` takes a **text-layer** PDF, pulls its text with
`pypdf` (no OCR — a scan is rejected with a message that says so), and has the
LLM condense it into a short fact list for the editor's Fakten field. Stateless:
the file is never stored and there is no per-Scenario document lifecycle. The
why-summarise and the prompt-safety details are in ADR 0059; this is also a
deliberate simplification of ADR 0005 / ADR 0024's "uploads route through the
Data Platform".

## Consequences

`library.py` becomes the one chokepoint for reading and writing the reference
tables, and every catalogue query now filters by author (and, with ADR 0060, by
tenant). The migration that adds these columns is additive; ADR 0060's is the
second one, widening the `visibility` CHECK.

Deleting a User (F-49) should remove their `private` Scenarios and anonymise
`created_by` on any they shared. Doing that cleanly wants the real foreign key
for `subject_id` that ADR 0031 deferred — noted here, not introduced.

The migrations, `docs/datenmodell.md` and the ER diagram regenerate from
`backend/db/models.py` as usual.
