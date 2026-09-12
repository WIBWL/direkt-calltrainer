# ADR 0084: Hesitation Sounds Are Estimated From the Pitch Contour; Articulation Is Not Measured

## Status

Accepted. Introduces the `hesitations` metric (F-51) and `backend/feedback/hesitations.py`. Records why articulation (F-38, the focus goal "Deutliche Artikulation") stays unmeasured, and why two ready-made filler detectors were not used. The two thresholds in `hesitations.py` are provisional until checked against real recordings.

## Context

"Äh", "ähm" and "hm" are the fillers people mean first, and the catalogue for "Prägnante Sprache" names "ähm" as its first example. They are also the one kind the transcript cannot count. Whisper normalises them away: across the stored transcripts not one "äh" survived, and in a test call made to look for them it kept exactly one, spelled the English way ("Um...") at the start of a turn. ADR 0083 counts the lexical fillers; the hesitation sounds need another source.

The audio is that source, and it is gone the moment the call ends (ADR 0048). Whatever reads it has to read it inline, from what `acoustics.py` already measures, or be added to `acoustics.py` itself.

Three ways were weighed.

**A trained filler model.** Two exist and both fit the task. *CrisperWhisper* is a Whisper fine-tune for verbatim transcription, trained on English and German, that writes fillers as `[UM]`/`[UH]`. Its licence is `cc-by-nc-4.0`. *PodcastFillers* is a dataset of about 35,000 annotated "uh"/"um" in English podcasts, with no trained model attached; its annotations are licensed for "noncommercial research purposes only", defined as "academic research and teaching only", and the licence says outright that this prohibits deploying technology built from them in commercial applications. A trainer piloted with companies (ADR 0060) cannot rest on either without a licence decision nobody on the team can make, and CrisperWhisper would be a second speech model to host besides.

**Asking Whisper to keep them.** The transcription API takes a `prompt`, and a prompt that itself contains fillers is documented to make Whisper keep them. It costs one parameter, no licence and no new model. Two things are unknown: whether the DiReKT gateway passes the parameter through (it ignores `language`), and what the Persona does with a transcript full of "ähm", since it reads the same text. It is not built; it remains the first thing to try.

**Reading them off the pitch.** A hesitation sound is a held, voiced stretch whose pitch barely moves. Running speech moves the pitch several times a second — ADR 0077 reads liveliness from that variation — so a quarter of a second of flat voicing is rare, and it is what "ähhh" is. The 10 ms pitch contour per utterance already exists (`pitch_per_turn`, F-35).

## Decision

**`hesitations` counts held, flat, voiced stretches in the user's pitch contour: at least 250 ms long, spanning under two semitones.** An unvoiced frame ends a stretch, since a hesitation sound is voiced throughout; the span is measured against the stretch's own first frame, so it is the same for a low and a high voice. Two semitones is wide enough for the tracker's frame-to-frame jitter (about a third of a semitone at 2% noise) and narrow enough to exclude intonation. Both numbers are marked provisional in the module.

It is an **estimate**, and says so on its tile ("geschätzt aus der Tonhöhe"). A drawn-out "jaaa" or "sooo" has the same shape and is counted too. It is `how` in ADR 0082's split and absent when any Turn's acoustics failed, since a missing contour would read as fewer hesitations rather than as none measured (ADR 0048).

It needs no new Praat call: the contour is already measured for F-35, and this is its second reader.

### Articulation stays unmeasured

The obvious reading of "Endungen verschlucken" — the level falls at the end of a phrase — fails on the loudness curve itself. `acoustics.py` marks every frame more than 25 dB below the utterance's peak as silence, and a swallowed ending is quiet by definition: it is discarded before any metric could see it. The browser records with noise suppression and automatic gain control on, which attenuate the same quiet endings. A metric built on it would show roughly the same value for everyone.

The phonetically sound measure is the spread of the vowel space (F1/F2 formants): clear speech keeps the vowels apart, mumbled speech pulls them to the centre. It is far less affected by level processing, but without knowing which frame belongs to which vowel it is a coarse spread, strongly shaped by anatomy, and it needs a new Praat analysis. Whisper's own confidence (`avg_logprob` via `verbose_json`) would measure the recogniser rather than the speaker — a poor headset lowers it as much as mumbling does — and the gateway may not serve it.

None of these is built. The goal stays a text-only goal in the progress view, which says there is no measurement rather than showing one that measures the microphone.

## Consequences

Hesitation sounds are counted at all, where before their absence from the transcript made them invisible. The count is an estimate and should be read as one.

phonation share (`phonation_share`, ADR 0085) counts a held "äh" as speech, so a call full of them reads as especially fluent. Subtracting the detected holds from the phonation time would correct that; it is not done yet.

Real recordings — the same sentence said with and without "ähm", mumbled and clear — are what the thresholds need and what an articulation measure would have to be chosen by. Until then both stay as recorded here. If the Whisper prompt works on the gateway, the hesitation sounds can be counted exactly from the transcript and this detector becomes the fallback.
