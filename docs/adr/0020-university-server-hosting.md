# ADR 0020: Deployment on a University-Hosted Server

## Status

Accepted

## Context

arc42's Verteilungssicht is still open. Beyond local Docker Compose, the running system needs an actual host for the pilot with Solox GmbH. Options considered would have included a commercial cloud provider or infrastructure provided by Solox itself.

## Decision

We will deploy the application on a server hosted by the university, alongside the DiReKT gateway (ADR 0011).

## Status update (September 2026)

The deployment is hosted by Hetzner Online GmbH in Gunzenhausen, not on a university machine. That is the address named in the privacy statement, and it is what the responsible body confirmed when the statement was written.

Recorded here rather than edited into the decision above, because the two are different things: the decision was to host at the university, and the fact is that it is hosted at a German provider under an Art. 28 processing agreement. Whether the decision should be restated or the deployment moved is for whoever owns it. What must not happen is that this file keeps asserting a location the privacy statement contradicts.

The Consequences below are stale in the same way and for the same reason, so read them as part of the decision rather than as a description: there are now two hosting relationships and not one, the commercial cost the decision avoided is being paid, and uptime depends on a provider under an Art. 28 agreement rather than on the university. Left standing rather than rewritten, because a consequence is what the decision was expected to bring about, and editing it would hide that the expectation did not hold.

The reasoning that followed from "alongside the DiReKT gateway" is worth re-checking against the actual arrangement: the gateway is still university-operated, so the application and the model backend are no longer on the same machine.

## Consequences

Consistent with DiReKT already being university infrastructure — one hosting relationship to manage instead of two, and no commercial cloud cost. The project depends on the university's server for uptime and maintenance, outside the team's direct control. Concrete deployment details (server access, CI/CD, domain and TLS setup) are not yet decided.
