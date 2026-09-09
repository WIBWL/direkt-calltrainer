# ADR 0070: Reverse — Replaying a Session With the Roles Swapped

## Status

**Accepted**, and built (F-61). It was written as *proposed* before any code
existed, because several of the decisions below are deliberate exceptions to
ADRs already in force (ADR 0043, ADR 0033's "no text during the call") and
those exceptions should be arguable in the open rather than discovered in a
diff. Three things changed on the way in, all recorded in Consequences: the
call-state notes (ADR 0071), the settlement check (ADR 0073) and the per-turn
anti-repeat nudge (ADR 0038) turned out to need the swap as well, since all
three are written from the caller's side.

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
five **goals**: the concrete things this call has to raise, ask or come away
with, each one tickable once it has happened. (They began as "watch-points",
advice on what to pay attention to; that produced remarks about tone, which
are not something a caller can work through. The prompt now rules manner out
by name.) It translates and re-addresses; it invents nothing. It lives in `reverse_brief` on the row, and the live call never sees
it: a briefing the Persona could read would be a briefing the Persona could
act on.

**The briefing is shown during the call** — the one deliberate exception to
ADR 0033's "no text during the live call, only a state animation". The rule
exists so the trainee listens instead of reading a transcript; this text is
the User's own briefing, fixed before the call starts, and never the Persona's
lines. It appears beside the state animation, the two splitting the screen
evenly, and at its full length: no scrollbox of its own, because a briefing
half-hidden behind an inner scrollbar is a briefing the User will not find the
fact in.

**Starting a reverse takes two presses and a screen in between.** *Rollen
tauschen* writes the Scenario; *Gespräch starten* begins the call; between them
is a screen carrying the briefing alone. The first press costs a model call and
the better part of a minute, so it cannot also be the press that starts a
conversation — and a reverse is a case the User has to argue, which is not
something to be dropped into. That screen stands where the microphone check
stands for an ordinary call, pre-warm (ADR 0042) and all, rather than after it:
the microphone was in use for the training this reverse came out of.

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

Three further places turned out to be written from the caller's side and had
to swap with the rest, none of them foreseen above, and all three for one
reason: they sit *nearer the reply* than the system prompt does, so a casting
they contradict is the casting that loses. The **call-state notes** (ADR 0071)
are most of what the model still sees of a call, so a frame naming the wrong
side as the caller undoes the system prompt one exchange at a time; they now
name the side that answered, and label the exchange `Agent` like the wrap-up's
dossier. The **settlement check** (ADR 0073) asked whether the user had given
the persona what it came for, which reversed turns into the persona pressing
the caller for the thing the caller rang about; it now asks whether the persona
has given the caller that. The **per-turn anti-repeat nudge** (ADR 0038) ends
in three lines forbidding the persona to put the user's proposal forward as its
own solution — written against a real failure mode of the caller casting, and
in the reverse casting a prohibition on the one thing the company side is there
to do; its reversed form keeps the demand for something new every turn and
drops that clause. All three are variants beside the original, not replacements,
and the ordinary text of each is pinned by a test — which is the shape this
whole change took: a handful of builders with a reversed form, everything that
has to hold in both castings written once.

The deletion asymmetry is stated where the Consequences above demanded it: the
profile screen's withdrawal confirmation names the reverse Scenarios it takes,
and its list of deletion paths says that removing a single training leaves them
standing. Creating a reverse is offered from a past training as well as from
the screen that follows the call — the row is written on request rather than by
the worker, so there is nothing about it that has to happen within a minute of
hanging up, and confining it there would have made a stored Scenario reachable
only in the window before it existed.

The retry-and-parse loop the follow-up (ADR 0069) and this briefing share moved
into `llm.complete_json`, beside the fence-unwrapping that was already there
for the same reason. The wrap-up deliberately does not use it: it needs the raw
text for its narrative fallback, which that helper does not hand back.
