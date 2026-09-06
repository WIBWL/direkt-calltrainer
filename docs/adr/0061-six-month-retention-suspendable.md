# ADR 0061: Stored Sessions Expire After Six Months, Unless the User Says Otherwise

## Status

Accepted. Closes the retention half of the open work ADR 0031 named; complements ADR 0060.

## Context

ADR 0031 recorded two obligations as open: "a retention period and a deletion path". ADR 0060 built the deletion path, in three forms — one training, all of them, and the consent withdrawal that removes everything. None of them is a retention period. They are all things a user has to *do*.

Without a period, a training recorded today is still on the server in four years, because nothing ever removes it. "We keep it until someone asks us not to" is not a retention policy; it is the absence of one, dressed as user control. It also puts the whole burden of data minimisation on the person least placed to carry it, who would have to remember that a system holds a recording of them and go and clear it out.

The counter-pressure is real: ADR 0059 wants the pilot's measurements to eventually establish what a distribution of these values looks like, and a period that quietly deletes them takes that away too.

## Decision

A stored Session is deleted six months after it was recorded. The user can suspend that for their own account.

**Six months, as `retention.RETENTION`.** Long enough to look back over a training period, short enough that recorded speech does not sit around for years on the strength of one click. The number is pinned by a test, so changing it is a decision someone makes rather than an edit that slips through.

**The default is deletion, and the default lives in the absence of a row.** `retention_preference` holds a row only for subjects who switched the sweep off. A subject who never touched the setting is covered, which is what makes this a period rather than something each account opts into. The alternative — a row written at first login — would have made the policy depend on a write having succeeded.

**The switch suspends; it does not shorten or extend.** Off means nothing is swept for that account, ever, until it is switched back on. There is no per-user period to configure: a policy each person tunes is not a policy, and the one useful exception ("I want to keep these") is served by a boolean.

**Switching it back on deletes nothing on the spot.** The next sweep applies the period as it always would. That keeps the control a statement about the future rather than a delete button wearing a different label, which is what an immediate purge on re-enabling would be.

**The sweep is driven from Postgres, on an interval, not from a timer.** `_retention_loop` in `app.py` runs it at startup and daily after that; `sweep()` asks which Sessions are past the boundary every time it wakes. A missed run therefore delays a deletion rather than cancelling it. The rejected alternative was a job scheduled six months ahead in Redis, which would not survive a restart and whose disappearance nothing would report — the same objection that applies to any durable intention parked in a cache.

Inside the app rather than as a cron entry, because a cron entry is a second thing to deploy and a second thing to forget, and this deployment has no scheduler of its own. `scripts/apply_retention.py` exists for the manual cases: seeing what the period would take before it takes it, or clearing a backlog after downtime.

**Failures never stop the loop.** A sweep that dies one night and never runs again is the failure mode worth designing against: nothing would report it, and the period would silently stop being enforced.

**The interface leads with the date, not the switch.** The profile says when the oldest stored training falls due; the control is underneath. What a user needs to know is when their data goes, not that a toggle exists. Under a suspended sweep no date is named, because there is not going to be one.

## Consequences

The system now forgets on its own. That is the substantive change: data minimisation stops depending on anyone remembering, and the promise on the profile page is one the software keeps rather than one the user has to enforce.

The cost is that the suspension makes the period soft. Anyone can switch it off and keep everything indefinitely, so the guarantee is really "six months unless you decided otherwise", and it should be described that way rather than as a blanket retention limit. That was the explicit product decision; the alternative — a period nobody could suspend — would have deleted trainings people were actively using, and would have made the export the only way to keep them.

ADR 0059's distribution data is affected: measurements go with the Session that carried them, so a cohort assembled from pilot data thins out at six months. If that data matters for establishing norms, the answer is the second consent purpose ADR 0059/0060 already anticipate — de-identified measurements retained separately, on their own basis — and not a longer period for everything.

Two things this deliberately does not do. It does not touch the consent log, which outlives the data it permitted (ADR 0062). And it does not reach the plaintext transcripts that `LOG_TRANSCRIPTS` writes when it is switched on, for the same reason nothing else does: no deletion path reaches a log file.

The period is expected to be revisited once the pilot has an opinion about how long people actually look back.
