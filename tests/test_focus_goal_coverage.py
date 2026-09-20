"""Every focus goal reaches the dashboard, and only the real ones do (F-62, F-13).

Covers:
  F-62      the shipped catalogue of focus goals a User picks from
  F-13      the progress view shows something per picked goal
  ADR 0076  a retired goal keeps its row; the catalogue is the seed's
  ADR 0080  the two habit goals are never assigned to a feedback point

A goal is added in one place, `seed_data.FOCUS_GOALS`, and read in three: the
dialog that offers it, `FOCUS_BACKING` for what its tile shows, and
`PRACTICE_CATEGORY` for what it is practised in (pinned in
`test_recommendations.py`). Only the first fails loudly when it is forgotten.

`backingOf` answers an unknown key with "no measurement", which is right for a
key the catalogue no longer has and wrong for one just added: a goal whose
metrics were built the same week then shows mentions instead of its fresh
series, on a tile the User picked themselves, and nothing anywhere fails. This
file is what fails instead.

Read out of the TypeScript source rather than executed, the way
`test_metrics.py` reads the metric catalogue: there is no Node in the pytest
run.
"""
import re
from pathlib import Path

from backend.db.seed_data import FOCUS_GOALS
from backend.feedback.generator import _NEVER_ASSIGNED

FOCUS_METRICS_TS = (
    Path(__file__).resolve().parent.parent /
    "frontend" / "src" / "utils" / "focusMetrics.ts"
)

#: What a tile can be backed by, as `FocusEvidenceKind` declares them.
KINDS = {"metric", "activity", "text", "segment"}


def _focus_backing() -> dict[str, str]:
    """The goal -> evidence kind table, as written in the source.

    Entries run over one line or several, so the keys are found by their
    indentation and each one's `kind` by searching forward from it -- `kind` is
    the first field of every entry.
    """
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
    """The reader above is a regex over a source file, so it can go quietly
    blind after an edit to that file's shape. Everything below would then pass
    against an empty table."""
    table = _focus_backing()

    assert len(table) >= len(_seeded_goals())
    assert set(table.values()) <= KINDS


def test_every_shipped_goal_has_a_tile() -> None:
    """A goal the User can pick has to show something, and which of the four
    shapes is a decision, not a default."""
    missing = _seeded_goals() - set(_focus_backing())

    assert not missing, (
        f"{sorted(missing)} can be picked but has no entry in FOCUS_BACKING, so "
        f"its tile falls back to 'no measurement' however much is measured"
    )


def test_the_backing_table_names_no_goal_that_is_not_shipped() -> None:
    """The other direction, which catches a retired goal and a typo alike. A
    stale entry is harmless on screen and misleading to read: it is the only
    record anywhere of which metrics a goal was thought to rest on."""
    unknown = set(_focus_backing()) - _seeded_goals()

    assert not unknown, f"{sorted(unknown)} is backed but not in the catalogue"


def test_the_goals_without_a_call_of_their_own_are_the_habit_goals() -> None:
    """`activity` on a tile and `_NEVER_ASSIGNED` in the generator are the same
    judgement: this goal is about the training itself and not about any one
    call.

    Held together because they fail in opposite directions. A goal marked
    `activity` that the wrap-up does assign loses those sentences, which reach
    no screen; one left out of `_NEVER_ASSIGNED`'s counterpart shows a tally
    over a denominator nobody can open.
    """
    by_activity = {goal for goal, kind in _focus_backing().items() if kind == "activity"}

    assert by_activity == set(_NEVER_ASSIGNED)


def test_a_goal_backed_by_metrics_names_them() -> None:
    """`metrics` is empty for every kind but `metric`, and a `metric` entry with
    an empty list renders a tile with a heading and nothing under it."""
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
