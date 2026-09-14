# Changelog

## v0.7.0 — 2026-09-14

Valuation gate on survivors. Skips v0.2–v0.6 by design — the hub's release track assigns
each satellite its own version number by pipeline position, not by shipping order, and
reverse-dcf-engine (v0.7) finished its 9-day plan before the satellites ahead of it in
the funnel (factor, risk, sizing, sentiment, vol) started theirs.

**Ships:**
- `stockstalker.gates.valuation` — reads reverse-dcf-engine's file contract
  (`{"valuation": {"implied_cagr", "implied_ebit_margin", "implied_reinvestment",
  "breakeven_growth"}}`, written by that repo's `python -m reverse_dcf.solve --contract`)
  and attaches it to the one screen candidate whose ticker matches, under the `valuation`
  key `schema/v1.json` already reserves. Every other candidate passes through unchanged;
  a ticker outside the current universe is a reported non-match, not an error.
- `stockstalker.report` — new `--valuation-contract`/`--valuation-ticker` flags apply the
  gate before rendering; the screen table grows two columns (Implied CAGR, Breakeven
  growth) only when at least one candidate actually carries a valuation block.

**Verified before tagging:**
- `pytest` — 161 passed, 1 skipped (the live-network smoke test; no network in this
  environment, expected)
- `python -m stockstalker.gates.valuation --screen <screen.json> --contract
  fixtures/valuation/GULFOILLUB.json --ticker GULFOILLUB` — run against the real
  reverse-dcf-engine fixture output
- `python -m stockstalker.report --offline --valuation-contract
  fixtures/valuation/GULFOILLUB.json --valuation-ticker GULFOILLUB` — end to end

**Known limitation (see README):** reverse-dcf-engine researched Gulf Oil Lubricants
India (GULFOILLUB), which is not in this repo's 3-ticker fixture universe (RELIANCE,
TATACHEM, CROMPTON). The gate is fully tested against a synthetic matching contract, but
the real contract currently produces zero matches end to end — an honest result of two
satellites built independently against their own fixture sets, not a bug.

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
