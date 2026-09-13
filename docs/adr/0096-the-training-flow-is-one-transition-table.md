# ADR 0096: The Training Flow Is One Transition Table

## Status

Accepted.

## Context

A training runs under one route, `/`, as a sequence of screens: setup, microphone check, the case or the reverse's briefing, the die, the ringing phone, the call, the wait for the wrap-up, and the wrap-up. They are screens and not routes on purpose. Leaving the page tears the WebSocket down, and an abandoned Session is never persisted (ADR 0034), which is also why the header's links are locked on the screens that hold one.

Which screen follows another depends on several facts at once: whether the committed Scenario is a reverse (ADR 0070), whether a random Scenario was drawn (F-62), whether the committed case has anything to read and whether it has arrived yet, whether the user asked for reduced motion, whether the microphone check is skipped because the call is started straight from a finished training (F-60, F-61), and whether the call that just ended was stored (ADR 0066).

Those transitions used to be fourteen `setScreen` calls spread through `App.tsx`, five of them producing the ringing phone and one written inline in the markup. The flow could only be read by finding every call site, and two had drifted apart: the microphone check's button label took the briefing from the library card while the router took it from the committed case, so a Scenario with facts but no card briefing promised a call and delivered a page of text.

## Decision

**Every change of screen goes through `nextScreen(context, event)`**, and `App`'s `advance` is its only caller. It returns the destination and the cut that covers the change — none, a fade, or the reverse's card turn (`ScreenTransition.tsx` performs it).

**The function is pure.** No React, no network, no environment. What a transition depends on is passed in as a `FlowContext`, including `prefersReducedMotion()`, which the caller asks at the moment of the transition. That is what makes the table testable by describing a situation, without a WebSocket, an AudioContext or the 15 MB VAD model.

**The switch over events is exhaustive.** A new event does not compile until somebody decides where it leads and what covers it.

**The table decides where, never what else happens.** Activating playback, sending `session.activate` and unmuting the microphone stay in `App`, performed on `callAccepted` — the only event that reaches the call.

**No path leads straight into a conversation.** Every way in ends on a screen the user leaves by pressing something: the ringing phone before an ordinary call (F-63), the briefing before a reverse. A case that is still in flight routes to the briefing screen, because skipping a case that turns out to hold something cannot be undone, whereas `caseArrivedEmpty` moves on by itself from one that turns out to hold nothing.

**Questions about the flow ask the table.** `briefingFollows` is answered by calling `nextScreen` with `micConfirmed` and looking at the destination, so the microphone check's label cannot disagree with where its button leads.

## Consequences

`App` refreshes the context in a ref on every render and reads it only from event handlers, so `advance` keeps one identity for the life of the component; the waiting screen's two-minute limit hangs off a callback built on it and would restart on a new identity.

A new screen touches three places: the `Screen` type, the table, and the render branch in `App`. A new fact the flow routes on touches `FlowContext` and every test that builds one.

The table does not guarantee the side effects of a transition. That playback is activated when the call begins is ensured by there being a single handler for `callAccepted`, not by the table.
