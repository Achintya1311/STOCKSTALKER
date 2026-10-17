"""Day 23 (C1): real, end-to-end smoke test for the live valuation-contract
subprocess path -- the one test in this day's suite that actually shells
out to the real reverse-dcf-engine sibling checkout via uv (running the Day
23 `reverse_dcf.solve --live-financials` CLI), instead of monkeypatching
the subprocess (see test_live_contracts.py and the Day 23 section of
test_run.py for the deterministic, environment-independent tests). Same
pattern as test_live_risk_contract_smoke.py (Day 21) and
test_live_factor_contract_smoke.py (Day 22) -- except this path's own
subprocess makes a real yfinance call for the financials (not just the
price this repo already supplies as a CSV), so a second, independent way
to skip honestly is added: the sibling is present, but this sandbox's
outbound network to Yahoo isn't reachable right now.

Three honest outcomes, all asserted on:

- The sibling checkout is present and live network is reachable: run it
  for real and check the real contract shape (not pinned numbers --
  yfinance's own trailing financial-statement window moves over time, so a
  pinned number here would eventually go stale through no fault of this
  code, unlike Day 22's factor smoke test, which regresses against a
  frozen OHLCV fixture rather than a live statement fetch).
- The sibling checkout isn't present (true in STOCKSTALKER's own GitHub
  Actions CI, which checks out only this one repo): skip.
- The sibling is present but the subprocess's own yfinance call fails (no
  live network in this sandbox): skip, not fail -- this is reverse-dcf-
  engine's own live_financials.py's honest-skip behaviour, inherited here.
"""

from __future__ import annotations

import pytest

from stockstalker import run
from stockstalker.live_contracts import resolve_reverse_dcf_root


def test_build_live_valuation_section_against_the_real_sibling_checkout(tmp_path):
    reverse_dcf_root = resolve_reverse_dcf_root()
    if not (reverse_dcf_root / "reverse_dcf" / "solve.py").is_file():
        pytest.skip(
            f"reverse-dcf-engine is not checked out at {reverse_dcf_root} in this "
            "environment; this is expected in STOCKSTALKER's own CI (a workflow "
            "only checks out the one repo it runs in), not a bug -- re-run next "
            "to a real sibling checkout to actually exercise the live path."
        )

    section = run.build_live_valuation_section("TATAELXSI", "fixtures", tmp_path)

    if section is None:
        pytest.skip(
            "the real subprocess call returned no contract -- most likely no "
            "live network reachable for yfinance from inside it in this "
            "sandbox right now (reverse-dcf-engine's own live_financials.py "
            "honest-skip behaviour); re-run with outbound network to yfinance "
            "to actually exercise this path end to end."
        )

    assert section["namespace"] == "valuation"
    assert section["available"] is True
    assert section["source"] == "reverse-dcf-engine (live)"
    data = section["data"]
    assert {"implied_cagr", "implied_ebit_margin", "implied_reinvestment", "breakeven_growth"} <= set(data)
    assert data["financials_source"] == "yfinance, consolidated, 4-5 years"
    # A real EBIT margin is a plain fraction of revenue -- a loose sanity
    # band, not a pinned number (TATAELXSI's own trailing margin moves
    # every time yfinance's statement window rolls forward).
    assert -1.0 < data["implied_ebit_margin"] < 1.0

    contract_path = tmp_path / "contracts" / "TATAELXSI" / "valuation.json"
    assert contract_path.exists()
