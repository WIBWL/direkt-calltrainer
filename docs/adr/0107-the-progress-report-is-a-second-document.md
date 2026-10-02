# ADR 0107: The Progress Report Is a Second Document on the Same Page Frame

## Status

Accepted, and written after the fact. The report has existed since F-13's fourth stage; ADR 0093 covers the feedback file and never mentions this one, so the second of the two documents this application writes had no decision recorded anywhere but in `docs/dashboard-concept.md` section F. The companion to ADR 0093, and it takes its data path from ADR 0106.

## Context

The progress view is what somebody takes into a conversation with a trainer, an instructor or a supervisor. Until the report existed the only way to take it was a screenshot per block, which is how the need was found — from use, not from the plan. It was added as stage 4 and the concept says so.

Two things had to be decided and only one of them had a precedent. ADR 0093 settled that the feedback file is built in the browser, but on a reason that does not transfer: without consent there is no stored Session at all (ADR 0066), so for that file the browser holds the only copy and a server route could not serve the one case where the download matters most. Here there is stored data by definition — no storage, no history, no dashboard.

## Decision

**A second PDF, built in the browser from the numbers the page already holds, on the page frame extracted from the first.**

### Built in the browser, for ADR 0106's reason rather than ADR 0093's

The figures are in the client because the dashboard loaded them there. A server route would be a second path to the same numbers, which ADR 0106 rules out, and it would additionally have to reimplement both switches to know which trainings the reader had selected. `buildProgressPdf` is exported without a caller in this repository, exactly as `buildFeedbackPdf` is, so the layout can be rendered and looked at outside a browser — which is how it was designed and checked.

jsPDF and the fonts are fetched on the press, so neither sits in the initial bundle.

### It carries what the page carries, in the page's order

The record of what was trained, the focus goals, what the wrap-ups keep naming, and every metric with its usual range and a drawn course. Read over the trainings the switches select, which the first page states in words, since the file has no switches to show.

What it says is not decided here. `utils/progressOutline.ts` decides the readings and this file renders them, which is ADR 0102's rule applied to the second report after it had already drifted apart from the first rendering (see that ADR's amendment).

### Three things are deliberately absent

**The calendar.** Twelve month grids are four pages of squares. What a reader takes from one — how many trainings fell in which month — is a list, and a list is what paper is good at.

**Every judgement.** No target, no traffic light, no arrow, no difference between an earlier and a later value, no aggregate (ADR 0004, ADR 0051, ADR 0065). On paper the rule is sharper than on screen: a sheet handed to somebody else reads as an assessment of the person unless it says otherwise, so it says otherwise twice, under the title and at the foot. This is also why the report has no equivalent of the screen's "i" — there is nothing to open, so anything that must be read has to be in the running text.

**The practice suggestion.** Block E ends in a button that starts a call, and paper cannot press it.

### One page frame for both documents

`utils/pdfDocument.ts` holds the geometry, the palette taken from `index.css`, the app's own subsetted faces, the navy banner with the wordmark, the fact rows, the section heading, the wrapped paragraph and the page break. `openSheet(title)` returns a `Sheet` whose `y` is the one cursor a document moves, and everything that draws advances it — an accessor rather than a field, because handing a cursor back and forth as a return value is what a layout written this way gets wrong first.

It was extracted *from* the feedback file rather than written beside it. The alternative was a second four-hundred-line module in which a change to the letter-spacing of an eyebrow would reach one document and not the other, with nothing to say so. The extraction was verified rather than assumed: the same feedback file rendered before and after came out byte-identical apart from the document id jsPDF derives from the creation timestamp.

## Consequences

The two documents this application writes look like one application, and a change to either's chrome reaches both by construction.

A reader can hold the sheet against the screen and find the same sentences, which is the point of the outline sitting under both. The one thing that legitimately differs is form: a tile has a chart and a tally where a paragraph has a sentence, and `goalSentence` in `progressPdf.ts` is where that difference is allowed to live.

The report states, on its first page, how many of the selected trainings its courses actually rest on (ADR 0034's second amendment). A sheet cannot be asked why a course covers fewer calls than the line above it names.

Nothing about this is a route, a job or a stored artefact. The file exists for as long as the browser tab that made it, and re-pressing the button makes it again.
