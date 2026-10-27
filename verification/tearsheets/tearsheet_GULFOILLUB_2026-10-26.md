# Tear sheet — GULFOILLUB (2026-10-26)

Educational research on historical data. Not investment advice. Not a SEBI-registered research analyst.

Close 1,077.30 as of 2026-10-09. Score 0.4237 (trend -0.159, momentum -0.022, volume -0.324), 20-day average turnover ₹4.69 cr (43,220 shares a day).

Technical signals describe how the price has behaved, not what the business is worth. This section reuses the screen's own scoring; the subject is not in `data/universe.txt` and this run does not add it there.

## Peer comparison

| Ticker | Return (1y) | Volatility (1y, ann.) | Turnover (20d avg, ₹ cr) | ADV (20d, shares) |
|--------|-------------|------------------------|--------------------------|-------------------|
| GULFOILLUB | -9.06% | +29.44% | ₹4.69 cr | 43,220 |
| CASTROLIND | +2.95% | +13.33% | ₹74.44 cr | 3,784,413 |
| SOTL | +90.79% | +49.69% | ₹28.52 cr | 391,219 |
| GANDHAR | +111.98% | +50.30% | ₹21.48 cr | 771,276 |

## Contract sections

### Valuation

Via `reverse-dcf-engine`.

| Field | Value |
|-------|-------|
| Implied revenue CAGR, 10y (implied_cagr) | n/a |
| EBIT margin, base year, held fixed: an input (implied_ebit_margin) | 13.37% |
| Implied reinvestment rate, year 1 (implied_reinvestment) | n/a |
| Perpetual breakeven growth (breakeven_growth) | n/a |
| Implied reinvestment rate, terminal (implied_reinvestment_terminal) | n/a |
| Median ROIC, historical (median_roic) | 25.89% |
| Terminal ROIC (terminal_roic) | 11.76% |
| Price reachable at a constant 10y growth rate (price_reachable) | No |
| Highest price the model reaches, 10y, ₹/share (max_achievable_price_10y) | ₹904.98 |
| Growth at that 10y maximum (growth_at_max_achievable_price_10y) | 11.76% |
| Price reachable at a constant perpetual growth rate (breakeven_reachable) | No |
| Highest price the model reaches, perpetual, ₹/share (max_achievable_price_perpetual) | ₹708.41 |
| Growth at that perpetual maximum (growth_at_max_achievable_price_perpetual) | 11.76% |
| Financials source (financials_source) | hand-entered, 10-year (GULFOILLUB base case) |
| Price solved against, ₹/share (price) | ₹1,054.00 |
| Price date (price_date) | 2026-10-26 |
| Base fiscal year (base_fiscal_year) | FY2023-24 |
| Base-year end to price date (years_to_price_date) | 2.57 years |
| Price reachable, 10y, dated to the price date (price_reachable_dated) | Yes |
| Implied revenue CAGR, 10y, dated to the price date (implied_cagr_dated) | 10.28% |
| Highest price the model reaches, 10y, dated to the price date, ₹/share (max_achievable_price_10y_dated) | ₹1,110.25 |
| Growth at that dated 10y maximum (growth_at_max_achievable_price_10y_dated) | 11.76% |

> solved against ₹1,054.00 (2026-10-26), FY2023-24 financials; implied_ebit_margin is the FY2023-24 EBIT margin held fixed (an input, not solved); financials source: hand-entered, 10-year (GULFOILLUB base case)

### Fundamentals

Via `three-statement-model`.

| Field | Value |
|-------|-------|
| Revenue CAGR to FY3, forecast (fy3_revenue_cagr) | 15.39% |
| EBIT margin, FY3, forecast (fy3_ebit_margin) | 12.82% |
| Net debt / EBITDA, FY3, forecast; negative is net cash (net_debt_ebitda_fy3) | -1.69x |
| Balance check, every forecast year (balance_check) | passed |
| Last reported fiscal year (base_fiscal_year) | FY2023-24 |
| FY3 (fy3_fiscal_year) | FY2026-27 |
| Dividend payout the forecast assumes (dividend_payout) | 0.00% |
| Inputs assumed, not from the filings (assumed_inputs) | dividend_payout 0% (no dividend data in the financials); amortization_rate 10%/yr (no loan schedule disclosed); revolver_limit = peak historical total debt (no facility size disclosed) |

> fy3 figures are the FY2026-27 forecast, the third year off FY2023-24 actuals (the years in between are modelled, not reported); negative net debt/EBITDA means net cash. net debt/EBITDA assumes a 0% dividend payout (no dividend data). built by hand for researched companies only (GULFOILLUB): three-statement-model stays driver-based by design, with no live-generation fallback for any other ticker.

### Risk

Via `monte-carlo-risk-lab`.

| Field | Value |
|-------|-------|
| VaR 95%, 20-day, simulated (var_95) | -11.72% |
| CVaR 95%, 20-day, simulated (cvar_95) | -17.71% |
| Mean simulated 20-day max drawdown (max_dd_sim) | -8.61% |
| Horizon, trading days (horizon_days) | 20 |
| VaR 99%, 20-day, simulated (var_99) | -22.28% |
| CVaR 99%, 20-day, simulated (cvar_99) | -28.69% |
| 1-day parametric VaR 95% backtest, Kupiec (kupiec_95) | n_obs=3006, n_exceptions=114, expected_exceptions=+150.3000, exception_rate=+0.0379, lr_stat=+10.0323, p_value=+0.0015, reject_at_5pct=True |
| 1-day parametric VaR 99% backtest, Kupiec (kupiec_99) | n_obs=3006, n_exceptions=44, expected_exceptions=+30.0600, exception_rate=+0.0146, lr_stat=+5.7129, p_value=+0.0168, reject_at_5pct=True |
| Out-of-sample 1-day VaR backtest, pre-registered (oos_var) | prereg=docs/PREREG_oos_var.md, window=500, refit_every=20, n_test=2506, expected_95=+125.3000, expected_99=+25.0600, garch_t_95_exceptions=111, garch_t_95_kupiec_p=+0.1817, garch_t_95_cc_p=+0.1663, garch_t_99_exceptions=21, garch_t_99_kupiec_p=+0.4017, garch_t_99_cc_p=+0.5891, garch_t_all_pass=True, garch_t_not_converged=0, gaussian_95_exceptions=101, gaussian_95_kupiec_p=+0.0214, gaussian_95_cc_p=+0.0060, gaussian_99_exceptions=42, gaussian_99_kupiec_p=+0.0019, gaussian_99_cc_p=+0.0036, gaussian_all_pass=False, gaussian_not_converged=0 |

> Kupiec backtest (this contract's own fields): parametric 1-day VaR REJECTED at both 95% (114/3,006 vs 150.3 expected, LR=10.032, p=0.0015) and 99% (44/3,006 vs 30.1 expected, LR=5.713, p=0.0168). Out of sample (pre-registered, 2,506 test days, 500-day window refit every 20 days): GARCH(1,1)-t passes all criteria (99%: 21 vs 25.1 expected, Kupiec p=0.402, conditional coverage p=0.589); the constant-volatility Gaussian fails (99%: 42 vs 25.1 expected, Kupiec p=0.002, conditional coverage p=0.004).

### Factor

Via `fama-french-factor-model`.

| Field | Value |
|-------|-------|
| Alpha, annualised (alpha_annual) | 10.64% |
| Alpha t-stat (alpha_t) | +1.01 |
| Alpha at the 5% level (significant) | not significant |
| Factor loadings (loadings) | mkt=+0.7972, smb=+0.4697, hml=-0.2370, wml=+0.0113 |
| Factor set (factor_source) | IIMA India factors (MF/SMB/HML/WML), monthly |
| First month regressed (window_start) | 2014-08 |
| Last month regressed (window_end) | 2025-12 |
| Months regressed (n_months) | 137 |

> IIMA India factors (MF/SMB/HML/WML), monthly, 2014-08 to 2025-12, 137 months

### Vol

Not available -- no listed options: not an NSE F&O underlying (fo_mktlots.csv, list dated 2026-10-22)

### Sentiment

Via `headline-sentiment-vs-price`.

| Field | Value |
|-------|-------|
| Headline sentiment score, 7 days (score_7d) | n/a |
| Headlines, 7 days (headline_count_7d) | 0 |
| Sentiment model (model) | vader |
| Headline coverage (coverage) | none |

`sizing` is left out on purpose: a sector-capped weight across the subject and its three lubricant peers is a sector bet, not a position size (NEXT_STEPS.md Day 2).

## Charts

- `rebased_GULFOILLUB.png`
- `drawdown_GULFOILLUB.png`
- `volatility_GULFOILLUB.png`

