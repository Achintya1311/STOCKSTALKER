# Stock Stalker

Screens the NSE universe down to a shortlist worth researching properly, using trend, momentum, volume and liquidity signals. Command-line only: arguments in, ranked candidates and chart files out.

**Status:** Last checkpoint 2026-10-12 · Next: Day 3 -- risk on the subject (monte-carlo-risk-lab): copy GULFOILLUB_NS.csv across, adapt mcsim.portfolio if hard-wired to RELIANCE, write STOCKSTALKER/fixtures/risk/GULFOILLUB.json with --contract in the v0.3 shape, record the Kupiec result

## What this is

The spine of a nine-repo research pipeline. On its own it answers a narrow question — which names in the universe are behaving in a way that makes them worth a closer look. The value comes from what gets layered on top: factor adjustment, risk envelopes, sentiment, and finally a valuation and a written view.

The screen is the funnel, not the product. What comes out the far end is an equity research note with an opinion in it. A ranked CSV is a starting point for research, and this README will not pretend otherwise.

## Honest status

This repo existed as a single empty commit for over a year while the project was listed on a CV. It is being rebuilt properly, in the open, one day at a time. The checkpoint log below is the real history — no backdating, no squashing it into one heroic commit.

What actually works is whatever the log says works. Anything above that line is intent.

## Correctness gate

`python -m stockstalker.screener --offline` produces a ranked CSV and a readable terminal report from committed fixtures alone, with output conforming to `schema/v1.json`, and `pytest` green.

Until that passes, this is a scaffold.

## Data sources

Every source is free. This project never requires a paid tier, a subscription, or a funded account.

- **yfinance** — daily OHLCV for NSE tickers, no key required
- **Alpha Vantage** — free tier, 25 requests/day, key read from `.env` and never committed
- **Committed fixtures** — two years of daily bars for three NSE names, so everything runs offline

## How to run

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
pytest
```

Offline against fixtures is the default path, not the fallback. Live fetching is opt-in via `--live` and needs a key in `.env` (see `.env.example`).

## Pipeline audit

```bash
python -m stockstalker.audit --offline
```

Checks that every indicator feeding the screen and the backtest is causal —
its value for bar *i* never changes when bars after *i* are truncated out
of the frame. Concretely: computes each of `sma`, `ema`, `rsi`,
`macd.histogram`, `obv` and `volume_zscore` on the full fixture series and
again on the series cut off at a sample of bars, and fails if the two ever
disagree. `tests/test_audit.py` includes two negative controls (a centred
rolling mean, a `shift(-1)`) that the checker must flag, so a pass means
the check actually ran, not that it is vacuous. Runs in CI on every push.

This is a structural check for look-ahead bias, not a statistical
endorsement of the strategy — it cannot tell you whether the screen's
thresholds are any good, only that the numbers behind them were computed
without seeing the future. See Findings and Limitations for that half of
the picture.

## Findings

### Day 7 — screen score vs. buy-and-hold (walk-forward, fixtures only)

`python -m stockstalker.backtest --offline` tests whether yesterday's blended
screen score (>= 0.5, i.e. a non-negative trend/momentum/volume blend)
predicts today capturing a positive return — long when the prior close's
score clears the bar, flat otherwise, no shorting, no costs — over the
~450 tradeable days once each ticker clears its 50-bar burn-in.

| Ticker | Strategy | Buy & hold | Edge |
|---|---|---|---|
| RELIANCE.NS | -1.85% | +5.19% | -7.04% |
| TATACHEM.NS | +4.62% | -39.34% | +43.96% |
| CROMPTON.NS | -35.32% | -36.05% | +0.73% |

2 of 3 names beat buy-and-hold, but only by losing less during a steep
decline: the strategy still lost money outright on TATACHEM and CROMPTON,
and lost to buy-and-hold on RELIANCE, the one name that actually went up.
Mean strategy return -10.85% vs. mean buy-and-hold -23.40%. Read this as
"doesn't obviously do worse than being long," not as validated edge —
three tickers over one overlapping two-year window is not a sample that
supports a stronger claim either way. Full numbers in
`outputs/backtest_<date>.{json,csv,md}`.

## Checkpoint log

<!-- CHECKPOINTS:START -->
| Date | Commit | What changed | Next |
|------|--------|--------------|------|
| 2026-10-12 | `fccfecf` | Front door Day 2: for each namespace (valuation, fundamentals, risk, factor, vol, sentiment), stockstalker.run.build_contract_sections reads fixtures/<namespace>/<TICKER>.json for the subject directly through that gate's existing load_contract, bypassing the screen-gate pattern entirely (which only matches a ticker in data/universe.txt, and the subject deliberately is not). Renders one section each in both the terminal and the markdown tear sheet. Today this fills real valuation and fundamentals sections for GULFOILLUB -- the only two satellites that have ever researched this company -- and reports risk/factor/vol/sentiment as not available with the exact reason (their fixtures are still keyed to RELIANCE/INFY/FORTIS from earlier integrations and land on Days 3-6), never a synthetic stand-in. sizing is left out of the loop entirely, documented rather than silently dropped: a sector-capped weight across the subject and its three lubricant peers is a sector bet, not a position size. Verified: 268/268 STOCKSTALKER tests pass (12 new), and the CLI was run by hand against GULFOILLUB (prints the two real sections plus four not-available lines, writes the matching markdown) and both error paths (unknown ticker, --live/--offline conflict). | Day 3 -- risk on the subject (monte-carlo-risk-lab): copy GULFOILLUB_NS.csv across, adapt mcsim.portfolio if hard-wired to RELIANCE, write STOCKSTALKER/fixtures/risk/GULFOILLUB.json with --contract in the v0.3 shape, record the Kupiec result |
| 2026-10-12 | `5a536bb` | Front door Day 1: python -m stockstalker.run --ticker GULFOILLUB --offline prints a price section (reusing screener.compute_signals/blended_score/liquidity_metrics, no new signal math) and a peer comparison table (GULFOILLUB, CASTROLIND, SOTL, GANDHAR -- trailing 1y return, 1y annualised volatility, 20d ADV) and writes outputs/tearsheet_<TICKER>_<date>.md. Trailing return/volatility are new pure functions guarded to return None/n-a below a full year of bars, though all four fixtures (GANDHAR shortest, ~2.8y) clear that window today. Subject stays out of data/universe.txt per NEXT_STEPS.md. Verified: 259/259 STOCKSTALKER tests pass (14 new), and the CLI was run by hand against GULFOILLUB (prints both tables, writes the markdown tear sheet) and against an error path (unknown ticker, --live/--offline conflict). | Day 2 -- contract sections: for each namespace (valuation, fundamentals, risk, factor, vol, sentiment), read fixtures/<namespace>/<TICKER>.json through that gate's load_contract and render one section each, with a one-line reason when missing; sizing left out on purpose |
| 2026-09-09 | `07e2431` | Integration day: shipped Stock Stalker v0.1.0 (screen + liquidity heatmap + CLI report). Verified end-to-end against fixtures before tagging - 137 tests pass, screener --offline produces schema/v1.json-valid output, report --offline renders both tables plus 3 heatmap PNGs, audit --offline finds no look-ahead. Bumped version out of dev (0.1.0.dev1 -> 0.1.0), added CHANGELOG.md, tagged v0.1.0 locally. Tag push to origin was rejected (HTTP 403 on refs/tags, branch push to main succeeded fine) - looks like the push credential here is scoped to branches only, not tags. Repo stays private per NEXT_STEPS.md ('ask before flipping public') - no live user to ask in this automated run, so left as-is. | reverse-dcf-engine Day 1 - shortlist 3 NSE mid-caps with written screening rationale |
| 2026-09-08 | `2a8bb73` | Day 9: stockstalker/audit.py checks that every indicator feeding the screen/backtest (sma, ema, rsi, macd histogram, obv, volume_zscore) is causal - its value at bar i must survive truncating the series at bar i, so a look-ahead regression fails the build. Two negative controls (centred rolling mean, shift(-1)) prove the checker actually fires. CI workflow and the daily EOD snapshot job were already shipped in earlier days; this closes the remaining Day 9 items (the audit pass and a limitations-section note on the audit's scope). 7 new tests, 137 total pass. Ran python -m stockstalker.audit --offline by hand against all 3 fixtures, clean, and wired the same command into ci.yml. | Day 9 complete (final day) - integration day next: read the v1 screen contract and ship Stock Stalker release v0.1 (screen + liquidity heatmap + CLI report) per projects.json |
| 2026-09-08 | `d9192ec` | Day 8: report.py renders a rich-table terminal report (ranked screen candidates + walk-forward-vs-buy-and-hold backtest) and writes a volume-at-price liquidity heatmap PNG per ticker to outputs/, reusing screener.build_screen/backtest.run_backtest and viz.liquidity.plot_liquidity_heatmap rather than new scoring or charting logic. 9 new tests, 130 total pass. Ran python -m stockstalker.report --offline by hand, confirmed the two tables print with real fixture numbers and 3 heatmap PNGs land in outputs/. | Day 9 - CI workflow, daily Actions EOD snapshot, ml-pipeline-audit pass, README limitations section |
| 2026-09-07 | `b9038a2` | Day 7: walk-forward long/flat backtest (stockstalker/backtest.py) tests the blended screen score against buy-and-hold on the 3 fixtures - long next-day only when the prior close's score clears 0.5, no shorting, no costs, 50-bar burn-in before the slowest indicator is defined. Reused screener.py's own compute_signals/blended_score so the walk-forward signal is provably the same math the live screen makes. Result reported straight: 2/3 tickers beat buy-and-hold but only by losing less during a decline - strategy lost money outright on 2/3 names and lost to buy-and-hold on the one that rose (mean -10.85% vs -23.40%). No edge claimed. 18 new tests, 121 total pass. Ran python -m stockstalker.backtest --offline by hand, confirmed json/csv/md written to outputs/ with real numbers. | Day 8 - report.py: terminal report (rich tables), chart files to outputs/. No server, no dashboard |
| 2026-09-07 | `d9c675a` | Day 6: screener.py blends trend/momentum/volume signals (YAML-configured weights in config/screen.yaml) into a ranked candidate list. Added momentum_score and volume_score alongside the existing trend_score, each a bounded [-1,1] snapshot. Writes outputs/screen_<date>.json (schema/v1.json contract), .csv, and .md, plus a terminal summary. 34 new tests, 102 total pass. Ran python -m stockstalker.screener --offline by hand against the 3 fixtures to confirm the CLI actually produces the files. | Day 7 - sanity check the screen against buy-and-hold on the fixture window, report results straight including if it loses |
| 2026-09-06 | `7e7f9d9` | Day 5: viz/liquidity.py volume-at-price heatmap - bins each day's close into equal-width price buckets, sums volume per bucket (conserves total), flags bins >=1.5x mean volume as high-activity zones, renders a single-hue horizontal bar heatmap with zones outlined in red to outputs/heatmap_<ticker>.png. Ran against all 3 fixtures and eyeballed the PNGs. 14 new tests, 68 total pass. | Day 6 - screener.py: YAML-configured rules combining trend/momentum/volume signals into a ranked candidate list (outputs/screen_<date>.csv + markdown report) |
| 2026-09-06 | `749054a` | Day 4: RSI/MACD momentum signals and OBV/volume z-score volume signals (momentum.py, volume.py) as pure functions, unit tested against fixtures and synthetic edge cases (flat, monotonic, spike series) | Day 5 - viz/liquidity.py: volume-at-price heatmap marking high-activity zones |
| 2026-09-06 | `5b4950c` | Day 3: SMA/EMA crossover trend signals (sma, ema, crossover_state, crossover_events, trend_score) as pure functions, unit tested against fixtures and synthetic series | Day 4 - signals/momentum.py (RSI, MACD) and signals/volume.py (OBV, volume z-score) |
| 2026-09-06 | `3a014ec` | Days 1-2: scaffold, v1 output contract, offline fixtures, and the provider interface over fixtures/yfinance/Alpha Vantage | Day 3 - SMA/EMA crossover signals as pure functions with unit tests |
<!-- CHECKPOINTS:END -->

## Limitations and what would make me wrong

- The ticker universe is today's list. Names that delisted or were removed are absent, so any historical result carries survivorship bias. Stated rather than corrected.
- Technical signals describe how a price has behaved, not what a business is worth. Nothing here is a valuation, and nothing here is a recommendation.
- The Alpha Vantage free tier is 25 requests/day. Live runs across a real universe are rate-limited by design, which is why the fixture path exists.
- Any backtest in this repo is in-sample unless the README says otherwise in that specific section.
- The screener's signal weights (`config/screen.yaml`) and each signal's internal blend (e.g. RSI/MACD 50/50 inside momentum) are hand-picked, not fit or optimized against anything. Day 7's walk-forward backtest against buy-and-hold (see Findings) found no clear edge — 2 of 3 tickers beat buy-and-hold, but only by losing less, and the strategy still lost to buy-and-hold on the one name that rose. Any future re-tuning of these weights against this same fixture window would be in-sample.
- The pipeline audit (`python -m stockstalker.audit`) only proves the indicators are causal — no future data leaks into a past bar's value. It says nothing about whether the screen's thresholds, weights, or the backtest's rule are any good; that question is still open per the two points above.
- The v0.7 valuation gate (`stockstalker.gates.valuation`) reads reverse-dcf-engine's contract for Gulf Oil Lubricants India (GULFOILLUB), a name that is not in this repo's 3-ticker fixture universe (RELIANCE, TATACHEM, CROMPTON). Running the real integration end to end today produces zero matches — the gate logic is exercised by tests against a synthetic contract keyed to a universe ticker, but no genuine valuation figure has actually been attached to a live candidate yet. That happens only once the two repos' universes overlap, or a satellite is re-run against a shared ticker.
- The v0.3 risk gate (`stockstalker.gates.risk`) reads monte-carlo-risk-lab's VaR/CVaR contract for RELIANCE, which *is* in this repo's universe, so `--risk-contract fixtures/risk/RELIANCE.json --risk-ticker RELIANCE` genuinely attaches to a live candidate rather than matching a synthetic stand-in. But the contract itself is only as good as monte-carlo-risk-lab's own model: that repo's README records that its Kupiec backtest rejects the 1-day parametric VaR at the 99% confidence level on this exact fixture (thin GBM tails understate real exceptions), and `var_95`/`cvar_95` here come from its historical (non-parametric) method specifically to avoid inheriting that failure — but the 99% figure is not in this contract at all, and a reader who needs it has to go read that repo directly.
- The v0.2 factor gate (`stockstalker.gates.factor`) reads fama-french-factor-model's FF5+momentum contract for RELIANCE — another genuine match, like v0.3's, not a synthetic stand-in. But the underlying regression is underpowered by that repo's own account: only 22 months overlap between this repo's OHLCV fixture window and Ken French's factor fixture, not enough to estimate up to seven parameters with any confidence, and it regresses INR closing prices against USD-denominated factors with no currency adjustment. All three of this repo's candidates come back with `significant: false` under every model that repo ran (plain-OLS and Newey-West alike) — read that as "underpowered," not as "the screen's edge is proven to be beta in disguise." See that repo's own README for the full caveat list.
- The v0.4 sizing gate (`stockstalker.gates.sizing`) reads markowitz-portfolio-optimizer's contract for RELIANCE.NS — a genuine match, like v0.3's and v0.2's, since that repo built its own fixtures from this repo's committed OHLCV history. But the number attached is not a diversified allocation: that repo's raw unconstrained max-Sharpe tangency portfolio on its 3-name universe is a 100% RELIANCE.NS corner solution, so the contract instead reports a sector-capped solve (50% cap) — RELIANCE.NS gets exactly 50%, with its own single-member sector ("Energy") as the binding constraint. Every ticker in that universe sits in its own sector, so the cap is mathematically identical to a plain position limit on RELIANCE.NS alone, not a genuine multi-name diversification constraint. And a less flattering number from that repo's own README: the sector-capped portfolio's Sharpe ratio is *worse* than the uncapped one (-0.83 vs -0.30) — forcing this "diversification" made risk-adjusted return worse, not better, on this fixture set. Read the 50% weight as one candidate's sizing gate output, not a recommended real-money allocation.
- The v0.5 sentiment gate (`stockstalker.gates.sentiment`) reads headline-sentiment-vs-price's contract for INFY.NS (Infosys), which is not in this repo's 3-ticker fixture universe (RELIANCE, TATACHEM, CROMPTON) — like v0.7's GULFOILLUB, not like v0.3/v0.2/v0.4/v0.6's genuine RELIANCE matches. Running the real integration end to end today produces zero matches — the gate logic is exercised by tests against a synthetic contract keyed to a universe ticker, but no genuine sentiment score has actually been attached to a live candidate yet. The contract itself also ships `"model": "vader"` rather than the `"finbert"` NEXT_STEPS.md originally envisioned, because that repo's sandbox has no `torch` installed; read any `score_7d` this gate attaches as a general-purpose lexicon score, not a finance-tuned one, until that repo's FinBERT path is actually exercised somewhere with network access and a cached model.
- The v0.8 fundamentals gate (`stockstalker.gates.fundamentals`) reads three-statement-model's contract for Gulf Oil Lubricants India (GULFOILLUB) — the same name v0.7's valuation gate already reads, since both satellites research the same company. GULFOILLUB is not in this repo's 3-ticker fixture universe (RELIANCE, TATACHEM, CROMPTON), so, like v0.7's and v0.5's integrations, the real end-to-end run produces zero matches; the gate logic is exercised by tests against a synthetic contract keyed to a universe ticker instead. The contract itself is real, not a placeholder: `fy3_revenue_cagr` (+15.39%), `fy3_ebit_margin` (12.82%) and `net_debt_ebitda_fy3` (-1.69, a net-cash position) come from that repo's actual 3-year linkage forecast on GULFOILLUB's real historical financials, and `balance_check` only reads `"passed"` because that repo's own balance-sheet assertion genuinely passed for every forecast year — it is not hardcoded.
- The front door's Day 2 contract sections (`stockstalker.run.build_contract_sections`) read each gate's `load_contract` directly against `fixtures/<namespace>/<TICKER>.json` for the subject ticker, bypassing the screen-gate pattern above entirely (that pattern only matches a ticker already in `data/universe.txt`, which the subject deliberately is not). Today that gives two real, filled sections for GULFOILLUB — `valuation` (reverse-dcf-engine) and `fundamentals` (three-statement-model), the only two satellites that have ever researched this company — and four honest "not available" lines for `risk`, `factor`, `vol` and `sentiment`, whose committed fixtures are still keyed to RELIANCE/INFY/FORTIS from earlier integrations. Those four fill in only once their own repos write a `GULFOILLUB.json` fixture, on NEXT_STEPS.md's Days 3–6. `sizing` is left out of the front door on purpose, not because of a missing fixture: markowitz-portfolio-optimizer's sector-capped weight is only meaningful across a screened universe of candidates competing for the same capital, and a sector cap across the subject plus its three lubricant peers would be a sector bet dressed up as a position size.

## Where this sits

Publishes the contract every satellite repo reads and extends:

```json
{
  "schema": "v1",
  "candidates": [
    {"ticker": "EXAMPLE.NS", "rank": 1, "score": 0.82,
     "signals": {"trend": 0.9, "momentum": 0.7, "volume": 0.85},
     "liquidity": {"adv_20d": 1234567, "spread_bps": 12},
     "factor": {"alpha_annual": -0.039, "alpha_t": -0.19, "significant": false,
                "loadings": {"mkt": 0.02, "smb": 0.10, "hml": -0.25}},
     "sizing": {"weight": 0.5, "method": "max_sharpe_ledoit_wolf",
                "constraint_binding": "Energy"},
     "sentiment": {"score_7d": 0.31, "headline_count_7d": 12, "model": "vader",
                   "coverage": "partial"}}
  ]
}
```

Satellites add keys under their own namespace — `factor`, `risk`, `sizing`, `sentiment`, `valuation`, `fundamentals` — rather than reshaping what already exists. Communication is by file, not by import, so any repo can be refactored without breaking the others.

## Exam mapping

Series XV ch.15 (technical analysis), ch.12.12 (measuring liquidity of equity shares); Series VIII (volume and open interest).

---

CLI only, by design. No dashboard, no server. Charts are written to `outputs/`.
