"""R31: the threshold grid, every cell reported, default marked."""

import json

import pytest

from stockstalker import backtest, screener


@pytest.fixture(scope="module")
def grid():
    cfg = screener.load_config(screener.CONFIG_PATH)
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    return backtest.run_threshold_grid(tickers, "fixtures", cfg), backtest.run_backtest(tickers, "fixtures", cfg)


def test_grid_is_the_stated_one_and_marks_the_default():
    assert backtest.THRESHOLD_GRID == (0.40, 0.45, 0.50, 0.55, 0.60)
    assert backtest.DEFAULT_THRESHOLD in backtest.THRESHOLD_GRID


def test_every_cell_is_reported(grid):
    rows, _ = grid
    assert [r["threshold"] for r in rows] == list(backtest.THRESHOLD_GRID)
    assert [r["default"] for r in rows] == [t == backtest.DEFAULT_THRESHOLD for t in backtest.THRESHOLD_GRID]
    for r in rows:
        assert len(r["percentiles"]) == r["tickers_tested"] == 3


def test_default_row_equals_the_headline(grid):
    rows, headline = grid
    row = next(r for r in rows if r["default"])
    s = headline["summary"]
    assert row["tickers_beating_exposure_matched_random"] == s["tickers_beating_exposure_matched_random"]
    assert row["tickers_beating_buy_and_hold_with_costs"] == s["tickers_beating_buy_and_hold_with_costs"]
    assert row["percentiles"] == {r["ticker"]: r["exposure_matched_percentile"] for r in headline["results"]}


def test_precomputed_scores_give_the_same_result():
    cfg = screener.load_config(screener.CONFIG_PATH)
    from stockstalker.data.providers import load
    scores = backtest.walk_forward_scores(load("CROMPTON.NS", provider="fixtures"), cfg)
    a = backtest.backtest_ticker("CROMPTON.NS", "fixtures", cfg, 0.55)
    b = backtest.backtest_ticker("CROMPTON.NS", "fixtures", cfg, 0.55, scores=scores)
    assert a == b


def test_cli_threshold_grid_flag(tmp_path, capsys):
    backtest.main(["--offline", "--threshold-grid", "--output-dir", str(tmp_path), "--date", "2026-10-27"])
    out = capsys.readouterr().out
    assert "Threshold grid" in out
    report = json.loads((tmp_path / "backtest_2026-10-27.json").read_text())
    assert [r["threshold"] for r in report["threshold_grid"]] == list(backtest.THRESHOLD_GRID)
