"""Momentum signals: RSI and MACD, pure functions over OHLCV frames.

Same shape as :mod:`stockstalker.signals.trend` — plain pandas in, plain
pandas out, no I/O — so these are just as testable against fixtures and
synthetic series.
"""

from __future__ import annotations

import pandas as pd

from .trend import ema


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI. The first ``period`` points are NaN (Wilder smoothing needs a seed).

    Uses Wilder's own smoothing (an EWM with ``alpha=1/period``), not a plain
    rolling mean of gains/losses — that distinction is what most charting
    platforms actually mean by "RSI" and a naive rolling-mean version does
    not match them.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    # Zero average gain and loss together means a flat window: no direction
    # to report, and the division above leaves it NaN rather than 0/0's
    # intended "neutral". Everywhere else (including all-gain, where rs is
    # +inf) the formula already resolves to the right bound on its own.
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
