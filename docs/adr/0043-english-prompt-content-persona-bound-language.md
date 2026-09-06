# ADR 0043: English Prompt Content, Session Language Bound to the Persona

## Status

Accepted (supersedes ADR 0022)

## Context

ADR 0022 modelled Language as a third independent Session parameter, chosen per Session alongside Scenario and Persona, so that one Persona could run in any supported language without being duplicated. ADR 0041 then moved Personas and Scenarios into the database and gave each Persona exactly one Language and one voice, including the KugelAudio voice id that ADR 0040 made the default backend's. Since then the Session's language follows from the selected Persona and there is no language control in the setup UI, so ADR 0022 no longer describes the system — but no decision recorded why, and the arc42 constraint C-01 and glossary still describe the superseded model.

Making this explicit matters now because KugelAudio offers both German and English voices, so a second language is within reach for the first time since ADR 0006 was superseded. Attempting it exposes where the language actually sits today, which is in three places at once: the Persona's `haltung`/`verhalten` text and the Scenario's `beschreibung` are German prose interpolated straight into the prompt; the prompt frame in `backend/session/orchestrator.py` is English except for its German example exchange, the closing/postpone regexes and the spoken fallback closing line; and `language_code` names the output language. Only the last of these is modelled as language. In particular `scenario` carries no language column, so an English Persona paired with any existing Scenario would be an invalid combination, which would break the property from ADR 0001 and ADR 0015 that any Persona can be combined with any Scenario.

A further conflation sits in the same fields: `rolle` and `beschreibung` are both prompt input and user-facing UI text — `/api/personas` and `/api/scenarios` serve them, and the setup cards render them as their subtitles — while `haltung` and `verhalten` are prompt-only and never shown. The two roles have different audiences and want different languages, but share one column.

## Decision

We will separate the language of the instructions from the language of the conversation, and separate prompt content from display content.

All content the LLM reads is authored in English: the Persona's role, traits and behavior, the Scenario's call context, and the prompt frame that already is. The Session's spoken language is determined solely by the selected Persona's `language_code` and fixed at Session start, expressed to the model as the existing `Reply exclusively in <language>` instruction. Scenarios stay language-neutral and get no language of their own, so every Persona × Scenario pairing remains valid and the free combination of the two survives unchanged.

Fields consumed by the prompt and fields shown to the user become distinct. Display fields — the Persona's name and role label, the Scenario's title and teaser — stay in the UI language and remain what `/api/personas` and `/api/scenarios` serve. Prompt fields are English, and are not part of the selection API.

The part of the prompt frame that cannot follow the instructions into English is keyed by `language_id` instead: the example exchange, because it demonstrates the register of a phone call in the target language rather than instructing the model; the closing-intent and postpone regexes of ADR 0037, because they match the user's own transcribed speech; and the fallback closing line of ADR 0038, because it is spoken aloud.

## Consequences

Adding a language becomes a bounded piece of work: a Persona row carrying that `language_code` and a voice for both TTS backends, plus one entry per language-keyed constant in the orchestrator. No Scenario changes, and no per-Session language setting to design or explain, which keeps the setup minimal in the sense of ADR 0013.

Instructions in English also play to where instruction-following is most reliable on the university-hosted model of ADR 0011, and it removes the mixed-language prompt that a German Persona description inside an otherwise English frame produces today.

The cost is the one ADR 0022 set out to avoid: a Persona is no longer language-neutral. Its name is spoken and introduced by the model, so the same character in another language is a second row rather than a translation, and the library grows per language. We accept that deliberately — it buys curated, language-specific content instead of the request-time translation whose fidelity ADR 0022 itself named as its open trade-off, and it fits ADR 0002's model of the library as the thing that grows.

Schema and content both have to follow: the `persona` and `scenario` tables need their prompt fields separated from their display fields, with a migration and the seed content of ADR 0041 rewritten in English. Authoring a library entry now means writing for two audiences — an English prompt text and a UI-language label — which also raises the bar for the user-authored Personas of ADR 0024. A Persona whose `language_code` has no entry in the orchestrator's language-keyed constants is a configuration error that only surfaces when a Session starts.
