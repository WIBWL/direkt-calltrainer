# ADR 0101: Four Structural Proposals Declined, So That They Are Not Proposed Again

## Status

Accepted.

## Context

Nine architecture reviews of this code, run between 12 and 17 September 2026, were consolidated into one prioritised list and worked through on 21 September. Most items were built. Four were examined and deliberately left as they are. Each of them will look like an improvement to the next review that reads the code cold, because the reason against it is not visible where the code is. Without a record, a tenth review lists them again, and the time goes into re-deriving an answer that already exists.

## Decision

**1. The metric inventory does not absorb readings and segment membership.** The proposal was to move `readings._READINGS` and `segments.SEGMENT_METRIC_KEYS` onto `MetricDef`, so that a metric entry carries all its consequences. Declined: `readings.py` is the one place the derived reading is kept apart from the stored measurement (ADR 0091), and every review that looked at it listed it as a module to leave alone; the segment list is a statement `segments.py` makes about which figures stay defined on part of a call, with its reasons written beside it and a test pinning it — moving it would put the list in one module and its justification in another. `metrics.py` is also seven lines under pylint's module ceiling. What the proposal was after — a new metric that is silently missing an explanation — is already caught by `tests/test_metric_readings.py`, which requires one for every active metric.

**2. The frontend keeps the finished call's transcript and its stored detail apart.** The proposal was one `FinishedCall` record in place of the socket's transcript, the stored Session's `detail` and the `localStorage` copy. Declined: they are not three copies of one thing. Without storage consent (ADR 0066) there is no stored detail at all and the socket's transcript is the only copy of the call — the reason the PDF is built in the browser (F-64). A record that joined them would have to be optional in every field but one. The backend half of the proposal, where it was a real smell — seven positional arguments written out by two callers — was built as `persistence.FinishedCall`.

**3. The Scenario listing keeps its server-side order, and a Scenario's kind is decided where it is asked.** The proposal called the listing's sort dead, since the grid re-sorts by name, and counted nine places that decide what kind a Scenario is. The sort is read three times: `/next` breaks its ties by it, `recommend` uses the position, and the selection screen's `firstSelectable` falls back to the first card in server order. The nine decisions answer different questions — may it be edited, may it be drawn blind, which filter shows it, which group it sorts into — and a single `kind` would have to be re-interpreted at each of them.

**4. The interruptible Turn stays in `api/session_ws.py`.** The proposal was to hide the race between a Turn's events and the client's control messages behind an interface on the orchestrator. Declined: every ordering in that race is load-bearing and each is pinned by a test — the played position is handed over before the cancel, both when the cancel lands in the generator and when it lands in a socket send (`test_barge_in_ordering.py`); an interrupt arriving after the generator returned still trims (the same file); a disconnect tears the Turn down before it propagates, and a forwarder that has already failed still closes the generator (`test_websocket_protocol.py`). An interface would move those orderings without making any of them safer, on the path where a mistake is least visible. The companion proposal, a request handle for the pooled TTS connection, was built on its own as `tts._pooled_request`, which needed nothing from this one.

## Consequences

A future review that proposes one of these again can be answered by pointing here. If the ground under one of them changes — a third kind of Scenario built from a Session (ADR 0100), a stored Session that no longer depends on consent, a metric module split below its ceiling — the corresponding decision is worth reopening, and this record says what it rested on.
