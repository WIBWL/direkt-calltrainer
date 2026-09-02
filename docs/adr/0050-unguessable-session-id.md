# ADR 0050: A Session Is Addressed by an Unguessable Id

## Status

Accepted

## Context

Nothing connected a finished call to its row. The WebSocket handed the client a `uuid4` for logging, while the schema's key is a serial integer, and the two had never met. Since the wrap-up is generated after the call ends (ADR 0019), the client has to be able to name its Session afterwards in order to fetch it.

That naming is also most of the access control. ADR 0009's authentication tells the route *that* a valid realm user is calling, and `subject_id` now records which one owns the row (ADR 0031), but the route makes no ownership check on top of the token: the screen that reads a wrap-up is the one that just finished the call, and nothing else looks a Session up. So the identifier is what stands between one user's call and another's.

## Decision

We will give `Session` an `oeffentliche_id`: a random UUID, unique, generated when the Session is written, and handed to the client as the `session_id` it already receives at the start of the call. It, and never the primary key, addresses a Session in the API.

## Consequences

Addressing Sessions by an unguessable id means the URL is the credential. This is weaker than authentication and is not presented as equivalent to it: anyone holding the id can read that Session, so it must not be logged anywhere it could leak, and the product itself must not put it somewhere shareable.

What it does buy, and what a serial key could not, is that Sessions cannot be enumerated. A bearer token is required (ADR 0009), but any valid realm token would do; behind a sequential id that would have made every user's call readable by counting.

The column stays the external identifier once a real ownership check is added -- comparing `session.subject_id` against the caller's `sub` is a one-line addition to the route, and is what a Session history (F-13/F-48) would need anyway.
