# ADR 0064: A Per-User Session History, With Ownership as the Query

## Status

Accepted. Supersedes the "no listing endpoint" position recorded in `CLAUDE.md` and implied by ADR 0050.

## Context

Until now the only way to reach a stored Session was `GET /api/sessions/{extern_id}`, and that was deliberate: the wrap-up was reachable for as long as the post-call screen was, plus a `sessionStorage` entry surviving a reload. There was no listing route and no way to enumerate a user's past at all. That position made sense while `subject_id` was the unenforced pseudonym of ADR 0031 — with no identity behind the column, "the caller's Sessions" was not a set the backend could name.

Three things have since changed. ADR 0009's Keycloak integration landed, so `subject_id` carries the real `sub`, written straight from the WebSocket handshake. ADR 0050's ownership check went in, so the detail route already compares that column against the caller. And Sessions have been accumulating under real identities ever since, which means the data F-13 (Aufzeichnung des Fortschritts, SHOULD) and F-48 (Trainingshistorie, COULD) need already exists — it is merely unreadable.

ADR 0028 and ADR 0052 both named this moment explicitly as the condition for revisiting their own index decisions: "once the read side (Session history, aggregated Feedback, F-13/F-48) is built against real query patterns rather than guesses."

## Decision

`GET /api/sessions` returns the caller's own finished Sessions, newest first, paginated.

**Ownership is the query, not a check on its result.** The route filters by `subject_id = caller.sub` in the `WHERE` clause rather than selecting rows and rejecting the foreign ones afterwards. The distinction matters: a filter cannot be forgotten for one code path the way a check can, there is no id for a caller to supply and therefore nothing to guess at, and the 404-vs-403 question ADR 0050 had to answer for the detail route does not arise here at all — a Session that is not yours is not absent from the response, it was never a candidate for it.

**The response carries each Session's Measurements, but not their `detail_json`.** One request therefore serves both screens: the history list reads the metadata, the progress view reads one value per metric per Session, which ADR 0051's uniqueness constraint already guarantees is exactly one. `detail_json` is dropped because it holds a metric's course over the call — the loudness curve alone outweighs everything else in the payload, multiplied by a page of Sessions, and no view spanning several Sessions plots it.

**It does not carry the wrap-up text, but it does say whether one exists.** The narrative belongs to the detail route — a page of summaries would dwarf everything else here, for a view that shows none of them. Whether a wrap-up exists is a different matter: it decides what a row promises when it is clicked, so the list carries `has_feedback` and, where that is false, `feedback_status` to say why not.

The two are separate fields because they answer separate questions, and neither is safely derived from the other: `has_feedback` is "is there something to open", `feedback_status` distinguishes a wrap-up still being generated from one that will never arrive. A job reading `done` whose feedback row is missing is exactly the case a single derived field would paper over.

Both travel under names of their own. `status` on this route is `session.status` (`completed`/`aborted`), the schema's own value passed through per ADR 0057, and it keeps meaning only that — the detail route already overloads `status` with the job's state, and a reader should not have to know which route a payload came from to know what the word means there.

*(This paragraph replaces an earlier decision to omit the wrap-up's state entirely. That was wrong in a way only the built screen showed: without it the history could not distinguish a Session it could open from one it could not, and the detail screen filled the gap by polling a days-old Session for a wrap-up that was never coming.)*

**The order is total.** `started_at DESC, session_id DESC`. The timestamp alone is a partial order — `started_at` comes from the client's `session.activate`, so two Sessions can genuinely share one, and an order Postgres is then free to choose changes between reads. Under pagination that is not cosmetic: a row appears on two pages, or on none.

**Pages are bounded**, defaulting to 20 and capped at 100. The cap exists because the progress view's natural instinct is to ask for everything.

`session.subject_id` is indexed (migration `18f5098dfb1b`) — this route filters on it and on nothing else.

## Consequences

F-48 becomes possible and F-13 has its data source; both had been blocked by construction rather than by effort. The endpoint is small because the work was already done — the schema, the ownership semantics and the per-Session statistics all existed, and what was missing was a way to ask for more than one row.

The reversal has a real cost: a user's Sessions are now enumerable by that user, which the previous design avoided entirely by having no route that returned a set. This makes the retention and deletion obligations ADR 0031 left open more pressing rather than less — a history the user can see is one they will reasonably expect to be able to delete, and self-service deletion (promised by ADR 0034, cascades in place and tested, no route yet) is now the conspicuous gap. It is deliberately left to its own change rather than bundled here.

Pagination is offset-based, which is the wrong tool if Sessions are ever written while a user pages through them — an insert shifts every subsequent row by one. At the volume of a pilot, where a user writes a Session every few minutes at most and reads their history between calls, this cannot bite; keyset pagination is the answer if it ever does.

Nothing here decides what the progress view may *say* about the values it plots. That is ADR 0065.

## Amendment: tagged points travel with their text

Since ADR 0080 every `feedback_point` carries the focus goal it is about, and the listing carries those tags as `feedback_goals`. They went on the wire without their text, on the reading of "it does not carry the wrap-up text" above.

That reading is narrowed here: **a tagged point travels with the sentence it was written as.** The progress view's second level has to say what the wrap-ups wrote about a goal, not only how often they wrote it (`docs/dashboard-konzept.md`, section 7), and six of the fourteen focus goals have nothing else behind them at all — for them the counted mentions *are* the content, and a count with no way to read what was counted asks the user to take a number on trust.

The payload argument does not apply at this size. What the original decision keeps off the listing is `detail_json`, a sampled curve per metric per Session, which is three orders of magnitude larger than a tagged point and which no cross-Session view plots. A wrap-up carries a handful of points, each a sentence or two.

What stays on the detail route is the wrap-up as a text: the summary, the phase-language paragraph, `tone_fit`, and any point the model left untagged. So the listing still cannot reconstruct a wrap-up; it carries what can be counted, plus the wording of each thing counted.

One thing this makes visible that was already true: `_feedback_goals` walks `feedback.points` and each point's `focus_goal`, which the listing query did not eager-load — a page of 20 wrap-ups cost a query per wrap-up and one per tagged point. Both now hang off the existing `selectinload`, so a page is a fixed number of queries again, as the paragraph on batching above always claimed.
