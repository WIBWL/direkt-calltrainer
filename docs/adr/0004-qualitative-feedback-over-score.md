# ADR 0004: Feedback Is Qualitative, Not Score-Based

## Status

Accepted

## Context

Many training tools reduce performance to a single number or KPI. The pilot stakeholder explicitly rejected this for Calltrainer, favoring differentiated, traceable feedback over a score.

## Decision

We will express Feedback as qualitative, narrative, behavior-focused insight with concrete improvement suggestions. A numeric score may be shown as a supplementary, optional addition, but never replaces the qualitative feedback.

## Consequences

Users get actionable, nuanced feedback instead of an opaque number, matching the stated quality goal. This makes Feedback harder to aggregate or compare across Sessions at a glance, and requires careful language design so it doesn't feel vague or inconsistent between runs.
