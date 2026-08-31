# ADR 0045: Case Facts, Call Goal and Success Condition on the Scenario; Objections on the Persona

## Status

Accepted (extends ADR 0001; builds on ADR 0041 and ADR 0043)

## Context

ADR 0001 splits the Session's setup into two independent parts: the Scenario is
the situation, the Persona is the character, and ADR 0015 rests on every Persona
being combinable with every Scenario. `CONTEXT.md` states the same split.
ADR 0041 moved both into the database and ADR 0043 separated their prompt fields
from their display fields, but neither touched what the fields actually contain.
The content does not hold the split, and it does not carry the case at all.

**The Scenario hands the Persona the user's goal.** Both seeded Scenarios end
their `beschreibung` with the trainer-facing objective — `price-cancellation-risk`
with *"The goal of the call is to keep the customer through price negotiation and
objection handling"*, `cold-call-followup` with *"clarify the concern and bring
the conversation to a conclusion"*. That text is interpolated into the system
prompt as `Context of the call:`, and the Persona is the customer. The prompt
therefore tells the caller that their goal is to keep themselves, or to bring the
call the user is being trained on to a close. The role model is inverted, not
merely imprecise.

**The Persona carries situation text.** Both Personas' `verhalten` opens with the
identical sentence *"You have a concrete reason for this call (see the context of
the call) and a clear goal you want to reach in the conversation."* — a statement
about the Session's setup, copied per Persona into a field that is supposed to
describe character. The prompt frame already says the same thing.

**Nothing anywhere carries the facts of the case.** The frame instructs the model
to *"invent concrete, plausible details on the spot — a product name, a number, a
prior concern"*. So the case is improvised: re-invented every Session, and
unanchored within one, since nothing ties the figure the Persona names in Turn 5
to the one it named in Turn 2. Two things follow. The user cannot be measured
against a case, so the feedback worker of ADR 0014 and ADR 0018 has no factual
ground to judge against. And two Sessions of the same Scenario are not
comparable, which is what the growing library of ADR 0002 and the cross-Session
Feedback of ADR 0004 depend on.

**The Session's end has no defined criterion.** The frame asks the Persona to
close when its concern is *"concretely addressed — a clear answer, or a specific
commitment with an actual action, amount, or timeframe"*. That is prose, judged
per reply. ADR 0037's regex and ADR 0038's repetition guard exist to catch what
that judgment misses.

**`persona_einwand` has been empty since it was created.** ADR 0026 modelled a
Persona's typical objections as ordered rows; `scripts/seed_reference_data.py`
seeds every Persona with an empty list, and `backend/library.py` does not load
the relation. R-12 ("Nutzer wollen den Umgang mit spontanen Einwänden
trainieren"), realised through F-01, has no implementation beyond a parenthesis
in the frame's example exchange.

## Decision

We will put the situation on the Scenario and the manner on the Persona, and
make the case itself explicit.

### The Scenario carries the case

`szenario` gains three prompt fields, English and language-neutral per ADR 0043,
so every Persona × Scenario pairing stays valid:

- **`fallfakten`** — the facts of the case: product, figures, dates, history.
  About the *case*, never about the caller: no name, no employer, no
  personality, no motive. That restriction is what lets any Persona carry them
  (ADR 0001, ADR 0015); it is an authoring rule the schema cannot enforce.
- **`anrufziel`** — what the caller wants out of this call, one sentence, in the
  caller's own terms.
- **`erfolgsbedingung`** — the observable condition under which the caller
  considers the matter settled.

`beschreibung` is reduced to the situation alone. The trainer-facing objective is
removed from it and not relocated: what the *user* is meant to achieve is not
part of the Persona's prompt.

### The Persona carries only manner

`verhalten` states how the Persona conducts itself — how persistent it is, how
long it tolerates a vague answer, what makes it yield — and nothing about the
situation. The shared opening sentence is dropped; the frame already carries it.

`trainingsziel` and `schwierigkeitsgrad` are untouched by this decision. Neither
is read today — not by the API, the prompt, or the frontend — and both are kept
for a use still to be found; `schwierigkeitsgrad` in particular is a plausible
summary of what `verhalten` now states outright, and the natural thing to show
on the selection card of ADR 0015.

`persona_einwand` is filled with three to four rows per Persona, loaded by
`backend/library.py` and rendered into the system prompt.

Objections are written in English, as *moves* rather than as verbatim lines —
"pushes back that the figure is above what was budgeted", not a quoted German
sentence. Two reasons. `persona_einwand` has no language column while a Persona
has a fixed language (ADR 0043), so a quoted line would have to be authored per
language. And quoted examples are reused verbatim by this model: the frame's
opening examples had to be multiplied for exactly that reason, and a single
anchor collapsed every call onto one wording. The frame instructs at most one
objection per Turn, raised only where it fits and never worked through as a
list — the "one objection, raised once" property the example exchange already
demonstrates.

### The frame stops inventing over the facts

*"Invent concrete, plausible details on the spot"* becomes *"use the facts of the
case; invent only what they leave open, and never contradict them."* The original
instruction remains as the fallback for a Scenario without `fallfakten`, which
the user-authored Scenarios of ADR 0024 will produce.

## Consequences

Authoring a Scenario becomes writing four things instead of one, and the Scenario
stops being a mood and becomes a case. That is the same rise in the authoring bar
ADR 0043 accepted for its two-audience texts, and it lands on the same fields
ADR 0024's authoring UI will have to expose as form inputs — so the columns are
the schema that UI binds to rather than an extra layer for it to flatten.

`erfolgsbedingung` gives the system its first addressable notion of "this call
achieved something": `[CALL_END]` can be weighed against a named criterion
instead of the frame's prose, and the feedback worker gets the thing it would
otherwise have to infer. It does not make ADR 0037 or ADR 0038 removable — those
catch a model that will not emit the marker at all, which is a different failure
from a model that misjudges when to.

R-12 acquires an implementation, and Sessions of the same Scenario become
comparable, which is a precondition for the cross-Session Feedback of ADR 0004.

The system prompt grows by three blocks and up to four objections, on the small
university-hosted model of ADR 0011. The known risks are that the model recites
the case facts unprompted rather than producing them when asked, and that it
works the objections as a checklist. Both are addressed by frame wording alone,
so both need the same kind of empirical check the opening examples got.

Migration and content follow: three columns on a seeded `szenario` table, which
per this repository's own warning autogenerate will emit as `NOT NULL` without a
backfill; the `Scenario` value object and the seed content; a `joinedload` for
`Persona.einwaende` in `backend/library.py`, since it returns detached rows; the
prompt frame; and the prompt tests, which assert the frame's wording directly.
