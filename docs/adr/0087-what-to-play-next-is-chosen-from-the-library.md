# ADR 0087: What to Play Next Is Chosen From the Library

## Status

Accepted. Introduces F-64 and `GET /api/scenarios/{extern_id}/next?persona=…`, served by `recommendations.next_calls`. The third offer after a call, beside the follow-up (ADR 0069) and the reverse (ADR 0070), and deliberately unlike both. Builds on the suggestions of ADR 0076's amendment. The option to offer a Scenario by weakness is not part of it; see Consequences.

## Context

After a call the screen offered two ways on, and both *write* something: the follow-up drafts the next call in the same matter from the wrap-up's improvement points, and the reverse replays the call with the roles swapped. Each is a model call and the better part of a minute, and each produces a Scenario that did not exist before.

What was missing is the plainest next step — another call from what is already there. Either the same Scenario again in a different form, or a different one worth playing next. A User finishing a call has just learned something, and the moment to start the next one is now, not after browsing the library.

Two facts about the library shape what can be offered. There were exactly two Personas when this was written, one German and one English, so "the same Scenario with another partner" and "the same Scenario in the other language" were the same offer. *(Since then the seed holds six, four German and two English. The decision below is unaffected — it offers the other-language Persona, and there being more than one to choose from does not change what the offer means. Recorded here rather than edited away, because the premise is what the reasoning rests on.)* And the suggestions of ADR 0076's amendment — from role, call types and focus goals — already rank the whole library for this User.

## Decision

**After a call, at most two existing Scenarios are offered, each started with one press.**

1. **The same Scenario in the other language**, with the Persona whose language differs from the one just played. Always offered: whether it should wait until someone has trained in the other language before was weighed, and decided in favour of always. Never for a reverse, whose briefing is German prose (ADR 0070).
2. **Another Scenario from the library**, with the same partner: the best of the profile's suggestions that is not the Scenario just played, one not yet played first. Without a profile, an unplayed Scenario of the same category. Each offer names its reason, composed on the client from what the route returns — "Passt zu Ihren Gesprächen · Übt „Sichere Einwandbehandlung" · noch nicht gespielt".

Nothing is generated. There is no model call, and so nothing to wait for and no way for it to fail.

### One press, no microphone check

"Starten" goes through the same path as the follow-up's (`handleStartFollowUp`): the call begins at once and skips the microphone check, which was in use seconds ago. The follow-up and the reverse take two presses because the first writes something and the button that begins a conversation must not be the one pressed before there was anything to begin (ADR 0069); here there is nothing to write, so one press is right.

### It needs no stored Session

The route takes the Scenario and the Persona that were just played, not a Session id. A User who declined consent has no stored Session and no wrap-up (ADR 0066), and still gets the offers: `FeedbackView` shows them under the notice that no wrap-up was kept, and under the follow-up/reverse row when there is one. A Scenario or Persona the caller cannot select is a 404, like every other route.

### The logic is in the backend

`next_calls` is a pure function over plain values, in the backend and under pytest, for the same reason the suggestions are (ADR 0076's amendment): the frontend's tests cover the live-call audio path and nothing else.

### The pairing has to be kept past the end of the call

The first version read the pairing from `committed`, which the app clears the moment a call ends so that the next Session connects only when the User commits to it (ADR 0042). On the post-call screen it was therefore always empty and the offers were never requested — found in the first manual test, since nothing tests the component. `App.tsx` now keeps the last pairing (`lastPlayed`) at the same moment it clears `committed`.

## Consequences

The offers appear only right after a call. A reload of the post-call screen loses the pairing, and a past training's page does not show them; a weeks-old call is a weaker starting point for "what next" than the one just finished.

With two Personas the first offer is always the language switch. More Personas would split it into two — another partner in the same language, and the other language.

**Offering a Scenario by weakness** is the option this leaves out. Since ADR 0080 the wrap-up's points carry a focus goal, and `GOAL_CATEGORIES` leads from a goal to a category, so "a Scenario that exercises what this call's improvement points were about" can now be built on data that exists. It would be a third offer, and needs its own wording: it rests on the wrap-up's reading of the call, not on anything measured.
