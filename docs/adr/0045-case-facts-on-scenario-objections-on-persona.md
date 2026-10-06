# ADR 0045: Case Facts, Call Goal and Success Condition on the Scenario; Objections on the Persona

## Context

The Scenario handed the Persona the trainee's goal, the Persona carried situation text, and the case was improvised anew each call, so calls were neither anchored nor comparable.

## Decision

- **The Scenario carries the case**, as English, language-neutral prompt fields: the description (situation only), `case_facts` (product, figures, dates, history; never anything about the caller), `call_goal` (what the caller wants), and `success_condition` (when the caller considers it settled). What the *trainee* should achieve is never in the prompt.
- **The Persona carries only manner**, plus three to four objections, written as English *moves* rather than quoted lines. The frame allows at most one objection per Turn, raised where it fits.
- The frame says: use the facts, invent only what they leave open, never contradict them.

## Consequences

Every Persona × Scenario pairing stays valid, calls of one Scenario become comparable, and R-12 has an implementation. Authoring a Scenario means writing four things. The model may recite facts or work objections as a checklist; that is controlled by frame wording only.
