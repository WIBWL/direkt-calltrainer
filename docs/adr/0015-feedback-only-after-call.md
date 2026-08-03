# ADR 0015: Speech-Behavior Feedback Surfaces Only in the Post-Call Wrap-Up

## Status

Accepted

## Context

While the user speaks, the system continuously analyzes intonation, pace, volume, and articulation. This could be surfaced live, interrupting or annotating the conversation as issues are detected, or collected silently and presented only after the call ends.

## Decision

We will collect speech-behavior findings silently during the Session, without interrupting or annotating the live conversation. All findings are surfaced together in the Feedback wrap-up after the call ends.

## Consequences

The simulated conversation stays uninterrupted and realistic, matching how a real phone call feels. The tradeoff is that the user gets no in-the-moment correction — every observation waits until the wrap-up, which places more weight on that summary's quality (see ADR 0004) to make the delay feel worthwhile.
