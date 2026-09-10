"""Does the screen actually do the one thing it exists to do?

Every other test file checks a unit in isolation (a formula, a config
default, a CSV round-trip). None of them ask the question a reviewer would
ask first: fed price/volume histories with a designed shape, does the
screen classify them the way that shape implies, and does filtering on
multiple independent factors at once actually narrow a universe down to
the right names for the right reasons?

Every regime below is built from named, documented parameters (a daily
drift, a volume trajectory) rather than random noise, and the expected
signs/orderings were confirmed by running the real signal functions
against them before being written down here - see the prototyping in this
commit's history if the numbers ever need re-deriving. That is what makes
this a test of the classifier's design rather than a snapshot of whatever
it happened to output.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stockstalker import screener
from stockstalker.data import providers


# ---------------------------------------------------------------------------
# Synthetic OHLCV construction - deliberately parameterized, not random.
# ---------------------------------------------------------------------------


def _ohlcv(close: np.ndarray, volume: np.ndarray, start: str = "2024-01-01") -> pd.DataFrame:
    n = len(close)
    dates = pd.bdate_range(start, periods=n)
    close = np.asarray(close, dtype=float)
    volume = np.asarray(volume, dtype=float)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.001
    low = np.minimum(open_, close) * 0.999
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=pd.Index(dates, name="date"),
    )


def _drift(n: int, daily_return: float, start_price: float = 100.0) -> np.ndarray:
    """Compounding price path at a constant daily return - a clean, noise-free trend."""
    return start_price * np.cumprod(1 + np.full(n, daily_return))


def _zigzag_flat(n: int, step: float = 0.4, start_price: float = 100.0) -> np.ndarray:
    """Perfectly alternating up/down bars of equal size, detrended to ~zero net drift.

    Equal average gain and average loss is what makes RSI land near 50 by
    construction, and the SMA fast/slow spread land near zero - "neutral" by
    design, not by luck.
    """
    delta = np.where(np.arange(n) % 2 == 0, step, -step)
    walk = np.cumsum(delta)
    detrended = walk - walk[-1] * np.arange(n) / n
    return start_price + detrended


def _rising_volume(n: int, start: float, step: float) -> np.ndarray:
    return start + step * np.arange(n)


def _falling_volume(n: int, start: float, step: float) -> np.ndarray:
    return np.maximum(start - step * np.arange(n), 5_000)


def _flat_volume(n: int, level: float) -> np.ndarray:
    return np.full(n, float(level))


N = 150  # comfortably past every lookback the signals use (slow=50, macd=26+9, z/obv=20)

REGIMES = {
    # name -> (close, volume) - each one engineered to exercise a specific,
    # named combination of trend / momentum / volume / liquidity.
    "strong_up_highvol": (
        _drift(N, 0.008),
        _rising_volume(N, 200_000, 2_000),
    ),
    "strong_down_lowvol": (
        _drift(N, -0.008),
        _falling_volume(N, 400_000, 2_500),
    ),
    "flat_choppy": (
        _zigzag_flat(N),
        _flat_volume(N, 100_000),
    ),
    "up_with_fading_volume": (
        _drift(N, 0.004),
        _falling_volume(N, 300_000, 1_800),
    ),
    "thin_rocket": (
        _drift(N, 0.01),
        _flat_volume(N, 3_000),
    ),
    "flat_megacap": (
        _zigzag_flat(N, step=0.3),
        _rising_volume(N, 900_000, 3_000),
    ),
}


@pytest.fixture(scope="module")
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


def _signals_and_score(name: str, cfg):
    close, volume = REGIMES[name]
    df = _ohlcv(close, volume)
    signals = screener.compute_signals(df, cfg)
    score = screener.blended_score(signals, cfg["weights"])
    liquidity = screener.liquidity_metrics(df)
    return df, signals, score, liquidity


# ---------------------------------------------------------------------------
# A. Does each factor classify its own designed regime correctly?
# ---------------------------------------------------------------------------


def test_sustained_uptrend_with_rising_volume_classifies_bullish_on_every_factor(cfg):
    _, signals, score, _ = _signals_and_score("strong_up_highvol", cfg)
    assert signals["trend"] > 0.5
    assert signals["momentum"] > 0.3
    assert signals["volume"] > 0.3
    assert score > 0.8


def test_sustained_downtrend_with_falling_volume_classifies_bearish_on_every_factor(cfg):
    _, signals, score, _ = _signals_and_score("strong_down_lowvol", cfg)
    assert signals["trend"] < -0.5
    assert signals["momentum"] < -0.2
    assert signals["volume"] < -0.3
    assert score < 0.3


def test_zero_drift_zigzag_classifies_as_genuinely_neutral(cfg):
    """A series built to have no net trend and equal up/down bars should score near 0.5.

    This is the control: a classifier that always leans bullish or always
    leans bearish regardless of input would fail this even though it might
    pass the two directional tests above by coincidence.
    """
    _, signals, score, _ = _signals_and_score("flat_choppy", cfg)
    assert signals["trend"] == pytest.approx(0.0, abs=0.05)
    assert signals["volume"] == pytest.approx(0.0, abs=0.05)
    assert score == pytest.approx(0.5, abs=0.05)


def test_uptrend_on_fading_volume_is_bullish_but_less_than_confirmed_uptrend(cfg):
    """Same direction of price move, weaker volume backing - the score should reflect that gradation.

    If the blend only looked at trend, this would score identically to the
    confirmed-volume case. It does not, because volume is an independent
    input, not decoration.
    """
    _, strong_signals, strong_score, _ = _signals_and_score("strong_up_highvol", cfg)
    _, fading_signals, fading_score, _ = _signals_and_score("up_with_fading_volume", cfg)
    assert fading_signals["trend"] > 0  # still a real uptrend
    assert fading_score < strong_score  # but weaker conviction scores lower
    assert fading_score > 0.5  # still net bullish, not neutral


def test_trend_score_is_a_graded_response_not_a_step_function(cfg):
    """Steeper uptrends should score strictly higher, up to the clip - proof this
    is a scaled measurement, not a bucketed classifier dressed up as a score."""
    returns = [0.0005, 0.0015, 0.003, 0.006]
    scores = []
    for r in returns:
        close = _drift(N, r)
        volume = _flat_volume(N, 150_000)
        df = _ohlcv(close, volume)
        scores.append(screener.compute_signals(df, cfg)["trend"])
    assert scores == sorted(scores)
    assert len(set(scores)) == len(scores)  # strictly increasing, no ties
    assert scores[-1] < 1.0  # this slope hasn't saturated the clip yet


# ---------------------------------------------------------------------------
# B. Config responsiveness - does the blend actually obey its own weights?
# ---------------------------------------------------------------------------


def test_changing_weights_flips_which_of_two_opposed_candidates_ranks_first():
    """A trend-strong/momentum-weak name and a momentum-strong/trend-weak name,
    reranked under two opposed weight configs. If the ranking didn't move, the
    weights in config/screen.yaml would be decoration, not real configuration."""
    trend_leader = {"ticker": "TREND_LEAD", "score": None,
                     "_signals": {"trend": 0.9, "momentum": -0.6, "volume": 0.0}}
    momentum_leader = {"ticker": "MOM_LEAD", "score": None,
                        "_signals": {"trend": -0.6, "momentum": 0.9, "volume": 0.0}}

    def scored(candidate, weights):
        c = dict(candidate)
        c["score"] = screener.blended_score(candidate["_signals"], weights)
        return c

    trend_heavy = {"trend": 0.8, "momentum": 0.1, "volume": 0.1}
    momentum_heavy = {"trend": 0.1, "momentum": 0.8, "volume": 0.1}

    ranked_trend_heavy = screener.rank(
        [scored(trend_leader, trend_heavy), scored(momentum_leader, trend_heavy)]
    )
    ranked_momentum_heavy = screener.rank(
        [scored(trend_leader, momentum_heavy), scored(momentum_leader, momentum_heavy)]
    )

    assert ranked_trend_heavy[0]["ticker"] == "TREND_LEAD"
    assert ranked_momentum_heavy[0]["ticker"] == "MOM_LEAD"


# ---------------------------------------------------------------------------
# C. Complex multi-layer filtering, end to end through build_screen.
# ---------------------------------------------------------------------------

# Six tickers, each excluded (or not) for a distinct, independently-verifiable
# reason once both a score gate and a liquidity gate apply together:
#
#            regime                    passes score (>=0.65)?  passes liquidity (>=100k)?
#   ROCKET   strong_up_highvol          yes                      yes            -> survives
#   PENNY    thin_rocket                yes                      no (illiquid)  -> dropped
#   MEGACAP  flat_megacap               no (flat)                yes            -> dropped
#   CRASH    strong_down_lowvol         no                       no             -> dropped
#   FADER    up_with_fading_volume      yes                      no             -> dropped
#   CHOPPY   flat_choppy                no                       yes (== floor) -> dropped

TICKER_REGIME = {
    "ROCKET.NS": "strong_up_highvol",
    "PENNY.NS": "thin_rocket",
    "MEGACAP.NS": "flat_megacap",
    "CRASH.NS": "strong_down_lowvol",
    "FADER.NS": "up_with_fading_volume",
    "CHOPPY.NS": "flat_choppy",
}

MIN_SCORE = 0.65
MIN_ADV_20D = 100_000


@pytest.fixture
def synthetic_universe(tmp_path, monkeypatch):
    """Write the six regimes out as real fixture CSVs and point FixtureProvider at them.

    Going through build_screen -> screen_ticker -> load -> FixtureProvider,
    exactly like a real run, rather than calling apply_filters on hand-built
    dicts - this is what makes it an end-to-end test of the filtering
    pipeline instead of another unit test of one function.
    """
    fixture_dir = tmp_path / "ohlcv"
    fixture_dir.mkdir()
    for ticker, regime in TICKER_REGIME.items():
        close, volume = REGIMES[regime]
        df = _ohlcv(close, volume)
        df.to_csv(fixture_dir / f"{ticker.replace('.', '_')}.csv")
    monkeypatch.setattr(providers, "FIXTURE_DIR", fixture_dir)
    return list(TICKER_REGIME)


def test_combined_score_and_liquidity_gates_keep_only_the_one_ticker_that_clears_both(
    cfg, synthetic_universe
):
    filters = {"min_adv_20d": MIN_ADV_20D, "min_score": MIN_SCORE}
    cfg_run = {**cfg, "filters": filters}
    screen = screener.build_screen(synthetic_universe, "fixtures", cfg_run, "TEST", "2026-01-01")

    survivors = [c["ticker"] for c in screen["candidates"]]
    assert survivors == ["ROCKET.NS"]
    assert screen["candidates"][0]["rank"] == 1


def test_each_dropped_ticker_was_excluded_for_its_own_documented_reason(cfg, synthetic_universe):
    """Multi-layer filtering is only meaningful if it's rejecting names for the
    right, independent reasons - not just rejecting "most things" by accident.
    Recompute the raw (pre-filter) numbers and check each ticker against the
    gate it was designed to fail."""
    errors: list[str] = []
    unfiltered_cfg = {**cfg, "filters": {"min_adv_20d": 0, "min_score": 0.0}}
    screen = screener.build_screen(
        synthetic_universe, "fixtures", unfiltered_cfg, "TEST", "2026-01-01", errors
    )
    by_ticker = {c["ticker"]: c for c in screen["candidates"]}
    assert not errors

    def passes_score(ticker):
        return by_ticker[ticker]["score"] >= MIN_SCORE

    def passes_liquidity(ticker):
        return by_ticker[ticker]["liquidity"]["adv_20d"] >= MIN_ADV_20D

    assert passes_score("ROCKET.NS") and passes_liquidity("ROCKET.NS")
    assert passes_score("PENNY.NS") and not passes_liquidity("PENNY.NS")
    assert not passes_score("MEGACAP.NS") and passes_liquidity("MEGACAP.NS")
    assert not passes_score("CRASH.NS") and not passes_liquidity("CRASH.NS")
    assert passes_score("FADER.NS") and not passes_liquidity("FADER.NS")
    assert not passes_score("CHOPPY.NS") and passes_liquidity("CHOPPY.NS")


def test_liquidity_gate_boundary_is_inclusive(cfg, synthetic_universe):
    """CHOPPY.NS's 20-day average volume is built to land exactly on MIN_ADV_20D.
    ``>=`` means it should clear the liquidity gate on that value alone - this
    pins down the boundary semantics apply_filters actually implements."""
    errors: list[str] = []
    unfiltered_cfg = {**cfg, "filters": {"min_adv_20d": 0, "min_score": 0.0}}
    screen = screener.build_screen(
        synthetic_universe, "fixtures", unfiltered_cfg, "TEST", "2026-01-01", errors
    )
    choppy = next(c for c in screen["candidates"] if c["ticker"] == "CHOPPY.NS")
    assert choppy["liquidity"]["adv_20d"] == pytest.approx(MIN_ADV_20D, rel=0.01)

    liquidity_only = screener.apply_filters(
        screen["candidates"], {"min_adv_20d": MIN_ADV_20D, "min_score": 0.0}
    )
    assert "CHOPPY.NS" in [c["ticker"] for c in liquidity_only]


def test_tightening_the_score_gate_monotonically_shrinks_the_survivor_set(cfg, synthetic_universe):
    """Raising the bar should never let a previously-excluded name back in.

    A screen built on real classification should behave like a real filter:
    survivors at a stricter threshold are always a subset of survivors at a
    looser one."""
    errors: list[str] = []
    unfiltered_cfg = {**cfg, "filters": {"min_adv_20d": 0, "min_score": 0.0}}
    screen = screener.build_screen(
        synthetic_universe, "fixtures", unfiltered_cfg, "TEST", "2026-01-01", errors
    )
    loose = {c["ticker"] for c in screener.apply_filters(screen["candidates"], {"min_adv_20d": 0, "min_score": 0.3})}
    strict = {c["ticker"] for c in screener.apply_filters(screen["candidates"], {"min_adv_20d": 0, "min_score": 0.7})}
    assert strict.issubset(loose)
    assert strict != loose  # the tightened gate must actually drop someone, or this proves nothing
