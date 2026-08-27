"""
MkDocs-Hooks fuer die Projektdoku.

Zweck: Das ER-Diagramm auf docs/datenmodell.md soll nie veralten. Statt sich
darauf zu verlassen, dass jemand nach einer Schemaaenderung von Hand
scripts/generate_erd.py aufruft, erzeugt dieser Hook das Diagramm vor jedem
Doku-Build neu aus backend/db/models.py.

Faellt die Erzeugung aus — fehlendes Graphviz-Programm "dot", fehlende
Python-Pakete —, bricht der Build NICHT ab. Es bleibt dann beim zuletzt
eingecheckten docs/er_modell.svg, und im Build-Log steht eine Warnung. Die
Doku laesst sich damit auch auf Rechnern ohne Graphviz bauen.
"""
import importlib.util
import logging
import os

log = logging.getLogger("mkdocs.hooks.erd")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(PROJECT_ROOT, "scripts", "generate_erd.py")


def _generator_main():
    """Laedt scripts/generate_erd.py ueber seinen Pfad und gibt main() zurueck.

    Ueber den Pfad statt per Import, weil scripts/ kein Python-Paket ist.
    """
    spec = importlib.util.spec_from_file_location("generate_erd", GENERATOR)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul.main


def on_pre_build(config) -> None:  # pylint: disable=unused-argument
    """MkDocs hook: regenerate the ER diagram before each docs build.

    `config` is part of the hook signature MkDocs calls, not something this
    hook needs.
    """
    try:
        _generator_main()()
        log.info("ER-Diagramm aus backend/db/models.py neu erzeugt.")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Bewusst breit: der Build darf hieran nicht scheitern.
        log.warning(
            "ER-Diagramm konnte nicht neu erzeugt werden (%s: %s). Die Doku zeigt "
            "das zuletzt eingecheckte docs/er_modell.svg, das veraltet sein kann. "
            "Fuer die Erzeugung werden das Graphviz-Programm 'dot' und die Pakete "
            "aus requirements.txt benoetigt.",
            type(exc).__name__,
            exc,
        )
