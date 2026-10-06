"""Package boundaries and the live call's independence from the analysis (ADR 0090, 0108)."""
import ast
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SESSION = ROOT / "backend" / "session"

# The seam: writes the finished call, after it has ended (ADR 0034).
SEAM = {"persistence.py"}

LIVE_MODULES = sorted(p for p in SESSION.glob("*.py") if p.name not in SEAM and p.name != "__init__.py")

# What a live module is imported as, for the transitive probe. The orchestrator
# is the turn loop; loading it loads every live module it runs.
LIVE_ENTRY_POINTS = ("backend.session.events", "backend.session.orchestrator")

# The one module of the analysis the live path may reach for, and why: it runs
# while the call is running, and imports nothing back.
ALLOWED = {"shared.feedback.acoustics"}
ANALYSIS = ("shared.feedback", "backend.feedback", "worker")

# Which package may import which: its own and `shared`, nothing else.
PACKAGES = {"shared": {"shared"}, "backend": {"shared", "backend"}, "worker": {"shared", "worker"}}

_PROBE = """
import importlib, sys
importlib.import_module(sys.argv[1])
print(" ".join(sorted(m for m in sys.modules if m.split(".")[0] in ("backend", "shared", "worker"))))
"""


def _package_modules(package):
    """The package's own source files -- its test suite is not in the image."""
    return sorted(p for p in (ROOT / package).rglob("*.py")
                  if "tests" not in p.relative_to(ROOT / package).parts)


def _probe(module):
    """The first-party modules loaded by importing `module`, in a fresh process:
    `sys.modules` is process-wide and the suite has imported everything already."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, module], cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return set(result.stdout.split())


@pytest.mark.parametrize("package", sorted(PACKAGES))
def test_a_package_imports_only_itself_and_shared(package):
    wrong = {
        f"{path.relative_to(ROOT)}: {module}"
        for path in _package_modules(package)
        for module in _imported_modules(path)
        if module.split(".")[0] in PACKAGES and module.split(".")[0] not in PACKAGES[package]
    }
    assert not wrong, f"{package} reaches outside shared: {sorted(wrong)}"


@pytest.mark.parametrize(("entry_point", "never"), [
    ("backend.app", "worker"),
    ("worker.__main__", "backend"),
    ("worker.generator", "backend"),
])
def test_loading_a_process_does_not_load_the_other(entry_point, never):
    loaded = _probe(entry_point)
    assert not {m for m in loaded if m.split(".")[0] == never}, (
        f"{entry_point} loads {never}: {sorted(m for m in loaded if m.split('.')[0] == never)}"
    )


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
    assert all((SESSION / name).exists() for name in SEAM)


@pytest.mark.parametrize("path", LIVE_MODULES, ids=lambda p: p.name)
def test_a_live_module_names_no_analysis_module_but_acoustics(path):
    reached = {m for m in _imported_modules(path) if m.startswith(ANALYSIS)}
    assert reached <= ALLOWED, (
        f"{path.name} imports {sorted(reached - ALLOWED)}; the analysis of a finished call "
        "starts at backend/session/persistence.py, after the call has ended"
    )


@pytest.mark.parametrize("module", LIVE_ENTRY_POINTS)
def test_loading_the_live_path_does_not_load_the_analysis_package(module):
    loaded = _probe(module)
    analysis = {m for m in loaded if m.startswith(ANALYSIS) and m not in ANALYSIS}
    assert analysis <= ALLOWED, f"{module} transitively loads {sorted(analysis - ALLOWED)}"
    # The ORM is the symptom that made this concrete: the in-memory turn loop
    # has no rows to map and was loading the whole schema anyway.
    assert not {m for m in loaded if m.startswith(("shared.db", "backend.db"))}, (
        "the live turn loop loads the database schema"
    )
