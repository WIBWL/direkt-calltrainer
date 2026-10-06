# ADR 0096: The Training Flow Is One Transition Table

## Context

A training is a sequence of screens under one route, because leaving the page tears down the socket. Screen changes were scattered across fourteen `setScreen` calls, and two had drifted apart.

## Decision

- Every screen change goes through the pure function `nextScreen(context, event)`, and `advance` is its only caller. It returns the destination and the cut (`none` or `fade`).
- Everything a transition depends on is passed in `FlowContext`, including reduced motion, so the table is testable without sockets or audio.
- The switch over events is exhaustive.
- The table decides only where; side effects (activating playback, `session.activate`, unmuting) happen in `App` on `callAccepted`, the only event that reaches the call.
- No path leads straight into a conversation: the ringing phone precedes an ordinary call, the briefing precedes a reverse.
- Questions about the flow ask the table, so labels cannot disagree with where buttons lead.

## Consequences

`advance` keeps one identity because the context lives in a ref. A new screen touches the type, the table and the render branch.
