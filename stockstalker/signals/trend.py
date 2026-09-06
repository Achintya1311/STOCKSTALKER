"""Trend signals: SMA/EMA crossovers, pure functions over OHLCV frames.

Everything here takes a ``close`` series or a frame with a ``close`` column
and returns plain pandas objects. No I/O, no provider calls — that keeps this
module trivially testable against fixtures and synthetic series alike.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average. The first ``window - 1`` points are NaN."""
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    return close.rolling(window=window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    """Exponential moving average, pandas-seeded (no fixed lookback needed)."""
    if span < 1:
        raise ValueError(f"span must be >= 1, got {span}")
    return close.ewm(span=span, adjust=False, min_periods=span).mean()


def crossover_state(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """+1 where fast sits above slow, -1 where below, 0 when equal or undefined."""
    state = pd.Series(0, index=fast.index, dtype=int)
    both_defined = fast.notna() & slow.notna()
    state[both_defined & (fast > slow)] = 1
    state[both_defined & (fast < slow)] = -1
    return state


def crossover_events(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """+1 the bar fast first closes above slow, -1 the bar it first closes below.

    Works off the raw fast/slow values rather than :func:`crossover_state`, so
    a bar where the two are exactly equal does not swallow the cross that
    follows it: a move from "at or below" to "above" still fires golden, and
    "at or above" to "below" still fires death. Needs both series defined on
    this bar and the previous one; the first live bar never fires.
    """
    diff = fast - slow
    prev_diff = diff.shift(1)
    defined = diff.notna() & prev_diff.notna()
    events = pd.Series(0, index=fast.index, dtype=int)
    events[defined & (prev_diff <= 0) & (diff > 0)] = 1
    events[defined & (prev_diff >= 0) & (diff < 0)] = -1
    return events


def sma_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.DataFrame:
    """SMA fast/slow crossover state and events over an OHLCV frame."""
    if fast >= slow:
        raise ValueError(f"fast window ({fast}) must be < slow window ({slow})")
    fast_ma = sma(df["close"], fast)
    slow_ma = sma(df["close"], slow)
    return pd.DataFrame(
        {
            "fast": fast_ma,
            "slow": slow_ma,
            "state": crossover_state(fast_ma, slow_ma),
            "event": crossover_events(fast_ma, slow_ma),
        }
    )


def ema_crossover(df: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.DataFrame:
    """EMA fast/slow crossover state and events over an OHLCV frame."""
    if fast >= slow:
        raise ValueError(f"fast span ({fast}) must be < slow span ({slow})")
    fast_ma = ema(df["close"], fast)
    slow_ma = ema(df["close"], slow)
    return pd.DataFrame(
        {
            "fast": fast_ma,
            "slow": slow_ma,
            "state": crossover_state(fast_ma, slow_ma),
            "event": crossover_events(fast_ma, slow_ma),
        }
    )


def trend_score(df: pd.DataFrame, fast: int = 20, slow: int = 50, method: str = "sma") -> float:
    """A single trend score in [-1, 1] from the latest fast/slow separation.

    Positive means the fast average sits above the slow one, scaled by how far
    apart they are relative to the slow average and clipped at +-1. This is a
    snapshot of the most recent bar, not a backtest signal — it is what will
    feed the ``signals.trend`` field of the v1 screen contract once
    ``screener.py`` exists (Day 6).
    """
    if method not in ("sma", "ema"):
        raise ValueError(f"method must be 'sma' or 'ema', got {method!r}")
    table = sma_crossover(df, fast, slow) if method == "sma" else ema_crossover(df, fast, slow)
    latest = table.iloc[-1]
    if pd.isna(latest["fast"]) or pd.isna(latest["slow"]) or latest["slow"] == 0:
        return 0.0
    spread = (latest["fast"] - latest["slow"]) / abs(latest["slow"])
    return float(np.clip(spread * 10, -1.0, 1.0))
