# ADR 0036: VAD Confirmed-Speech Threshold Instead of a Backchannel Word List

## Status

Accepted

## Context

With barge-in enabled (ADR 0035), a brief backchannel like "mhm", "ja", "okay", or a cough interrupts the persona instantly, which is unwanted — the user is signaling they're listening, not taking the floor. A first implementation filtered these by matching the recognized transcript against a hardcoded list of backchannel words/fillers before allowing an interruption.

## Decision

We removed the word-list filter and instead raised the client-side Voice Activity Detection's (Silero VAD via `@ricky0123/vad-web`) confirmed-speech threshold (`minSpeechMs`), triggering a barge-in only on `onSpeechRealStart` (speech sustained past that duration) rather than the raw `onSpeechStart` event. A backchannel or brief noise below the threshold is silently absorbed by the VAD (`onVADMisfire`) and never reaches the barge-in logic at all.

## Consequences

The filter is now language- and vocabulary-independent — it catches non-lexical fillers a word list could never enumerate, and needs no maintenance as new phrasings surface. The trade-off is a small, fixed delay before any interruption (genuine or not) registers, and the threshold is a blunt instrument: a very short genuine interjection can still be swallowed, and a sustained filler past the threshold could still register as a real turn-take.
