"""Provider tests. All offline: no network, no keys, no flakes."""

import datetime as dt
import os

import pandas as pd
import pytest

from stockstalker.data import providers
from stockstalker.data.providers import (
    AlphaVantageProvider,
    BadCredentials,
    FixtureProvider,
    ProviderError,
    RateLimited,
)


class _StubLiveProvider:
    """A fake live provider that counts fetches and never touches the network."""

    name = "stub"

    def __init__(self):
        self.calls = 0

    def fetch(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        self.calls += 1
        df = pd.DataFrame(
            {"open": [1.0], "high": [1.1], "low": [0.9], "close": [1.0], "volume": [100]},
            index=pd.to_datetime(["2026-01-01"]),
        )
        df.index.name = "date"
        return df


def test_fixture_provider_lists_committed_tickers():
    assert set(FixtureProvider().available()) >= {"RELIANCE.NS", "TATACHEM.NS", "CROMPTON.NS"}


def test_fixture_fetch_returns_the_shared_shape():
    df = FixtureProvider().fetch("RELIANCE.NS")
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    assert df.index.tz is None
    assert len(df) > 400


def test_unknown_fixture_names_the_alternatives():
    """An error that lists what is available saves a round trip."""
    with pytest.raises(ProviderError, match="available:"):
        FixtureProvider().fetch("NOTATICKER.NS")


def test_missing_column_fails_loudly():
    bad = pd.DataFrame({"open": [1.0], "close": [1.0]}, index=pd.to_datetime(["2026-01-01"]))
    with pytest.raises(ProviderError, match="missing"):
        providers._normalise(bad, "X.NS")


def test_empty_frame_is_an_error_not_an_empty_result():
    with pytest.raises(ProviderError, match="no rows"):
        providers._normalise(pd.DataFrame(), "X.NS")


def test_normalise_drops_a_row_with_any_nan_field_not_just_all_nan():
    """A still-forming session (yfinance's most recent bar mid-day, or a
    corrupted row) can have some OHLCV fields populated and one - often
    close - still NaN. That row is not a completed trading day and must not
    survive: dropping only fully-NaN rows (``how="all"``) let exactly this
    kind of row through and broke a downstream ``close > 0`` check on live
    data (the incomplete bar's close was NaN, everything else present).
    """
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, float("nan")],
            "volume": [1000, 500],
        },
        index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
    )
    out = providers._normalise(df, "X.NS")
    assert len(out) == 1
    assert out.index[0] == pd.Timestamp("2026-01-01")


def test_normalise_raises_if_every_row_is_partial():
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [102.0],
            "low": [99.0],
            "close": [float("nan")],
            "volume": [1000],
        },
        index=pd.to_datetime(["2026-01-01"]),
    )
    with pytest.raises(ProviderError, match="no complete bars"):
        providers._normalise(df, "X.NS")


def test_multiindex_columns_are_flattened():
    """yfinance hands back a MultiIndex even for a single ticker sometimes."""
    idx = pd.to_datetime(["2026-01-01"])
    df = pd.DataFrame(
        [[1.0, 2.0, 0.5, 1.5, 100]],
        index=idx,
        columns=pd.MultiIndex.from_tuples(
            [("Open", "X.NS"), ("High", "X.NS"), ("Low", "X.NS"), ("Close", "X.NS"), ("Volume", "X.NS")]
        ),
    )
    out = providers._normalise(df, "X.NS")
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]


class TestAlphaVantageNotices:
    """The quota message and the bad-key message arrive through the same field.

    Alpha Vantage's rate-limit text also mentions premium plans, so checking for
    key problems first would misreport an exhausted quota as a broken key.
    """

    def test_quota_message_raises_rate_limited(self):
        payload = {
            "Information": "We have detected your API key and our standard API "
            "rate limit is 25 requests per day. Consider a premium plan."
        }
        with pytest.raises(RateLimited):
            AlphaVantageProvider._raise_for_notice(payload)

    def test_key_message_raises_bad_credentials(self):
        payload = {"Information": "Invalid API key. Please claim a free api key."}
        with pytest.raises(BadCredentials):
            AlphaVantageProvider._raise_for_notice(payload)

    def test_error_message_field_is_credentials(self):
        with pytest.raises(BadCredentials):
            AlphaVantageProvider._raise_for_notice({"Error Message": "invalid api call"})

    def test_clean_payload_passes(self):
        AlphaVantageProvider._raise_for_notice({"Time Series (Daily)": {}})


def test_missing_key_points_at_the_offline_path():
    with pytest.raises(BadCredentials, match="--offline"):
        AlphaVantageProvider(api_key="").fetch("RELIANCE.NS")


def test_load_defaults_to_fixtures():
    df = providers.load("TATACHEM.NS")
    assert not df.empty


# -- D11: a cached live fetch must expire, not be served forever ----------


def _patch_stub_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(providers, "CACHE_DIR", tmp_path)
    stub = _StubLiveProvider()
    monkeypatch.setitem(providers.PROVIDERS, "stub", lambda: stub)
    return stub


def test_load_reuses_a_same_day_cache_without_refetching(tmp_path, monkeypatch):
    stub = _patch_stub_provider(monkeypatch, tmp_path)

    providers.load("X.NS", provider="stub")
    providers.load("X.NS", provider="stub")

    assert stub.calls == 1


def test_load_refetches_once_the_cache_is_from_an_earlier_day(tmp_path, monkeypatch):
    """D11: ``load()`` used to return a cached live CSV forever -- no TTL, no
    date check -- once one existed for a ticker. A cache written on an
    earlier day must be treated as stale and re-fetched, not served as if it
    were today's bar.
    """
    stub = _patch_stub_provider(monkeypatch, tmp_path)

    providers.load("X.NS", provider="stub")
    assert stub.calls == 1

    cached = tmp_path / "stub_X_NS_2y.csv"
    assert cached.exists()
    yesterday = (dt.datetime.now() - dt.timedelta(days=1)).timestamp()
    os.utime(cached, (yesterday, yesterday))

    providers.load("X.NS", provider="stub")
    assert stub.calls == 2, "a cache from an earlier day must not be served forever (D11)"


def test_use_cache_false_always_refetches_live(tmp_path, monkeypatch):
    stub = _patch_stub_provider(monkeypatch, tmp_path)

    providers.load("X.NS", provider="stub")
    providers.load("X.NS", provider="stub", use_cache=False)

    assert stub.calls == 2


def test_local_csv_path_refetches_a_stale_cache_too(tmp_path, monkeypatch):
    """D11: the three live satellite paths (``run.py``'s ``local_csv_path``
    call sites) go through the same ``load()`` cache, so they must pick up
    the same staleness fix rather than being re-verified separately.
    """
    stub = _patch_stub_provider(monkeypatch, tmp_path)

    providers.local_csv_path("X.NS", provider="stub")
    cached = tmp_path / "stub_X_NS_2y.csv"
    yesterday = (dt.datetime.now() - dt.timedelta(days=1)).timestamp()
    os.utime(cached, (yesterday, yesterday))

    providers.local_csv_path("X.NS", provider="stub")
    assert stub.calls == 2


def test_get_provider_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown provider"):
        providers.get_provider("bloomberg")


# -- Day 21 (C1): local_csv_path, a real file for a subprocess to read -----


def test_local_csv_path_for_fixtures_points_at_the_committed_file():
    path = providers.local_csv_path("TATACHEM.NS", provider="fixtures")
    assert path == providers.FIXTURE_DIR / "TATACHEM_NS.csv"
    assert path.exists()
    assert path.read_text().splitlines()[0].split(",")[0] == "date"


def test_local_csv_path_raises_provider_error_for_unknown_fixture():
    with pytest.raises(ProviderError, match="available:"):
        providers.local_csv_path("NOTATICKER.NS", provider="fixtures")
