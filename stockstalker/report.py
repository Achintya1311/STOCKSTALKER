"""Day 8: terminal report and chart files.

Runs the screen and the walk-forward backtest in memory (via
``screener.build_screen`` and ``backtest.run_backtest`` — no new scoring
math lives here) and renders two ``rich`` tables to the terminal: ranked
candidates, and how each did against buy-and-hold. Also draws a
volume-at-price liquidity heatmap per candidate to ``outputs/`` — reusing
``viz.liquidity.plot_liquidity_heatmap`` rather than a new chart routine.

Still no server and no dashboard: this is one CLI invocation that prints a
report and writes PNG files, the same shape as ``screener.py`` and
``backtest.py``.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .backtest import DEFAULT_THRESHOLD, run_backtest
from .data.providers import ProviderError, load
from .gates.factor import apply_factor_gate, load_contract as load_factor_contract
from .gates.risk import apply_risk_gate, load_contract as load_risk_contract
from .gates.valuation import apply_valuation_gate, load_contract as load_valuation_contract
from .screener import CONFIG_PATH, UNIVERSE_PATH, build_screen, load_config, load_universe
from .viz.liquidity import plot_liquidity_heatmap

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"


def render_screen_table(screen: dict[str, Any]) -> Table:
    """Ranked candidates, one row per ticker that cleared the screen's filters.

    Adds a Valuation column (v0.7, reverse-dcf-engine's implied vs. breakeven
    growth) and a Factor column (v0.2, fama-french-factor-model's alpha vs.
    market loading) only when at least one candidate carries that key — most
    runs have none, since a gate only attaches it to the one ticker a
    satellite has actually researched.
    """
    has_valuation = any("valuation" in c for c in screen["candidates"])
    has_risk = any("risk" in c for c in screen["candidates"])
    has_factor = any("factor" in c for c in screen["candidates"])
    table = Table(title=f"Screen — {screen['generated']} ({screen['universe']}, {screen['source']})")
    table.add_column("Rank", justify="right")
    table.add_column("Ticker")
    table.add_column("Score", justify="right")
    table.add_column("Trend", justify="right")
    table.add_column("Momentum", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("ADV(20d)", justify="right")
    if has_risk:
        table.add_column("VaR 95%")
        table.add_column("CVaR 95%")
    if has_valuation:
        table.add_column("Implied CAGR")
        table.add_column("Breakeven growth")
    if has_factor:
        table.add_column("Alpha (ann.)")
        table.add_column("Mkt loading")
        table.add_column("Sig.(5%)")
    for c in screen["candidates"]:
        s = c["signals"]
        row = [
            str(c["rank"]),
            c["ticker"],
            f"{c['score']:.4f}",
            f"{s['trend']:+.3f}",
            f"{s['momentum']:+.3f}",
            f"{s['volume']:+.3f}",
            f"{c['liquidity']['adv_20d']:,.0f}",
        ]
        if has_risk:
            r = c.get("risk")
            row.append(f"{r['var_95']:+.2%}" if r else "-")
            row.append(f"{r['cvar_95']:+.2%}" if r else "-")
        if has_valuation:
            v = c.get("valuation")
            row.append(f"{v['implied_cagr']:+.2%}" if v else "-")
            row.append(f"{v['breakeven_growth']:+.2%}" if v else "-")
        if has_factor:
            f = c.get("factor")
            row.append(f"{f['alpha_annual']:+.2%}" if f else "-")
            row.append(f"{f['loadings'].get('mkt'):+.2f}" if f else "-")
            row.append(str(f["significant"]) if f else "-")
        table.add_row(*row)
    return table


def render_backtest_table(report: dict[str, Any]) -> Table:
    """Walk-forward strategy vs. buy-and-hold, one row per ticker tested."""
    s = report["summary"]
    table = Table(
        title=f"Backtest — threshold {report['threshold']} "
        f"({s['tickers_beating_buy_and_hold']}/{s['tickers_tested']} beat buy-and-hold)"
    )
    table.add_column("Ticker")
    table.add_column("Window")
    table.add_column("Strategy", justify="right")
    table.add_column("Buy & hold", justify="right")
    table.add_column("Edge", justify="right")
    table.add_column("Beats B&H")
    for r in report["results"]:
        table.add_row(
            r["ticker"],
            f"{r['start']} to {r['end']}",
            f"{r['strategy_return']:+.2%}",
            f"{r['buy_and_hold_return']:+.2%}",
            f"{r['edge']:+.2%}",
            "yes" if r["beat_buy_and_hold"] else "no",
        )
    return table


def write_charts(
    tickers: list[str], provider_name: str, output_dir: Path, errors: list[str] | None = None
) -> list[Path]:
    """One liquidity heatmap per ticker that still loads, skipping (and recording) failures."""
    if errors is None:
        errors = []
    paths = []
    for ticker in tickers:
        try:
            df = load(ticker, provider=provider_name)
            paths.append(plot_liquidity_heatmap(df, ticker, output_dir=output_dir))
        except ProviderError as exc:
            errors.append(f"{ticker}: {exc}")
    return paths


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
    parser.add_argument("--no-charts", action="store_true", help="skip writing heatmap PNGs")
    parser.add_argument("--date", default=None, help="override the generated date (mainly for tests)")
    parser.add_argument(
        "--valuation-contract",
        default=None,
        help="v0.7 gate: path to a reverse-dcf-engine --contract JSON file to attach to the "
        "matching candidate (requires --valuation-ticker)",
    )
    parser.add_argument(
        "--valuation-ticker",
        default=None,
        help="the ticker --valuation-contract was solved for",
    )
    parser.add_argument(
        "--risk-contract",
        default=None,
        help="v0.3 gate: path to a monte-carlo-risk-lab --contract JSON file to attach to the "
        "matching candidate (requires --risk-ticker)",
    )
    parser.add_argument(
        "--risk-ticker",
        default=None,
        help="the ticker --risk-contract was solved for",
    )
    parser.add_argument(
        "--factor-contract",
        default=None,
        help="v0.2 gate: path to a fama-french-factor-model --contract JSON file to attach to the "
        "matching candidate (requires --factor-ticker)",
    )
    parser.add_argument(
        "--factor-ticker",
        default=None,
        help="the ticker --factor-contract was solved for",
    )
    args = parser.parse_args(argv)

    if bool(args.valuation_contract) != bool(args.valuation_ticker):
        parser.error("--valuation-contract and --valuation-ticker must be given together")

    if bool(args.risk_contract) != bool(args.risk_ticker):
        parser.error("--risk-contract and --risk-ticker must be given together")

    if bool(args.factor_contract) != bool(args.factor_ticker):
        parser.error("--factor-contract and --factor-ticker must be given together")

    if args.live and args.offline:
        parser.error("--live and --offline are mutually exclusive")

    provider_name = "yfinance" if args.live else "fixtures"
    cfg = load_config(Path(args.config))
    tickers = load_universe(Path(args.universe))
    generated = args.date or date.today().isoformat()

    if not tickers:
        print(f"no tickers in {args.universe}")
        return 1

    console = Console()
    errors: list[str] = []
    screen = build_screen(tickers, provider_name, cfg, "NSE", generated, errors)
    backtest_report = run_backtest(tickers, provider_name, cfg, args.threshold, generated, errors)

    if args.valuation_contract:
        valuation = load_valuation_contract(args.valuation_contract)
        screen, matched = apply_valuation_gate(screen, args.valuation_ticker, valuation)
        if matched:
            console.print(
                f"valuation gate: attached reverse-dcf-engine's contract for {args.valuation_ticker}"
            )
        else:
            console.print(
                f"valuation gate: {args.valuation_ticker} is not in this screen's universe -- no candidate updated"
            )

    if args.risk_contract:
        risk = load_risk_contract(args.risk_contract)
        screen, matched = apply_risk_gate(screen, args.risk_ticker, risk)
        if matched:
            console.print(
                f"risk gate: attached monte-carlo-risk-lab's contract for {args.risk_ticker}"
            )
        else:
            console.print(
                f"risk gate: {args.risk_ticker} is not in this screen's universe -- no candidate updated"
            )

    if args.factor_contract:
        fac = load_factor_contract(args.factor_contract)
        screen, matched = apply_factor_gate(screen, args.factor_ticker, fac)
        if matched:
            console.print(
                f"factor gate: attached fama-french-factor-model's contract for {args.factor_ticker}"
            )
        else:
            console.print(
                f"factor gate: {args.factor_ticker} is not in this screen's universe -- no candidate updated"
            )

    console.print(render_screen_table(screen))
    if backtest_report["results"]:
        console.print(render_backtest_table(backtest_report))

    chart_paths: list[Path] = []
    if not args.no_charts:
        out_dir = Path(args.output_dir)
        chart_paths = write_charts(tickers, provider_name, out_dir, errors)
        for path in chart_paths:
            console.print(f"chart: {path}")

    for e in errors:
        console.print(f"[red]![/red] {e}")

    return 0 if screen["candidates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
