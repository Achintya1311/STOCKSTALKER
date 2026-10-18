"""Day 24 (C1): real, end-to-end smoke test for the live sentiment-contract
subprocess path -- shells out to the real headline-sentiment-vs-price
sibling checkout via uv and runs its real ``sentiment.contract`` CLI
against its own committed headline corpus, instead of monkeypatching the
subprocess (see test_live_contracts.py and the Day 24 section of
test_run.py for the deterministic, environment-independent tests).

TATAELXSI is used deliberately: ``sentiment.tickers``' closed lookup table
(see that repo's own module) has no rule naming it, so the real result is
a genuine, deterministic "coverage: none" zero regardless of how large the
corpus has grown since (D3/D10's daily scrape only ever adds headlines
that match an *existing* rule's pattern to a *different* company, so a
ticker outside the table entirely can never pick up a match it didn't
already have) -- the same honest-zero shape GULFOILLUB's own committed
fixture already has.

Two honest outcomes, both asserted on, the same pattern
test_live_risk_contract_smoke.py already uses:

- The sibling checkout is actually present next to this repo (true in the
  routine's own sandbox and on Achintya's own machine): run it for real
  and check the real contract, not a stub.
- It isn't (true in STOCKSTALKER's own GitHub Actions CI, which checks out
  only this one repo): skip, rather than silently pass or fail.
"""

from __future__ import annotations

import pytest

from stockstalker import run
from stockstalker.live_contracts import resolve_sentiment_root


def test_build_live_sentiment_section_against_the_real_sibling_checkout(tmp_path):
    sentiment_root = resolve_sentiment_root()
    if not (sentiment_root / "sentiment" / "contract.py").is_file():
        pytest.skip(
            f"headline-sentiment-vs-price is not checked out at {sentiment_root} in "
            "this environment; this is expected in STOCKSTALKER's own CI (a workflow "
            "only checks out the one repo it runs in), not a bug -- re-run next "
            "to a real sibling checkout to actually exercise the live path."
        )

    section = run.build_live_sentiment_section("TATAELXSI", tmp_path)

    assert section is not None, "the real subprocess call failed -- see stderr above"
    assert section["namespace"] == "sentiment"
    assert section["available"] is True
    assert section["source"] == "headline-sentiment-vs-price (live)"
    data = section["data"]
    assert data["score_7d"] is None
    assert data["headline_count_7d"] == 0
    assert data["model"] == "vader"
    assert data["coverage"] == "none"

    contract_path = tmp_path / "contracts" / "TATAELXSI" / "sentiment.json"
    assert contract_path.exists()
