"""
MkDocs hooks for the project documentation.

Purpose: the ER diagram on docs/datenmodell.md should never go stale. Rather
than relying on someone running scripts/generate_erd.py by hand after a schema
change, this hook regenerates the diagram from backend/db/models.py before
every docs build.

If generating it fails — a missing Graphviz "dot" binary, missing Python
packages — the build does NOT abort. The last checked-in docs/er_modell.svg
is used instead and a warning goes into the build log, so the docs can still be
built on machines without Graphviz.
"""
import importlib.util
import logging
import os

log = logging.getLogger("mkdocs.hooks.erd")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(PROJECT_ROOT, "scripts", "generate_erd.py")


def _generator_main():
    """Loads scripts/generate_erd.py by its path and returns its main().

    By path rather than by import, because scripts/ is not a Python package.
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
        # Deliberately broad: the build must not fail because of this.
        log.warning(
            "ER-Diagramm konnte nicht neu erzeugt werden (%s: %s). Die Doku zeigt "
            "das zuletzt eingecheckte docs/er_modell.svg, das veraltet sein kann. "
            "Fuer die Erzeugung werden das Graphviz-Programm 'dot' und die Pakete "
            "aus requirements.txt benoetigt.",
            type(exc).__name__,
            exc,
        )
