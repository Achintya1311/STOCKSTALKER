# Stock Stalker

The front door to a nine-repo equity research pipeline. One command —

```bash
python -m stockstalker.run --ticker GULFOILLUB --offline
```

— pulls together everything the other eight repos have ever found about one
stock (Gulf Oil Lubricants India) and prints it as a single tear sheet,
plus writes the same to `outputs/tearsheet_GULFOILLUB_<date>.md`. It also
runs a separate, smaller daily screen over three unrelated NSE names —
see "The screen is a separate, smaller thing" below for how the two relate.

**Status:** Complete (v0.9, Oct 2026). `python -m stockstalker.run --ticker GULFOILLUB` reads every module's findings for the note's stock.

## The front door

`python -m stockstalker.run --ticker <TICKER> --offline` (GULFOILLUB is the
default) prints, in this order:

1. **Price section.** The subject's own trend/momentum/volume score and
   20-day ADV — computed with the exact same `screener.compute_signals`,
   `blended_score` and `liquidity_metrics` functions the daily screen uses,
   so the number is provably the same math, not a lookalike. GULFOILLUB is
   deliberately not in `data/universe.txt` (see below), so this is that
   math run once, by hand, against the subject — the daily screen itself
   never produces it.
2. **Peer table.** GULFOILLUB against three listed lubricant peers —
   CASTROLIND, SOTL, GANDHAR — on trailing 1y return, 1y annualised
   volatility and 20d ADV. GANDHAR only has ~2.8 years of fixture history
   (IPO 2023-11-30); any stat needing a full year prints `n/a` for it
   rather than a shorter-window number under the same heading.
3. **Six contract sections**, one per satellite, each read straight from
   that repo's own file contract for GULFOILLUB — never through the
   screen-gate pattern (`stockstalker.gates.*`'s `apply_*_gate`), which
   only matches a ticker already in `data/universe.txt` and would never
   match the subject:

   | Section | From | What it is |
   |---|---|---|
   | `valuation` | [reverse-dcf-engine](https://github.com/Achintya1311/reverse-dcf-engine) | what growth, margin and reinvestment the market price already assumes |
   | `fundamentals` | [three-statement-model](https://github.com/Achintya1311/three-statement-model) | 3-year forecast revenue CAGR, EBIT margin, net debt/EBITDA, and a balance-sheet check |
   | `risk` | [monte-carlo-risk-lab](https://github.com/Achintya1311/monte-carlo-risk-lab) | simulated 1-day VaR/CVaR and max drawdown over a 20-day horizon |
   | `factor` | [fama-french-factor-model](https://github.com/Achintya1311/fama-french-factor-model) | factor-adjusted alpha and loadings against Indian (IIMA) factors |
   | `vol` | [implied-vol-surface](https://github.com/Achintya1311/implied-vol-surface) | options-implied ATM IV, 25-delta skew and term slope — unverified for GULFOILLUB, see Limitations |
   | `sentiment` | [headline-sentiment-vs-price](https://github.com/Achintya1311/headline-sentiment-vs-price) | 7-day headline sentiment score and coverage |

   `sizing` ([markowitz-portfolio-optimizer](https://github.com/Achintya1311/markowitz-portfolio-optimizer))
   is left out of the front door on purpose, not for lack of a fixture: a
   sector-capped weight across the subject and its three lubricant peers
   would be a sector bet dressed up as a position size, not a number
   anyone should act on.

   Four of those six are genuine matches against GULFOILLUB's real
   researched numbers (`valuation`, `fundamentals`, `risk`, `factor`). The
   other two render as honest absences, not placeholders: `sentiment` is a
   real zero (nothing in headline-sentiment-vs-price's ~50-headline corpus
   names GULFOILLUB), and `vol` prints "unverified" because this sandbox's
   network could not confirm whether GULFOILLUB even has an NSE option
   chain — see Limitations for both.
4. **Charts to `outputs/`** — three PNGs: GULFOILLUB vs. its three peers
   rebased to 100, drawdown from peak, and rolling 1-year annualised
   volatility. Pass `--no-charts` to skip them.
5. **The tear sheet itself** — `outputs/tearsheet_<TICKER>_<date>.md`,
   the same content as the terminal output, written every run.

Run `python -m stockstalker.run --help` for `--peers`, `--live`, `--config`
and the rest of the flags.

## The screen is a separate, smaller thing

`python -m stockstalker.screener`, `stockstalker.report` and
`stockstalker.backtest` run a daily trend/momentum/volume monitor over
three NSE names — RELIANCE, TATACHEM, CROMPTON — listed in
`data/universe.txt`. Earlier versions of this README called the screen
"the funnel" that narrows a universe down to the one name the rest of the
pipeline researches. That was never actually true, and this is the
correction: GULFOILLUB, the subject every satellite from `valuation`
through the eventual note is built around, was picked by hand against
written criteria — market cap band, thin analyst coverage, a sourceable
ten years of annual reports — recorded in
[`reverse-dcf-engine/research/shortlist.md`](https://github.com/Achintya1311/reverse-dcf-engine/blob/main/research/shortlist.md).
GULFOILLUB has never been in `data/universe.txt` and this screener has
never ranked it, scored it, or produced it as a candidate. The screen is a
monitor on its own small, unrelated universe — useful on its own terms
(see Findings) — not the process that chose the stock this repo's front
door, or the capstone note, is actually about.

## What this is

The spine of a nine-repo research pipeline. The screen above answers a
narrow question on its own three-ticker universe — which of those names is
behaving in a way worth a closer look. The front door above is the
different, larger thing: one command showing everything the pipeline
knows about the stock the capstone note is actually being written on.

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
supports a stronger claim either way.

### Day 8 — the same table with costs

The no-cost numbers above were never realistic: daily rebalancing pays STT
on every entry and exit. `backtest.py` now charges 0.1% STT per side,
0.015% stamp duty on the buy side only, and a `--slippage-bps` flag
(default 10) on every trade — Indian delivery-equity costs, not a made-up
haircut. Buy-and-hold pays the same schedule on its one entry and one exit,
so the comparison below is still apples-to-apples; it just barely moves the
buy-and-hold number, because that side trades twice in total instead of
roughly 150 times.

| Ticker | Strategy | Buy & hold | Edge |
|---|---|---|---|
| RELIANCE.NS | -10.45% | +4.76% | -15.21% |
| TATACHEM.NS | -1.32% | -39.60% | +38.27% |
| CROMPTON.NS | -41.49% | -36.31% | -5.18% |

Costs change the verdict, not just the margin: CROMPTON flips from
"beats buy-and-hold" to "loses to it" once its ~138 round trips each pay
their share of STT, stamp duty and slippage — a name that looked like a
wash before costs is a clear loser after them. Only 1 of 3 names still
beats buy-and-hold (down from 2 of 3), mean strategy return -17.75% vs.
mean buy-and-hold -23.72%. The daily-rebalancing style this screen implies
is considerably more expensive than the Day 7 numbers let on — read this as
the honest version of the Day 7 finding, not a separate result. Full
numbers for both tables, every run, in `outputs/backtest_<date>.{json,csv,md}`.

## Checkpoint log

<!-- CHECKPOINTS:START -->
| Date | Commit | What changed | Next |
|------|--------|--------------|------|
| 2026-10-13 | `581760a` | Front door Day 9 (final day, the release): README rewritten as the front door -- leads with the one command (python -m stockstalker.run --ticker GULFOILLUB --offline), a table of what each of the six contract sections means and which satellite it comes from with a link to each, and corrects a framing error every checkpoint note up to Day 8 carried: calling the daily screen 'the funnel' that narrows a universe down to the pipeline's one subject. That was never true -- GULFOILLUB was picked by hand against written criteria in reverse-dcf-engine/research/shortlist.md, has never been in data/universe.txt, and the screen (RELIANCE/TATACHEM/CROMPTON) has never ranked it. New 'The screen is a separate, smaller thing' section states this plainly and links the source of the real pick. CHANGELOG.md gained a v0.9 entry and pyproject.toml bumped 0.8.0 -> 0.9.0 -- this lands in pipeline order (v0.2-v0.8 all already shipped), so no out-of-sequence patch deviation. No code changed; this is a documentation day. Verified honestly: pytest 300 passed (1 deselected -- the live-network smoke test, which does reach the network in this sandbox but is excluded from the routine run to keep it fast and deterministic; a separate full run including it also passed 301/301), and python -m stockstalker.run --ticker GULFOILLUB --offline was run by hand end to end, all six contract sections, three charts and the tear sheet render exactly as before -- this day changed no behavior, only what the README claims about it. | equity-research-initiation Day 1 - business and industry structure, value chain, unit economics |
| 2026-10-13 | `be517f8` | Front door Day 8: backtest.py charges real Indian delivery-equity costs on every trade -- 0.1% STT per side, 0.015% stamp duty on the buy only, plus a --slippage-bps flag (default 10) -- via a new holdings_from_scores/trading_cost_series pair that marks entry/exit days off the same position.shift(1) long_flat_returns already uses, so the cost model can never drift from the signal it is costing. Buy-and-hold gets the identical one-round-trip cost schedule (buy_and_hold_return_with_costs), not a free pass, so 'edge with costs' stays a fair comparison instead of pitting a costed strategy against an uncosted benchmark. Re-ran the day-7 table: costs change the verdict, not just the margin -- CROMPTON flips from beating buy-and-hold to losing to it once its ~138 round trips each pay their share, so only 1 of 3 names still beats buy-and-hold (down from 2 of 3), mean strategy -17.75% vs buy-and-hold -23.72%. README's Findings section keeps the old no-cost Day 7 table unchanged and adds the Day 8 with-costs table right below it per NEXT_STEPS.md; Limitations section records the cost model's own simplifications (flat percentage, no spread/impact/partial fills) and that report.py's quick terminal screen still shows only the no-cost numbers. Verified honestly: 301/301 STOCKSTALKER tests pass (9 new -- holdings/cost-series unit tests, long_flat_returns_with_costs and buy_and_hold_return_with_costs behavior, backtest_ticker/run_backtest's new fields, the --slippage-bps CLI flag), and python -m stockstalker.backtest --offline plus python -m stockstalker.report --offline were both run by hand end to end against the real fixtures. | Day 9 - README rewritten as the front door: one command, what each section means, a link per satellite, limitations; correct the screen's claimed role (GULFOILLUB was hand-picked, not screener output); add a CHANGELOG entry; checkpoint with --status done --ship v0.9 (the release, no separate integration day) |
| 2026-10-12 | `b1c3301` | Front door Day 7: stockstalker.viz.charts writes three PNGs to outputs/ for GULFOILLUB from committed fixtures alone -- rebased-to-100 comparison against CASTROLIND/SOTL/GANDHAR (each series divided by its own first close, since GANDHAR's fixture starts 2023-11-30 versus the other three's 2014-07-31, with the legend naming each series' own start date rather than implying a shared window), drawdown-from-peak, and rolling 1y annualised volatility (the latter two for GULFOILLUB only -- NEXT_STEPS.md's 'subject vs peers' wording covers the rebased chart alone, and four peer drawdown/volatility lines would just redraw the existing peer table, not profile the name the note is about). stockstalker.run gained write_charts() and a --no-charts flag mirroring report.py's existing heatmap wiring, on by default, with the three PNGs listed in a new '## Charts' section of the tear sheet. Verified honestly: 292/292 STOCKSTALKER tests pass (21 new -- pure rebase/drawdown/volatility math, the three plot_* functions, write_charts' peer-failure and subject-failure paths, and the CLI's default-on/--no-charts behavior), and python -m stockstalker.run --ticker GULFOILLUB --offline was run by hand end to end -- all three PNGs render sensibly by eye (GANDHAR's shorter rebased line correctly starts partway through the chart) and the tear sheet lists them. | Day 8 - costs in backtest.py: 0.1% STT per side plus 0.015% stamp duty on the buy, plus a --slippage-bps flag (default 10); re-run the day-7 findings table with costs and replace the README numbers, keeping the old no-cost row for comparison |
| 2026-10-12 | `f8a0b20` | Front door Day 6 (absence day): sentiment.contract --ticker GULFOILLUB.NS against headline-sentiment-vs-price's ~50-headline RSS corpus returns a genuine zero (no ticker-table rule names GULFOILLUB) -- fixtures/sentiment/GULFOILLUB.json ships {score_7d: null, headline_count_7d: 0, model: vader, coverage: none} as a real result, not a placeholder, so the front door's sentiment section now fills for GULFOILLUB. vol stays unavailable, but the reason changed from generic 'no fixture' to an investigated 'unverified': a live NSE option-chain request from this sandbox returned the identical empty/blocked payload for GULFOILLUB and for RELIANCE (a name known to have real listed options), so the response proves the sandbox's network is blocked, not that GULFOILLUB lacks a chain. stockstalker.run.UNVERIFIED_CONTRACT_REASONS carries that distinction into the tear sheet by name. Both READMEs (STOCKSTALKER's) record the investigation; no code change was needed in headline-sentiment-vs-price or implied-vol-surface since both CLIs/providers already existed -- today only re-ran them against a new ticker. Verified: 272/272 STOCKSTALKER tests pass (3 new), CLI run by hand end to end (python -m stockstalker.run --ticker GULFOILLUB --offline renders the real sentiment section and the unverified vol line, writes the matching tear sheet). | Day 7 - charts to outputs/, PNG only: subject vs peers rebased to 100 (each from its own first common date, labelled), drawdown from peak, rolling 1y volatility |
| 2026-10-12 | `9484f75` | Front door Day 5: factors/gulfoillub.py (fama-french-factor-model) regresses GULFOILLUB's own monthly returns against IIM Ahmedabad's Indian factors instead of RELIANCE's Ken French ones - CAPM (IIMA MF alone), FF3 (+SMB/HML), FF3+WML, on 137 real overlapping months (2014-08 to 2025-12) versus RELIANCE's underpowered 22. IIMA has no RMW/CMA, so there is no FF5+Mom spec. Honest result: alpha is not significant under any spec, OLS or Newey-West, despite the much larger sample (FF3+WML: +10.64% annualized, t=+1.01 OLS / +1.20 NW); wml's loading (+0.011, t=+0.06) shows no detectable momentum tilt. to_contract() writes STOCKSTALKER/fixtures/factor/GULFOILLUB.json in the existing v0.2 shape (mf renamed to mkt, extra wml key passed through unchanged - gates.factor.load_contract was read first and only checks the four top-level keys, so no gate change was needed). STOCKSTALKER's front door now renders a real factor section for GULFOILLUB instead of 'not available'. Verified: 110/110 fama-french-factor-model tests pass (13 new), 270/270 STOCKSTALKER tests pass (1 new), both CLIs run by hand end to end (factors.gulfoillub --contract and stockstalker.run --ticker GULFOILLUB --offline). | Day 6 - absence day, sentiment and vol: run sentiment.contract --ticker GULFOILLUB.NS against the committed corpus (expect zero headlines) and check whether GULFOILLUB is an NSE F&O underlying for a vol contract; if the check can't be made from this sandbox, say 'unverified', not 'no options' |
| 2026-10-12 | `9004786` | Front door Day 4: factors/iima.py (fama-french-factor-model) loads IIM Ahmedabad's committed Indian four-factor CSV (SMB/HML/WML/MF/RF, percent -> decimal, YYYY-MM -> PeriodIndex), the free Indian benchmark GULFOILLUB's own regression needs instead of USD Ken French factors. NEXT_STEPS.md's 'drop NA rows before MF starts' undersold the file: 1993-10 is missing MF/RF as expected, but 1994-11 separately drops SMB/HML/WML -- both rows (2 of 387) are dropped via dropna across all five columns, and that repo's README corrects the original plan's description rather than leaving it. MF is documented by IIMA as already a market excess return, so it is not reduced by RF a second time. No STOCKSTALKER changes this day -- this is purely a fama-french-factor-model loader, the GULFOILLUB regression and its factor contract land on Day 5. Verified: 97/97 fama-french-factor-model tests pass (8 new), including known-value pins on the first kept row (1993-11) and the last row (2025-12) against the committed CSV. | Day 5 -- GULFOILLUB factor regression on IIMA factors (CAPM, FF3, FF3+WML, Newey-West), monthly returns 2014-08 to 2025-12 (~137 months vs RELIANCE's 22); write STOCKSTALKER/fixtures/factor/GULFOILLUB.json in the v0.2 shape (add a wml loading only if gates.factor.load_contract accepts extra keys, else update the gate and its tests in the same commit) |
| 2026-10-12 | (this commit) | Front door Day 3: monte-carlo-risk-lab's mcsim.portfolio was never hard-wired to RELIANCE -- --fixture already took any OHLCV CSV -- so no code change was needed there, only a copied-in fixtures/ohlcv/GULFOILLUB_NS.csv and a re-run against it. Writes STOCKSTALKER/fixtures/risk/GULFOILLUB.json in the existing v0.3 shape, so the front door's risk section for GULFOILLUB is now a genuine fixture match, same as valuation and fundamentals. Honest result, worse than RELIANCE's own v0.3 integration: the Kupiec test rejects the parametric 1-day VaR at both 95% and 99% confidence on GULFOILLUB's ~11-year fixture (RELIANCE's ~2-year fixture only failed at 99%) -- more history gave the test more power to show the same Gaussian-tails gap Day 5 already flagged, not a different underlying model, and both repos' READMEs record this plainly. Verified: 156/156 monte-carlo-risk-lab tests pass (1 new), 269/269 STOCKSTALKER tests pass (1 new), and both CLIs (mcsim.portfolio --contract and stockstalker.run --ticker GULFOILLUB --offline) were run by hand end to end, confirming the tear sheet's risk section now renders real numbers instead of 'not available'. | Day 4 -- Indian factors (fama-french-factor-model): factors/iima.py loads the committed IIMA CSV (percent -> decimal, YYYY-MM -> month-end, MF already excess so no second RF subtraction); tests pin a known row |
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
- The front door's contract sections (`stockstalker.run.build_contract_sections`) read each gate's `load_contract` directly against `fixtures/<namespace>/<TICKER>.json` for the subject ticker, bypassing the screen-gate pattern above entirely (that pattern only matches a ticker already in `data/universe.txt`, which the subject deliberately is not). As of Day 5, that gives four real, filled sections for GULFOILLUB — `valuation` (reverse-dcf-engine), `fundamentals` (three-statement-model), `risk` (monte-carlo-risk-lab, whose `mcsim.portfolio` was re-run against a copied-in GULFOILLUB fixture rather than RELIANCE's) and `factor` (fama-french-factor-model, regressed against IIMA's Indian factors rather than RELIANCE's Ken French ones) — and two honest "not available" lines for `vol` and `sentiment`, whose committed fixtures are still keyed to RELIANCE/INFY from earlier integrations. Those two fill in only once their own repos write a `GULFOILLUB.json` fixture, on NEXT_STEPS.md's Day 6. `sizing` is left out of the front door on purpose, not because of a missing fixture: markowitz-portfolio-optimizer's sector-capped weight is only meaningful across a screened universe of candidates competing for the same capital, and a sector cap across the subject plus its three lubricant peers would be a sector bet dressed up as a position size.
- GULFOILLUB's real `risk` section (Day 3) is a worse Kupiec result than RELIANCE's own v0.3 integration: the parametric 1-day VaR is rejected at both 95% and 99% confidence on GULFOILLUB's ~11-year fixture, where RELIANCE's ~2-year fixture only failed at 99%. The front door renders the four risk numbers (`var_95`, `cvar_95`, `max_dd_sim`, `horizon_days`) but not the Kupiec verdict itself — a reader relying only on this tear sheet has no way to see that the model backing those numbers is rejected at both confidence levels; see monte-carlo-risk-lab's own README for the full backtest.
- GULFOILLUB's real `factor` section (Day 5) is a genuinely different regression from RELIANCE's screen-gate one, not just a different ticker: 137 overlapping months against RELIANCE's underpowered 22, IIMA's Indian factors instead of Ken French's USD ones, and FF3+WML instead of FF5+Mom (IIMA has no RMW/CMA). The honest result is still an insignificant alpha (`alpha_t` ≈ +1.01, OLS) despite the much larger sample — the front door renders `alpha_annual`, `alpha_t`, `significant` and the `loadings` dict (including a `wml` key RELIANCE's own FF5+Mom contract has never carried) but not the Newey-West-corrected t-stat or the diagnostics tests fama-french-factor-model's own README records; a reader who needs those has to go read that repo directly, the same gap the `risk` section above already has for its Kupiec verdict.
- Day 6 is an absence day, and both absences are real, not placeholders. `sentiment` is now filled for GULFOILLUB with a genuine zero: `python -m sentiment.contract --ticker GULFOILLUB.NS` against headline-sentiment-vs-price's ~50-headline Economic Times RSS snapshot returns `{"score_7d": null, "headline_count_7d": 0, "model": "vader", "coverage": "none"}`, because that repo's ticker table (`sentiment.tickers`) has no rule naming GULFOILLUB at all — a deliberately narrow, closed lookup (see that repo's README), not a filter that happened to exclude it. A count of zero from a ~50-headline single-source snapshot says nothing about this stock's real news coverage; it is a fact about the corpus, not about the company. `vol` stays unavailable, but the reason changed from "no fixture yet" to an investigated "unverified": a live check against NSE's own option-chain endpoint (`volsurface.chain.NSEChainProvider`) was run from this sandbox for both GULFOILLUB and RELIANCE, and both came back with the identical empty `{}` payload after a 403 on the cookie warm-up — RELIANCE is known to have listed NSE options, so an empty response proves the sandbox's network is blocked here, not that GULFOILLUB has no option chain. `stockstalker.run.UNVERIFIED_CONTRACT_REASONS` carries that distinction into the tear sheet by name rather than letting the generic "fixture not found" line imply a negative that was never actually checked.
- Day 7's three charts (`stockstalker.viz.charts`, written to `outputs/` by `stockstalker.run` unless `--no-charts`) are deliberately scoped narrower than "subject vs peers" everywhere: only the rebased comparison plots all four names, because NEXT_STEPS.md's "subject vs peers" qualifier sits on that one chart alone — drawdown and rolling volatility are GULFOILLUB only, a risk profile of the name the note is about, not a four-line reprise of the peer table. The rebased comparison is not one shared start date either: each series is divided by its own first close, so CASTROLIND and SOTL (both committed back to 2014-07-31, the same day as GULFOILLUB) rebase from day one of the subject's own history, but GANDHAR (IPO 2023-11-30) rebases from its own much later first day — the legend names each series' own start date so a ~3-year GANDHAR line is never misread as spanning the same ~11 years as the other three. These fixtures were pulled with `yfinance`'s `auto_adjust=True`, which already folds dividends into every close, so these are rebased total-return-ish series, not pure price.
- Day 8's trading costs (`backtest.STT_RATE`, `backtest.STAMP_DUTY_RATE`, `--slippage-bps`) are a flat percentage of position value charged on each entry and exit, not a simulated order-book fill. There is no separate bid-ask spread, no market-impact model, and no partial fills — real execution on ~140-190 round trips a year on these small/mid-cap names would plausibly be worse, not better, than this estimate. `stockstalker.report`'s backtest table still shows only the no-cost numbers (it calls the same `run_backtest`, but renders `strategy_return`/`buy_and_hold_return`, not the `_with_costs` fields) — the cost-adjusted view only exists in this README's Findings section and in `outputs/backtest_<date>.{json,csv,md}`, not in the quick terminal screen.
- Day 9 is a documentation day, not a code day — no module in `stockstalker/` changed. It corrects a framing error this README carried since Day 1 of the front-door project (and, before that, every earlier checkpoint note): calling the screen "the funnel" that narrows a universe down to the pipeline's one subject. That was never what happened. GULFOILLUB was chosen by hand in `reverse-dcf-engine/research/shortlist.md` against written criteria, and the screen's own 3-ticker universe (RELIANCE, TATACHEM, CROMPTON) has no overlap with it at all — a reader who took the old wording literally would have incorrectly concluded the screen ran over a larger universe at some point and produced GULFOILLUB as its output. It did not. This correction does not change any number in this README; it changes what the numbers are claimed to be downstream of.

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
