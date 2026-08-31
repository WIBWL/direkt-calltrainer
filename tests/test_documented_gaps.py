"""Guards for features that the docs describe but the MVP does NOT yet
implement. These tests assert the *current* state on purpose: when one
starts failing, the corresponding feature has landed and needs its own
proper feature tests (and this guard removed).

  ADR 0034      session data is decided-to-be-persisted but not yet wired
                into app.py / session_ws.py
  F-09 / F-10   AI-generated feedback + concrete suggestions: the async
                worker of ADR 0018/0019 is not built
  F-13 / F-48   progress history across sessions: needs auth (ADR 0009)
  F-53          evaluation dashboard: not built
  F-56          UI language switch (DE/EN): not built
  F-58 / F-34   user-authored / document-derived scenarios: not built
  R-12          spontaneous objections: `persona_einwand` exists (ADR 0026)
                but is seeded empty and never read -- ADR 0045 closes this
  ADR 0045      the Scenario carries no case facts, call goal or success
                condition yet
"""

from pathlib import Path

import pytest

from backend.app import app
from backend.db import models
from tests.conftest import load_seed_module

# pylint: disable=missing-function-docstring

REPO = Path(__file__).resolve().parent.parent


def _read(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def test_session_persistence_is_not_yet_wired_in():
    """ADR 0034 is 'Accepted' but the live path still opens no DB session."""
    app_src = _read("backend/app.py")
    ws_src = _read("backend/api/session_ws.py")
    for src in (app_src, ws_src):
        assert "session_scope" not in src
        assert "backend.db" not in src


def test_no_feedback_generation_pipeline_exists():
    """F-09/F-10: no module produces qualitative feedback yet."""
    backend_files = list((REPO / "backend").rglob("*.py"))
    joined = "\n".join(p.name for p in backend_files)
    assert "feedback_worker.py" not in joined
    assert not (REPO / "backend" / "analysis").exists()
    assert not (REPO / "backend" / "feedback").exists()


def test_no_rq_or_redis_worker_is_configured():
    """ADR 0019's job queue is not built."""
    reqs = _read("requirements.txt").lower()
    assert "rq" not in reqs.split()
    assert "redis" not in reqs


def test_personas_carry_no_objections_yet():
    """R-12 / ADR 0045: `persona_einwand` has existed since ADR 0026, but every
    seeded Persona gets an empty list and `library.py` never loads the
    relation, so no objection can reach a call."""
    seed = load_seed_module()
    assert seed.PERSONAS, "the seed ships personas at all"
    assert all(entry["einwaende"] == [] for entry in seed.PERSONAS)
    assert "einwaende" not in _read("backend/library.py")


def test_scenarios_carry_no_case_facts_yet():
    """ADR 0045: the Scenario is a situation, not a case — it has no facts, no
    call goal and no success condition, so the model improvises the case anew
    on every Session."""
    for column in ("fallfakten", "anrufziel", "erfolgsbedingung"):
        assert not hasattr(models.Szenario, column)


def test_the_prompt_frame_still_tells_the_model_to_invent_the_case():
    """ADR 0045: until case facts exist, the frame has nothing to point the
    model at and asks it to make the specifics up instead."""
    orch = _read("backend/session/orchestrator.py")
    assert "invent" in orch and "concrete, plausible details" in orch
    assert "never contradict" not in orch.lower()
