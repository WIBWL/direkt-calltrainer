"""The scripted trainee for `scripts/play_scenarios.py`.

Five user turns per call, the same five for every Scenario, so the transcripts
are comparable: the only thing that varies between two runs of different
Scenarios is the system prompt.

Four of the five are generic. The fourth is written per Scenario, because it has
to satisfy that Scenario's `success_condition`, and those differ: one wants a
figure with a validity date, another wants four points recapped. A single line
cannot do both, and a generic one would fail everywhere, which would make the
"persona never settles" flag useless.

The probes carry a constraint that is easy to miss and silent when broken.
`backend.session.language_packs.signals_closing` matches `farewell_re` AND
`postpone_re` against the *user's* text, and a match sets `force_end_call`,
which ends the call regardless of what the model said. A probe that trips it by
accident does not fail loudly, it just cuts the call short and looks like a
clean run. "I'll look into it and get back to you" is exactly such a phrase:
`get back to you` is in the English `postpone_re`.

`check_probes()` therefore validates every line against both packs, and the
script refuses to run if it fails. Probes 1 to 4 must not signal closing;
probe 5 must.
"""
from __future__ import annotations

from backend.session.language_packs import LANGUAGE_PACKS, signals_closing

# Probe slots, in order. Slot 4 is filled per Scenario from CONCRETE_ANSWERS.
ACCEPT, PULL_FACTS, VAGUE, CONCRETE, FAREWELL = range(5)

PROBE_PURPOSE = {
    ACCEPT: "Annahme des Gesprächs",
    PULL_FACTS: "Fakten ziehen",
    VAGUE: "vage Zusage, muss zurückgewiesen werden",
    CONCRETE: "konkrete Antwort, muss die Erfolgsbedingung erfüllen",
    FAREWELL: "Verabschiedung, muss den Anruf beenden",
}

# The four generic slots, per language. Deliberately role-neutral: depending on
# the Scenario the user sits in support, consulting, sales or project
# management, and one wording has to fit all of them.
GENERIC: dict[str, dict[int, str]] = {
    "de": {
        ACCEPT: (
            "Guten Tag. Ja, da sind Sie bei mir richtig. "
            "Schildern Sie mir das bitte einmal in Ruhe."
        ),
        PULL_FACTS: (
            "Können Sie mir dazu die konkreten Zahlen und Termine nennen? "
            "Seit wann läuft das, und was genau ist betroffen?"
        ),
        # No name, no date, no substance. Every success_condition in the library
        # rules a bare promise to look into it out; cold-call-followup says so
        # word for word, because that already happened eleven days ago.
        VAGUE: "Verstehe. Das nehme ich so mit und kümmere mich darum.",
        FAREWELL: "Dann machen wir das so. Vielen Dank für den Anruf, auf Wiederhören.",
    },
    "en": {
        ACCEPT: (
            "Good afternoon. Yes, you have come through to the right person. "
            "Please talk me through it."
        ),
        PULL_FACTS: (
            "Can you give me the exact figures and dates? Since when has this "
            "been going on, and what exactly is affected?"
        ),
        # "I'll get back to you" would trip postpone_re and end the call.
        VAGUE: "I see. I will take that away and look into it.",
        FAREWELL: "Then let us do it that way. Thank you for calling, goodbye.",
    },
}

# Slot 4, per Scenario key. Each line is written to satisfy that Scenario's
# `success_condition` and to use figures that agree with its `case_facts`, so a
# persona that checks the numbers cannot reject it on those grounds.
CONCRETE_ANSWERS: dict[str, dict[str, str]] = {
    "cold-call-followup": {
        "de": (
            "Der Export bricht seit dem Update vom 3. an einem Rechteproblem des "
            "zweiten Teamkontos ab. Der Fix ist für Donnerstag, den 14., eingeplant, "
            "danach läuft der Export wieder."
        ),
        "en": (
            "The export has been failing since the update on the 3rd, a permissions "
            "problem on the second team account. The fix is scheduled for Thursday "
            "the 14th, after that exports run again."
        ),
    },
    "price-cancellation-risk": {
        "de": (
            "Ich kann Ihnen 1.050 Euro halten, also den Stand vor der Erhöhung, "
            "gültig ab dem 1. des kommenden Monats für die restliche Laufzeit."
        ),
        "en": (
            "I can hold you at 1,050 euros, the level before the rise, effective "
            "from the first of next month for the rest of the term."
        ),
    },
    "escalation-repeated-outage": {
        # Five percent of 2,400 euros is 120, which is what the case facts imply.
        "de": (
            "Ursache war ein Verbindungslimit, das der Fix vom 18. April nicht "
            "abgedeckt hat. Wir ziehen die Grenze am Montag, den 22., hoch. Die "
            "Gutschrift für April über fünf Prozent, also 120 Euro, ist bestätigt "
            "und erscheint auf der Mairechnung."
        ),
        "en": (
            "The cause was a connection limit the 18 April fix did not cover. We "
            "raise it on Monday the 22nd. The five percent service credit for "
            "April, 120 euros, is confirmed and appears on the May invoice."
        ),
    },
    "upsell-seat-expansion": {
        "de": (
            "Für 30 Nutzer sind es 2.160 Euro im Monat, also 72 Euro je Nutzer nach "
            "der Staffel. Für die Einweisung schlage ich Donnerstag um 14 Uhr vor, "
            "eine Stunde."
        ),
        "en": (
            "For 30 users it is 2,160 euros a month, 72 euros each at tier price. "
            "For the walkthrough I suggest Thursday at two in the afternoon, one hour."
        ),
    },
    "closing-after-handover": {
        # Confirms three of the four remembered terms and corrects the fourth,
        # which is the branch the success condition allows.
        "de": (
            "Ich habe es geprüft: 25 Lizenzen zu 68 Euro, also 1.700 Euro im Monat, "
            "zwei Monate kündbare Testphase und Start am 1. Juli stimmen. Beim "
            "Onboarding weicht es ab, das ist nur bis zehn Nutzer kostenfrei, "
            "darüber die 1.200 Euro einmalig. Den Vertrag schicke ich Ihnen morgen "
            "zur Unterschrift, damit Sie vor dem 6. Juni durch sind."
        ),
        "en": (
            "I have checked it: 25 licences at 68 euros, so 1,700 euros a month, a "
            "two-month cancellable trial and a start on 1 July are all correct. "
            "Onboarding differs, it is free only up to ten users, above that the "
            "one-off 1,200 euros applies. I will send the contract for signature "
            "tomorrow so you are through before 6 June."
        ),
    },
    "process-halted-before-deadline": {
        "de": (
            "Die Zuordnung scheitert an einem geänderten Belegformat seit dem 9. "
            "Wir spielen die Anpassung am Mittwoch, den 17., ein, das ist vier Tage "
            "vor Ihrem Stichtag."
        ),
        "en": (
            "The assignment fails on a changed document format since the 9th. We "
            "deploy the adjustment on Wednesday the 17th, four days before your "
            "cut-off."
        ),
    },
    "explain-mandatory-change-plainly": {
        # Three steps, no jargon, each repeatable in the caller's own words.
        "de": (
            "Drei Schritte, ohne Fachwort: Erstens schicken Sie mir bis Ende des "
            "Monats eine Liste der drei Personen, die den Ablauf bedienen. Zweitens "
            "stellen wir im Mai bei jeder von ihnen eine Einstellung um, das dauert "
            "je eine halbe Stunde. Drittens laufen die ersten zwei Wochen im Juni "
            "beide Wege parallel, damit Sie vergleichen können."
        ),
        "en": (
            "Three steps, no jargon: first, send me a list of the three people who "
            "run the process by the end of the month. Second, in May we change one "
            "setting for each of them, half an hour each. Third, for the first two "
            "weeks in June both routes run side by side so you can compare."
        ),
    },
    "vague-automation-request": {
        "de": (
            "Machbar ist es, aber das entscheidet sich am Detail. Konkret: Ich komme "
            "am Dienstag, den 12., für zwei Stunden zu Ihnen und nehme mit beiden "
            "Abteilungen den Ablauf auf. Danach bekommen Sie von mir bis zum 20. "
            "eine Schätzung mit Aufwand und Preis."
        ),
        "en": (
            "It is feasible, but the detail decides it. Concretely: I come to you on "
            "Tuesday the 12th for two hours and record the process with both "
            "departments. After that you have an estimate from me with effort and "
            "price by the 20th."
        ),
    },
    "change-outside-contract-scope": {
        # The billing branch, with a reason the caller can repeat back.
        "de": (
            "Ihr Vertrag deckt Betrieb und Fehlerbehebung, und diese Anpassung ist "
            "eine Erweiterung, deshalb wird sie berechnet. Der Fall vor zwei Jahren "
            "lief als Kulanz und war ausdrücklich einmalig. Es sind vier Stunden zum "
            "vereinbarten Tagessatz."
        ),
        "en": (
            "Your contract covers operation and fault fixing, and this adjustment is "
            "an extension, which is why it is billed. The case two years ago was "
            "goodwill and expressly a one-off. It is four hours at the agreed daily "
            "rate."
        ),
    },
    "outage-escalation-no-callback": {
        "de": (
            "Frau Berger aus dem Betrieb hat den Fall seit einer Stunde. Sie meldet "
            "sich bis 16 Uhr bei Ihnen mit einem verbindlichen Zeitpunkt, und ich "
            "bleibe bis dahin dran."
        ),
        "en": (
            "Ms Berger in operations has had the case for an hour. She will contact "
            "you by four this afternoon with a firm time, and I stay on it until then."
        ),
    },
    "closing-recap-mismatch": {
        # Carries the contradiction on purpose: the caller understood the test
        # data would be supplied *to* them. The recap says the opposite, plainly
        # enough that they can notice. That is the whole exercise.
        "de": (
            "Fassen wir zusammen: Liefertermin in zwei Wochen, die Testdaten stellen "
            "Sie uns bereit, die Übergabe dokumentieren wir im Protokoll, und die "
            "zwei offenen Punkte aus dem letzten Gespräch nehme ich mit."
        ),
        "en": (
            "Let me sum up: delivery in two weeks, you provide the test data to us, "
            "we document the handover in the minutes, and I take the two open items "
            "from the last call with me."
        ),
    },
    "process-capture-interview": {
        "de": (
            "Ich spiegele das zurück: acht Schritte, drei davon mit Sonderfällen. "
            "Und da ist ein Unterschied, den Sie als dasselbe beschreiben: der eine "
            "prüft vor der Freigabe gegen die Liste, der andere gibt frei und "
            "korrigiert danach. Das ist der Grund für die eine Korrektur unter zehn."
        ),
        "en": (
            "Let me play that back: eight steps, three of them with special cases. "
            "And there is a difference you describe as if it were the same: one "
            "checks against the list before releasing, the other releases first and "
            "corrects afterwards. That is why about one entry in ten gets corrected."
        ),
    },
    "technology-choice-objections": {
        # One answer per reservation, and the middle one named openly as a risk,
        # which the success condition allows and a blanket assurance does not.
        "de": (
            "Zu den drei Punkten einzeln. Abhängigkeit: Sie können die Konfiguration "
            "jederzeit als offenes Format exportieren, das steht im Vertrag. Grenzen "
            "bei komplexen Anforderungen: Das ist ein echtes Risiko, zwei Ihrer "
            "geplanten Fälle liegen an der Grenze, die würde ich vorab prototypisieren. "
            "Tragfähigkeit: Der Hersteller sichert fünf Jahre Wartung zu, schriftlich."
        ),
        "en": (
            "The three points one by one. Dependence: you can export the "
            "configuration to an open format at any time, that is in the contract. "
            "Limits with complex requirements: that is a real risk, two of your "
            "planned cases sit at the edge, I would prototype those first. "
            "Longevity: the vendor commits to five years of maintenance, in writing."
        ),
    },
    "procurement-price-negotiation": {
        # Names the scope gap the caller was holding back, which is what turns a
        # discount into a defensible one.
        "de": (
            "Ich gebe Ihnen acht Prozent, gültig bis zum 30. dieses Monats. Mehr "
            "geht nicht, denn im Vergleichsangebot fehlen die Datenmigration und das "
            "zweite Supportjahr, die bei uns enthalten sind."
        ),
        "en": (
            "I can give you eight percent, valid until the 30th of this month. More "
            "is not possible, because the competing quote leaves out the data "
            "migration and the second year of support, which are included with us."
        ),
    },
    "sceptical-it-governance": {
        "de": (
            "Konkret: Die Fachabteilung entscheidet über Inhalte, Ihre IT über "
            "Freigabe und Betrieb. Der Freigabeweg läuft über ein Ticket bei Ihnen, "
            "Zielzeit zwei Arbeitstage. Betrieben wird es von Ihrer IT, wir stellen "
            "den zweiten Level. Die Testumgebung wird bis Freitag stillgelegt, bis "
            "das steht."
        ),
        "en": (
            "Concretely: the department decides on content, your IT on approval and "
            "operation. The approval path is a ticket with you, target two working "
            "days. Your IT operates it, we provide second level support. The test "
            "environment goes down on Friday until that is in place."
        ),
    },
    "regulated-environment-questions": {
        # Two answered, the third expressly marked open with a name and a date,
        # which is the branch that counts as settled.
        "de": (
            "Punkt eins, Datenhaltung: ausschließlich in Frankfurt, das steht im "
            "Vertrag. Punkt zwei, Zugriffsrechte: rollenbasiert, protokolliert, "
            "Export der Protokolle jederzeit möglich. Punkt drei, Nachweispflichten: "
            "Dazu habe ich heute keine belastbare Antwort. Herr Klein aus unserer "
            "Rechtsabteilung liefert sie Ihnen bis Freitag, den 14., schriftlich."
        ),
        "en": (
            "Point one, where the data is held: Frankfurt only, that is in the "
            "contract. Point two, access rights: role based, logged, and the logs "
            "can be exported at any time. Point three, evidence requirements: I have "
            "no solid answer today. Mr Klein from our legal team will supply it in "
            "writing by Friday the 14th."
        ),
    },
    "deadline-correction": {
        # A new date plus what happens to the appointment hanging off it. A new
        # date on its own is explicitly not a result.
        "de": (
            "Ich muss Ihnen den Termin absagen, er ist nicht zu halten. Realistisch "
            "ist der 5. des Folgemonats, also drei Wochen später. Für den Termin mit "
            "dem Dritten liefern wir Ihnen bis zum ursprünglichen Datum einen "
            "Teilstand, der dafür ausreicht, damit Sie den nicht verschieben müssen."
        ),
        "en": (
            "I have to withdraw the date, it cannot be held. Realistically it is the "
            "5th of next month, three weeks later. For the appointment with the "
            "third party we will give you a partial delivery by the original date "
            "that is enough for it, so you do not have to move it."
        ),
    },
}

# Used when a Scenario has no entry above, so adding one to the seed does not
# break the harness. Concrete (a name and a date) but not tailored, so the
# summary marks the run and its "persona never settles" flag is weaker.
FALLBACK_CONCRETE = {
    "de": (
        "Ich sage Ihnen das verbindlich zu: Frau Berger übernimmt das und nennt "
        "Ihnen bis Freitag, den 14., einen festen Termin."
    ),
    "en": (
        "I can commit to this: Ms Berger takes it on and will name you a firm date "
        "by Friday the 14th."
    ),
}


def probes_for(scenario_key: str | None, language: str) -> tuple[list[str], bool]:
    """The five user turns for one run, and whether slot 4 is the fallback."""
    generic = GENERIC[language]
    tailored = CONCRETE_ANSWERS.get(scenario_key or "", {}).get(language)
    return (
        [
            generic[ACCEPT],
            generic[PULL_FACTS],
            generic[VAGUE],
            tailored or FALLBACK_CONCRETE[language],
            generic[FAREWELL],
        ],
        tailored is None,
    )


def check_probes() -> list[str]:
    """Every way a probe could silently measure the wrong thing. Empty = fine.

    Run before the first LLM call: a probe that trips `signals_closing` sets
    `force_end_call` and cuts the call short, which looks like a clean short run
    rather than a broken probe.
    """
    problems = []
    for language, pack in LANGUAGE_PACKS.items():
        if language not in GENERIC:
            problems.append(f"{language}: no probe set for a language that has a pack")
            continue
        keys = list(CONCRETE_ANSWERS) + [None]
        for key in keys:
            probes, _ = probes_for(key, language)
            name = key or "<fallback>"
            for slot, text in enumerate(probes):
                closes = signals_closing(pack, text)
                if slot == FAREWELL and not closes:
                    problems.append(
                        f"{language}/{name}: probe 5 does not signal closing, "
                        f"so the backstop is never exercised"
                    )
                elif slot != FAREWELL and closes:
                    problems.append(
                        f"{language}/{name}: probe {slot + 1} "
                        f"({PROBE_PURPOSE[slot]}) trips signals_closing and would "
                        f"end the call early"
                    )
    for key, by_language in CONCRETE_ANSWERS.items():
        missing = set(GENERIC) - set(by_language)
        if missing:
            problems.append(f"{key}: no concrete answer for {', '.join(sorted(missing))}")
    return problems
