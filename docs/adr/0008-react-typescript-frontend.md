# ADR 0008: Frontend Built with React and TypeScript

## Status

Accepted

## Context

The frontend needs to manage growing interactive state — login, live conversation UI, Feedback display — well beyond what the current audio-upload spike required. A plain static HTML/JS page was used for that spike but does not reflect the intended architecture.

## Decision

We will build the frontend as a React + TypeScript single-page application, built with Vite. The FastAPI backend serves the production build as static files, keeping the existing single-container deployment model.

## Consequences

Provides component structure, type safety, and a standard toolchain suited to future growth (Keycloak login flow, live conversation UI). Requires a Node.js build step and its own dependency ecosystem, and during local development the Vite dev server and the FastAPI backend run as two separate processes/origins, requiring CORS configuration.
