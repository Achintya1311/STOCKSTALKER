# Stock Stalker

Screens the NSE universe down to a shortlist worth researching properly, using trend, momentum, volume and liquidity signals. Command-line only: arguments in, ranked candidates and chart files out.

**Status:** Last checkpoint 2026-09-08 · Next: Day 9 - CI workflow, daily Actions EOD snapshot, ml-pipeline-audit pass, README limitations section

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

## Where this sits

Publishes the contract every satellite repo reads and extends:

```json
{
  "schema": "v1",
  "candidates": [
    {"ticker": "EXAMPLE.NS", "rank": 1, "score": 0.82,
     "signals": {"trend": 0.9, "momentum": 0.7, "volume": 0.85},
     "liquidity": {"adv_20d": 1234567, "spread_bps": 12}}
  ]
}
```

Satellites add keys under their own namespace — `factor`, `risk`, `sentiment`, `valuation`, `fundamentals` — rather than reshaping what already exists. Communication is by file, not by import, so any repo can be refactored without breaking the others.

## Exam mapping

Series XV ch.15 (technical analysis), ch.12.12 (measuring liquidity of equity shares); Series VIII (volume and open interest).

---

CLI only, by design. No dashboard, no server. Charts are written to `outputs/`.
