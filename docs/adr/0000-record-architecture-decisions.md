# ADR 0000: Record Architecture Decisions

## Context

Decisions are made incrementally, and the reasoning behind them is the hardest thing to recover later. Large documents go stale and go unread.

## Decision

Architecturally significant decisions are recorded as short ADRs in `docs/adr/`, numbered sequentially.

- An ADR states a decision **as it currently holds**. A change edits it in place; git is the history.
- A reversed decision is deleted. Its number is never reused.
- Format: a title, **Context** (a few sentences), **Decision** and **Consequences**, ideally under 40 lines. There is no Status section, because every ADR in the folder is in force. An ADR not yet built says so in one line under the title.
- No file or function names, no amendment sections, and no lists of related ADRs. Cite another ADR only where the link is essential.

## Consequences

The folder reads as the current architecture rather than its history. Superseded reasoning lives only in git.
