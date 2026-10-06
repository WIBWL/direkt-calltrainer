# ADR 0077: The Liveliness Reading Moves to the Pitch Variation Quotient

## Context

F-35's five-step reading on the pitch range rested on a derivation that a literature review found no source for. The review did find support for the pitch variation quotient, a better ceiling for the pitch pass, and a perceptual threshold for level endings.

## Decision

- **The reading uses the pitch variation quotient** (Hincks 2005): standard deviation over mean F0, in Hz, per 10-second window, then averaged. There are three steps: monoton below 0.15, lebendig from 0.15 to 0.25, sehr lebendig above 0.25. The scale has no bad end.
- **The range in semitones stays the headline figure, without a verdict.** Semitones stay the unit (Nolan 2003).
- **A traffic light on the step** under ADR 0078: monoton red, lebendig green, sehr lebendig yellow. Yellow means the measurement is least trustworthy there (octave errors, nervousness), not that the speaker was too expressive. The colour goes on the word, never on the semitone figure.
- **The metric page** shows the contour, one coloured lead sentence, and the figures; method and limits sit behind an info toggle, limits first.
- **A level ending** is below the glissando threshold 0.32/T semitones over the final 400 ms (Mertens 2004).
- **The second pitch pass's ceiling** is 2.5 × q3 (Hirst 2011), because expressive rises are normal material here.

## Consequences

The boundaries come from 18 Swedish students speaking L2 English, and the interface names that population. They are not validated for German telephone calls. The quotient is one cue; fluency also carries perceived liveliness, and nothing combines the two.
