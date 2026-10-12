"""Front door Day 7: subject-vs-peer and subject-risk charts, PNG only.

Three charts, written to ``outputs/``:

- :func:`plot_rebased_comparison` -- the subject and each peer, each series
  divided by its own first close and multiplied by 100. GANDHAR's fixture
  starts 2023-11-30 (its IPO), about nine years after the other three, so
  this is not one shared start date -- each line is rebased to 100 at the
  first date *that series* has data, and the legend names that date so a
  shorter peer line never reads as if it shared the subject's window.
- :func:`plot_drawdown` -- the subject only: percent below its own running
  all-time high, close-to-close. Peers are left out here and in the
  volatility chart; NEXT_STEPS.md's "subject vs peers" qualifier is only on
  the rebased comparison, and four peers' worth of drawdown/volatility
  lines on one axis would read as the screen's peer table turned into a
  chart no one asked for, not a risk profile of the name the note is about.
- :func:`plot_rolling_volatility` -- the subject only: rolling 1y
  annualised stdev of daily returns, the same measure
  ``run.trailing_volatility`` reports as a single point, plotted as a
  series instead.

The series math (:func:`rebase_to_100`, :func:`drawdown_from_peak`,
:func:`rolling_volatility`) is pure pandas, tested without matplotlib. Only
the three ``plot_*`` functions touch the filesystem or a plotting backend.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "outputs"

TRADING_DAYS_PER_YEAR = 252


def rebase_to_100(df: pd.DataFrame) -> pd.Series:
    """``close`` divided by its own first value, times 100.

    The series' own first row is its "first common date" with the subject
    whenever its fixture starts later than the subject's (GANDHAR); when a
    peer's fixture spans the subject's full history (CASTROLIND, SOTL) the
    two coincide, so this one rule covers both cases without special-casing
    either.
    """
    if df.empty:
        raise ValueError("cannot rebase an empty frame")
    first = float(df["close"].iloc[0])
    return (df["close"] / first * 100).rename("rebased")


def drawdown_from_peak(df: pd.DataFrame) -> pd.Series:
    """Percent below the running all-time high, close-to-close.

    Zero at a new high, negative everywhere else; never positive.
    """
    if df.empty:
        raise ValueError("cannot compute drawdown for an empty frame")
    close = df["close"]
    return (close / close.cummax() - 1).rename("drawdown")


def rolling_volatility(df: pd.DataFrame, window: int = TRADING_DAYS_PER_YEAR) -> pd.Series:
    """Rolling annualised stdev of daily returns over ``window`` trading days.

    The first ``window`` rows have no full window behind them and are
    dropped, rather than returned as a misleadingly early NaN-free series.
    """
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    daily_returns = df["close"].pct_change()
    vol = daily_returns.rolling(window).std(ddof=1) * (TRADING_DAYS_PER_YEAR**0.5)
    return vol.dropna().rename("volatility_1y")


def _safe_name(ticker: str) -> str:
    return ticker.replace(".", "_")


def plot_rebased_comparison(
    frames: dict[str, pd.DataFrame],
    subject_ticker: str,
    output_dir: Path | None = None,
) -> Path:
    """Subject and peers rebased to 100, each from its own first close.

    ``frames`` maps ticker -> OHLCV frame and must contain ``subject_ticker``;
    the subject is drawn in black and heavier, peers in a muted palette, so
    the line a reader should anchor on is unambiguous at a glance.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if subject_ticker not in frames:
        raise ValueError(f"{subject_ticker} missing from frames")

    out_dir = output_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rebased_{_safe_name(subject_ticker)}.png"

    peer_colors = ["#1f77b4", "#2ca02c", "#9467bd", "#8c564b", "#17becf"]
    fig, ax = plt.subplots(figsize=(9, 5.5))

    peer_idx = 0
    for ticker, df in frames.items():
        series = rebase_to_100(df)
        start = series.index[0].date().isoformat()
        label = f"{ticker} (from {start})"
        if ticker == subject_ticker:
            ax.plot(series.index, series.to_numpy(), color="black", linewidth=2.2, label=label, zorder=3)
        else:
            color = peer_colors[peer_idx % len(peer_colors)]
            peer_idx += 1
            ax.plot(series.index, series.to_numpy(), color=color, linewidth=1.3, label=label, zorder=2)

    ax.axhline(100, color="#999999", linewidth=0.8, linestyle="--", zorder=1)
    ax.set_xlabel("Date")
    ax.set_ylabel("Rebased close (100 = each series' own first day)")
    ax.set_title(f"{subject_ticker} vs peers, rebased to 100")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_drawdown(df: pd.DataFrame, ticker: str, output_dir: Path | None = None) -> Path:
    """Drawdown-from-peak for one ticker, filled area below zero."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = output_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"drawdown_{_safe_name(ticker)}.png"

    dd = drawdown_from_peak(df)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.fill_between(dd.index, dd.to_numpy() * 100, 0, color="#d62728", alpha=0.35, linewidth=0)
    ax.plot(dd.index, dd.to_numpy() * 100, color="#d62728", linewidth=1.0)
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown from peak (%)")
    ax.set_title(f"{ticker} — drawdown from peak")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_rolling_volatility(
    df: pd.DataFrame,
    ticker: str,
    window: int = TRADING_DAYS_PER_YEAR,
    output_dir: Path | None = None,
) -> Path:
    """Rolling annualised volatility for one ticker."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = output_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"volatility_{_safe_name(ticker)}.png"

    vol = rolling_volatility(df, window=window)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(vol.index, vol.to_numpy() * 100, color="#1f77b4", linewidth=1.2)
    ax.set_xlabel("Date")
    ax.set_ylabel(f"Rolling {window}d annualised volatility (%)")
    ax.set_title(f"{ticker} — rolling 1y volatility")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
