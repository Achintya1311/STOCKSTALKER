"""The screen's own test as a chart (P138): random same-size exposure draws.

For each screened name, a histogram of the cumulative returns of being long
the same number of tested days as the screen, picked at random (the draws
``backtest.random_exposure_returns`` makes), with the screen's own return
and its percentile marked. Both are before costs, as the percentile in the
backtest report is. Written by ``python -m stockstalker.backtest --chart``.
"""

from __future__ import annotations

from pathlib import Path

DISCLAIMER = "Educational research on historical data. Not investment advice. Not a SEBI-registered research analyst."


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def panel_titles(panels: list[dict]) -> list[str]:
    """One title per name: ticker without the exchange suffix, and its percentile."""
    return [
        f"{p['ticker'].split('.')[0]}: {_ordinal(round(p['exposure_matched_percentile'] * 100))} percentile"
        for p in panels
    ]


def plot_random_exposure(panels: list[dict], out_path: Path) -> Path:
    if not panels:
        raise ValueError("no backtest results to chart")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(panels), figsize=(4 * len(panels), 3.6), squeeze=False)
    for ax, p, title in zip(axes[0], panels, panel_titles(panels)):
        draws = p["random_draws"] * 100
        ax.hist(draws, bins=40, color="#9aa5b1")
        ax.axvline(p["strategy_return"] * 100, color="#111111", linewidth=2, label="screen's own days")
        ax.set_title(title, fontsize=11)
        ax.set_xlabel(f"cumulative return, % (long {p['days_long']} of {p['days_tested']} days)", fontsize=8)
        ax.legend(fontsize=8, loc="upper right")
    axes[0][0].set_ylabel(f"random draws (of {len(panels[0]['random_draws']):,})")
    fig.suptitle("Screen vs. random same-size exposure, before costs", fontsize=12)
    fig.text(0.5, 0.01, DISCLAIMER, ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
