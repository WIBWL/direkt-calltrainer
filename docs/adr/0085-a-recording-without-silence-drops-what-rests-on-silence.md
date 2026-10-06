# ADR 0085: A Recording Without Detectable Silence Drops What Rests on Silence

## Context

Silence is a fixed 25 dB below an utterance's peak. In a room with steady background noise nothing falls below it, and the noise is counted as speech. Normal calls run 37–67 % silent frames; a noisy one ran 0.6 %.

## Decision

When fewer than 10 % of a call's loudness frames are silent, `pauses`, `phonation_share`, `pace`, `loudness` and `run_length` are omitted. Pitch-based and text metrics, talk share and reaction time are unaffected. An adaptive threshold was rejected: it damages clean recordings and cannot be verified without stored audio.

## Consequences

A noisy room shows fewer tiles, with no explanation yet; a visible line would need a signal from the analysis.
