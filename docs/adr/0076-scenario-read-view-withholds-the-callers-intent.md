# ADR 0076: A Scenario Read View, Withholding the Caller's Intent

## Status

**Accepted.** Amends ADR 0058, which closed `GET /api/scenarios/{id}` to
everything but the caller's own rows.

## Context

The selection screen shows a Scenario as a card: title, one-line teaser,
category, and the trainee's own `briefing` (ADR 0054). Everything else about it
— the situation, the facts of the case, what the caller wants, what counts as
settled — was reachable only through the editor, and the editor opens only on a
row the caller authored. ADR 0058 made that explicit: a built-in, or another
User's row, answers 404, "it is not editable and its case must not leak."

That rule was written for one question — who may *write* a Scenario — and
answered a second one by accident: who may *read* it. The consequences showed up
as soon as the Personas got an info panel and the Scenarios did not:

- A user picking among seventeen built-ins has one line of teaser per card to go
  on. The briefing helps, but it describes their own side, not the case.
- The two panels on one screen would behave differently for no reason the user
  can see: a Persona can be read, a Scenario cannot.
- A colleague's shared Scenario (ADR 0060) was unreadable too. Sharing a case
  with the company while making it illegible to the company is not a policy
  anyone chose; it fell out of the same 404.

The thing genuinely worth withholding is narrower than "the case". The four
prompt fields do not brief the trainee, they brief the simulated caller
(ADR 0045) — but they do not all give the same thing away.

## Decision

`GET /api/scenarios/{id}` serves **any Scenario the caller may select**, scoped
by the same `library.get_scenario` visibility clause the list uses. It carries
an `editable` flag, decided server-side from the verified `sub`.

What each caller sees:

| Row | Situation, Fakten | Ziel des Anrufs, Erfolgsbedingung | `editable` |
| :--- | :---: | :---: | :---: |
| Shipped built-in | yes | **no** (`null`) | false |
| Shared by a colleague (`tenant`) | yes | yes | false |
| The caller's own / a follow-up | yes | yes | true |
| Another User's private row | — 404, as before — | | |

`call_goal` and `success_condition` are what a built-in withholds, and they are
withheld as `null` rather than `""` so the client can tell a withheld field from
one its author left empty.

The **write** routes are untouched: `PATCH`, `DELETE` and
`PUT …/visibility` remain owner-scoped, and only the author may edit.

## Rationale

The split is between the *situation* and the *intent*.

`description` and `case_facts` describe a state of the world the call is about.
The caller will state most of it within the first minute — that is what the call
is for. Reading it beforehand is the same preparation a real salesperson does
before dialling, and it is the difference between choosing a training case and
guessing at one.

`call_goal` and `success_condition` are different in kind. One is what the
counterpart is trying to get out of you; the other is the condition under which
the exercise is over. A trainee who reads them knows the answer before the
question. That is the leak ADR 0058 was right about, and it survives here.

A colleague's shared Scenario is served whole because sharing is a deliberate
act between people who work together: the author chose to make this case
available to the company, and a case nobody may read is not available. The
asymmetry with a built-in is not an inconsistency — a built-in is a curated
exercise, a shared row is a colleague's working material.

## Consequences

- The info panel on the setup screen renders whatever it is given and shows an
  edit affordance only where `editable` is true. The "Bearbeiten" link moves off
  the card and into that panel, so reading comes before writing for every
  Scenario and the card carries one affordance instead of two.
- Two tests that pinned the old 404 (`test_a_built_in_has_no_editable_detail_view`
  and the tenant-sharing case in `test_tenant_scenarios_are_readable_not_editable`)
  now assert the read view and the `editable` flag instead. The 404 for another
  User's private row is unchanged and still tested.
- `_detail` needs the caller's `sub`, so every call site passes it. It is never
  read from the request body.
- If a future Scenario field is added, it has to be classified: situation or
  intent. The default for anything the model is told *to pursue* is to withhold
  it from a built-in.
