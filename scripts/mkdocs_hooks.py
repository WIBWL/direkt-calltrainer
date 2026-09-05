"""
MkDocs hooks for the project documentation.

Purpose: the ER diagram on docs/datenmodell.md must never go stale. Rather than
relying on someone calling scripts/generate_erd.py by hand after a schema
change, this hook regenerates it from backend/db/models.py before every docs
build.

If generation fails — no Graphviz "dot" binary, missing Python packages — the
build does NOT abort. The last committed docs/er_modell.svg is used instead and
a warning goes into the build log, so the docs still build on machines without
Graphviz.
"""
import importlib.util
import logging
import os

log = logging.getLogger("mkdocs.hooks.erd")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(PROJECT_ROOT, "scripts", "generate_erd.py")


def _generator_main():
    """Loads scripts/generate_erd.py by path and returns its main().

    By path rather than by import, because scripts/ is not a Python package.
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
        log.info("Regenerated the ER diagram from backend/db/models.py.")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Deliberately broad: the docs build must not fail because of this.
        log.warning(
            "Could not regenerate the ER diagram (%s: %s). The docs will show the "
            "last committed docs/er_modell.svg, which may be out of date. "
            "Generating it needs the Graphviz 'dot' binary and the packages from "
            "requirements.txt.",
            type(exc).__name__,
            exc,
        )
