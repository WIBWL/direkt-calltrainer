# ADR 0083: Metrics That Read Words Take the Session's Language

## Context

Question types, fillers and repetitions need vocabularies, and a German list over an English call reports a zero that looks measured.

## Decision

- `Conversation.language_id` is the Persona's language. Each metric that reads words takes its list from that language's pack. Without a pack, a metric that is nothing but its vocabulary is absent.
- **Open/closed questions** are a detail of `questions`: a question starting with a question word is open. Both are read off the same question marks, so they add up.
- **Fillers** are lexical only (quasi, sozusagen, eigentlich, halt, …; basically, you know, …), word-bounded. The tile names the commonest. Whisper drops "äh"; ADR 0084 handles those.
- **Repetitions** are passages of four or more words repeated verbatim, non-overlapping and merged. No vocabulary needed.

## Consequences

"Prägnante Sprache" has backing. A new language must bring these lists, or it fails at import.
