# ADR 0078: A Classification May Carry a Traffic Light

## Context

The wrap-up shows its figures at equal weight and says nothing about which deserves attention. Colour is the only channel that answers that at a glance. ADR 0051 forbids invisible thresholds on raw figures, which is a different thing from a visible boundary that names a step.

## Decision

A metric's classification may carry a traffic light on the single-call view only if **all** of these hold:

1. The colour sits on a named step, never on a raw figure.
2. The whole scale is visible beside it, in the user's unit, with this call marked.
3. The step is always written in words as well.
4. "Einschätzung" stands beside it, and unvalidated boundaries name the population they came from.
5. Colour and wording are served from beside the threshold in the backend; the frontend never maps a step to a colour.
6. The direction each colour claims is written down beside the constants.
7. It stays on the single call: never on the progress view, across Sessions, or as an overall colour.

The colours direct attention and do not grade. Red means *look here*, yellow *worth a second look* (possibly at the measurement), green *nothing needs attention today*.

## Consequences

A further light needs to meet the seven conditions, not a new ADR. Some users will read colour as a grade regardless; the visible scale and caveat are the mitigation. There are two lights today: intonation and interruptions.
