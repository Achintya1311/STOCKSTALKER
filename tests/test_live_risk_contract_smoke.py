"""Day 21 (C1): real, end-to-end smoke test for the live risk-contract
subprocess path -- the one test in this day's suite that actually shells
out to the real monte-carlo-risk-lab sibling checkout via uv, instead of
monkeypatching the subprocess (see test_live_contracts.py and the Day 21
section of test_run.py for the deterministic, environment-independent
tests).

Two honest outcomes, both asserted on, the same pattern
test_live_provider_smoke.py already uses for a real yfinance call:

- The sibling checkout is actually present next to this repo (true in the
  routine's own sandbox, and on Achintya's own machine): run it for real
  and check the real numbers, not a stub.
- It isn't (true in STOCKSTALKER's own GitHub Actions CI, which checks out
  only this one repo): skip, rather than silently pass or fail, so a skip
  in the test report means exactly "no sibling checkout here", never
  "the live path was verified."
"""

from __future__ import annotations

import pytest

from stockstalker import run
from stockstalker.live_contracts import resolve_risk_lab_root


def test_build_live_risk_section_against_the_real_sibling_checkout(tmp_path):
    risk_lab_root = resolve_risk_lab_root()
    if not (risk_lab_root / "mcsim" / "portfolio.py").is_file():
        pytest.skip(
            f"monte-carlo-risk-lab is not checked out at {risk_lab_root} in this "
            "environment; this is expected in STOCKSTALKER's own CI (a workflow "
            "only checks out the one repo it runs in), not a bug -- re-run next "
            "to a real sibling checkout to actually exercise the live path."
        )

    section = run.build_live_risk_section("TATAELXSI", "fixtures", tmp_path)

    assert section is not None, "the real subprocess call failed -- see stderr above"
    assert section["namespace"] == "risk"
    assert section["available"] is True
    assert section["source"] == "monte-carlo-risk-lab (live)"
    data = section["data"]
    assert data["horizon_days"] == 20
    # TATAELXSI's own real OHLCV fixture (496 daily closes, committed Day
    # 20) run through mcsim.portfolio at its CLI defaults (confidence 0.95
    # 0.99, horizon 20, paths 1e6, seed 42) -- real numbers, not a stub,
    # confirmed by hand against the same command run directly in
    # monte-carlo-risk-lab this same day (Day 21).
    assert data["var_95"] == pytest.approx(-0.1636326908838061, rel=1e-6)
    assert data["cvar_95"] == pytest.approx(-0.19037324003810938, rel=1e-6)
    assert data["var_99"] == pytest.approx(-0.21432773266847796, rel=1e-6)
    assert data["cvar_99"] == pytest.approx(-0.22225330499942367, rel=1e-6)
    assert data["max_dd_sim"] == pytest.approx(-0.0970035516209491, rel=1e-5)
    assert data["kupiec_95"]["reject_at_5pct"] is False
    assert data["kupiec_99"]["reject_at_5pct"] is False

    contract_path = tmp_path / "contracts" / "TATAELXSI" / "risk.json"
    assert contract_path.exists()
