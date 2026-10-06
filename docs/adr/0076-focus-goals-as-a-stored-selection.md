# ADR 0076: Focus Goals as a Stored Selection

## Context

Users know what they want to practise, but the application treated everyone the same and stored nothing about it.

## Decision

- A User picks **at most five** focus goals from a shipped catalogue of thirteen in four groups, at first start and later in the profile. The backend refuses a sixth goal with a 400 and serves `MAX_GOALS` to the client.
- **"No focus" is an answer.** `focus_selection` records that the User answered, so they are never asked again. Goals live in `focus_selection_goal`, and the catalogue in `focus_goal`, a seeded reference table where retired goals are deactivated, not deleted.
- The selection also carries an optional role and call types. Call types use the Scenario category vocabulary (ADR 0072). A `PUT` replaces everything.
- `focus_goal.evidence` (measured, mixed, interpretive) is internal planning data and never served. Whatever reports on a goal must still say whether it rests on a measurement or an appraisal.
- **It is a setting, not training data:** there is no consent gate and no deletion path touches it. The privacy text names it.
- **Suggestions** are rule-based in the backend: a matching call type scores 2, each goal exercised by the Scenario's category scores 1, an unplayed Scenario wins ties, and at most five are offered. Voice goals, reverses and uncategorised Scenarios steer nothing. The setup screen opens on *Empfehlungen* when there are any.
- Loudness and articulation are not goals (ADR 0111): what the app measures there is the device as much as the speaker.

## Consequences

The first-run screen is the longest in the app. Catalogue text is seed data, so a caption edit needs a restart. The role and goals are not yet in the data export.
