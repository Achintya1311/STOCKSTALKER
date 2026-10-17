"""Front door, Day 1: one ticker, everything the pipeline knows about it.

``python -m stockstalker.run --ticker GULFOILLUB --offline`` prints a price
section for the subject plus a peer comparison table, and writes the same
as a markdown tear sheet to ``outputs/``.

The price section reuses the screen's own scoring -- ``screener.compute_signals``,
``screener.blended_score`` and ``screener.liquidity_metrics`` -- rather than
deriving new signal math, so a subject's trend/momentum/volume numbers here
are provably the same computation the daily screen would produce if the
ticker were in ``data/universe.txt`` (it deliberately is not; see the
Traps section of this project's NEXT_STEPS.md).

Trailing 1-year return and annualised volatility, used only for the peer
table, are new here -- the screen has no notion of either. Both fall back
to ``None`` ("n/a") when a fixture does not yet hold a full year of bars,
rather than reporting a shorter-window number under a "1y" heading.

Contract sections (Day 2) read each satellite's own ``--contract`` file
directly for the subject ticker -- ``fixtures/<namespace>/<TICKER>.json`` --
through that namespace's existing ``gates.<namespace>.load_contract``,
rather than through the screen-gate pattern those modules were built for
(which only attaches a contract when the ticker is already a candidate in
today's screen output, keyed off ``data/universe.txt``; the subject is
deliberately not in that universe, so that pattern would never match it).
A namespace with no fixture file for the subject, or a malformed one,
renders one explicit "not available" line instead of silently omitting
the section or standing in a contract for a different ticker.

``sizing`` is deliberately left out: markowitz-portfolio-optimizer's
sector-capped weight is a position size *within a screened universe of
candidates*, and a sector-capped weight across the subject plus its three
lubricant peers would be a sector bet dressed up as a position size, not
a number anyone should act on. See NEXT_STEPS.md Day 2.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .data.providers import ProviderError, load
from .gates import factor as gate_factor
from .gates import fundamentals as gate_fundamentals
from .gates import risk as gate_risk
from .gates import sentiment as gate_sentiment
from .gates import valuation as gate_valuation
from .gates import vol as gate_vol
from .screener import CONFIG_PATH, blended_score, compute_signals, liquidity_metrics, load_config
from .viz import charts as viz_charts

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"
FIXTURES_DIR = ROOT / "fixtures"

TRADING_DAYS_PER_YEAR = 252

# (namespace, gate module, the satellite repo that publishes it) in the
# order NEXT_STEPS.md Day 2 lists them. ``sizing`` is excluded on purpose --
# see the module docstring.
CONTRACT_NAMESPACES: list[tuple[str, Any, str]] = [
    ("valuation", gate_valuation, "reverse-dcf-engine"),
    ("fundamentals", gate_fundamentals, "three-statement-model"),
    ("risk", gate_risk, "monte-carlo-risk-lab"),
    ("factor", gate_factor, "fama-french-factor-model"),
    ("vol", gate_vol, "implied-vol-surface"),
    ("sentiment", gate_sentiment, "headline-sentiment-vs-price"),
]

# Lubricant-sector peers for GULFOILLUB, the subject this project is built
# around (NEXT_STEPS.md, "already committed for this project"). Sourced from
# reverse-dcf-engine/fixtures/peers/lubricants.csv, duplicated as a plain
# constant here rather than read from that repo at runtime -- satellites
# talk to the spine through files it reads deliberately, never by reaching
# into another repo's working tree.
DEFAULT_PEERS = ["CASTROLIND", "SOTL", "GANDHAR"]


def to_yf_ticker(ticker: str) -> str:
    """Bare NSE symbol to the yfinance-suffixed form the data providers key on."""
    ticker = ticker.upper().strip()
    return ticker if ticker.endswith(".NS") else f"{ticker}.NS"


def trailing_return(df, window: int = TRADING_DAYS_PER_YEAR) -> float | None:
    """Price return over the trailing ``window`` trading days.

    ``None`` when the fixture does not hold ``window + 1`` bars yet --
    never a shorter-window number reported under the same heading.
    """
    if len(df) < window + 1:
        return None
    start = float(df["close"].iloc[-(window + 1)])
    end = float(df["close"].iloc[-1])
    return round(end / start - 1, 4)


def trailing_volatility(df, window: int = TRADING_DAYS_PER_YEAR) -> float | None:
    """Annualised stdev of daily returns over the trailing ``window`` trading days."""
    if len(df) < window + 1:
        return None
    daily_returns = df["close"].pct_change().iloc[-window:]
    return round(float(daily_returns.std(ddof=1) * (TRADING_DAYS_PER_YEAR**0.5)), 4)


def build_subject_section(ticker: str, provider_name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Price section for the subject: the screen's own signals, score and liquidity."""
    df = load(to_yf_ticker(ticker), provider=provider_name)
    signals = compute_signals(df, cfg)
    return {
        "ticker": ticker.upper(),
        "as_of": df.index[-1].date().isoformat(),
        "close": round(float(df["close"].iloc[-1]), 4),
        "score": blended_score(signals, cfg["weights"]),
        "signals": {k: round(v, 4) for k, v in signals.items()},
        "liquidity": liquidity_metrics(df),
    }


def build_peer_table(
    tickers: list[str], provider_name: str, errors: list[str] | None = None
) -> list[dict[str, Any]]:
    """One row per ticker: trailing 1y return, 1y annualised volatility, 20d ADV.

    A ticker whose fixture fails to load is skipped and recorded in
    ``errors``, not silently dropped.
    """
    if errors is None:
        errors = []
    rows = []
    for ticker in tickers:
        try:
            df = load(to_yf_ticker(ticker), provider=provider_name)
        except ProviderError as exc:
            errors.append(f"{ticker}: {exc}")
            continue
        rows.append(
            {
                "ticker": ticker.upper(),
                "return_1y": trailing_return(df),
                "volatility_1y": trailing_volatility(df),
                "adv_20d": liquidity_metrics(df)["adv_20d"],
            }
        )
    return rows


def write_charts(
    subject_ticker: str,
    peer_tickers: list[str],
    provider_name: str,
    output_dir: Path,
    errors: list[str] | None = None,
) -> list[Path]:
    """Day 7: rebased comparison, subject drawdown, subject rolling volatility.

    A ticker (subject or peer) whose fixture fails to load is skipped and
    recorded in ``errors``, the same shape ``build_peer_table`` already
    uses -- never silently dropped. The subject must load for any chart to
    be produced; a peer failing only shrinks the rebased comparison.
    """
    if errors is None:
        errors = []
    frames: dict[str, Any] = {}
    for ticker in [subject_ticker, *peer_tickers]:
        yf_ticker = to_yf_ticker(ticker)
        try:
            frames[ticker.upper()] = load(yf_ticker, provider=provider_name)
        except ProviderError as exc:
            errors.append(f"{ticker}: {exc}")

    subject = subject_ticker.upper()
    if subject not in frames:
        return []

    paths = [viz_charts.plot_rebased_comparison(frames, subject, output_dir=output_dir)]
    paths.append(viz_charts.plot_drawdown(frames[subject], subject, output_dir=output_dir))
    paths.append(viz_charts.plot_rolling_volatility(frames[subject], subject, output_dir=output_dir))
    return paths


def _fmt_pct(value: float | None) -> str:
    return f"{value:+.2%}" if value is not None else "n/a"


def _fmt_scalar(value: Any) -> str:
    """Render one contract field for both the terminal table and the tear sheet."""
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:+.4f}"
    if isinstance(value, dict):
        return ", ".join(f"{k}={_fmt_scalar(v)}" for k, v in value.items())
    return str(value)


# Day 5 (D2): NSE's own F&O lot-size snapshot -- whether a missing vol
# fixture means "not an F&O underlying at all" (a real, checkable fact) or
# just "not built yet" used to be undecidable from this sandbox, because
# the live NSE option-chain endpoint returned the same empty/blocked
# payload for GULFOILLUB as it did for RELIANCE, a name known to have
# listed options (see implied-vol-surface's README Findings, 2026-10-12).
# fo_mktlots.csv settles it without touching that endpoint at all.
FO_MKTLOTS_PATH = ROOT / "fixtures" / "fo_mktlots.csv"
FO_MKTLOTS_META_PATH = ROOT / "fixtures" / "fo_mktlots_meta.json"


def load_fo_underlyings(path: Path = FO_MKTLOTS_PATH) -> set[str]:
    """NSE F&O underlying symbols (stock and index) from the lot-size snapshot.

    ``fo_mktlots.csv`` is NSE's own export: one header row, then the index
    derivatives (NIFTY, BANKNIFTY, ...) before the per-stock rows -- both
    kinds belong in the result, since the only question this answers is
    "is this symbol an F&O underlying at all". Every field is fixed-width
    space-padded, so each value is stripped after the plain comma split.
    """
    symbols: set[str] = set()
    with Path(path).open(newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header row
        for row in reader:
            if len(row) < 2:
                continue
            symbol = row[1].strip()
            if symbol:
                symbols.add(symbol.upper())
    return symbols


def fo_mktlots_list_date(meta_path: Path = FO_MKTLOTS_META_PATH) -> str:
    """The snapshot's own effective date (NSE's Last-Modified at capture time)."""
    try:
        meta = json.loads(Path(meta_path).read_text())
        return meta["list_last_modified"]
    except (OSError, KeyError, json.JSONDecodeError):
        return "unknown"


def _vol_unavailable_reason(ticker: str, source_repo: str, path: Path) -> str:
    """A missing vol fixture is "no listed options" only once fo_mktlots.csv
    actually says the ticker is not an F&O underlying; otherwise it is the
    same generic "not built yet" reason every other namespace uses.
    """
    try:
        underlyings = load_fo_underlyings()
    except OSError:
        underlyings = None
    if underlyings is not None and ticker.upper() not in underlyings:
        return (
            f"no listed options: not an NSE F&O underlying "
            f"(fo_mktlots.csv, list dated {fo_mktlots_list_date()})"
        )
    return f"no {source_repo} contract fixture for {ticker.upper()} ({path.relative_to(ROOT)} not found)"


def build_contract_section(
    namespace: str, gate_module: Any, source_repo: str, ticker: str, fixtures_dir: Path
) -> dict[str, Any]:
    """Read ``fixtures/<namespace>/<TICKER>.json`` for ``ticker`` through ``gate_module.load_contract``.

    Looks the fixture up by ticker directly -- never through a screen-gate's
    ``apply_*_gate``, which only matches a candidate already in
    ``data/universe.txt`` (see the module docstring's Traps note). Returns
    an "available" section with the contract's own fields, or an
    "unavailable" section with a one-line reason: no fixture committed for
    this ticker yet, the fixture failed its gate's own validation, or (vol
    only, see ``_vol_unavailable_reason``) the ticker has no listed options
    at all per NSE's own lot-size list.
    """
    path = fixtures_dir / namespace / f"{ticker.upper()}.json"
    if not path.exists():
        if namespace == "vol":
            reason = _vol_unavailable_reason(ticker, source_repo, path)
        else:
            reason = f"no {source_repo} contract fixture for {ticker.upper()} ({path.relative_to(ROOT)} not found)"
        return {
            "namespace": namespace,
            "available": False,
            "reason": reason,
        }
    try:
        data = gate_module.load_contract(path)
    except (ValueError, json.JSONDecodeError) as exc:
        return {"namespace": namespace, "available": False, "reason": str(exc)}
    return {"namespace": namespace, "available": True, "source": source_repo, "data": data}


def build_contract_sections(ticker: str, fixtures_dir: Path | None = None) -> list[dict[str, Any]]:
    fixtures_dir = fixtures_dir or FIXTURES_DIR
    return [
        build_contract_section(namespace, gate_module, source_repo, ticker, fixtures_dir)
        for namespace, gate_module, source_repo in CONTRACT_NAMESPACES
    ]


# R7: the one line explaining why `sizing` never appears in CONTRACT_NAMESPACES
# at all -- shared verbatim between the console and the tear sheet so the two
# can't drift apart.
SIZING_EXCLUSION_NOTE = (
    "is left out on purpose: a sector-capped weight across the subject and "
    "its three lubricant peers is a sector bet, not a position size (NEXT_STEPS.md Day 2)."
)


def contract_section_note(section: dict[str, Any], ticker: str) -> str | None:
    """A one-line caveat for this contract section, beyond its own fields (R5, R6)."""
    namespace = section["namespace"]
    if namespace == "risk":
        return gate_risk.kupiec_note(ticker, section.get("data"))
    if namespace == "factor":
        return gate_factor.method_label(ticker)
    return None


def render_contract_section(section: dict[str, Any]) -> Table | str:
    if not section["available"]:
        return f"[yellow]·[/yellow] {section['namespace']}: not available -- {section['reason']}"
    table = Table(title=f"{section['namespace']} (via {section['source']})")
    table.add_column("Field")
    table.add_column("Value", justify="right")
    for key, value in section["data"].items():
        if section["namespace"] == "factor" and key == "significant":
            value = gate_factor.significance_label(value)
        table.add_row(key, _fmt_scalar(value))
    return table


def contract_sections_markdown(sections: list[dict[str, Any]], ticker: str) -> list[str]:
    lines = ["## Contract sections", ""]
    for section in sections:
        lines.append(f"### {section['namespace'].capitalize()}")
        lines.append("")
        if not section["available"]:
            lines.append(f"Not available -- {section['reason']}")
        else:
            lines.append(f"Via `{section['source']}`.")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            for key, value in section["data"].items():
                if section["namespace"] == "factor" and key == "significant":
                    value = gate_factor.significance_label(value)
                lines.append(f"| {key} | {_fmt_scalar(value)} |")
        note = contract_section_note(section, ticker)
        if note:
            lines.append("")
            lines.append(f"> {note}")
        lines.append("")
    lines.append(f"`sizing` {SIZING_EXCLUSION_NOTE}")
    lines.append("")
    return lines


def render_subject_table(subject: dict[str, Any]) -> Table:
    table = Table(title=f"{subject['ticker']} — {subject['as_of']} (close {subject['close']:,.2f})")
    table.add_column("Score", justify="right")
    table.add_column("Trend", justify="right")
    table.add_column("Momentum", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("ADV(20d)", justify="right")
    s = subject["signals"]
    table.add_row(
        f"{subject['score']:.4f}",
        f"{s['trend']:+.3f}",
        f"{s['momentum']:+.3f}",
        f"{s['volume']:+.3f}",
        f"{subject['liquidity']['adv_20d']:,.0f}",
    )
    return table


def render_peer_table(rows: list[dict[str, Any]]) -> Table:
    table = Table(title="Peer comparison")
    table.add_column("Ticker")
    table.add_column("Return (1y)", justify="right")
    table.add_column("Volatility (1y, ann.)", justify="right")
    table.add_column("ADV(20d)", justify="right")
    for r in rows:
        table.add_row(
            r["ticker"],
            _fmt_pct(r["return_1y"]),
            _fmt_pct(r["volatility_1y"]),
            f"{r['adv_20d']:,.0f}",
        )
    return table


def write_tearsheet(
    subject: dict[str, Any],
    peer_rows: list[dict[str, Any]],
    generated: str,
    path: Path,
    contract_sections: list[dict[str, Any]] | None = None,
    chart_paths: list[Path] | None = None,
) -> None:
    s = subject["signals"]
    lines = [
        f"# Tear sheet — {subject['ticker']} ({generated})",
        "",
        f"Close {subject['close']:,.2f} as of {subject['as_of']}. Score {subject['score']:.4f} "
        f"(trend {s['trend']:+.3f}, momentum {s['momentum']:+.3f}, volume {s['volume']:+.3f}), "
        f"ADV(20d) {subject['liquidity']['adv_20d']:,.0f}.",
        "",
        "Technical signals describe how the price has behaved, not what the business is "
        "worth. This section reuses the screen's own scoring; the subject is not in "
        "`data/universe.txt` and this run does not add it there.",
        "",
        "## Peer comparison",
        "",
        "| Ticker | Return (1y) | Volatility (1y, ann.) | ADV(20d) |",
        "|--------|-------------|------------------------|----------|",
    ]
    for r in peer_rows:
        lines.append(
            f"| {r['ticker']} | {_fmt_pct(r['return_1y'])} | {_fmt_pct(r['volatility_1y'])} "
            f"| {r['adv_20d']:,.0f} |"
        )
    lines += ["", *contract_sections_markdown(contract_sections or [], subject["ticker"])]
    if chart_paths:
        lines += ["## Charts", ""]
        for chart_path in chart_paths:
            lines.append(f"- `{chart_path.name}`")
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ticker", default="GULFOILLUB", help="subject ticker, no .NS suffix")
    parser.add_argument(
        "--peers",
        default=",".join(DEFAULT_PEERS),
        help="comma-separated peer tickers, no .NS suffix",
    )
    parser.add_argument("--config", default=str(CONFIG_PATH), help="YAML rules file")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument(
        "--live", action="store_true", help="fetch via yfinance instead of committed fixtures"
    )
    parser.add_argument(
        "--offline", action="store_true", help="explicit fixtures path (already the default)"
    )
    parser.add_argument("--date", default=None, help="override the generated date (mainly for tests)")
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="skip writing the rebased/drawdown/volatility PNGs",
    )
    args = parser.parse_args(argv)

    if args.live and args.offline:
        parser.error("--live and --offline are mutually exclusive")

    provider_name = "yfinance" if args.live else "fixtures"
    cfg = load_config(Path(args.config))
    peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    generated = args.date or date.today().isoformat()

    console = Console()
    errors: list[str] = []

    try:
        subject = build_subject_section(args.ticker, provider_name, cfg)
    except ProviderError as exc:
        console.print(f"[red]![/red] {args.ticker}: {exc}")
        return 1

    peer_rows = build_peer_table([args.ticker, *peers], provider_name, errors)
    contract_sections = build_contract_sections(args.ticker)

    console.print(render_subject_table(subject))
    console.print(render_peer_table(peer_rows))
    for section in contract_sections:
        console.print(render_contract_section(section))
        note = contract_section_note(section, args.ticker)
        if note:
            console.print(f"  [dim]{note}[/dim]")
    console.print(f"[dim]· sizing {SIZING_EXCLUSION_NOTE}[/dim]")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chart_paths: list[Path] = []
    if not args.no_charts:
        chart_paths = write_charts(args.ticker, peers, provider_name, out_dir, errors)
        for chart_path in chart_paths:
            console.print(f"chart: {chart_path}")

    for e in errors:
        console.print(f"[red]![/red] {e}")

    tearsheet_path = out_dir / f"tearsheet_{subject['ticker']}_{generated}.md"
    write_tearsheet(subject, peer_rows, generated, tearsheet_path, contract_sections, chart_paths)
    console.print(f"tear sheet: {tearsheet_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
