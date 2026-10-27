"""P116: the status table's tear-sheet row must name the same modules as the prose."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("price signals", "risk", "factor exposure", "reverse DCF", "options", "headline sentiment")


def _readme():
    return (ROOT / "README.md").read_text()


def _table_row(text):
    rows = [l for l in text.splitlines() if l.startswith("| **Tear sheet** |")]
    assert len(rows) == 1
    return rows[0]


def _prose(text):
    start = text.index("— price signals, risk")
    return " ".join(text[start:text.index("\n\n", start)].split())


def test_table_row_names_every_module_the_prose_names():
    text = _readme()
    prose, row = _prose(text), _table_row(text)
    for module in MODULES:
        assert module in prose, module
        assert module in row, module


def test_table_row_scopes_only_fundamentals_to_one_name():
    row = _table_row(_readme())
    assert "price signals for any NSE stock, full fundamentals" not in row
    assert "any NSE stock" in row
    assert "GULFOILLUB" in row
