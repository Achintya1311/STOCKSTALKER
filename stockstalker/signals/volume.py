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
