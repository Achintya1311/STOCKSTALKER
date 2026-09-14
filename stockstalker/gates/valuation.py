"""v0.7 -- valuation gate on survivors.

reverse-dcf-engine publishes one company's valuation as a file, not a Python
object: ``{"valuation": {"implied_cagr", "implied_ebit_margin",
"implied_reinvestment", "breakeven_growth"}}`` (see that repo's
``reverse_dcf.solve.ReverseDcfResult.to_contract`` and its ``--contract`` CLI
flag). This module reads that file and attaches it to the one candidate in a
``schema/v1.json`` screen output whose ticker matches, under the ``valuation``
key schema/v1.json already reserves for it.

Communication stays by file: this module never imports ``reverse_dcf``, and
nothing here fails if the satellite's researched ticker is outside today's
screened universe -- the two repos build their fixture sets independently, so
a screen with no matching candidate is an expected, reported outcome, not an
error.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_VALUATION_KEYS = {
    "implied_cagr",
    "implied_ebit_margin",
    "implied_reinvestment",
    "breakeven_growth",
}


def load_contract(path: str | Path) -> dict[str, float]:
    """Read and validate a reverse-dcf-engine ``--contract`` JSON file."""
    raw = json.loads(Path(path).read_text())
    valuation = raw.get("valuation")
    if not isinstance(valuation, dict):
        raise ValueError(f"{path}: no 'valuation' object at the top level")
    missing = REQUIRED_VALUATION_KEYS - set(valuation)
    if missing:
        raise ValueError(f"{path}: valuation block missing keys: {sorted(missing)}")
    return valuation


def _normalize_ticker(ticker: str) -> str:
    """NSE names show up with (this repo) and without (reverse-dcf-engine) the yfinance '.NS' suffix."""
    return ticker.upper().removesuffix(".NS")


def apply_valuation_gate(screen: dict[str, Any], ticker: str, valuation: dict[str, float]) -> dict[str, Any]:
    """Return a copy of ``screen`` with ``valuation`` attached to the candidate matching ``ticker``.

    Every other candidate passes through unchanged. Returns the screen dict
    unchanged (aside from the copy) plus a bool the caller can report on.
    """
    target = _normalize_ticker(ticker)
    gated_candidates = []
    matched = False
    for candidate in screen["candidates"]:
        candidate = dict(candidate)
        if _normalize_ticker(candidate["ticker"]) == target:
            candidate["valuation"] = dict(valuation)
            matched = True
        gated_candidates.append(candidate)
    gated = dict(screen)
    gated["candidates"] = gated_candidates
    return gated, matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screen", required=True, help="path to a schema/v1.json-shaped screen output")
    parser.add_argument("--contract", required=True, help="path to reverse-dcf-engine's --contract JSON output")
    parser.add_argument("--ticker", required=True, help="the ticker that contract was solved for")
    parser.add_argument("--out", default=None, help="defaults to overwriting --screen in place")
    args = parser.parse_args(argv)

    screen = json.loads(Path(args.screen).read_text())
    valuation = load_contract(args.contract)
    gated, matched = apply_valuation_gate(screen, args.ticker, valuation)

    out_path = Path(args.out) if args.out else Path(args.screen)
    out_path.write_text(json.dumps(gated, indent=2) + "\n")

    if matched:
        print(f"valuation gate: attached reverse-dcf-engine's contract for {args.ticker} to 1 candidate -> {out_path}")
    else:
        print(
            f"valuation gate: {args.ticker} is not in this screen's universe -- "
            f"no candidate updated, {out_path} written unchanged"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
