# Changelog

## v0.9 one-ticker front door (package v0.9.0) — 2026-10-13

One-ticker front door: every satellite module's view of GULFOILLUB in one tear
sheet. The stockstalker-front-door project (hub project 9) finished its 9-day
plan in pipeline order — v0.2 through v0.8 are all already shipped — so the
package version bumps cleanly from 0.8.0 to 0.9.0, no out-of-sequence patch
needed.

**Ships (across Days 1-8, this release just closes the project out):**
- `stockstalker.run` — `python -m stockstalker.run --ticker GULFOILLUB
  --offline` prints a price section (the screen's own
  `compute_signals`/`blended_score`/`liquidity_metrics`, run once against the
  subject), a peer table (CASTROLIND, SOTL, GANDHAR), six contract sections
  read directly from each satellite's file contract for GULFOILLUB (bypassing
  the screen-gate pattern, which only matches tickers already in
  `data/universe.txt`), three charts to `outputs/` (rebased comparison,
  drawdown, rolling volatility), and a markdown tear sheet
  (`outputs/tearsheet_<TICKER>_<date>.md`).
- Real GULFOILLUB fixtures and contracts in four satellites that previously
  only had RELIANCE/INFY data: `fixtures/risk/GULFOILLUB.json`
  (monte-carlo-risk-lab, re-run against a copied-in GULFOILLUB price fixture),
  `fixtures/factor/GULFOILLUB.json` (fama-french-factor-model, regressed
  against IIM Ahmedabad's Indian factors instead of Ken French's), and
  `fixtures/sentiment/GULFOILLUB.json` (headline-sentiment-vs-price, a
  genuine zero-headline result). `valuation` and `fundamentals` already had
  real GULFOILLUB contracts from v0.7 and v0.8; this release is what first
  reads them by ticker instead of through the screen-gate non-match path.
- `backtest.py` — real Indian delivery-equity trading costs (0.1% STT per
  side, 0.015% stamp duty on the buy, a `--slippage-bps` flag) on every trade
  in the Day 7 walk-forward backtest, applied identically to the
  buy-and-hold benchmark so the costed comparison stays fair.
- This README, rewritten as the front door: one command, what each of its
  sections means and where it comes from, a link to every satellite, and the
  corrected claim about how GULFOILLUB was actually chosen (see below).

**Verified before tagging:**
- `pytest` — 301 passed, 0 skipped
- `python -m stockstalker.run --ticker GULFOILLUB --offline` — run by hand
  end to end; all six contract sections render (four genuine matches, two
  honest absences), three charts write to `outputs/`, the tear sheet writes
  correctly
- `python -m stockstalker.backtest --offline` and `python -m
  stockstalker.report --offline` — run by hand against the real fixtures

**Correction, not a new finding:** every checkpoint note up to and including
Day 8 described the screen as "the funnel" that narrows a universe down to
the pipeline's one subject. That framing was never accurate — GULFOILLUB was
picked by hand against written criteria in
`reverse-dcf-engine/research/shortlist.md`, has never been in
`data/universe.txt`, and the screen has never ranked it or produced it as a
candidate. The screen is a monitor on its own separate 3-ticker universe
(RELIANCE, TATACHEM, CROMPTON); the README now says so plainly. No code or
number in this repo changed because of this correction — only what the
numbers are claimed to be downstream of.

## v0.8 fundamentals gate (package v0.8.0) — 2026-10-11

Fundamental quality gate on survivors. three-statement-model finished its 8-day plan
in pipeline order this time — v0.2 (fama-french-factor-model), v0.3 (monte-carlo-
risk-lab), v0.4 (markowitz-portfolio-optimizer), v0.5 (headline-sentiment-vs-price),
v0.6 (implied-vol-surface) and v0.7 (reverse-dcf-engine) are all already shipped, so
unlike every integration since v0.3, there is no out-of-order deviation to record:
the package version bumps cleanly from 0.7.5 straight to 0.8.0.

**Ships:**
- `stockstalker.gates.fundamentals` — reads three-statement-model's file contract
  (`{"fundamentals": {"fy3_revenue_cagr", "fy3_ebit_margin", "net_debt_ebitda_fy3",
  "balance_check"}}`, written by that repo's new `python -m model.statements
  --contract ...`, requires `--forecast-years >= 3` and a passing balance check) and
  attaches it to the one screen candidate whose ticker matches, under the
  `fundamentals` key `schema/v1.json` already reserves. Every other candidate passes
  through unchanged; a ticker outside the current universe is a reported non-match,
  not an error — same shape as every other gate in this repo.
- `stockstalker.report` — new `--fundamentals-contract`/`--fundamentals-ticker` flags
  apply the gate before rendering; the screen table grows two columns
  (Rev. CAGR(FY3), Net debt/EBITDA(FY3)) only when at least one candidate actually
  carries a fundamentals block.

**Verified before tagging:**
- `pytest` — 245 passed (16 new: contract loading/matching in
  `stockstalker.gates.fundamentals`, the report table/CLI wiring)
- `python -m stockstalker.gates.fundamentals --screen <screen.json> --contract
  fixtures/fundamentals/GULFOILLUB.json --ticker GULFOILLUB` — run against the real
  three-statement-model fixture output, and again with a synthetic contract against a
  universe ticker (RELIANCE.NS) to exercise the matching path
- `python -m stockstalker.report --offline --fundamentals-contract
  fixtures/fundamentals/GULFOILLUB.json --fundamentals-ticker GULFOILLUB` — end to end

**Like v0.7's GULFOILLUB non-match and v0.5's INFY non-match, unlike v0.3/v0.2/v0.4/v0.6's
real matches:** three-statement-model researched the same company reverse-dcf-engine
did (Gulf Oil Lubricants India, GULFOILLUB), which is not in this repo's 3-ticker
fixture universe (RELIANCE, TATACHEM, CROMPTON). The real integration produces zero
matches; the gate is fully tested against a synthetic matching contract, but the real
contract's actual numbers (`fy3_revenue_cagr: +15.39%`, `fy3_ebit_margin: 12.82%`,
`net_debt_ebitda_fy3: -1.69`, `balance_check: "passed"`) have not actually attached to
a live candidate yet — an honest result of two satellites built independently against
their own fixture sets, not a bug.

## v0.5 sentiment gate (package v0.7.5) — 2026-10-10

Headline sentiment overlay on the screen. headline-sentiment-vs-price finished its
8-day plan out of pipeline order, behind reverse-dcf-engine (v0.7), monte-carlo-
risk-lab (v0.3), fama-french-factor-model (v0.2), markowitz-portfolio-optimizer (v0.4)
and implied-vol-surface (v0.6) rather than ahead of them — the release-track label
stays v0.5 (pipeline position), but this repo's own package version cannot honestly
move backward from 0.7.4 to reflect that, since v0.7/v0.3/v0.2/v0.4/v0.6's gates are
all still present and this adds to them, not replaces them. Bumping to another patch
release (0.7.5), the same deviation the five prior integrations' changelog entries
already recorded.

**Ships:**
- `stockstalker.gates.sentiment` — reads headline-sentiment-vs-price's file contract
  (`{"sentiment": {"score_7d", "headline_count_7d", "model", "coverage"}}`, written by
  that repo's new `python -m sentiment.contract --ticker ... --contract ...`) and
  attaches it to the one screen candidate whose ticker matches, under the `sentiment`
  key `schema/v1.json` already reserves. Every other candidate passes through
  unchanged; a ticker outside the current universe is a reported non-match, not an
  error — same shape as every other gate in this repo.
- `stockstalker.report` — new `--sentiment-contract`/`--sentiment-ticker` flags apply
  the gate before rendering; the screen table grows two columns (Sent. score(7d),
  Headlines(7d)) only when at least one candidate actually carries a sentiment block.

**Verified before tagging:**
- `pytest` — 229 passed (15 new: contract loading/matching in
  `stockstalker.gates.sentiment`, the report table/CLI wiring)
- `python -m stockstalker.gates.sentiment --screen <screen.json> --contract
  fixtures/sentiment/INFY.json --ticker INFY.NS` — run against the real
  headline-sentiment-vs-price fixture output, and again with a synthetic contract
  against a universe ticker (RELIANCE.NS) to exercise the matching path
- `python -m stockstalker.report --offline --sentiment-contract
  fixtures/sentiment/INFY.json --sentiment-ticker INFY.NS` — end to end

**Like v0.7's GULFOILLUB non-match, unlike v0.3/v0.2/v0.4/v0.6's real matches:**
headline-sentiment-vs-price's 50-headline fixture resolves 23 headlines to 23 NSE
tickers (Infosys, Wipro, HDFC Bank, and so on), and none of them is RELIANCE, TATACHEM
or CROMPTON — this repo's own 3-ticker universe. The real integration produces zero
matches end to end. The gate logic is fully exercised by tests against a synthetic
contract keyed to a universe ticker (`RELIANCE.NS`), and the real, honest non-match
is itself tested end to end too — both repos' READMEs record this the same way v0.7's
entry does.

**Model deviation, recorded by both repos:** the sentiment contract shape
NEXT_STEPS.md committed to before this integration shows `"model": "finbert"` as its
example value. FinBERT cannot run in this sandbox (no `torch`, a gap every checkpoint
since that repo's Day 3 has documented), so the contract this integration actually
ships reports `"model": "vader"` instead — an honest substitution, not a silent one.

## v0.6 vol gate (package v0.7.4) — 2026-09-28

Options-implied risk signal on the screen. implied-vol-surface finished its 8-day plan
out of pipeline order, behind reverse-dcf-engine (v0.7), monte-carlo-risk-lab (v0.3),
fama-french-factor-model (v0.2) and markowitz-portfolio-optimizer (v0.4) rather than
ahead of them — the release-track label stays v0.6 (pipeline position), but this
repo's own package version cannot honestly move backward from 0.7.3 to reflect that,
since v0.7/v0.3/v0.2/v0.4's gates are all still present and this adds to them, not
replaces them. Bumping to another patch release (0.7.4), the same deviation the three
prior integrations' changelog entries already recorded.

**Ships:**
- `stockstalker.gates.vol` — reads implied-vol-surface's file contract
  (`{"vol": {"atm_iv_30d", "skew_25d", "term_slope", "iv_rank_1y"}}`, written by that
  repo's `python -m volsurface.history --contract ...`) and attaches it to the one
  screen candidate whose ticker matches, under the `vol` key `schema/v1.json` already
  reserves. Every other candidate passes through unchanged; a ticker outside the
  current universe is a reported non-match, not an error — same shape as every other
  gate in this repo.
- `stockstalker.report` — new `--vol-contract`/`--vol-ticker` flags apply the gate
  before rendering; the screen table grows two columns (ATM IV(30d), Skew(25d)) only
  when at least one candidate actually carries a vol block.

**Verified before tagging:**
- `pytest` — 214 passed (16 new: contract loading/matching in `stockstalker.gates.vol`,
  the report table/CLI wiring)
- `python -m stockstalker.gates.vol --screen <screen.json> --contract
  fixtures/vol/RELIANCE.json --ticker RELIANCE` — run against the real
  implied-vol-surface fixture output, and again with a ticker outside the universe
- `python -m stockstalker.report --offline --vol-contract fixtures/vol/RELIANCE.json
  --vol-ticker RELIANCE` — end to end

**Like v0.3's, v0.2's and v0.4's real matches, unlike v0.7's GULFOILLUB non-match:**
implied-vol-surface's fixture is built around RELIANCE, one of this repo's own three
universe tickers, so this is a genuine end-to-end match, not a synthetic stand-in.

**Honest partial ship, the same documented-gap pattern v0.2's and v0.3's version-order
deviations already recorded:** `atm_iv_30d`, `skew_25d` and `term_slope` are real
numbers computed from implied-vol-surface's own fitted surface and 25-delta skew.
`iv_rank_1y` ships `null` — that repo's own history has never accumulated more than one
distinct trading day (its only working data path is a fixture whose `data_date` never
advances), so there is no real trailing-year window for a percentile to rank against.
`stockstalker.gates.vol.load_contract` requires the key be present, not that it be
non-null, and passes `null` straight through rather than inventing a number — see both
repos' Limitations sections.

## v0.4 sizing gate (package v0.7.3) — 2026-09-25

Optimizer-driven position sizing on the screen. markowitz-portfolio-optimizer finished
its 7-day plan out of pipeline order, behind reverse-dcf-engine (v0.7), monte-carlo-
risk-lab (v0.3) and fama-french-factor-model (v0.2) rather than ahead of them — same
recurring deviation v0.3's and v0.2's changelog entries already recorded. The
release-track label stays v0.4 (pipeline position); this repo's own package version
cannot honestly move backward from 0.7.2, so it bumps to another patch release (0.7.3)
instead.

**Ships:**
- `stockstalker.gates.sizing` — reads markowitz-portfolio-optimizer's file contract
  (`{"sizing": {"weight", "method", "constraint_binding"}}`, written by that repo's
  `python -m optimizer.sizing --contract ... --contract-ticker ...`) and attaches it to
  the one screen candidate whose ticker matches, under the `sizing` key `schema/v1.json`
  already reserves. Every other candidate passes through unchanged; a ticker outside the
  current universe is a reported non-match, not an error — same shape as every other
  gate in this repo.
- `stockstalker.report` — new `--sizing-contract`/`--sizing-ticker` flags apply the gate
  before rendering; the screen table grows two columns (Weight, Constraint) only when at
  least one candidate actually carries a sizing block.

**Verified before tagging:**
- `pytest` — 197 passed, 1 failed (unrelated: the live-network smoke test hit a real,
  rate-limited yfinance response with a `NaN` close for today's date — a live-data
  anomaly, not a regression from this change; every test this integration added passed)
- `python -m stockstalker.gates.sizing --screen <screen.json> --contract
  fixtures/sizing/RELIANCE.json --ticker RELIANCE` — run against the real
  markowitz-portfolio-optimizer fixture output
- `python -m stockstalker.report --offline --sizing-contract fixtures/sizing/RELIANCE.json
  --sizing-ticker RELIANCE` — end to end, and again with a ticker outside the universe to
  confirm the honest non-match path

**Unlike v0.7's non-match, like v0.3's and v0.2's:** markowitz-portfolio-optimizer built
its Day 1 fixtures from this repo's own committed OHLCV history (`RELIANCE.NS`,
`TATACHEM.NS`, `CROMPTON.NS`), so RELIANCE.NS is a real shared ticker, not a synthetic
stand-in. The genuine result: markowitz-portfolio-optimizer's raw unconstrained max-Sharpe
tangency portfolio is a 100% single-name corner solution (a finding that repo's own Day
3/4/6/7 already reported), so the contract published here is the *sector-capped* solve
instead (50% cap) — RELIANCE.NS's weight comes in at exactly 50%, with `Energy` (its own,
single-member sector) recorded as the binding constraint. Because that fixture universe
puts every ticker in its own sector, this is mathematically identical to a plain position
limit on RELIANCE.NS alone, not a distinct multi-name sector constraint — see both repos'
Limitations sections.

## v0.2 factor gate (package v0.7.2) — 2026-09-22

Factor-adjusted ranking on the screen. fama-french-factor-model finished its 7-day plan
out of pipeline order, behind reverse-dcf-engine (v0.7) and monte-carlo-risk-lab (v0.3)
rather than ahead of them — the release-track label stays v0.2 (pipeline position), but
this repo's own package version cannot honestly move backward from 0.7.1 to reflect
that, since v0.7's valuation gate and v0.3's risk gate are both still present and this
adds to them, not replaces them. Bumping to another patch release (0.7.2), the same
deviation v0.3's own changelog entry already recorded and explained.

**Ships:**
- `stockstalker.gates.factor` — reads fama-french-factor-model's file contract
  (`{"factor": {"alpha_annual", "alpha_t", "significant", "loadings"}}`, written by that
  repo's `python -m factors.screen_check --contract ... --contract-ticker ...`) and
  attaches it to the one screen candidate whose ticker matches, under the `factor` key
  `schema/v1.json` already reserves. Every other candidate passes through unchanged; a
  ticker outside the current universe is a reported non-match, not an error — same shape
  as v0.3's risk gate and v0.7's valuation gate.
- `stockstalker.report` — new `--factor-contract`/`--factor-ticker` flags apply the gate
  before rendering; the screen table grows three columns (Alpha (ann.), Mkt loading,
  Sig.(5%)) only when at least one candidate actually carries a factor block.

**Verified before tagging:**
- `pytest` — 186 passed, 0 skipped
- `python -m stockstalker.gates.factor --screen <screen.json> --contract
  fixtures/factor/RELIANCE.json --ticker RELIANCE` — run against the real
  fama-french-factor-model fixture output
- `python -m stockstalker.report --offline --factor-contract fixtures/factor/RELIANCE.json
  --factor-ticker RELIANCE` — end to end

**Unlike v0.7's non-match, like v0.3's:** fama-french-factor-model committed a snapshot of
this repo's own `screen_2026-09-20.json` and OHLCV fixtures (`RELIANCE.NS`, `TATACHEM.NS`,
`CROMPTON.NS` — all three of this repo's universe tickers), so every candidate this repo
screens has a real factor result available, not just RELIANCE; RELIANCE was the one run
through `--contract` here to keep the CLI's single-ticker shape consistent with v0.3 and
v0.7. The genuine result is an honest negative: none of the three candidates shows a
statistically significant alpha under any model fama-french-factor-model ran (CAPM, FF3,
FF5+momentum), plain-OLS or Newey-West-corrected — but that repo's own README records only
22 overlapping months between the two fixture windows, underpowered for up to seven
parameters, so "insignificant" here means "underpowered," not "proven to be beta in
disguise." See both repos' Limitations sections.

## v0.3 risk gate (package v0.7.1) — 2026-09-18

VaR/CVaR risk envelope on survivors. monte-carlo-risk-lab finished its 7-day plan out
of pipeline order, behind reverse-dcf-engine (v0.7, shipped 2026-09-14) rather than
ahead of it — the release-track label stays v0.3 (pipeline position), but this repo's
own package version cannot honestly move backward from 0.7.0 to reflect that, since
v0.7's valuation gate is still present and this adds to it, not replaces it. Bumping to
a patch release (0.7.1) instead of a new minor is a deliberate deviation from the
"version = release label" convention v0.7.0's changelog entry described — that
convention assumed shipping order would track pipeline order, which it has not.
Recorded here rather than silently reusing 0.7.0 or renumbering past releases.

**Ships:**
- `stockstalker.gates.risk` — reads monte-carlo-risk-lab's file contract
  (`{"risk": {"var_95", "cvar_95", "max_dd_sim", "horizon_days"}}`, written by that
  repo's `python -m mcsim.portfolio --contract`) and attaches it to the one screen
  candidate whose ticker matches, under the `risk` key `schema/v1.json` already
  reserves. Every other candidate passes through unchanged; a ticker outside the
  current universe is a reported non-match, not an error — same shape as v0.7's
  valuation gate.
- `stockstalker.report` — new `--risk-contract`/`--risk-ticker` flags apply the gate
  before rendering; the screen table grows two columns (VaR 95%, CVaR 95%) only when
  at least one candidate actually carries a risk block.

**Verified before tagging:**
- `pytest` — 176 passed, 1 skipped (the live-network smoke test; no network in this
  environment, expected)
- `python -m stockstalker.gates.risk --screen <screen.json> --contract
  fixtures/risk/RELIANCE.json --ticker RELIANCE` — run against the real
  monte-carlo-risk-lab fixture output
- `python -m stockstalker.report --offline --risk-contract fixtures/risk/RELIANCE.json
  --risk-ticker RELIANCE` — end to end

**Unlike v0.7's non-match:** monte-carlo-risk-lab's fixture (`RELIANCE_NS.csv`) is
itself copied from this repo's own committed RELIANCE history, and RELIANCE.NS is one
of this repo's three universe tickers — so this integration is a genuine match on real
data, not a synthetic stand-in exercised only in tests.

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

## Checkpoint log (moved from the README on 25 Oct 2026)

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
