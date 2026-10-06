# ADR 0092: One Stylesheet, Not One per Component

## Context

Per-component stylesheets would add locality, but 53 of `index.css`'s classes are styled from more than one section. Their winning rule depends on concatenation order, which per-component imports would hand to the module graph. No type check, test or build would notice the difference.

## Decision

One `index.css`, sectioned by comments that serve as its index. `stylesheet.test.ts` fails on a class no component names. Runtime-built classes are an explicit allowlist, and a second test fails when an allowlist entry has no rules left.

## Consequences

Dead rules cannot accumulate. Locality is given up. If the sheet is ever split, use one module that imports the parts in a stated order, never per-component imports.
