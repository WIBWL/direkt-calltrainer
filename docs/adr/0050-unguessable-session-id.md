# ADR 0050: A Session Is Addressed by an Unguessable Id

## Context

The client must name its Session after the call to fetch the wrap-up. A serial key would make Sessions enumerable.

## Decision

`session.extern_id` is a random UUID, handed to the client as its `session_id`. It, never the primary key, addresses a Session in the API. Every read also compares `subject_id` with the caller's `sub` and answers **404, never 403**, so a foreign Session cannot be told apart from a missing one.

## Consequences

Sessions cannot be enumerated, and holding an id is not enough to read one.
