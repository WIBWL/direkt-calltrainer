"""Every focus goal reaches the dashboard, read from the TypeScript as text (F-13, F-62, ADR 0076, 0080)."""
import re
from pathlib import Path

from shared.db.seed_data import FOCUS_GOALS
from worker.generator import _NEVER_ASSIGNED

FOCUS_METRICS_TS = (
    Path(__file__).resolve().parents[2] /
    "frontend" / "src" / "utils" / "focusMetrics.ts"
)

#: What a tile can be backed by, as `FocusEvidenceKind` declares them.
KINDS = {"metric", "activity", "text", "segment"}


def _focus_backing() -> dict[str, str]:
    """Read from the frontend source as text; keys are found by indentation."""
    text = FOCUS_METRICS_TS.read_text(encoding="utf-8")
    body = text.split("export const FOCUS_BACKING", 1)[1].split("= {", 1)[1]
    body = body.split("\n};", 1)[0]

    table: dict[str, str] = {}
    for match in re.finditer(r"^  (\w+):", body, re.M):
        kind = re.search(r'kind:\s*"(\w+)"', body[match.start():])
        assert kind, f"no kind on the entry for {match.group(1)}"
        table[match.group(1)] = kind.group(1)
    return table


def _seeded_goals() -> set[str]:
    return {goal["id"] for goal in FOCUS_GOALS}


def test_the_backing_table_parsed() -> None:
    table = _focus_backing()

    assert len(table) >= len(_seeded_goals())
    assert set(table.values()) <= KINDS


def test_every_shipped_goal_has_a_tile() -> None:
    missing = _seeded_goals() - set(_focus_backing())

    assert not missing, (
        f"{sorted(missing)} can be picked but has no entry in FOCUS_BACKING, so "
        f"its tile falls back to 'no measurement' however much is measured"
    )


def test_the_backing_table_names_no_goal_that_is_not_shipped() -> None:
    unknown = set(_focus_backing()) - _seeded_goals()

    assert not unknown, f"{sorted(unknown)} is backed but not in the catalogue"


def test_the_goals_without_a_call_of_their_own_are_the_habit_goals() -> None:
    by_activity = {goal for goal, kind in _focus_backing().items() if kind == "activity"}

    assert by_activity == set(_NEVER_ASSIGNED)


def test_a_goal_backed_by_metrics_names_them() -> None:
    text = FOCUS_METRICS_TS.read_text(encoding="utf-8")
    body = text.split("export const FOCUS_BACKING", 1)[1].split("= {", 1)[1]
    body = body.split("\n};", 1)[0]

    for match in re.finditer(r"^  (\w+):", body, re.M):
        entry = body[match.start():]
        kind = re.search(r'kind:\s*"(\w+)"', entry).group(1)  # type: ignore[union-attr]
        metrics = re.search(r"metrics:\s*\[(.*?)\]", entry, re.S).group(1)  # type: ignore[union-attr]
        named = bool(metrics.strip())

        if kind in {"metric", "segment"}:
            assert named, f"{match.group(1)} is backed by metrics but names none"
        else:
            assert not named, f"{match.group(1)} is {kind} but names metrics"
