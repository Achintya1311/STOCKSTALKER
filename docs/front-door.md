# The front door, section by section

Moved from the README on 25 Oct 2026 so the README leads with the verdict. Nothing here changed.

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
   | `vol` | [implied-vol-surface](https://github.com/Achintya1311/implied-vol-surface) | options-implied ATM IV, 25-delta skew and term slope — no listed options for GULFOILLUB, see Limitations |
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
   names GULFOILLUB), and `vol` prints "no listed options" because NSE's
   own F&O lot-size snapshot (`fixtures/fo_mktlots.csv`, fix-phase Day 5)
   confirms GULFOILLUB's SYMBOL is absent from it — a checked fact now,
   not the earlier "unverified" hedge from a blocked network response —
   see Limitations for both.
4. **Charts to `outputs/`** — three PNGs: GULFOILLUB vs. its three peers
   rebased to 100, drawdown from peak, and rolling 1-year annualised
   volatility. Pass `--no-charts` to skip them.
5. **The tear sheet itself** — `outputs/tearsheet_<TICKER>_<date>.md`,
   the same content as the terminal output, written every run.

Run `python -m stockstalker.run --help` for `--peers`, `--live`, `--config`
and the rest of the flags.
