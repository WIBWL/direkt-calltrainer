# ADR 0110: The User Picks Up First; Only a Reverse Is Answered by the Persona

## Status

Accepted. Narrows ADR 0042 to the reverse (ADR 0070).

## Context

Since F-63 an ordinary call reaches the User as a ringing phone they have to accept: the Persona is the one who rang (`_casting` in `session/prompting.py`). Once accepted, though, the Persona spoke first — its opening line had been generated during the microphone check and held back until `session.activate` (ADR 0042). A phone does not work that way. Whoever is called answers it, and says who they are — "Beispiel GmbH, Müller am Apparat, guten Tag" — before the caller says a word. The trainee never got to practise that line, and it is the very line F-63's `opening` metric reads for a greeting, a name and an offer of help.

## Decision

In an ordinary call the User speaks first. After the phone is accepted the server sends `state: listening` and waits for the User's first Turn; the Persona's first reply is the answer to it, requested by the opening instruction, which now says that the User has just picked up and that the rule against greeting again does not apply to this one reply. It is appended after the User's line for as long as nothing the Persona said has been heard, so a first reply the User talked over entirely still gets it on the next Turn.

A reverse is unchanged: the User rang, so the Persona picks up and speaks first, pre-warmed while the User reads their briefing (ADR 0042). The branch is taken in `session_ws._open_call` on `scenario.reverse`.

## Consequences

The ordinary call's pre-warm disappears — there is nothing to say before somebody has answered — and with it the one Turn per abandoned microphone check ADR 0042 accepted as waste. The cost moves to the Persona's first reply, which now takes a normal Turn's latency (STT, generation, first TTS chunk) after the User has spoken instead of starting on the accept press.

The User's first utterance is now a real Turn with audio: it is measured like every other, and the opening metric reads the line the User actually answered the phone with. Reaction time has no Persona line to count the first utterance from and skips it, as it already skipped a Turn with no preceding reply.

A User who accepts and says nothing would hear nothing at all, which a real caller does not put up with. The Persona therefore asks into the silence, as a caller does: "Hallo?" four seconds after the pick-up (`pickup.PROMPT_AFTER_MS`), "Hallo? Hören Sie mich?" four seconds after that, and then it waits. The lines are fixed per language pack (`pickup_prompts`) rather than generated, because they are the same two words for every caller and a model round trip would only delay them; each is a Turn with no user side, interruptible like any other. They go into the history, so the model knows it asked, but they are not the opening — the reply to the User's first words still gets the opening instruction, and the re-greeting guard stands down for it.

The silence is timed on the server, while it waits for the User's first Turn. The User's audio only arrives once they have finished speaking, so on its own the server would ask "Hallo?" into a slow answer still being recorded. The client therefore reports each confirmed speech start that is not a barge-in (`user.speaking`), and the silence is counted afresh from it. A report that turns out to be a cough only postpones the prompt. A reverse never asks: there the Persona has already picked up.
