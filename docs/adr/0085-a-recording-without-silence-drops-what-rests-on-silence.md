# ADR 0085: A Recording Without Detectable Silence Drops What Rests on Silence

## Status

Accepted. Introduces the `phonation_share` metric (phonation share, F-51) and the guard `_silence_found` in `backend/feedback/metrics.py`. Refines ADR 0047/0048: the acoustic measurement itself is unchanged; what changes is which of its figures are reported for a recording it could not split. An adaptive silence threshold was considered and rejected; the reasons are below.

## Context

**phonation share** was added as the companion to pauses. `pauses` knows the average length of a pause and nothing about how much of the call went into them; `phonation_share` is the share of the user's own recording that was speech — phonation time over recording time, two figures `Conversation` already carried. It sits systematically short of 100% even for an unbroken utterance, because the client's voice-activity detection pads every recording at both ends and that padding is in the denominator. That makes it a reading against the user's own calls rather than an absolute, which is the only reading ADR 0051 allows anyway.

The first test call after it shipped reported **99%** for a call whose turns were visibly halting — eleven words in almost eleven seconds. The stored data explained it. Every earlier call in the database had between **37 and 67%** of its loudness frames marked silent and found between one and twenty-two pauses; this one had **0.6%** silent and one pause of 0.35 s in 35 seconds of speech. The user confirmed a steady background noise in the room.

`acoustics.py` decides silence at a fixed **25 dB below the utterance's peak**, in two places: the loudness curve's sounding mask and Praat's silence segmentation, which yields both the pauses and the phonation time. That recording spanned 18 dB in total, so its noise floor sat above the threshold and nothing fell below it. Four figures rest on that split — phonation share (phonation over recording), speaking pace (words over phonation), pauses (the segmentation) and the loudness span (the sounding frames) — and all four were wrong for that call in the same direction: the noise was counted as speech.

Nothing about the call was broken. Steady background noise is ordinary in the places this trainer will be used.

## Decision

**When fewer than 10% of a call's loudness frames are silent, the recording is taken to have no detectable silence, and the figures that rest on it are left out.** `pauses`, `phonation_share`, `pace`, `loudness` and `run_length` return nothing for that call. The metrics read from pitch (intonation, Verzögerungslaute — noise has no pitch), talk share (recording length, not phonation), reaction time and every text metric are unaffected.

**Amended:** `run_length` (the mean length of runs) was not on this list when the rule was written — the metric was added days later and nobody connected it. It belongs here more than any of the other four: *both* terms of its division come off the same split, so a recording the threshold could not separate inflates the numerator (noise counted as phonation) *and* shrinks the denominator (almost no pause found), and the two errors compound instead of cancelling. It carries neither a step nor a colour, so there was nothing on screen for a wrong value to contradict. The backfill script had been safe all along by accident: `scripts/backfill_run_length.py` gates on a stored `phonation_share` row, which is exactly what this rule withholds — so the figure was protected when reconstructed later and unprotected when measured live.

Absent rather than wrong: a figure shown for such a call would be indistinguishable from a measured one, which is what ADR 0051 refuses. The cut-off sits far from anything ordinary — the lowest silent share of any earlier stored call is 37%, the noisy one 0.6% — so a real speaker who simply paused little does not trip it.

### Why not an adaptive threshold

The obvious fix is to place the silence threshold relative to the noise floor instead of the peak: estimate the floor from the quietest frames and put the threshold some decibels above it. It was rejected for two reasons.

**It damages clean recordings.** The floor has to be estimated from the recording itself, as a low percentile of its intensity. A turn spoken without a pause has no quiet frames except the few the voice-activity detection leaves at its edges, so the low percentile lands in quiet speech; the threshold then rises into the speech and marks weak consonants as silence. The fixed threshold is wrong only for noisy rooms; the adaptive one would be wrong for some quiet ones too.

**It could not be checked.** Whether it helps more than it harms is a question about real audio, and the audio is never stored (ADR 0048). The test suite's synthetic tones cannot represent a room.

## Consequences

A user in a noisy room sees fewer metrics for that call. The tiles simply do not appear — the same way the figures of a failed measurement do not appear today — and nothing yet tells the user why. A visible line ("Hintergrundgeräusch: Pausen und Tempo nicht messbar") would need a signal from the analysis to the screen that does not exist; it is the natural next step.

Calls stored before this keep the figures computed then. The loudness curve is stored, so the rule could be applied to them retroactively by deleting the four rows where it fails; that has not been done.

phonation share counts a held "äh" as speech, as ADR 0084 notes: a call full of hesitation sounds reads as fluent. Subtracting the detected holds would fix that and is not built.
