# ADR 0047: Praat via Parselmouth as the Paraverbal Measurement Engine

## Context

Several MUST features rest on numbers from the user's waveform. Praat is the reference implementation for phonetic analysis; a hand-rolled DSP layer would be wrong in ways nobody here could notice.

## Decision

Praat through `praat-parselmouth` is the only acoustic engine, imported in exactly one module that takes WAV bytes and returns a plain dataclass. Loudness is stored as a range, not a level, because browser auto-gain makes absolute levels describe the headset.

## Consequences

`praat-parselmouth` is GPLv3+, which makes the deployed app a combined work. That is acceptable while it is not distributed. The module is testable on synthetic waveforms. There is no Linux arm64 wheel, so images are amd64 only.
