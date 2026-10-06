"""Guards for documented features that are not built (F-56); a failure means one landed."""

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _read(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def test_frontend_has_no_ui_language_switch_yet():
    src_files = list((REPO / "frontend" / "src").rglob("*.ts*"))
    joined = "\n".join(_read(p.relative_to(REPO)) for p in src_files).lower()
    assert "i18n" not in joined
    assert "usetranslation" not in joined
