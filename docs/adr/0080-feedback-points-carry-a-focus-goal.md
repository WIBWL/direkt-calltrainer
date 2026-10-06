# ADR 0080: Feedback Points Carry a Focus Goal

## Context

Wrap-up points were free text, so "the closing keeps coming up" could not be counted. Several focus goals have no measurement and never will.

## Decision

- The wrap-up assigns each point one focus goal from the catalogue, in the call it already makes, stored as `feedback_point.focus_goal_id`.
- The prompt says: an empty goal is normal, never force a fit, the goal never changes what the point says, and habit goals are never assigned.
- At the write boundary an unknown key or a habit goal becomes NULL; the point is kept. Deactivated goals still resolve.
- The history route carries the tagged points with their text (ADR 0064). There is no aggregate endpoint.
- The progress view counts **per training**, over trainings whose wrap-up has any tag. A theme appears from two mentions, at most three per column. The wording is always "genannt", as a count over a named denominator, never a percentage.
- A practice suggestion follows from the most recent mention: a follow-up from that training, else a Scenario of the matching kind, against the same Persona.

## Consequences

Goals without measurements get a data basis. This is the closest anything comes to ADR 0065's line, and it stays on the counting side. If the counts cluster on a few goals, the model is choosing convenient keys.
