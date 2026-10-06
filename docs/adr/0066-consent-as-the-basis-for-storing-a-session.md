# ADR 0066: Consent Is What Permits a Session to Be Stored

## Context

Stored Sessions contain what people said aloud. They are personal data (ADR 0031) and need a basis, a way to take them back, and limits that are stated honestly.

## Decision

- **A finished Session is stored only under consent to the current wording.** `consent` is append-only and the newest row holds. Repeating the decision in force writes nothing.
- **The wording is versioned.** Raising `CURRENT_VERSION` makes earlier grants stale. A withdrawal is never asked again.
- **The check runs inside the writing transaction**, under a per-subject advisory lock shared with withdrawal, so a withdrawal cannot slip between check and insert.
- **It fails closed**: an unanswerable check means no storage.
- **Declining leaves the trainer usable.** The call and transcript work; only storage, the wrap-up and the history are absent. The notice says so before the call.
- **Withdrawal deletes** the stored Sessions in the same transaction as the decision.
- **Data rights:** `GET /api/me/data` (counts and span), `GET /api/me/export` (everything, as a download), and `DELETE /api/sessions/{id}` (one training). All are scoped by `sub` in the query. All deletion goes through `deletion.remove` (ADR 0102).
- **Spoken content is never logged**, at any level. Only lengths are logged, and a test pins it.
- The one purpose today is `session_storage`.

## Consequences

Nothing spoken is stored without a record of agreement, and withdrawal really removes data. A User who declines gets no feedback, which is most of the product's value. There are three known limits:

- **No backups exist.** Whoever adds backups must add a retention policy here in the same change, or deletion stops being complete. Hoster snapshots are outside every deletion path.
- Re-identification is one query away for anyone who can read both the realm and the database.
- Audio and transcripts go to the DiReKT gateway, and only the generated Persona text goes to KugelAudio.

Consent may not be the right legal basis for a training tool; that is not the code's decision.
