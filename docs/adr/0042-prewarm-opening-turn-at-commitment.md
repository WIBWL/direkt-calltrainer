# ADR 0042: Opening Turn Pre-Warmed at Session Commitment, Not on Selection

## Status

Accepted

## Context

The Persona speaks first. Every Session opens with a Turn the User did not trigger, and that opening Turn has no user utterance to transcribe — but it still needs a full dialogue-generation pass and one TTS call per chunk before the first audio exists (ADR 0033). Whatever that takes is silence at the very start of the Session, at the moment the User is most likely to judge whether the simulation feels like a phone call at all.

The frontend has so far hidden that silence by starting the Session as early as it possibly could. The WebSocket connects as soon as a Persona and a Scenario are known, which — because the card view preselects the first entry of each list (ADR 0015) — is immediately after the app has loaded, long before the User has expressed any intent to start. The server runs the opening Turn straight after the handshake, and the client holds the arriving audio chunks in a buffer, releasing them only once the call screen appears.

Two forces pull against each other here. Perceived latency wants the opening Turn generated as early as anything is known about it. Against that, the EFRE-Direkt gateway (ADR 0011) runs on shared university hardware (ADR 0020), and an opening Turn is not a cheap request: one streamed completion plus one TTS call per chunk. Every Session started in anticipation and then abandoned spends that capacity on audio nobody hears. Binding the work to the earliest knowable moment maximizes the first force and ignores the second entirely — each click on a Persona or Scenario card replaces the connection and starts another opening Turn.

There is a second, quieter problem in the same mechanism: the buffer holding the anticipated audio is not bound to the connection that filled it. When a connection is replaced, its buffered chunks survive, and the chunks of the replacement are appended to them. Releasing the buffer at the start of the call then plays every opening line that was ever generated, back to back. This has been observed in the running app, and it is the reason the anticipation is visible to the User at all rather than being invisible groundwork.

## Decision

We will keep pre-warming the opening Turn, and bind it to the moment the User commits to a Session rather than to the selection that configures one. The Session connects when the User leaves the selection screen for the microphone check — dead time of several seconds, since the check cannot be confirmed until the microphone has actually picked up speech, and enough to cover the opening Turn's generation. Changing a Persona or Scenario no longer starts anything; it only changes what the next commitment will start. The same rule governs the Session that follows a completed one: it pre-warms when the User commits to it, not while the Transcript is still on screen.

We will further treat the buffered opening audio as belonging to exactly one connection. Whenever the connection is replaced, the buffer is discarded and playback returns to its held state, so that releasing it can only ever play audio from the Session that is about to be conducted. This rule is tied to the connection's identity itself, not repaired at each individual point where a Session can be abandoned, because those points are not enumerable in advance — cancelling the microphone check is only the one we happen to know about.

## Consequences

The gateway sees one opening Turn per Session that is actually conducted, instead of one per interaction with the selection screen. Load from pre-warming becomes proportional to Sessions rather than to browsing, which matters on shared hardware where the same models serve every concurrent User.

The latency benefit is preserved but no longer unlimited: it is now bounded by how long the User spends on the microphone check. A User who speaks immediately and confirms at once may hear a short silence before the Persona starts. We accept that, since the check is a deliberate gate rather than a formality, and a Session begun without a working microphone is worse than a Session begun a second later.

Second and later Sessions lose the head start they previously got from the time the User spent reading the Transcript. We prefer one rule that holds everywhere over an extra second that only applies to repeat Sessions and is invalidated anyway whenever the User changes the selection afterwards.

Abandoning the microphone check still spends one opening Turn, since the commitment has already been made at that point. This is bounded at one wasted Turn per abandoned attempt rather than one per click, which we consider proportionate.

The invariant is maintained by two places in the frontend that must share the same notion of when the connection changes: the pre-warm trigger and the buffer discard. If those drift apart, the symptom returns as audio from a Session that no longer exists. This coupling is worth a comment at both ends, and it is the first thing to inspect if an opening line is ever heard twice.
