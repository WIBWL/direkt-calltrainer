# ADR 0082: The Metrics Are Shown in Two Halves, How and What

## Context

The metrics grid grew into a wall of numbers mixing two kinds of thing: how the user spoke and what the exchange was like.

## Decision

- `metric_type.aspect` is `how` (delivery) or `what` (the exchange), CHECK-enforced, and set on each `MetricDef`.
- The post-call screen shows one half at a time behind the same `FilterSlider` the library uses, opening on `how`. It hides itself if one half is empty.
- Talk share is `what`; reaction time and everything measured from audio alone are `how`.
- Words per sentence is a tile built from `word_count`'s detail, not a second metric.
- The progress view groups by focus goal, not by half.

## Consequences

Each half answers one question; the other half is one click away. A test asserts every metric names a valid half and both halves have active metrics.
