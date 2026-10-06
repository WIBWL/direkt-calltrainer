# ADR 0094: The Frontend Is Checked by a Strict Compiler, a Narrow Test Suite and the Hook Rules

## Context

There is no CI. The frontend is verified when the image builds. A stale hook dependency list is the one defect class here that is both likely and silent.

## Decision

1. **`tsc` at maximum strictness** is the broad check, specs included. No flag is relaxed to make a change compile.
2. **Tests only where the compiler and a manual run cannot see:** audio races, pure decision tables, the sentences a screen claims about a person, and static invariants of the source. No component rendering.
3. **ESLint with only `rules-of-hooks` and `exhaustive-deps`**, as errors, with `reportUnusedDisableDirectives`. It is the first step of `npm run build`. A remaining disable comment is a checked exception carrying its reason.

## Consequences

The image build fails on a hook violation. A regression in what a screen shows is caught only by looking at it, and accessibility is not checked automatically.
