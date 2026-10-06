# ADR 0036: VAD Confirmed-Speech Threshold Instead of a Backchannel Word List

## Context

A "mhm" or a cough should not interrupt the Persona.

## Decision

There is no word list. A barge-in fires only once the browser VAD confirms sustained speech (`onSpeechRealStart`, after `minSpeechMs`). Shorter sounds are absorbed as misfires.

## Consequences

This is language-independent and catches non-lexical sounds. Every interruption registers after a small fixed delay; a very short real interjection can be swallowed.
