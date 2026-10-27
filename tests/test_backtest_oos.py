"""R29: the frozen rule scored on the snapshot days it was not chosen on."""

import pandas as pd
import pytest

from stockstalker import backtest, screener
from stockstalker.data.providers import FixtureProvider


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


def _write_snapshot(path, rows):
    pd.DataFrame(rows, columns=["date", "ticker", "open", "high", "low", "close", "volume"]).to_csv(
        path, index=False
    )


def test_load_snapshot_bars_keeps_one_ticker_sorted_and_deduplicated(tmp_path):
    p = tmp_path / "snap.csv"
    _write_snapshot(p, [
        ("2026-09-08", "AAA.NS", 1, 2, 1, 2, 10),
        ("2026-09-07", "AAA.NS", 1, 2, 1, 1.5, 10),
        ("2026-09-07", "BBB.NS", 5, 5, 5, 5, 10),
        ("2026-09-08", "AAA.NS", 1, 2, 1, 2.5, 10),  # rerun of the same day: last row wins
    ])
    bars = backtest.load_snapshot_bars("AAA.NS", p)
    assert list(bars.index.strftime("%Y-%m-%d")) == ["2026-09-07", "2026-09-08"]
    assert bars["close"].tolist() == [1.5, 2.5]
    assert list(bars.columns) == ["open", "high", "low", "close", "volume"]
    assert bars.attrs["dropped_nan_rows"] == 0


def test_load_snapshot_bars_drops_rows_with_no_price(tmp_path):
    p = tmp_path / "snap.csv"
    _write_snapshot(p, [
        ("2026-09-07", "AAA.NS", 1, 2, 1, 1.5, 10),
        ("2026-09-08", "AAA.NS", None, None, None, None, 10),
        ("2026-09-09", "AAA.NS", 1, 2, 1, 2.0, 10),
    ])
    bars = backtest.load_snapshot_bars("AAA.NS", p)
    assert bars["close"].tolist() == [1.5, 2.0]
    assert bars.attrs["dropped_nan_rows"] == 1


def test_extend_with_snapshots_appends_only_newer_bars():
    idx = pd.to_datetime(["2026-09-03", "2026-09-04"])
    df = pd.DataFrame({"open": [1, 1], "high": [1, 1], "low": [1, 1], "close": [1.0, 2.0], "volume": [1, 1]}, index=idx)
    snap = pd.DataFrame(
        {"open": [9, 3], "high": [9, 3], "low": [9, 3], "close": [9.0, 3.0], "volume": [1, 1]},
        index=pd.to_datetime(["2026-09-04", "2026-09-07"]),
    )
    out = backtest.extend_with_snapshots(df, snap)
    assert out["close"].tolist() == [1.0, 2.0, 3.0]  # the overlapping 4 Sep bar keeps the fixture


def test_out_of_sample_window_starts_after_the_freeze(cfg):
    snap = backtest.load_snapshot_bars("RELIANCE.NS")
    expected_days = int((snap.index > pd.Timestamp(backtest.RULE_FROZEN_ON)).sum())
    assert snap["close"].notna().all()
    assert expected_days > 0
    r = backtest.out_of_sample_ticker("RELIANCE.NS", "fixtures", cfg)
    assert r["start"] > backtest.RULE_FROZEN_ON
    assert r["days_tested"] == expected_days
    assert 0 <= r["days_long"] <= r["days_tested"]
    assert 0.0 <= r["exposure_matched_percentile"] <= 1.0
    # buy-and-hold over exactly the scored days
    full = backtest.extend_with_snapshots(FixtureProvider().fetch("RELIANCE.NS"), snap)
    after = full[full.index > pd.Timestamp(backtest.RULE_FROZEN_ON)]
    before = full[full.index <= pd.Timestamp(backtest.RULE_FROZEN_ON)]
    hold = after["close"].iloc[-1] / before["close"].iloc[-1] - 1
    assert r["buy_and_hold_return"] == pytest.approx(round(hold, 4))


def test_out_of_sample_strategy_matches_the_in_sample_rule(cfg):
    """Same scores, same long/flat rule: the OOS return is the full-run return sliced."""
    full = backtest.extend_with_snapshots(
        FixtureProvider().fetch("RELIANCE.NS"), backtest.load_snapshot_bars("RELIANCE.NS")
    )
    scores = backtest.walk_forward_scores(full, cfg)
    rets = backtest.long_flat_returns(full, scores, backtest.DEFAULT_THRESHOLD)
    oos = rets[rets.index > pd.Timestamp(backtest.RULE_FROZEN_ON)]
    r = backtest.out_of_sample_ticker("RELIANCE.NS", "fixtures", cfg)
    assert r["strategy_return"] == pytest.approx(round(backtest.cumulative_return(oos), 4))


def test_cli_out_of_sample_flag_prints_and_writes_the_segment(tmp_path, capsys):
    rc = backtest.main(["--offline", "--out-of-sample", "--output-dir", str(tmp_path), "--date", "2026-10-27"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Out of sample" in out
    import json
    report = json.loads((tmp_path / "backtest_2026-10-27.json").read_text())
    assert report["out_of_sample"]["rule_frozen_on"] == backtest.RULE_FROZEN_ON
    assert len(report["out_of_sample"]["results"]) == 3


def test_cli_without_the_flag_has_no_segment(tmp_path):
    backtest.main(["--offline", "--output-dir", str(tmp_path), "--date", "2026-10-27"])
    import json
    report = json.loads((tmp_path / "backtest_2026-10-27.json").read_text())
    assert "out_of_sample" not in report


def test_never_long_has_no_percentile(cfg):
    r = backtest.out_of_sample_ticker("RELIANCE.NS", "fixtures", cfg, threshold=1.01)
    assert r["days_long"] == 0
    assert r["strategy_return"] == 0.0
    assert r["exposure_matched_percentile"] is None
