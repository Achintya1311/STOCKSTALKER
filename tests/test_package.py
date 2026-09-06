import json
from pathlib import Path

import stockstalker

ROOT = Path(__file__).resolve().parent.parent


def test_version_is_set():
    assert stockstalker.__version__


def test_schema_is_valid_json_and_versioned():
    schema = json.loads((ROOT / "schema" / "v1.json").read_text())
    assert schema["properties"]["schema"]["const"] == "v1"
    assert "candidates" in schema["required"]


def test_fixtures_are_present_and_non_empty():
    """The offline path is the default, so missing fixtures is a hard failure."""
    csvs = list((ROOT / "fixtures" / "ohlcv").glob("*.csv"))
    assert len(csvs) >= 3
    for path in csvs:
        assert path.stat().st_size > 1000, f"{path.name} looks truncated"
