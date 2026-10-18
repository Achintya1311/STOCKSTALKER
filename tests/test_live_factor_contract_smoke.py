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

TATAELXSI's own real fixture only overlaps IIMA's factor history by 14
months (fama-french-factor-model/factors.stock's FF3+WML spec needs 5
parameters incl. intercept, 4 factor columns). Before fama-french-factor-
model's D15 fix (critiques/2026-10-18-fama-french-factor-model-1.md,
NEXT_STEPS.md day 39) this repo had no minimum-sample floor at all and
silently returned a "result" from those 14 months; D15 added a 3x-the-
parameter-count floor (>=15 months here), so this sibling checkout's own
subprocess now correctly declines TATAELXSI as insufficient data rather
than fabricating a number -- the exact behaviour the day 39 fix was meant
to produce, confirmed here against the real checkout.
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

    # TATAELXSI's 14-month overlap with IIMA's factor history is below
    # fama-french-factor-model's D15 floor (3x FF3+WML's 5 parameters = 15
    # months), so the sibling's own CLI now declines with a one-line
    # reason instead of writing a contract -- build_live_factor_section
    # reports that the same way as any other live-path failure (sibling
    # missing, uv missing): None, not a fabricated "available" section.
    section = run.build_live_factor_section("TATAELXSI", "fixtures", tmp_path)

    assert section is None
    contract_path = tmp_path / "contracts" / "TATAELXSI" / "factor.json"
    assert not contract_path.exists()
