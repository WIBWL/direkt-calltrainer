# ADR 0115: A Call's Figures Are Placed Against the User's Own Usual Range

## Status

**Accepted**, with the project lead: the usual range as the reference (not the mean, not the previous call), five earlier trainings as the floor, quantities only in the wording, the range stated as the half of the calls it holds, and the wrap-up model kept out. Not built yet. One point is left open on purpose and does not block it: the loudness, which stays out of the comparison until one of the two ways below has been tried. Amends ADR 0065 on its scope: that ADR governs the progress view, and this one brings a reference *across* Sessions into the single-call view for the first time. ADR 0065's list of what stays refused on the progress view is untouched, and so is ADR 0078's seventh condition (no traffic light across Sessions). Depends on ADR 0114 having been backfilled, see "Before this can be built".

## Context

A figure on the post-call screen is shown without a reference. "3 Unterbrechungen" or "Redeanteil 38 %" tells the user what happened. It does not tell them whether that was ordinary *for them*, and that is the question they bring to the screen. Three references are available, and two are ruled out.

**A norm over other people** is what ADR 0051 refused, and the reason still holds: nothing is validated for this population, and "an invented threshold is a score in disguise". The two traffic lights (ADR 0078) exist only where a published scale could be named.

**The previous call** is the reference that suggests itself ("mehr Unterbrechungen als beim letzten Mal"). It is the weakest of the three. One call against one call measures the difference between two Scenarios and two Personas at least as much as a change in behaviour, the limitation ADR 0065's amendment already writes on the progress view. For a count between 0 and 3, "von 1 auf 2" is mostly chance.

**The user's own usual range** has neither problem. It is not a norm, because it is built from nobody but the user. It rests on several calls, not one. It already exists: `progressStats.band` computes it for the progress view (median ± MAD, from three trainings on), and the progress view shows it as "Ihr üblicher Bereich". What the single-call screen lacks is the step of holding one call up against it.

That step says what a norm would say, *unusual*, without the norm. "For you, this was unusual" is a statement about a distribution the user produced. It is not a judgement of their conduct. The distinction has to be kept in the wording, because the obvious phrasings ("Verschlechterung", "zu viele", a red mark) turn it back into exactly the grade ADR 0004 refused. Several of these figures have no better direction at all. Cutting in is often right (the interruption text says so itself), and a higher talk share is right in a consultation and wrong in a complaint.

## Decision

**1. The reference is the usual range, never the previous call and never a mean.** It is the band `progressStats.band` already draws: median ± MAD over the user's *earlier* completed trainings, the current one excluded. One implementation, so the progress view and the single-call screen cannot name two different "usual ranges". A mean is ruled out because one aborted or unusual call moves it.

**2. It is shown only with enough calls behind it: five earlier trainings.** The progress view draws a band from three, which is enough to describe a spread and too few to call anything unusual against it. Five is chosen over eight knowingly. A user sees the note after their sixth training rather than their ninth, and the price is that the spread of five calls is itself uncertain: one unusual call among them widens the range noticeably, which makes "ungewöhnlich" rarer rather than more frequent. That is the safe direction to be wrong in. If the pilot shows the note flickering between neighbouring calls, raise the floor.

**3. Where possible, like against like.** If there are five earlier trainings of the same kind of call (the occasion filter's `scenario.category`, ADR 0072), those are the reference. Otherwise all earlier trainings are. The text says which: "verglichen mit Ihren Reklamationsgesprächen" / "verglichen mit allen Ihren Gesprächen".

**4. Two statements, never merged.**

- *The range, always* (once condition 2 holds), beside the figure, **worded as what it is: "Die Hälfte Ihrer Gespräche lag zwischen 0 und 1"** ("… lag bei 1" where both ends round to the same value). The band is the median ± one MAD, and by the definition of the MAD exactly half of the calls it was computed from lie inside it — at least half, where the MAD is zero and the fallback to the mean deviation applies, which the sentence still states truly. "Sonst meist" or "üblich" would claim more than the band holds. The band itself is not widened: the sentence is made true, not the number bent to fit a word. The progress view keeps its wording for now ("Ihr üblicher Bereich" in `ProgressView.tsx`, `ProgressMetricTable.tsx` and `progressPdf.ts`, and `meist` in `progressStats.formatRange`), by decision of the project lead. The two screens then name one range in two ways, knowingly; whoever changes either should bring the other along.
- *"Für Sie ungewöhnlich"*, only when the figure lies clearly outside: further from the median than 2.5 times the MAD (scaled by 1.4826 so it estimates a standard deviation), the "moderately conservative" cut-off of Leys et al. (2013) for exactly this robust test. For a count the distance must also be at least 2, or 0 → 1 would be flagged whenever half the calls lay at 0. This cut-off says how rare the figure is *in the user's own history*. It says nothing about whether the conduct was right. It is a statistical convention, stated as one, and not a boundary somebody invented for good or bad.

**5. The words carry a quantity, never a quality.** Permitted: "mehr als sonst", "weniger als sonst", "länger", "kürzer", "ungewöhnlich". Forbidden, as in ADR 0065 condition 2: "besser", "schlechter", "Verbesserung", "Rückschritt", "zu viel", "zu wenig". No colour, no arrow, no icon that points up or down. Not a traffic light, and ADR 0078's seventh condition stays exactly as it is.

**6. Which metrics.** Those `utils/metrics.ts` marks `comparableAcrossCalls` and draws as a line. Not the checklists (opening, closing), whose 0–3 parts make "unusual" meaningless. Not the loudness, see below. Not the call length, which is the Scenario's more than the user's. The two classified metrics keep their scale, and the range stands beside it without replacing it.

**7. Where it is computed.** In the browser, from the same client-side load the dashboard reads (ADR 0112), with the pure functions in `utils/progressStats.ts`. The sentence is decided in one place, like `reportOutline.ts`, so the screen and the PDF cannot say different things. No endpoint and no stored field: it is a reading, derived on every read (ADR 0091), and it changes as the history grows.

**8. The wrap-up model does not see it** (initially). The generated text stays about this call. Whether the model may say "anders als sonst" is a second decision, and it would need the range passed into the prompt against the prompt's own rule not to judge figures against a reference.

## The loudness

The stored loudness figure is already a fluctuation, not a level: the span between the user's quiet and loud passages in dB, 5th to 95th percentile (ADR 0047). A span in dB is a ratio and so, in principle, independent of how loud the microphone is set. That makes it the right candidate for a comparison across calls.

It is excluded today because of `autoGainControl: true` (`useMicrophoneVAD.ts`). The browser's automatic gain does not apply one fixed gain. It raises quiet stretches and lowers loud ones while the user speaks, which compresses exactly the span being measured, and how strongly depends on browser, operating system and device. Two calls on two headsets differ in their AGC as much as in the user's voice.

Two ways to open it, neither decided here:

- **Record without automatic gain** (`autoGainControl: false`). The span would then describe the voice, and only the noise floor and the distance to the microphone would still reach it. The cost falls on the call itself: quiet users reach the speech recogniser and the VAD more quietly. That has to be tried against Whisper and Silero before anything else is decided.
- **Compare only calls on the same device.** The client knows the device label, and a hash of it could be stored per Session. AGC would still distort the span, but in the same way for every compared call.

Until one of them is tested, the loudness keeps its within-call reading (ADR 0081, the course of `loudness_course`), where the device is the same on both sides.

## Before this can be built

- **ADR 0114 backfilled** (`scripts/backfill_voiced_span.py --apply`). Otherwise the range is built from calls measured under the old definition, and a new call is flagged as unusual because the measurement changed rather than the user.
- **A rule for every later change of a derivation**: a change that alters stored values ships its backfill in the same change, or the metric drops out of this comparison until five trainings exist under the new definition. Without that rule this feature turns every measurement fix into a false "ungewöhnlich".

## Alternatives considered

- **The previous call as reference** — see Context: noisy, and dominated by Scenario and Persona.
- **A direction from the user's focus goal.** Somebody who picked "Aktives Zuhören" has said themselves that fewer interruptions is what they are after, and the application would not be inventing the direction. It is attractive, and it is left for later. It would be the first place a Kennzahl is framed as "in the direction of your goal", and that needs its own decision about what happens when the figure moves the other way.
- **A colour for "ungewöhnlich".** Refused. A colour on a figure without a named step fails ADR 0078's first condition, and across Sessions its seventh.

## Consequences

The single-call screen can answer "war das für mich normal?" without a norm. A user with fewer than five trainings sees nothing new, which is honest and will look to them like a missing feature. The note then says how many more trainings it needs.

"Ungewöhnlich" will sometimes be the Scenario's doing and not the user's. Condition 3 narrows that, and the wording ("verglichen mit …") names what the call was compared with, so the user can discount it.
