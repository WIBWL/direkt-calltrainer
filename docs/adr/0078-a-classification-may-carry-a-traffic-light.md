# ADR 0078: A Classification May Carry a Traffic Light

## Status

Accepted. Amends ADR 0004 and ADR 0051, leaves ADR 0065 in force unchanged, and
replaces the "trial that contradicts the rules" framing carried by ADR 0051's
interruptions light and by ADR 0077.

## Context

Two metrics now show a coloured step: F-51's interruptions and F-35's
intonation. Both were built as exceptions. Both were described in the code
and in their ADRs as contradicting ADR 0004, ADR 0051 and ADR 0065, tolerated
because somebody asked for them, and removable in a few lines.

That framing has stopped being true and it was never quite right.

It has stopped being true because there are two of them, on the two metrics a
reader most often opens, and a rule that is broken twice on purpose is not a
rule with two exceptions. It is an unwritten rule plus an out-of-date written
one, and the written one is what the next person reads.

It was never quite right because of what the wrap-up actually looks like. A user
finishes a call and gets a paragraph of prose, two lists of points, and nine
figures in a grid. Every one of those figures is presented with exactly the same
weight. Nothing on that screen says which of them is worth thirty seconds of
attention and which is context. The user has just spoken for four minutes and
wants to know, first, roughly how it went, and only then why. Uniform grey does
not answer that. It hands them nine numbers and a reading task.

Colour is the only channel that answers it before the reading starts. It is
seen, not read, and it is seen at a glance across a whole grid. Nothing else
available on that screen has the same property: bold text has to be found,
ordering implies a ranking we cannot defend, and a summary sentence is more
prose on a screen that already has plenty.

So the question this ADR settles is not whether to allow a rule to be broken. It
is what an honest use of colour looks like, given that the alternative is a
screen that treats every figure as equally important and therefore says nothing
about any of them.

## What the earlier ADRs actually objected to

Worth separating, because the three are usually cited together and they say
different things.

**ADR 0004** rejected reducing performance to a single number or KPI, at the
pilot stakeholder's explicit request, and required that qualitative feedback
stay the product's output. Its objection is to a *score standing in for* the
feedback. A colour on one step of one named scale is not a score: it does not
aggregate, it does not rank, it does not travel between Sessions, and it
replaces no prose. ADR 0004 already permits a supplementary numeric score that
never replaces the qualitative feedback, which is a weaker constraint than the
one this project has been applying to itself.

**ADR 0051** ruled out target ranges on the metrics because none was
validated for this population, and stated that an invented threshold is a score
in disguise. This objection stands and is the sharp one. It is aimed at a silent
band drawn behind a raw figure, where the user is shown a number, shown a
target, and left to conclude that the gap is their failing, with no way to see
where the target came from or to disagree with it.

**ADR 0065** ruled out judgement on the progress view, where a colour asserts a
direction over a person's development rather than an observation about one call.
That objection is untouched here and stays in force in full.

The distinction this ADR turns on is therefore between an *invisible* threshold
applied to a *raw figure*, which remains forbidden, and a *visible* boundary
that produced a *named step*, which is what a classification is.

## Decision

A metric's classification may carry a traffic light on the single-call view,
under all of the following. These are conditions, not guidance; a light that
fails one of them is not permitted.

**1. The colour attaches to a classification, never to a raw figure.** If there
is no named step there is no colour. F-35 shows this at its plainest: the step
is read from the pitch variation quotient while the metric's number is the
range, so the colour goes on the word and the semitone figure stays black. A
colour over a number it was not read from is the thing ADR 0051 forbids,
whatever it is called.

**2. The whole scale is visible where the colour is.** Every step, its
boundaries in the unit the user is shown, and a mark on the one this call landed
on. A boundary the reader cannot see is a verdict they cannot disagree with, and
that is the property that made an invented target range dishonest rather than
merely uncertain.

**3. Colour is never the only channel.** The step is written out in words
wherever the colour appears. This is an accessibility requirement and an honesty
requirement at once: the words are what the classification actually says, and
the colour is a pointer to them.

**4. The word "Einschätzung" stays beside it,** and where the boundaries are not
validated for this population the interface says what they *were* established
on. "Not validated for this user group" without naming the population it came
from tells the reader to distrust the number without telling them how much.

**5. Colour and wording are served from beside the threshold.** Both come from
the backend, from the same table that decides the step. Nothing in the frontend
maps a step to a colour. A recalibration then reaches the legend, the word and
the colour together, or it reaches none of them.

**6. The direction the light claims is written down** where the constants live,
per colour, in prose. A traffic light asserts a direction whether or not the
author intended one, so the assertion is made explicit and can be argued with.
F-35's yellow is the case in point: it does not mean "too expressive", which
nothing supports, it means "this is the region where the measurement is least
trustworthy, look at the contour".

**7. It stays on the single call.** ADR 0065 is unchanged and unweakened: no
colour on the progress view, no colour carried across Sessions, no aggregate
colour for a training or for a user.

### What the colours mean

They direct attention. They do not grade.

- **Red** means *this is where to look*, not *you did badly*.
- **Yellow** means *worth a second look*, which may be at the user's delivery or
  at the measurement itself.
- **Green** means *nothing here needs your attention today*, not *good enough*.

This is the reading that makes a light compatible with ADR 0004 rather than
merely tolerated beside it. A pointer is not a mark. It is also the reading the
wording on both metrics already follows, and it is now the reading any future
one has to follow.

### What stays forbidden

- A colour on a raw measured figure with no named step behind it.
- A colour on the progress view or anywhere across Sessions (ADR 0065).
- An overall colour for a call, a Session or a user. That is a score with a
  palette, and it is precisely what ADR 0004 refused.
- A target range or band drawn on a chart, which is condition 2 failing rather
  than a different kind of thing.
- A light whose thresholds exist nowhere but in the frontend.

## Consequences

A third light no longer needs a new ADR. It needs to satisfy the seven
conditions, and the review question becomes "does it" rather than "should we
break the rule again". That is the point of writing this down: the previous
arrangement made each new light a fresh argument from first principles, which is
how a codebase ends up with three different answers.

**The rules cost something at the point of adding one.** A classification, a
visible scale in the user's unit, German wording beside the thresholds, and a
written statement of what each colour claims is more work than colouring a
number. It is meant to be. The work is the part that keeps it honest, and a
light that is not worth that effort is a light that was not worth adding.

**Colour will be read as a grade by some users regardless.** Conditions 3, 4 and
7 are the mitigation and they are not a cure. What they buy is that a user who
looks closer finds the scale, the caveat and the population it came from, rather
than finding nothing behind the colour. A user who does not look closer gets an
orientation that is roughly right, which is better than the uniform grey that
gave them no orientation at all.

**ADR 0051's central claim survives intact and should not be read as softened.**
No metric carries a target range, `metric_type` still has no target column, no
`Finding` row is written from a threshold, and the wrap-up prompt still forbids
the model from judging a figure against a norm of its own. This ADR changes
where a *visible* boundary may be shown, not whether an invisible one may be
invented.

**The thresholds behind both lights are still weak, in different ways.** F-51's
two numbers are declared heuristics with nothing behind them at all. F-35's come
from a study of 18 Swedish students presenting in English in a seminar room
(ADR 0077). Neither is validated for German telephone calls, and this ADR does
not make them better. It states how a weak threshold may be shown, and the
answer is: with its scale, its wording, its origin and its uncertainty attached.

**This is falsifiable in the same way ADR 0065 is.** If the pilot produces
enough Sessions to say what these distributions actually look like for this
population, the boundaries stop being borrowed or invented and the caveats
change. Nothing about the seven conditions changes with them.
