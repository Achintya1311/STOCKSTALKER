"""Backtest tests: burn-in sizing, walk-forward scoring, the long/flat
rule, and the CLI end to end against the committed fixtures."""

import json

import numpy as np
import pandas as pd
import pytest

from stockstalker import backtest, screener
from stockstalker.data.providers import FixtureProvider


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def reliance():
    return FixtureProvider().fetch("RELIANCE.NS")


def test_burn_in_period_takes_the_slowest_indicator(cfg):
    assert backtest.burn_in_period(cfg) == max(
        cfg["trend"]["slow"], cfg["momentum"]["macd_slow"],
        cfg["volume"]["obv_window"], cfg["volume"]["z_window"],
    )


def test_walk_forward_scores_are_nan_inside_burn_in_and_bounded_after(reliance, cfg):
    burn_in = backtest.burn_in_period(cfg)
    scores = backtest.walk_forward_scores(reliance, cfg)
    assert scores.iloc[:burn_in].isna().all()
    tail = scores.iloc[burn_in:]
    assert tail.notna().all()
    assert ((tail >= 0.0) & (tail <= 1.0)).all()


def test_walk_forward_score_matches_a_full_screen_on_the_same_slice(reliance, cfg):
    """The walk-forward score at the last bar must equal what the live screener
    would compute given only that much history — same math, same answer."""
    scores = backtest.walk_forward_scores(reliance, cfg)
    signals = screener.compute_signals(reliance, cfg)
    expected = screener.blended_score(signals, cfg["weights"])
    assert scores.iloc[-1] == pytest.approx(expected)


def test_long_flat_returns_are_zero_when_score_never_clears_threshold():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame({"close": [100, 101, 102, 103, 104]}, index=idx)
    scores = pd.Series([np.nan, 0.1, 0.1, 0.1, 0.1], index=idx)
    returns = backtest.long_flat_returns(df, scores, threshold=0.5)
    assert (returns == 0.0).all()


def test_long_flat_returns_capture_the_next_bar_after_a_qualifying_score():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame({"close": [100.0, 110.0, 121.0, 90.0]}, index=idx)
    # score on day 0 qualifies -> day 1's return (10%) is captured;
    # score on day 1 does not -> day 2's return (10%) is not captured.
    scores = pd.Series([0.9, 0.1, 0.9, np.nan], index=idx)
    returns = backtest.long_flat_returns(df, scores, threshold=0.5)
    assert returns.iloc[1] == pytest.approx(0.10)
    assert returns.iloc[2] == pytest.approx(0.0)


def test_cumulative_return_compounds():
    returns = pd.Series([0.1, 0.1, -0.1])
    expected = 1.1 * 1.1 * 0.9 - 1
    assert backtest.cumulative_return(returns) == pytest.approx(expected)


def test_buy_and_hold_return_matches_manual_ratio(reliance):
    result = backtest.buy_and_hold_return(reliance, start_idx=50)
    expected = reliance["close"].iloc[-1] / reliance["close"].iloc[50] - 1
    assert result == pytest.approx(expected)


def test_buy_and_hold_return_is_zero_for_a_too_short_window(reliance):
    assert backtest.buy_and_hold_return(reliance, start_idx=len(reliance) - 1) == 0.0


def test_backtest_ticker_shape(cfg):
    result = backtest.backtest_ticker("RELIANCE.NS", "fixtures", cfg)
    assert set(result) >= {
        "ticker", "start", "end", "days_tested", "days_long",
        "strategy_return", "buy_and_hold_return", "edge", "beat_buy_and_hold",
    }
    assert result["ticker"] == "RELIANCE.NS"
    assert result["edge"] == pytest.approx(result["strategy_return"] - result["buy_and_hold_return"])
    assert result["beat_buy_and_hold"] == (result["strategy_return"] > result["buy_and_hold_return"])


def test_backtest_ticker_raises_when_history_is_too_short(cfg, monkeypatch):
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    short_df = pd.DataFrame(
        {
            "open": 1.0, "high": 1.0, "low": 1.0,
            "close": np.linspace(100, 110, 10), "volume": 1000,
        },
        index=idx,
    )
    monkeypatch.setattr(backtest, "load", lambda ticker, provider: short_df)
    from stockstalker.data.providers import ProviderError

    with pytest.raises(ProviderError):
        backtest.backtest_ticker("SHORT.NS", "fixtures", cfg)


def test_run_backtest_records_a_fetch_error_without_failing_the_run(cfg):
    errors = []
    report = backtest.run_backtest(
        ["RELIANCE.NS", "NOPE.NS"], "fixtures", cfg, generated="2026-09-07", errors=errors
    )
    assert [r["ticker"] for r in report["results"]] == ["RELIANCE.NS"]
    assert len(errors) == 1
    assert "NOPE.NS" in errors[0]


def test_run_backtest_summary_matches_results(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    report = backtest.run_backtest(tickers, "fixtures", cfg, generated="2026-09-07")
    s = report["summary"]
    assert s["tickers_tested"] == len(report["results"])
    assert s["tickers_beating_buy_and_hold"] == sum(
        1 for r in report["results"] if r["beat_buy_and_hold"]
    )
    assert s["mean_strategy_return"] == pytest.approx(
        sum(r["strategy_return"] for r in report["results"]) / len(report["results"])
    )


def test_write_json_round_trips_the_report(cfg, tmp_path):
    report = backtest.run_backtest(["RELIANCE.NS"], "fixtures", cfg, generated="2026-09-07")
    path = tmp_path / "backtest.json"
    backtest.write_json(report, path)
    assert json.loads(path.read_text()) == report


def test_write_csv_has_one_row_per_ticker(cfg, tmp_path):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    report = backtest.run_backtest(tickers, "fixtures", cfg, generated="2026-09-07")
    path = tmp_path / "backtest.csv"
    backtest.write_csv(report, path)
    rows = pd.read_csv(path)
    assert len(rows) == len(report["results"])


def test_write_markdown_reports_beats_and_caveats(cfg, tmp_path):
    report = backtest.run_backtest(["RELIANCE.NS"], "fixtures", cfg, generated="2026-09-07")
    path = tmp_path / "backtest.md"
    backtest.write_markdown(report, [], path)
    text = path.read_text()
    assert "RELIANCE.NS" in text
    assert "Caveats" in text
    assert "not statistically" in text


def test_write_markdown_handles_no_results(tmp_path):
    empty = {"generated": "2026-09-07", "threshold": 0.5, "source": "fixtures", "results": [], "summary": {}}
    path = tmp_path / "backtest.md"
    backtest.write_markdown(empty, ["BAD.NS: no fixture"], path)
    text = path.read_text()
    assert "No tickers had enough history" in text
    assert "BAD.NS: no fixture" in text


def test_main_runs_offline_against_the_real_fixtures_and_writes_all_three_files(tmp_path):
    exit_code = backtest.main(["--output-dir", str(tmp_path), "--date", "2026-09-07"])
    assert exit_code == 0
    assert (tmp_path / "backtest_2026-09-07.json").exists()
    assert (tmp_path / "backtest_2026-09-07.csv").exists()
    assert (tmp_path / "backtest_2026-09-07.md").exists()

    payload = json.loads((tmp_path / "backtest_2026-09-07.json").read_text())
    assert payload["schema"] == "backtest-v1"
    assert len(payload["results"]) == 3


def test_main_rejects_live_and_offline_together(tmp_path):
    with pytest.raises(SystemExit):
        backtest.main(["--live", "--offline", "--output-dir", str(tmp_path)])


def test_main_empty_universe_is_a_clean_failure(tmp_path):
    empty = tmp_path / "universe.txt"
    empty.write_text("# nothing here\n")
    exit_code = backtest.main(["--universe", str(empty), "--output-dir", str(tmp_path)])
    assert exit_code == 1
