"""Guards for features the docs describe but the application does NOT implement.

They assert the current state on purpose: when one fails, the feature has landed
and needs its own tests. F-56 (UI language switch): not built; each Persona has
one fixed language (ADR 0043) and the UI is German. A guard must name the route
the feature would really take, or it only guards a spelling (the history guard
watched `/api/history` while the feature shipped as `GET /api/sessions`)."""

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def _read(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def test_frontend_has_no_ui_language_switch_yet():
    """F-56: the DE/EN UI toggle is not implemented."""
    src_files = list((REPO / "frontend" / "src").rglob("*.ts*"))
    joined = "\n".join(_read(p.relative_to(REPO)) for p in src_files).lower()
    assert "i18n" not in joined
    assert "usetranslation" not in joined
