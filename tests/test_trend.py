"""Trend signal tests. Pure functions, checked against pandas primitives,
synthetic series with known crossovers, and the committed fixtures."""

import numpy as np
import pandas as pd
import pytest

from stockstalker.data.providers import FixtureProvider
from stockstalker.signals.trend import (
    crossover_events,
    crossover_state,
    ema,
    ema_crossover,
    sma,
    sma_crossover,
    trend_score,
)


@pytest.fixture
def reliance():
    return FixtureProvider().fetch("RELIANCE.NS")


def test_sma_matches_pandas_rolling_mean(reliance):
    result = sma(reliance["close"], 20)
    expected = reliance["close"].rolling(20).mean()
    pd.testing.assert_series_equal(result, expected, check_names=False)


def test_sma_window_one_equals_close(reliance):
    result = sma(reliance["close"], 1)
    pd.testing.assert_series_equal(result, reliance["close"], check_names=False)


def test_sma_rejects_non_positive_window(reliance):
    with pytest.raises(ValueError, match="window"):
        sma(reliance["close"], 0)


def test_sma_leading_values_are_nan_then_defined(reliance):
    result = sma(reliance["close"], 20)
    assert result.iloc[:19].isna().all()
    assert result.iloc[19:].notna().all()


def test_ema_matches_pandas_ewm(reliance):
    result = ema(reliance["close"], 12)
    expected = reliance["close"].ewm(span=12, adjust=False, min_periods=12).mean()
    pd.testing.assert_series_equal(result, expected, check_names=False)


def test_ema_rejects_non_positive_span(reliance):
    with pytest.raises(ValueError, match="span"):
        ema(reliance["close"], 0)


def test_crossover_state_signs_and_undefined_rows():
    idx = pd.date_range("2026-01-01", periods=5)
    fast = pd.Series([np.nan, 2.0, 3.0, 1.0, 2.0], index=idx)
    slow = pd.Series([np.nan, 1.0, 2.5, 2.0, 2.0], index=idx)
    state = crossover_state(fast, slow)
    assert list(state) == [0, 1, 1, -1, 0]


def test_crossover_events_fire_only_on_the_flip_bar():
    idx = pd.date_range("2026-01-01", periods=6)
    fast = pd.Series([0, 0, 0, 2, 2, 0], index=idx, dtype=float)
    slow = pd.Series([1, 1, 1, 1, 1, 1], index=idx, dtype=float)
    events = crossover_events(fast, slow)
    assert list(events) == [0, 0, 0, 1, 0, -1]


def test_crossover_events_needs_two_defined_bars():
    idx = pd.date_range("2026-01-01", periods=3)
    fast = pd.Series([np.nan, 5.0, 5.0], index=idx)
    slow = pd.Series([np.nan, 1.0, 1.0], index=idx)
    events = crossover_events(fast, slow)
    assert list(events) == [0, 0, 0]


def test_sma_crossover_rejects_fast_not_less_than_slow(reliance):
    with pytest.raises(ValueError, match="fast"):
        sma_crossover(reliance, fast=50, slow=20)


def test_ema_crossover_rejects_fast_not_less_than_slow(reliance):
    with pytest.raises(ValueError, match="fast"):
        ema_crossover(reliance, fast=26, slow=12)


def test_sma_crossover_detects_a_known_golden_cross():
    idx = pd.date_range("2026-01-01", periods=10)
    # Flat at 10, then a jump to 30: the 2-day average catches the jump
    # faster than the 5-day one, so fast crosses above slow.
    close = pd.Series([10.0] * 5 + [30.0] * 5, index=idx)
    df = pd.DataFrame({"close": close})
    table = sma_crossover(df, fast=2, slow=5)
    golden_days = table.index[table["event"] == 1]
    assert list(golden_days) == [idx[5]]
    assert (table["event"] == -1).sum() == 0


def test_sma_crossover_detects_a_known_death_cross():
    idx = pd.date_range("2026-01-01", periods=10)
    close = pd.Series([30.0] * 5 + [10.0] * 5, index=idx)
    df = pd.DataFrame({"close": close})
    table = sma_crossover(df, fast=2, slow=5)
    death_days = table.index[table["event"] == -1]
    assert list(death_days) == [idx[5]]


def test_trend_score_is_bounded_and_finite(reliance):
    score = trend_score(reliance, fast=20, slow=50, method="sma")
    assert isinstance(score, float)
    assert -1.0 <= score <= 1.0
    assert np.isfinite(score)


def test_trend_score_ema_also_bounded(reliance):
    score = trend_score(reliance, fast=12, slow=26, method="ema")
    assert -1.0 <= score <= 1.0


def test_trend_score_rejects_unknown_method(reliance):
    with pytest.raises(ValueError, match="method"):
        trend_score(reliance, method="rsi")


def test_trend_score_positive_when_price_ramping_up():
    idx = pd.date_range("2026-01-01", periods=60)
    close = pd.Series(np.linspace(100, 200, 60), index=idx)
    df = pd.DataFrame({"close": close})
    assert trend_score(df, fast=5, slow=20, method="sma") > 0


def test_trend_score_negative_when_price_ramping_down():
    idx = pd.date_range("2026-01-01", periods=60)
    close = pd.Series(np.linspace(200, 100, 60), index=idx)
    df = pd.DataFrame({"close": close})
    assert trend_score(df, fast=5, slow=20, method="sma") < 0


def test_trend_score_flat_price_is_zero():
    idx = pd.date_range("2026-01-01", periods=60)
    close = pd.Series([100.0] * 60, index=idx)
    df = pd.DataFrame({"close": close})
    assert trend_score(df, fast=5, slow=20, method="sma") == 0.0
