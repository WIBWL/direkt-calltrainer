# ADR 0100: The Follow-Up and the Reverse Stay Two Routes, Sharing What Must Not Drift

## Status

Accepted.

## Context

Two routes turn a finished Session into a Scenario the User owns: `POST /api/sessions/{id}/follow-up` (F-60, ADR 0069) and `POST /api/sessions/{id}/reverse` (F-61, ADR 0070). Since ADR 0069's amendment they share their shape down to the status codes — 404 for an absent or foreign Session, 409 for one there is nothing to build from, 503 for a model that would not answer, idempotency through a UNIQUE column — and `tests/test_followup_scenario.py` and `tests/test_reverse.py` are deliberately written alike, so that a difference between the routes shows up as a difference between the files.

Every architecture review of this code found the pair, and they disagreed about it. Five runs proposed one choreography with the two as configurations of it. One argued the opposite: a shared flow would need four or five parameters and a callback per step, and would be harder to read than two honest copies — the argument `api/sessions.py` already makes for its two `_feedback` shapes. A later run added the case for merging that weighed most: the precondition *had* drifted, with the reverse refusing a call under three user utterances on the screen but not on the server, and ADR 0087's "offer by weakness" would add a third copy.

## Decision

**The two routes stay two.** Their differences are the features, not noise around one: a follow-up needs improvement points and a reverse does not; a reverse refuses a reverse and a follow-up has no such case; one drafts six authorable fields through its own re-asking loop, the other a four-field briefing through `llm.complete_json`; they store different columns, are reached by different restore functions and answer with different payloads. A shared driver would carry each of those as a parameter, and the reader of either route would have to read the driver and the configuration to find out what happens.

**What must not drift is shared, and only that:**

- the ownership read — `_owned_with_wrapup` in `api/sessions.py`, the one query that decides whether the caller may build anything from this Session;
- the length precondition — `MIN_USER_UTTERANCES` and `_too_short`, pinned against the client's `MIN_USER_TURNS`;
- what a prompt asking for JSON forbids — `llm.JSON_ANSWER_NEVER`;
- how a field a model wrote is held to its cap — `authored_text.fit`, at a word boundary with an ellipsis.

**The two test files stay alike**, as the detector for everything not in that list.

**A third kind revisits this.** When ADR 0087's offer by weakness, or anything else that builds a Scenario from a Session, is written, it starts from the four shared pieces above; if it then needs more than they give it, three copies are the point at which one driver pays for its parameters, and that is decided then, with three real shapes to fit rather than two.

## Consequences

The two routes remain about two hundred lines each with a visible family resemblance, and a change to one still has to be carried to the other by hand wherever the list above does not reach — the parallel test files are what catches a forgotten one.

The drift that prompted the question, the missing length check, is fixed and pinned, and the pieces most likely to drift next are single definitions.
