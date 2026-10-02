# ADR 0054: The Scenario Briefs the Trainee, Not Only the Persona

## Status

Accepted. Extends ADR 0045 (which created the hole this fills) and follows the
display/prompt split of ADR 0043. Built as `scenario.briefing` in migration
`c8d1f3a67b40`; the briefing is shown on the microphone check as decided below
*and* on the setup screen, where picking a Scenario is itself a decision the
card's one line does not carry.

## Context

Everything a Session knows about the case is currently addressed to one side of the call. The system prompt receives the Scenario's context and — where ADR 0045 has landed — the facts of the case, what the caller wants, and the condition under which the caller counts the matter as settled. `/api/scenarios` serves `id`, `name` and one line of description. The Persona is briefed; the trainee is not.

In practice this means the trainee learns the case only while the Persona recites it. Entering `price-cancellation-risk`, they are told nothing about the fourteen licences, the twelve-percent rise, or the March start date until the caller says so — and nothing at all about their own position. They do not know what room they have: whether a discount is theirs to offer, whether a callback with a date is an acceptable outcome, whether escalation exists. They are asked to defend a product that does not exist, with no brief.

**ADR 0045 created this hole while fixing a worse one.** It found that both seeded Scenarios ended their description with the trainer-facing objective — *"The goal of the call is to keep the customer through price negotiation"* — and that this text was interpolated into the Persona's prompt as the call's context. The caller was being told its goal was to keep itself. Removing it was right. But it was removed without being rehomed: nothing on the display side took the trainee's objective over, and the field it used to occupy was the only place it had ever lived.

**C-05 does not object; it argues the other way.** R-40 and R-41 exclude customer-specific product and domain knowledge, so that the training runs in any customer landscape. A briefing about an invented case is not domain knowledge — it is the setup of the exercise. If the trainee is assumed to bring no prior knowledge, the exercise has to supply the little it presupposes. Without that, C-05 is satisfied in the letter and defeated in effect: the call is generic, and unplayable.

**Q-01 is the stronger argument.** The quality goal requires the analysis to be traceable and its feedback comprehensible. Feedback on how someone argued cannot be defended when they were never told what they were arguing for. The gap therefore does not stop at conversation quality; it undermines the feedback built on top of it.

## Decision

The Scenario carries a `briefing`: a display field, written in the UI language, addressed to the trainee.

It is served by `/api/scenarios` alongside the fields already there, and shown before the call begins. The microphone check is its place — ADR 0042 made that the screen where a Session is already committed to and the user is already waiting, so the briefing costs no extra step and no extra click.

It states three things and stops there:

- the role the trainee is called in, so the answer comes from somewhere
- the room for manoeuvre — what may be offered, promised or escalated
- what counts as a good outcome from the trainee's side

**It is never interpolated into the system prompt.** That is the whole point: the objective belongs to the trainee, and handing it to the Persona is precisely the defect ADR 0045 removed. The separation is the one ADR 0043 already established between prompt fields and display fields, and it is enforced the same way — by which field the prompt builder reads, not by convention.

## Consequences

Authoring a Scenario gains a fifth text and a third audience. The Scenario already speaks to the model in English and to the selection card in the UI language; the briefing speaks to the trainee before the call. That is the same rise in the authoring bar ADR 0043 and ADR 0045 each accepted, and it lands on a field ADR 0024's authoring UI will expose as one more form input.

The briefing and the case fields describe one case from two sides and can drift apart — a briefing that offers a discount the caller's success condition does not recognise makes the call unwinnable in a way neither field reveals on its own. They have to be authored together, and a Scenario is not complete until they agree.

The risk on the other side is a briefing that says too much. Told what to offer and in which order, the trainee reads a script and the exercise stops being a conversation — which is what R-43 keeps out of the product by excluding call guides as an evaluation basis. Role, room and outcome are enough; what to say is not the briefing's business.

Q-01 gains ground it did not have. Feedback can refer to something the trainee was actually told, rather than to an objective they had to infer from the caller's first sentence.

Sessions of the same Scenario become comparable in a further respect: two trainees who received the same briefing were set the same task, which is a precondition for the cross-Session view of ADR 0004.

## Amendment: the briefing becomes the Wissensstand

For the seventeen built-ins, `briefing` no longer holds three sentences of role, room and outcome. It holds the trainee's **Wissensstand**: a list of `- ` lines, starting with role and authority, then the two or three products of the fictitious Kontura Software GmbH that bear on the case, then only what *the trainee's own company* knows about this customer — contract, prices, ticket history, its own promises. Nothing that only the caller knows (their budget, their notes, their misunderstanding), and no "a good outcome is": the outcome is what the exercise is about, and stating it in a list the trainee reads mid-call reads as the script the third paragraph of the consequences warns against. Some entries are facts the model has never been given (a workaround, a price tier, a product variant); they sit on the trainee's side of the company only, which the caller could not know about, so the Persona has nothing to contradict them with.

Where it is shown moves with that. The **setup screen** shows the German `description_label` instead (served on the card as `description`) — who calls, why, what is practised — because a list of figures is not what a Scenario is picked by. The Wissensstand is read on the screen after the microphone check and **beside the live call**, where it replaces the translated case facts: a list is what one reaches back into for a number mid-sentence. The read-only info panel shows the description alone.

A built-in therefore **withholds `case_facts` from the client** as it withholds `call_goal` (`None`, ADR 0062): the facts are the caller's side of the case, and with a Wissensstand beside them they would hand the trainee exactly what the draft excludes. An authored Scenario keeps showing its facts, since its author wrote them to be read. `case_facts_label` stays in the seed; nothing displays it for a built-in any more, but a reverse copies it, and a reverse is where seeing the caller's side is the feature (ADR 0070).

The display is structured but not Markdown: `StructuredText` renders `- ` lines as a list, an indented `1. ` line as a numbered sub-item and `**…**` as bold, as React elements and never as HTML, and treats anything else as a paragraph — so a prose briefing an author or the follow-up generator wrote reads as it always did. The prompt builder still never reads `briefing`.
