# Stock Stalker

Educational research on historical data. Not investment advice. Not a SEBI-registered research analyst.

**Question:** does the daily trend/momentum/volume screen beat simply buying and holding, once realistic Indian delivery-equity trading costs are included?
**Method:** a walk-forward long/flat backtest — long the next day only when yesterday's blended screen score clears 0.5, no shorting — over three NSE names (RELIANCE, TATACHEM, CROMPTON), 14 Nov 2024 to 4 Sep 2026 (450 tested days each), costed at 0.1% STT per side, 0.015% stamp duty on buys, and 10bps slippage.
**Finding (Day 58, the honest one):** only 1 of 3 names beats being long this often, on these days, vs. being long the same number of days at random — down from "2 of 3 beat 100%-exposure buy-and-hold" (Day 7), and down to 1 of 3 vs. buy-and-hold once costs are included too (mean −17.75% vs. −23.72%, Day 8). Full tables in Findings below.
**Chart:** `outputs/tearsheet_GULFOILLUB_<date>.md` lists the three charts `stockstalker.run` writes to `outputs/` — GULFOILLUB vs. peers rebased to 100, drawdown from peak, rolling 1y volatility.
**Reproduce:** `python -m stockstalker.backtest --offline` (the finding above) or `python -m stockstalker.run --ticker GULFOILLUB --offline` (the front door below).

**One name, three things.** "Stock Stalker" covers three separate pieces of work:

| Part | Scope | Status |
|---|---|---|
| **Screen** | 3 names (RELIANCE, TATACHEM, CROMPTON); 1 of 3 held up against random same-size exposure | done; a small monitor, not a universe screen |
| **Tear sheet** | any NSE stock, one command (`python -m stockstalker.run --ticker <TICKER> --live`) | done (v0.9); verified end to end on 3 names |
| **Lab** | separate repo, [`stockstalker-lab`](https://github.com/Achintya1311/stockstalker-lab), 213-stock NSE F&O universe | testing phase; train-split results only |

**Evidence** (lab reports as of 26 Oct 2026, 2015-2020 train split only; the lab re-runs them, so the linked files win over these numbers; nothing here has been checked on unseen years yet):

- [`evidence_train.md`](https://github.com/Achintya1311/stockstalker-lab/blob/main/reports/evidence_train.md): some one-day rules beat the market line even after correcting for how many rules were tried (SPA p < 0.001 bearish, i.e. none of 2,000 bootstrap draws, and p = 0.003 bullish). On the one-week horizon none cleared the 5% level (p = 0.100 and 0.540).
- [`train_leaderboard.md`](https://github.com/Achintya1311/stockstalker-lab/blob/main/reports/train_leaderboard.md): every trial ranked; 9 of 125 clear the many-trials bar (t ≥ 4.25), all on the one-day horizon.
- [`champion_v1_train.md`](https://github.com/Achintya1311/stockstalker-lab/blob/main/reports/champion_v1_train.md): this repo's own blended screen score, run on the full F&O universe, shows no edge: within 0.74 points of the market line on all four horizon/side tables, with a negative move after costs on all four.
- [`corporate_actions_check.md`](https://github.com/Achintya1311/stockstalker-lab/blob/main/reports/corporate_actions_check.md): data check. The detector finds 3 candidate events in the dataset; 1 is confirmed, 1 is plausible and 1 is unexplained.

**Which stock each module was verified on.**

| Module | Verified on | Why that stock |
|---|---|---|
| Screen and backtest | RELIANCE, TATACHEM, CROMPTON | the screen's own fixture universe (`data/universe.txt`) |
| Price-only sections (`risk`, `factor`, `vol`, `sizing`) | RELIANCE (`risk` and `factor` also GULFOILLUB) | they need only prices, and RELIANCE is the one name in both the screen universe and those satellites' fixtures |
| Fundamentals (`fundamentals`) and the full 10-year `valuation` | GULFOILLUB | they need ten years of annual-report data entered by hand, which exists for this one name only; other tickers get a shorter reverse DCF run live from 4-5 years of yfinance financials (see the RELIANCE and CASTROLIND tear sheets in `verification/tearsheets/`) |

The split follows the data: price history is free for any NSE stock, but driver-based fundamentals were built by hand for a single company, so the fundamentals section stays GULFOILLUB-only rather than showing made-up numbers for others.

**What it is, what held up, what failed.**

| Part | What it is | What held up | What failed |
|---|---|---|---|
| Screen | a daily trend/momentum/volume score on 3 names, tested long/flat walk-forward | TATACHEM's chosen days beat 90% of 2,000 random same-size exposures (Day 58); with three names, one result that high happens by chance about 27% of the time | RELIANCE (38th percentile) and CROMPTON (5th) did not; after costs only 1 of 3 beats buy-and-hold, mean −17.75% vs. −23.72% (Day 8) |
| Tear sheet | one command that gathers price, risk, factor, valuation, options and sentiment sections for one stock from the six sibling repos | runs end to end on RELIANCE, CASTROLIND and GULFOILLUB, tear sheets committed in `verification/tearsheets/` | fundamentals exist for GULFOILLUB only; its parametric VaR is rejected by the Kupiec test at 95% and 99%; its factor alpha is not significant (t ≈ +1.01) |
| Lab | the same kinds of rules tested on 213 F&O stocks with a market line and many-trials corrections | some one-day rules beat the market line on 2015-2020 train data after the SPA correction | nothing on the one-week horizon; this repo's own blended score shows no edge at scale; nothing yet checked on unseen years |

**Reproduce:**

```bash
uv venv && source .venv/bin/activate
uv pip install -e . pytest
pytest                                                   # 447 passed, 2 skipped on 26 Oct 2026
python -m stockstalker.backtest --offline                # the screen findings (Days 7, 8, 58)
python -m stockstalker.run --ticker GULFOILLUB --offline # the front door from committed fixtures
```

The front door to an eight-repo equity research pipeline (this repo plus seven research repos; the separate stockstalker-lab is not counted). One command builds
a tear sheet for any NSE stock —

```bash
python -m stockstalker.run --ticker <TICKER> --live
```

— price signals, risk, factor exposure, a reverse DCF from public
financials, options for F&O stocks and headline sentiment, falling back
from a committed fixture to a live run against the sibling repo for any
ticker that has none, and prints it as a single tear sheet, writing the
same to `outputs/tearsheet_<TICKER>_<date>.md`. Verified end to end,
fix-phase Day 25, for RELIANCE (F&O large-cap), CASTROLIND (non-F&O
mid-cap) and GULFOILLUB (the hand-researched note's subject, from
committed fixtures) — tear sheets committed as evidence at
`verification/tearsheets/`. The three-statement model stays driver-based
by hand for GULFOILLUB only; every other ticker prints that scope note
instead of a fabricated fundamentals section. It also runs a separate,
smaller daily screen over three unrelated NSE names — see "The screen is
a separate, smaller thing" below for how the two relate.

**Status:** Complete (v0.9, Oct 2026). `python -m stockstalker.run --ticker <ANY> --live` reads every module's live or committed findings for that stock; `--offline` (GULFOILLUB is the default) reads the original hand-researched fixtures.

*Educational research on historical data. Not investment advice. Not a SEBI-registered research analyst.*

## The front door

Each of the six satellite sections, which repo it comes from, what it means for GULFOILLUB and why `sizing` is left out: [`docs/front-door.md`](docs/front-door.md). Run `python -m stockstalker.run --help` for the flags.

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

Growing this list to a real, point-in-time NSE F&O universe (the monthly
`fo_mktlots.csv` snapshot plus history from the F&O and equity bhavcopy,
survivorship-checked) is lab-phase work in `stockstalker-lab`, not
something this repo does on its own — see `PLAN.md` §3 and D6 in the
hub's `CRITIQUES.md` for why point-in-time matters here.

## What this is

The spine of an eight-repo research pipeline. The screen above answers a
narrow question on its own three-ticker universe — which of those names is
behaving in a way worth a closer look. The front door above is the
different, larger thing: one command showing everything the pipeline
knows about any NSE stock, not only the one the capstone note is actually
being written on.

## Honest status

This repo existed as a single empty commit for over a year while the project was listed on a CV. It is being rebuilt properly, in the open, one day at a time. The checkpoint log below is the real history — no backdating, no squashing it into one heroic commit.

What actually works is whatever the log says works. Anything above that line is intent.

## Correctness gate

`python -m stockstalker.screener --offline` produces a ranked CSV and a readable terminal report from committed fixtures alone, with output conforming to `schema/v1.json`, and `pytest` green.

Until that passes, this is a scaffold.

## Data sources

Every source is free. This project never requires a paid tier, a subscription, or a funded account.

- **yfinance** — daily OHLCV for NSE tickers, no key required. The only provider any default or `--live` code path actually selects today
- **Alpha Vantage** — implemented and tested (`AlphaVantageProvider`), free tier, 25 requests/day, key read from `.env` and never committed, but not wired into any default path, CLI flag, or workflow yet — nothing currently runs `--provider alphavantage`
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
~450 tradeable days once each ticker clears its 50-bar burn-in (14 Nov 2024 to 4 Sep 2026; `stockstalker.backtest` prints the window per ticker).

| Ticker | Strategy | Buy & hold | Edge |
|---|---|---|---|
| RELIANCE.NS | -1.85% | +5.19% | -7.04% |
| TATACHEM.NS | +4.62% | -39.34% | +43.96% |
| CROMPTON.NS | -35.32% | -36.05% | +0.73% |

2 of 3 names beat 100%-exposure buy-and-hold, but only by losing less during
a steep decline: the strategy still lost money outright on TATACHEM and
CROMPTON, and lost to buy-and-hold on RELIANCE, the one name that actually
went up. Mean strategy return -10.85% vs. mean buy-and-hold -23.40% (mean
edge +12.55% ± stderr 15.86%, n=3 — three tickers is a wide error bar, not a
significance claim). Read this as "doesn't obviously do worse than being
long," not as validated edge — three tickers over one overlapping two-year
window is not a sample that supports a stronger claim either way.

### Day 58 — the same days, against being long this often at random

Beating 100%-exposure buy-and-hold only answers "better than being long
every day?" A strategy that is long 42% of days (RELIANCE), 36% (TATACHEM)
or 31% (CROMPTON) could beat that just by being out of the market during a
decline — not by picking good days. The honest comparison is against being
long that *same number* of days, chosen at random, not against being long
every day. `backtest.random_exposure_returns` draws 2,000 random same-size
subsets of each ticker's own tested window and compounds each:

| Ticker | Days long / tested | Strategy (no cost) | Random-exposure mean ± std | Beats random | Percentile |
|---|---|---|---|---|---|
| RELIANCE.NS | 188/450 | -1.85% | +2.73% ± 14.05% | no | 38th |
| TATACHEM.NS | 163/450 | +4.62% | -15.06% ± 15.35% | yes | 90th |
| CROMPTON.NS | 138/450 | -35.32% | -11.85% ± 15.66% | no | 5th |

Only **1 of 3** beats being long this often, on these days, vs. being long
this often at random — down from "2 of 3 beat buy-and-hold" above, and this
is the harder, more honest number. TATACHEM's Day 7 edge survives this check
(90th percentile of 2,000 random same-length exposures): its specific days
were better than most random picks of the same count. That is one name of
three, though: with three names, at least one landing at the 90th percentile
or better happens by chance about 27% of the time (1 − 0.9³), so on its own
it doesn't separate a good rule from luck. CROMPTON's
Day 7 "beat buy-and-hold" was the opposite of what it looked like — its
actual days rank in the bottom 5% of random same-length exposures, i.e. the
screen picked *worse* days than chance would, and it only "beat" buy-and-hold
because 138/450 days long was a favorable amount of exposure during this
ticker's decline, not because the screen chose which 138. RELIANCE's loss to
buy-and-hold also isn't distinguishable from chance (38th percentile — a
below-average but unremarkable random draw). Read "2 of 3 beat buy-and-hold"
and "1 of 3 beats random exposure" as two different, both-true findings
about the same backtest, not a contradiction: the first is about full
exposure, the second is about the specific days chosen given the same amount
of exposure. Full numbers in `outputs/backtest_<date>.{json,csv,md}`.

### Day 8 — the same table with costs

The no-cost numbers above were never realistic: daily rebalancing pays STT
on every entry and exit. `backtest.py` now charges 0.1% STT per side,
0.015% stamp duty on the buy side only, and a `--slippage-bps` flag
(default 10) on every trade — the two largest Indian delivery-equity
taxes (STT and stamp duty) plus a slippage allowance, not a made-up haircut. Exchange, SEBI,
GST and depository charges are not modelled, so these after-cost numbers
are optimistic (see `docs/limitations.md`). Buy-and-hold pays the same schedule on its one entry and one exit,
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

### Day 85 — the same rule families, tested at scale in the lab

The two findings above are a 3-name, in-sample monitor result — useful on
its own small universe, but not a test. The same rule families (trend,
momentum, reversal, breakout and open-interest signals, among others) are
now evaluated properly in
[`stockstalker-lab`](https://github.com/Achintya1311/stockstalker-lab): a
213-stock NSE F&O universe, a market-line edge (hit rate over the base
rate of the market itself rising or falling), stationary block-bootstrap
95% intervals over dates, and a many-trials correction (Hansen's SPA test
across every trial of a horizon/side, plus StepM and the model confidence
set) so a result can't just be the best of many random-looking rules.
Full numbers, every trial, every horizon and side:
[`stockstalker-lab/reports/evidence_train.md`](https://github.com/Achintya1311/stockstalker-lab/blob/main/reports/evidence_train.md).

On the 2015–2020 train split, that report's SPA test rejects "no rule
beats the market line" for the day horizon on both sides (bearish and
bullish). On the bearish day side it names several of the lab's own rule
families StepM finds individually superior at the 10% level, including
`e2a-day`, `d01c-day`, `a02-extreme-day-reversal-day` and
`a09-gap-fade-day`, alongside several trend/momentum rules; on the
bullish day side it names fewer, including `d01c-day` and
`t04-connors-rsi2-day`. None of these are this repo's own screen or its
signal set — the lab evaluates its own, separate rule catalog. On the
week horizon, both sides fail to reject "no rule beats the market line":
the report's own SPA p-values are not small and it names no rule as
StepM-superior on either week side. The exact rule list, trial counts,
edges and intervals live in the report itself, not copied here by hand,
since the lab's own routine can re-run and update that report on a cadence
this one doesn't track.

**This is a train-split result, not a validated one.** The lab's own
sealed/unsealed design holds 2023–Jul 2026 out until a version is formally
unsealed; nothing above has been checked against unseen years, and a rule
that survives the 2015–2020 trials could still fail there. No pick, score
or hit rate is published by this repo or this section — the lab's own
scoreboard, where one exists, is the only public directional output this
portfolio carries (see `PLAN.md` rule 1).

## Limitations and what would make me wrong

- The ticker universe is today's list. Names that delisted or were removed are absent, so any historical result carries survivorship bias. Stated rather than corrected.
- Technical signals describe how a price has behaved, not what a business is worth. Nothing here is a valuation, and nothing here is a recommendation.
- The Alpha Vantage free tier is 25 requests/day. Live runs across a real universe are rate-limited by design, which is why the fixture path exists.
- Any backtest in this repo is in-sample unless the README says otherwise in that specific section.
- The screener's signal weights (`config/screen.yaml`) and each signal's internal blend (e.g. RSI/MACD 50/50 inside momentum) are hand-picked, not fit or optimized against anything. Day 7's walk-forward backtest against buy-and-hold (see Findings) found no clear edge — 2 of 3 tickers beat buy-and-hold, but only by losing less, and the strategy still lost to buy-and-hold on the one name that rose. Day 58's exposure-matched baseline (see Findings) is harder on the same backtest: only 1 of 3 beats being long this often, on these days, vs. being long the same number of days at random — CROMPTON's Day 7 "beat buy-and-hold" ranks in the bottom 5% of random same-length exposures, i.e. its 138 chosen days were worse than a random 138 days, not better. Any future re-tuning of these weights against this same fixture window would be in-sample.
- The pipeline audit (`python -m stockstalker.audit`) only proves the indicators are causal — no future data leaks into a past bar's value. It says nothing about whether the screen's thresholds, weights, or the backtest's rule are any good; that question is still open per the two points above.
- Module-by-module and per-day limitations (each gate's real or synthetic match, GULFOILLUB's parametric VaR rejected by the Kupiec test at both 95% and 99%, the flat trading-cost model, the any-stock verification on three tickers) are kept in full in [`docs/limitations.md`](docs/limitations.md).

## Checkpoint log

New checkpoints land in the table below; every earlier entry (Sep to Oct 2026) is in [`CHANGELOG.md`](CHANGELOG.md#checkpoint-log-moved-from-the-readme-on-25-oct-2026).

<!-- CHECKPOINTS:START -->
| Date | Commit | What changed | Next |
|------|--------|--------------|------|
<!-- CHECKPOINTS:END -->

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

Series XV ch.15 (technical analysis), ch.12.12 (measuring liquidity of equity shares); Series VIII (volume). Open interest is not computed by this repo — that is `implied-vol-surface`'s option-chain territory.

---

CLI only, by design. No dashboard, no server. Charts are written to `outputs/`.
