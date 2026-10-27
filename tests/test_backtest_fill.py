"""R30: next-open fills reported beside the signal-close default."""

import json

import numpy as np
import pandas as pd
import pytest

from stockstalker import backtest


def _df(close, open_):
    idx = pd.date_range("2026-01-01", periods=len(close), freq="B")
    return pd.DataFrame({"open": open_, "high": close, "low": close, "close": close, "volume": 1}, index=idx)


def test_next_open_prices_entry_and_exit_at_the_open():
    df = _df([100.0, 110.0, 100.0], [100.0, 105.0, 108.0])
    scores = pd.Series([0.6, 0.4, 0.4], index=df.index)
    close_fill = backtest.long_flat_returns(df, scores, 0.5)
    open_fill = backtest.long_flat_returns(df, scores, 0.5, fill="next-open")
    assert close_fill.tolist() == pytest.approx([0.0, 0.10, 0.0])
    # bought at day 1's open, sold at day 2's open
    assert open_fill.tolist() == pytest.approx([0.0, 110 / 105 - 1, 108 / 110 - 1])
    assert backtest.cumulative_return(open_fill) == pytest.approx(108 / 105 - 1)


def test_continuing_days_are_close_to_close_under_both_fills():
    df = _df([100.0, 110.0, 121.0, 121.0], [100.0, 104.0, 115.0, 120.0])
    scores = pd.Series([0.6, 0.6, 0.4, 0.4], index=df.index)
    open_fill = backtest.long_flat_returns(df, scores, 0.5, fill="next-open")
    assert open_fill.iloc[2] == pytest.approx(121 / 110 - 1)
    assert backtest.cumulative_return(open_fill) == pytest.approx(120 / 104 - 1)


def test_unknown_fill_is_rejected():
    df = _df([1.0, 1.0], [1.0, 1.0])
    with pytest.raises(ValueError):
        backtest.long_flat_returns(df, pd.Series([0.6, 0.6], index=df.index), 0.5, fill="vwap")


def test_random_exposure_with_every_day_held_matches_one_open_to_close_hold():
    df = _df([100.0, 110.0, 120.0, 130.0], [100.0, 104.0, 118.0, 131.0])
    draws = backtest.random_exposure_returns(df, start_idx=1, days_long=3, n_draws=5, seed=1, fill="next-open")
    assert np.allclose(draws, 130 / 104 - 1)
    close_draws = backtest.random_exposure_returns(df, start_idx=1, days_long=3, n_draws=5, seed=1)
    assert np.allclose(close_draws, 130 / 100 - 1)


def test_default_report_is_signal_close_and_cli_reports_next_open(tmp_path, capsys):
    backtest.main(["--offline", "--output-dir", str(tmp_path), "--date", "2026-10-27"])
    default = json.loads((tmp_path / "backtest_2026-10-27.json").read_text())
    assert default["fill"] == "signal-close"
    capsys.readouterr()
    backtest.main(["--offline", "--fill", "next-open", "--output-dir", str(tmp_path), "--date", "2026-10-28"])
    out = capsys.readouterr().out
    assert "fill next-open" in out
    opened = json.loads((tmp_path / "backtest_2026-10-28.json").read_text())
    assert opened["fill"] == "next-open"
    assert [r["strategy_return"] for r in opened["results"]] != [r["strategy_return"] for r in default["results"]]
