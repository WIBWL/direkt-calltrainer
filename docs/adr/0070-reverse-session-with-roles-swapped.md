# ADR 0070: Reverse — Replaying a Session With the Roles Swapped

## Status

**Proposed.** The feature (F-61) is not built. This records the decisions
taken in `docs/plans/reverse-scenario.md` up front, because several of them
are deliberate exceptions to ADRs already in force (ADR 0043,
ADR 0033's "no text during the call") and those exceptions should be arguable
before the code exists, not discovered in it. Revisit and move to Accepted
when the feature lands; until then, nothing in this ADR describes running
code.

## Context

A trainee hears one side of a call. The counterpart's situation — why they
rang, what they knew, what would have satisfied them — stays invisible, and
the strongest lesson available after a difficult conversation is to stand
where the other person stood (R-25: a call is perceived differently by each
side). A *reverse* replays one finished Session with the roles swapped: the
User now calls, the Persona picks up and takes the side the User held, and
the User sees the briefing the Persona had for the original call.

This is not the follow-up Scenario (F-60, ADR 0069). That one invents a *new*
case in the same subject area from the wrap-up's improvement points, and
produces an editable draft. A reverse copies *one concrete case* verbatim,
stores itself, and is never authored. The two share the route shape on the
sessions router and `llm.complete(think=True)` off the live path, nothing
more.

## Decision

**A reverse is a Scenario row carrying a `reverse` marker**, not a convention
in the Scenario text and not a revived `scenario_type`. The former
`scenario_type` free-text label was not consumed; this column is read by four
places — the prompt casting, the wrap-up's speaker labels, the setup filter and
the briefing panel. The row copies the played
Scenario's title, short description and four prompt fields verbatim, and adds
`origin_session_id` (UNIQUE, so the button is idempotent — one reverse per
Session; `ON DELETE SET NULL`, so the row outlives the Session it replays) and
`reverse_brief`.

**The played Scenario's case reaches the client on a reverse.** ADR 0043
withholds a built-in's prompt fields from the browser, and that stands
everywhere else; here it is suspended on purpose, because seeing what the
Persona had *is* the feature, and because the User has just heard that case
play out for a whole call. What ADR 0043 protects is a run the User has not
had yet, which a reverse by definition is not.

**The casting is swapped in the prompt, not in a second prompt.** The Persona
keeps its name, traits and behaviour — an impatient agent is a fair
counterpart — and loses `role` and its objections, since every seeded role is
a customer's and so are the objections. A casting paragraph says the situation
was written for the caller, that the user is now that caller, and that the
Persona never states a reason for calling. The case block keeps its three
fields, relabelled to the callee's side, and the silent-check sentence
(ADR 0045) is reworded rather than dropped.

**The Persona still speaks first, it just says less.** The opening instruction
asks for nothing but how someone answers a phone — company or department,
name, an offer to help — from a new `answering_examples` field per
`LanguagePack`, the sibling of `opening_examples` that ADR 0043 established.
The re-greeting guard, the pre-warm (ADR 0042) and the opening-turn mechanics
are untouched.

**The briefing is generated once, stored, and never put in a prompt.** One
`llm.complete(think=True)` at creation turns the four prompt fields (plus the
improvement points and `phase_language` where a wrap-up exists) into German
text addressed to the User — situation, facts, goal, settled — and three to
five imperative watch-points. It translates and re-addresses; it invents
nothing. It lives in `reverse_brief` on the row, and the live call never sees
it: a briefing the Persona could read would be a briefing the Persona could
act on.

**The briefing is shown during the call** — the one deliberate exception to
ADR 0033's "no text during the live call, only a state animation". The rule
exists so the trainee listens instead of reading a transcript; this text is
the User's own briefing, fixed before the call starts, and never the Persona's
lines. It appears on the mic-check screen and beside the state animation.

**A reverse is stored and analysed like any Session** — consent (ADR 0066),
retention (ADR 0067), history and wrap-up all apply unchanged. The wrap-up
labels the Persona's turns `Agent` rather than `Caller` and states that the
trainee was the caller; the measurements are untouched, being symmetric and
about the User's half either way. As an addendum to ADR 0066/0067: withdrawing
consent hard-deletes the subject's reverse rows after their Sessions are gone,
because the briefing is derived from their own feedback, while deleting a
single training and the retention sweep leave the row standing and let the
foreign key null itself.

## Consequences

The trainee gets the one perspective the product could not give them before,
from a conversation they have just had, in one click — and a reverse is
selectable again later, because it is a row rather than a mode. The cost is
spread thin but real: a marker column that four subsystems branch on, a
circular foreign key between `session` and `scenario`, a second opening
instruction and casting paragraph to keep in step with the first (a guard test
pins the non-reverse prompt byte-identical), and two live-force ADRs carrying
a documented exception each. The deletion asymmetry — reverse rows die with a
consent withdrawal but survive a single deletion — is defensible but has to be
stated in the profile screen's wording, or "your trainings are deleted" stops
being true in the direction users care about.

The briefing is a translation the model performs, so it can be wrong about a
case the User is about to argue. It is generated once and stored rather than
per call, which makes it inspectable and fixable; it is not regenerated when
the origin Scenario changes, and after the origin Session is deleted the row
keeps a briefing whose conversation no longer exists.
