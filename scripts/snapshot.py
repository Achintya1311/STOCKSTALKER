#!/usr/bin/env python3
"""Append today's EOD bars to the snapshot history.

Run by the daily Actions workflow. Idempotent: rerunning on the same day
overwrites that day's rows rather than duplicating them, so a manual trigger
after a failed run is safe.

Deliberately quiet about failure. A holiday, a thin feed, or a single bad ticker
should not fail the workflow and should not commit an empty file.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
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
            df = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {ticker}: fetch failed ({exc})", file=sys.stderr)
            continue
        if df is None or df.empty:
            print(f"  {ticker}: no rows", file=sys.stderr)
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        last = df.tail(1)
        rows.append(
            {
                "date": last.index[-1].date().isoformat(),
                "ticker": ticker,
                "open": round(float(last["Open"].iloc[0]), 4),
                "high": round(float(last["High"].iloc[0]), 4),
                "low": round(float(last["Low"].iloc[0]), 4),
                "close": round(float(last["Close"].iloc[0]), 4),
                "volume": int(last["Volume"].iloc[0]),
            }
        )
        print(f"  {ticker}: {rows[-1]['date']} close {rows[-1]['close']}")
    return pd.DataFrame(rows)


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

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOT_DIR / f"{date.today().year}.csv"

    if out.exists():
        existing = pd.read_csv(out)
        combined = pd.concat([existing, fresh], ignore_index=True)
        # Last write wins for a given date/ticker, which makes reruns idempotent.
        combined = combined.drop_duplicates(subset=["date", "ticker"], keep="last")
    else:
        combined = fresh

    combined = combined.sort_values(["date", "ticker"])
    combined.to_csv(out, index=False)
    print(f"wrote {len(combined)} rows to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
