"""Day 9: pipeline audit for look-ahead bias in the signal library.

Every score this project produces is a snapshot: "as of this bar's close,
what does the indicator say." That snapshot is only honest if the function
computing it never reaches past the bar it is being asked about. A rolling
mean is causal by construction; a centred rolling mean, or a shift in the
wrong direction, is not — and either would silently let today's screen
"see" tomorrow's close.

This module checks that mechanically rather than by inspection: for each
indicator, the value it reports for bar *i* on the full series must be
identical to the value it reports for bar *i* when every bar after *i* is
simply not there yet. If truncating the future ever changes a past value,
the function is not causal and the audit fails.

This is a structural check, not a statistical one. It cannot tell you
whether the screen's thresholds are well chosen — see the backtest and the
README limitations section for that — only that the numbers feeding them
were computed without peeking.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .data.providers import load
from .screener import CONFIG_PATH, UNIVERSE_PATH, load_config, load_universe
from .signals.momentum import macd, rsi
from .signals.trend import ema, sma
from .signals.volume import obv, volume_zscore

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"

# Sample every Nth bar rather than every bar - the check is O(n) calls to the
# indicator per sample, and every bar would make this O(n^2) for no extra
# confidence once a periodic sample already spans burn-in, mid-series and
# tail behaviour.
SAMPLE_STRIDE = 15


def causality_violations(
    name: str, series_fn: Callable[[pd.DataFrame], pd.Series], df: pd.DataFrame, min_index: int = 0
) -> list[str]:
    """Bars where truncating the series after bar i changes bar i's value.

    ``series_fn`` takes the OHLCV frame and returns a series aligned to its
    index (an indicator over the whole history). Compares that series
    computed on the full frame against the same series recomputed on a
    frame that ends at bar ``i``, for a sample of bars from ``min_index``
    onward. Returns one message per bar where the two disagree; an empty
    list means no look-ahead was detected for this indicator.
    """
    full = series_fn(df)
    violations = []
    for i in range(min_index, len(df), SAMPLE_STRIDE):
        truncated = series_fn(df.iloc[: i + 1])
        full_value = full.iloc[i]
        truncated_value = truncated.iloc[-1]
        both_nan = pd.isna(full_value) and pd.isna(truncated_value)
        if not both_nan and not _close_enough(full_value, truncated_value):
            violations.append(
                f"{name}: bar {i} ({df.index[i].date()}) = {full_value!r} on the full "
                f"series but {truncated_value!r} truncated at that bar - depends on data "
                "that had not happened yet"
            )
    return violations


def _close_enough(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def indicator_checks(df: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Callable[[pd.DataFrame], pd.Series]]:
    """The time-series-valued functions the screen and backtest depend on.

    One entry per indicator actually wired into ``signals/`` and consumed by
    ``screener.compute_signals`` - if a new indicator joins that blend
    without an entry here, it runs unaudited.
    """
    t_cfg, m_cfg, v_cfg = cfg["trend"], cfg["momentum"], cfg["volume"]
    return {
        "sma(fast)": lambda frame: sma(frame["close"], t_cfg["fast"]),
        "sma(slow)": lambda frame: sma(frame["close"], t_cfg["slow"]),
        "ema(fast)": lambda frame: ema(frame["close"], t_cfg["fast"]),
        "rsi": lambda frame: rsi(frame["close"], m_cfg["rsi_period"]),
        "macd.histogram": lambda frame: macd(
            frame["close"], m_cfg["macd_fast"], m_cfg["macd_slow"], m_cfg["macd_signal"]
        )["histogram"],
        "obv": lambda frame: obv(frame["close"], frame["volume"]),
        "volume_zscore": lambda frame: volume_zscore(frame["volume"], v_cfg["z_window"]),
    }


def audit_ticker(ticker: str, provider_name: str, cfg: dict[str, Any]) -> list[str]:
    df = load(ticker, provider=provider_name)
    violations = []
    for name, fn in indicator_checks(df, cfg).items():
        violations += causality_violations(f"{ticker}:{name}", fn, df)
    return violations


def run_audit(tickers: list[str], provider_name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    findings: dict[str, list[str]] = {}
    errors: list[str] = []
    for ticker in tickers:
        try:
            violations = audit_ticker(ticker, provider_name, cfg)
        except Exception as exc:  # noqa: BLE001 - a fetch failure is a data problem, not an audit failure
            errors.append(f"{ticker}: {exc}")
            continue
        if violations:
            findings[ticker] = violations
    return {
        "tickers_checked": len(tickers) - len(errors),
        "clean": not findings,
        "findings": findings,
        "errors": errors,
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"Pipeline audit - {report['tickers_checked']} ticker(s) checked for look-ahead bias")
    if report["clean"]:
        print("  no look-ahead detected: every indicator's value at bar i survives truncation at bar i")
    for ticker, violations in report["findings"].items():
        print(f"  {ticker}: {len(violations)} violation(s)")
        for v in violations:
            print(f"    - {v}")
    for e in report["errors"]:
        print(f"  ! {e}")


def write_markdown(report: dict[str, Any], path: Path, generated: str) -> None:
    lines = [
        f"# Pipeline audit — {generated}",
        "",
        "Checks that every indicator feeding the screen and the backtest is "
        "causal: its value for bar *i* must not change when bars after *i* "
        "are not yet in the frame. This is a structural check for "
        "look-ahead bias, not a statistical claim about the strategy - see "
        "the backtest section and Limitations for that.",
        "",
        f"**{report['tickers_checked']}** ticker(s) checked. "
        f"**{'clean' if report['clean'] else 'violations found'}**.",
        "",
    ]
    if report["findings"]:
        lines.append("## Violations")
        lines.append("")
        for ticker, violations in report["findings"].items():
            lines.append(f"### {ticker}")
            lines += [f"- {v}" for v in violations]
            lines.append("")
    if report["errors"]:
        lines.append("## Errors")
        lines += [f"- {e}" for e in report["errors"]]
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--universe", default=str(UNIVERSE_PATH))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--live", action="store_true", help="fetch via yfinance instead of committed fixtures")
    parser.add_argument("--offline", action="store_true", help="explicit fixtures path (already the default)")
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

    report = run_audit(tickers, provider_name, cfg)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_markdown(report, out_dir / f"audit_{generated}.md", generated)

    print_report(report)
    return 0 if report["clean"] and report["tickers_checked"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
