"""Guards for features that the docs describe but the application does NOT yet
implement. These tests assert the *current* state on purpose: when one starts
failing, the corresponding feature has landed and needs its own proper feature
tests (and this guard removed).

  F-56          UI language switch (DE/EN): not built. Each Persona has one
                fixed language (ADR 0043) and the interface itself is German
                throughout, so there is nothing to toggle yet.

Removed guards, each because the feature landed and brought its own tests:
F-13/F-48 (the history and the progress view -- `test_session_history.py`) and
F-58/F-34 (authored and document-derived Scenarios -- `test_scenario_documents.py`,
`test_persona_scenario_library.py`). The history guard is worth a note: it
watched for `/api/history` and `/api/feedback`, and the feature shipped as
`GET /api/sessions`, so it never failed and went on reading as a live guard
long after what it guarded was gone. A current-state guard has to name the
route the feature would actually take, or it only guards a spelling.
"""

from pathlib import Path

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
