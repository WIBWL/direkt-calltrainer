# ADR 0076: Focus Goals as a Stored Selection

## Status

Accepted. Introduces F-62 (`docs/features.md`) and migration `c8a1f60d34be`.
Scoped deliberately: this decides what a focus *is* and where it lives. What
reads one — the wrap-up and the progress dashboard — is a later step and is not
part of this change.

**Amended 2026-09-11** — the selection now also carries a role and call types,
and the setup screen reads it to suggest Scenarios. See the amendment at the end.

## Context

The trainer treats every user the same. It measures the same six Kennzahlen,
the wrap-up weighs the same aspects, and the setup screen offers the same
seventeen Scenarios regardless of what the person in front of it is trying to
get better at. Someone who knows their weak point is the close gets the same
call and the same wrap-up as someone working on their speaking rate.

Users know what they want to practise. Nothing in the application lets them say
so, and nothing stores it, so nothing later could act on it either. A dashboard
(F-13) that shows every metric equally is the same problem one screen further
on: fifteen numbers with nothing to say which of them this user cares about.

The catalogue of goals worth offering came out of the requirements work as
fifteen entries in four groups — the five paraverbal core dimensions, four
along the phases of a call, four about the effect on the other side, and two
about the training habit rather than the performance.

## Decision

A User picks **at most five** focus goals from a shipped catalogue, at first
start and afterwards in their profile. The selection is stored per subject and
is a setting, not training data.

### The limit is five, and it is enforced at the backend

A focus that covers everything is not a focus, and the number has to be small
enough that picking is an act of leaving things out. Five is the point at which
the picked set still fits on one line of a card and still means something.

The API refuses a sixth goal with a 400 rather than storing the first five: a
truncated selection is a focus the user did not pick, and nothing on screen
would tell them it happened. `MAX_GOALS` lives in `backend/focus.py` and travels
to the client in every `/api/focus` response, so the interface disables the
sixth checkbox using the same number the backend rejects it with — the
arrangement ADR 0063 chose for the editor's field limits, for the same reason.

### "No focus" is an answer, not the absence of one

The first-run dialog offers **Ohne Fokus fortfahren** beside the save button
and with equal weight. That is what makes the question askable before the app
appears at all: it can be answered in a second, it costs nothing, and it is
changeable later.

It follows that "picked nothing" and "was never asked" have to be
distinguishable, which is why the decision has a row of its own
(`focus_selection`) rather than being derived from whether any goals are
selected. Reading them as the same state would put the dialog in front of the
user on every single start — turning a free choice into something they have to
keep fending off, which is exactly the failure mode ADR 0066 avoids for consent
by not re-prompting after a withdrawal.

### Three tables

| table | what it holds |
|---|---|
| `focus_goal` | the shipped catalogue: key, German display text, group, evidence kind, position, `active` |
| `focus_selection` | that one subject has answered, and when |
| `focus_selection_goal` | which goals they picked |

`focus_goal` is a reference table in the sense ADR 0041 established: the seed
content lives in `backend/db/seed_data.py`, the table is the source of truth,
and `backend/focus.py` is the single place it is read and written. A retired
goal is deactivated, never deleted, because selections reference it — the same
rule `persona` and `scenario` follow.

The ownership edge (`focus_selection_goal` → `focus_selection`) cascades; the
reference edge (→ `focus_goal`) carries no `ondelete` at all, so a goal with
selections behind it cannot be deleted. That is ADR 0026/0052's split applied
unchanged. `focus_selection.subject_id` carries no foreign key, for ADR 0031's
reason: identity lives in Keycloak and there is no local User table.

A selection is **replaced**, never merged: the client sends the whole set, so a
partial update would need a second call to remove anything and could leave the
row in a state nobody chose. Hence `PUT /api/focus` and not a `POST`, which is
the difference from `/api/consent` — that one appends decisions to a log.

### How far a goal is measurable is recorded, and stays internal

`focus_goal.evidence` is a closed vocabulary of three: `measured` (derivable
from the audio or the transcript), `mixed`, `interpretive` (only a language
model could judge it today). It is planning information for the analysis work
that follows, and it does not leave the backend: `/api/focus` does not serve it
and no card shows it.

An earlier version of this decision put the value on every card as a badge, on
the grounds that ADR 0004 and ADR 0051 refuse to dress an appraisal up as a
measurement. That was the wrong place to apply the rule. Those decisions govern
what the application *claims about a finished call*, and they still hold there
without exception. A goal in a picker is not a claim about anything: it is
something the user wants to work on. Telling them that "Empathie und
Kundenorientierung" is currently harder to measure than "Ausgewogener
Redeanteil" asks them to carry an implementation detail into a choice about
their own training, and it quietly discourages picking the goals that are worth
the most work. The intent is that every goal in this catalogue becomes
measurable; the column records how far that has got, which is a question for
whoever builds the analysis and not for the person choosing.

The obligation the badge was meant to discharge does not disappear, it moves.
Whatever eventually reports on a focus has to say what it is: a measurement
where there is one, an appraisal where there is not. That is a constraint on
the wrap-up and the dashboard, and it is stated as one under Consequences.

Nothing reads a selection yet, and no catalogue text claims otherwise: the
entries say what a goal is about, never what the system will do with it.

### A setting, not training data

The selection says what someone wants to work on. It is not a transcript, not a
measurement, and not the content of a call, so:

- **No consent gate.** ADR 0066's consent covers storing finished Sessions. A
  User who declines still trains, and their focus still shapes what they would
  be shown — withholding the setting would make the decline cost more than it
  should.
- **No deletion path touches it.** Withdrawing consent deletes Sessions
  (`backend/deletion.py`); it must not silently reset the goals someone chose.
  `retention_preference` is the same kind of row and is treated the same way. A
  test in `tests/test_focus_goals.py` pins this, because nothing in
  `deletion.py` mentions focus and the test is what would notice if something
  did.
- **It is named where data is listed.** The profile's data section and the
  privacy statement say that the selection is stored under the account, because
  it is personal data even though it is not call content.

### Where it is asked

`FocusProvider` nests inside `ConsentProvider` (`frontend/src/main.tsx`), so
the two first-run questions come one after the other and the one with a legal
basis behind it comes first. Neither blocks on a failed load: a network blip
must not ask a user who answered months ago to answer again, and their answer
under that dialog would overwrite the one they already had.

## Consequences

One additive migration: three new tables, no existing column touched, so it
runs on a populated database without rewriting a row.

Fifteen cards is a lot for a first screen. The captions carry the meaning and
the paragraphs sit behind an "i" (the `InfoDetails` pattern the consent screens
use), so the dialog can be answered in ten seconds or read in full. It is still
the longest first-run screen in the application, and if the catalogue grows the
grouping will stop being enough.

The catalogue's German text lives in the database, like a Scenario's title.
Editing a caption is therefore a seed change plus a restart, not a frontend
edit — the price of having one source for it.

Two goals in the catalogue (`training_regularity`, `training_variety`) are
about the training habit rather than about how a call went. They are grouped
and worded so that they cannot be read as a judgement of performance, which is
the same line ADR 0065 draws for the progress view.

What this does not do is act on the selection. The wrap-up prompt does not read
it, the setup screen does not sort by it, and no dashboard exists yet. That is
the next step, and it inherits the obligation the evidence column carries:
whatever reports on a focus may only say what is actually behind that goal, an
appraisal where there is no measurement yet, and in no case a score. Five of
the fifteen are `interpretive` or would be reported as one today, which is
where the work is.

## Amendment (2026-09-11): the selection is read, to suggest Scenarios

The Status above put "what reads one" off to a later step. This is that step
for one reader: the setup screen suggests Scenarios from the selection. To give
it something to match, the selection also records a role and the kinds of call
a User takes (migration `d4e7a2c91b36`).

### Role and call types sit beside the goals

Asked on the same first-run screen and stored in the same selection, under the
same rules: a setting, not training data, so no consent guard and untouched by
every deletion path; replaced in full by each `PUT /api/focus`, so leaving them
out means none. Both are optional, like the goals.

The **call types** use the vocabulary of `scenario.category` (ADR 0072). That
is not a convenience: it is the only attribute every seeded Scenario carries
that a suggestion can match, so any other vocabulary would need a translation
nobody could check. The **role** (`TRAINING_ROLES`, CHECK-enforced) is scored
on nothing. It preselects the call types it usually means, which the User then
adjusts — a role is a guess about someone's work, and they know better.

Experience was considered and not asked. Scenarios have no difficulty, so the
answer would change nothing, and a question whose answer changes nothing only
costs time on the one screen that is already the longest.

The role is nullable and not backfilled. Everyone who answered before it
existed is not asked again; the profile section is where they add it.

### How a suggestion is made

Rule-based, in `backend/recommendations.py`: 2 for a matching call type, 1 for
each picked goal whose call context exercises it (`GOAL_CATEGORIES`), an
unplayed Scenario first on a tie, at most five. The voice goals steer nothing,
since every Scenario trains the voice; a reverse replays one particular call
and an uncategorised Scenario has no context, so neither is suggested.

Rules rather than a model, for three reasons: the result is the same every
time, each suggestion can name its reason on the card, and nothing a User said
about their work leaves for a model provider. It is computed in the backend and
not the frontend because that is where it can be tested — the frontend's tests
cover the live-call audio path and nothing else.

### A view over the cards, not a group

The listing marks the suggested cards (`recommendation: {call_type, goals}`)
and the setup screen offers them as **Ihre Empfehlungen**, first in the origin
row. A suggested card keeps its own origin and appears under both: taking it out
of "Standard" because it was also suggested would hide it from anyone looking
there. ADR 0072's rule that every Scenario sits under exactly one origin option
now holds for the origins proper, with the company option and the suggestions as
views across them.

Where there are suggestions, the screen opens on them with the category row on
"Alle", since one category alone would often leave nothing. ADR 0072's opening
selection, Standard with Betrieb & Störung, is the fallback where there are none.

### The evidence obligation is untouched

Suggesting a Scenario to practise a goal claims nothing about how the User does
at it, so it is not a report on the goal. The obligation recorded in `evidence`
stays with whatever comes to report on one — above all the wrap-up, which still
does not read the selection.

### Consequences

The setup screen's first view now depends on the User, which makes a support
question like "what did you see?" one more step to answer.

The role describes a person's work and is personal data like the goals. Neither
is in `/api/me/export` yet; the export was built around trainings, and a
setting was not considered. That is an open point, not a decision.
