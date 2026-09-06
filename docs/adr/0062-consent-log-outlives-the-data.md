# ADR 0062: The Consent Log Outlives the Data It Permitted

## Status

Accepted. Makes explicit a behaviour ADR 0060 introduced without deciding it.

## Context

ADR 0060 records consent decisions in an append-only `consent` table and deletes a subject's Sessions when they withdraw. It did not say what happens to the consent rows themselves, and the implementation quietly kept them: `deletion.py` removes Sessions and nothing else.

So "delete everything" does not delete everything. What remains is one row per decision, each carrying the subject's Keycloak `sub`, the purpose, the wording version, the status and the moment. That is personal data, it survives the withdrawal, and nobody decided it should.

The tension is real in both directions. Keeping the log means retaining data about someone who just asked to be forgotten. Deleting it means destroying the only evidence that they were ever asked, that they answered, and that the answer was honoured — which is the entire reason for recording consent rather than assuming it. A consent record that disappears with the withdrawal cannot demonstrate anything about the period before it, including that the storage which did happen was permitted.

## Decision

Withdrawal deletes the Sessions and keeps the decisions. The `consent` table is not touched by any deletion path.

**What the log holds is the decision, not its subject matter.** A row says that this account granted or withdrew consent to this wording at this moment. It carries no transcript, no measurement and no wrap-up: nothing about what was said, only about what was permitted. That is a far smaller thing to retain than the data it governed, and it is the part that has to survive for the record to mean anything.

**The `sub` is stored in the clear, and not hashed.** A hash would be theatre here: the value is a UUID drawn from a small known set that Keycloak holds, so any digest of it is reversible by anyone who can also read the realm — which is the same person who can read this database. Hashing would obscure the field from a casual reader while changing nothing about who can actually re-identify it, and it would cost the ability to answer the one question the log exists for ("what did this account decide?"). A keyed HMAC would be genuinely one-way, but the key would have to live somewhere the application can reach, which puts it on the same server.

**The log is therefore honest rather than pseudonymised further.** ADR 0031's analysis applies unchanged: this is pseudonymisation as a mitigation, not anonymisation.

**It is not swept.** ADR 0061 deletes Sessions after six months and leaves this table alone. A decision from a year ago is exactly the kind of thing a retention question asks about, and expiring the evidence on the same schedule as the evidence's subject would defeat both.

**It is not exported either**, beyond the current state. `GET /api/me/export` includes the subject's standing decision, not the full history of decisions. The history is a record kept about the processing, not a copy of what the user provided; putting every past grant and withdrawal in a downloadable file serves nobody and widens what a leaked export would contain.

## Consequences

The system can answer, per account, what was agreed to and when, including decisions later reversed. That is the property a consent record exists to have, and it survives the deletion of everything it was about.

The cost is stated plainly rather than avoided: an account that withdraws consent and has its trainings deleted still leaves rows in this table, and those rows identify it. Anyone describing the deletion to a user should say "your trainings are deleted", not "all your data is deleted", because the second is not true. The profile page's wording follows that distinction.

This is the smallest retention we could justify, and it is still a retention. If it later has to go — because the record's value is judged lower than the residue's cost — the change is a delete in `deletion.py` and a paragraph replacing this one, not a redesign. Deciding it now, in writing, is what makes that a decision rather than an oversight someone discovers.
