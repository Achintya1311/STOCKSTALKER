"""Momentum signal tests: RSI and MACD, checked against known series,
edge cases, and the committed fixtures."""

import numpy as np
import pandas as pd
import pytest

from stockstalker.data.providers import FixtureProvider
from stockstalker.signals.momentum import macd, rsi


@pytest.fixture
def reliance():
    return FixtureProvider().fetch("RELIANCE.NS")


def test_rsi_rejects_non_positive_period(reliance):
    with pytest.raises(ValueError, match="period"):
        rsi(reliance["close"], 0)


def test_rsi_leading_values_are_nan_then_bounded(reliance):
    result = rsi(reliance["close"], 14)
    assert result.iloc[:14].isna().all()
    live = result.iloc[14:]
    assert live.notna().all()
    assert (live >= 0).all() and (live <= 100).all()


def test_rsi_is_100_for_a_strictly_rising_series():
    idx = pd.date_range("2026-01-01", periods=20)
    close = pd.Series(np.arange(20, dtype=float) + 100, index=idx)
    result = rsi(close, period=14)
    assert (result.iloc[14:] == 100.0).all()


def test_rsi_is_0_for_a_strictly_falling_series():
    idx = pd.date_range("2026-01-01", periods=20)
    close = pd.Series(100 - np.arange(20, dtype=float), index=idx)
    result = rsi(close, period=14)
    assert (result.iloc[14:] == 0.0).all()


def test_rsi_is_50_for_a_flat_series():
    idx = pd.date_range("2026-01-01", periods=20)
    close = pd.Series([100.0] * 20, index=idx)
    result = rsi(close, period=14)
    assert (result.iloc[14:] == 50.0).all()


def test_macd_rejects_fast_not_less_than_slow(reliance):
    with pytest.raises(ValueError, match="fast"):
        macd(reliance["close"], fast=26, slow=12)


def test_macd_shape_and_columns(reliance):
    table = macd(reliance["close"], fast=12, slow=26, signal=9)
    assert list(table.columns) == ["macd", "signal", "histogram"]
    assert len(table) == len(reliance)


def test_macd_histogram_equals_macd_minus_signal(reliance):
    table = macd(reliance["close"])
    live = table.dropna()
    pd.testing.assert_series_equal(
        live["histogram"], live["macd"] - live["signal"], check_names=False
    )


def test_macd_line_matches_ema_difference(reliance):
    table = macd(reliance["close"], fast=12, slow=26, signal=9)
    fast_ema = reliance["close"].ewm(span=12, adjust=False, min_periods=12).mean()
    slow_ema = reliance["close"].ewm(span=26, adjust=False, min_periods=26).mean()
    pd.testing.assert_series_equal(table["macd"], fast_ema - slow_ema, check_names=False)


def test_macd_is_zero_for_a_flat_series():
    idx = pd.date_range("2026-01-01", periods=60)
    close = pd.Series([100.0] * 60, index=idx)
    table = macd(close, fast=12, slow=26, signal=9)
    live = table.dropna()
    assert not live.empty
    assert (live["macd"] == 0.0).all()
    assert (live["histogram"] == 0.0).all()
