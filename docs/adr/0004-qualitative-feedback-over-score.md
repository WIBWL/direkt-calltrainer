# ADR 0004: Feedback Is Qualitative, Not Score-Based

## Status

Accepted. Amended by ADR 0078, which permits a traffic light on a named
classification of a single call under seven conditions. That amendment does not
soften what this ADR refuses: an overall colour for a call, a Session or a user
is a score with a palette and stays out. What it allows is a pointer telling the
reader which of nine equally-weighted figures is worth reading first, which this
ADR never argued against.

## Context

Many training tools reduce performance to a single number or KPI. The pilot stakeholder explicitly rejected this for Calltrainer, favoring differentiated, traceable feedback over a score.

## Decision

We will express Feedback as qualitative, narrative, behavior-focused insight with concrete improvement suggestions. A numeric score may be shown as a supplementary, optional addition, but never replaces the qualitative feedback.

## Consequences

Users get actionable, nuanced feedback instead of an opaque number, matching the stated quality goal. This makes Feedback harder to aggregate or compare across Sessions at a glance, and requires careful language design so it doesn't feel vague or inconsistent between runs.
