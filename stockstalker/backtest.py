"""Day 7 sanity check: does the blended screen score beat buy-and-hold?

Walk-forward, long/flat, one ticker at a time, on the committed fixtures.
No transaction costs, no position sizing, no shorting. This exists to
catch the screen being *worse* than doing nothing clever — it is a sanity
check, not a strategy pitch. See the README limitations section for what
it does not prove (three tickers, one two-year window, in-sample rule
thresholds).

Reuses :mod:`stockstalker.screener`'s own scoring functions rather than
re-deriving the math, so the walk-forward signal is provably the same
computation the live screen makes — just run once per day on truncated
history instead of once on the full window.
"""

from __future__ import annotations

import argparse
import csv
import json
import zlib
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .data.providers import ProviderError, load
from .screener import blended_score, compute_signals, load_config, load_universe

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "screen.yaml"
UNIVERSE_PATH = ROOT / "data" / "universe.txt"
OUTPUT_DIR = ROOT / "outputs"

DEFAULT_THRESHOLD = 0.5  # score >= 0.5 means the blend of signals is non-negative
DEFAULT_RANDOM_EXPOSURE_DRAWS = 2000
# R30: "signal-close" buys and sells at the close the score was computed on
# (the Day 7 convention, kept as the default); "next-open" fills at the
# following session's open, which a daily close-based signal can actually do.
FILLS = ("signal-close", "next-open")
# R31: a fixed grid around the Day 7 default, set in the critique that asked for it.
# Every cell is reported; the default was chosen on Day 7, not tuned.
THRESHOLD_GRID = (0.40, 0.45, 0.50, 0.55, 0.60)
DEFAULT_FILL = "signal-close"

# R29: the daily-snapshot workflow appends EOD bars here; nothing else reads them.
SNAPSHOT_PATH = ROOT / "data" / "snapshots" / "2026.csv"
# The signal math and weights were last changed on 7 Sep 2026 (d9c675a,
# b9038a2) and the fixtures end on 4 Sep, so bars after this date are the
# only days the rule was not chosen on.
RULE_FROZEN_ON = "2026-09-07"

# Indian delivery-equity costs. STT is charged on both legs of a delivery
# trade; stamp duty only on the buy leg (both NSE, as of this writing).
STT_RATE = 0.001
STAMP_DUTY_RATE = 0.00015
DEFAULT_SLIPPAGE_BPS = 10.0


def burn_in_period(cfg: dict[str, Any]) -> int:
    """Bars needed before every signal in the blend has a defined value.

    The slowest indicator in play sets the pace: SMA/EMA "slow" span, RSI
    period, MACD slow span, or either volume window, whichever asks for the
    most history.
    """
    return max(
        cfg["trend"]["slow"],
        cfg["momentum"]["rsi_period"],
        cfg["momentum"]["macd_slow"],
        cfg["volume"]["obv_window"],
        cfg["volume"]["z_window"],
    )


def walk_forward_scores(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.Series:
    """Blended score as of each bar's close, using only data up to and including it.

    Index-aligned with ``df``. Bars inside the burn-in window are NaN — not
    enough history yet for the slowest indicator in the blend. Recomputes
    the full signal stack on every truncated slice rather than incrementally
    updating it, which is O(n^2) but fine at fixture scale (a few hundred
    bars) and keeps this provably consistent with the live screen's math.
    """
    burn_in = burn_in_period(cfg)
    scores = pd.Series(index=df.index, dtype=float)
    for i in range(burn_in, len(df)):
        window = df.iloc[: i + 1]
        signals = compute_signals(window, cfg)
        scores.iloc[i] = blended_score(signals, cfg["weights"])
    return scores


def _held_returns(open_: np.ndarray, close: np.ndarray, prev_close: np.ndarray,
                  held: np.ndarray, prev_held: np.ndarray, fill: str) -> np.ndarray:
    """Daily returns of a long/flat holding pattern under one fill convention.

    ``held`` marks the days the position is on (decided at the previous
    close). Under "signal-close" every held day earns close-to-close. Under
    "next-open" an entry day earns open-to-close, a continuing day
    close-to-close, and the first flat day after a hold earns the move from
    the last close to the open it was sold at. Works on 1-D or (draws, days)
    arrays.
    """
    if fill not in FILLS:
        raise ValueError(f"fill must be one of {FILLS}, got {fill!r}")
    c2c = close / prev_close - 1.0
    if fill == "signal-close":
        return np.where(held, c2c, 0.0)
    entry = held & ~prev_held
    cont = held & prev_held
    exit_ = ~held & prev_held
    return (
        np.where(entry, close / open_ - 1.0, 0.0)
        + np.where(cont, c2c, 0.0)
        + np.where(exit_, open_ / prev_close - 1.0, 0.0)
    )


def long_flat_returns(
    df: pd.DataFrame, scores: pd.Series, threshold: float, fill: str = DEFAULT_FILL
) -> pd.Series:
    """Next-bar return, earned only when the *prior* bar's score cleared ``threshold``.

    Long/flat, no shorting, no leverage, no costs. A score known at the
    close of day t decides whether day t+1 is held. With the default
    "signal-close" fill the trade happens at that same close, the price the
    score was computed from; "next-open" fills at day t+1's open (R30).
    """
    held = holdings_from_scores(scores, threshold).to_numpy()
    prev_held = np.concatenate([[False], held[:-1]])
    close = df["close"].to_numpy(dtype=float)
    prev_close = np.concatenate([[np.nan], close[:-1]])
    # The default path needs only closes, so close-only frames still work.
    open_ = df["open"].to_numpy(dtype=float) if fill == "next-open" else close
    out = _held_returns(open_, close, prev_close, held, prev_held, fill)
    return pd.Series(out, index=df.index).fillna(0.0)


def holdings_from_scores(scores: pd.Series, threshold: float) -> pd.Series:
    """Actual day-by-day position: yesterday's score decides today's holding.

    Mirrors the ``position.shift(1)`` inside :func:`long_flat_returns` so the
    two never drift apart — this is what a trade-cost model needs to know
    when a position actually opens or closes, not just what the signal was.
    """
    position = (scores >= threshold).astype(float)
    return position.shift(1).fillna(0.0).astype(bool)


def trading_cost_series(
    holdings: pd.Series, buy_cost_rate: float, sell_cost_rate: float
) -> pd.Series:
    """Cost (as a fraction of position value) charged on each entry/exit day.

    A buy cost lands on the day a flat position turns long — that day's
    return already reflects holding from the open, so the entry cost belongs
    there. A sell cost lands on the *last* day still long, not the first flat
    day after: the flat day earns zero return by construction, while the
    exit realizes (and should discount) the gain the position just earned.
    A one-day round trip gets both costs on the same day.
    """
    prev_day_long = holdings.shift(1).fillna(False).astype(bool)
    next_day_long = holdings.shift(-1).fillna(False).astype(bool)
    entries = holdings & ~prev_day_long
    exits = holdings & ~next_day_long
    costs = pd.Series(0.0, index=holdings.index)
    costs[entries] += buy_cost_rate
    costs[exits] += sell_cost_rate
    return costs


def long_flat_returns_with_costs(
    df: pd.DataFrame,
    scores: pd.Series,
    threshold: float,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    fill: str = DEFAULT_FILL,
) -> pd.Series:
    """``long_flat_returns``, minus STT, stamp duty and slippage on every trade."""
    gross = long_flat_returns(df, scores, threshold, fill)
    holdings = holdings_from_scores(scores, threshold)
    slippage_rate = slippage_bps / 10_000
    buy_cost_rate = STT_RATE + STAMP_DUTY_RATE + slippage_rate
    sell_cost_rate = STT_RATE + slippage_rate
    costs = trading_cost_series(holdings, buy_cost_rate, sell_cost_rate)
    return gross - costs


def cumulative_return(returns: pd.Series) -> float:
    return float((1 + returns).prod() - 1)


def buy_and_hold_return(df: pd.DataFrame, start_idx: int) -> float:
    """Return of holding from the close at ``start_idx`` to the last close."""
    window = df.iloc[start_idx:]
    if len(window) < 2:
        return 0.0
    return float(window["close"].iloc[-1] / window["close"].iloc[0] - 1)


def buy_and_hold_return_with_costs(
    df: pd.DataFrame, start_idx: int, slippage_bps: float = DEFAULT_SLIPPAGE_BPS
) -> float:
    """``buy_and_hold_return`` after one round trip's STT, stamp duty and slippage.

    Buy-and-hold only trades twice (enter once, exit once), so this is exact
    rather than the strategy's day-by-day approximation: the effective entry
    price is marked up by the buy-side costs, the effective exit price marked
    down by the sell-side costs. Without this, "edge with costs" would compare
    a costed strategy against an uncosted benchmark, which is not a fair fight.
    """
    window = df.iloc[start_idx:]
    if len(window) < 2:
        return 0.0
    slippage_rate = slippage_bps / 10_000
    buy_cost_rate = STT_RATE + STAMP_DUTY_RATE + slippage_rate
    sell_cost_rate = STT_RATE + slippage_rate
    effective_entry = window["close"].iloc[0] * (1 + buy_cost_rate)
    effective_exit = window["close"].iloc[-1] * (1 - sell_cost_rate)
    return float(effective_exit / effective_entry - 1)


def random_exposure_returns(
    df: pd.DataFrame,
    start_idx: int,
    days_long: int,
    n_draws: int = DEFAULT_RANDOM_EXPOSURE_DRAWS,
    seed: int | None = None,
    fill: str = DEFAULT_FILL,
) -> np.ndarray:
    """Cumulative return of being long ``days_long`` of the tested days, picked at random.

    This is the exposure-matched baseline D16 asks for: 100%-exposure
    buy-and-hold only answers "beats being long every day?" It says nothing
    about whether the strategy's own chosen days are better than being long
    the *same number* of days chosen by chance. Draws ``n_draws`` random
    same-size subsets (without replacement) of the tested window's daily
    returns and compounds each subset the same way :func:`long_flat_returns`
    compounds the strategy's actual holding pattern.
    """
    daily_return = df["close"].pct_change().iloc[start_idx:].to_numpy()
    n = len(daily_return)
    if days_long <= 0 or n == 0:
        return np.zeros(n_draws)
    days_long = min(days_long, n)
    rng = np.random.default_rng(seed)
    # Vectorized without-replacement sampling: rank each day by an independent
    # random key per draw, keep the lowest `days_long` ranks. Equivalent to
    # `rng.choice(n, days_long, replace=False)` run `n_draws` times, without a
    # Python-level loop over draws.
    ranks = rng.random((n_draws, n))
    chosen = np.argsort(ranks, axis=1)[:, :days_long]
    if fill == DEFAULT_FILL:
        selected_returns = daily_return[chosen]
        return np.prod(1.0 + selected_returns, axis=1) - 1.0
    # Same draws, priced with the fill convention: entries and exits depend
    # on which neighbouring days were also drawn. The day before the window
    # counts as flat.
    held = np.zeros((n_draws, n), dtype=bool)
    np.put_along_axis(held, chosen, True, axis=1)
    prev_held = np.concatenate([np.zeros((n_draws, 1), dtype=bool), held[:, :-1]], axis=1)
    close = df["close"].to_numpy(dtype=float)
    returns = _held_returns(
        df["open"].to_numpy(dtype=float)[start_idx:], close[start_idx:],
        close[start_idx - 1:-1], held, prev_held, fill,
    )
    return np.prod(1.0 + returns, axis=1) - 1.0


def backtest_ticker(
    ticker: str,
    provider_name: str,
    cfg: dict[str, Any],
    threshold: float = DEFAULT_THRESHOLD,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    fill: str = DEFAULT_FILL,
    scores: pd.Series | None = None,
) -> dict[str, Any]:
    """Walk-forward strategy vs. buy-and-hold for one ticker, same tested window for both.

    Reports both the no-cost strategy return (the Day 7 number) and a
    cost-adjusted one (STT + stamp duty + slippage on every entry/exit), so
    neither number silently replaces the other.
    """
    df = load(ticker, provider=provider_name)
    burn_in = burn_in_period(cfg)
    if len(df) <= burn_in + 1:
        raise ProviderError(
            f"{ticker}: only {len(df)} bars, need more than {burn_in + 1} for burn-in"
        )

    if scores is None:  # the threshold grid passes them in: scores don't depend on it
        scores = walk_forward_scores(df, cfg)
    strategy_returns = long_flat_returns(df, scores, threshold, fill).iloc[burn_in + 1 :]
    strategy_returns_with_costs = long_flat_returns_with_costs(
        df, scores, threshold, slippage_bps, fill
    ).iloc[burn_in + 1 :]
    strategy_cum = cumulative_return(strategy_returns)
    strategy_cum_with_costs = cumulative_return(strategy_returns_with_costs)
    hold_cum = buy_and_hold_return(df, burn_in)
    hold_cum_with_costs = buy_and_hold_return_with_costs(df, burn_in, slippage_bps)

    tested_scores = scores.iloc[burn_in:-1]  # scores that actually gated a next-day trade
    days_long = int((tested_scores >= threshold).sum())

    # Exposure-matched random baseline (D16): is being long on *these*
    # days better than being long this *often* on days picked by chance?
    # A different question from buy-and-hold's "better than being long
    # every day". Seeded from the ticker name so the same ticker always
    # draws the same random subsets (reproducible, not a fresh roll per run).
    seed = zlib.crc32(ticker.encode())
    random_draws = random_exposure_returns(df, burn_in + 1, days_long, seed=seed, fill=fill)
    exposure_matched_mean_return = float(random_draws.mean())
    exposure_matched_std_return = (
        float(random_draws.std(ddof=1)) if len(random_draws) > 1 else 0.0
    )
    exposure_matched_percentile = float((random_draws < strategy_cum).mean())

    return {
        "ticker": ticker,
        "start": df.index[burn_in].date().isoformat(),
        "end": df.index[-1].date().isoformat(),
        "days_tested": int(len(strategy_returns)),
        "days_long": days_long,
        "strategy_return": round(strategy_cum, 4),
        "strategy_return_with_costs": round(strategy_cum_with_costs, 4),
        "buy_and_hold_return": round(hold_cum, 4),
        "buy_and_hold_return_with_costs": round(hold_cum_with_costs, 4),
        "edge": round(strategy_cum - hold_cum, 4),
        "edge_with_costs": round(strategy_cum_with_costs - hold_cum_with_costs, 4),
        "beat_buy_and_hold": strategy_cum > hold_cum,
        "beat_buy_and_hold_with_costs": strategy_cum_with_costs > hold_cum_with_costs,
        "exposure_matched_mean_return": round(exposure_matched_mean_return, 4),
        "exposure_matched_std_return": round(exposure_matched_std_return, 4),
        "beat_exposure_matched_random": strategy_cum > exposure_matched_mean_return,
        "exposure_matched_percentile": round(exposure_matched_percentile, 4),
    }


def load_snapshot_bars(ticker: str, path: Path = SNAPSHOT_PATH) -> pd.DataFrame:
    """One ticker's EOD bars from the daily snapshot file, oldest first.

    A rerun of the workflow on the same day rewrites that day's row, so the
    last row for a date wins. Rows with a missing price (yfinance sometimes
    returns a NaN last bar and the workflow commits it) are dropped, so the
    next kept bar's return spans the gap; ``bars.attrs["dropped_nan_rows"]``
    says how many.
    """
    cols = ["open", "high", "low", "close", "volume"]
    if not Path(path).exists():
        return pd.DataFrame(columns=cols, index=pd.DatetimeIndex([], name="date"))
    raw = pd.read_csv(path)
    raw = raw[raw["ticker"] == ticker].drop_duplicates("date", keep="last")
    bars = raw.set_index(pd.DatetimeIndex(pd.to_datetime(raw["date"]), name="date"))[cols]
    bars = bars.sort_index().astype(float)
    priced = bars[["open", "high", "low", "close"]].notna().all(axis=1)
    kept = bars[priced]
    kept.attrs["dropped_nan_rows"] = int((~priced).sum())
    return kept


def extend_with_snapshots(df: pd.DataFrame, snapshots: pd.DataFrame) -> pd.DataFrame:
    """Fixture bars, then every snapshot bar dated after the fixture's last bar.

    Where the two overlap (the fixtures' last day) the fixture bar is kept.
    """
    newer = snapshots[snapshots.index > df.index[-1]]
    out = pd.concat([df, newer.astype(df.dtypes.to_dict())])
    return out[~out.index.duplicated(keep="first")]


def out_of_sample_ticker(
    ticker: str,
    provider_name: str,
    cfg: dict[str, Any],
    threshold: float = DEFAULT_THRESHOLD,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    snapshot_path: Path = SNAPSHOT_PATH,
    frozen_on: str = RULE_FROZEN_ON,
    fill: str = DEFAULT_FILL,
) -> dict[str, Any]:
    """The frozen rule scored only on days after ``frozen_on`` (R29).

    Scores are walk-forward over fixtures plus snapshots, so the signal on
    the first out-of-sample day still sees its full history. Only the
    returns earned after the freeze are counted, against buy-and-hold and
    random same-size exposure over exactly those days.
    """
    snapshots = load_snapshot_bars(ticker, snapshot_path)
    df = extend_with_snapshots(load(ticker, provider=provider_name), snapshots)
    after = df.index > pd.Timestamp(frozen_on)
    if not after.any():
        raise ProviderError(f"{ticker}: no snapshot bars after {frozen_on}")
    start_idx = int(np.argmax(after))
    scores = walk_forward_scores(df, cfg)
    gross = long_flat_returns(df, scores, threshold, fill)[after]
    net = long_flat_returns_with_costs(df, scores, threshold, slippage_bps, fill)[after]
    days_long = int(holdings_from_scores(scores, threshold)[after].sum())
    strategy_cum = cumulative_return(gross)
    hold_cum = float(df["close"].iloc[-1] / df["close"].iloc[start_idx - 1] - 1.0)
    draws = random_exposure_returns(df, start_idx, days_long, seed=zlib.crc32(ticker.encode()), fill=fill)
    return {
        "ticker": ticker,
        "start": df.index[start_idx].date().isoformat(),
        "end": df.index[-1].date().isoformat(),
        "days_tested": int(after.sum()),
        "days_long": days_long,
        "snapshot_rows_dropped_nan": snapshots.attrs.get("dropped_nan_rows", 0),
        "strategy_return": round(strategy_cum, 4),
        "strategy_return_with_costs": round(cumulative_return(net), 4),
        "buy_and_hold_return": round(hold_cum, 4),
        "exposure_matched_mean_return": round(float(draws.mean()), 4),
        # Never long means nothing to compare: no percentile rather than a fake 0%.
        "exposure_matched_percentile": round(float((draws < strategy_cum).mean()), 4) if days_long else None,
    }


def run_out_of_sample(
    tickers: list[str],
    provider_name: str,
    cfg: dict[str, Any],
    threshold: float = DEFAULT_THRESHOLD,
    errors: list[str] | None = None,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    snapshot_path: Path = SNAPSHOT_PATH,
    fill: str = DEFAULT_FILL,
) -> dict[str, Any]:
    if errors is None:
        errors = []
    results = []
    for ticker in tickers:
        try:
            results.append(
                out_of_sample_ticker(ticker, provider_name, cfg, threshold, slippage_bps, snapshot_path, fill=fill)
            )
        except ProviderError as exc:
            errors.append(f"{ticker} (out of sample): {exc}")
    return {
        "rule_frozen_on": RULE_FROZEN_ON,
        "snapshot_file": str(Path(snapshot_path).relative_to(ROOT)) if Path(snapshot_path).is_relative_to(ROOT) else str(snapshot_path),
        "results": results,
        "tickers_beating_exposure_matched_random": sum(
            1 for r in results if r["days_long"] and r["strategy_return"] > r["exposure_matched_mean_return"]
        ),
        "tickers_never_long": sum(1 for r in results if not r["days_long"]),
    }


def run_threshold_grid(
    tickers: list[str],
    provider_name: str,
    cfg: dict[str, Any],
    grid: tuple[float, ...] = THRESHOLD_GRID,
    errors: list[str] | None = None,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    fill: str = DEFAULT_FILL,
) -> list[dict[str, Any]]:
    """The same backtest at every threshold in ``grid`` (R31), scores computed once per ticker."""
    if errors is None:
        errors = []
    scores = {}
    for ticker in tickers:
        try:
            scores[ticker] = walk_forward_scores(load(ticker, provider=provider_name), cfg)
        except ProviderError as exc:
            errors.append(f"{ticker} (threshold grid): {exc}")
    rows = []
    for threshold in grid:
        results = [
            backtest_ticker(t, provider_name, cfg, threshold, slippage_bps, fill, scores=sc)
            for t, sc in scores.items()
        ]
        rows.append({
            "threshold": threshold,
            "default": threshold == DEFAULT_THRESHOLD,
            "tickers_tested": len(results),
            "tickers_beating_buy_and_hold_with_costs": sum(r["beat_buy_and_hold_with_costs"] for r in results),
            "tickers_beating_exposure_matched_random": sum(r["beat_exposure_matched_random"] for r in results),
            "days_long": {r["ticker"]: r["days_long"] for r in results},
            "percentiles": {r["ticker"]: r["exposure_matched_percentile"] for r in results},
        })
    return rows


def run_backtest(
    tickers: list[str],
    provider_name: str,
    cfg: dict[str, Any],
    threshold: float = DEFAULT_THRESHOLD,
    generated: str | None = None,
    errors: list[str] | None = None,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    fill: str = DEFAULT_FILL,
) -> dict[str, Any]:
    """Backtest every ticker, dropping (and recording) the ones that fail to fetch."""
    if errors is None:
        errors = []
    results = []
    for ticker in tickers:
        try:
            results.append(backtest_ticker(ticker, provider_name, cfg, threshold, slippage_bps, fill))
        except ProviderError as exc:
            errors.append(f"{ticker}: {exc}")

    n_beat = sum(1 for r in results if r["beat_buy_and_hold"])
    n_beat_with_costs = sum(1 for r in results if r["beat_buy_and_hold_with_costs"])
    n_beat_random_exposure = sum(1 for r in results if r["beat_exposure_matched_random"])
    # Simple honest uncertainty measure for the cross-ticker mean edge (D16):
    # stderr of the per-ticker edges, not just their mean. With n=3 this is
    # wide, not a claim of significance -- it says how wide, instead of
    # saying nothing at all.
    edges = [r["edge"] for r in results]
    mean_edge_stderr = (
        float(np.std(edges, ddof=1) / np.sqrt(len(edges))) if len(edges) > 1 else 0.0
    )
    summary = {
        "tickers_tested": len(results),
        "tickers_beating_buy_and_hold": n_beat,
        "tickers_beating_buy_and_hold_with_costs": n_beat_with_costs,
        "tickers_beating_exposure_matched_random": n_beat_random_exposure,
        "mean_edge_stderr": round(mean_edge_stderr, 4),
        "mean_strategy_return": round(sum(r["strategy_return"] for r in results) / len(results), 4)
        if results
        else 0.0,
        "mean_strategy_return_with_costs": round(
            sum(r["strategy_return_with_costs"] for r in results) / len(results), 4
        )
        if results
        else 0.0,
        "mean_buy_and_hold_return": round(
            sum(r["buy_and_hold_return"] for r in results) / len(results), 4
        )
        if results
        else 0.0,
        "mean_buy_and_hold_return_with_costs": round(
            sum(r["buy_and_hold_return_with_costs"] for r in results) / len(results), 4
        )
        if results
        else 0.0,
    }
    return {
        "schema": "backtest-v1",
        "generated": generated or date.today().isoformat(),
        "threshold": threshold,
        "fill": fill,
        "source": provider_name,
        "slippage_bps": slippage_bps,
        "costs": {
            "stt_rate": STT_RATE,
            "stamp_duty_rate": STAMP_DUTY_RATE,
            "slippage_bps": slippage_bps,
        },
        "results": results,
        "summary": summary,
    }


def write_json(report: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(report, indent=2) + "\n")


def write_csv(report: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "ticker", "start", "end", "days_tested", "days_long",
        "strategy_return", "strategy_return_with_costs",
        "buy_and_hold_return", "buy_and_hold_return_with_costs",
        "edge", "edge_with_costs",
        "beat_buy_and_hold", "beat_buy_and_hold_with_costs",
        "exposure_matched_mean_return", "exposure_matched_std_return",
        "beat_exposure_matched_random", "exposure_matched_percentile",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in report["results"]:
            writer.writerow(r)


def _markdown_table(report: dict[str, Any], with_costs: bool = False) -> str:
    """Same shape as the Day 7 table. ``with_costs`` swaps in the cost-adjusted fields."""
    suffix = "_with_costs" if with_costs else ""
    beat_key = "beat_buy_and_hold" + suffix
    header = "| Ticker | Window | Days tested | Days long | Strategy | Buy & hold | Edge | Beat B&H |"
    sep = "|--------|--------|-------------|-----------|----------|------------|------|----------|"
    rows = [header, sep]
    for r in report["results"]:
        strategy_return = r["strategy_return" + suffix]
        hold_return = r["buy_and_hold_return" + suffix]
        edge = r["edge" + suffix]
        rows.append(
            f"| {r['ticker']} | {r['start']} to {r['end']} | {r['days_tested']} | {r['days_long']} "
            f"| {strategy_return:+.2%} | {hold_return:+.2%} | {edge:+.2%} "
            f"| {'yes' if r[beat_key] else 'no'} |"
        )
    return "\n".join(rows)


def _exposure_matched_markdown_table(report: dict[str, Any]) -> str:
    """D16: beats being long this often, on these days, vs. being long this often at random."""
    header = (
        "| Ticker | Days long / tested | Strategy (no cost) | Random-exposure mean | "
        "Random-exposure std | Beat random | Percentile |"
    )
    sep = "|--------|---------------------|---------------------|-----------------------|----------------------|--------------|------------|"
    rows = [header, sep]
    for r in report["results"]:
        rows.append(
            f"| {r['ticker']} | {r['days_long']}/{r['days_tested']} "
            f"| {r['strategy_return']:+.2%} | {r['exposure_matched_mean_return']:+.2%} "
            f"| {r['exposure_matched_std_return']:.2%} "
            f"| {'yes' if r['beat_exposure_matched_random'] else 'no'} "
            f"| {r['exposure_matched_percentile']:.0%} |"
        )
    return "\n".join(rows)


def write_markdown(report: dict[str, Any], errors: list[str], path: Path) -> None:
    s = report["summary"]
    slippage_bps = report.get("slippage_bps", DEFAULT_SLIPPAGE_BPS)
    lines = [
        f"# Backtest sanity check — {report['generated']}",
        "",
        f"Walk-forward long/flat on the blended screen score (threshold {report['threshold']}), "
        f"source {report['source']}. No shorting, no position sizing. Reports both a no-cost "
        "return and one after costs — STT (0.1% each side), stamp duty (0.015%, buy side only) "
        f"and {slippage_bps:.0f} bps slippage on each trade — so neither number hides the other.",
        "",
    ]
    if report["results"]:
        lines += ["### No costs (Day 7)", ""]
        lines.append(_markdown_table(report, with_costs=False))
        lines += [
            "",
            f"**{s['tickers_beating_buy_and_hold']}/{s['tickers_tested']}** ticker(s) beat "
            f"100%-exposure buy-and-hold. Mean strategy return {s['mean_strategy_return']:+.2%} "
            f"vs. mean buy-and-hold {s['mean_buy_and_hold_return']:+.2%} "
            f"(mean edge {s['mean_strategy_return'] - s['mean_buy_and_hold_return']:+.2%} "
            f"± stderr {s['mean_edge_stderr']:.2%}, n={s['tickers_tested']} — "
            "three tickers is a wide error bar, not a claim of significance).",
            "",
            "### Exposure-matched random baseline (Day 58)",
            "",
            "100%-exposure buy-and-hold above answers \"beats being long every day?\" "
            "This table answers a different question: is the strategy's own choice of "
            f"days better than being long this *often* — the same `days_long` count — "
            "on days picked at random? Each ticker's random-exposure mean/std/percentile "
            f"come from {DEFAULT_RANDOM_EXPOSURE_DRAWS} random same-size draws of its own "
            "tested window.",
            "",
        ]
        lines.append(_exposure_matched_markdown_table(report))
        lines += [
            "",
            f"**{s['tickers_beating_exposure_matched_random']}/{s['tickers_tested']}** "
            "ticker(s) beat being long this often, on these days, vs. being long this "
            "often at random.",
            "",
            "### With costs (Day 8)",
            "",
        ]
        lines.append(_markdown_table(report, with_costs=True))
        lines += [
            "",
            f"**{s['tickers_beating_buy_and_hold_with_costs']}/{s['tickers_tested']}** "
            f"ticker(s) beat buy-and-hold. Mean strategy return "
            f"{s['mean_strategy_return_with_costs']:+.2%} vs. mean buy-and-hold "
            f"{s['mean_buy_and_hold_return_with_costs']:+.2%} — buy-and-hold pays the same "
            "cost schedule on its one entry and one exit, so this stays a fair comparison; "
            "it barely moves the buy-and-hold number because it is one round trip, not one "
            "per day.",
        ]
    else:
        lines.append("No tickers had enough history to test.")
    if errors:
        lines += ["", "## Errors", ""]
        lines += [f"- {e}" for e in errors]
    lines += [
        "",
        "## Caveats",
        "",
        "- Three tickers, one ~2-year fixture window. This is not statistically "
        "meaningful evidence of edge either way.",
        "- Rule thresholds (`min_score` etc.) and signal weights in `config/screen.yaml` "
        "were hand-picked, not fit on this data, but they were picked before this "
        "check existed to test them — later re-tuning against this same window "
        "would be in-sample.",
        "- Costs are a flat percentage of position value per trade (STT, stamp duty, "
        "slippage), not a real order-book fill. No bid-ask spread is modeled separately, "
        "and the buy-and-hold leg pays the same per-trade cost schedule on its single "
        "entry and exit — so the comparison is apples-to-apples, but still a simplification "
        "of what either side would actually pay.",
        "- Long/flat only. No short leg, so a strategy that only avoids the worst "
        "days can still show a smaller loss than buy-and-hold without ever making money.",
        f"- The random-exposure baseline draws {DEFAULT_RANDOM_EXPOSURE_DRAWS} random "
        "same-size subsets of each ticker's own already-realized daily returns (seeded "
        "per ticker, so it reproduces run to run) — it is a resampling of the one "
        "historical path that happened, not a fresh market simulation, and at n=3 "
        "tickers the mean-edge stderr above is a wide error bar, not a significance claim.",
    ]
    path.write_text("\n".join(lines) + "\n")


def print_report(report: dict[str, Any], errors: list[str]) -> None:
    s = report["summary"]
    slippage_bps = report.get("slippage_bps", DEFAULT_SLIPPAGE_BPS)
    print(
        f"Backtest {report['generated']} — threshold {report['threshold']}, "
        f"fill {report.get('fill', DEFAULT_FILL)} ({report['source']})"
    )
    print(f"  costs: STT {STT_RATE:.2%}/side, stamp duty {STAMP_DUTY_RATE:.3%} (buy only), slippage {slippage_bps:.0f}bps")
    for r in report["results"]:
        verdict = "beats" if r["beat_buy_and_hold"] else "loses to"
        verdict_with_costs = "beats" if r["beat_buy_and_hold_with_costs"] else "loses to"
        verdict_random = "beats" if r["beat_exposure_matched_random"] else "loses to"
        print(
            f"  {r['ticker']:<14} strategy {r['strategy_return']:+.2%} -> {r['strategy_return_with_costs']:+.2%} "
            f"with costs  buy&hold {r['buy_and_hold_return']:+.2%} -> {r['buy_and_hold_return_with_costs']:+.2%} "
            f"({verdict} buy&hold no-cost, {verdict_with_costs} with costs, "
            f"{r['days_long']}/{r['days_tested']} days long, {r['start']} to {r['end']})"
        )
        print(
            f"  {'':<14} vs. random exposure (same {r['days_long']} days, chosen at random): "
            f"mean {r['exposure_matched_mean_return']:+.2%} ± {r['exposure_matched_std_return']:.2%} "
            f"({verdict_random} random, {r['exposure_matched_percentile']:.0%} percentile)"
        )
    if report["results"]:
        print(
            f"  {s['tickers_beating_buy_and_hold']}/{s['tickers_tested']} beat 100%-exposure buy-and-hold (no cost) — "
            f"mean {s['mean_strategy_return']:+.2%} vs {s['mean_buy_and_hold_return']:+.2%} "
            f"(edge ± stderr {s['mean_edge_stderr']:.2%}, n={s['tickers_tested']})"
        )
        print(
            f"  {s['tickers_beating_buy_and_hold_with_costs']}/{s['tickers_tested']} beat buy-and-hold (with costs) — "
            f"mean {s['mean_strategy_return_with_costs']:+.2%} vs {s['mean_buy_and_hold_return_with_costs']:+.2%}"
        )
        print(
            f"  {s['tickers_beating_exposure_matched_random']}/{s['tickers_tested']} beat being long this often, "
            "on these days, vs. being long this often at random"
        )
    grid = report.get("threshold_grid")
    if grid:
        print("  Threshold grid (fixed grid, every cell reported; * = default; percentile vs. random same-size exposure):")
        for row in grid:
            cells = ", ".join(f"{t.split('.')[0]} {p:.0%}" for t, p in row["percentiles"].items())
            print(
                f"  {'*' if row['default'] else ' '} {row['threshold']:.2f}  "
                f"{row['tickers_beating_exposure_matched_random']}/{row['tickers_tested']} beat random, "
                f"{row['tickers_beating_buy_and_hold_with_costs']}/{row['tickers_tested']} beat buy-and-hold with costs  ({cells})"
            )
    oos = report.get("out_of_sample")
    if oos:
        print(f"  Out of sample (days after the rule froze on {oos['rule_frozen_on']}, from {oos['snapshot_file']}):")
        for r in oos["results"]:
            print(
                f"  {r['ticker']:<14} strategy {r['strategy_return']:+.2%} -> {r['strategy_return_with_costs']:+.2%} "
                f"with costs  buy&hold {r['buy_and_hold_return']:+.2%}  "
                f"{r['days_long']}/{r['days_tested']} days long, {r['start']} to {r['end']} "
                f"({r['snapshot_rows_dropped_nan']} snapshot days with no price skipped); "
                + (
                    f"random-exposure mean {r['exposure_matched_mean_return']:+.2%}, "
                    f"{r['exposure_matched_percentile']:.0%} percentile"
                    if r["days_long"]
                    else "never long, so no random comparison"
                )
            )
        print(
            f"  {oos['tickers_beating_exposure_matched_random']}/{len(oos['results']) - oos['tickers_never_long']} "
            f"beat random same-size exposure out of sample ({oos['tickers_never_long']} never long; "
            "a few weeks per name: too short to say anything on its own)"
        )
    for e in errors:
        print(f"  ! {e}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(CONFIG_PATH), help="YAML rules file")
    parser.add_argument("--universe", default=str(UNIVERSE_PATH), help="ticker list, one per line")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--live", action="store_true", help="fetch via yfinance instead of committed fixtures"
    )
    parser.add_argument(
        "--offline", action="store_true", help="explicit fixtures path (already the default)"
    )
    parser.add_argument("--date", default=None, help="override the generated date (mainly for tests)")
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=DEFAULT_SLIPPAGE_BPS,
        help="slippage in basis points, charged on each entry and exit (default 10)",
    )
    parser.add_argument(
        "--out-of-sample",
        action="store_true",
        help="also score the frozen rule on data/snapshots bars after RULE_FROZEN_ON (R29)",
    )
    parser.add_argument(
        "--fill",
        choices=FILLS,
        default=DEFAULT_FILL,
        help="trade at the signal's own close (default, the Day 7 convention) or the next open (R30)",
    )
    parser.add_argument(
        "--threshold-grid",
        action="store_true",
        help=f"also run every threshold in {THRESHOLD_GRID} and report each cell (R31)",
    )
    args = parser.parse_args(argv)

    if args.live and args.offline:
        parser.error("--live and --offline are mutually exclusive")

    provider_name = "yfinance" if args.live else "fixtures"
    cfg = load_config(Path(args.config))
    tickers = load_universe(Path(args.universe))
    generated = args.date or date.today().isoformat()

    if not tickers:
        print(f"no tickers in {args.universe}")
        return 1

    errors: list[str] = []
    report = run_backtest(
        tickers, provider_name, cfg, args.threshold, generated, errors, args.slippage_bps, args.fill
    )

    if args.threshold_grid:
        report["threshold_grid"] = run_threshold_grid(
            tickers, provider_name, cfg, errors=errors, slippage_bps=args.slippage_bps, fill=args.fill
        )
    if args.out_of_sample:
        report["out_of_sample"] = run_out_of_sample(
            tickers, provider_name, cfg, args.threshold, errors, args.slippage_bps, fill=args.fill
        )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, out_dir / f"backtest_{generated}.json")
    write_csv(report, out_dir / f"backtest_{generated}.csv")
    write_markdown(report, errors, out_dir / f"backtest_{generated}.md")

    print_report(report, errors)
    return 0 if report["results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
