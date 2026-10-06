# ADR 0012: Backend Built with Python and FastAPI

## Context

The backend mostly waits on chained external calls (STT, LLM, TTS) and the database. The acoustic analysis uses Python libraries.

## Decision

The backend is Python with FastAPI.

## Consequences

Async I/O suits the workload. All backend work is tied to the Python ecosystem.
