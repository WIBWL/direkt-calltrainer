from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str


SCENARIOS: list[Scenario] = [
    Scenario(
        id="cold-call-followup",
        name="Offenes Anliegen zu bestehendem Vertrag",
        description=(
            "Der Kunde (die Persona) ruft den Nutzer an, der im Support "
            "arbeitet. Der Kunde hat eine konkrete Frage oder ein offenes "
            "Anliegen zu einem bestehenden Angebot oder Vertrag und ruft an, um "
            "das zu klären. Ziel des Anrufs ist es, das Anliegen zu klären und "
            "das Gespräch zu einem Abschluss zu führen."
        ),
    ),
    Scenario(
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
]
