# ADR 0115: A Call's Figures Are Placed Against the User's Own Usual Range

Not yet implemented.

## Context

A post-call figure says what happened, not whether it was ordinary *for this user*. A norm over others is refused (ADR 0051), and the previous call mostly measures the difference between two Scenarios. The User's own usual range is neither a norm nor noisy, and it already exists on the progress view.

## Decision

1. **The reference is the usual range** from `progressStats.band` (median ± MAD) over earlier completed trainings, excluding the current one.
2. **It is shown only with five earlier trainings.**
3. **Like against like** where five trainings of the same category exist; the text names what was compared.
4. **Two statements, never merged:** the range, worded as what it is ("Die Hälfte Ihrer Gespräche lag zwischen 0 und 1"), and "Für Sie ungewöhnlich" only beyond 2.5 scaled MADs (Leys et al. 2013), with a minimum distance of 2 for counts.
5. **Quantity words only**: "mehr als sonst", "ungewöhnlich", never "besser" or "zu viel". No colour, arrow or icon.
6. **Metrics:** those marked `comparableAcrossCalls` and drawn as lines. Not the checklists, call length or loudness.
7. **Computed in the browser** from the dashboard's load, the sentence decided in one place.
8. **The wrap-up model does not see it.**

Loudness stays out until recording without auto-gain, or comparing same-device calls only, has been tried. A later change to a derivation must keep stored values comparable, or the metric leaves the comparison until five trainings exist under the new definition.

## Consequences

The single-call screen can answer "was that normal for me?" without a norm. With fewer than five trainings, the note says how many more are needed. "Ungewöhnlich" will sometimes be the Scenario's doing; naming the comparison helps the User discount it.
