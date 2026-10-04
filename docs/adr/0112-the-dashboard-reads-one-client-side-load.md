# ADR 0112: The Dashboard Reads One Client-Side Load and Adds No Endpoint

## Status

Accepted, and written after the fact. The arrangement it records has been built since F-13's first stage and argued at length in `docs/dashboard-concept.md` section 9; what it never had was an ADR, so the decision lived only in a concept document beside the screen's visual choices. ADR 0113 leans on it for the report on paper.

Narrows nothing and reverses nothing. It states the data path all three dashboard screens share, and the three alternatives that were declined.

## Context

The progress view (F-13) reads a user's whole training history, groups it per metric, describes each metric's spread, counts what the wrap-ups said, and does that again on two detail levels and once more into a PDF. Every one of those is an aggregation over many Sessions, and the obvious shape for an aggregation is a route that performs it.

`GET /api/progress?period=…` was in fact proposed. It was never built, and the reason it was never built has held up well enough to be worth recording before somebody proposes it again — which they will, because it is what the shape of the problem suggests.

## Decision

**The dashboard reads `GET /api/sessions` and nothing else. Everything above that is a pure function in the browser.**

Four parts.

### No endpoint of its own

`GET /api/sessions` already carries each Session's Measurements (ADR 0064) and, since ADR 0080's amendment, the focus goal and text of each tagged wrap-up point. Every figure the dashboard shows was measured when its call ended and stored with it (ADR 0051); nothing is computed afresh from anything the listing does not hold.

A second route to those numbers would be the first place they could disagree. Not in theory: the same defect was found twice inside the browser alone, where the progress report rebuilt the readings the screen had already built (ADR 0102's amendment) and the screen and the calendar each kept their own idea of which trainings count (ADR 0034's second amendment). A server route computing the same aggregates in Python, against the same rows, with its own idea of which Sessions qualify, is that failure with a network hop through the middle of it.

The grouping lives in `utils/progressStats.ts`, the counting of statements in `utils/goalMentions.ts`, what each is *claimed* to mean in `utils/progressOutline.ts`. All pure, all tested through their own interfaces, none of them able to reach a database.

### No aggregate table

Six months of retention (ADR 0067) caps what one account can hold at an order of magnitude a plain query carries. A materialised aggregate would be a second truth that every deletion has to drag along: withdrawing consent, deleting one training and the retention sweep all remove Sessions (ADR 0066, ADR 0067), and each would then have to remember to correct a stored total. A figure that survives the training it was computed from is the worst kind of leftover, because it looks authoritative.

### The selection is a filter in the browser, and lives in the URL

The period and the occasion narrow an already-loaded list, so changing either costs no request. They sit in the URL (`?trainings=`, `?anlass=`) rather than in component state, which is what makes a reload and a shared link show the same screen — and that is the reason `docs/dashboard-concept.md` section 7 makes the two detail levels routes at all. A default stays out of the URL, so the plain path is the one people copy.

### One load for all three screens

`ProgressContext` is a layout route around the overview, a metric's page and a goal's page. Before it, each level called the loader itself, so every step into a detail and back re-fetched the whole history and drew "Wird geladen …" over a screen that had just been painted — and, worse, the period switch reached the overview only, so a tile saying "aus 5 Trainings" linked to a page drawn over every stored one. Two screens describing the same metric differently is the thing this whole area is most prone to.

The loader reads up to ten pages of a hundred (`useProgressData.MAX_PAGES`). It read exactly one until September 2026, and the three counted figures at the top then described a page while reading as absolutes — not incomplete but wrong, on any account past a hundred trainings. A thousand is far beyond what six months of retention can hold; `truncated` is the honest answer for an account that would nevertheless pass it, and the screen says so.

## Consequences

The dashboard's correctness is a property of pure functions over a payload, which is why its specs can pin the sentences the screen says out loud without rendering a component or touching a database (ADR 0094).

It also means the client does the work. Ten sequential requests and a grouping pass over a thousand rows is the worst case, and it is fine; if it ever stops being fine, the fix is to narrow what the listing carries, not to add a route that carries a different answer.

The listing is therefore load-bearing for two features at once, and what it may carry is constrained by ADR 0064 — no wrap-up prose, `detail_json` withheld — with ADR 0080's amendment the one deliberate widening. Anything the dashboard needs in future is a field on that route or a pure function over it, and the burden is on the proposal to show it can be neither.

Nothing here is about what the dashboard is allowed to *say*; that is ADR 0065 and ADR 0004, and they are untouched.
