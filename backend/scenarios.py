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
        name="Eingehender Anruf: Kunde mit offenem Anliegen",
        description=(
            "Der Kunde (die Persona) ruft den Nutzer an, der im Vertrieb/Support "
            "arbeitet. Der Kunde hat eine konkrete Frage oder ein offenes "
            "Anliegen zu einem bestehenden Angebot oder Vertrag und ruft an, um "
            "das zu klären. Ziel des Calls ist es, das Anliegen zu klären und "
            "das Gespräch zu einem Abschluss (Closing) zu führen."
        ),
    ),
}

DEFAULT_SCENARIO_ID = "cold-call-followup"
