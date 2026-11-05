"""P121, P165: the daily snapshot writes only priced rows, fills a day an
earlier run missed, and files rows by their own year.

`scripts/snapshot.py` took yfinance's last row from a 5-day window even
when that bar was NaN, so 11 of 41 sessions per name had no price by
5 Nov 2026; and it wrote `{today's year}.csv` while the backtest read only
`2026.csv`.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stockstalker import backtest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def snapshot(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("snapshot_script", ROOT / "scripts" / "snapshot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "SNAPSHOT_DIR", tmp_path)
    return mod


def _frame(rows):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, *_ in rows], name="Date")
    cols = ["Open", "High", "Low", "Close", "Volume"]
    return pd.DataFrame([r[1:] for r in rows], index=idx, columns=cols)


def test_nan_last_bar_is_skipped_and_earlier_days_are_written(snapshot, monkeypatch):
    frame = _frame([
        ("2026-11-02", 10.0, 11.0, 9.0, 10.5, 100),
        ("2026-11-03", 10.5, 11.5, 10.0, 11.0, 200),
        ("2026-11-04", np.nan, np.nan, np.nan, np.nan, 300),
    ])
    monkeypatch.setattr(snapshot.yf, "download", lambda *a, **k: frame)
    fresh = snapshot.fetch(["AAA.NS"])
    assert list(fresh["date"]) == ["2026-11-02", "2026-11-03"]
    assert fresh["close"].notna().all()


def test_a_later_run_fills_a_day_an_earlier_run_left_empty(snapshot, tmp_path):
    (tmp_path / "2026.csv").write_text(
        "date,ticker,open,high,low,close,volume\n"
        "2026-11-03,AAA.NS,,,,,200\n"
        "2026-11-02,AAA.NS,10.0,11.0,9.0,10.5,100\n"
    )
    fresh = pd.DataFrame([
        {"date": "2026-11-03", "ticker": "AAA.NS", "open": 10.5, "high": 11.5, "low": 10.0, "close": 11.0, "volume": 200},
    ])
    snapshot.write(fresh)
    out = pd.read_csv(tmp_path / "2026.csv")
    assert len(out) == 2
    assert out.set_index("date").loc["2026-11-03", "close"] == 11.0


def test_rows_are_filed_by_their_own_year(snapshot, tmp_path):
    fresh = pd.DataFrame([
        {"date": "2026-12-31", "ticker": "AAA.NS", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        {"date": "2027-01-01", "ticker": "AAA.NS", "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "volume": 2},
    ])
    snapshot.write(fresh)
    assert list(pd.read_csv(tmp_path / "2026.csv")["date"]) == ["2026-12-31"]
    assert list(pd.read_csv(tmp_path / "2027.csv")["date"]) == ["2027-01-01"]


def test_backtest_reads_every_year_file(tmp_path):
    header = "date,ticker,open,high,low,close,volume\n"
    (tmp_path / "2026.csv").write_text(header + "2026-12-31,AAA.NS,1,1,1,1,1\n")
    (tmp_path / "2027.csv").write_text(header + "2027-01-01,AAA.NS,2,2,2,2,2\n")
    bars = backtest.load_snapshot_bars("AAA.NS", tmp_path)
    assert [d.date().isoformat() for d in bars.index] == ["2026-12-31", "2027-01-01"]


def test_default_snapshot_source_is_the_directory():
    assert backtest.SNAPSHOT_PATH == ROOT / "data" / "snapshots"


def test_an_already_priced_row_keeps_its_capture_day_values(snapshot, tmp_path):
    # README: bars are adjusted as of each capture day, so a later dividend
    # does not back-adjust them; refetching a month must not rewrite them.
    (tmp_path / "2026.csv").write_text(
        "date,ticker,open,high,low,close,volume\n2026-11-02,AAA.NS,10.0,11.0,9.0,10.5,100\n"
    )
    fresh = pd.DataFrame([
        {"date": "2026-11-02", "ticker": "AAA.NS", "open": 9.8, "high": 10.8, "low": 8.8, "close": 10.3, "volume": 100},
    ])
    snapshot.write(fresh)
    assert pd.read_csv(tmp_path / "2026.csv").loc[0, "close"] == 10.5
