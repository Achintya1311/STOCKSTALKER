"""Live-network smoke test for YFinanceProvider.

Every other provider test in this suite (test_providers.py) is offline by
design: no network, no keys, no flakes. That is correct for the fixture
path, but it also means nothing in the suite ever actually calls Yahoo, so
"the scanner works" has silently meant "the scanner works against three
CSVs we committed ourselves." This file is the one exception, on purpose.

Two honest outcomes, both asserted on:

- This sandbox has live outbound network: prove the bars that come back
  are real, varying market data, not a degenerate stub (same value
  repeated, empty frame, zero volume).
- This sandbox's outbound proxy blocks it (true as of this writing - see
  the environment's network policy): prove the failure surfaces as the
  provider's own typed ProviderError, not a raw curl/requests exception
  leaking past the abstraction, and skip rather than pass. A skip shows up
  as distinctly not-a-pass in the test report, so nobody mistakes "network
  was unavailable" for "the live path was verified."
"""

from __future__ import annotations

import pytest

from stockstalker.data.providers import ProviderError, YFinanceProvider

LIVE_TICKER = "RELIANCE.NS"


def test_yfinance_provider_gives_real_live_values_or_fails_cleanly():
    provider = YFinanceProvider()
    try:
        df = provider.fetch(LIVE_TICKER, period="1mo")
    except ProviderError as exc:
        pytest.skip(
            f"no live network reachable in this sandbox ({exc}); this is the "
            "offline/zero-spend default working as intended, not a scanner bug. "
            "Re-run in an environment with outbound network to actually exercise "
            "the live path."
        )
        return

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) >= 5
    assert df.index.is_monotonic_increasing
    assert (df["close"] > 0).all()
    assert (df["volume"] >= 0).all()
    # A real month of NSE trading is never a flat line - this is what actually
    # distinguishes "live values" from a provider quietly handing back a
    # degenerate/cached/stub frame that happens to have the right shape.
    assert df["close"].nunique() > 1
    assert df["close"].std() > 0
    # Loose sanity band, not a hardcoded price target - catches a unit mix-up
    # (paise vs rupees) or a garbage payload without pinning today's price.
    assert 1.0 < df["close"].iloc[-1] < 1_000_000


def test_yfinance_provider_never_leaks_a_raw_exception():
    """Whatever goes wrong reaching Yahoo, it must surface as ProviderError.

    screener.build_screen only catches ProviderError per ticker - anything
    else escapes and takes down the whole screen run over one bad symbol or
    one network hiccup, live or offline.
    """
    provider = YFinanceProvider()
    try:
        provider.fetch("THIS-IS-NOT-A-REAL-TICKER-XYZ123", period="5d")
    except ProviderError:
        pass
    except Exception as exc:  # noqa: BLE001 - the whole point of this test
        pytest.fail(
            f"YFinanceProvider leaked a raw {type(exc).__name__} instead of "
            f"ProviderError: {exc}"
        )
    else:
        pytest.fail("expected a nonexistent ticker to raise ProviderError")
