# Committed tear sheets

Each file is the unedited output of `python -m stockstalker.run --ticker <TICKER> --offline` (or `--live`) on the date in its name.

The 2026-10-18 tear sheets predate two fixture fixes made on 26 Oct 2026 (hub CRITIQUES.md D39 and D30). The RELIANCE `vol` block there (atm_iv_30d 0.2150) came from implied-vol-surface's synthetic chain. The GULFOILLUB `valuation` ceilings there (₹914.55 and ₹715.52) predate reverse-dcf-engine's 25 Oct WACC refresh. The 2026-10-26 files carry the regenerated values. CASTROLIND uses no committed fixture and was not re-run, so its valuation block also predates the WACC refresh.
