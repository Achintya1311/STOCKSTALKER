# Test verification log — STOCKSTALKER

Machine-owned by `tools/verify.py` (called from the hub) - don't hand-edit. Full per-test detail lives in `verification/log.json`; this file is the human-readable summary a future routine run reads **before** deciding what to test next, so it adds new coverage instead of re-running what already passed, and retries open items differently instead of repeating them verbatim. 'Repeated (unchanged)' is a true no-op repeat (same outcome as last time); 'Fixed' and 'Regressed' are repeated test IDs whose outcome moved since they were last seen - real information, not noise.

<!-- VERIFICATION:START -->
| Date | Commit | Passed | Failed | Skipped | New test IDs | Repeated (unchanged) | Fixed | Regressed | Notes |
|------|--------|--------|--------|---------|--------------|-----------------------|-------|-----------|-------|
| 2026-09-10 | `59ac4e2` | 148 | 0 | 1 | 149 | 0 | 0 | 0 | Baseline + first classification/multi-layer-filtering/live-provider-contract pass: 6 engineered OHLCV regimes verifying trend/momentum/volume classify correctly, config-weight responsiveness, end-to-end multi-layer score+liquidity filtering with per-exclusion-reason checks, and a real (sandbox-blocked) live-network contract test. |
| 2026-10-22 | `7c5e994` | 433 | 0 | 0 | 285 | 148 | 0 | 0 | Day 54 (P54): re-verify tools/verify.py after switching run_pytest() from python -m pytest to uv run --with pytest pytest, confirming recorded totals match the bare-pytest-equivalent ground truth (433 passed, 0 failed, 0 skipped, uv run --with pytest pytest -q, 316.39s) |
| 2026-10-24 | `e07d3d7` | 446 | 1 | 0 | 14 | 432 | 0 | 1 | Day 88 (P65): re-run after tools/verify.py now tracks outcome transitions (fixed/regressed), not just test-ID membership. Confirming STOCKSTALKER's existing log still renders correctly under the new logic. |
<!-- VERIFICATION:END -->

## Currently open (failing or skipped as of the latest run)

Next time this project is verified: retry these differently (a new angle, or after whatever blocked them has changed) rather than leaving them standing indefinitely or re-running them unchanged.

- `tests.test_live_vol_contract_smoke::test_build_live_vol_section_against_the_real_sibling_checkout` — **failed**: assert 0.2801038061895711 == 0.24847844072190686 ± 2.5e-07

