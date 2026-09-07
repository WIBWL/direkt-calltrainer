# ADR 0069: The Follow-up Scenario Is Written From the Feedback and Stored

## Status

Accepted. Builds on ADR 0058 (User-authored Scenarios) and ADR 0049 (the wrap-up
it is written from); bounded by ADR 0051 (no target ranges) and ADR 0043 (a
built-in's prompt fields stay withheld). Its lifecycle follows ADR 0026 (a
Session's Scenario is not deletable), ADR 0066 (deletion) and ADR 0067
(retention).

## Context

The wrap-up already names what a User should work on, and names it concretely:
every improvement point quotes the moment it is about (ADR 0049, F-10). What it
does not do is give them anywhere to practise it. The User reads "you said you
would look into it, where a date was asked for", goes back to the setup screen,
and picks the same list of Scenarios they picked from last time — none of which
is built around that.

The feature asked for is a *Folgeszenario*: the next call, aimed at the weakness
the last one exposed. Four things had to be decided.

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
four prompt fields, because they are the answer key to the exercise. A Scenario
the User can read and edit would be a way around that.

**Whether the User has to ask for it.** The first version of this feature was a
button on the post-call screen that drafted a Scenario into the editor and stored
nothing. Two things were wrong with that. The exercise existed only as long as
the screen did: leave the page and the follow-up is gone, which turns the one
piece of the product that points forwards into something you have to notice in
time. And it asked the User to decide whether they wanted an exercise before
there was anything to look at — a button whose result takes half a minute to
arrive and might be thin. The material for the follow-up is finished at exactly
the moment the wrap-up is, in a worker with nobody waiting on it.

## Decision

**Every finished Session whose Feedback names improvement points gets one stored
follow-up Scenario, written without being asked for.**

It is generated in the RQ Feedback worker, immediately after `generator.py` has
stored the wrap-up and closed the job (`backend/followups.py::create_follow_up`).
That is after the job is `done`, not before: the wrap-up is what the User is
polling for, and the follow-up is a second thinking-mode call behind it. The
generation is **silent on failure** — no improvement points, an unreachable
model, or a reply that never yields a usable draft all mean there is no
follow-up, logged and nothing more. The User keeps their wrap-up either way.

It is stored as **an ordinary authored Scenario**, through
`backend/library.py::create_scenario`: `created_by` is the Session's
`subject_id`, `visibility` is `private`, and the text goes through the same
sanitising (ADR 0059) and the same field caps (ADR 0063) as anything typed into
the editor — including the three fields `POST /api/scenarios` requires, which the
worker refuses a draft without rather than storing a row that route would have
rejected. `tenant_id` is NULL: the worker has no request and so no `tenant`
claim to resolve a company from, and `set_scenario_visibility` already stamps a
row that has none at the moment it is first shared (ADR 0060). From then on the
follow-up is the User's Scenario in every respect — editable, shareable,
deletable, playable against any Persona.

The material handed to the model is unchanged from the first version:

* the **improvement points** of that Session's Feedback, and F-42's
  `phase_language` paragraph if there is one;
* the played Scenario's **card only** — `title` and `short_description`, both of
  which the User has already seen — to fix the subject area.

Not the measured statistics, and not the played Scenario's four prompt fields.

The Scenario is a **new situation in the same subject area**, not a replay of the
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

The values are written in **German**, unlike the seeded built-ins whose prompt
fields are English (ADR 0043). It lands in a library a German User reads and in
an editor they rewrite it in, and F-58 already writes German into the same
`case_facts` field: ADR 0043 fixes the language of the prompt *frame*, not of the
authored content dropped into it.

**Provenance is recorded**, reversing the first version's "no
`derived_from_session_id` column": `scenario.derived_from_session_id` is a
nullable, indexed (ADR 0052) foreign key to `session`, NULL on every
hand-authored row and every built-in. It carries three things at once.

* **Exactly one per Session**, enforced by a UNIQUE on that column rather than by
  a check in the worker. `scripts/requeue_feedback.py` exists to put a finished
  Session back on the queue, so the job genuinely runs twice; the constraint is
  what makes the second run produce nothing instead of a second Scenario.
  Postgres allows many NULLs under a UNIQUE index, so nothing else is affected.
* **A category of its own** in the library. The card carries `follow_up: boolean`
  beside `origin: "own"` rather than a new `origin` value — the pattern `shared`
  already uses (ADR 0060) — so the edit affordance and the badge logic stay keyed
  on `origin === "own"`. The setup screen gets a fourth filter chip,
  *Folgeszenario*, and *Individuell* now means hand-authored. Scenarios are
  ordered by category and, within one, by `created_at`.
* **A lifecycle tied to the training it came from.** A follow-up goes when its
  source Session goes: one training deleted, consent withdrawn (ADR 0066), or the
  six-month sweep (ADR 0067).

That last one is a soft delete — `active = False`, the mechanism retired
reference rows already use — and not a row deletion, because **a later Session
may have been played on the follow-up**. `session.scenario_id` is NOT NULL and
carries no `ondelete` by design (ADR 0026): a stored training has to stay
readable, wrap-up and all, whatever happens to the Scenario it ran. So the row
itself survives its source, deactivated: gone from the library, gone from the
selection, and still there for anything that points at it.
`backend/deletion.py::retire_follow_ups` is the single place that decides this,
called from both deletion paths and from the retention sweep; the column's
`ON DELETE SET NULL` — the one such edge into `session`, where ADR 0026
otherwise reserves SET NULL for back-references a Session owns — clears the
provenance at the same moment, so a raw-SQL delete cannot leave a dangling
reference either.

**No consent check is needed anywhere in this path**, and none is added: a
Session that was never stored has no Feedback (ADR 0066 fails closed at write
time), and no Feedback means no job and no follow-up. The condition is upstream
of the worker, and a guard here would only restate it.

The post-call screen shows the finished Scenario — its name, its one-line
description, and two buttons: *Bearbeiten*, which opens the ordinary editor on
the stored row, and *Starten*, which goes straight into the call, against the
Persona this training was played with. The pairing is not a fresh choice: the
exercise follows from that conversation, and asking which partner to have it
with again is a step with only one sensible answer. A *different* partner is
still available — the follow-up is an ordinary row in the library, so starting
it from the setup screen picks any of them. The Persona's `extern_id` therefore
joins its display name on `GET /api/sessions/{extern_id}` (`persona_id`), since
`session.start` takes ids, never names (ADR 0050). While the follow-up is still
being written, the same place carries one busy line, driven by the wrap-up poll
that is already running (`useSessionFeedback`) rather than by a second poller of
its own.

The history's detail page (`PastSessionView`) shows the same block, minus the
waiting: nothing is in flight there, so a Session whose wrap-up produced no
follow-up simply shows none. Its two buttons do the same two things by a
different route — the editor is rendered over that page, and *Starten* hands the
pairing to the training flow through the router's location state
(`TrainingStart`), which consumes it once and clears it, so neither a reload nor
the Back button starts a second call.

`POST /api/sessions/{extern_id}/follow-up` and `createFollowUpDraft` are deleted.
There is no route: the worker calls `draft_follow_up` directly.

## Consequences

The feature costs one column, one call in the worker, one block on two screens
and one filter chip. Everything a generated Scenario needs afterwards —
editing, deleting, sharing with the company (ADR 0060), running against any
Persona — it gets for free, because it *is* an authored Scenario.

**The User is no longer the reviewer before storage.** A small model (ADR 0011)
writing a whole scenario unsupervised will sometimes produce a thin one, and now
it lands in the library rather than in a form. That is the trade this ADR makes:
a private row of one's own, on a screen that says where it went and offers
*Bearbeiten* first, is cheaper to ignore than an offer that expires with the
page. The floor under it is the required-field check — a Scenario with no
situation is refused rather than stored — and the ceiling is that nobody else
ever sees it unless its owner shares it.

**A follow-up per Session accumulates.** A User who trains twenty times has
twenty of them, hence the category and the ordering; the six-month retention
sweep (ADR 0067) is what eventually clears them, on the same clock as the
trainings they came from.

The Scenario library now holds rows nobody typed. `created_by` does not
distinguish them from hand-authored ones — deliberately: the User owns it
exactly as if they had written it, and the only place the difference is visible
is the badge.

The follow-up is reachable from the setup screen forever after, so leaving the
post-call screen no longer loses it, and the training it came from offers it
again for as long as that training is stored. The category is the third way
back to an older one.

One thing is still deliberately not built:

* **"The same case, harder."** It would need the played Scenario's prompt
  fields, which for a built-in are withheld. It is available in principle for a
  Scenario the User authored themselves — they already own that text — but a
  rule that holds for one half of the library and not the other would be no rule
  at all.
