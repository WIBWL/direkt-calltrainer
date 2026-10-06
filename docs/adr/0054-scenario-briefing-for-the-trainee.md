# ADR 0054: The Scenario Briefs the Trainee, Not Only the Persona

## Context

After ADR 0045 the Persona knew the case and the trainee knew nothing: not their role, their room for manoeuvre, or the facts their own company would have.

## Decision

- The Scenario carries a `briefing` addressed to the trainee, in the UI language. **The model never reads it.**
- For built-ins it is the trainee's *Wissensstand*: `- ` lines with role and authority, relevant products of the fictitious Kontura Software GmbH, and what the trainee's own company knows about this customer. It holds nothing only the caller knows and no stated outcome, because a list read mid-call becomes a script.
- It is shown after the microphone check and beside the live call. The setup card shows the German `description_label` instead.
- A built-in withholds `case_facts` and `call_goal` from the client (ADR 0062). An authored Scenario shows its facts.
- `StructuredText` renders lists, numbered sub-items and bold as React elements, never as HTML.

## Consequences

Feedback can refer to what the trainee was told. Briefing and case fields describe one case from two sides and must be authored together, or the call becomes unwinnable.
