# Calltrainer

An AI phone conversation trainer: simulated calls, speech analysis, and qualitative feedback on speaking behaviour over time.

## Language

**Session**:
One pass through the product: a simulated phone call followed by feedback.
_Avoid_: Call, conversation, training session

**User**:
The person who performs Sessions. There is no human coach; the AI writes all feedback.
_Avoid_: Trainee, learner, customer

**Scenario**:
The situation of a Session: why the call happens. It is chosen independently of the Persona. It may carry a **Category** (`operations`, `requirements`, `pricing`, `closing`), which is used for display and filtering only and never reaches the prompt.
_Avoid_: Situation, type, Szenariotyp

**Briefing**:
The Scenario's text for the User, not the Persona: their role, their room for manoeuvre, and what their own company knows. It never reaches the prompt.
_Avoid_: Instructions, script, Kurzbeschreibung

**Follow-up Scenario** (_Folgeszenario_):
A Scenario drafted on request from a finished Session's Feedback: the same matter, a later call, built around the improvement points. There is at most one per Session. Otherwise it is an ordinary Scenario the User owns.
_Avoid_: Follow-up call, next session, exercise

**Reverse** (_Rollentausch_):
A Session that replays a finished one with the roles swapped: the User calls, and the Persona answers and takes the User's former side. It is stored as a Scenario with a `reverse` marker and a **Reverse Brief** the User reads during the call. It cannot be edited or shared.
_Avoid_: Replay, mirror, role-play; "Rollentausch" in code

**Focus Goal** (_Fokusziel_):
A catalogue entry a User chooses to work on (at most five, or none). It belongs to the User, not to a Session, and it has no target value.
_Avoid_: Learning goal, objective, KPI, target; not the Scenario's `call_goal`

**Persona**:
The curated character of the AI conversation partner. It fixes the Session's language and voice.
_Avoid_: Character, counterpart

**Tenant**:
The company a User belongs to, which owns the Scenarios its members share. In Keycloak it is an Organization, whose alias is the Tenant's reference. Built-ins and Personas have no Tenant.
_Avoid_: Mandant, organization (outside Keycloak), company, account

**Language**:
The language a Session is conducted in. It follows from the Persona; it is not a separate setting.
_Avoid_: Locale

**Feedback**:
Qualitative, behaviour-focused insight written by the AI, for one Session or across Sessions.
_Avoid_: Score, evaluation, result

**Wrap-up**:
The Feedback of one Session: summary, strengths, improvements, phase language and tone fit.

**Turn**:
One exchange: the User's utterance and the Persona's reply. When stored, it becomes one row per speaker.
_Avoid_: Exchange, round, message

**Transcript**:
The plain record of what was said, shown after the Session. It is not analysed and is not Feedback.
_Avoid_: Protocol, log

**Measurement**:
One speech metric over the whole call or one marked stretch of it (`call`, `pressure`, `rest`), never per Turn. It always describes the User, never the Persona.
_Avoid_: Metric, score, KPI

**Finding**:
An event at one moment of a Session; today, a hard interruption by the User. It is never a value judged against a threshold.
_Avoid_: Issue, error, annotation
