"""Momentum signal tests: RSI and MACD, checked against known series,
edge cases, and the committed fixtures."""

import numpy as np
import pandas as pd
import pytest

from stockstalker.data.providers import FixtureProvider
from stockstalker.signals import momentum
from stockstalker.signals.momentum import macd, momentum_score, rsi


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


def test_rsi_matches_textbook_wilder_in_the_opening_window():
    """The extremes (100/0/50) pass under any smoothing, so pin the early bars.

    ewm(adjust=False) seeds from the first observation instead of the mean of
    the first `period` deltas. It converges later, so only the opening window
    catches the difference — and that window is where short histories live.
    """
    close = FixtureProvider().fetch("RELIANCE.NS")["close"]
    period = 14

    delta = close.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    avg_g = [float("nan")] * len(close)
    avg_l = list(avg_g)
    avg_g[period] = gain.iloc[1 : period + 1].mean()
    avg_l[period] = loss.iloc[1 : period + 1].mean()
    for i in range(period + 1, len(close)):
        avg_g[i] = (avg_g[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_l[i] = (avg_l[i - 1] * (period - 1) + loss.iloc[i]) / period
    expected = pd.Series(
        [100 - 100 / (1 + (a / b)) if b else (100 if a else 50) for a, b in zip(avg_g, avg_l)],
        index=close.index,
    )

    got = rsi(close, period)
    assert got.first_valid_index() == expected.first_valid_index()
    pd.testing.assert_series_equal(
        got.iloc[period : period + 40], expected.iloc[period : period + 40], atol=1e-9
    )


def test_momentum_score_is_bounded_and_finite(reliance):
    score = momentum_score(reliance["close"])
    assert isinstance(score, float)
    assert -1.0 <= score <= 1.0
    assert np.isfinite(score)


def test_momentum_score_positive_for_a_strictly_rising_series():
    idx = pd.date_range("2026-01-01", periods=60)
    close = pd.Series(np.linspace(100, 200, 60), index=idx)
    assert momentum_score(close) > 0


def test_momentum_score_negative_for_a_strictly_falling_series():
    idx = pd.date_range("2026-01-01", periods=60)
    close = pd.Series(np.linspace(200, 100, 60), index=idx)
    assert momentum_score(close) < 0


def test_momentum_score_zero_for_a_flat_series():
    idx = pd.date_range("2026-01-01", periods=60)
    close = pd.Series([100.0] * 60, index=idx)
    assert momentum_score(close) == 0.0


def test_momentum_score_too_short_for_either_indicator_is_zero():
    idx = pd.date_range("2026-01-01", periods=5)
    close = pd.Series([100.0, 101.0, 99.0, 102.0, 98.0], index=idx)
    assert momentum_score(close) == 0.0


def test_macd_saturation_threshold_is_the_documented_one_percent_of_price():
    """Pins the deliberate, fixed 1%-of-price MACD saturation bound (D19) --
    not an arbitrary round number, and not something that should silently
    drift to a different value without this test catching it."""
    assert momentum.MACD_HISTOGRAM_SATURATION_PCT == 1.0


def test_momentum_score_macd_component_is_not_yet_saturated_just_below_threshold(monkeypatch):
    idx = pd.date_range("2026-01-01", periods=1)
    close = pd.Series([100.0], index=idx)
    # Histogram at 0.99% of price: just under the saturation bound.
    fake_macd = pd.DataFrame({"macd": [0.0], "signal": [0.0], "histogram": [0.99]}, index=idx)
    monkeypatch.setattr(momentum, "macd", lambda *a, **k: fake_macd)
    monkeypatch.setattr(momentum, "rsi", lambda *a, **k: pd.Series([float("nan")], index=idx))

    score = momentum_score(close)
    assert score == pytest.approx(0.5 * 0.99)


def test_momentum_score_macd_component_saturates_at_the_one_percent_threshold(monkeypatch):
    idx = pd.date_range("2026-01-01", periods=1)
    close = pd.Series([100.0], index=idx)
    # Histogram at exactly 1% of price: right at the documented bound.
    fake_macd = pd.DataFrame({"macd": [0.0], "signal": [0.0], "histogram": [1.0]}, index=idx)
    monkeypatch.setattr(momentum, "macd", lambda *a, **k: fake_macd)
    monkeypatch.setattr(momentum, "rsi", lambda *a, **k: pd.Series([float("nan")], index=idx))

    score = momentum_score(close)
    assert score == pytest.approx(0.5 * 1.0)
