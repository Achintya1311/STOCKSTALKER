"""S27: every named-stock CLI prints PLAN.md rule 1's disclaimer, not only the tear sheet."""

import importlib
import json

import pytest

from stockstalker import backtest, report, screener
from stockstalker.disclaimer import DISCLAIMER

RULE_1 = "Educational research on historical data. Not investment advice. Not a SEBI-registered research analyst."
GATES = ("factor", "fundamentals", "risk", "sentiment", "sizing", "valuation", "vol")


def test_disclaimer_is_rule_1_verbatim():
    assert DISCLAIMER == RULE_1


def test_screener_prints_and_writes_the_disclaimer(tmp_path, capsys):
    screener.main(["--offline", "--output-dir", str(tmp_path), "--date", "2026-10-30"])
    assert RULE_1 in capsys.readouterr().out
    assert RULE_1 in (tmp_path / "screen_2026-10-30.md").read_text()


def test_backtest_prints_the_disclaimer(tmp_path, capsys):
    backtest.main(["--offline", "--output-dir", str(tmp_path), "--date", "2026-10-30"])
    assert RULE_1 in capsys.readouterr().out


def test_report_prints_the_disclaimer(tmp_path, capsys):
    report.main(["--output-dir", str(tmp_path), "--date", "2026-10-30", "--no-charts"])
    assert RULE_1 in capsys.readouterr().out


@pytest.mark.parametrize("name", GATES)
def test_gate_prints_the_disclaimer(name, tmp_path, capsys, monkeypatch):
    gate = importlib.import_module(f"stockstalker.gates.{name}")
    monkeypatch.setattr(gate, "load_contract", lambda path: {})
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps({"schema": "v1", "candidates": []}))
    gate.main(["--screen", str(screen_path), "--contract", "unused.json", "--ticker", "ZZZ.NS"])
    assert RULE_1 in capsys.readouterr().out
