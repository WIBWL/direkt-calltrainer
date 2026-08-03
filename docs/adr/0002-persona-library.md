# ADR 0002: Personas as an Extensible Library

## Status

Accepted

## Context

A Session's AI counterpart needs character traits (see ADR 0001 — Persona) that can vary independently of the Scenario. Stakeholder feedback from the pilot customer (Solox GmbH) calls for the roster of AI counterpart types to grow over time without reworking the core simulation.

## Decision

We will model Personas as entries in an open, extensible library, not as a single fixed or hardcoded configuration. New Personas can be added to the library without changing the core Session/Scenario mechanics.

## Consequences

The system can grow its roster of AI counterpart types over time without touching Session or Scenario logic. In exchange, the library itself needs a storage and management mechanism, which is not yet designed.
