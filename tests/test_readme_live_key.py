"""P91: the README must not say --live needs an API key while it uses yfinance."""

import re
from pathlib import Path

from stockstalker import run
from stockstalker.data.providers import get_provider

ROOT = Path(__file__).resolve().parents[1]


def test_live_path_selects_a_keyless_provider(monkeypatch):
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    source = Path(run.__file__).read_text()
    assert 'provider_name = "yfinance" if args.live else "fixtures"' in source
    provider = get_provider("yfinance")
    assert not getattr(provider, "api_key", "")


def test_readme_does_not_say_live_needs_a_key():
    text = (ROOT / "README.md").read_text()
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if "--live" in sentence:
            assert not re.search(r"needs? (an? (API )?)?key", sentence, re.IGNORECASE), sentence
