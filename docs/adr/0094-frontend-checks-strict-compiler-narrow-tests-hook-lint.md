# ADR 0094: The Frontend Is Checked by a Strict Compiler, a Narrow Test Suite and the Hook Rules

## Status

Proposed. The first two parts describe what is in place. The third — ESLint restricted to the React hook rules — is not built.

## Context

There is no CI workflow in the repository and no Node toolchain on the development machine. The frontend is verified when the image is built: `docker build --target frontend-build` runs `npm ci && npm run build`, and `build` is `tsc && vite build`. Whatever that step does not catch reaches the browser.

**The compiler runs at maximum strictness** (`frontend/tsconfig.json`): `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noUnusedLocals`, `noUnusedParameters`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `verbatimModuleSyntax`. The test specs are type-checked with everything else, since a fixture had once drifted out of shape while they were excluded. CLAUDE.md still describes them as excluded; `tsconfig.json` is the current state.

**The test suite is deliberately narrow** (Vitest, jsdom, hand-written Web Audio and WebSocket fakes in `src/test/setup.ts`):

- `useStreamedAudioPlayback`, `useSessionSocket` and `useBargeIn` — the barge-in races that the compiler cannot see and a click-through cannot reproduce (ADR 0035).
- `trainingFlow.test.ts` — the pure transition table of the training flow (ADR 0096).
- `stylesheet.test.ts` — a static check that no rule outlives its markup (ADR 0092).

No component is rendered to check what it shows.

**What neither catches is a hook's dependency list.** Five `eslint-disable-next-line react-hooks/exhaustive-deps` comments are in the source (`App.tsx` three times, `useSessionSocket.ts`, `MicCheck.tsx`), although ESLint is not installed: they record an intent, and nothing enforces the rule they switch off. `beginSession` in `App.tsx` declares no dependencies and closes over `advance`, which works only because `advance` happens to keep one identity. `useBargeIn.ts` documents the same hazard from the other side: a single dependency added to the wrong callback would freeze barge-in against a dead socket, with no type error and no failing test. A stale closure is the one class of defect in this frontend that is both likely and silent.

## Decision

**1. The compiler is the broad check.** The strict flags stay, and none is relaxed to make a change compile.

**2. Tests are written where the compiler and a manual run cannot see:** timing and races, pure decision tables, static invariants of the source. Rendering is not tested. The screens change with nearly every feature, and a snapshot suite would pin wording and markup rather than behaviour.

**3. ESLint runs with `eslint-plugin-react-hooks` and nothing else** — `rules-of-hooks` and `exhaustive-deps` — as part of `npm run build`, so that the image build fails on a violation. No style or formatting rules: formatting is not what breaks here, and a large rule set would bury the two rules that matter under warnings nobody reads. The existing disable comments become checked exceptions, each keeping its reason, and dependency lists that are merely incomplete are completed.

### Rejected

**No linter, and the disable comments deleted.** It keeps the toolchain smaller, but it leaves unchecked the one defect class the code already documents as dangerous.

**Component tests with Testing Library.** Considered for the post-call screen, which has the most branches. Its branches depend on server data and on the flow state, and a test there would mostly assert copy; the decisions behind the branches already live in pure functions (`trainingFlow.ts`, `utils/metrics.ts`, `utils/progressStats.ts`) where they can be tested without rendering.

## Consequences

The build gains a lint step and a development dependency. Effects that are deliberately keyed on an object's identity — the committed Session in `App.tsx` and `useSessionSocket.ts` — keep a disable comment, now as a checked exception rather than a note.

A regression in what a screen shows is still caught only by looking at it. The accessibility of the markup is not checked automatically either (see ADR 0097).

Because there is no CI, all of this runs only when somebody builds the image. The deploy builds the same image, so nothing reaches a server unchecked, but a broken commit can sit on a branch until then.
