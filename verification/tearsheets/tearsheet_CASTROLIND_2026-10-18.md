# Tear sheet — CASTROLIND (2026-10-18)

Educational research on historical data. Not investment advice. Not a SEBI-registered research analyst.

Close 197.74 as of 2026-10-16. Score 0.5500 (trend +0.301, momentum -0.064, volume +0.009), ADV(20d) 3,544,071.

Technical signals describe how the price has behaved, not what the business is worth. This section reuses the screen's own scoring; the subject is not in `data/universe.txt` and this run does not add it there.

## Peer comparison

| Ticker | Return (1y) | Volatility (1y, ann.) | ADV(20d) |
|--------|-------------|------------------------|----------|
| CASTROLIND | +5.21% | +13.40% | 3,544,071 |

## Contract sections

### Valuation

Via `reverse-dcf-engine (live)`.

| Field | Value |
|-------|-------|
| implied_cagr | n/a |
| implied_ebit_margin | +0.2266 |
| implied_reinvestment | n/a |
| breakeven_growth | n/a |
| implied_reinvestment_terminal | n/a |
| median_roic | +0.3192 |
| terminal_roic | +0.1198 |
| price_reachable | False |
| max_achievable_price_10y | +128.6933 |
| growth_at_max_achievable_price_10y | +0.1198 |
| breakeven_reachable | False |
| max_achievable_price_perpetual | +94.1083 |
| growth_at_max_achievable_price_perpetual | +0.1198 |
| financials_source | yfinance, consolidated, 4-5 years |

> financials source: yfinance, consolidated, 4-5 years

### Fundamentals

Not available -- no three-statement-model contract fixture for CASTROLIND (fixtures/fundamentals/CASTROLIND.json not found)

> built by hand for researched companies only (GULFOILLUB): three-statement-model stays driver-based by design, with no live-generation fallback for any other ticker.

### Risk

Via `monte-carlo-risk-lab (live)`.

| Field | Value |
|-------|-------|
| var_95 | -0.1041 |
| cvar_95 | -0.1384 |
| max_dd_sim | -0.0725 |
| horizon_days | 20 |
| var_99 | -0.1549 |
| cvar_99 | -0.1662 |
| kupiec_95 | n_obs=496, n_exceptions=19, expected_exceptions=+24.8000, exception_rate=+0.0383, lr_stat=+1.5477, p_value=+0.2135, reject_at_5pct=False |
| kupiec_99 | n_obs=496, n_exceptions=8, expected_exceptions=+4.9600, exception_rate=+0.0161, lr_stat=+1.5874, p_value=+0.2077, reject_at_5pct=False |

> Kupiec backtest (this contract's own fields): parametric 1-day VaR not rejected at either 95% (19/496 vs 24.8 expected, LR=1.548, p=0.2135) or 99% (8/496 vs 5.0 expected, LR=1.587, p=0.2077).

### Factor

Via `fama-french-factor-model (live)`.

| Field | Value |
|-------|-------|
| alpha_annual | -0.0944 |
| alpha_t | -0.3395 |
| significant | not significant |
| loadings | mkt=-0.7564, smb=+0.5378, hml=+1.0024, wml=+0.1271 |

### Vol

Not available -- no listed options: not an NSE F&O underlying (fo_mktlots.csv, list dated 2026-09-29)

### Sentiment

Via `headline-sentiment-vs-price (live)`.

| Field | Value |
|-------|-------|
| score_7d | n/a |
| headline_count_7d | 0 |
| model | vader |
| coverage | none |

`sizing` is left out on purpose: a sector-capped weight across the subject and its three lubricant peers is a sector bet, not a position size (NEXT_STEPS.md Day 2).

