# ADR 0072: The Scenario Category as a Closed Vocabulary

## Context

At seventeen built-ins the selection no longer reads at a glance, and the origin filters say *whose* a Scenario is, not what kind of call. A former free-text type field was inconsistent, two languages, and read by nothing.

## Decision

- `scenario.category` is one of `operations`, `requirements`, `pricing`, `closing`, or NULL, enforced by a CHECK. They refine F-03's three call contexts, with offer-and-pricing split into negotiating and closing. German labels name the occasion and live in one frontend map.
- It is display and filter only. **The model never reads it.**
- It is optional for authored Scenarios; every seeded one has a category, enforced by a test.
- The selection screen has two independent filter rows, origin and category. Each option shows how many Scenarios it would yield under the other row, and each row is a `radiogroup`, not a range input.

## Consequences

A fifth category is one constant, one label and a constraint swap. A much larger library would need search, not more filters. Sales proximity, a second axis, stays out of the data model.
