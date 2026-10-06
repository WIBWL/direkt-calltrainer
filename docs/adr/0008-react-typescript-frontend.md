# ADR 0008: Frontend Built with React and TypeScript

## Context

The frontend manages substantial interactive state: login, the live call, the wrap-up and progress views.

## Decision

The frontend is a React + TypeScript SPA built with Vite, served by its own container (ADR 0108).

## Consequences

It has component structure, type safety and a standard toolchain, at the cost of a Node build step and a second dependency ecosystem.
