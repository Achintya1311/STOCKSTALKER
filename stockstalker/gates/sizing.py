"""v0.4 -- optimizer-driven position sizing on the screen.

markowitz-portfolio-optimizer publishes one ticker's sector-capped,
Ledoit-Wolf-shrunk max-Sharpe position size as a file, not a Python object:
``{"sizing": {"weight", "method", "constraint_binding"}}`` (see that repo's
``optimizer.sizing.to_contract`` and its ``--contract`` CLI flag). This
module reads that file and attaches it to the one candidate in a
``schema/v1.json`` screen output whose ticker matches, under the ``sizing``
key schema/v1.json already reserves for it.

Communication stays by file: this module never imports ``optimizer``, and
nothing here fails if the satellite's researched ticker is outside today's
screened universe -- the two repos build their fixture sets independently,
so a screen with no matching candidate is an expected, reported outcome,
not an error.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..disclaimer import DISCLAIMER

REQUIRED_SIZING_KEYS = {
    "weight",
    "method",
    "constraint_binding",
}


def load_contract(path: str | Path) -> dict[str, Any]:
    """Read and validate a markowitz-portfolio-optimizer ``--contract`` JSON file."""
    raw = json.loads(Path(path).read_text())
    sizing = raw.get("sizing")
    if not isinstance(sizing, dict):
        raise ValueError(f"{path}: no 'sizing' object at the top level")
    missing = REQUIRED_SIZING_KEYS - set(sizing)
    if missing:
        raise ValueError(f"{path}: sizing block missing keys: {sorted(missing)}")
    return sizing


def _normalize_ticker(ticker: str) -> str:
    """NSE names show up with (this repo) and without (markowitz-portfolio-optimizer) the yfinance '.NS' suffix."""
    return ticker.upper().removesuffix(".NS")


def apply_sizing_gate(screen: dict[str, Any], ticker: str, sizing: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return a copy of ``screen`` with ``sizing`` attached to the candidate matching ``ticker``.

    Every other candidate passes through unchanged. Returns the screen dict
    unchanged (aside from the copy) plus a bool the caller can report on.
    """
    target = _normalize_ticker(ticker)
    gated_candidates = []
    matched = False
    for candidate in screen["candidates"]:
        candidate = dict(candidate)
        if _normalize_ticker(candidate["ticker"]) == target:
            candidate["sizing"] = dict(sizing)
            matched = True
        gated_candidates.append(candidate)
    gated = dict(screen)
    gated["candidates"] = gated_candidates
    return gated, matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screen", required=True, help="path to a schema/v1.json-shaped screen output")
    parser.add_argument("--contract", required=True, help="path to markowitz-portfolio-optimizer's --contract JSON output")
    parser.add_argument("--ticker", required=True, help="the ticker that contract was solved for")
    parser.add_argument("--out", default=None, help="defaults to overwriting --screen in place")
    args = parser.parse_args(argv)

    screen = json.loads(Path(args.screen).read_text())
    sizing = load_contract(args.contract)
    gated, matched = apply_sizing_gate(screen, args.ticker, sizing)

    out_path = Path(args.out) if args.out else Path(args.screen)
    out_path.write_text(json.dumps(gated, indent=2) + "\n")

    if matched:
        print(f"sizing gate: attached markowitz-portfolio-optimizer's contract for {args.ticker} to 1 candidate -> {out_path}")
    else:
        print(
            f"sizing gate: {args.ticker} is not in this screen's universe -- "
            f"no candidate updated, {out_path} written unchanged"
        )
    print(DISCLAIMER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
