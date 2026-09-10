# Test verification log — STOCKSTALKER

Machine-owned by `tools/verify.py` (called from the hub) - don't hand-edit. Full per-test detail lives in `verification/log.json`; this file is the human-readable summary a future routine run reads **before** deciding what to test next, so it adds new coverage instead of re-running what already passed, and retries open items differently instead of repeating them verbatim.

<!-- VERIFICATION:START -->
| Date | Commit | Passed | Failed | Skipped | New test IDs | Repeated (no new coverage) | Notes |
|------|--------|--------|--------|---------|--------------|------------------------------|-------|
| 2026-09-10 | `59ac4e2` | 148 | 0 | 1 | 149 | 0 | Baseline + first classification/multi-layer-filtering/live-provider-contract pass: 6 engineered OHLCV regimes verifying trend/momentum/volume classify correctly, config-weight responsiveness, end-to-end multi-layer score+liquidity filtering with per-exclusion-reason checks, and a real (sandbox-blocked) live-network contract test. |
<!-- VERIFICATION:END -->

## Currently open (failing or skipped as of the latest run)

Next time this project is verified: retry these differently (a new angle, or after whatever blocked them has changed) rather than leaving them standing indefinitely or re-running them unchanged.

- `tests.test_live_provider_smoke::test_yfinance_provider_gives_real_live_values_or_fails_cleanly` — **skipped**: no live network reachable in this sandbox (no rows returned for RELIANCE.NS); this is the offline/zero-spend default working as intended, not a scanner bug. Re-run in an environment with outbound network to actually exercise the live path.

