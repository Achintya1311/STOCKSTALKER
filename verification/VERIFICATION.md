# Test verification log — STOCKSTALKER

Machine-owned by `tools/verify.py` (called from the hub) - don't hand-edit. Full per-test detail lives in `verification/log.json`; this file is the human-readable summary a future routine run reads **before** deciding what to test next, so it adds new coverage instead of re-running what already passed, and retries open items differently instead of repeating them verbatim.

<!-- VERIFICATION:START -->
| Date | Commit | Passed | Failed | Skipped | New test IDs | Repeated (no new coverage) | Notes |
|------|--------|--------|--------|---------|--------------|------------------------------|-------|
| 2026-09-10 | `59ac4e2` | 148 | 0 | 1 | 149 | 0 | Baseline + first classification/multi-layer-filtering/live-provider-contract pass: 6 engineered OHLCV regimes verifying trend/momentum/volume classify correctly, config-weight responsiveness, end-to-end multi-layer score+liquidity filtering with per-exclusion-reason checks, and a real (sandbox-blocked) live-network contract test. |
| 2026-10-22 | `7c5e994` | 433 | 0 | 0 | 285 | 148 | Day 54 (P54): re-verify tools/verify.py after switching run_pytest() from python -m pytest to uv run --with pytest pytest, confirming recorded totals match the bare-pytest-equivalent ground truth (433 passed, 0 failed, 0 skipped, uv run --with pytest pytest -q, 316.39s) |
<!-- VERIFICATION:END -->

## Currently open (failing or skipped as of the latest run)

Nothing open - every collected test passed on the latest run.

