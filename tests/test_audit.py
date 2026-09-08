"""Pipeline audit tests.

The point of this audit is to catch look-ahead bias mechanically. That is
only worth anything if the checker actually fires on a function that
peeks at the future, so the negative-control tests below feed it a
deliberately broken indicator alongside the real ones.
"""

import pandas as pd
import pytest

from stockstalker.audit import causality_violations, run_audit
from stockstalker.data.providers import FixtureProvider
from stockstalker.screener import DEFAULT_CONFIG


@pytest.fixture
def reliance():
    return FixtureProvider().fetch("RELIANCE.NS")


def test_real_sma_is_causal(reliance):
    from stockstalker.signals.trend import sma

    violations = causality_violations("sma", lambda df: sma(df["close"], 20), reliance)
    assert violations == []


def test_real_rsi_is_causal(reliance):
    from stockstalker.signals.momentum import rsi

    violations = causality_violations("rsi", lambda df: rsi(df["close"], 14), reliance)
    assert violations == []


def test_real_obv_is_causal(reliance):
    from stockstalker.signals.volume import obv

    violations = causality_violations(
        "obv", lambda df: obv(df["close"], df["volume"]), reliance
    )
    assert violations == []


def test_centered_rolling_mean_is_flagged(reliance):
    """A centred window looks ahead by definition - the audit must catch it."""

    def leaky(df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(window=21, center=True, min_periods=21).mean()

    violations = causality_violations("leaky_centered_sma", leaky, reliance)
    assert violations, "a centred rolling mean uses future bars and must be flagged"


def test_shift_negative_is_flagged(reliance):
    """Shifting a series backwards pulls tomorrow's value into today's row."""

    def leaky(df: pd.DataFrame) -> pd.Series:
        return df["close"].shift(-1)

    violations = causality_violations("leaky_shift", leaky, reliance)
    assert violations, "shift(-1) is future data by construction and must be flagged"


def test_run_audit_clean_on_real_universe(reliance):
    tickers = ["RELIANCE.NS", "TATACHEM.NS", "CROMPTON.NS"]
    report = run_audit(tickers, "fixtures", DEFAULT_CONFIG)
    assert report["tickers_checked"] == 3
    assert report["errors"] == []
    assert report["clean"] is True
    assert report["findings"] == {}


def test_run_audit_reports_missing_ticker():
    report = run_audit(["NOT_A_REAL_TICKER.NS"], "fixtures", DEFAULT_CONFIG)
    assert report["tickers_checked"] == 0
    assert report["errors"]
