# Tear sheet — GULFOILLUB (2026-10-26)

Educational research on historical data. Not investment advice. Not a SEBI-registered research analyst.

Close 1,077.30 as of 2026-10-09. Score 0.4237 (trend -0.159, momentum -0.022, volume -0.324), ADV(20d) 43,220.

Technical signals describe how the price has behaved, not what the business is worth. This section reuses the screen's own scoring; the subject is not in `data/universe.txt` and this run does not add it there.

## Peer comparison

| Ticker | Return (1y) | Volatility (1y, ann.) | ADV(20d) |
|--------|-------------|------------------------|----------|
| GULFOILLUB | -9.06% | +29.44% | 43,220 |
| CASTROLIND | +2.95% | +13.33% | 3,784,413 |
| SOTL | +90.79% | +49.69% | 391,219 |
| GANDHAR | +111.98% | +50.30% | 771,276 |

## Contract sections

### Valuation

Via `reverse-dcf-engine`.

| Field | Value |
|-------|-------|
| implied_cagr | n/a |
| implied_ebit_margin | +0.1337 |
| implied_reinvestment | n/a |
| breakeven_growth | n/a |
| implied_reinvestment_terminal | n/a |
| median_roic | +0.2589 |
| terminal_roic | +0.1176 |
| price_reachable | False |
| max_achievable_price_10y | +904.9835 |
| growth_at_max_achievable_price_10y | +0.1176 |
| breakeven_reachable | False |
| max_achievable_price_perpetual | +708.4123 |
| growth_at_max_achievable_price_perpetual | +0.1176 |
| financials_source | hand-entered, 10-year (GULFOILLUB base case) |

> financials source: hand-entered, 10-year (GULFOILLUB base case)

### Fundamentals

Via `three-statement-model`.

| Field | Value |
|-------|-------|
| fy3_revenue_cagr | +0.1539 |
| fy3_ebit_margin | +0.1282 |
| net_debt_ebitda_fy3 | -1.6879 |
| balance_check | passed |

> built by hand for researched companies only (GULFOILLUB): three-statement-model stays driver-based by design, with no live-generation fallback for any other ticker.

### Risk

Via `monte-carlo-risk-lab`.

| Field | Value |
|-------|-------|
| var_95 | -0.1172 |
| cvar_95 | -0.1771 |
| max_dd_sim | -0.0861 |
| horizon_days | 20 |
| var_99 | -0.2228 |
| cvar_99 | -0.2869 |
| kupiec_95 | n_obs=3006, n_exceptions=114, expected_exceptions=+150.3000, exception_rate=+0.0379, lr_stat=+10.0323, p_value=+0.0015, reject_at_5pct=True |
| kupiec_99 | n_obs=3006, n_exceptions=44, expected_exceptions=+30.0600, exception_rate=+0.0146, lr_stat=+5.7129, p_value=+0.0168, reject_at_5pct=True |
| oos_var | prereg=docs/PREREG_oos_var.md, window=500, refit_every=20, n_test=2506, expected_95=+125.3000, expected_99=+25.0600, garch_t_95_exceptions=111, garch_t_95_kupiec_p=+0.1817, garch_t_95_cc_p=+0.1663, garch_t_99_exceptions=21, garch_t_99_kupiec_p=+0.4017, garch_t_99_cc_p=+0.5891, garch_t_all_pass=True, garch_t_not_converged=0, gaussian_95_exceptions=101, gaussian_95_kupiec_p=+0.0214, gaussian_95_cc_p=+0.0060, gaussian_99_exceptions=42, gaussian_99_kupiec_p=+0.0019, gaussian_99_cc_p=+0.0036, gaussian_all_pass=False, gaussian_not_converged=0 |

> Kupiec backtest (this contract's own fields): parametric 1-day VaR REJECTED at both 95% (114/3,006 vs 150.3 expected, LR=10.032, p=0.0015) and 99% (44/3,006 vs 30.1 expected, LR=5.713, p=0.0168). Out of sample (pre-registered, 2,506 test days, 500-day window refit every 20 days): GARCH(1,1)-t passes all criteria (99%: 21 vs 25.1 expected, Kupiec p=0.402, conditional coverage p=0.589); the constant-volatility Gaussian fails (99%: 42 vs 25.1 expected, Kupiec p=0.002, conditional coverage p=0.004).

### Factor

Via `fama-french-factor-model`.

| Field | Value |
|-------|-------|
| alpha_annual | +0.1064 |
| alpha_t | +1.0112 |
| significant | not significant |
| loadings | mkt=+0.7972, smb=+0.4697, hml=-0.2370, wml=+0.0113 |

### Vol

Not available -- no listed options: not an NSE F&O underlying (fo_mktlots.csv, list dated 2026-09-29)

### Sentiment

Via `headline-sentiment-vs-price`.

| Field | Value |
|-------|-------|
| score_7d | n/a |
| headline_count_7d | 0 |
| model | vader |
| coverage | none |

`sizing` is left out on purpose: a sector-capped weight across the subject and its three lubricant peers is a sector bet, not a position size (NEXT_STEPS.md Day 2).

