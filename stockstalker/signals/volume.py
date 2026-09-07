"""Volume signals: OBV and a rolling volume z-score, pure functions over OHLCV frames.

Same shape as the other signal modules — plain pandas in, plain pandas out,
no I/O.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-balance volume: cumulative volume, signed by the day's price direction.

    Granville's original definition: up days add the day's volume, down days
    subtract it, flat days add nothing. The first bar has no prior close to
    compare against, so it contributes 0 and the series starts there rather
    than at that day's raw volume.
    """
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series:
    """How many rolling standard deviations today's volume sits from its recent mean.

    Flags liquidity spikes and droughts rather than raw volume level, which
    is not comparable across tickers. A window with zero variance (volume
    perfectly flat) scores 0 rather than dividing by zero.
    """
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    rolling_mean = volume.rolling(window=window, min_periods=window).mean()
    rolling_std = volume.rolling(window=window, min_periods=window).std()
    z = (volume - rolling_mean) / rolling_std
    z[rolling_std == 0] = 0.0
    return z


def volume_score(close: pd.Series, volume: pd.Series, z_window: int = 20, obv_window: int = 20) -> float:
    """A single volume score in [-1, 1] from the latest volume z-score and OBV trend.

    Two components, averaged: today's volume z-score (a spike or drought,
    divided by 3 so a +-3 sigma move saturates the range), and OBV's net
    change over ``obv_window`` bars divided by the volume traded over that
    same window. The second component is bounded in [-1, 1] on its own —
    each day's OBV contribution is at most that day's volume — so the clip
    only guards the edge case where ``obv_window`` exceeds the series
    length. This is a snapshot of the most recent bar, not a backtest
    signal — it feeds the ``signals.volume`` field of the v1 screen
    contract.
    """
    latest_z = volume_zscore(volume, z_window).iloc[-1]
    z_component = 0.0 if pd.isna(latest_z) else float(np.clip(latest_z / 3, -1.0, 1.0))

    obv_series = obv(close, volume)
    if len(obv_series) > obv_window:
        change = obv_series.iloc[-1] - obv_series.iloc[-obv_window - 1]
        traded = volume.iloc[-obv_window:].sum()
        obv_component = 0.0 if traded == 0 else float(np.clip(change / traded, -1.0, 1.0))
    else:
        obv_component = 0.0

    return float(np.clip(0.5 * z_component + 0.5 * obv_component, -1.0, 1.0))
