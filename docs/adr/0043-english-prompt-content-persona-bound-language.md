# ADR 0043: English Prompt Content, Session Language Bound to the Persona

## Context

Instructions and conversation language were mixed, and display text doubled as prompt text.

## Decision

- Everything the model reads is authored in English.
- The spoken language is the selected Persona's language, fixed at call start. Scenarios are language-neutral, so every pairing stays valid.
- Prompt fields and display fields are separate columns. Built-ins' prompt fields are not served to the client.
- What cannot be English is keyed by language in a language pack: the example exchange, the regexes over the user's speech, and the spoken fallback lines.

## Consequences

Adding a language means Personas with that language and one language-pack entry. A character in another language is a second Persona row. Authoring means writing for two audiences.
