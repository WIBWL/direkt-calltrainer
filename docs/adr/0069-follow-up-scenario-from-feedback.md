# ADR 0069: The Follow-up Scenario Is Drafted From the Feedback, Into the Editor

## Status

Accepted. Builds on ADR 0058 (User-authored Scenarios) and ADR 0049 (the wrap-up
the draft is built from); bounded by ADR 0051 (no target ranges) and ADR 0043
(a built-in's prompt fields stay withheld).

## Context

The wrap-up already names what a User should work on, and names it concretely:
every improvement point quotes the moment it is about (ADR 0049, F-10). What it
does not do is give them anywhere to practise it. The User reads "you said you
would look into it, where a date was asked for", goes back to the setup screen,
and picks the same list of Scenarios they picked from last time — none of which
is built around that.

The feature asked for is a *Folgegespräch*: the next call, aimed at the weakness
the last one exposed. Three things had to be decided.

**Where the exercise comes from.** The Scenario authoring surface already exists
(ADR 0058): six fields, sanitising at the write boundary (ADR 0059), length caps
(ADR 0063), ownership and a Tenant stamp (ADR 0060), a sharing toggle. A
generated Scenario that bypassed any of that would be a second write path into
the same table.

**What it is built from.** The Session carries two kinds of after-the-fact
material: the wrap-up's prose, and the measured statistics. The statistics are
deliberately norm-free (ADR 0051/0004) — nothing in the system knows whether a
talk share of 62 % is worth training against, and a Scenario built to correct one
would have to assume the range ADR 0051 declined to invent.

**How much of the played Scenario carries over.** The obvious follow-up is "the
same case, but harder". The case, though, is exactly what ADR 0043/0045 withhold
from the client for a built-in: `/api/scenarios` serves the card and never the
four prompt fields, because they are the answer key to the exercise. A draft the
User can read and edit would be a way around that.

## Decision

`POST /api/sessions/{extern_id}/follow-up` returns a **Scenario draft and stores
nothing** (`backend/followups.py`, `backend/api/sessions.py`). The draft opens in
the ordinary Scenario editor, pre-filled; the User reads it, changes what they
like, and it becomes a Scenario only when they press Speichern — through
`POST /api/scenarios`, like anything else they authored. This is the same shape
as the document helper (F-58, ADR 0058): a stateless LLM call that fills a form,
not a second writer.

The material handed to the model is:

* the **improvement points** of that Session's Feedback, and F-42's
  `phase_language` paragraph if there is one;
* the played Scenario's **card only** — `title` and `short_description`, both of
  which the User has already seen — to fix the subject area.

Not the measured statistics, and not the played Scenario's four prompt fields.

The draft is a **new situation in the same subject area**, not a replay of the
same case: the caller's `success_condition` is set to exactly the thing the
feedback says was missing, stated as the caller's own bar, so the exercise
cannot be passed by doing what was done last time. Transfer, rather than a
second run at a case the User now knows the answer to.

The prompt keeps the exercise out of the four fields that become the simulated
caller's briefing (`description`, `case_facts`, `call_goal`,
`success_condition`). A caller told what is being trained plays the answer back.
What the exercise is for may be said on the card (`name`,
`short_description`) — the card never reaches the prompt
(`backend/session/orchestrator.py`).

The draft's values are written in **German**, unlike the seeded built-ins whose
prompt fields are English (ADR 0043). Its destination is the editor, where a
German User reads and rewrites it, and F-58 already writes German into the same
`case_facts` field: ADR 0043 fixes the language of the prompt *frame*, not of the
authored content dropped into it.

Refusals mirror the routes next door: a Session that is not the caller's answers
404, exactly like an unknown one (ADR 0050/0031); a wrap-up that has not landed
or carries no improvement points is a 409; an unreachable model or a reply that
never parses is a 503. The button is only offered where there are improvement
points, so those 409s are guards rather than paths the UI walks.

No provenance is recorded. A saved follow-up is an authored Scenario like any
other — no `derived_from_session_id` column, no badge, no chain.

## Consequences

The feature is one new backend module, one route, one optional editor prop and
one button. Everything a generated Scenario needs afterwards — editing,
deleting, sharing with the company (ADR 0060), running against any Persona — it
gets for free, because it *is* an authored Scenario from the moment it is saved.

The User is the reviewer. A small model (ADR 0011) writing a whole scenario
unsupervised will sometimes produce a thin one; it lands in an editable form
with a line saying so, not in the library. Nothing is stored until they agree.

The draft is asked in thinking mode and takes as long as the document summary
does — well over a few seconds. It is off the live path, so this costs only a
busy state on the button.

Because there is no listing endpoint for Sessions (ADR 0050), the offer lives
exactly as long as the post-call screen does. A User who leaves it cannot come
back for the follow-up later; they can still author the same Scenario by hand.

Two things are deliberately not built, and both stay open:

* **"The same case, harder."** It would need the played Scenario's prompt
  fields, which for a built-in are withheld. It is available in principle for a
  Scenario the User authored themselves — they already own that text — but a
  rule that holds for one half of the library and not the other would be no rule
  at all.
* **Provenance.** `scenario.derived_from_session_id` would enable a
  "Folgegespräch" badge and a series over several Sessions (F-23). It is a
  migration and a delete-path decision for something the pilot does not need to
  answer yet.
