"""Front door Day 7: rebased comparison, drawdown, and rolling volatility
charts, checked against synthetic series, edge cases, and the committed
GULFOILLUB/peer fixtures."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stockstalker.data.providers import FixtureProvider
from stockstalker.viz.charts import (
    drawdown_from_peak,
    plot_drawdown,
    plot_rebased_comparison,
    plot_rolling_volatility,
    rebase_to_100,
    rolling_volatility,
)


@pytest.fixture
def gulfoillub():
    return FixtureProvider().fetch("GULFOILLUB.NS")


@pytest.fixture
def gandhar():
    return FixtureProvider().fetch("GANDHAR.NS")


def test_rebase_to_100_starts_at_100():
    idx = pd.date_range("2026-01-01", periods=4)
    df = pd.DataFrame({"close": [50.0, 55.0, 45.0, 60.0]}, index=idx)
    result = rebase_to_100(df)
    assert result.iloc[0] == pytest.approx(100.0)
    assert result.iloc[-1] == pytest.approx(60.0 / 50.0 * 100)


def test_rebase_to_100_rejects_empty_frame():
    with pytest.raises(ValueError, match="empty"):
        rebase_to_100(pd.DataFrame({"close": []}))


def test_rebase_to_100_on_gulfoillub_fixture_starts_at_100(gulfoillub):
    result = rebase_to_100(gulfoillub)
    assert result.iloc[0] == pytest.approx(100.0)
    assert result.index[0] == gulfoillub.index[0]


def test_rebase_to_100_gandhar_starts_later_than_gulfoillub(gulfoillub, gandhar):
    # GANDHAR's fixture starts years after GULFOILLUB's -- each is rebased
    # to its own first row, not a shared start date.
    subject_rebased = rebase_to_100(gulfoillub)
    peer_rebased = rebase_to_100(gandhar)
    assert peer_rebased.index[0] > subject_rebased.index[0]
    assert peer_rebased.iloc[0] == pytest.approx(100.0)


def test_drawdown_from_peak_is_zero_at_a_new_high():
    idx = pd.date_range("2026-01-01", periods=4)
    df = pd.DataFrame({"close": [100.0, 90.0, 80.0, 110.0]}, index=idx)
    dd = drawdown_from_peak(df)
    assert list(dd) == pytest.approx([0.0, -0.1, -0.2, 0.0])


def test_drawdown_from_peak_never_positive(gulfoillub):
    dd = drawdown_from_peak(gulfoillub)
    assert (dd <= 1e-12).all()


def test_drawdown_from_peak_rejects_empty_frame():
    with pytest.raises(ValueError, match="empty"):
        drawdown_from_peak(pd.DataFrame({"close": []}))


def test_rolling_volatility_drops_rows_before_a_full_window():
    idx = pd.date_range("2026-01-01", periods=10)
    df = pd.DataFrame({"close": np.linspace(100, 110, 10)}, index=idx)
    vol = rolling_volatility(df, window=5)
    # 1 NaN from pct_change, 4 more from the rolling window not yet full.
    assert len(vol) == 10 - 1 - 4


def test_rolling_volatility_rejects_too_small_window():
    idx = pd.date_range("2026-01-01", periods=5)
    df = pd.DataFrame({"close": [1.0] * 5}, index=idx)
    with pytest.raises(ValueError, match="window"):
        rolling_volatility(df, window=1)


def test_rolling_volatility_is_nonnegative_on_gulfoillub_fixture(gulfoillub):
    vol = rolling_volatility(gulfoillub)
    assert len(vol) > 0
    assert (vol >= 0).all()


def test_plot_rebased_comparison_writes_a_png(gulfoillub, gandhar, tmp_path):
    frames = {"GULFOILLUB": gulfoillub, "GANDHAR": gandhar}
    out_path = plot_rebased_comparison(frames, "GULFOILLUB", output_dir=tmp_path)
    assert out_path == tmp_path / "rebased_GULFOILLUB.png"
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_rebased_comparison_requires_subject_in_frames(gandhar, tmp_path):
    with pytest.raises(ValueError, match="GULFOILLUB"):
        plot_rebased_comparison({"GANDHAR": gandhar}, "GULFOILLUB", output_dir=tmp_path)


def test_plot_drawdown_writes_a_png(gulfoillub, tmp_path):
    out_path = plot_drawdown(gulfoillub, "GULFOILLUB", output_dir=tmp_path)
    assert out_path == tmp_path / "drawdown_GULFOILLUB.png"
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_rolling_volatility_writes_a_png(gulfoillub, tmp_path):
    out_path = plot_rolling_volatility(gulfoillub, "GULFOILLUB", output_dir=tmp_path)
    assert out_path == tmp_path / "volatility_GULFOILLUB.png"
    assert out_path.exists()
    assert out_path.stat().st_size > 0
