# ADR 0093: The Feedback PDF Is Built in the Browser

## Status

Accepted.

## Context

The post-call screen offers the wrap-up as a file to take away. It began as the transcript alone and became the whole report: summary, strengths, improvements, the phase paragraph, the Kennzahlen with the loudness course, and the transcript last.

A file like that can be produced in two places. A server route (`GET /api/sessions/{id}/pdf`) would render it from the stored Session: one renderer, no fonts shipped to the client, and the same file whichever browser asks. Rendering in the browser needs a PDF library and the fonts on the client, and repeats layout the screen already expresses in CSS.

One case decides between them. A training run without consent is never stored (ADR 0066), yet the call runs, the transcript is shown and the download is offered — and for that training the file is the only copy there will ever be. A server route has nothing to render it from.

## Decision

**The document is built in the browser, from the data the screen already holds.** `FeedbackScreen` hands over the transcript it shows and the `SessionDetail` the post-call screen polled or the history page read. The file cannot say anything the page does not, because it is built from the same object.

**None of it is in the initial bundle.** jsPDF is a dynamic `import()`, and the fonts are fetched as assets on the press. Most trainings end without anyone wanting a file, and together they are the largest thing the frontend can pull.

**It is set in the app's own faces.** Hanken Grotesk and Schibsted Grotesk are OFL and therefore embeddable. They are converted from the bundled woff2 to TTF, which is what jsPDF can embed, and subsetted to Latin plus the marks German uses — about 50 kB for all three files. `drawable()` replaces a character outside the subset with "?", because a missing glyph is an invisible gap in a transcript, and a gap is worse than a visible replacement. The logo is optional: a failed fetch costs the tile in the banner, whereas a failed font fails the download, since the fonts decide how every line is set.

**It holds what the page holds, in the page's order,** with two deliberate differences. The next steps are left out: those offers write a Scenario when pressed, and paper cannot press them. Both halves of the metrics are printed one after the other, because paper has no switch between them (ADR 0082).

**Without a wrap-up it is a protocol, and says so.** Where there is no consent or the generation failed, the banner reads "Gesprächsprotokoll", the file is named `Calltrainer_Protokoll_…`, and the button offers a transcript rather than feedback. A user who presses a button offering feedback and receives a bare transcript was misled.

**Building and saving are separate functions** (`buildFeedbackPdf`, `downloadFeedbackPdf`), so the layout can be rendered and looked at outside a browser, which is how it was designed.

## Consequences

There are two renderers of one report: the screen in React and CSS, the file in jsPDF drawing calls. They agree because they read the same data and, for the loudness course, the same arithmetic (`utils/loudness.ts`) — not because anything checks the layout. A section added to the page has to be added to the file by hand.

The palette, the wordmark and the tracking of the small uppercase labels are constants copied from the stylesheet. A change there has to be repeated in `feedbackPdf.ts`.

The file for a training that was not stored exists only where the user saved it. That is the point of the decision, and also its limit: nobody can produce it again later.

The file carries the date it is built on, because `date` defaults to now. That is right after a call and wrong for a training opened from the history weeks later, which prints today's date: `SessionDetail` carries no start time to pass in. Closing that gap is a field on the detail route, not a change to this decision.
