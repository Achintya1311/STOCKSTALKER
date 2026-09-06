"""Liquidity heatmap tests: volume-at-price binning, zone detection, and the
plot itself, checked against synthetic series, edge cases, and the committed
fixtures."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stockstalker.data.providers import FixtureProvider
from stockstalker.viz.liquidity import (
    high_activity_zones,
    plot_liquidity_heatmap,
    volume_at_price,
)


@pytest.fixture
def reliance():
    return FixtureProvider().fetch("RELIANCE.NS")


def test_volume_at_price_rejects_non_positive_bins(reliance):
    with pytest.raises(ValueError, match="bins"):
        volume_at_price(reliance, bins=0)


def test_volume_at_price_rejects_empty_frame():
    empty = pd.DataFrame({"close": [], "volume": []})
    with pytest.raises(ValueError, match="empty"):
        volume_at_price(empty)


def test_volume_at_price_has_one_row_per_bin(reliance):
    result = volume_at_price(reliance, bins=24)
    assert len(result) == 24


def test_volume_at_price_conserves_total_volume(reliance):
    result = volume_at_price(reliance, bins=24)
    assert result["volume"].sum() == pytest.approx(reliance["volume"].sum())


def test_volume_at_price_bins_span_the_close_range(reliance):
    result = volume_at_price(reliance, bins=24)
    assert result["bin_low"].iloc[0] == pytest.approx(reliance["close"].min())
    assert result["bin_high"].iloc[-1] == pytest.approx(reliance["close"].max())


def test_volume_at_price_flat_price_series_is_one_degenerate_bin():
    idx = pd.date_range("2026-01-01", periods=5)
    df = pd.DataFrame({"close": [100.0] * 5, "volume": [10, 20, 30, 40, 50]}, index=idx)
    result = volume_at_price(df, bins=24)
    assert len(result) == 1
    assert result["volume"].iloc[0] == 150


def test_volume_at_price_puts_each_days_volume_in_its_own_bin():
    idx = pd.date_range("2026-01-01", periods=4)
    close = pd.Series([100.0, 101.0, 102.0, 103.0], index=idx)
    volume = pd.Series([10.0, 20.0, 30.0, 40.0], index=idx)
    df = pd.DataFrame({"close": close, "volume": volume})
    result = volume_at_price(df, bins=3)
    # edges at 100, 101, 102, 103 -> bin0 gets days 100&101 (include_lowest),
    # bin1 gets day 102, bin2 gets day 103.
    assert list(result["volume"]) == [30.0, 30.0, 40.0]


def test_volume_at_price_monotonic_series_bins_are_ascending_in_price():
    idx = pd.date_range("2026-01-01", periods=50)
    close = pd.Series(np.linspace(100, 200, 50), index=idx)
    volume = pd.Series([1000.0] * 50, index=idx)
    df = pd.DataFrame({"close": close, "volume": volume})
    result = volume_at_price(df, bins=10)
    assert (result["bin_low"].diff().dropna() > 0).all()


def test_high_activity_zones_rejects_non_positive_threshold():
    vap = pd.DataFrame({"bin_low": [1.0], "bin_high": [2.0], "volume": [10.0]})
    with pytest.raises(ValueError, match="threshold"):
        high_activity_zones(vap, threshold=0)


def test_high_activity_zones_empty_when_no_volume():
    vap = pd.DataFrame({"bin_low": [1.0, 2.0], "bin_high": [2.0, 3.0], "volume": [0.0, 0.0]})
    assert high_activity_zones(vap).empty


def test_high_activity_zones_flags_a_spike_bin():
    vap = pd.DataFrame(
        {
            "bin_low": [1.0, 2.0, 3.0, 4.0],
            "bin_high": [2.0, 3.0, 4.0, 5.0],
            "volume": [100.0, 100.0, 100.0, 1_000.0],
        }
    )
    zones = high_activity_zones(vap, threshold=1.5)
    assert list(zones["bin_low"]) == [4.0]


def test_high_activity_zones_flags_nothing_when_volume_is_uniform():
    vap = pd.DataFrame(
        {"bin_low": [1.0, 2.0, 3.0], "bin_high": [2.0, 3.0, 4.0], "volume": [100.0, 100.0, 100.0]}
    )
    # every bin sits exactly at the mean, so a >1.0 threshold flags none.
    assert high_activity_zones(vap, threshold=1.01).empty


def test_plot_liquidity_heatmap_writes_a_png(reliance, tmp_path):
    out_path = plot_liquidity_heatmap(reliance, "RELIANCE.NS", output_dir=tmp_path)
    assert out_path == tmp_path / "heatmap_RELIANCE_NS.png"
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_liquidity_heatmap_runs_with_no_high_activity_zones(tmp_path):
    idx = pd.date_range("2026-01-01", periods=30)
    df = pd.DataFrame({"close": np.linspace(50, 60, 30), "volume": [1000.0] * 30}, index=idx)
    out_path = plot_liquidity_heatmap(df, "FLAT.NS", output_dir=tmp_path)
    assert out_path.exists()
