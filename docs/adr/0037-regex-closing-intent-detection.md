# ADR 0037: Closing-Intent Detection Is Regex-Based, Not an LLM Classifier

## Context

The model often missed indirect goodbyes. An LLM classifier that replaced a regex check ended calls mid-conversation on wandering reasoning, which is a costly false positive.

## Decision

- A user's goodbye or request to postpone is detected by per-language regexes on the latest user message, with no model call. A hit sends the closing nudge.
- The Persona's `[CALL_END]` is trusted on a nudged Turn. Unprompted, it is vetoed while the reply's last sentence is still pressing (a question, or `still_pressing_re`), unless the reply carries a farewell.
- A committed reply with a farewell and no marker also ends the call, with no extra closing line.
- The chunk is cut at the marker, so nothing after it is spoken.

## Consequences

A missed phrasing costs at most a Turn and is fixed by widening the patterns, not by a classifier. A missed veto is an abrupt ending, so the patterns lean toward vetoing.
