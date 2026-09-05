# ADR 0012: Backend Built with Python and FastAPI

## Status

Accepted

## Context

The backend needs to orchestrate calls to the DiReKT LLM gateway (ADR 0011) over HTTP and to talk to the project's own PostgreSQL instance (ADR 0010). The OpenAI-compatible client used for the LLM gateway is a Python library.

## Decision

We will implement the backend in Python using FastAPI.

## Consequences

FastAPI's async I/O suits a backend that mostly waits on chained external calls (STT, LLM, TTS), and using Python keeps the backend in the same language as the OpenAI SDK integration. This ties the team to the Python ecosystem for all backend work going forward.
