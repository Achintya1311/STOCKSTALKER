"""Request 25 (desk-review 2026-10-27): the lab re-runs its leaderboard, so the
README must not pin a trial count or t-bar that goes stale."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _leaderboard_line():
    text = (ROOT / "README.md").read_text()
    lines = [l for l in text.splitlines() if "train_leaderboard.md" in l and l.startswith("- ")]
    assert len(lines) == 1
    return lines[0]


def test_leaderboard_line_pins_no_counts_or_bar():
    line = _leaderboard_line()
    assert not re.search(r"\d+ of \d+ trials", line)
    assert not re.search(r"t ≥ \d", line)
    assert "see the file" in line
