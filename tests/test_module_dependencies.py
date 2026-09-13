"""The live call may not depend on the analysis of a finished one.

A structural guard, not a feature test. `backend/session/models.py` is what the
turn loop writes into while somebody is on the phone; `backend/feedback/` reads
a call that is over. The dependency ran both ways until the two readings of a
finished Session moved to `backend/feedback/calls.py` -- importing the live
module pulled in the ORM, Praat's wrappers and the whole metric inventory to
name one result type.

Nothing breaks the day that comes back, which is why it is pinned here: it
returns as one convenient import, and the cost is paid in a module whose
failures are the hardest in the application to see.

`acoustics` is the deliberate exception. It measures audio *during* the call
(`session/measuring.py`) and imports nothing back, so the live path depending
on it points the right way.

Covers:
  ADR 0033  the live path is streamed and latency-bound
  ADR 0034  a Session is read and written only after the call has ended
  ADR 0049  the wrap-up is produced in the worker, not in the request
"""
import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIVE_MODULE = ROOT / "backend" / "session" / "models.py"

# The one module of the analysis package the live path may reach for, and why:
# it runs while the call is running, and imports nothing back.
ALLOWED = {"backend.feedback.acoustics"}

_PROBE = """
import sys
import backend.session.models
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


def test_the_timeline_module_names_no_analysis_module_but_acoustics():
    """The direct imports, read off the source."""
    reached = {m for m in _imported_modules(LIVE_MODULE) if m.startswith("backend.feedback")}
    assert reached <= ALLOWED, (
        f"{LIVE_MODULE.name} imports {sorted(reached - ALLOWED)}; the two readings of a "
        "finished call live in backend/feedback/calls.py"
    )


def test_importing_the_timeline_module_does_not_load_the_analysis_package():
    """The same rule transitively, and the one that actually bites.

    In a subprocess on purpose: `sys.modules` is process-wide, so by the time
    any test runs the suite has imported half the backend, and this check would
    pass no matter what the timeline module itself does.
    """
    result = subprocess.run(
        [sys.executable, "-c", _PROBE], cwd=ROOT, capture_output=True, text=True, check=True,
    )
    loaded = set(result.stdout.split())
    analysis = {m for m in loaded if m.startswith("backend.feedback.")}
    assert analysis <= ALLOWED, f"the live call transitively loads {sorted(analysis - ALLOWED)}"
    # The ORM is the symptom that made this concrete: the in-memory turn loop
    # has no rows to map and was loading the whole schema anyway.
    assert not {m for m in loaded if m.startswith("backend.db")}, (
        "the live turn loop loads the database schema"
    )
