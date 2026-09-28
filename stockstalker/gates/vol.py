"""v0.6 -- options-implied risk signal on the screen.

implied-vol-surface publishes one ticker's vol block as a file, not a
Python object: ``{"vol": {"atm_iv_30d", "skew_25d", "term_slope", "iv_rank_1y"}}``
(see that repo's ``volsurface.history.DailySummary.to_contract`` and its
``--contract`` CLI flag on ``python -m volsurface.history``). This module
reads that file and attaches it to the one candidate in a ``schema/v1.json``
screen output whose ticker matches, under the ``vol`` key schema/v1.json
already reserves for it.

``iv_rank_1y`` legitimately ships ``null`` on this integration -- volsurface's
own history has never accumulated more than one distinct trading day, so
there is no real trailing-year window to rank against yet (see that repo's
README Limitations). This gate passes the key through unchanged rather than
inventing a value; ``load_contract`` only requires the key be present, not
that it be non-null.

Communication stays by file: this module never imports ``volsurface``, and
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

REQUIRED_VOL_KEYS = {
    "atm_iv_30d",
    "skew_25d",
    "term_slope",
    "iv_rank_1y",
}


def load_contract(path: str | Path) -> dict[str, float | None]:
    """Read and validate an implied-vol-surface ``--contract`` JSON file."""
    raw = json.loads(Path(path).read_text())
    vol = raw.get("vol")
    if not isinstance(vol, dict):
        raise ValueError(f"{path}: no 'vol' object at the top level")
    missing = REQUIRED_VOL_KEYS - set(vol)
    if missing:
        raise ValueError(f"{path}: vol block missing keys: {sorted(missing)}")
    return vol


def _normalize_ticker(ticker: str) -> str:
    """NSE names show up with (this repo) and without (implied-vol-surface) the yfinance '.NS' suffix."""
    return ticker.upper().removesuffix(".NS")


def apply_vol_gate(
    screen: dict[str, Any], ticker: str, vol: dict[str, float | None]
) -> tuple[dict[str, Any], bool]:
    """Return a copy of ``screen`` with ``vol`` attached to the candidate matching ``ticker``.

    Every other candidate passes through unchanged. Returns the screen dict
    unchanged (aside from the copy) plus a bool the caller can report on.
    """
    target = _normalize_ticker(ticker)
    gated_candidates = []
    matched = False
    for candidate in screen["candidates"]:
        candidate = dict(candidate)
        if _normalize_ticker(candidate["ticker"]) == target:
            candidate["vol"] = dict(vol)
            matched = True
        gated_candidates.append(candidate)
    gated = dict(screen)
    gated["candidates"] = gated_candidates
    return gated, matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screen", required=True, help="path to a schema/v1.json-shaped screen output")
    parser.add_argument("--contract", required=True, help="path to implied-vol-surface's --contract JSON output")
    parser.add_argument("--ticker", required=True, help="the ticker that contract was solved for")
    parser.add_argument("--out", default=None, help="defaults to overwriting --screen in place")
    args = parser.parse_args(argv)

    screen = json.loads(Path(args.screen).read_text())
    vol = load_contract(args.contract)
    gated, matched = apply_vol_gate(screen, args.ticker, vol)

    out_path = Path(args.out) if args.out else Path(args.screen)
    out_path.write_text(json.dumps(gated, indent=2) + "\n")

    if matched:
        print(f"vol gate: attached implied-vol-surface's contract for {args.ticker} to 1 candidate -> {out_path}")
    else:
        print(
            f"vol gate: {args.ticker} is not in this screen's universe -- "
            f"no candidate updated, {out_path} written unchanged"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
