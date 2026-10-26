"""D41: the README's price-fixture table must match the files on disk."""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ROW = re.compile(r"\| `(fixtures/ohlcv/[^`]+\.csv)` \| (\d{4}-\d{2}-\d{2}) \| (\d{4}-\d{2}-\d{2}) \| ([\d,]+) \|")


def test_readme_lists_every_price_fixture_with_its_real_span():
    rows = {m[0]: m[1:] for m in ROW.findall((ROOT / "README.md").read_text())}
    on_disk = {str(p.relative_to(ROOT)) for p in (ROOT / "fixtures" / "ohlcv").glob("*.csv")}
    assert set(rows) == on_disk
    for path, (first, last, bars) in rows.items():
        df = pd.read_csv(ROOT / path)
        assert (df["date"].iloc[0], df["date"].iloc[-1], len(df)) == (first, last, int(bars.replace(",", ""))), path
