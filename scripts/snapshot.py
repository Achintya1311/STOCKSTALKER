#!/usr/bin/env python3
"""Append recent EOD bars to the snapshot history.

Run by the daily Actions workflow. Idempotent: a rerun never duplicates a day's
rows, so a manual trigger after a failed run is safe.

P121/P165 (hub CRITIQUES.md, 5 Nov 2026): it used to keep only yfinance's
last row from a 5-day window, even when that bar was NaN, and never revisit
a day, so 11 of 41 sessions per name had no price. It now writes every row
with a complete open/high/low/close from the last month, skips NaN rows, lets
a later run fill a day an earlier one missed, and never rewrites a row that
already has a price. Rows go to the file for
their own year (``data/snapshots/<year>.csv``), and the backtest reads them all.

Deliberately quiet about failure. A holiday, a thin feed, or a single bad ticker
should not fail the workflow and should not commit an empty file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
PERIOD = "1mo"  # long enough to refill a missed day; yfinance returns about 21 bars
PRICE_COLS = ["Open", "High", "Low", "Close"]
UNIVERSE_FILE = ROOT / "data" / "universe.txt"


def universe() -> list[str]:
    if UNIVERSE_FILE.exists():
        return [
            line.strip()
            for line in UNIVERSE_FILE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    # Fall back to whatever has committed fixtures, so the job still does
    # something useful before the universe file is filled in.
    return sorted(p.stem.replace("_", ".") for p in (ROOT / "fixtures" / "ohlcv").glob("*.csv"))


def fetch(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        try:
            df = yf.download(ticker, period=PERIOD, interval="1d", progress=False, auto_adjust=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {ticker}: fetch failed ({exc})", file=sys.stderr)
            continue
        if df is None or df.empty:
            print(f"  {ticker}: no rows", file=sys.stderr)
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        complete = df.dropna(subset=PRICE_COLS)
        skipped = len(df) - len(complete)
        for ts, bar in complete.iterrows():
            volume = bar["Volume"]
            rows.append(
                {
                    "date": ts.date().isoformat(),
                    "ticker": ticker,
                    "open": round(float(bar["Open"]), 4),
                    "high": round(float(bar["High"]), 4),
                    "low": round(float(bar["Low"]), 4),
                    "close": round(float(bar["Close"]), 4),
                    "volume": int(volume) if pd.notna(volume) else None,
                }
            )
        if complete.empty:
            print(f"  {ticker}: no priced rows ({skipped} without a price skipped)", file=sys.stderr)
        else:
            print(f"  {ticker}: {len(complete)} priced rows to {complete.index[-1].date()}, {skipped} without a price skipped")
    return pd.DataFrame(rows)


def write(fresh: pd.DataFrame) -> None:
    """Merge ``fresh`` into ``SNAPSHOT_DIR/<year>.csv`` by each row's own year.

    A row already in the file with a price keeps its capture-day values (a
    later adjusted refetch must not rewrite it); a fresh row fills a date
    that is missing or has no price. Rows not in ``fresh`` stay.
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    years = fresh["date"].str.slice(0, 4)
    for year, part in fresh.groupby(years):
        out = SNAPSHOT_DIR / f"{year}.csv"
        if out.exists():
            existing = pd.read_csv(out)
            priced = existing.dropna(subset=["open", "high", "low", "close"])
            combined = pd.concat([priced, part], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date", "ticker"], keep="first")
            # an unpriced old row with no fresh replacement is kept as it was
            unpriced = existing.drop(priced.index)
            keys = set(zip(combined["date"], combined["ticker"]))
            leftover = unpriced[[(d, t) not in keys for d, t in zip(unpriced["date"], unpriced["ticker"])]]
            combined = pd.concat([combined, leftover], ignore_index=True)
        else:
            combined = part
        combined = combined.sort_values(["date", "ticker"])
        combined.to_csv(out, index=False)
        print(f"wrote {len(combined)} rows to {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


def main() -> int:
    tickers = universe()
    if not tickers:
        print("no universe and no fixtures - nothing to snapshot")
        return 0

    print(f"fetching {len(tickers)} tickers")
    fresh = fetch(tickers)
    if fresh.empty:
        print("no bars returned - likely a market holiday. Not writing a file.")
        return 0

    write(fresh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
