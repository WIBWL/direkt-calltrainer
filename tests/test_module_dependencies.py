"""The live call may not depend on the analysis of a finished one (ADR 0033/0034/0049).

Nothing in `backend/session/` or loaded by `orchestrator.py` may import `backend/feedback/`, except
`acoustics` (measures during the call, imports nothing back). The seam is `session/persistence.py` and
`session_ws._record`, which run after the call ended. A regression breaks nothing visibly, hence this guard."""
import ast
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SESSION = ROOT / "backend" / "session"

# The seam: writes the finished call, after it has ended (ADR 0034).
SEAM = {"persistence.py"}

LIVE_MODULES = sorted(p for p in SESSION.glob("*.py") if p.name not in SEAM and p.name != "__init__.py")

# What a live module is imported as, for the transitive probe. The orchestrator
# is the turn loop; loading it loads every live module it runs.
LIVE_ENTRY_POINTS = ("backend.session.models", "backend.session.orchestrator")

# The one module of the analysis package the live path may reach for, and why:
# it runs while the call is running, and imports nothing back.
ALLOWED = {"backend.feedback.acoustics"}

_PROBE = """
import importlib, sys
importlib.import_module(sys.argv[1])
print(" ".join(sorted(m for m in sys.modules if m.startswith("backend."))))
"""


def _imported_modules(path):
    """Every module named by an import statement in one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_seam_is_still_there():
    """If the seam were renamed, the glob above would quietly start calling it
    live and this file would fail for the wrong reason -- or, worse, a new
    module named like it would be exempt."""
    assert all((SESSION / name).exists() for name in SEAM)


@pytest.mark.parametrize("path", LIVE_MODULES, ids=lambda p: p.name)
def test_a_live_module_names_no_analysis_module_but_acoustics(path):
    """The direct imports, read off the source."""
    reached = {m for m in _imported_modules(path) if m.startswith("backend.feedback")}
    assert reached <= ALLOWED, (
        f"{path.name} imports {sorted(reached - ALLOWED)}; the analysis of a finished call "
        "starts at backend/session/persistence.py, after the call has ended"
    )


@pytest.mark.parametrize("module", LIVE_ENTRY_POINTS)
def test_loading_the_live_path_does_not_load_the_analysis_package(module):
    """The same rule transitively, and the one that actually bites.

    In a subprocess: `sys.modules` is process-wide and the suite has imported half the
    backend already, so in-process this would always pass.
    """
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, module], cwd=ROOT, capture_output=True, text=True, check=True,
    )
    loaded = set(result.stdout.split())
    analysis = {m for m in loaded if m.startswith("backend.feedback.")}
    assert analysis <= ALLOWED, f"{module} transitively loads {sorted(analysis - ALLOWED)}"
    # The ORM is the symptom that made this concrete: the in-memory turn loop
    # has no rows to map and was loading the whole schema anyway.
    assert not {m for m in loaded if m.startswith("backend.db")}, (
        "the live turn loop loads the database schema"
    )
