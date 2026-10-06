# ADR 0062: A Scenario Read View, Withholding the Caller's Intent

## Context

Only a Scenario's author could open it, so Users chose built-ins from a one-line teaser, and a colleague's shared Scenario was unreadable to the company it was shared with.

## Decision

`GET /api/scenarios/{id}` serves any Scenario the caller may select, with an `editable` flag decided server-side.

| Row | Situation | Case facts | Goal, success condition | `editable` |
| :--- | :---: | :---: | :---: | :---: |
| Built-in | yes | no (Wissensstand instead, ADR 0054) | no (`null`) | false |
| Colleague's shared row | yes | yes | yes | false |
| Own row or follow-up | yes | yes | yes | true |
| Another User's private row | 404 | | | |

Withheld fields are `null`, not `""`. The write routes stay owner-only.

## Consequences

Reading comes before editing for every Scenario. Any new Scenario field must be classified as situation or intent, and intent is withheld from built-ins by default.
