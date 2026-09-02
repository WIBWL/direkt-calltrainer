# ADR 0047: Praat via Parselmouth as the Paraverbal Measurement Engine

## Status

Accepted, narrowed by ADR 0051: Praat remains the engine, but only for duration, pauses and loudness. The pitch and voice-quality analysis this ADR originally covered (F-35, F-38) is no longer collected.

## Context

Several MUST features rest on numbers derived from the user's waveform. ADR 0026 modelled the results as `Messung` rows and ADR 0029 gave them a `detail_json` column for the contours, but the measurement engine itself was never chosen.

The candidates were a hand-rolled DSP layer on numpy/scipy, a general-purpose MIR library, or Praat driven from Python through Parselmouth. Praat is the reference implementation for phonetic analysis: its algorithms are the ones the literature cites, and its defaults encode decades of tuning against real speech. librosa is built for music information retrieval and has no silence-segmentation primitive shaped like Praat's. A hand-rolled layer would mean reimplementing autocorrelation pitch tracking and being wrong about it in ways nobody on the team is equipped to notice.

## Decision

We will use Praat through `praat-parselmouth` as the sole engine for paraverbal measurement, and confine every import of it to one module whose public surface is a single function taking WAV bytes and returning a plain dataclass of numbers.

Loudness is stored as a range, not an absolute level: `getUserMedia` applies automatic gain control by default, so an absolute level describes the user's headset at least as much as their voice.

## Consequences

`praat-parselmouth` is GPLv3-or-later. Importing it makes the deployed Calltrainer a combined work under the GPL, and isolating it in one module does not change that, since it runs in the same process. For the pilot deployment of ADR 0020 — university-hosted, not distributed to third parties — this is accepted. If Calltrainer is ever distributed as a closed-source product, the honest alternatives are relicensing it or losing the validated algorithms.

Confining Parselmouth to one module means the choice can be revisited without touching the Feedback pipeline, and that module is testable against synthetic waveforms with no network — unlike every other analysis path in this codebase.

The dependency adds numpy to a backend that was previously numpy-free. Wheels exist for manylinux and Windows, so the image needs no build toolchain.
