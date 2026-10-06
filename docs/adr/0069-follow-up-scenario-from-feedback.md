# ADR 0069: The Follow-up Scenario Is Written From the Feedback and Stored

## Context

The wrap-up names what a User should work on, but gives them nowhere to practise it. A follow-up Scenario is the next call, aimed at that weakness.

## Decision

On request, a finished Session whose Feedback names improvement points gets **one stored follow-up Scenario**, an ordinary private authored Scenario (ADR 0058) owned by the User and stamped with their Tenant. It goes through the same sanitising (ADR 0059), caps (ADR 0063) and required fields as one typed into the editor.

- **Material:** the improvement points, the phase-language paragraph, the wrap-up's summary, and the played Scenario's card and four prompt fields. The User has just heard that case played out, so the exception to ADR 0043 is the same one ADR 0070 takes. The measured statistics are left out (ADR 0051).
- **Shape:** the same matter, a later call, carried forward. `success_condition` is set to exactly what the feedback says was missing, stated as the caller's own bar, so repeating the last call does not pass it. The four briefing fields never mention feedback or training. A trainee-facing "Worum es geht" (`description_label`) is required, because the caller rings the User (ADR 0110).
- **Values are German**, since the User reads and edits them.
- **One per Session:** a UNIQUE provenance column on the Scenario. Asking again returns the stored row and reactivates it if it was removed.
- **Lifecycle:** it is deactivated, not deleted, when its source Session goes (deletion, withdrawal, retention), because a later Session may have been played on it (ADR 0026).
- No consent check is needed here: an unstored Session has no Feedback (ADR 0066).

A call started from a finished training skips the microphone check, since the call that was just had already answered it.

## Consequences

A follow-up is editable, shareable and playable against any Persona with no extra code. Failures are visible as a 503 the User can retry. Transfer to an unfamiliar case is given up; if pilots show people improving on one case and no further, the fix is a second kind of follow-up.
