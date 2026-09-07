"""Volume signal tests: OBV and rolling volume z-score, checked against
known series, edge cases, and the committed fixtures."""

import numpy as np
import pandas as pd
import pytest

from stockstalker.data.providers import FixtureProvider
from stockstalker.signals.volume import obv, volume_score, volume_zscore


@pytest.fixture
def reliance():
    return FixtureProvider().fetch("RELIANCE.NS")


def test_obv_starts_at_zero_with_no_prior_close(reliance):
    result = obv(reliance["close"], reliance["volume"])
    assert result.iloc[0] == 0.0


def test_obv_length_matches_input(reliance):
    result = obv(reliance["close"], reliance["volume"])
    assert len(result) == len(reliance)


def test_obv_adds_volume_on_up_days_and_subtracts_on_down_days():
    idx = pd.date_range("2026-01-01", periods=4)
    close = pd.Series([10.0, 11.0, 10.0, 10.0], index=idx)  # flat, up, down, flat
    volume = pd.Series([100, 200, 300, 400], index=idx)
    result = obv(close, volume)
    assert list(result) == [0, 200, -100, -100]


def test_volume_zscore_rejects_small_window(reliance):
    with pytest.raises(ValueError, match="window"):
        volume_zscore(reliance["volume"], window=1)


def test_volume_zscore_leading_values_are_nan_then_defined(reliance):
    result = volume_zscore(reliance["volume"], window=20)
    assert result.iloc[:19].isna().all()
    assert result.iloc[19:].notna().all()


def test_volume_zscore_is_zero_for_constant_volume():
    idx = pd.date_range("2026-01-01", periods=30)
    volume = pd.Series([1000] * 30, index=idx)
    result = volume_zscore(volume, window=10)
    assert (result.iloc[9:] == 0.0).all()


def test_volume_zscore_flags_a_spike():
    idx = pd.date_range("2026-01-01", periods=25)
    volume = pd.Series([1000.0] * 24 + [10_000.0], index=idx)
    result = volume_zscore(volume, window=20)
    assert result.iloc[-1] > 3.0


def test_volume_zscore_matches_manual_calculation():
    idx = pd.date_range("2026-01-01", periods=5)
    volume = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=idx)
    result = volume_zscore(volume, window=5)
    mean = volume.mean()
    std = volume.std()
    expected = (volume.iloc[-1] - mean) / std
    assert result.iloc[-1] == pytest.approx(expected)


def test_volume_score_is_bounded_and_finite(reliance):
    score = volume_score(reliance["close"], reliance["volume"])
    assert isinstance(score, float)
    assert -1.0 <= score <= 1.0
    assert np.isfinite(score)


def test_volume_score_positive_when_price_rises_on_uniform_volume():
    idx = pd.date_range("2026-01-01", periods=30)
    close = pd.Series(np.linspace(100, 130, 30), index=idx)
    volume = pd.Series([1000.0] * 30, index=idx)
    assert volume_score(close, volume) > 0


def test_volume_score_negative_when_price_falls_on_uniform_volume():
    idx = pd.date_range("2026-01-01", periods=30)
    close = pd.Series(np.linspace(130, 100, 30), index=idx)
    volume = pd.Series([1000.0] * 30, index=idx)
    assert volume_score(close, volume) < 0


def test_volume_score_positive_for_a_volume_spike_on_flat_price():
    # Flat price means every day's OBV direction is 0, so the OBV component
    # is exactly 0 and only the z-score spike can move the score.
    idx = pd.date_range("2026-01-01", periods=30)
    close = pd.Series([100.0] * 30, index=idx)
    volume = pd.Series([1000.0] * 29 + [5000.0], index=idx)
    assert volume_score(close, volume) > 0


def test_volume_score_zero_for_flat_price_and_flat_volume():
    idx = pd.date_range("2026-01-01", periods=30)
    close = pd.Series([100.0] * 30, index=idx)
    volume = pd.Series([1000.0] * 30, index=idx)
    assert volume_score(close, volume) == 0.0


def test_volume_score_ignores_obv_component_when_window_exceeds_series_length():
    idx = pd.date_range("2026-01-01", periods=10)
    close = pd.Series(np.linspace(100, 110, 10), index=idx)
    volume = pd.Series([1000.0] * 9 + [5000.0], index=idx)
    score = volume_score(close, volume, z_window=5, obv_window=20)
    expected_z = volume_zscore(volume, window=5).iloc[-1]
    expected = 0.5 * float(np.clip(expected_z / 3, -1.0, 1.0))
    assert score == pytest.approx(expected)
