# ADR 0098: Every Kennzahl Opens Onto Its Evidence, and the Evidence Is Never Recomputed

## Context

With no target allowed (ADR 0004/0051), a bare "4 Wiederholungen" invites the reader to supply a norm. Showing *which* four is the only answer that invents none, and the stored details already hold the evidence.

## Decision

1. **Every active metric carries an explanation** (what is counted, how, what it is worth, where it stops being trustworthy), and that is what makes its tile open. A test fails on an unexplained metric.
2. **The evidence page shows what the figure was read off, never a recomputation.** Where a quote must line up with a count, the client reproduces the backend's exact rule (questions cut at question marks; fillers lower-cased with whitespace collapsed).
3. **The evidence explains and does not judge.** No target, no colour on a value.

`pace` stores its two terms. `hesitations` stores each hold with its utterance index (a located event, not a per-Turn statistic). Wrap-up points with a `turn_id` open the transcript at that line. A footnote says that unmeasurable metrics leave no tile, without naming which.

## Consequences

Every stored tile opens; an unstored training's tiles do not. Some pages show only a division, because nothing located was kept.
