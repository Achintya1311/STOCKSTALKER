"""Volume-at-price heatmap: where a name's volume has concentrated by price.

NISM XV 12.12 frames liquidity as ease of exit; this shows the price shelves
where that liquidity actually sits. A price band that has absorbed a lot of
past volume tends to act as support or resistance, because a lot of holders'
cost basis sits there.

The binning (:func:`volume_at_price`) and zone detection
(:func:`high_activity_zones`) are pure functions over a DataFrame, tested
independently of matplotlib. Only :func:`plot_liquidity_heatmap` touches the
filesystem or a plotting backend.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "outputs"


def volume_at_price(df: pd.DataFrame, bins: int = 24) -> pd.DataFrame:
    """Bucket each day's volume into an equal-width close-price bin.

    This is a simplification of a true volume profile, which spreads each
    bar's volume across its intrabar high-low range using tick data. Daily
    OHLCV alone carries no intrabar distribution, so this bins by the day's
    close instead — coarser, but it needs nothing this project doesn't
    already have. Documented as a limitation, not hidden.

    Returns a frame with one row per bin: ``bin_low``, ``bin_high``,
    ``volume`` (0 for a bin no day closed in). Bin volumes sum to the input's
    total volume — no day's volume is dropped or double-counted.
    """
    if bins < 1:
        raise ValueError(f"bins must be >= 1, got {bins}")
    if df.empty:
        raise ValueError("cannot compute volume-at-price for an empty frame")

    price_min, price_max = df["close"].min(), df["close"].max()
    if price_min == price_max:
        # Every close sat at exactly one price - one degenerate bin holds it all.
        edges = np.array([price_min, price_min + 1.0])
    else:
        edges = np.linspace(price_min, price_max, bins + 1)

    bin_idx = pd.cut(df["close"], bins=edges, include_lowest=True, labels=False)
    volume_by_bin = df["volume"].groupby(bin_idx).sum()
    volume_by_bin = volume_by_bin.reindex(range(len(edges) - 1), fill_value=0.0)

    return pd.DataFrame(
        {
            "bin_low": edges[:-1],
            "bin_high": edges[1:],
            "volume": volume_by_bin.to_numpy(dtype=float),
        }
    )


def high_activity_zones(vap: pd.DataFrame, threshold: float = 1.5) -> pd.DataFrame:
    """Bins whose volume is at least ``threshold``x the mean bin volume.

    A candidate support/resistance shelf, not a statistical claim. With zero
    total volume across all bins, nothing qualifies.
    """
    if threshold <= 0:
        raise ValueError(f"threshold must be > 0, got {threshold}")
    mean_volume = vap["volume"].mean()
    if mean_volume == 0:
        return vap.iloc[0:0]
    return vap[vap["volume"] >= threshold * mean_volume]


def plot_liquidity_heatmap(
    df: pd.DataFrame,
    ticker: str,
    bins: int = 24,
    threshold: float = 1.5,
    output_dir: Path | None = None,
) -> Path:
    """Draw a volume-at-price heatmap and write it to ``outputs/heatmap_<ticker>.png``.

    Bars are shaded on a single sequential ramp (light = low volume, dark =
    high volume) so magnitude reads by lightness, not hue. High-activity
    zones get a red edge and an inline label rather than a hue swap, so the
    zones are still identifiable without relying on color alone.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    vap = volume_at_price(df, bins=bins)
    zones = high_activity_zones(vap, threshold=threshold)

    out_dir = output_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"heatmap_{ticker.replace('.', '_')}.png"

    midpoints = (vap["bin_low"] + vap["bin_high"]) / 2
    heights = vap["bin_high"] - vap["bin_low"]
    peak = vap["volume"].max()
    shade = vap["volume"] / peak if peak > 0 else vap["volume"]
    colors = plt.get_cmap("Blues")(0.25 + 0.7 * shade)

    fig, ax = plt.subplots(figsize=(6, 8))
    ax.barh(
        midpoints,
        vap["volume"],
        height=heights * 0.9,
        color=colors,
        edgecolor="none",
        align="center",
    )
    is_zone = vap["bin_low"].isin(zones["bin_low"])
    for mid, height, hi in zip(midpoints[is_zone], heights[is_zone], vap["volume"][is_zone]):
        ax.barh(
            mid,
            hi,
            height=height * 0.9,
            facecolor="none",
            edgecolor="#d62728",
            linewidth=1.5,
            align="center",
        )
    if is_zone.any():
        top_zone_mid = midpoints[is_zone].iloc[0]
        ax.annotate(
            "high-activity zone",
            xy=(vap["volume"][is_zone].iloc[0], top_zone_mid),
            xytext=(8, 0),
            textcoords="offset points",
            fontsize=8,
            color="#d62728",
            va="center",
        )

    ax.set_xlabel("Volume traded at price")
    ax.set_ylabel("Price")
    ax.set_title(f"Volume-at-price — {ticker}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
