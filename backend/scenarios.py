from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str


SCENARIOS: dict[str, Scenario] = {
    "cold-call-followup": Scenario(
        id="cold-call-followup",
        name="Follow-up-/Closing-Call nach Kaltakquise",
        description=(
            "Der Nutzer ruft einen Kunden an, der zuvor per externer Kaltakquise "
            "kontaktiert wurde. Ziel des Calls ist es, das Gespräch zum Abschluss "
            "(Closing) zu führen."
        ),
    ),
}

DEFAULT_SCENARIO_ID = "cold-call-followup"
