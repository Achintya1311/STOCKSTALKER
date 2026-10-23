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

# Indian delivery-equity costs. STT is charged on both legs of a delivery
# trade; stamp duty only on the buy leg (both NSE, as of this writing).
STT_RATE = 0.001
STAMP_DUTY_RATE = 0.00015
DEFAULT_SLIPPAGE_BPS = 10.0


def burn_in_period(cfg: dict[str, Any]) -> int:
    """Bars needed before every signal in the blend has a defined value.

    The slowest indicator in play sets the pace: SMA/EMA "slow" span, MACD
    slow span, or either volume window, whichever asks for the most history.
    """
    return max(
        cfg["trend"]["slow"],
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


def long_flat_returns(df: pd.DataFrame, scores: pd.Series, threshold: float) -> pd.Series:
    """Next-bar return, earned only when the *prior* bar's score cleared ``threshold``.

    Long/flat, no shorting, no leverage, no costs. A score known at the
    close of day t decides whether day t+1's return is captured — the
    signal never trades the bar it was computed on.
    """
    daily_return = df["close"].pct_change()
    position = (scores >= threshold).astype(float)
    return (position.shift(1) * daily_return).fillna(0.0)


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
) -> pd.Series:
    """``long_flat_returns``, minus STT, stamp duty and slippage on every trade."""
    gross = long_flat_returns(df, scores, threshold)
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
    selected_returns = daily_return[chosen]
    return np.prod(1.0 + selected_returns, axis=1) - 1.0


def backtest_ticker(
    ticker: str,
    provider_name: str,
    cfg: dict[str, Any],
    threshold: float = DEFAULT_THRESHOLD,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
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

    scores = walk_forward_scores(df, cfg)
    strategy_returns = long_flat_returns(df, scores, threshold).iloc[burn_in + 1 :]
    strategy_returns_with_costs = long_flat_returns_with_costs(
        df, scores, threshold, slippage_bps
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
    random_draws = random_exposure_returns(df, burn_in + 1, days_long, seed=seed)
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


def run_backtest(
    tickers: list[str],
    provider_name: str,
    cfg: dict[str, Any],
    threshold: float = DEFAULT_THRESHOLD,
    generated: str | None = None,
    errors: list[str] | None = None,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
) -> dict[str, Any]:
    """Backtest every ticker, dropping (and recording) the ones that fail to fetch."""
    if errors is None:
        errors = []
    results = []
    for ticker in tickers:
        try:
            results.append(backtest_ticker(ticker, provider_name, cfg, threshold, slippage_bps))
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
    print(f"Backtest {report['generated']} — threshold {report['threshold']} ({report['source']})")
    print(f"  costs: STT {STT_RATE:.2%}/side, stamp duty {STAMP_DUTY_RATE:.3%} (buy only), slippage {slippage_bps:.0f}bps")
    for r in report["results"]:
        verdict = "beats" if r["beat_buy_and_hold"] else "loses to"
        verdict_with_costs = "beats" if r["beat_buy_and_hold_with_costs"] else "loses to"
        verdict_random = "beats" if r["beat_exposure_matched_random"] else "loses to"
        print(
            f"  {r['ticker']:<14} strategy {r['strategy_return']:+.2%} -> {r['strategy_return_with_costs']:+.2%} "
            f"with costs  buy&hold {r['buy_and_hold_return']:+.2%} -> {r['buy_and_hold_return_with_costs']:+.2%} "
            f"({verdict} buy&hold no-cost, {verdict_with_costs} with costs, "
            f"{r['days_long']}/{r['days_tested']} days long)"
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
        tickers, provider_name, cfg, args.threshold, generated, errors, args.slippage_bps
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
