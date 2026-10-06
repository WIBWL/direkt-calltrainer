# ADR 0110: The User Picks Up First; Only a Reverse Is Answered by the Persona

## Context

In an ordinary call the Persona rings, but it also spoke first. Whoever is called answers the phone, and that is the line the opening metric reads.

## Decision

- **In an ordinary call the User speaks first.** After the phone is accepted, the server listens. The Persona's first reply answers the User's line, under an opening instruction that allows greeting just this once. Nothing is pre-warmed.
- **A reverse is unchanged:** the Persona picks up and speaks first, pre-warmed (ADR 0042).
- **Into silence the Persona asks** "Hallo?" four seconds after the pick-up and "Hallo? Hören Sie mich?" four seconds later, then waits. The lines are fixed per language pack and go into the history. The client reports each confirmed speech start (`user.speaking`), which restarts the silence timer.

## Consequences

The Persona's first reply now takes a normal Turn's latency after the User speaks. The User's first utterance is a real, measured Turn. Reaction time skips it, since no Persona line precedes it.
