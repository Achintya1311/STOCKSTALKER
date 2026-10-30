"""v0.8 -- fundamental quality gate on survivors.

three-statement-model publishes one company's FY3 fundamentals as a file,
not a Python object: ``{"fundamentals": {"fy3_revenue_cagr",
"fy3_ebit_margin", "net_debt_ebitda_fy3", "balance_check"}}`` (see that
repo's ``model.linkage.to_fundamentals_contract`` and its
``model.statements --contract`` CLI flag). This module reads that file and
attaches it to the one candidate in a ``schema/v1.json`` screen output whose
ticker matches, under the ``fundamentals`` key schema/v1.json already
reserves for it.

Communication stays by file: this module never imports ``model`` (three-
statement-model's package), and nothing here fails if the satellite's
researched ticker is outside today's screened universe -- the two repos
build their fixture sets independently, so a screen with no matching
candidate is an expected, reported outcome, not an error. This is in fact
the real-data case here: three-statement-model researched Gulf Oil
Lubricants India (GULFOILLUB), which is not in this repo's 3-ticker fixture
universe (RELIANCE/TATACHEM/CROMPTON), the same honest non-match v0.7's
reverse-dcf-engine integration already recorded.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..disclaimer import DISCLAIMER

REQUIRED_FUNDAMENTALS_KEYS = {
    "fy3_revenue_cagr",
    "fy3_ebit_margin",
    "net_debt_ebitda_fy3",
    "balance_check",
}


def load_contract(path: str | Path) -> dict[str, Any]:
    """Read and validate a three-statement-model ``--contract`` JSON file."""
    raw = json.loads(Path(path).read_text())
    fundamentals = raw.get("fundamentals")
    if not isinstance(fundamentals, dict):
        raise ValueError(f"{path}: no 'fundamentals' object at the top level")
    missing = REQUIRED_FUNDAMENTALS_KEYS - set(fundamentals)
    if missing:
        raise ValueError(f"{path}: fundamentals block missing keys: {sorted(missing)}")
    return fundamentals


def _normalize_ticker(ticker: str) -> str:
    """NSE names show up with (this repo) and without (three-statement-model) the yfinance '.NS' suffix."""
    return ticker.upper().removesuffix(".NS")


def apply_fundamentals_gate(
    screen: dict[str, Any], ticker: str, fundamentals: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Return a copy of ``screen`` with ``fundamentals`` attached to the candidate matching ``ticker``.

    Every other candidate passes through unchanged. Returns the screen dict
    unchanged (aside from the copy) plus a bool the caller can report on.
    """
    target = _normalize_ticker(ticker)
    gated_candidates = []
    matched = False
    for candidate in screen["candidates"]:
        candidate = dict(candidate)
        if _normalize_ticker(candidate["ticker"]) == target:
            candidate["fundamentals"] = dict(fundamentals)
            matched = True
        gated_candidates.append(candidate)
    gated = dict(screen)
    gated["candidates"] = gated_candidates
    return gated, matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screen", required=True, help="path to a schema/v1.json-shaped screen output")
    parser.add_argument("--contract", required=True, help="path to three-statement-model's --contract JSON output")
    parser.add_argument("--ticker", required=True, help="the ticker that contract was built for")
    parser.add_argument("--out", default=None, help="defaults to overwriting --screen in place")
    args = parser.parse_args(argv)

    screen = json.loads(Path(args.screen).read_text())
    fundamentals = load_contract(args.contract)
    gated, matched = apply_fundamentals_gate(screen, args.ticker, fundamentals)

    out_path = Path(args.out) if args.out else Path(args.screen)
    out_path.write_text(json.dumps(gated, indent=2) + "\n")

    if matched:
        print(f"fundamentals gate: attached three-statement-model's contract for {args.ticker} to 1 candidate -> {out_path}")
    else:
        print(
            f"fundamentals gate: {args.ticker} is not in this screen's universe -- "
            f"no candidate updated, {out_path} written unchanged"
        )
    print(DISCLAIMER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
