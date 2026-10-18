"""Day 24 (C1): real, end-to-end smoke test for the live vol-contract
subprocess path -- shells out to the real implied-vol-surface sibling
checkout via uv and solves its real committed raw NSE capture for
RELIANCE, instead of monkeypatching the subprocess (see test_live_contracts.py
and the Day 24 section of test_run.py for the deterministic,
environment-independent tests).

Two honest outcomes, both asserted on, the same pattern
test_live_risk_contract_smoke.py already uses:

- The sibling checkout is actually present next to this repo, with a real
  raw NSE capture committed for RELIANCE (true in the routine's own
  sandbox and on Achintya's own machine): run it for real and check the
  real numbers, not a stub.
- It isn't (true in STOCKSTALKER's own GitHub Actions CI, which checks out
  only this one repo): skip, rather than silently pass or fail, so a skip
  in the test report means exactly "no sibling checkout/capture here",
  never "the live path was verified."
"""

from __future__ import annotations

import pytest

from stockstalker import run
from stockstalker.live_contracts import raw_capture_exists, resolve_iv_surface_root


def test_build_live_vol_section_against_the_real_sibling_checkout(tmp_path):
    iv_surface_root = resolve_iv_surface_root()
    if not (iv_surface_root / "volsurface" / "history.py").is_file():
        pytest.skip(
            f"implied-vol-surface is not checked out at {iv_surface_root} in this "
            "environment; this is expected in STOCKSTALKER's own CI (a workflow "
            "only checks out the one repo it runs in), not a bug -- re-run next "
            "to a real sibling checkout to actually exercise the live path."
        )
    if not raw_capture_exists("RELIANCE", iv_surface_root):
        pytest.skip(
            "implied-vol-surface has no raw NSE capture committed for RELIANCE in "
            "this environment -- P12's home-connection job is the only source of "
            "one; expected wherever that job hasn't run yet, not a bug."
        )

    section = run.build_live_vol_section("RELIANCE", tmp_path)

    assert section is not None, "the real subprocess call failed -- see stderr above"
    assert section["namespace"] == "vol"
    assert section["available"] is True
    assert section["source"] == "implied-vol-surface (live)"
    data = section["data"]
    # RELIANCE's own real raw v3 captures (3 expiries, captured 2026-10-16
    # per P12) solved through volsurface.history --provider nse_raw --
    # real numbers, not a stub, confirmed by hand against the same command
    # run directly in implied-vol-surface this same day (Day 24).
    assert data["atm_iv_30d"] == pytest.approx(0.24847844072190686, rel=1e-6)
    assert data["skew_25d"] == pytest.approx(-0.004580337234500909, rel=1e-6)
    assert data["term_slope"] == pytest.approx(-0.01363522714076379, rel=1e-6)
    assert data["iv_rank_1y"] is None

    contract_path = tmp_path / "contracts" / "RELIANCE" / "vol.json"
    assert contract_path.exists()
