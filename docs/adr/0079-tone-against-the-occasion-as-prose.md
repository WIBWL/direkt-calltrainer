# ADR 0079: Whether the Tone Suited the Occasion, as Prose

## Status

Accepted. Follows ADR 0056's pattern for F-42, closes the gap ADR 0077 left
open, and introduces migration `b6e2d914f70a`.

## Context

F-35 measures the shape of a speaker's pitch and, since ADR 0077, classifies
their liveliness against boundaries somebody published. Every text on that
screen ends in the same caveat, in one form or another: how much melody is
appropriate depends on the occasion. A complaint is not a sales call. Someone
who rings up angry is not answered well by the delivery that closes a deal.

The caveat was honest and it was also a dead end. The application knew the
occasion the whole time, because the user picked a Scenario before the call, and
said nothing about it. The user was handed a figure, a classification and a
warning that the classification might not apply here, with no way to find out
whether it did.

Nothing measured can close that gap. There is no distribution of appropriate
liveliness per kind of call, and there will not be one from this pilot: it would
need a norm per Scenario category, and ADR 0051 refused a single norm for the
metrics on the grounds that none was measured. A per-category norm would be
the same invention four times over.

There is, however, an existing answer to exactly this shape of problem. F-42
asks whether the register moved with the phase of the call, which is also
something no figure carries and which would also need norms nobody has. ADR 0056
made it a paragraph of prose written by the wrap-up model rather than a
Measurement. That has been in production since, and it is the right precedent.

## Decision

The wrap-up writes a fifth thing: one paragraph on whether the way the trainee
sounded suited the occasion of this particular call. Stored as
`feedback.tone_fit`, nullable, beside `feedback.phase_language`.

### It is prose, not a Measurement, for ADR 0056's reasons

The right register for a complaint is not the right register for a price
negotiation. No norm is measured for either. A figure here would be the invented
threshold ADR 0051 refused, and would additionally have to be invented once per
kind of call.

### The occasion goes into the prompt, which is new

`_dossier` now opens with the played Scenario's `description` and `call_goal`.
Until now the wrap-up saw the transcript and the statistics and nothing else, so
the situation had to be inferred from the dialogue. The judgement this block
makes cannot rest on an inference about what kind of call it was.

Both fields are English prompt fields already (ADR 0043), so nothing is
translated on the way in and no display text reaches the model.

`success_condition` is deliberately withheld. It says what would have ended the
call well, which is a *result* rather than an occasion, and handing it over
invites the model to grade the outcome under the heading of tone.

### One model call, not a second

Same argument as ADR 0056 made for F-42: it is read off the same transcript, and
a second round trip buys latency and a second way to fail. The wrap-up job still
has exactly one model call and one thing that can go wrong.

### The prompt rules that make it a description rather than a norm

Seven rules, and three of them exist to stop this block becoming the thing this
project has refused four times.

- **Start from the occasion, not from the figures.** Asked the other way round,
  a model reads a figure, calls it lively, and works out afterwards what call it
  must have been. That is an invented norm with a story on top.
- **There is no correct register for a kind of call, and the model must not
  imply one exists.** Two people handle the same complaint well sounding quite
  different. What may be said is what *this* delivery would do to *this* caller
  in *this* situation.
- **A tone that suited the occasion is a normal and frequent answer.** Say so,
  in the same detail. Do not manufacture a mismatch to have something to report.

Plus: the observation is carried by a quotation from the transcript, never by a
figure on its own; the block is about how it sounded and not about what was said
or whether the matter was solved; and it must not restate `phase_language`,
which is about a change *across* the call where this is the call set against its
occasion.

### It is rendered on the intonation page, not in the wrap-up

It answers the question that page raises and cannot settle, and it sits directly
under the classification whose caveat it resolves. Putting it in the wrap-up
would separate it from the figures it is about and would add a third prose block
to a screen that already has a summary, two point lists and `phase_language`.

It is visibly set apart there: its own ground, its own heading, and a line
saying it was written by the model from the transcript and the situation, that
it is a reading rather than a measurement, and that it can be wrong. A reader has
to be able to tell at a glance which parts of that page were counted and which
were interpreted.

## Consequences

**The gap F-35 kept naming is closed, and the caveats can stop apologising for
it.** The info texts still say that appropriateness depends on the occasion;
what changed is that the application now says something about this occasion.

**No Session stored before this has one.** The migration adds the column
nullable and backfills nothing, exactly as `c1f4a83b7d29` did for
`phase_language`. Those wrap-ups came from a prompt that was never given the
occasion, so any value written for them now would be invented. NULL means "not
analysed" and the block is omitted rather than shown empty. Re-queueing
(`scripts/requeue_feedback.py`) does produce one, because it regenerates from
the stored Transcript and Measurements (ADR 0049) and the Scenario is still on
the Session row.

**This is the first thing in the wrap-up that judges a call against its
context**, and it is worth being clear that it judges nothing else. It says
whether a delivery fitted a situation. It does not say the call went well, does
not rank it, and produces no figure. ADR 0004 is untouched: this is qualitative,
narrative and traceable to a quoted moment, which is what that ADR asked the
product's output to be.

**It is the weakest claim on the page, and it is presented as such.** The
classification above it rests on boundaries somebody measured, however far from
this population. This rests on a model reading a transcript. The caveat under it
says so in plain words rather than in a footnote, because a reader who cannot
tell the two apart will trust the wrong one.

**The prompt is longer, on a model that loses rules in long prompts (ADR 0011).**
The tone_fit rules are numbered and live under their own heading, which is the
arrangement the rest of that prompt already uses for the same reason. Whether a
4B model actually holds all seven is not something the tests can answer; they
pin what it was asked, which is the line `tests/README.md` draws for every
prompt test in this suite.
