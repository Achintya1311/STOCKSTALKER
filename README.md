# Stock Stalker

Screens the NSE universe down to a shortlist worth researching properly, using trend, momentum, volume and liquidity signals. Command-line only: arguments in, ranked candidates and chart files out.

**Status:** Last checkpoint 2026-09-06 · Next: Day 4 - signals/momentum.py (RSI, MACD) and signals/volume.py (OBV, volume z-score)

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

## Findings

Nothing yet.

## Checkpoint log

<!-- CHECKPOINTS:START -->
| Date | Commit | What changed | Next |
|------|--------|--------------|------|
| 2026-09-06 | `5b4950c` | Day 3: SMA/EMA crossover trend signals (sma, ema, crossover_state, crossover_events, trend_score) as pure functions, unit tested against fixtures and synthetic series | Day 4 - signals/momentum.py (RSI, MACD) and signals/volume.py (OBV, volume z-score) |
| 2026-09-06 | `3a014ec` | Days 1-2: scaffold, v1 output contract, offline fixtures, and the provider interface over fixtures/yfinance/Alpha Vantage | Day 3 - SMA/EMA crossover signals as pure functions with unit tests |
<!-- CHECKPOINTS:END -->

## Limitations and what would make me wrong

- The ticker universe is today's list. Names that delisted or were removed are absent, so any historical result carries survivorship bias. Stated rather than corrected.
- Technical signals describe how a price has behaved, not what a business is worth. Nothing here is a valuation, and nothing here is a recommendation.
- The Alpha Vantage free tier is 25 requests/day. Live runs across a real universe are rate-limited by design, which is why the fixture path exists.
- Any backtest in this repo is in-sample unless the README says otherwise in that specific section.

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
