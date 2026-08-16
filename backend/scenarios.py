from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str


SCENARIOS: dict[str, Scenario] = {
    # id kept stable (referenced as a dict key/default elsewhere) even though
    # the framing changed: the Persona is now the caller, not the user — see
    # CallTrainer session note on ADR 0026's opening-turn feature, which has
    # the Persona speak first as someone who initiated the call.
    "cold-call-followup": Scenario(
        id="cold-call-followup",
        name="Offenes Anliegen zu bestehendem Vertrag",
        description=(
            "Der Kunde (die Persona) ruft den Nutzer an, der im Vertrieb/Support "
            "arbeitet. Der Kunde hat eine konkrete Frage oder ein offenes "
            "Anliegen zu einem bestehenden Angebot oder Vertrag und ruft an, um "
            "das zu klären. Ziel des Calls ist es, das Anliegen zu klären und "
            "das Gespräch zu einem Abschluss (Closing) zu führen."
        ),
    ),
    "service-complaint": Scenario(
        id="service-complaint",
        name="Beschwerde über ein aktuelles Problem",
        description=(
            "Der Kunde (die Persona) ruft verärgert an, weil kürzlich etwas "
            "nicht funktioniert hat (z.B. ein Ausfall, eine falsche Abrechnung "
            "oder eine nicht wie versprochen erbrachte Leistung) und erwartet "
            "eine Erklärung sowie eine konkrete Lösung. Der Kunde ist zu Beginn "
            "spürbar unzufrieden, lässt sich aber durch eine kompetente, "
            "verbindliche Antwort beruhigen. Ziel des Calls ist es, die "
            "Beschwerde zu klären und den Kunden zufriedenzustellen."
        ),
    ),
    "price-cancellation-risk": Scenario(
        id="price-cancellation-risk",
        name="Kündigungsabsicht wegen Preis",
        description=(
            "Der Kunde (die Persona) ruft an, um mitzuteilen, dass er über "
            "eine Kündigung oder ein Downgrade nachdenkt, weil ihm die "
            "laufenden Kosten im Verhältnis zum Nutzen zu hoch erscheinen. Der "
            "Kunde ist grundsätzlich noch offen für ein Gespräch, erwartet "
            "aber eine überzeugende, nutzenorientierte Begründung, warum sich "
            "die Ausgabe weiterhin lohnt. Ziel des Calls ist es, den Kunden "
            "durch Preisverhandlung bzw. Einwandbehandlung zum Bleiben zu "
            "bewegen."
        ),
    ),
}

DEFAULT_SCENARIO_ID = "cold-call-followup"
