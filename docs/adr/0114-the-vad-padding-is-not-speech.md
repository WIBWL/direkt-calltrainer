# ADR 0114: The VAD's Padding Is Not Speech

## Context

The browser VAD sends about 1.8 s that nobody spoke with every utterance: an 800 ms lead-in and 1000 ms of trailing silence. Talk share, Redefluss and reaction time took that padding for the user. Short answers inflated talk share, Redefluss measured utterance length, and reaction times were 0.8 s short.

## Decision

- Praat's segmentation places each utterance: its Turn runs from the first sound to the last (`voice_start_ms`, `voice_end_ms`). Pauses stay relative to the recording.
- `Conversation.user_voiced_ms` is the summed span from first sound to last, which is exactly phonation plus inner pauses.
- **Talk share** = user span / (user span + Persona audio). It rests on the silence split, so it joins the figures ADR 0085 withholds.
- **Redefluss** = phonation / span. A call with no pause of 250 ms or more reads 100 %.
- **Reaction time** ends at the first sound. What remains in it is network time, which makes it slightly too large rather than too small.

## Consequences

The three figures describe the user, not the client's VAD settings. Redefluss sits near 100 % for most calls; its narrower spread is the true one. A Turn continued after a long pause still counts as one utterance for run length, which is a separate defect.
