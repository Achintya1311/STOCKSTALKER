# Tear sheet — RELIANCE (2026-10-26)

Educational research on historical data. Not investment advice. Not a SEBI-registered research analyst.

Close 1,322.00 as of 2026-09-04. Score 0.5260 (trend +0.054, momentum +0.071, volume +0.022), ADV(20d) 10,498,450.

Technical signals describe how the price has behaved, not what the business is worth. This section reuses the screen's own scoring; the subject is not in `data/universe.txt` and this run does not add it there.

## Peer comparison

| Ticker | Return (1y) | Volatility (1y, ann.) | ADV(20d) |
|--------|-------------|------------------------|----------|
| RELIANCE | -3.24% | +20.18% | 10,498,450 |
| CASTROLIND | +2.95% | +13.33% | 3,784,413 |
| SOTL | +90.79% | +49.69% | 391,219 |
| GANDHAR | +111.98% | +50.30% | 771,276 |

## Contract sections

### Valuation

Not available -- no reverse-dcf-engine contract fixture for RELIANCE (fixtures/valuation/RELIANCE.json not found)

### Fundamentals

Not available -- no three-statement-model contract fixture for RELIANCE (fixtures/fundamentals/RELIANCE.json not found)

> built by hand for researched companies only (GULFOILLUB): three-statement-model stays driver-based by design, with no live-generation fallback for any other ticker.

### Risk

Via `monte-carlo-risk-lab`.

| Field | Value |
|-------|-------|
| var_95 | -0.0915 |
| cvar_95 | -0.1082 |
| max_dd_sim | -0.0589 |
| horizon_days | 20 |
| var_99 | -0.1207 |
| cvar_99 | -0.1270 |
| kupiec_95 | n_obs=500, n_exceptions=20, expected_exceptions=+25.0000, exception_rate=+0.0400, lr_stat=+1.1267, p_value=+0.2885, reject_at_5pct=False |
| kupiec_99 | n_obs=500, n_exceptions=10, expected_exceptions=+5.0000, exception_rate=+0.0200, lr_stat=+3.9136, p_value=+0.0479, reject_at_5pct=True |

> Kupiec backtest (this contract's own fields): parametric 1-day VaR REJECTED at 99% (10/500 vs 5.0 expected, LR=3.914, p=0.0479) but not rejected at 95% (20/500 vs 25.0 expected, LR=1.127, p=0.2885).

### Factor

Via `fama-french-factor-model`.

| Field | Value |
|-------|-------|
| alpha_annual | -0.0386 |
| alpha_t | -0.1852 |
| significant | not significant |
| loadings | mkt=+0.0155, smb=+0.1043, hml=-0.2515, rmw=+0.0180, cma=-0.7568, mom=-0.2185 |

> old method -- Ken French USD factors, 22 overlapping months, underpowered (fama-french-factor-model README, Day 5 screen check); GULFOILLUB's own contract uses IIMA's Indian factors on 137 months instead

### Vol

Via `implied-vol-surface`.

| Field | Value |
|-------|-------|
| atm_iv_30d | +0.2801 |
| skew_25d | +0.0210 |
| term_slope | +0.1136 |
| iv_rank_1y | n/a |

### Sentiment

Via `headline-sentiment-vs-price (live)`.

| Field | Value |
|-------|-------|
| score_7d | n/a |
| headline_count_7d | 0 |
| model | vader |
| coverage | none |

`sizing` is left out on purpose: a sector-capped weight across the subject and its three lubricant peers is a sector bet, not a position size (NEXT_STEPS.md Day 2).

