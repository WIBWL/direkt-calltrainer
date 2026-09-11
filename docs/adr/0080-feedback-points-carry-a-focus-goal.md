# ADR 0080: Feedback Points Carry a Focus Goal

## Status

Accepted. Stage 2 of `docs/dashboard-konzept.md`, the decision its section 10
left open. Introduces migration `d4c81b70e2a5`. Constrained by ADR 0004 and
ADR 0065; uses F-62's catalogue (ADR 0076).

## Context

The progress view was built without the two blocks it was designed around. What
recurs across somebody's trainings, and the practice suggestion that follows
from it, stood on the page as a labelled placeholder with invented entries and a
"Beispiel" chip, because nothing could be counted.

The reason was one missing edge. The wrap-up writes points of two kinds,
`strength` and `improvement`, as free text. A point carries an optional Turn
reference and nothing else. `feedback_point.metric_type_id` exists and is never
written. So "the closing keeps coming up" was a thing a person could notice by
reading eight wrap-ups and a thing the application could not say at all.

The same gap sat under a second problem. Of F-62's fifteen focus goals, six have
no measurement: Gesprächseinstieg, Einwandbehandlung, Gesprächsabschluss,
Empathie, Souveränität unter Druck, Artikulation. Four of those will never have
one. Whether a close was clear is in what was said, and no acoustic figure
reaches it. Their tiles on the dashboard said "no measurement yet" and would
have gone on saying it forever, while the wrap-ups had in fact been writing
about all six all along without anything recording which was which.

Adding more Kennzahlen would not have fixed either problem. This is not a
measurement gap.

## Decision

Every feedback point is assigned one focus goal from F-62's catalogue as the
wrap-up writes it, stored as `feedback_point.focus_goal_id`.

### A foreign key into the catalogue, not free text

Two spellings of the same weakness would count as two, and the aggregation has
to be deterministic. The same fifteen keys the user picks their goals from, so
a tile and a count are talking about the same thing by construction.

The alternative considered and rejected: cluster a user's points with a model at
read time. More expensive, not reproducible, and it would produce different
groups on every view of the same data.

### Assigned by the wrap-up, in the call it already makes

One extra key per point in the JSON. No second model call, no pass over the
user's history, and the assignment is made by the only thing that has read the
call.

### Six prompt rules, and three of them are about not forcing a fit

- **An empty goal is a normal answer.** A key that nearly fits puts a point into
  somebody's tally of a weakness they do not have, which is worse than an
  untagged point. "Never force a fit" is in the prompt in those words.
- **The goal never changes what the point says.** Write the point on its own
  merits, then label it; if you find yourself rewording a point to match a key,
  delete the key. Without this the feature turns the wrap-up into feedback about
  the catalogue rather than about the call, which would be worse than not having
  it.
- **The two habit goals are never assigned.** Regelmäßiges Training and
  Trainingsvielfalt are not things one call can show.

### Validated at the write boundary, and dropped rather than raised on

`generator._goal_ids` resolves the key against the table. Anything else becomes
NULL: an invented sixteenth key, a habit goal the model assigned anyway, an
empty string. A point with a good observation and a bad label is still a good
observation, and losing the wrap-up over its label would be the wrong trade. The
habit goals are refused here as well as in the prompt, because a rule the model
can ignore is not a constraint.

Deactivated goals still resolve. A point is a statement about a call that
happened, and a goal leaving the catalogue does not make the statement untrue.

### The counts ride on the history route, not on an aggregate one

`GET /api/sessions` carries `feedback_goals`: one `{kind, goal}` per tagged
point, no text. The progress view adds no endpoint, for the reason it never
did — a second path to the same numbers is a second place for them to drift.
This does not reopen what the listing withholds: a tag is a classification, the
wrap-up text still lives only on the detail route.

### What the count is, and the wording that keeps it that

**A frequency of statements, never a measurement of a person.** "The closing was
named as an improvement in 4 of 8 wrap-ups" reports what the wrap-ups said. It
is not a score across Sessions, which ADR 0065 rules out, and it is not a
measurement, which would need the norms ADR 0051 declined to invent.

That distinction is sound in the data and fragile in the reading, so it is
carried by the interface: "genannt" throughout and never "war" or "ist"; a count
over a named denominator and never a percentage; no ordering language beyond
most-mentioned first.

Counted **per training, not per point** — two improvements about the closing in
one call are one call that mentioned the closing. The denominator is the
trainings whose wrap-up carries any assignment at all, because a training with
no wrap-up never had an opinion and one written before this feature had no way
to record one; leaving either in would quietly shrink every fraction.

A theme appears from **two mentions**. One point from one training is an
observation, not a pattern. At most three per column.

## Consequences

**The placeholder is gone rather than kept alongside.** `ProgressPreview` is
deleted. Where there is nothing to count yet the block says which of the three
reasons applies, rather than showing invented entries under somebody's name.

**Six focus goals get a data basis, and four of them get the only one they will
ever have.** Their tiles now show how often the wrap-ups named them. No
threshold there, unlike the recurring block: on a tile somebody picked
themselves, "once so far" is a legitimate answer to "how is this going".

**Every stored wrap-up is untagged and stays that way.** The column is nullable
and backfills nothing; guessing a goal from the text now would be inventing the
data the block exists to count. `scripts/requeue_feedback.py` does produce the
assignment, since it regenerates from the stored Transcript and Measurements
(ADR 0049). Until a user has two tagged wrap-ups the block shows its empty
state, and says why.

**The wrap-up prompt grew again, on a 4B model (ADR 0011).** Fifteen keys plus
six rules, numbered and under their own heading like the rest. Whether the model
picks well is not something the tests can answer — they pin what it was asked,
which is the line `tests/README.md` draws for prompt tests. The failure mode to
watch for is not a wrong key but a *convenient* one: if the counts come out
dominated by two or three goals, the model is reaching for the familiar rather
than reading the point, and rule A4 needs more weight.

**Block E is built on top of it** (`ProgressPractice.tsx`). Three routes in the
concept's order: a follow-up Scenario written from the very training where the
point was last named, else a Scenario of the kind the goal is practised in
(`utils/practiceRoutes.ts`, an editorial table, preferring one not played yet),
else any unplayed Scenario for the goals that bind to no kind of call. The
partner is the Persona from that same training rather than a fresh choice, and
not because that is best but because it is the only defensible one available:
the wire carries no difficulty on a Persona, so the concept's "more demanding
partner" is not something this could pick. Keeping the voice constant also makes
the next call an exercise on the point rather than a different call. The
suggestion always states its ground before it makes its offer; a goal absent
from the editorial table produces no suggestion at all, which forces a decision
when the catalogue grows instead of silently defaulting to "any call".

**This is the first thing the application counts across Sessions.** ADR 0065
drew its line at evaluation, not at counting, and this stays on the permitted
side — but it is the closest anything has come to the line, and the next feature
that wants to aggregate should be read against that ADR rather than against this
one.
