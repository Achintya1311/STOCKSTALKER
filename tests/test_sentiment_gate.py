"""Sentiment gate (v0.5) tests: contract loading, ticker matching, and the
CLI end to end against the real headline-sentiment-vs-price fixture."""

import json
from pathlib import Path

import pytest

from stockstalker import screener
from stockstalker.gates import sentiment

ROOT = Path(__file__).resolve().parent.parent
INFY_CONTRACT = ROOT / "fixtures" / "sentiment" / "INFY.json"

# headline-sentiment-vs-price's own tests cover how this number is derived;
# here it's just an opaque payload this repo passes through.
SYNTHETIC_SENTIMENT = {
    "score_7d": 0.31,
    "headline_count_7d": 12,
    "model": "finbert",
    "coverage": "partial",
}


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def screen(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    return screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-09-29")


def test_load_contract_reads_the_real_headline_sentiment_fixture():
    loaded = sentiment.load_contract(INFY_CONTRACT)
    assert set(loaded) == sentiment.REQUIRED_SENTIMENT_KEYS
    assert loaded["score_7d"] == pytest.approx(0.296)
    assert loaded["model"] == "vader"


def test_load_contract_rejects_a_sentiment_block_missing_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"sentiment": {"score_7d": 0.1}}))
    with pytest.raises(ValueError, match="missing keys"):
        sentiment.load_contract(bad)


def test_load_contract_rejects_a_file_with_no_sentiment_block(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "v1"}))
    with pytest.raises(ValueError, match="no 'sentiment' object"):
        sentiment.load_contract(bad)


def test_load_contract_accepts_a_null_score_7d(tmp_path):
    """headline-sentiment-vs-price ships score_7d: null when no headline in
    its sample resolved to the requested ticker within the window - the
    key must still be present, but its value is allowed to be null."""
    path = tmp_path / "null_score.json"
    path.write_text(
        json.dumps(
            {"sentiment": {"score_7d": None, "headline_count_7d": 0, "model": "vader", "coverage": "partial"}}
        )
    )
    loaded = sentiment.load_contract(path)
    assert loaded["score_7d"] is None


def test_apply_sentiment_gate_attaches_the_block_to_the_matching_ticker_only(screen):
    gated, matched = sentiment.apply_sentiment_gate(screen, "RELIANCE.NS", SYNTHETIC_SENTIMENT)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["sentiment"] == SYNTHETIC_SENTIMENT
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "sentiment" not in candidate


def test_apply_sentiment_gate_matches_without_the_ns_suffix(screen):
    gated, matched = sentiment.apply_sentiment_gate(screen, "reliance", SYNTHETIC_SENTIMENT)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["sentiment"] == SYNTHETIC_SENTIMENT


def test_apply_sentiment_gate_leaves_every_candidate_unchanged_when_ticker_is_outside_the_universe(screen):
    """The real INFY.NS contract against this repo's 3-ticker fixture universe
    (RELIANCE/TATACHEM/CROMPTON): no overlap, and that is an expected outcome
    to report, not an error."""
    gated, matched = sentiment.apply_sentiment_gate(screen, "INFY.NS", SYNTHETIC_SENTIMENT)
    assert matched is False
    assert gated["candidates"] == screen["candidates"]


def test_apply_sentiment_gate_does_not_mutate_the_input_screen(screen):
    before = json.loads(json.dumps(screen))
    sentiment.apply_sentiment_gate(screen, "RELIANCE.NS", SYNTHETIC_SENTIMENT)
    assert screen == before


def test_main_writes_the_gated_screen_when_the_ticker_matches(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"sentiment": SYNTHETIC_SENTIMENT}))
    out_path = tmp_path / "screen_gated.json"

    exit_code = sentiment.main(
        [
            "--screen", str(screen_path),
            "--contract", str(contract_path),
            "--ticker", "RELIANCE.NS",
            "--out", str(out_path),
        ]
    )
    assert exit_code == 0

    gated = json.loads(out_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["sentiment"] == SYNTHETIC_SENTIMENT


def test_main_against_the_real_infy_fixture_reports_no_match_honestly(screen, tmp_path, capsys):
    """End-to-end against the actual headline-sentiment-vs-price output: INFY.NS
    isn't in this repo's fixture universe, so the honest result is zero
    matches, not a fabricated one."""
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))

    exit_code = sentiment.main(
        [
            "--screen", str(screen_path),
            "--contract", str(INFY_CONTRACT),
            "--ticker", "INFY.NS",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "is not in this screen's universe" in out

    unchanged = json.loads(screen_path.read_text())
    assert all("sentiment" not in c for c in unchanged["candidates"])


def test_main_defaults_out_to_overwriting_the_screen_in_place(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"sentiment": SYNTHETIC_SENTIMENT}))

    sentiment.main(["--screen", str(screen_path), "--contract", str(contract_path), "--ticker", "TATACHEM.NS"])

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["TATACHEM.NS"]["sentiment"] == SYNTHETIC_SENTIMENT
