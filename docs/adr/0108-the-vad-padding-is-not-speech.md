# ADR 0108: The VAD's Padding Is Not Speech

## Status

Accepted. Amends ADR 0051 on one bullet ("a share divides audio duration by audio duration") and ADR 0085 on which figures a recording without silence withholds. Changes how three stored figures are computed — Redeanteil (F-24), Redefluss (F-51) and Reaktionszeit (F-53) — and where a user utterance sits on the call's timeline, which moves F-51's interruption classification with it. Stored Sessions are corrected by `scripts/backfill_voiced_span.py`.

## Context

The client's voice-activity detection (`@ricky0123/vad-web`, `useMicrophoneVAD.ts`) does not send what the user said. It sends everything from a lead-in before the first sound to the end of the silence it waited through before deciding the user had finished: `preSpeechPadMs`, which the client never sets and which defaults to **800 ms** in vad-web 0.0.30, and `redemptionMs`, set to **1000 ms**. Read in the library's `frame-processor.js`: every buffered frame, pad and redemption frames alike, is concatenated into the audio handed to `onSpeechEnd`. Every user recording therefore carries about 1.8 s that nobody spoke. The stored calls say the same thing from the other side — 37 to 67 % of their loudness samples are silent (ADR 0085), far more than the pauses inside speech account for.

Three figures took that padding for part of the user:

- **Redeanteil** compared the length of the user's recordings with the length of the Persona's synthesized audio (ADR 0051: "the only quantity both sides have"). The Persona's audio has no padding; the user's has 1.8 s per utterance. A call of ten four-second answers against 80 s of Persona read 42 % where the user had spoken for 33 %, and the shorter the answers, the larger the gap. The same bias reached the pressing/rest comparison (ADR 0081), where the answers under pressure are typically the short ones.
- **Redefluss** divided phonation by recording length. ADR 0085 named the padding and concluded the figure was "a reading against the user's own calls". It was not even that: the padding is the same absolute amount per utterance, so the figure mostly measured *how long the utterances were* — a fluent speaker giving short answers read as halting.
- **Reaktionszeit** placed the user's start at "arrival minus recording length", which is the start of the lead-in, 0.8 s before the first sound. Every gap was short by that much, less the network time, and many were clamped to zero. The text behind the "i" told the user the opposite: "eher etwas zu groß als zu klein".

The same placement made every reply start 0.8 s early on the timeline F-51 classifies, so the "noch X Sekunden zu sagen" of an interruption was overstated by as much, and a backchannel (under 1000 ms) could never be recognised: no recording is shorter than 1.8 s.

A dry run of the backfill over the development database: Redeanteil down 5 to 17 points, Redefluss up from 40–70 % to 75–100 %, reaction times up 0.2 to 0.7 s, the zeros gone.

## Decision

**Praat's segmentation says where the sound is, and the utterance is placed by it.** `acoustics.analyze` returns `voice_start_ms` and `voice_end_ms`, the start of the first sounding interval and the end of the last. `measuring.attach_measurements` puts the Turn's start at the first fragment's first sound and its end at the last fragment's last sound. The pauses stay rebased on the recording's start, which is what their offsets are relative to. `user_speech_ms` stays what it was — the recordings' length, a fact — but no figure divides by it any more.

**The user's side of a share is the span from first sound to last**, summed over the utterances: `Conversation.user_voiced_ms`. Praat labels every stretch between the first sound and the last as sounding or as a pause, so the span is exactly phonation plus the pauses inside it. Both terms are stored, which is what makes the correction exact for old Sessions and the live and stored readings of a call identical.

- **Redeanteil** = user span / (user span + Persona audio). Both sides now carry their inner pauses and neither carries padding. It rests on Praat's split into speech and silence, so it joins the figures ADR 0085 withholds over a recording without silence.
- **Redefluss** = phonation / span. A call without a single pause of 250 ms or more reads 100 %. Its detail stores `voiced_ms` instead of `speech_ms`, so the page cannot draw an old row's padding as pauses.
- **Reaktionszeit** needs no formula change: its gaps end where the reply now begins. Its detail says so (`measured_to: first_sound`), which is also the marker the backfill reads to avoid shifting a call twice.

What is left in the reaction time is the network: the Persona's end is modelled on the server, the user's start is placed by the arrival of the audio, and the time the sound takes to the browser and back lies between them. That is a fraction of a second and it makes the figure too large rather than too small, which is now what the text behind the "i" says.

**Stored Sessions are corrected, not left to mix.** `scripts/backfill_voiced_span.py`:

- rewrites Redeanteil and Redefluss exactly, from phonation (Redefluss' or Sprechtempo's detail, or Sprechtempo's division undone) plus the stored pause total, and the pressing/rest Redeanteil from the Turns' stored facts;
- corrects the Reaktionszeit approximately where the Turns carry their loudness curve (stored since 2026-09-11, ADR 0081): the first sound is read off the first audible 100 ms sample, right to about a tenth of a second. The gaps' `at_ms` stay on the transcript's offsets, which the backfill does not move. Older Sessions keep their reaction time, and the script counts them;
- deletes a Redeanteil only where the call positively found no silence (words counted, every Turn measured, no Sprechtempo), since the live path now withholds it there.

## Consequences

The three figures describe the user rather than the client's settings. A change to `preSpeechPadMs` or `redemptionMs` no longer moves any of them.

Old and new Sessions become comparable only once the backfill has run with `--apply`. Until then the progress view mixes both definitions, and the halves of ADR 0065's amendment would show a change that is nothing but this ADR. Run it after deploying, and take the `pg_dump` `docs/deployment.md` asks for first.

The reaction time of a Session stored before 2026-09-11 stays short by the lead-in. It cannot be corrected without the per-utterance curve, and deleting it would take a figure from the user's history that is wrong by a known, constant amount. That is a judgement call, recorded here so that it can be revisited.

Redefluss now sits close to 100 % for most calls, because only pauses of 250 ms and more count against it. It still separates a call with long pauses from one without, which is what it is for; its spread across a user's calls is narrower than before, and the narrower spread is the true one.

Interruptions are not backfilled. A hard interruption rests on the Persona's reply having been cut, which the padding never touched; what changes for old calls is the "X Sekunden" in a Finding's text and the soft/backchannel counts, which are context only.

Not changed by this ADR: a Turn continued after a pause long enough to end the recording (ADR 0035) still counts as one utterance for Sprechlänge am Stück, and the pause between its fragments still appears in no figure. That is a separate defect.
