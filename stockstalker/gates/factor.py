"""v0.2 -- factor-adjusted ranking on the screen.

fama-french-factor-model publishes one ticker's factor regression as a
file, not a Python object: ``{"factor": {"alpha_annual", "alpha_t",
"significant", "loadings"}}`` (see that repo's ``factors.screen_check.
to_contract`` and its ``--contract``/``--contract-ticker`` CLI flags).
This module reads that file and attaches it to the one candidate in a
``schema/v1.json`` screen output whose ticker matches, under the ``factor``
key schema/v1.json already reserves for it.

Communication stays by file: this module never imports ``factors``, and
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

REQUIRED_FACTOR_KEYS = {
    "alpha_annual",
    "alpha_t",
    "significant",
    "loadings",
}


def load_contract(path: str | Path) -> dict[str, Any]:
    """Read and validate a fama-french-factor-model ``--contract`` JSON file."""
    raw = json.loads(Path(path).read_text())
    factor = raw.get("factor")
    if not isinstance(factor, dict):
        raise ValueError(f"{path}: no 'factor' object at the top level")
    missing = REQUIRED_FACTOR_KEYS - set(factor)
    if missing:
        raise ValueError(f"{path}: factor block missing keys: {sorted(missing)}")
    return factor


def _normalize_ticker(ticker: str) -> str:
    """NSE names show up with (this repo) and without (fama-french-factor-model) the yfinance '.NS' suffix."""
    return ticker.upper().removesuffix(".NS")


def significance_label(significant: bool) -> str:
    """Render the contract's own ``significant`` bool as words, not True/False (R6)."""
    return "significant" if significant else "not significant"


# R6: RELIANCE's contract is still fama-french-factor-model's original
# regression -- USD Ken French factors against INR prices, 22 overlapping
# months, underpowered for up to 7 parameters (that repo's README, Day 5
# screen-check). GULFOILLUB's contract (front-door Day 5) replaced that
# with IIMA's Indian factors on 137 real months instead; every ticker not
# listed here used that newer method.
OLD_METHOD_FACTOR_TICKERS: dict[str, str] = {
    "RELIANCE": (
        "old method -- Ken French USD factors, 22 overlapping months, "
        "underpowered (fama-french-factor-model README, Day 5 screen check); "
        "GULFOILLUB's own contract uses IIMA's Indian factors on 137 months instead"
    ),
}


def method_label(ticker: str) -> str | None:
    """A one-line method caveat for tickers still on the old Ken French regression, else None."""
    return OLD_METHOD_FACTOR_TICKERS.get(_normalize_ticker(ticker))


def apply_factor_gate(screen: dict[str, Any], ticker: str, factor: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return a copy of ``screen`` with ``factor`` attached to the candidate matching ``ticker``.

    Every other candidate passes through unchanged. Returns the screen dict
    unchanged (aside from the copy) plus a bool the caller can report on.
    """
    target = _normalize_ticker(ticker)
    gated_candidates = []
    matched = False
    for candidate in screen["candidates"]:
        candidate = dict(candidate)
        if _normalize_ticker(candidate["ticker"]) == target:
            candidate["factor"] = dict(factor)
            matched = True
        gated_candidates.append(candidate)
    gated = dict(screen)
    gated["candidates"] = gated_candidates
    return gated, matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screen", required=True, help="path to a schema/v1.json-shaped screen output")
    parser.add_argument("--contract", required=True, help="path to fama-french-factor-model's --contract JSON output")
    parser.add_argument("--ticker", required=True, help="the ticker that contract was solved for")
    parser.add_argument("--out", default=None, help="defaults to overwriting --screen in place")
    args = parser.parse_args(argv)

    screen = json.loads(Path(args.screen).read_text())
    factor = load_contract(args.contract)
    gated, matched = apply_factor_gate(screen, args.ticker, factor)

    out_path = Path(args.out) if args.out else Path(args.screen)
    out_path.write_text(json.dumps(gated, indent=2) + "\n")

    if matched:
        print(f"factor gate: attached fama-french-factor-model's contract for {args.ticker} to 1 candidate -> {out_path}")
    else:
        print(
            f"factor gate: {args.ticker} is not in this screen's universe -- "
            f"no candidate updated, {out_path} written unchanged"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
