"""v0.5 -- headline sentiment overlay on the screen.

headline-sentiment-vs-price publishes one ticker's sentiment block as a
file, not a Python object: ``{"sentiment": {"score_7d", "headline_count_7d",
"model", "coverage"}}`` (see that repo's ``sentiment.contract.build_contract``
and its ``--contract``/``--ticker`` flags on ``python -m sentiment.contract``).
This module reads that file and attaches it to the one candidate in a
``schema/v1.json`` screen output whose ticker matches, under the
``sentiment`` key ``schema/v1.json`` already reserves for it.

``score_7d`` legitimately ships ``null`` when no headline in that repo's
sample resolved to the requested ticker within its trailing window -- this
gate passes the key through unchanged rather than inventing a number;
``load_contract`` only requires the key be present, not that it be non-null,
the same convention ``gates.vol`` already set for ``iv_rank_1y``.

Communication stays by file: this module never imports ``sentiment`` (the
headline-sentiment-vs-price package), and nothing here fails if the
satellite's researched ticker is outside today's screened universe -- the
two repos build their fixture sets independently, so a screen with no
matching candidate is an expected, reported outcome, not an error.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..disclaimer import DISCLAIMER

REQUIRED_SENTIMENT_KEYS = {
    "score_7d",
    "headline_count_7d",
    "model",
    "coverage",
}


def load_contract(path: str | Path) -> dict[str, Any]:
    """Read and validate a headline-sentiment-vs-price ``--contract`` JSON file."""
    raw = json.loads(Path(path).read_text())
    sentiment = raw.get("sentiment")
    if not isinstance(sentiment, dict):
        raise ValueError(f"{path}: no 'sentiment' object at the top level")
    missing = REQUIRED_SENTIMENT_KEYS - set(sentiment)
    if missing:
        raise ValueError(f"{path}: sentiment block missing keys: {sorted(missing)}")
    return sentiment


def _normalize_ticker(ticker: str) -> str:
    """NSE names show up with (this repo) and without (headline-sentiment-vs-price's
    own ticker table already carries the yfinance suffix, but strip it anyway so this
    gate matches the same way every other gate in this repo does)."""
    return ticker.upper().removesuffix(".NS")


def apply_sentiment_gate(
    screen: dict[str, Any], ticker: str, sentiment: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Return a copy of ``screen`` with ``sentiment`` attached to the candidate matching ``ticker``.

    Every other candidate passes through unchanged. Returns the screen dict
    unchanged (aside from the copy) plus a bool the caller can report on.
    """
    target = _normalize_ticker(ticker)
    gated_candidates = []
    matched = False
    for candidate in screen["candidates"]:
        candidate = dict(candidate)
        if _normalize_ticker(candidate["ticker"]) == target:
            candidate["sentiment"] = dict(sentiment)
            matched = True
        gated_candidates.append(candidate)
    gated = dict(screen)
    gated["candidates"] = gated_candidates
    return gated, matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screen", required=True, help="path to a schema/v1.json-shaped screen output")
    parser.add_argument("--contract", required=True, help="path to headline-sentiment-vs-price's --contract JSON output")
    parser.add_argument("--ticker", required=True, help="the ticker that contract was built for")
    parser.add_argument("--out", default=None, help="defaults to overwriting --screen in place")
    args = parser.parse_args(argv)

    screen = json.loads(Path(args.screen).read_text())
    sentiment = load_contract(args.contract)
    gated, matched = apply_sentiment_gate(screen, args.ticker, sentiment)

    out_path = Path(args.out) if args.out else Path(args.screen)
    out_path.write_text(json.dumps(gated, indent=2) + "\n")

    if matched:
        print(f"sentiment gate: attached headline-sentiment-vs-price's contract for {args.ticker} to 1 candidate -> {out_path}")
    else:
        print(
            f"sentiment gate: {args.ticker} is not in this screen's universe -- "
            f"no candidate updated, {out_path} written unchanged"
        )
    print(DISCLAIMER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
