"""Backtest tests: burn-in sizing, walk-forward scoring, the long/flat
rule, and the CLI end to end against the committed fixtures."""

import copy
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


def test_burn_in_period_includes_rsi_period_when_it_is_the_slowest_window(cfg):
    cfg = copy.deepcopy(cfg)
    other_windows = (
        cfg["trend"]["slow"], cfg["momentum"]["macd_slow"],
        cfg["volume"]["obv_window"], cfg["volume"]["z_window"],
    )
    cfg["momentum"]["rsi_period"] = max(other_windows) + 5
    assert backtest.burn_in_period(cfg) >= cfg["momentum"]["rsi_period"]


def test_walk_forward_scores_wait_for_rsi_when_it_is_the_slowest_signal(reliance, cfg):
    """D17: a config where ``rsi_period`` exceeds every other window must not
    let the blended score go non-NaN before RSI itself has a defined value —
    otherwise momentum silently scores 0.0 for bars that aren't tested yet."""
    cfg = copy.deepcopy(cfg)
    other_windows = (
        cfg["trend"]["slow"], cfg["momentum"]["macd_slow"],
        cfg["volume"]["obv_window"], cfg["volume"]["z_window"],
    )
    rsi_period = max(other_windows) + 5
    cfg["momentum"]["rsi_period"] = rsi_period

    scores = backtest.walk_forward_scores(reliance, cfg)
    rsi_first_defined_position = rsi_period  # rsi()'s first `period` points are NaN
    first_non_nan_position = scores.index.get_loc(scores.first_valid_index())
    assert first_non_nan_position >= rsi_first_defined_position


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


def test_holdings_from_scores_mirrors_long_flat_returns_shift():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    scores = pd.Series([0.9, 0.1, 0.9, np.nan], index=idx)
    holdings = backtest.holdings_from_scores(scores, threshold=0.5)
    assert list(holdings) == [False, True, False, True]


def test_trading_cost_series_charges_both_legs_on_a_one_day_hold():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    holdings = pd.Series([False, True, False, True], index=idx)
    costs = backtest.trading_cost_series(holdings, buy_cost_rate=0.01, sell_cost_rate=0.02)
    assert costs.iloc[0] == 0.0
    assert costs.iloc[1] == pytest.approx(0.03)  # one-day hold: entry and exit same day
    assert costs.iloc[2] == 0.0
    assert costs.iloc[3] == pytest.approx(0.03)  # still long at the end of the series


def test_trading_cost_series_splits_entry_and_exit_over_a_multi_day_hold():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    holdings = pd.Series([False, True, True, False], index=idx)
    costs = backtest.trading_cost_series(holdings, buy_cost_rate=0.01, sell_cost_rate=0.02)
    assert costs.iloc[0] == 0.0
    assert costs.iloc[1] == pytest.approx(0.01)
    assert costs.iloc[2] == pytest.approx(0.02)
    assert costs.iloc[3] == 0.0


def test_long_flat_returns_with_costs_never_beats_the_no_cost_version():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame({"close": [100.0, 110.0, 121.0, 90.0]}, index=idx)
    scores = pd.Series([0.9, 0.1, 0.9, np.nan], index=idx)
    gross = backtest.long_flat_returns(df, scores, threshold=0.5)
    net = backtest.long_flat_returns_with_costs(df, scores, threshold=0.5, slippage_bps=10.0)
    assert (net <= gross + 1e-12).all()
    assert net.iloc[1] < gross.iloc[1]


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


def test_buy_and_hold_return_with_costs_is_worse_than_the_no_cost_version(reliance):
    gross = backtest.buy_and_hold_return(reliance, start_idx=50)
    net = backtest.buy_and_hold_return_with_costs(reliance, start_idx=50, slippage_bps=10.0)
    assert net < gross


def test_buy_and_hold_return_with_costs_matches_manual_round_trip(reliance):
    net = backtest.buy_and_hold_return_with_costs(reliance, start_idx=50, slippage_bps=10.0)
    buy_rate = backtest.STT_RATE + backtest.STAMP_DUTY_RATE + 0.0010
    sell_rate = backtest.STT_RATE + 0.0010
    entry = reliance["close"].iloc[50] * (1 + buy_rate)
    exit_ = reliance["close"].iloc[-1] * (1 - sell_rate)
    assert net == pytest.approx(exit_ / entry - 1)


def test_buy_and_hold_return_with_costs_is_zero_for_a_too_short_window(reliance):
    assert backtest.buy_and_hold_return_with_costs(reliance, start_idx=len(reliance) - 1) == 0.0


def test_random_exposure_returns_is_deterministic_and_bounded_by_draw_count():
    idx = pd.date_range("2024-01-01", periods=6, freq="D")
    df = pd.DataFrame({"close": [100.0, 110.0, 99.0, 108.9, 98.0, 107.8]}, index=idx)
    draws_a = backtest.random_exposure_returns(df, start_idx=1, days_long=2, n_draws=50, seed=7)
    draws_b = backtest.random_exposure_returns(df, start_idx=1, days_long=2, n_draws=50, seed=7)
    assert len(draws_a) == 50
    np.testing.assert_array_equal(draws_a, draws_b)  # same seed, same draws


def test_random_exposure_returns_with_full_exposure_matches_buy_and_hold_style_compounding():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame({"close": [100.0, 110.0, 121.0, 108.9, 120.0]}, index=idx)
    daily_return = df["close"].pct_change().iloc[1:]
    expected = float((1 + daily_return).prod() - 1)
    # days_long == every tested day -> only one possible subset, every draw identical
    draws = backtest.random_exposure_returns(df, start_idx=1, days_long=len(daily_return), n_draws=10, seed=1)
    assert draws == pytest.approx(expected)


def test_random_exposure_returns_is_zero_when_days_long_is_zero():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame({"close": [100.0, 110.0, 90.0, 95.0]}, index=idx)
    draws = backtest.random_exposure_returns(df, start_idx=1, days_long=0, n_draws=20, seed=3)
    assert (draws == 0.0).all()


def test_backtest_ticker_reports_the_exposure_matched_random_baseline(cfg):
    # Characterizes D16: the strategy must be compared against being long
    # `days_long` days picked at random, not just against 100%-exposure
    # buy-and-hold -- this is new and absent before the D16 fix.
    result = backtest.backtest_ticker("RELIANCE.NS", "fixtures", cfg)
    assert "exposure_matched_mean_return" in result
    assert "exposure_matched_std_return" in result
    assert "beat_exposure_matched_random" in result
    assert "exposure_matched_percentile" in result
    assert result["exposure_matched_std_return"] >= 0.0
    assert 0.0 <= result["exposure_matched_percentile"] <= 1.0
    assert result["beat_exposure_matched_random"] == (
        result["strategy_return"] > result["exposure_matched_mean_return"]
    )


def test_backtest_ticker_exposure_matched_baseline_is_deterministic_across_runs(cfg):
    first = backtest.backtest_ticker("RELIANCE.NS", "fixtures", cfg)
    second = backtest.backtest_ticker("RELIANCE.NS", "fixtures", cfg)
    assert first["exposure_matched_mean_return"] == second["exposure_matched_mean_return"]
    assert first["exposure_matched_std_return"] == second["exposure_matched_std_return"]


def test_run_backtest_summary_reports_exposure_matched_count_and_edge_uncertainty(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    report = backtest.run_backtest(tickers, "fixtures", cfg, generated="2026-09-07")
    s = report["summary"]
    assert "tickers_beating_exposure_matched_random" in s
    assert s["tickers_beating_exposure_matched_random"] == sum(
        1 for r in report["results"] if r["beat_exposure_matched_random"]
    )
    assert "mean_edge_stderr" in s
    edges = [r["edge"] for r in report["results"]]
    expected_stderr = float(np.std(edges, ddof=1) / np.sqrt(len(edges)))
    assert s["mean_edge_stderr"] == pytest.approx(expected_stderr, abs=5e-5)


def test_backtest_ticker_shape(cfg):
    result = backtest.backtest_ticker("RELIANCE.NS", "fixtures", cfg)
    assert set(result) >= {
        "ticker", "start", "end", "days_tested", "days_long",
        "strategy_return", "strategy_return_with_costs",
        "buy_and_hold_return", "buy_and_hold_return_with_costs",
        "edge", "edge_with_costs",
        "beat_buy_and_hold", "beat_buy_and_hold_with_costs",
        "exposure_matched_mean_return", "exposure_matched_std_return",
        "beat_exposure_matched_random", "exposure_matched_percentile",
    }
    assert result["ticker"] == "RELIANCE.NS"
    assert result["edge"] == pytest.approx(result["strategy_return"] - result["buy_and_hold_return"])
    assert result["beat_buy_and_hold"] == (result["strategy_return"] > result["buy_and_hold_return"])
    assert result["edge_with_costs"] == pytest.approx(
        result["strategy_return_with_costs"] - result["buy_and_hold_return_with_costs"]
    )
    assert result["beat_buy_and_hold_with_costs"] == (
        result["strategy_return_with_costs"] > result["buy_and_hold_return_with_costs"]
    )
    # costs only ever subtract from the no-cost numbers, never add to them
    assert result["strategy_return_with_costs"] <= result["strategy_return"] + 1e-9
    assert result["buy_and_hold_return_with_costs"] <= result["buy_and_hold_return"] + 1e-9


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
    assert s["tickers_beating_buy_and_hold_with_costs"] == sum(
        1 for r in report["results"] if r["beat_buy_and_hold_with_costs"]
    )
    # Each per-ticker number is already rounded to 4dp, and the mean is rounded
    # again on top of that, so an exact match isn't guaranteed — only agreement
    # within the rounding granularity.
    assert s["mean_strategy_return_with_costs"] == pytest.approx(
        sum(r["strategy_return_with_costs"] for r in report["results"]) / len(report["results"]),
        abs=5e-5,
    )
    assert s["mean_buy_and_hold_return_with_costs"] == pytest.approx(
        sum(r["buy_and_hold_return_with_costs"] for r in report["results"]) / len(report["results"]),
        abs=5e-5,
    )


def test_run_backtest_honors_the_slippage_bps_argument(cfg):
    low = backtest.run_backtest(
        ["RELIANCE.NS"], "fixtures", cfg, generated="2026-09-07", slippage_bps=0.0
    )
    high = backtest.run_backtest(
        ["RELIANCE.NS"], "fixtures", cfg, generated="2026-09-07", slippage_bps=100.0
    )
    assert low["slippage_bps"] == 0.0
    assert high["slippage_bps"] == 100.0
    assert (
        high["results"][0]["strategy_return_with_costs"]
        <= low["results"][0]["strategy_return_with_costs"]
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
    assert "strategy_return_with_costs" in rows.columns
    assert "buy_and_hold_return_with_costs" in rows.columns


def test_write_markdown_reports_beats_and_caveats(cfg, tmp_path):
    report = backtest.run_backtest(["RELIANCE.NS"], "fixtures", cfg, generated="2026-09-07")
    path = tmp_path / "backtest.md"
    backtest.write_markdown(report, [], path)
    text = path.read_text()
    assert "RELIANCE.NS" in text
    assert "Caveats" in text
    assert "not statistically" in text
    assert "No costs (Day 7)" in text
    assert "With costs (Day 8)" in text


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
    assert payload["slippage_bps"] == backtest.DEFAULT_SLIPPAGE_BPS


def test_main_accepts_a_custom_slippage_bps(tmp_path):
    exit_code = backtest.main(
        ["--output-dir", str(tmp_path), "--date", "2026-09-07", "--slippage-bps", "25"]
    )
    assert exit_code == 0
    payload = json.loads((tmp_path / "backtest_2026-09-07.json").read_text())
    assert payload["slippage_bps"] == 25.0


def test_main_rejects_live_and_offline_together(tmp_path):
    with pytest.raises(SystemExit):
        backtest.main(["--live", "--offline", "--output-dir", str(tmp_path)])


def test_main_empty_universe_is_a_clean_failure(tmp_path):
    empty = tmp_path / "universe.txt"
    empty.write_text("# nothing here\n")
    exit_code = backtest.main(["--universe", str(empty), "--output-dir", str(tmp_path)])
    assert exit_code == 1
