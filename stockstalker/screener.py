"""YAML-configured screener: blend trend/momentum/volume signals into a
ranked candidate list conforming to ``schema/v1.json``.

``config/screen.yaml`` owns the rules — signal parameters, how the three
signal families are weighted, and the liquidity/score gates a candidate
must clear to rank. Changing the screen's behaviour should mean editing
that file, not this one.

Writes three files per run: the JSON contract satellites will read
(``screen_<date>.json``), a CSV for spreadsheet convenience, and a
markdown report — plus a short terminal summary. All three carry the same
ranked candidates.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .data.providers import ProviderError, load
from .signals.momentum import momentum_score
from .signals.trend import trend_score
from .signals.volume import volume_score

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "screen.yaml"
UNIVERSE_PATH = ROOT / "data" / "universe.txt"
OUTPUT_DIR = ROOT / "outputs"

DEFAULT_CONFIG: dict[str, Any] = {
    "weights": {"trend": 0.4, "momentum": 0.35, "volume": 0.25},
    "trend": {"method": "sma", "fast": 20, "slow": 50},
    "momentum": {"rsi_period": 14, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9},
    "volume": {"z_window": 20, "obv_window": 20},
    "filters": {"min_adv_20d": 0, "min_score": 0.0},
}


def load_config(path: Path) -> dict[str, Any]:
    """Read the YAML rules file, falling back to :data:`DEFAULT_CONFIG` section-by-section.

    A config missing a section (or the whole file, past the ``FileNotFoundError``
    guard callers can choose to raise) still produces a working screen — the
    rules file is a knob, not a required ritual.
    """
    raw = yaml.safe_load(path.read_text()) or {}
    merged = {}
    for section, defaults in DEFAULT_CONFIG.items():
        section_value = raw.get(section)
        if isinstance(defaults, dict):
            merged[section] = {**defaults, **(section_value or {})}
        else:
            merged[section] = section_value if section_value is not None else defaults
    return merged


def load_universe(path: Path) -> list[str]:
    """One ticker per non-blank, non-comment line."""
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def compute_signals(df, cfg: dict[str, Any]) -> dict[str, float]:
    """The three [-1, 1] signal components this ticker's row will carry."""
    t_cfg, m_cfg, v_cfg = cfg["trend"], cfg["momentum"], cfg["volume"]
    return {
        "trend": trend_score(df, fast=t_cfg["fast"], slow=t_cfg["slow"], method=t_cfg["method"]),
        "momentum": momentum_score(
            df["close"],
            rsi_period=m_cfg["rsi_period"],
            macd_fast=m_cfg["macd_fast"],
            macd_slow=m_cfg["macd_slow"],
            macd_signal=m_cfg["macd_signal"],
        ),
        "volume": volume_score(
            df["close"], df["volume"], z_window=v_cfg["z_window"], obv_window=v_cfg["obv_window"]
        ),
    }


def blended_score(signals: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted average of the [-1, 1] signals, mapped into the contract's [0, 1] score.

    Weights are normalised by their own total, so ``{trend: 2, momentum: 2,
    volume: 1}`` behaves the same as ``{trend: 0.4, momentum: 0.4, volume: 0.2}``.
    A zero total (every weight zero) falls back to an equal blend rather than
    dividing by zero.
    """
    total = sum(weights.get(k, 0.0) for k in signals)
    if total == 0:
        blend = sum(signals.values()) / len(signals)
    else:
        blend = sum(signals[k] * weights.get(k, 0.0) for k in signals) / total
    return round(min(max((blend + 1) / 2, 0.0), 1.0), 4)


def liquidity_metrics(df, window: int = 20) -> dict[str, float]:
    """20-day average daily volume and average traded value, from the most recent bars."""
    tail = df.tail(window)
    return {
        "adv_20d": round(float(tail["volume"].mean()), 2),
        "turnover_20d": round(float((tail["close"] * tail["volume"]).mean()), 2),
    }


def screen_ticker(ticker: str, provider_name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    df = load(ticker, provider=provider_name)
    signals = compute_signals(df, cfg)
    return {
        "ticker": ticker,
        "score": blended_score(signals, cfg["weights"]),
        "signals": {k: round(v, 4) for k, v in signals.items()},
        "liquidity": liquidity_metrics(df),
    }


def apply_filters(candidates: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Drop candidates that fail the configured liquidity or score gate."""
    min_adv = filters.get("min_adv_20d", 0)
    min_score = filters.get("min_score", 0.0)
    return [
        c
        for c in candidates
        if c["liquidity"]["adv_20d"] >= min_adv and c["score"] >= min_score
    ]


def rank(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by score descending and stamp a 1-based rank in place."""
    ranked = sorted(candidates, key=lambda c: c["score"], reverse=True)
    for i, c in enumerate(ranked, start=1):
        c["rank"] = i
    return ranked


def build_screen(
    tickers: list[str],
    provider_name: str,
    cfg: dict[str, Any],
    universe_name: str,
    generated: str,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """Screen every ticker, dropping (and recording) the ones that fail to fetch."""
    if errors is None:
        errors = []
    candidates = []
    for ticker in tickers:
        try:
            candidates.append(screen_ticker(ticker, provider_name, cfg))
        except ProviderError as exc:
            errors.append(f"{ticker}: {exc}")
    ranked = rank(apply_filters(candidates, cfg["filters"]))
    return {
        "schema": "v1",
        "generated": generated,
        "universe": universe_name,
        "source": provider_name,
        "candidates": ranked,
    }


def write_json(screen: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(screen, indent=2) + "\n")


def write_csv(screen: dict[str, Any], path: Path) -> None:
    fieldnames = ["rank", "ticker", "score", "trend", "momentum", "volume", "adv_20d", "turnover_20d"]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for c in screen["candidates"]:
            writer.writerow(
                {
                    "rank": c["rank"],
                    "ticker": c["ticker"],
                    "score": c["score"],
                    "trend": c["signals"]["trend"],
                    "momentum": c["signals"]["momentum"],
                    "volume": c["signals"]["volume"],
                    "adv_20d": c["liquidity"]["adv_20d"],
                    "turnover_20d": c["liquidity"]["turnover_20d"],
                }
            )


def _markdown_table(screen: dict[str, Any]) -> str:
    header = "| Rank | Ticker | Score | Trend | Momentum | Volume | ADV(20d) |"
    sep = "|------|--------|-------|-------|----------|--------|----------|"
    rows = [header, sep]
    for c in screen["candidates"]:
        s = c["signals"]
        rows.append(
            f"| {c['rank']} | {c['ticker']} | {c['score']:.4f} | {s['trend']:.4f} "
            f"| {s['momentum']:.4f} | {s['volume']:.4f} | {c['liquidity']['adv_20d']:,.0f} |"
        )
    return "\n".join(rows)


def write_markdown(screen: dict[str, Any], errors: list[str], path: Path) -> None:
    lines = [
        f"# Screen — {screen['generated']}",
        "",
        f"Universe: {screen['universe']} · source: {screen['source']} · "
        f"{len(screen['candidates'])} candidate(s)",
        "",
        "Technical signals describe how a price has behaved, not what a business is "
        "worth. This is a shortlist for research, not a recommendation.",
        "",
    ]
    if screen["candidates"]:
        lines.append(_markdown_table(screen))
    else:
        lines.append("No candidates cleared the configured filters.")
    if errors:
        lines += ["", "## Fetch errors", ""]
        lines += [f"- {e}" for e in errors]
    path.write_text("\n".join(lines) + "\n")


def print_report(screen: dict[str, Any], errors: list[str]) -> None:
    print(f"Screen {screen['generated']} — universe {screen['universe']} ({screen['source']})")
    if not screen["candidates"]:
        print("  no candidates cleared the configured filters")
    for c in screen["candidates"]:
        s = c["signals"]
        print(
            f"  {c['rank']:>2}. {c['ticker']:<14} score {c['score']:.4f}  "
            f"trend {s['trend']:+.3f}  momentum {s['momentum']:+.3f}  volume {s['volume']:+.3f}  "
            f"adv20 {c['liquidity']['adv_20d']:,.0f}"
        )
    for e in errors:
        print(f"  ! {e}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(CONFIG_PATH), help="YAML rules file")
    parser.add_argument("--universe", default=str(UNIVERSE_PATH), help="ticker list, one per line")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
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
    screen = build_screen(tickers, provider_name, cfg, "NSE", generated, errors)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(screen, out_dir / f"screen_{generated}.json")
    write_csv(screen, out_dir / f"screen_{generated}.csv")
    write_markdown(screen, errors, out_dir / f"screen_{generated}.md")

    print_report(screen, errors)
    return 0 if screen["candidates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
