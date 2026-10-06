# ADR 0113: The Progress Report Is a Second Document on the Same Page Frame

## Context

Users take the progress view to a trainer or supervisor and were doing it by screenshot.

## Decision

- A second PDF is built in the browser from the numbers the dashboard loaded (ADR 0112's reason, not ADR 0093's). jsPDF and the fonts load on press.
- It carries the page's content in the page's order, with readings decided by `progressOutline.ts`. The first page states which trainings were selected and how many the courses rest on.
- Left out on purpose: the calendar (as a list instead), every judgement (it says so twice, since paper reads as an assessment), and the practice button.
- Both PDFs share one page frame, `utils/pdfDocument.ts`, extracted from the first so that a chrome change reaches both.

## Consequences

The two documents look like one application. Sheet and screen say the same sentences; only the form differs.
