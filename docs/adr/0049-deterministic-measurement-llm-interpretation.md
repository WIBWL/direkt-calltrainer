# ADR 0049: The Model Interprets Measurements, It Does Not Produce Them

## Context

A small model asked to assess speech invents quantities it cannot know.

## Decision

The wrap-up has a measurement half and an interpretation half, and the model gets only the second. Every number is computed before the model is called and passed as fact; the model must not estimate or introduce quantities. It returns a summary plus points, each optionally citing a Turn. A citation outside the Session is dropped and the text kept. `Feedback.score` stays null.

## Consequences

The facts can be shown to a User who disputes them, and subjectivity is confined to wording. A reply that never validates yields a summary without evidence links. The wrap-up can only discuss what is measured.
