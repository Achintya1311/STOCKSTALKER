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


SCOPE = (
    "price signals, risk, factor exposure, a reverse DCF from public financials, "
    "options for F&O stocks and headline sentiment for any NSE stock; full fundamentals are hand-built for one name"
)


def test_no_line_claims_every_module_for_any_stock():
    # Request 23 (desk-review 2026-10-27): fundamentals are GULFOILLUB-only and
    # options need an F&O listing, so "every module" overclaims.
    text = _readme()
    assert "every module for any NSE stock" not in text
    assert "every module's live or committed findings" not in text


def test_table_row_and_status_use_the_site_scope_sentence():
    text = _readme()
    assert SCOPE in _table_row(text)
    status = next(l for l in text.splitlines() if l.startswith("**Status:**"))
    assert SCOPE in status
