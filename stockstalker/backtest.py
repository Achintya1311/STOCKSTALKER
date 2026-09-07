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
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .data.providers import ProviderError, load
from .screener import blended_score, compute_signals, load_config, load_universe

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "screen.yaml"
UNIVERSE_PATH = ROOT / "data" / "universe.txt"
OUTPUT_DIR = ROOT / "outputs"

DEFAULT_THRESHOLD = 0.5  # score >= 0.5 means the blend of signals is non-negative


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


def cumulative_return(returns: pd.Series) -> float:
    return float((1 + returns).prod() - 1)


def buy_and_hold_return(df: pd.DataFrame, start_idx: int) -> float:
    """Return of holding from the close at ``start_idx`` to the last close."""
    window = df.iloc[start_idx:]
    if len(window) < 2:
        return 0.0
    return float(window["close"].iloc[-1] / window["close"].iloc[0] - 1)


def backtest_ticker(
    ticker: str, provider_name: str, cfg: dict[str, Any], threshold: float = DEFAULT_THRESHOLD
) -> dict[str, Any]:
    """Walk-forward strategy vs. buy-and-hold for one ticker, same tested window for both."""
    df = load(ticker, provider=provider_name)
    burn_in = burn_in_period(cfg)
    if len(df) <= burn_in + 1:
        raise ProviderError(
            f"{ticker}: only {len(df)} bars, need more than {burn_in + 1} for burn-in"
        )

    scores = walk_forward_scores(df, cfg)
    strategy_returns = long_flat_returns(df, scores, threshold).iloc[burn_in + 1 :]
    strategy_cum = cumulative_return(strategy_returns)
    hold_cum = buy_and_hold_return(df, burn_in)

    tested_scores = scores.iloc[burn_in:-1]  # scores that actually gated a next-day trade
    days_long = int((tested_scores >= threshold).sum())

    return {
        "ticker": ticker,
        "start": df.index[burn_in].date().isoformat(),
        "end": df.index[-1].date().isoformat(),
        "days_tested": int(len(strategy_returns)),
        "days_long": days_long,
        "strategy_return": round(strategy_cum, 4),
        "buy_and_hold_return": round(hold_cum, 4),
        "edge": round(strategy_cum - hold_cum, 4),
        "beat_buy_and_hold": strategy_cum > hold_cum,
    }


def run_backtest(
    tickers: list[str],
    provider_name: str,
    cfg: dict[str, Any],
    threshold: float = DEFAULT_THRESHOLD,
    generated: str | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """Backtest every ticker, dropping (and recording) the ones that fail to fetch."""
    if errors is None:
        errors = []
    results = []
    for ticker in tickers:
        try:
            results.append(backtest_ticker(ticker, provider_name, cfg, threshold))
        except ProviderError as exc:
            errors.append(f"{ticker}: {exc}")

    n_beat = sum(1 for r in results if r["beat_buy_and_hold"])
    summary = {
        "tickers_tested": len(results),
        "tickers_beating_buy_and_hold": n_beat,
        "mean_strategy_return": round(sum(r["strategy_return"] for r in results) / len(results), 4)
        if results
        else 0.0,
        "mean_buy_and_hold_return": round(
            sum(r["buy_and_hold_return"] for r in results) / len(results), 4
        )
        if results
        else 0.0,
    }
    return {
        "schema": "backtest-v1",
        "generated": generated or date.today().isoformat(),
        "threshold": threshold,
        "source": provider_name,
        "results": results,
        "summary": summary,
    }


def write_json(report: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(report, indent=2) + "\n")


def write_csv(report: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "ticker", "start", "end", "days_tested", "days_long",
        "strategy_return", "buy_and_hold_return", "edge", "beat_buy_and_hold",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in report["results"]:
            writer.writerow(r)


def _markdown_table(report: dict[str, Any]) -> str:
    header = "| Ticker | Window | Days tested | Days long | Strategy | Buy & hold | Edge | Beat B&H |"
    sep = "|--------|--------|-------------|-----------|----------|------------|------|----------|"
    rows = [header, sep]
    for r in report["results"]:
        rows.append(
            f"| {r['ticker']} | {r['start']} to {r['end']} | {r['days_tested']} | {r['days_long']} "
            f"| {r['strategy_return']:+.2%} | {r['buy_and_hold_return']:+.2%} | {r['edge']:+.2%} "
            f"| {'yes' if r['beat_buy_and_hold'] else 'no'} |"
        )
    return "\n".join(rows)


def write_markdown(report: dict[str, Any], errors: list[str], path: Path) -> None:
    s = report["summary"]
    lines = [
        f"# Backtest sanity check — {report['generated']}",
        "",
        f"Walk-forward long/flat on the blended screen score (threshold {report['threshold']}), "
        f"source {report['source']}. No costs, no shorting, no position sizing — "
        "this checks the screen isn't obviously worse than doing nothing clever, "
        "nothing more.",
        "",
    ]
    if report["results"]:
        lines.append(_markdown_table(report))
        lines += [
            "",
            f"**{s['tickers_beating_buy_and_hold']}/{s['tickers_tested']}** ticker(s) beat "
            f"buy-and-hold. Mean strategy return {s['mean_strategy_return']:+.2%} vs. "
            f"mean buy-and-hold {s['mean_buy_and_hold_return']:+.2%}.",
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
        "- No transaction costs, slippage, or bid-ask spread. Real trading would erode "
        "any edge shown here, especially with daily rebalancing.",
        "- Long/flat only. No short leg, so a strategy that only avoids the worst "
        "days can still show a smaller loss than buy-and-hold without ever making money.",
    ]
    path.write_text("\n".join(lines) + "\n")


def print_report(report: dict[str, Any], errors: list[str]) -> None:
    s = report["summary"]
    print(f"Backtest {report['generated']} — threshold {report['threshold']} ({report['source']})")
    for r in report["results"]:
        verdict = "beats" if r["beat_buy_and_hold"] else "loses to"
        print(
            f"  {r['ticker']:<14} strategy {r['strategy_return']:+.2%}  "
            f"buy&hold {r['buy_and_hold_return']:+.2%}  ({verdict} buy&hold, "
            f"{r['days_long']}/{r['days_tested']} days long)"
        )
    if report["results"]:
        print(
            f"  {s['tickers_beating_buy_and_hold']}/{s['tickers_tested']} beat buy-and-hold — "
            f"mean {s['mean_strategy_return']:+.2%} vs {s['mean_buy_and_hold_return']:+.2%}"
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
    report = run_backtest(tickers, provider_name, cfg, args.threshold, generated, errors)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, out_dir / f"backtest_{generated}.json")
    write_csv(report, out_dir / f"backtest_{generated}.csv")
    write_markdown(report, errors, out_dir / f"backtest_{generated}.md")

    print_report(report, errors)
    return 0 if report["results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
