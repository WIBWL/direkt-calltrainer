"""Guards for features that the docs describe but the MVP does NOT yet
implement. These tests assert the *current* state on purpose: when one
starts failing, the corresponding feature has landed and needs its own
proper feature tests (and this guard removed).

  F-13 / F-48   progress history across sessions: auth (ADR 0009) and
                persistence (ADR 0034) are both built, but nothing reads a
                user's earlier Sessions
  F-53          cross-session evaluation dashboard: not built
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


def test_frontend_has_no_ui_language_switch_yet():
    """F-56: the DE/EN UI toggle is not implemented."""
    src_files = list((REPO / "frontend" / "src").rglob("*.ts*"))
    joined = "\n".join(_read(p.relative_to(REPO)) for p in src_files).lower()
    assert "i18n" not in joined
    assert "usetranslation" not in joined


@pytest.mark.parametrize("endpoint", ["/api/feedback", "/api/history"])
def test_no_cross_session_history_endpoints_are_registered(endpoint):
    """F-13/F-48/F-53: only the Session just finished is readable, via
    /api/sessions/{extern_id} (ADR 0050). There is no history."""
    routes = {getattr(r, "path", None) for r in app.routes}
    assert endpoint not in routes
