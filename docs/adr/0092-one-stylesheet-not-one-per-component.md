# ADR 0092: One Stylesheet, Not One per Component

## Status

Accepted. Records a refactor that was measured and declined, so that it is not proposed again without the measurement in hand. Pinned by `frontend/src/stylesheet.test.ts`.

## Context

`frontend/src/index.css` is 8,300 lines, imported once (`main.tsx`), and serves 74 components. The obvious move is one stylesheet per component, imported from the component — Vite supports it, and it is what most React codebases do.

The case for it is real: a rule outlives the markup that needed it and nothing says so. Fourteen classes had accumulated that way, every one of them residue from a change this project had recorded and shipped — the privacy statement's draft banner after the two gaps were filled in, the header's sign-out button after it moved to the profile screen, the brand mark after `BrandName.tsx` took over drawing it, the per-figure method paragraphs ADR 0077 moved behind an "i".

The case against it was not obvious and had to be measured.

## Decision

**One stylesheet.** It is already sectioned — 52 blocks, each with a comment naming the feature and the ADR it serves — and those section comments are load-bearing documentation, not decoration.

### What the measurement found

**53 of its 613 classes are styled from more than one section.**

| class | sections |
|---|---|
| `.card` | 12 — profile, retention, consent, focus, follow-up, reverse, metric detail, the period switch, … |
| `.consent-button` | 6 |
| `.info-details` / `.info-summary` / `.info-body` | 4 each |
| `.profile-page`, `.progress-page` | 4 each |

For those 53, which rule wins is decided by the order the sheet is concatenated in. One file gives that order deterministically. Per-component `import "./Foo.css"` hands it to the **module graph** — the order React happens to import components in.

That is the disqualifying property, and it is specifically about what this project can verify. `tsc` cannot see it. The Vitest suite cannot see it. The production build succeeds either way. The symptom is a visual regression on a screen nobody opened during the change. The shared `InfoDetails` component is the clearest case: four different contexts deliberately extend its three classes, and which extension wins would become an accident of import order.

### What was done instead

The fourteen dead classes were deleted — 155 lines, a pure deletion — and `frontend/src/stylesheet.test.ts` now reads `index.css` and the source as text and fails on a class no component names. It is the one test in the frontend suite that renders nothing, and it earns the exception by being static: two sets of files and a string comparison, no jsdom, no fakes.

Classes assembled at runtime (`card-origin-${…}`, the die's six faces, the traffic light's colours, and four more) are an explicit allowlist rather than a pattern, because a rule nothing can reach is exactly what the test is for and a clever matcher would quietly readmit one. A second test fails when an allowlist entry outlives its own rules, so the exemption cannot widen on its own.

## Consequences

The sheet keeps growing, and nothing here changes that. A reader looking for a component's styles still goes to one file and finds the section comment, rather than opening a file beside the component.

The section comments are now load-bearing: they are the only index into 8,300 lines.

Dead rules can no longer accumulate silently, which was the real benefit the split promised. What the split additionally promised — locality, a component's styles beside it — is not delivered and is the price of this decision.

**If it is ever split anyway**, those 53 classes are the hazard list, and the way to do it is a single module that imports the parts in an explicit, stated order — never per-component imports, which is the arrangement that makes the order invisible. The count is reproducible: group rule heads by the section comment above them and report the classes appearing under more than one.
