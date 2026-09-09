# Changelog

## v0.1.0 — 2026-09-09

First integration release. The spine of the nine-repo pipeline, ready for satellites to read.

**Ships:**
- `stockstalker.screener` — YAML-configured trend/momentum/volume screen, ranked candidate list (`outputs/screen_<date>.{json,csv,md}`), conforming to `schema/v1.json`
- `stockstalker.viz.liquidity` — volume-at-price liquidity heatmap per ticker (`outputs/heatmap_<ticker>.png`)
- `stockstalker.report` — combined CLI report (rich terminal tables: screen + walk-forward-vs-buy-and-hold backtest) plus the heatmap charts, in one command
- `stockstalker.audit` — look-ahead bias check wired into CI, with negative controls proving it actually fires
- `schema/v1.json` — the versioned contract satellite repos extend under their own namespace (`factor`, `risk`, `sizing`, `sentiment`, `vol`, `valuation`, `fundamentals`)
- Offline-by-default: every command runs against committed fixtures with no network or API key required; `--live` is opt-in

**Verified before tagging:**
- `pytest` — 137 passed
- `python -m stockstalker.screener --offline` — ranked CSV/JSON/MD, JSON validated against `schema/v1.json`
- `python -m stockstalker.report --offline` — terminal report + 3 heatmap PNGs
- `python -m stockstalker.audit --offline` — no look-ahead detected

**Known limitations (see README for the full list):** no validated trading edge (Day 7 backtest lost to buy-and-hold on 2/3 names), survivorship bias in the ticker universe, screen weights are hand-picked rather than fit, Alpha Vantage free tier caps live runs at 25 requests/day.

**Not yet done:** repo is still private. Flipping it public is a decision for a human, not this pipeline — see `NEXT_STEPS.md`.
