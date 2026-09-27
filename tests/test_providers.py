"""Provider tests. All offline: no network, no keys, no flakes."""

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


def test_get_provider_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown provider"):
        providers.get_provider("bloomberg")
