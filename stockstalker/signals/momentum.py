"""Momentum signals: RSI and MACD, pure functions over OHLCV frames.

Same shape as :mod:`stockstalker.signals.trend` — plain pandas in, plain
pandas out, no I/O — so these are just as testable against fixtures and
synthetic series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .trend import ema


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing: simple-mean seed, then his recursion.

    ``ewm(alpha=1/period, adjust=False)`` looks equivalent and is not — it
    seeds from the first observation, where Wilder seeds from the mean of the
    first ``period`` values. The two converge (identical by ~250 bars) but
    disagree by up to ~7 RSI points early, which is the difference between
    reading a name as deeply oversold and not oversold at all. That window is
    exactly where a recently listed stock or a short history lands.
    """
    arr = values.to_numpy(dtype=float)
    out = np.full(arr.shape, np.nan)
    if arr.size > period:
        out[period] = arr[1 : period + 1].mean()
        for i in range(period + 1, arr.size):
            out[i] = (out[i - 1] * (period - 1) + arr[i]) / period
    return pd.Series(out, index=values.index)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI. The first ``period`` points are NaN (the seed needs them).

    Matches the RSI charting platforms display, including in the opening
    window — see :func:`_wilder_smooth` for why the obvious EWM one-liner does
    not.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    delta = close.diff()
    avg_gain = _wilder_smooth(delta.clip(lower=0), period)
    avg_loss = _wilder_smooth(-delta.clip(upper=0), period)
    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    # Zero average gain and loss together means a flat window: no direction to
    # report, and the division leaves it NaN rather than the intended neutral.
    # Elsewhere (including all-gain, where rs is +inf) the formula resolves to
    # the right bound on its own.
    result[(avg_gain == 0) & (avg_loss == 0)] = 50.0
    return result


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line, its signal line, and the histogram between them.

    ``macd`` is the fast/slow EMA spread (reusing :func:`stockstalker.signals.trend.ema`
    rather than re-deriving it); ``signal`` is that line's own EMA; ``histogram``
    is the gap the "MACD crossover" trade actually watches.
    """
    if fast >= slow:
        raise ValueError(f"fast span ({fast}) must be < slow span ({slow})")
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})
