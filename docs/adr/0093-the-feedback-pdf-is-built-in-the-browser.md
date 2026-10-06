# ADR 0093: The Feedback PDF Is Built in the Browser

## Context

The wrap-up is offered as a file. A server route cannot render it for a training run without consent, which was never stored, and for that training the file is the only copy.

## Decision

- The PDF is built in the browser from the data the screen already holds, so it cannot say anything the page doesn't.
- jsPDF and the fonts load only when the button is pressed.
- It is set in the app's own OFL faces, subsetted to Latin. A character outside the subset prints as "?" rather than leaving a gap.
- It follows the page's content and order, except that the next-step offers are left out and both metric halves are printed.
- Without a wrap-up it is a "Gesprächsprotokoll" and is named as one.
- Building and saving are separate functions.

## Consequences

There are two renderers of one report, kept in step by hand, and the palette constants are copied from the stylesheet. An unstored training's file exists only where the user saved it.
