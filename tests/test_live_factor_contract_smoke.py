"""Day 22 (C1): real, end-to-end smoke test for the live factor-contract
subprocess path -- the one test in this day's suite that actually shells
out to the real fama-french-factor-model sibling checkout via uv (running
the Day 22 `factors.stock` CLI), instead of monkeypatching the subprocess
(see test_live_contracts.py and the Day 22 section of test_run.py for the
deterministic, environment-independent tests). Same pattern as
test_live_risk_contract_smoke.py (Day 21).

Two honest outcomes, both asserted on:

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
from stockstalker.live_contracts import resolve_factor_model_root


def test_build_live_factor_section_against_the_real_sibling_checkout(tmp_path):
    factor_model_root = resolve_factor_model_root()
    if not (factor_model_root / "factors" / "stock.py").is_file():
        pytest.skip(
            f"fama-french-factor-model is not checked out at {factor_model_root} in this "
            "environment; this is expected in STOCKSTALKER's own CI (a workflow "
            "only checks out the one repo it runs in), not a bug -- re-run next "
            "to a real sibling checkout to actually exercise the live path."
        )

    section = run.build_live_factor_section("TATAELXSI", "fixtures", tmp_path)

    assert section is not None, "the real subprocess call failed -- see stderr above"
    assert section["namespace"] == "factor"
    assert section["available"] is True
    assert section["source"] == "fama-french-factor-model (live)"
    data = section["data"]
    assert set(data) == {"alpha_annual", "alpha_t", "significant", "loadings"}
    # TATAELXSI's own real OHLCV fixture (496 daily closes, committed Day
    # 20) regressed against IIMA's factors through `factors.stock` -- real
    # numbers, not a stub, confirmed by hand against the same command run
    # directly in fama-french-factor-model this same day (Day 22). Only 14
    # months overlap (IIMA's own history stops 2025-12, and TATAELXSI's
    # fixture starts mid-2024) -- an honestly small sample, reported as-is.
    assert data["alpha_annual"] == pytest.approx(-0.17698389510750168, rel=1e-6)
    assert data["alpha_t"] == pytest.approx(-0.9796779615257218, rel=1e-6)
    assert data["significant"] is False
    assert set(data["loadings"]) == {"mkt", "smb", "hml", "wml"}
    assert data["loadings"]["mkt"] == pytest.approx(0.5224708626452492, rel=1e-6)

    contract_path = tmp_path / "contracts" / "TATAELXSI" / "factor.json"
    assert contract_path.exists()
