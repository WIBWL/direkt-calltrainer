# ADR 0007: Primary Access via PC + Headset, Mobile Optional

## Status

Accepted

## Context

The pilot use cases — support and advisory calls — happen at a desk. Mobile access was discussed during stakeholder interviews but is not required for the MVP.

## Decision

We will design and test the product primarily for desktop use with a headset (microphone and speakers). Mobile browser or app access may work opportunistically but is not a supported or tested MVP target.

## Consequences

This simplifies audio I/O handling and UI layout decisions for the MVP, since no mobile-specific capture or permissions handling is needed. Mobile users may encounter a degraded or untested experience until mobile support is explicitly prioritized.
