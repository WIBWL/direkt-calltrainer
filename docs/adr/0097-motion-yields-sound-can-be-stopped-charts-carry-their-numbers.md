# ADR 0097: Motion Yields to the System Setting, Sound Can Be Stopped, Charts Carry Their Numbers in Text

## Status

Accepted.

The accessibility statement (`/barrierefreiheit`) names EN 301 549, which corresponds in substance to WCAG 2.1 level AA, and states partial conformance. The Calltrainer itself has not been through the BITV self-assessment that statement describes.

## Context

The frontend has acquired things that move, make sound and draw: the card turn before a reverse (F-61), the die before a random Scenario (F-62), the ringing phone and its ringtone (F-63), the waiting screen with its animated waveform, and three hand-drawn charts on the feedback and progress pages. Each was decided with its feature, and the reasoning sits in component comments. Written down nowhere as a rule, it would be decided again, differently, by the next animation.

## Decision

### Motion

**`prefers-reduced-motion` is read at the moment it matters** (`utils/motion.ts`), not subscribed to: every caller asks once, just before starting something that moves, and a setting changed mid-animation does not cut that animation short.

**What happens under it depends on what the motion is for:**

- **An animation that is the whole of its screen is skipped together with the screen.** The die has nothing to say standing still, so under reduced motion the flow goes from the microphone check straight to the ringing phone (`trainingFlow.ts`, ADR 0096).
- **An animation that covers a change is skipped, and the change still happens.** `ScreenTransition` runs the cut at once instead of behind the card or the fade. A dropped cut would leave the press without any effect, which is worse than no animation.
- **A screen that is a wait or a decision stays, standing still.** The waiting screen keeps its waveform and lens without moving them; the ringing phone keeps the phone and its rings without the shaking.
- **Decorative transitions are switched off in the stylesheet**: the filter slider's thumb, the lift of a card under the pointer, the calendar cells, the sparkline dots, the call animation's bars, the login button.

### Sound

**The only sound that starts by itself is the ringtone, and it can be stopped** (WCAG 1.4.2) by a switch on the screen, styled as the phone's own silent switch. The choice is kept in `localStorage`: it is per browser, of no interest to the server, and somebody who turns it off in an open-plan office should not have to again before every call.

The tone is synthesised rather than played from a file, at a level one can talk over, and is deliberately not a telephone bell. Silence is the failure mode: a browser without an AudioContext leaves the screen working and quiet.

The switch's target is larger than the sliver it draws (WCAG 2.5.8), and its visible label and its accessible name are the same words (WCAG 2.5.3).

### Charts

**Charts are inline SVG, without a charting library** (`Sparkline`, `LoudnessCourse`, `PitchContour`). A band, a line and a few marks do not warrant the dependency, and a library would bring its own accessibility behaviour that would then have to be audited.

**Every chart states its numbers in text.** It is `role="img"` with an accessible name that carries the values — how many trainings, the range they covered, the last value; for the loudness course, where a departure from the usual band occurred. The hover readout adds which training a point was, is `aria-hidden`, and never holds a value found nowhere else.

**Where the values are the point, a real table is the accessible half and not a fallback:** the per-metric page lists every training with its value, the Kennzahlen overview is a table with one row per metric, and the activity calendar and the variety grid are tables with header cells.

**Colour is never the only channel.** ADR 0078 sets this for the traffic lights, ADR 0095 for the families on the progress view.

### The live call

**The call's state is not narrated to a screen reader.** The animation is `aria-hidden`: a phone call gives nobody a spoken "listening" or "thinking", only the other person's voice and the gaps around it, which the Persona's audio already provides (ADR 0014, ADR 0033).

## Consequences

A new animation has to say which of the three kinds it is before it is built, because the kind decides what reduced motion does to it.

The charts' data appears twice, drawn and as text or a table. That is intended, and it means a change to what a chart shows has to change its accessible name as well.

Nothing here is checked automatically (ADR 0094). Conformance rests on these rules being followed, and the self-assessment the accessibility statement promises is still outstanding.
