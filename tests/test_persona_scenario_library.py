"""The persona and scenario libraries themselves (the data, not the endpoint).

Covers:
  F-04  Kundenpersona-Bibliothek  (extensible; cost-critical customers,
        managing directors / IT leads focused on strategy & budget)
  F-03  Szenario-Typen  (support cases, pricing/offer talks, ...)
  F-01  the counterpart reflects conversational dynamics, not just facts
  ADR 0006 / R-35  German only for the MVP
  ADR 0022  language is a per-persona parameter, not a global setting
"""

import pytest

from backend.personas import PERSONAS, Persona, PersonaVoice
from backend.scenarios import SCENARIOS, Scenario

# pylint: disable=missing-function-docstring


def test_persona_library_is_non_empty_and_well_formed():
    assert PERSONAS, "F-04: the library ships at least one persona"
    for p in PERSONAS:
        assert isinstance(p, Persona)
        assert p.id and p.name and p.role
        assert p.traits, "F-01: a persona carries character traits"
        assert p.behavior, "F-01: a persona carries a behaviour description"
        assert isinstance(p.voice, PersonaVoice)


def test_persona_ids_are_unique():
    ids = [p.id for p in PERSONAS]
    assert len(ids) == len(set(ids))


def test_library_covers_the_budget_focused_decision_maker_persona():
    """F-04 / R-08: a managing director or IT lead with a strategy & budget
    focus is representable."""
    joined = " ".join(f"{p.role} {p.traits} {p.behavior}".lower() for p in PERSONAS)
    assert "geschäftsführer" in joined or "it-leiter" in joined
    assert "budget" in joined or "strategie" in joined


def test_persona_behaviour_encodes_price_pushback():
    """F-04 / R-07: a cost-critical counterpart that presses on price."""
    joined = " ".join(p.behavior.lower() for p in PERSONAS)
    assert "preis" in joined


def test_scenario_library_is_non_empty_and_well_formed():
    assert SCENARIOS, "F-03: the library ships at least one scenario"
    for s in SCENARIOS:
        assert isinstance(s, Scenario)
        assert s.id and s.name
        assert len(s.description) > 40


def test_scenario_ids_are_unique():
    ids = [s.id for s in SCENARIOS]
    assert len(ids) == len(set(ids))


def test_scenarios_cover_support_and_pricing_contexts():
    """F-03 / R-09 / R-10: at least a support-style case and a
    price/cancellation negotiation are trainable."""
    blob = " ".join(f"{s.name} {s.description}".lower() for s in SCENARIOS)
    assert "support" in blob
    assert "kündigung" in blob or "preis" in blob


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p.id)
def test_every_persona_is_german(persona):
    """ADR 0006 / R-35: German is the only supported session language for the
    MVP, so every persona is pinned to 'de'."""
    assert persona.language_id == "de"


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p.id)
def test_every_persona_has_its_own_voice(persona):
    """ADR 0022: voice/language is a per-persona property. Each persona names
    both an EFRE fallback voice and a KugelAudio voice id."""
    assert persona.voice.tts_voice
    assert isinstance(persona.voice.kugelaudio_voice_id, int)
