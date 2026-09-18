"""v0.3 -- VaR/CVaR risk envelope on the screen.

monte-carlo-risk-lab publishes one ticker's risk envelope as a file, not a
Python object: ``{"risk": {"var_95", "cvar_95", "max_dd_sim", "horizon_days"}}``
(see that repo's ``mcsim.portfolio.to_contract`` and its ``--contract`` CLI
flag). This module reads that file and attaches it to the one candidate in a
``schema/v1.json`` screen output whose ticker matches, under the ``risk`` key
schema/v1.json already reserves for it.

Communication stays by file: this module never imports ``mcsim``, and nothing
here fails if the satellite's researched ticker is outside today's screened
universe -- the two repos build their fixture sets independently, so a screen
with no matching candidate is an expected, reported outcome, not an error.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_RISK_KEYS = {
    "var_95",
    "cvar_95",
    "max_dd_sim",
    "horizon_days",
}


def load_contract(path: str | Path) -> dict[str, float]:
    """Read and validate a monte-carlo-risk-lab ``--contract`` JSON file."""
    raw = json.loads(Path(path).read_text())
    risk = raw.get("risk")
    if not isinstance(risk, dict):
        raise ValueError(f"{path}: no 'risk' object at the top level")
    missing = REQUIRED_RISK_KEYS - set(risk)
    if missing:
        raise ValueError(f"{path}: risk block missing keys: {sorted(missing)}")
    return risk


def _normalize_ticker(ticker: str) -> str:
    """NSE names show up with (this repo) and without (monte-carlo-risk-lab) the yfinance '.NS' suffix."""
    return ticker.upper().removesuffix(".NS")


def apply_risk_gate(screen: dict[str, Any], ticker: str, risk: dict[str, float]) -> tuple[dict[str, Any], bool]:
    """Return a copy of ``screen`` with ``risk`` attached to the candidate matching ``ticker``.

    Every other candidate passes through unchanged. Returns the screen dict
    unchanged (aside from the copy) plus a bool the caller can report on.
    """
    target = _normalize_ticker(ticker)
    gated_candidates = []
    matched = False
    for candidate in screen["candidates"]:
        candidate = dict(candidate)
        if _normalize_ticker(candidate["ticker"]) == target:
            candidate["risk"] = dict(risk)
            matched = True
        gated_candidates.append(candidate)
    gated = dict(screen)
    gated["candidates"] = gated_candidates
    return gated, matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screen", required=True, help="path to a schema/v1.json-shaped screen output")
    parser.add_argument("--contract", required=True, help="path to monte-carlo-risk-lab's --contract JSON output")
    parser.add_argument("--ticker", required=True, help="the ticker that contract was solved for")
    parser.add_argument("--out", default=None, help="defaults to overwriting --screen in place")
    args = parser.parse_args(argv)

    screen = json.loads(Path(args.screen).read_text())
    risk = load_contract(args.contract)
    gated, matched = apply_risk_gate(screen, args.ticker, risk)

    out_path = Path(args.out) if args.out else Path(args.screen)
    out_path.write_text(json.dumps(gated, indent=2) + "\n")

    if matched:
        print(f"risk gate: attached monte-carlo-risk-lab's contract for {args.ticker} to 1 candidate -> {out_path}")
    else:
        print(
            f"risk gate: {args.ticker} is not in this screen's universe -- "
            f"no candidate updated, {out_path} written unchanged"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
