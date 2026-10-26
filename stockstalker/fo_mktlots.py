"""Refresh NSE's F&O lot-size list, ``fixtures/fo_mktlots.csv`` (hub CRITIQUES.md D42).

The front door's "no listed options" verdict for a ticker rests on this file,
and NSE republishes it monthly. This sandbox cannot reliably reach NSE, but
GitHub's hosted runners can (D25), so ``.github/workflows/fetch-fo-mktlots.yml``
runs ``python -m stockstalker.fo_mktlots`` once a month.

A blocked or truncated response (an HTML error page, an empty body) is refused
before anything is written, so a bad fetch never replaces a good list.

    python -m stockstalker.fo_mktlots                      # fetch live from NSE
    python -m stockstalker.fo_mktlots --from-file PATH     # validate and install a saved copy
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
CSV_PATH = ROOT / "fixtures" / "fo_mktlots.csv"
META_PATH = ROOT / "fixtures" / "fo_mktlots_meta.json"
# The 2026-09-29 list has 220 underlyings; a real list has never been near this floor.
MIN_ROWS = 100
NOTE = (
    "NSE's own current F&O lot-size snapshot (every index and stock underlying with listed "
    "derivatives). SYMBOL column checked for front-door honesty (CRITIQUES.md D2): a ticker "
    "absent here has no listed options, full stop -- not merely an unchecked or blocked case."
)


def validate(text: str) -> int:
    """Return the number of underlyings in ``text``, or raise ValueError."""
    if not text.strip():
        raise ValueError("empty response")
    rows = list(csv.reader(io.StringIO(text)))
    header = [cell.strip().upper() for cell in rows[0]]
    if len(header) < 2 or header[1] != "SYMBOL":
        raise ValueError(f"no SYMBOL column in the header: {rows[0][:3]}")
    symbols = {row[1].strip().upper() for row in rows[1:] if len(row) >= 2 and row[1].strip()}
    if len(symbols) < MIN_ROWS:
        raise ValueError(f"only {len(symbols)} rows, expected at least {MIN_ROWS}")
    if "NIFTY" not in symbols:
        raise ValueError("NIFTY missing from the SYMBOL column")
    return len(symbols)


def build_meta(last_modified: str | None, today: str) -> dict:
    listed = parsedate_to_datetime(last_modified).date().isoformat() if last_modified else "unknown"
    return {"source": URL, "fetched_at": today, "list_last_modified": listed, "note": NOTE}


def fetch() -> tuple[str, str | None]:
    import requests

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*", "Referer": "https://www.nseindia.com/"}
    resp = requests.get(URL, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.text, resp.headers.get("Last-Modified")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-file", default=None, help="install a saved copy instead of fetching")
    ap.add_argument("--last-modified", default=None, help="Last-Modified header to record with --from-file")
    ap.add_argument("--csv", default=str(CSV_PATH))
    ap.add_argument("--meta", default=str(META_PATH))
    ap.add_argument("--today", default=date.today().isoformat())
    args = ap.parse_args(argv)

    if args.from_file:
        text, last_modified = Path(args.from_file).read_text(), args.last_modified
    else:
        text, last_modified = fetch()
    try:
        n = validate(text)
    except ValueError as exc:
        raise SystemExit(f"refusing to write {args.csv}: {exc}")

    Path(args.csv).write_text(text)
    meta = build_meta(last_modified, args.today)
    Path(args.meta).write_text(json.dumps(meta, indent=2) + "\n")
    print(f"fo_mktlots: {n} underlyings, list dated {meta['list_last_modified']} -> {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
