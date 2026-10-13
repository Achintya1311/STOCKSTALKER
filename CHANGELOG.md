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
