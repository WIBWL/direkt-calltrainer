# ADR 0102: One Place Decides a Shared Fact — Five Seams From the Tenth Review

## Status

Accepted.

## Context

A tenth architecture review (22 September 2026) read the code against ADR 0100 and ADR 0101, which had settled the previous round, and looked at the files that had changed most since. It found nine places where one fact was worked out independently in two or more of them. Three were already visible to a User:

- the downloaded feedback file left out the focus goal a point was filed under and never said a call had been a Rollentausch, though the page shows both — against the promise the file's own module docstring makes;
- the Gesprächsdauer row on the progress overview linked to a page that answered "Zu dieser Kennzahl liegen keine Werte vor", because the overview added the call length to its series and the detail level did not;
- `segments.py` folded a slice of a call without `reverse`, so the first metric that reads who rang would have measured a reverse the ordinary way round. Harmless only because `opening` is not in `SEGMENT_METRIC_KEYS` today.

None of these was a coding mistake at the site where it showed. Each was a fact — what the report says, which series a selection has, how a stored call is read back — that had no single owner, so two readers answered it differently and nothing failed.

## Decision

**A fact that more than one reader needs is decided in one module, and the readers ask it.** Concretely, five seams, each with the thing it now owns:

1. **`frontend/src/utils/reportOutline.ts`** — what the feedback report *says*: the meta line, each point with its moment and its focus goal already looked up, the two metric halves. The page renders it as JSX and `feedbackPdf.ts` as jsPDF; neither decides which sections exist. Pure and derived per render, which is not the joined record ADR 0101 §2 declined: without consent there is no stored detail at all, and the outline is then the meta line and nothing else.
2. **`backend/feedback/stored.py`** — reading a stored Session back: transcript order, the whole call's figures apart from the segment rows, the user's lines, the rows rebuilt into Turns, and a fold that takes the language *and the casting* from the Session itself. `rows.py` is the way in, this is the way out. It is not in `calls.py`, which folds the live call's Turns and imports no ORM on purpose.
3. **`deletion.remove`** — the order in which a Session and what hangs off it come out: follow-ups retired, reverses read while `origin_session_id` still links them, the Sessions deleted, then the reverses nothing plays any more. All three paths (one training, a withdrawal, the sweep) go through it. `retention.py` used to spell the sequence out itself, with the reason for the order written as a comment in both files.
4. **`progressStats.selectionSeries`**, served from `ProgressContext` — the series a selection has, read by the overview, a metric's page, a goal's page and (since it exists) the progress PDF.
5. **`reply_checks.ending`** — whether a finished reply ends the call *and* whether a goodbye must be spoken after it. These were two boolean expressions side by side in the orchestrator that had to agree, and the comments beside them recorded both ways they had failed to: a call that ended in silence, and a goodbye said twice.

Four smaller consolidations follow the same rule and need no ADR of their own: `heard.SpokenReply.cut` (both barge-in paths ask one question), `nudges.for_turn` (the precedence between the per-Turn nudges, beside the nudges themselves), `_loading.owned_session` (recorded in ADR 0100, which names it), and `hooks/useTrainingRun` (the committed Session's lifecycle, which was eight loose states in `App.tsx`).

**One behaviour changed with them**, and deliberately: the retention sweep now deletes a subject's expired reverses inside that subject's savepoint rather than once after the loop over all subjects. A failure there rolls back one subject instead of the whole sweep, which is what ADR 0067's savepoints are for. It is safe because a reverse is private to its author (ADR 0070), so no other subject's Session can be the one still playing it.

## Consequences

The three defects above are fixed at their source rather than at the site where each showed, and the fourth — a reverse-sensitive metric joining the segment list — cannot arise.

Every one of these modules is pure or takes its database handle from its caller (ADR 0099), so each is tested through its own interface: `reportOutline.test.ts`, `test_stored_session.py`, `test_reply_checks.py`'s ending table, `test_turn_nudge.py`, `useTrainingRun.test.ts` and a `selectionSeries` case. The frontend specs still render no components (ADR 0094).

The cost is one more module to find in four of the five cases. The rule for a later reader is the one this ADR is named for: before working a fact out where it is needed, look for the module that already answers it, and if two places would answer it, that is the seam.

A later review that proposes merging one of these back — for instance "the PDF could read the page's props directly" — is proposing the state this ADR removed, and the three defects above are what it looked like.
