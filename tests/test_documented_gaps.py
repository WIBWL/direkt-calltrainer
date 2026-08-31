"""Guards for features that the docs describe but the MVP does NOT yet
implement. These tests assert the *current* state on purpose: when one
starts failing, the corresponding feature has landed and needs its own
proper feature tests (and this guard removed).

  ADR 0034      session data is decided-to-be-persisted but not yet wired
                into app.py / session_ws.py
  F-09 / F-10   AI-generated feedback + concrete suggestions: the async
                worker of ADR 0018/0019 is not built
  F-13 / F-48   progress history across sessions: auth (ADR 0009) is now built,
                but persistence (ADR 0034) and per-user history are not
  F-53          evaluation dashboard: not built
  F-56          UI language switch (DE/EN): not built
  F-58 / F-34   user-authored / document-derived scenarios: not built
"""

from pathlib import Path

import pytest

from backend.app import app

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


def test_only_german_is_supported():
    """ADR 0006: English was removed, not hidden. No language map beyond 'de'."""
    orch = _read("backend/session/orchestrator.py")
    assert '_LANGUAGE_NAMES_EN: dict[str, str] = {"de": "German"}' in orch


def test_frontend_has_no_ui_language_switch_yet():
    """F-56: the DE/EN UI toggle is not implemented."""
    src_files = list((REPO / "frontend" / "src").rglob("*.ts*"))
    joined = "\n".join(_read(p.relative_to(REPO)) for p in src_files).lower()
    assert "i18n" not in joined
    assert "usetranslation" not in joined


@pytest.mark.parametrize("endpoint", ["/api/feedback", "/api/sessions", "/api/history"])
def test_no_history_or_feedback_endpoints_are_registered(endpoint):
    """F-13/F-48/F-53: nothing serves past-session data yet."""
    routes = {getattr(r, "path", None) for r in app.routes}
    assert endpoint not in routes
