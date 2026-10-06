# ADR 0089: The Closing Is Read as Three Parts, in the User's Last Two Turns

## Context

"Klarer Gesprächsabschluss" names three parts: a short recap, a clear agreement, a friendly goodbye. All are in the words, which are stored.

## Decision

- The user's last two turns are checked for a **recap** (`recap_re`), a concrete **next step** (`agreement_re`, deliberately not "ich kümmere mich darum"), and a **farewell** (`sign_off_re`, wider than the live path's `farewell_re`, which must not end calls on "schönen Tag noch").
- Two turns, because the recap usually comes one turn before the goodbye. Below three user turns the metric is absent.
- The same parts apply whoever rang.
- The value is "von 3". The tile, progress view and report all show the parts from one shared list (`metricParts`). The detail carries `turns_read`.
- Whether the close was *clear* stays the wrap-up's judgement, so the goal's evidence is `mixed`.

## Consequences

The patterns will miss real closings, and each miss reads "nicht erkannt".
