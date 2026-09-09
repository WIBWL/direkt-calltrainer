# pylint: disable=too-many-lines  # a data module: splitting it by line count would scatter the seed
"""Initial content for the `persona`, `scenario` and `focus_goal` reference tables.

ADR 0041 made the database the source of truth for the first two, so this
content is seed state and not a runtime source: `backend/library.py` reads the
tables, never this module. The focus-goal catalogue (ADR 0076) follows the same
rule and is read through `backend/focus.py`. `backend/db/provision.py` writes
all of it on startup and `scripts/seed_reference_data.py` on demand, both
idempotently.

Field names here are English and match both the value types in
`backend/personas.py` / `backend/scenarios.py` and the columns of the library
tables, so provision.py writes them straight through without mapping.
"""

# --- Personas -----------------------------------------------------------
# Every Persona has exactly one Language and one voice (ADR 0041). Two voice
# values per Persona: kugelaudio_voice_id for the default TTS backend,
# tts_voice for the DiReKT fallback (ADR 0040).
#
# Known gap: the DiReKT fallback model only carries German voices. de_male and
# de_female work, every English voice name it was probed with returns a 500.
# An English Persona therefore has no usable fallback voice and effectively
# depends on KugelAudio being up; its tts_voice is set to a German voice only
# so the NOT NULL column has a value.
#
# Two kinds of text per entry (ADR 0043): "role_label" is the label shown on
# the selection card and is written in the UI language; "role"/"traits"/
# "behavior" are read only by the model and are English, so that the language
# the Persona speaks is decided by language_id alone.
LANGUAGE_NAMES = {"de": "Deutsch", "en": "Englisch"}

# Tenants (ADR 0060, R-58). The two pilot companies plus a `default` tenant that
# every User with no company (dev users included) resolves to. `extern_ref` is
# the stable key `backend/tenants.py` resolves to -- a Keycloak Organization
# alias once that is enabled (phase 2), this string until then.
TENANTS = [
    {"extern_ref": "default", "name": "Ohne Unternehmen"},
    {"extern_ref": "solox", "name": "Solox"},
    {"extern_ref": "appollo", "name": "APPOLLO"},
]

PERSONAS = [
    {
        "id": "thomas-brandt-ceo",
        "name": "Thomas Brandt",
        "role_label": "Geschäftsführer, Fokus auf Strategie & Budget",
        "role": "Managing director of a mid-sized company, focused on strategy and budget",
        "traits": (
            "matter-of-fact, time-conscious, impatient with overly technical "
            "detail, an experienced negotiator"
        ),
        # Manner only (ADR 0045): how hard this Persona pushes and how long it
        # tolerates a vague answer. What the call is about lives on the
        # Scenario.
        "behavior": (
            "You lose patience quickly with technical, evasive or convoluted "
            "answers and say so. Two of them in a row and you cut in to ask "
            "for the short version. You want a number, a date or a name, "
            "and until you have one the matter stays open for you, but each "
            "attempt takes a different angle than the last: name the specific gap "
            "in what you were told, narrow the question down to the one piece you "
            "are still missing, say what not knowing it costs you, or state what "
            "you will do instead. Never put the same question the same way twice: "
            "if you have nothing new to add to it, move to a different part of "
            "the matter. On price you hold out longest. A concrete answer settles "
            "it immediately and you say so; you do not keep grinding once you "
            "have one"
        ),
        # Not modelled before this script took over the content: "medium"
        # because this Persona is demanding but not an escalation case.
        # Note that `training_goal` does not reach the model: neither the
        # `Persona` value type nor `library._to_persona` carries it yet.
        "training_goal": (
            "Einwandbehandlung unter Zeitdruck und Verbindlichkeit: Der Nutzer "
            "muss eine Zahl, einen Termin oder einen Namen liefern, statt "
            "allgemein zu bleiben."
        ),
        "difficulty": "medium",
        "language_id": "de",
        "tts_voice": "de_male",
        "kugelaudio_voice_id": 1657,
        # R-12 / ADR 0045: moves, not quotable lines -- the model reuses quoted
        # examples verbatim, and these have to work in any Scenario.
        "objections": [
            "pushes back that the figure is above what was budgeted for this",
            "says this was promised once before and nothing came of it",
            "asks what exactly is being paid for, item by item",
            "threatens to take the decision to the next budget round instead",
        ],
    },
    {
        "id": "samantha-ferris-marketing",
        "name": "Samantha Ferris",
        "role_label": "Marketing-Managerin bei einem Kundenunternehmen",
        "role": "Marketing manager at a company that is a customer of the user's",
        "traits": (
            "very polite, courteous, calm and composed, never pushy, easy and "
            "pleasant to talk to"
        ),
        # Manner only (ADR 0045). Same persistence as the other Persona, worn
        # differently: she never raises her voice and never interrupts, and
        # that is the whole difference.
        "behavior": (
            "You never interrupt and never raise your voice, and you give the "
            "other person time to finish even when the answer is going "
            "nowhere. You are just as hard to satisfy as anyone impatient, "
            "only politely: a vague answer gets a friendly restatement of the "
            "same question, and you will ask a third and fourth time without "
            "any edge in your voice. You apologise for pressing while you do "
            "it. Once an answer is concrete you accept it warmly and stop"
        ),
        "training_goal": (
            "Bedarfsermittlung und Konkretheit: Die Persona bleibt freundlich, "
            "auch wenn sie nichts bekommt. Der Nutzer muss selbst merken, "
            "dass die Frage noch offen ist."
        ),
        "difficulty": "easy",
        "language_id": "en",
        # tts_voice is a German voice because the DiReKT fallback has no
        # English one; see the note above.
        "tts_voice": "de_female",
        "kugelaudio_voice_id": 1071,
        "objections": [
            "apologises, then returns to the question that was not answered",
            "says she understands, but that this does not answer what she asked",
            "asks whether she should call back once someone can give her a firm answer",
        ],
    },
]

# --- Scenarios -----------------------------------------------------------
# Scenarios carry no language of their own (ADR 0043). "name" and
# "short_description" are the display texts in the UI language; the rest is the
# English call context the model reads, which is what lets any Persona run any
# Scenario regardless of the language that Persona speaks.
#
# Four prompt fields (ADR 0045): "description" is the situation, and
# "case_facts"/"call_goal"/"success_condition" are the case. Two authoring rules
# hold them together:
#   * The facts are about the *case*, never about the caller (no name, no
#     employer, no motive), because both Personas have to be able to carry
#     them (ADR 0001, ADR 0015).
#   * "call_goal" is what the *caller* wants. What the user is meant to achieve
#     is not part of the Persona's prompt; it used to be, and the caller was
#     being told to keep itself as a customer.
#
# "category" (ADR 0072) is display and filter only, never prompt input: one of
# `models.SCENARIO_CATEGORIES`. The four refine F-03's three call contexts --
# operations (short support cases), requirements (consultative project talks),
# and pricing / closing, which split F-03's offer-and-pricing calls. Every
# seeded Scenario carries one, because a shipped Scenario that no category
# filter finds is a Scenario nobody selects.
#
# The twelve entries below the built-in five come from the scenario catalogue
# (S-01..S-05, S-07..S-13). Two of its fourteen are deliberately not here:
# S-06 needs a memory across Sessions (F-23, not built), and S-14 is not a
# Scenario at all -- since ADR 0043 the language belongs to the Persona, so
# "the same call in English" is an English Persona, not a row of its own.
#
# Their case figures are invented but internally consistent, and they name no
# company, person, product or brand: the catalogue's anonymisation rule follows
# from C-05 (R-40/R-41), which requires the training to run without
# customer-specific product knowledge, and from ADR 0015, which requires every
# Persona to be able to carry every case.
SCENARIOS = [
    {
        "id": "cold-call-followup",
        "category": "operations",
        "name": "Offenes Anliegen zu bestehendem Vertrag",
        "short_description": (
            "Der Kunde ruft mit einer offenen Frage zu einem bestehenden "
            "Vertrag an und will sie geklärt haben."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "support, about an unresolved issue with an existing contract."
        ),
        "case_facts": (
            "A support ticket was opened eleven days ago about exports failing "
            "for one of the two team accounts. It was acknowledged the same "
            "day, a callback was promised within 48 hours, and nothing has "
            "happened since. The workaround in use is exporting one record at "
            "a time, roughly 40 a week. The contract runs to the end of the "
            "year and includes next-business-day support."
        ),
        "call_goal": (
            "Find out what is actually happening with the ticket and get a "
            "date by which the export works again."
        ),
        "success_condition": (
            "someone names what is wrong and when it will be fixed, or says "
            "plainly that it cannot be fixed and what happens instead. A "
            "promise to look into it is not enough on its own, because that "
            "happened eleven days ago."
        ),
    },
    {
        "id": "price-cancellation-risk",
        "category": "pricing",
        "name": "Kündigungsabsicht wegen Preis",
        "short_description": (
            "Der Kunde erwägt zu kündigen, weil ihm die laufenden Kosten zu "
            "hoch sind."
        ),
        "description": (
            "The customer (the persona) is calling to say they are considering "
            "cancelling or downgrading, because the running costs seem too "
            "high relative to the benefit. The customer is still open to a "
            "conversation in principle."
        ),
        "case_facts": (
            "The \"Insight Analytics\" package: 14 licences at 1,180 euros a "
            "month, running since March last year. The most recent renewal "
            "raised it by 12 percent, from 1,050 euros, with no change to what "
            "is included. Two of the package's six modules are in regular use; "
            "a competitor quoted roughly 800 euros for what looks like the "
            "same scope."
        ),
        "call_goal": (
            "Get the price down, or get a clear reason why it cannot come "
            "down. Cancelling is a real option and one you say out loud."
        ),
        "success_condition": (
            "a specific figure is committed to together with a date it takes "
            "effect from, or it is stated plainly that there will be no "
            "reduction and why. An offer to check internally and come back can "
            "be a result too."
        ),
    },
    # --- Beschwerde und Eskalation (Nutzer sitzt im Support) -------------
    # Dense, interlocking figures on purpose (the case density decided for the
    # library): the availability guarantee, the two April outages and the
    # service credit only add up to a lever if the numbers actually work out,
    # and a Persona that presses for specifics will surface it if they do not.
    {
        "id": "escalation-repeated-outage",
        "category": "operations",
        "name": "Wiederholter Ausfall trotz Zusage",
        "short_description": (
            "Der dritte Ausfall in sieben Wochen. Der Kunde will diesmal "
            "mehr als eine Entschuldigung."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "support, after the same service has failed repeatedly despite an "
            "earlier assurance that it had been fixed for good."
        ),
        "case_facts": (
            "The export service has gone down three times: forty minutes on "
            "14 March, three and a half hours on 2 April, and again this "
            "morning since 09:10, still down as this call starts. After "
            "the second outage a permanent fix was promised for the following "
            "release, which shipped on 18 April. The contract covers 30 licences "
            "at 2,400 euros a month and guarantees 99.5 percent monthly "
            "availability, which allows approximately three and a half hours "
            "of downtime in a 30-day month, with service credits of five "
            "percent of the monthly fee for any month that misses it. "
            "April has now missed it twice over."
        ),
        "call_goal": (
            "Find out why the fix did not hold, and get a commitment on what "
            "happens now, both to the service itself and to the service "
            "credit April has earned."
        ),
        "success_condition": (
            "the actual cause of the repeat failure is named and a dated next "
            "step is committed to, and the service credit for April is either "
            "confirmed or plainly refused with a reason. Another assurance "
            "that it is fixed, with nothing behind it, is word for word what "
            "was said after the second outage."
        ),
    },
    # --- Terminvereinbarung und Ausbau (Nutzer sitzt im Vertrieb) ---------
    # Deliberately the shortest case in the library: one decision, one date,
    # a clear point at which the call is done. That makes it the scenario
    # where an unreliable [CALL_END] shows up soonest.
    {
        "id": "upsell-seat-expansion",
        "category": "closing",
        "name": "Ausbau auf eine zweite Abteilung",
        "short_description": (
            "Der Kunde will ein zweites Team aufschalten und braucht Zahl "
            "und Termin, bevor sein Budget zugeht."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "sales, about extending an existing licence to a second "
            "department, and wants a concrete next step before the call ends."
        ),
        "case_facts": (
            "The current licence covers 18 users at 1,440 euros a month, which "
            "is 80 euros each. The second department would add 12 people, "
            "bringing the total to 30. The published price list has a volume "
            "tier starting at 25 users at 72 euros each, so the same 30 come "
            "to 2,160 euros a month at tier price against 2,400 "
            "euros at the current rate. The budget for this is approved only "
            "until the quarter closes on 30 June. Thursday afternoon and "
            "Friday morning are both free for an hour-long walkthrough."
        ),
        "call_goal": (
            "Get a price for the full 30 users and a walkthrough "
            "actually scheduled, before the budget window closes on 30 June."
        ),
        "success_condition": (
            "a price for 30 users is named and a specific day and "
            "time for the walkthrough is agreed. An offer to send something "
            "over is only a result if a date comes with it."
        ),
    },
    # --- Abschluss nach Übergabe (Nutzer sitzt im Vertrieb) ---------------
    # The point of this one is the information gap: the Persona holds facts
    # from a call the user was not on and has no notes for. It trains asking
    # over agreeing, which is why `description` says outright that the user
    # has nothing in writing. The 68 euros the Persona remembers sits below
    # the 72-euro tier in `upsell-seat-expansion` on purpose -- a figure that
    # may or may not have been promised is the whole hook.
    {
        "id": "closing-after-handover",
        "category": "closing",
        "name": "Abschluss nach Erstgespräch mit Kollegin",
        "short_description": (
            "Der Kunde ruft zum Abschluss zurück und beruft sich auf Zusagen "
            "aus einem anderen Gespräch."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "sales, to close a deal that was prepared three weeks ago in a "
            "call with a different colleague. The user was not on that call "
            "and has no notes from it."
        ),
        "case_facts": (
            "The first call was on 11 May, with a colleague the persona knows "
            "only as Frau Sandner. What the persona took away from it: 25 "
            "licences at 68 euros each, so 1,700 euros a month, a two-month "
            "trial period that can be cancelled, onboarding thrown in at no "
            "charge, otherwise a one-off 1,200 euros, and a start on "
            "1 July. None of it was confirmed in writing; the only record is "
            "a line in the persona's own notes. The internal approval to sign "
            "expires on 6 June."
        ),
        "call_goal": (
            "Get the agreement confirmed the way you understood it, and a "
            "signature under way before your internal approval expires on "
            "6 June."
        ),
        "success_condition": (
            "the terms are confirmed as you understood them, or you are told "
            "where they actually differ and why, and a step towards "
            "signature is agreed with a date on it. Checking back with the "
            "colleague first is a result too, as long as a date comes with it."
        ),
    },
    # --- Aus dem Szenariokatalog: Profil A, Betrieb und Betreuung ---------
    # S-01. The short end of the duration span C-06/R-03 asks for: one fault,
    # one deadline, one answer. The eight-day cut-off is what stops "we are
    # looking into it" from being an answer.
    {
        "id": "process-halted-before-deadline",
        "category": "operations",
        "name": "Störung im laufenden Betrieb",
        "short_description": (
            "Ein eingespielter Ablauf steht seit drei Tagen. Der Stichtag "
            "rückt näher."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "support, because a recurring document-driven process has stopped "
            "and items are no longer being assigned. A cut-off date is coming "
            "up and the caller does not know whether it can still be met."
        ),
        "case_facts": (
            "The process has run unchanged for more than a year. For the past "
            "three days items have been left unassigned, roughly 30 a day, so "
            "around 90 are now waiting. The stopgap is assigning each one by "
            "hand, which takes about two minutes each. The cut-off is in eight "
            "days, and anything still unassigned by then has to be handled "
            "outside the process. Nothing was changed on the customer's side "
            "in that time."
        ),
        "call_goal": (
            "Find out what is causing it and get a date by which the process "
            "runs again."
        ),
        "success_condition": (
            "a cause and a date are named, or it is said plainly that it will "
            "not be working before the cut-off, together with what applies "
            "instead. A promise to look into it is not a result on its own."
        ),
    },
    # S-02. C-05: the case carries the *shape* of a regulatory deadline, never
    # its content. Naming a real regulation would make the call unplayable
    # without domain knowledge, which is what R-40/R-41 rule out.
    {
        "id": "explain-mandatory-change-plainly",
        "category": "requirements",
        "name": "Erklärung für einen fachfremden Kontakt",
        "short_description": (
            "Eine verpflichtende Umstellung mit fester Frist, erklärt ohne "
            "Fachbegriffe."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "consulting or development, about a mandatory changeover with a "
            "fixed deadline that affects one of the customer's processes. The "
            "caller wants to know what it means for them and what they have "
            "to do about it."
        ),
        "case_facts": (
            "The deadline runs out in just under five months. The process "
            "affected is operated by three people, none of them technical. A "
            "circular about the changeover went out four weeks ago that nobody "
            "on the customer's side understood; it named the deadline and "
            "nothing else. Whether the customer has to change anything at all "
            "is still open. Nothing has been budgeted for it."
        ),
        "call_goal": (
            "Have it explained in plain words what has to be done and what it "
            "will cost, in words a non-technical person can repeat back."
        ),
        "success_condition": (
            "three concrete steps are named that the caller can repeat back in "
            "their own words. A pointer to documentation, or a term that is "
            "not explained, does not count."
        ),
    },
    # S-03. The one case the catalogue records as evidenced from both pilot
    # profiles. The point is that the caller cannot name the trigger or the
    # finished state, so a general "yes, that is feasible" settles nothing.
    {
        "id": "vague-automation-request",
        "category": "requirements",
        "name": "Anforderungsklärung bei vagem Wunsch",
        "short_description": (
            "Der Kunde will etwas automatisieren, kann aber weder Auslöser "
            "noch Zielzustand benennen."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "consulting or development, wanting a recurring manual process "
            "automated, but cannot say what triggers it or what the finished "
            "state should look like."
        ),
        "case_facts": (
            "Two departments handle the process differently and neither knows "
            "in detail how the other does it. Two earlier attempts at "
            "automating it, one three years ago and one last year, ended "
            "without a result; the caller cannot say why. No budget has been "
            "named. A target date has: this year if at all possible. Roughly "
            "20 cases a week go through the process."
        ),
        "call_goal": (
            "Find out whether this is feasible at all and what happens next."
        ),
        "success_condition": (
            "the caller can say what happens next, who does it and when. A "
            "general statement that it is feasible is not enough."
        ),
    },
    # S-04. R-07's case: the one customer type quoted verbatim in the pilot
    # interviews. Consultative, deliberately not a closing call: the money is
    # half a day of work, and the earlier goodwill job is the whole lever.
    {
        "id": "change-outside-contract-scope",
        "category": "pricing",
        "name": "Leistung außerhalb des Vertrags",
        "short_description": (
            "Eine gewünschte Anpassung ist vom Vertrag nicht gedeckt und wäre "
            "zu berechnen."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "consulting or account management, about an adjustment that the "
            "running contract does not cover and that would have to be billed "
            "as effort."
        ),
        "case_facts": (
            "The contract covers operation and fault fixing, not extensions. "
            "The adjustment asked for is about half a day of work, which comes "
            "to a low four-figure sum at the agreed daily rate. Something "
            "comparable was done two years ago as a goodwill gesture and never "
            "billed, which the caller remembers clearly. The contract runs for "
            "another fourteen months."
        ),
        "call_goal": (
            "Get the adjustment made, without any additional cost."
        ),
        "success_condition": (
            "either it is agreed at no charge, or the reason for billing it is "
            "given in a way the caller can repeat back. A bare \"that is not "
            "covered\", with no reason behind it, is not one."
        ),
    },
    # S-05. R-06's emotional case. The five hours of downtime and the silence
    # since the first report are the facts; how loudly they are carried is the
    # Persona's business, never the Scenario's (ADR 0001, ADR 0015).
    {
        "id": "outage-escalation-no-callback",
        "category": "operations",
        "name": "Eskalation nach einem Ausfall",
        "short_description": (
            "Seit dem Morgen steht eine zentrale Komponente, und seit drei "
            "Stunden meldet sich niemand."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "support or account management, because a central system component "
            "has been down since this morning and nobody has come back to them "
            "about it."
        ),
        "case_facts": (
            "The outage has lasted five hours and is still going on as this "
            "call starts. All of the customer's sites are affected and around "
            "60 people cannot work normally. A first report was taken three "
            "hours ago, with a callback promised within the hour, and there "
            "has been no word since. A comparable outage last happened four "
            "months ago and took two days to explain."
        ),
        "call_goal": (
            "Get a time by which it will be working again, and know who is "
            "taking care of it."
        ),
        "success_condition": (
            "a name and a time are given, or it is said openly that neither "
            "is settled yet, together with a commitment to when it will be."
        ),
    },
    # S-07. Trains the ground F-54 sits on: the summary at the end of a call.
    # The one point the caller took away differently is what makes summarising
    # an act rather than a recital, and it surfaces only if the recap is
    # specific enough to contradict them.
    {
        "id": "closing-recap-mismatch",
        "category": "operations",
        "name": "Absicherndes Wrap-up am Gesprächsende",
        "short_description": (
            "Vier besprochene Punkte, einer davon anders verstanden. Fällt es "
            "beim Zusammenfassen auf?"
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "support or consulting, at the end of a clarification process, to "
            "go through what was agreed once more out loud before the written "
            "summary follows."
        ),
        "case_facts": (
            "Four points were discussed earlier: a delivery date two weeks "
            "out, who supplies the test data, how the handover gets "
            "documented, and what happens to two items left open from the "
            "previous call. On the test data the caller understood that it "
            "would be supplied for them, when what was meant is that they "
            "supply it, and they will notice that only if the recap is "
            "specific enough to contradict them."
        ),
        "call_goal": (
            "Be sure both sides mean the same thing before anything is put in "
            "writing."
        ),
        "success_condition": (
            "the recap covers all four points and the one that was understood "
            "differently has been noticed and put right. A recap general "
            "enough for both readings to fit is not a result."
        ),
    },
    # --- Aus dem Szenariokatalog: Profil B, Beratung und Einführung --------
    # The catalogue marks these as proposals: they are derived from the pilot's
    # activity profile, not from a recorded call. The cases are sound to train
    # against, but they have not been checked back with the customer.
    #
    # S-08. Listening and ordering, the mirror image of S-02: here the caller
    # supplies too much detail, not too little.
    {
        "id": "process-capture-interview",
        "category": "requirements",
        "name": "Prozessaufnahme im Fachbereich",
        "short_description": (
            "Ein Ablauf, den zwei Personen unterschiedlich ausführen, während "
            "Anrufer hält beides für dasselbe."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "consulting or requirements analysis, for a first conversation "
            "about an existing manual process, so that it can be modelled "
            "later. The caller is one of the people who runs it."
        ),
        "case_facts": (
            "The process has roughly eight steps, three of them with special "
            "cases. It is documented nowhere. Two people carry it out "
            "differently: one checks an entry against a list before releasing "
            "it, the other releases it first and corrects afterwards, which is "
            "why about one entry in ten gets corrected later. The caller "
            "considers the two variants to be the same thing and describes "
            "both as though they were."
        ),
        "call_goal": (
            "Explain how the process works today and find out what happens "
            "next."
        ),
        "success_condition": (
            "the steps have been played back and the difference between the "
            "two variants has been named out loud."
        ),
    },
    # S-09. R-12's ground on the Scenario side: three reservations that each
    # need an answer or an honest "that is a risk". Blanket reassurance is the
    # failure mode the success condition rules out.
    {
        "id": "technology-choice-objections",
        "category": "closing",
        "name": "Einwände gegen die Lösungswahl",
        "short_description": (
            "Drei Vorbehalte gegen den vorgeschlagenen Ansatz, und eine "
            "Entscheidung in sechs Wochen."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "consulting or management, with reservations about the proposed "
            "approach: dependence on a single vendor, limits once the "
            "requirements get complex, and doubt about whether it will still "
            "carry in five years."
        ),
        "case_facts": (
            "An earlier project of the customer's on a comparable approach was "
            "replaced after two years. The caller was involved in it and "
            "brings it up, without knowing exactly why it was replaced. A "
            "decision is due in six weeks and is taken by a group of four, of "
            "whom the caller is one. Roughly 40 people would work with the "
            "result day to day."
        ),
        "call_goal": (
            "Test whether the reservations can be answered, with something "
            "concrete, not with reassurance."
        ),
        "success_condition": (
            "each of the three reservations has either a concrete answer or is "
            "named openly as a risk. A blanket assurance that it will not be a "
            "problem does not count for any of them."
        ),
    },
    # S-10. R-10, and the sharpest case in the library for the sales/no-sales
    # question K-01 leaves open: the competing quote covers less, and the
    # caller does not volunteer that. It comes out only if someone asks what is
    # actually in it.
    {
        "id": "procurement-price-negotiation",
        "category": "pricing",
        "name": "Preis- und Konditionsverhandlung",
        "short_description": (
            "Der Einkauf fordert einen Nachlass und verweist auf ein "
            "Vergleichsangebot."
        ),
        "description": (
            "The customer's procurement side (the persona) is calling the "
            "user, who works in sales or management, to ask for a discount, "
            "citing a competing quote."
        ),
        "case_facts": (
            "The quote on the table is a running annual figure in the middle "
            "five-figure range. The competing quote named is around 20 percent "
            "below it, but covers a smaller scope: it leaves out the "
            "migration of existing data and the second year of support, which "
            "the caller does not volunteer and concedes only if asked what is "
            "actually in it. The decision is meant to be made this week."
        ),
        "call_goal": (
            "Get the price down. The competing quote is the lever, not the "
            "point."
        ),
        "success_condition": (
            "a figure is committed to with a date it is valid until, or it is "
            "stated plainly that there will be no discount and why. An offer "
            "to check internally is not a result."
        ),
    },
    # S-11. R-08's other half, and R-04 read the second way: the IT side is not
    # against the thing, it was bypassed. Trains asking what the objection
    # actually is before answering the one that was voiced.
    {
        "id": "sceptical-it-governance",
        "category": "requirements",
        "name": "Gespräch mit einer skeptischen IT-Seite",
        "short_description": (
            "Der Fachbereich ist überzeugt, die IT sieht Steuerbarkeit und "
            "Betrieb gefährdet."
        ),
        "description": (
            "The customer's IT side (the persona) is calling the user, who "
            "works in consulting. The department is convinced by the approach; "
            "the IT side sees control, security and day-to-day operation at "
            "risk if departments configure things for themselves."
        ),
        "case_facts": (
            "The department has already started work in a test environment "
            "without consulting IT. An internal policy forbids exactly that, "
            "and the IT side found out about it three weeks in. The IT side is "
            "not opposed to the approach in principle. It was bypassed, which "
            "is a different objection and not the one being made out loud. Two "
            "further departments are waiting to follow."
        ),
        "call_goal": (
            "Settle who decides what from here on, and who runs it once it is "
            "live."
        ),
        "success_condition": (
            "responsibility, the approval path and who operates it are each "
            "named. An assurance that IT will be involved in future, without "
            "saying how, is not one."
        ),
    },
    # S-12. Systementwurf, not evidenced: plausible for the consulting profile
    # but not recorded in an interview. The third question has no solid answer,
    # and saying so is the trained behaviour. An uncertain answer delivered
    # confidently is the failure mode.
    {
        "id": "regulated-environment-questions",
        "category": "requirements",
        "name": "Gespräch im regulierten Umfeld",
        "short_description": (
            "Drei Fragen zu Datenhaltung und Nachweisen, auf eine gibt es "
            "keine belastbare Antwort."
        ),
        "description": (
            "The customer (the persona) works in a heavily regulated area and "
            "is calling the user, who works in consulting, with questions "
            "about where data is held, who may access it, and what has to be "
            "evidenced. The caller takes notes and reads commitments back."
        ),
        "case_facts": (
            "An internal audit is due in three months and this is one of the "
            "areas it will look at. Of the three questions, two have a solid "
            "answer on record and a third does not, and whatever is said about "
            "that one will be quoted in the audit exactly as it was given. The "
            "caller has to hand their notes to a second person who was not on "
            "the call."
        ),
        "call_goal": (
            "Get an answer for each question that is solid enough to quote."
        ),
        "success_condition": (
            "every question is either answered or expressly marked as open, "
            "with a commitment on who supplies it by when. An uncertain answer "
            "that sounds certain counts as not settled."
        ),
    },
    # S-13. Systementwurf on R-06's back. The caller rings to confirm the date,
    # not knowing it has slipped. The case says nothing about it slipping,
    # because the caller does not know (ADR 0045: these are the caller's facts).
    # The Kurzbeschreibung is where the trainee learns it, that card being the
    # only briefing channel there is until ADR 0054 is built.
    {
        "id": "deadline-correction",
        "category": "operations",
        "name": "Termin- und Erwartungskorrektur",
        "short_description": (
            "Der Kunde will einen zugesagten Termin bestätigt haben. Halten "
            "lässt er sich nicht."
        ),
        "description": (
            "The customer (the persona) is calling the user, who works in "
            "project management, to have a committed date confirmed, because "
            "internal appointments have been scheduled behind it."
        ),
        "case_facts": (
            "The date was committed to six weeks ago and falls in ten days. "
            "Two further appointments have been hung on it internally, one of "
            "them with a third party who was booked eight weeks in advance and "
            "is hard to move. Nothing has been heard about the state of the "
            "work since the commitment was made, and the caller has heard "
            "nothing to suggest it is at risk."
        ),
        "call_goal": (
            "Have the date confirmed, and if it does not hold, know what "
            "applies instead and whether the appointment with the third party "
            "can still be kept."
        ),
        "success_condition": (
            "the date is confirmed, or a new one is named together with what "
            "happens to the appointment that hangs off it. A new date on its "
            "own leaves the third party unanswered."
        ),
    },
]

# --- Focus goals ----------------------------------------------------------
# The catalogue a User picks their training focus from (F-62, ADR 0076). All
# text here is German and user-facing: it is content, like a Scenario's title,
# and the interface shows it unchanged. Only "id" is English, because it is the
# key on the wire (ADR 0057/0061).
#
# "evidence" records how far a goal can be derived from a recording today:
#   measured     -- derived from the audio or the transcript
#   mixed        -- a measurable part plus an interpreted one
#   interpretive -- an appraisal, not a measurement
# It is planning information for the analysis work and is deliberately *not*
# served to the client or shown on a card. The aim is that every goal becomes
# measurable; asking a user to weigh up how far each one already is would make
# them carry an implementation detail while picking.
#
# The texts say what a goal is about, never what the system will do with it:
# nothing reads a selection yet (ADR 0076's scope), and a promise here would be
# one this release does not keep.
#
# "position" is the display order across the whole catalogue; "group" only
# decides which heading a card sits under.
FOCUS_GROUP_NAMES = {
    "paraverbal": "Stimme und Sprechweise",
    "phases": "Gesprächsverlauf",
    "impact": "Wirkung auf den Gesprächspartner",
    "habit": "Ihr Training",
}

FOCUS_GOALS = [
    # --- A. Paraverbal: the measurable core of the voice.
    {
        "id": "pace",
        "group": "paraverbal",
        "evidence": "measured",
        "position": 1,
        "title": "Ausgewogenes Sprechtempo",
        "caption": (
            "Weder gehetzt noch schleppend, sondern in einem Tempo, dem Ihr "
            "Gegenüber mühelos folgt."
        ),
        "info": (
            "Wer zu schnell spricht, wirkt nervös und überfordert sein "
            "Gegenüber. Wer zu langsam spricht, wirkt unsicher oder "
            "desinteressiert. Gefragt ist ein gleichmäßiges Tempo mit "
            "bewussten Pausen an den Sinngrenzen. Ausgewertet wird auch, an "
            "welchen Stellen Sie deutlich schneller oder langsamer werden."
        ),
    },
    {
        "id": "intonation",
        "group": "paraverbal",
        "evidence": "measured",
        "position": 2,
        "title": "Lebendige Sprachmelodie",
        "caption": "Betonung und Tonhöhe variieren, statt monoton zu klingen.",
        "info": (
            "Eine abwechslungsreiche Betonung hält die Aufmerksamkeit und "
            "transportiert das, was am Telefon sonst verloren geht. Monotonie "
            "lässt selbst gute Inhalte flach wirken. Im Blick sind die "
            "Bandbreite Ihrer Tonhöhe und die Frage, ob wichtige Aussagen "
            "hörbar hervortreten."
        ),
    },
    {
        "id": "loudness",
        "group": "paraverbal",
        "evidence": "measured",
        "position": 3,
        "title": "Souveräne Lautstärke",
        "caption": (
            "Gut hörbar und gleichmäßig, ohne zu verhallen oder zu "
            "übersteuern."
        ),
        "info": (
            "Eine stabile Lautstärke signalisiert Präsenz und Sicherheit. "
            "Fällt die Stimme am Satzende ab oder schwankt sie stark, wirkt "
            "das unsicher. Ausgewertet wird Ihr Pegel über das ganze Gespräch "
            "und damit auch die Stellen, an denen Sie deutlich leiser oder "
            "lauter werden."
        ),
    },
    {
        "id": "articulation",
        "group": "paraverbal",
        "evidence": "mixed",
        "position": 4,
        "title": "Deutliche Artikulation",
        "caption": (
            "Klar verständlich sprechen, ohne zu nuscheln oder Endungen zu "
            "verschlucken."
        ),
        "info": (
            "Am Telefon fehlt das Mundbild, deshalb trägt die Aussprache "
            "allein die Verständlichkeit. Undeutliche oder verschluckte "
            "Wörter zwingen Ihr Gegenüber zum Nachfragen und stören den "
            "Gesprächsfluss. Im Blick ist, wie klar Sie über das ganze "
            "Gespräch hinweg sprechen."
        ),
    },
    {
        "id": "conciseness",
        "group": "paraverbal",
        "evidence": "measured",
        "position": 5,
        "title": "Prägnante Sprache",
        "caption": (
            "Auf den Punkt kommen und Füllwörter, Wiederholungen und "
            "Abschweifungen reduzieren."
        ),
        "info": (
            "Füllwörter wie „ähm“, „quasi“ oder „sozusagen“ verwässern die "
            "Botschaft und lassen Unsicherheit durchscheinen. Gefragt ist eine "
            "klare Sprache, die dieselbe Aussage mit weniger Worten trägt. "
            "Ausgewertet werden Häufungen von Füllwörtern und inhaltliche "
            "Wiederholungen."
        ),
    },
    # --- B. Along the course of the call.
    {
        "id": "opening",
        "group": "phases",
        "evidence": "mixed",
        "position": 6,
        "title": "Souveräner Gesprächseinstieg",
        "caption": (
            "Begrüßung, Vorstellung und Anlass des Gesprächs klar und "
            "freundlich setzen."
        ),
        "info": (
            "Die ersten Sekunden entscheiden über den ersten Eindruck und über "
            "die Stimmung im weiteren Gespräch. Gefragt ist ein Einstieg, der "
            "Name, Anliegen und Rahmen vermittelt, ohne zu hetzen. Dabei zählt "
            "beides: Wie ruhig und zugewandt Sie klingen und ob inhaltlich "
            "nichts fehlt."
        ),
    },
    {
        "id": "needs_analysis",
        "group": "phases",
        "evidence": "mixed",
        "position": 7,
        "title": "Aktive Bedarfsermittlung",
        "caption": "Durch gezielte Fragen herausfinden, was Ihr Kunde wirklich braucht.",
        "info": (
            "Gute Gespräche leben von Fragen, nicht von Monologen. Gefragt "
            "ist, offene Fragen zu stellen, nachzuhaken und Ihrem Gegenüber "
            "Raum zu geben. Ausgewertet werden Ihr Frageanteil, Ihr Redeanteil "
            "und ob Sie an das anknüpfen, was der Kunde gesagt hat."
        ),
    },
    {
        "id": "objection_handling",
        "group": "phases",
        "evidence": "mixed",
        "position": 8,
        "title": "Sichere Einwandbehandlung",
        "caption": "Auf Bedenken und Einwände ruhig und überzeugend eingehen.",
        "info": (
            "Einwände sind der Prüfstein jedes Gesprächs. Gefragt ist, sie "
            "nicht abzuwehren, sondern aufzunehmen, zu verstehen und sachlich "
            "aufzulösen, und dabei auch unter Druck souverän zu klingen. Jede "
            "Persona bringt ihre eigenen typischen Einwände mit."
        ),
    },
    {
        "id": "closing",
        "group": "phases",
        "evidence": "interpretive",
        "position": 9,
        "title": "Klarer Gesprächsabschluss",
        "caption": (
            "Ergebnisse zusammenfassen und mit einer klaren nächsten Aktion "
            "schließen."
        ),
        "info": (
            "Ein guter Abschluss sichert Verbindlichkeit. Er fasst kurz "
            "zusammen, hält eine klare Vereinbarung fest und verabschiedet "
            "freundlich. Offene oder abrupte Enden hinterlassen Unsicherheit. "
            "Im Blick ist, ob und wie Sie das Gespräch zu Ende führen."
        ),
    },
    # --- C. What the call did to the other side.
    {
        "id": "active_listening",
        "group": "impact",
        "evidence": "mixed",
        "position": 10,
        "title": "Aktives Zuhören",
        "caption": "Ausreden lassen, aufgreifen und bestätigen, statt zu unterbrechen.",
        "info": (
            "Zuhören zeigt sich in Timing und Reaktion. Lassen Sie Ihr "
            "Gegenüber ausreden, knüpfen Sie an seine Worte an und geben Sie "
            "kurze Bestätigungen. Häufiges Unterbrechen oder ein abrupter "
            "Themenwechsel signalisieren das Gegenteil. Ausgewertet werden "
            "Unterbrechungen, Redeanteil und der inhaltliche Bezug Ihrer "
            "Antworten."
        ),
    },
    {
        "id": "empathy",
        "group": "impact",
        "evidence": "interpretive",
        "position": 11,
        "title": "Empathie und Kundenorientierung",
        "caption": "Die Situation und die Stimmung Ihres Gegenübers erkennen und aufgreifen.",
        "info": (
            "Kundenorientierung heißt, das Anliegen und die Stimmung des "
            "Gegenübers wahrzunehmen und darauf einzugehen, sprachlich wie im "
            "Ton. Gefragt ist ein zugewandter Gesprächsstil, der auch dann "
            "trägt, wenn es inhaltlich schwierig wird."
        ),
    },
    {
        "id": "composure",
        "group": "impact",
        "evidence": "mixed",
        "position": 12,
        "title": "Souveränität unter Druck",
        "caption": "Auch bei Gegenwind ruhig, klar und stabil in der Stimme bleiben.",
        "info": (
            "Kritische Kunden, Zeitdruck und Einwände dürfen Sie nicht aus dem "
            "Konzept bringen. Gefragt ist stimmliche Stabilität, also "
            "gleichmäßiges Tempo, ruhige Lautstärke und wenige Füllwörter, "
            "gerade in den fordernden Momenten. Ausgewertet wird, wie sich "
            "Ihre Werte in diesen Passagen vom Rest des Gesprächs "
            "unterscheiden."
        ),
    },
    {
        "id": "talk_share",
        "group": "impact",
        "evidence": "measured",
        "position": 13,
        "title": "Ausgewogener Redeanteil",
        "caption": "Das richtige Verhältnis zwischen selbst sprechen und sprechen lassen.",
        "info": (
            "Wer zu viel redet, verliert den Kunden. Wer zu wenig führt, "
            "verliert das Gespräch. Gefragt ist eine Balance, die Ihrem "
            "Gegenüber Raum gibt, ohne die Steuerung abzugeben. Ausgewertet "
            "wird Ihr prozentualer Redeanteil am Gespräch."
        ),
    },
    # --- D. The training habit, not the performance. Worded so that a goal
    # about how often you practise cannot be read as a judgement of how well
    # you did.
    {
        "id": "training_regularity",
        "group": "habit",
        "evidence": "measured",
        "position": 14,
        "title": "Regelmäßiges Training",
        "caption": "Dranbleiben und kontinuierlich üben statt in seltenen Schüben.",
        "info": (
            "Kommunikative Fähigkeiten wachsen durch Wiederholung. Dieses Ziel "
            "betrifft nicht Ihre Leistung im Gespräch, sondern wie gleichmäßig "
            "Sie trainieren."
        ),
    },
    {
        "id": "training_variety",
        "group": "habit",
        "evidence": "measured",
        "position": 15,
        "title": "Trainingsvielfalt",
        "caption": "Verschiedene Szenarien und Gesprächspartner bewusst durchspielen.",
        "info": (
            "Wer immer dieselbe Situation übt, wird nur in dieser Situation "
            "sicher. Dieses Ziel betrifft die Breite Ihres Trainings, also "
            "welche Kombinationen aus Szenario und Persona Sie schon gespielt "
            "haben und wo noch Lücken sind. Über die Qualität eines Gesprächs "
            "sagt es nichts."
        ),
    },
]
