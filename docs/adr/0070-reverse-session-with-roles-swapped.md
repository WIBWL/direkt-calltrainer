# ADR 0070: Reverse — Replaying a Session With the Roles Swapped

## Context

A trainee never sees the counterpart's side: why they rang, what they knew, what would have satisfied them (R-25). Standing where the other person stood is the strongest lesson after a difficult call.

## Decision

- **A reverse is a Scenario row with a `reverse` marker**, copying the played Scenario's card and four prompt fields. It adds `origin_session_id` (UNIQUE, so one reverse per Session; `SET NULL`) and `reverse_brief`. It is created on request, from the post-call screen or a past training.
- **The played case reaches the client**, an exception to ADR 0043: the User has just heard it played out.
- **The casting is swapped inside the same prompt builders.** The Persona keeps its name and manner, but loses its customer role and objections, and answers the phone. The User calls, so a reverse keeps the pre-warmed opening (ADR 0042). The call-state notes, the settlement check and the anti-repeat nudge each have a reversed form. The ordinary prompt is pinned byte-identical by a test.
- **The briefing is generated once and stored**, in German, addressed to the User: situation, facts, goal, settlement, and three to five tickable goals (never remarks on manner). **The model never reads it.** It is shown during the call beside the state animation, at full length, an exception to the no-text-during-the-call rule.
- Starting takes two presses with the briefing screen between them, in place of the microphone check.
- It is stored and analysed like any Session. The wrap-up labels the Persona `Agent`.
- **Deletion:** withdrawal and the retention sweep hard-delete a subject's unreferenced reverses. Deleting a single training leaves them, and the profile says so.

## Consequences

The trainee gets the other perspective in one click, as a replayable row. Four subsystems branch on the marker, `session` and `scenario` reference each other, and the deletion asymmetry has to be stated. The briefing is a model translation and can be wrong; it is not regenerated when the origin changes.
