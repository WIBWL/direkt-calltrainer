# ADR 0000: Record Architecture Decisions

## Status

Accepted

## Context

Architecture in agile projects cannot be described or fixed in one go. Decisions are made incrementally over the life of the project, and the documentation has to accommodate that.

Agile methods are not opposed to documentation as such — only to documentation without value. Documents that help the team itself do have value, but only for as long as they are kept current. Large documents are never kept current; small, modular ones at least stand a chance.

Large documents also go unread. On many projects the specification ends up larger in bytes than the source code, which makes it effectively impossible to open, read, or update. Bite-sized pieces are easier for every stakeholder to consume.

The hardest thing to track over a project's lifetime is the motivation behind individual decisions. Someone joining later who does not know the reasoning has only two options:

**Accept the decision blindly.** That is fine while the decision still holds. If the context has changed, however, the decision really ought to be revisited. Once enough unexamined decisions accumulate, the team becomes afraid to change anything and the project collapses under its own weight.

**Reverse the decision blindly.** This may also be the right move. But without knowing the motivation or the consequences, reversing it risks damaging the value of the system — for instance when the decision supported a non-functional requirement that has not yet been tested.

Both forms of blindness are to be avoided.

## Decision

We will keep a collection of records for all "architecturally significant" decisions — those affecting structure, non-functional characteristics, dependencies, interfaces, or construction techniques.

An architecture decision record (ADR) is a short text file in a format loosely modelled on an Alexandrian pattern. Each record describes a set of forces in tension and the single decision taken in response. The decision is the centrepiece, so the same force may well appear in several ADRs.

Specifically:

- ADRs live in the project repository under `doc/arch/adr-NNN.md`.
- We use a lightweight markup language such as Markdown.
- ADRs are numbered sequentially and monotonically. Numbers are never reused.
- If a decision is reversed, the old record stays in place and is marked as superseded. It remains relevant to know that this once was the decision, even though it no longer is.

Each ADR has only a handful of sections:

**Title** — a short noun phrase, e.g. "ADR 1: Deployment on Ruby on Rails 3.0.10" or "ADR 9: LDAP for Multitenant Integration".

**Context** — the forces at play: technological, political, social, project-local. These forces are usually in tension, and that tension should be named. The language here is value-neutral; it simply states facts.

**Decision** — our response to those forces, written in full sentences and active voice: "We will …".

**Status** — *proposed* while the stakeholders have not yet agreed, *accepted* once they have. If a later ADR changes or reverses the decision, it becomes *deprecated* or *superseded*, with a reference to its replacement.

**Consequences** — the resulting context once the decision has been applied. All consequences are listed, not only the favourable ones. A decision may have positive, negative, and neutral effects, and all of them will shape the team and the project going forward.

The whole document runs to one or two pages. Each ADR is written as if it were a conversation with a future developer: full sentences organised into paragraphs. Bullets are acceptable for visual rhythm, never as an excuse for sentence fragments.

## Consequences

One ADR captures exactly one significant decision for one specific project. It should be something that affects how the rest of the project runs.

The consequences of one ADR are very likely to become the context for later ones. This mirrors Alexander's idea of a pattern language: large-scale responses create the spaces that smaller-scale ones fit into.

Developers and stakeholders can read the ADRs even as the team composition changes over time.

The motivation behind earlier decisions stays visible to everyone, present and future. Nobody is left wondering "what were they thinking?", and the right moment to revisit an old decision becomes apparent from changes in the project's context.
