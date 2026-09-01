# ADR 0048: A Session Is Addressed by an Unguessable Id

## Status

Accepted

## Context

Nothing connected a finished call to its row. The WebSocket handed the client a `uuid4` for logging, while the schema's key is a serial integer, and the two had never met. Since the wrap-up is generated after the call ends (ADR 0019), the client has to be able to name its Session afterwards in order to fetch it.

That naming is also the access control. ADR 0009's authentication is unbuilt and `subject_id` is a placeholder (ADR 0031), so there is no identity to scope the request to, and the identifier itself is the only thing standing between one user's call and another's.

## Decision

We will give `Session` an `oeffentliche_id`: a random UUID, unique, generated when the Session is written, and handed to the client as the `session_id` it already receives at the start of the call. It, and never the primary key, addresses a Session in the API.

## Consequences

Addressing Sessions by an unguessable id means the URL is the credential. This is weaker than authentication and is not presented as equivalent to it: anyone holding the id can read that Session, so it must not be logged anywhere it could leak, and the product itself must not put it somewhere shareable.

What it does buy, and what a serial key could not, is that Sessions cannot be enumerated. With no authentication in the MVP, a sequential id would have made every user's call readable by counting.

When ADR 0009's authentication lands, this column stays useful as the external identifier and gains a real ownership check behind it.
