# ADR 0013: Turn-Based, Non-Streaming Pipeline for the MVP

## Status

Accepted

## Context

The Session loop needs to feel like a natural phone conversation (F-21), but chaining three external calls (STT, dialogue generation, TTS) against a single university-hosted gateway carries real latency risk, already flagged in arc42 as a top risk. Two shapes were considered: full-turn request/response (record until the user pauses, send the whole clip, wait for the complete reply, then speak it) versus true streaming (partial transcripts, token-by-token generation, TTS starting before the text is finished).

## Decision

We will implement the Session loop as a turn-based, full-request/response pipeline for the MVP: record a full user turn, send it, wait for the complete STT → dialogue → TTS chain to finish, then play back the response. Real-time streaming across these three steps is explicitly deferred to a later phase.

## Consequences

This keeps the MVP implementation simple and lets the team measure the gateway's real latency before investing in the much harder streaming architecture (partial transcripts, token-streamed generation, incremental TTS, and error handling for a stream cut off mid-response). The tradeoff is a MVP conversation that pauses between turns rather than flowing continuously, which may fall short of the Echtzeitfähigkeit quality goal until streaming is built.
