# ADR 0084: Hesitation Sounds Are Estimated From the Pitch Contour; Articulation Is Not Measured

## Context

Whisper removes "äh" and "ähm" from the transcript. The licensed filler models are non-commercial. A hesitation sound is a held, voiced, flat stretch of pitch, which running speech rarely produces.

## Decision

- `hesitations` counts voiced stretches of at least 250 ms spanning under two semitones in the user's pitch contour. Both thresholds are provisional. It needs no new Praat call.
- It is labelled an estimate. A drawn-out "jaaa" counts too. It is absent if any Turn's acoustics failed.
- **Articulation stays unmeasured.** Swallowed endings fall below the silence threshold and the browser's noise suppression; formant spread and recogniser confidence measure anatomy or the headset.
- Not yet tried: prompting Whisper to keep fillers, which depends on the gateway passing the parameter through.

## Consequences

Hesitation sounds are visible at all. Redefluss counts a held "äh" as speech. The thresholds need checking against real recordings.
