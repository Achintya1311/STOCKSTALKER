"""Market data providers behind one interface.

Three sources, same contract: a DataFrame indexed by date with
``open, high, low, close, volume`` columns.

- :class:`FixtureProvider` reads committed CSVs. This is the default, so the
  project runs with no network and no API key.
- :class:`YFinanceProvider` fetches live daily bars. No key required.
- :class:`AlphaVantageProvider` uses the free tier (25 requests/day).

Alpha Vantage reports both rate limiting and an invalid key through the same
``Information``/``Note`` field. Conflating the two turns a five-second fix into
an afternoon, so they raise distinct exceptions here.
"""

from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]
ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_DIR = ROOT / "fixtures" / "ohlcv"
CACHE_DIR = ROOT / ".cache" / "ohlcv"


class ProviderError(RuntimeError):
    """Data could not be retrieved."""


class RateLimited(ProviderError):
    """The provider refused the request because a quota is exhausted.

    Distinct from :class:`BadCredentials` because the remedy is completely
    different: wait, versus fix your key.
    """


class BadCredentials(ProviderError):
    """The API key is missing, malformed, or rejected."""


def _normalise(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Coerce a provider's frame into the shared shape, or fail loudly."""
    if df is None or df.empty:
        raise ProviderError(f"no rows returned for {ticker}")

    # yfinance returns a MultiIndex when given a list of tickers, and sometimes
    # when given one. Flatten before matching column names.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.rename(columns=str.lower)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ProviderError(f"{ticker}: provider frame is missing {missing}")

    df = df[COLUMNS].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    # how="any", not "all": yfinance's most recent bar can be a still-forming
    # session with some OHLCV fields populated and one (often close) still
    # NaN - not a fully-empty row, so "all" let it through. A bar missing any
    # field isn't a completed trading day and shouldn't reach the pipeline.
    df = df.sort_index().dropna(how="any")
    if df.empty:
        raise ProviderError(f"no complete bars for {ticker} after dropping partial rows")
    return df


class FixtureProvider:
    """Reads the committed CSVs. Offline, deterministic, always available."""

    name = "fixtures"

    def __init__(self, directory: Path | None = None):
        self.directory = directory or FIXTURE_DIR

    def available(self) -> list[str]:
        return sorted(p.stem.replace("_", ".") for p in self.directory.glob("*.csv"))

    def fetch(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        path = self.directory / f"{ticker.replace('.', '_')}.csv"
        if not path.exists():
            raise ProviderError(
                f"no fixture for {ticker}. available: {', '.join(self.available()) or 'none'}"
            )
        df = pd.read_csv(path, index_col="date", parse_dates=True)
        return _normalise(df, ticker)


class YFinanceProvider:
    """Live daily bars from Yahoo. No key, no documented quota, no guarantees."""

    name = "yfinance"

    def fetch(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        import yfinance as yf  # imported lazily so offline runs need not have it

        try:
            df = yf.download(
                ticker, period=period, interval="1d", progress=False, auto_adjust=True
            )
        except Exception as exc:  # noqa: BLE001 - surface as our own error type
            raise ProviderError(f"yfinance failed for {ticker}: {exc}") from exc
        return _normalise(df, ticker)


class AlphaVantageProvider:
    """Free tier: 25 requests/day. Treat every call as expensive."""

    name = "alphavantage"
    URL = "https://www.alphavantage.co/query"
    RATE_LIMIT_PHRASES = ("rate limit", "requests per day", "call frequency", "premium")

    def __init__(self, api_key: str | None = None, pause: float = 1.0):
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_API_KEY", "")
        self.pause = pause

    def fetch(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        import requests

        if not self.api_key:
            raise BadCredentials(
                "ALPHAVANTAGE_API_KEY is not set. Copy .env.example to .env, or use "
                "--offline to run against fixtures."
            )

        time.sleep(self.pause)  # free tier is unforgiving about burst rates
        try:
            response = requests.get(
                self.URL,
                params={
                    "function": "TIME_SERIES_DAILY_ADJUSTED",
                    "symbol": ticker,
                    "outputsize": "full",
                    "apikey": self.api_key,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"alpha vantage request failed for {ticker}: {exc}") from exc

        self._raise_for_notice(payload)

        series = payload.get("Time Series (Daily)")
        if not series:
            raise ProviderError(f"unexpected alpha vantage payload for {ticker}: {list(payload)}")

        df = pd.DataFrame(series).T
        df.columns = [c.split(". ", 1)[-1] for c in df.columns]
        df = df.rename(columns={"adjusted close": "adj_close"}).astype(float)
        return _normalise(df, ticker)

    @classmethod
    def _raise_for_notice(cls, payload: dict) -> None:
        """Split rate limiting from a bad key.

        Alpha Vantage returns both through ``Information``/``Note``, and its
        rate-limit text mentions premium plans, so the quota phrasing has to be
        checked before anything that looks like a key problem.
        """
        notice = payload.get("Information") or payload.get("Note")
        if not notice:
            if "Error Message" in payload:
                raise BadCredentials(f"alpha vantage rejected the request: {payload['Error Message']}")
            return

        lowered = notice.lower()
        if any(phrase in lowered for phrase in cls.RATE_LIMIT_PHRASES):
            raise RateLimited(f"alpha vantage quota exhausted: {notice}")
        if "api key" in lowered or "apikey" in lowered:
            raise BadCredentials(f"alpha vantage key problem: {notice}")
        raise ProviderError(f"alpha vantage returned a notice: {notice}")


PROVIDERS = {
    FixtureProvider.name: FixtureProvider,
    YFinanceProvider.name: YFinanceProvider,
    AlphaVantageProvider.name: AlphaVantageProvider,
}


def get_provider(name: str = "fixtures"):
    if name not in PROVIDERS:
        raise ValueError(f"unknown provider '{name}'. choose from {', '.join(PROVIDERS)}")
    return PROVIDERS[name]()


def _cache_fetch_date(path: Path) -> dt.date:
    """The calendar date ``path`` was last written, from its own mtime."""
    return dt.datetime.fromtimestamp(path.stat().st_mtime).date()


def load(ticker: str, provider: str = "fixtures", period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
    """Fetch bars, going through the on-disk cache for live providers.

    Fixtures are already local, so caching them would only add a way to serve
    stale data.

    D11: a live fetch is cached for same-day reuse only -- one fetch per
    ticker per calendar day, not forever. The cache is keyed by the day it
    was written (its own mtime), so a cache from an earlier day is treated
    as stale and re-fetched rather than served as if it were today's bar.
    Pass ``use_cache=False`` (the CLI's ``--refresh``/``--no-cache``) to force
    a live fetch regardless of the cache's age.
    """
    source = get_provider(provider)
    if provider == "fixtures" or not use_cache:
        return source.fetch(ticker, period)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"{provider}_{ticker.replace('.', '_')}_{period}.csv"
    if cached.exists() and _cache_fetch_date(cached) == dt.date.today():
        return _normalise(pd.read_csv(cached, index_col="date", parse_dates=True), ticker)

    df = source.fetch(ticker, period)
    df.to_csv(cached)
    return df


def local_csv_path(ticker: str, provider: str = "fixtures", period: str = "2y", use_cache: bool = True) -> Path:
    """The on-disk CSV ``load()`` serves ``ticker`` from, as a real file path.

    Calls ``load()`` first (cheap once cached) purely to make sure the file
    actually exists on disk -- a committed fixture always does, but a live
    provider's bars are only ever written to ``CACHE_DIR`` as a side effect
    of ``load()`` itself. A caller that needs a real file (not a DataFrame
    in memory), such as a subprocess shelling out to a sibling repo's own
    CLI, gets exactly the data ``load()`` would hand back, not a second,
    separately-fetched copy of it.

    Raises :class:`ProviderError` under the same conditions ``load()``
    does (no fixture, bad ticker, network failure) -- there is no file to
    point at when the fetch itself failed.
    """
    load(ticker, provider=provider, period=period, use_cache=use_cache)
    if provider == "fixtures" or not use_cache:
        return FixtureProvider().directory / f"{ticker.replace('.', '_')}.csv"
    return CACHE_DIR / f"{provider}_{ticker.replace('.', '_')}_{period}.csv"
