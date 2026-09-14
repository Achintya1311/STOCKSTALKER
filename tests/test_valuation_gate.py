"""Valuation gate (v0.7) tests: contract loading, ticker matching, and the
CLI end to end against the real reverse-dcf-engine fixture."""

import json
from pathlib import Path

import pytest

from stockstalker import screener
from stockstalker.gates import valuation

ROOT = Path(__file__).resolve().parent.parent
GULFOILLUB_CONTRACT = ROOT / "fixtures" / "valuation" / "GULFOILLUB.json"

# reverse-dcf-engine's own tests round-trip these numbers back through its
# forward DCF; here they're just an opaque payload this repo passes through.
SYNTHETIC_VALUATION = {
    "implied_cagr": 0.10,
    "implied_ebit_margin": 0.20,
    "implied_reinvestment": 0.30,
    "breakeven_growth": 0.08,
}


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def screen(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    return screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-09-14")


def test_load_contract_reads_the_real_reverse_dcf_engine_fixture():
    loaded = valuation.load_contract(GULFOILLUB_CONTRACT)
    assert set(loaded) == valuation.REQUIRED_VALUATION_KEYS
    assert loaded["implied_cagr"] == pytest.approx(-0.004924241036374619)


def test_load_contract_rejects_a_valuation_block_missing_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"valuation": {"implied_cagr": 0.1}}))
    with pytest.raises(ValueError, match="missing keys"):
        valuation.load_contract(bad)


def test_load_contract_rejects_a_file_with_no_valuation_block(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "v1"}))
    with pytest.raises(ValueError, match="no 'valuation' object"):
        valuation.load_contract(bad)


def test_apply_valuation_gate_attaches_the_block_to_the_matching_ticker_only(screen):
    gated, matched = valuation.apply_valuation_gate(screen, "RELIANCE.NS", SYNTHETIC_VALUATION)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["valuation"] == SYNTHETIC_VALUATION
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "valuation" not in candidate


def test_apply_valuation_gate_matches_without_the_ns_suffix(screen):
    """reverse-dcf-engine's tickers carry no yfinance suffix (e.g. GULFOILLUB, not GULFOILLUB.NS)."""
    gated, matched = valuation.apply_valuation_gate(screen, "reliance", SYNTHETIC_VALUATION)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["valuation"] == SYNTHETIC_VALUATION


def test_apply_valuation_gate_leaves_every_candidate_unchanged_when_ticker_is_outside_the_universe(screen):
    """The real GULFOILLUB contract against this repo's 3-ticker fixture universe: no overlap,
    and that is an expected outcome to report, not an error."""
    gated, matched = valuation.apply_valuation_gate(screen, "GULFOILLUB", SYNTHETIC_VALUATION)
    assert matched is False
    assert gated["candidates"] == screen["candidates"]


def test_apply_valuation_gate_does_not_mutate_the_input_screen(screen):
    before = json.loads(json.dumps(screen))
    valuation.apply_valuation_gate(screen, "RELIANCE.NS", SYNTHETIC_VALUATION)
    assert screen == before


def test_main_writes_the_gated_screen_when_the_ticker_matches(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"valuation": SYNTHETIC_VALUATION}))
    out_path = tmp_path / "screen_gated.json"

    exit_code = valuation.main(
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
    assert by_ticker["RELIANCE.NS"]["valuation"] == SYNTHETIC_VALUATION


def test_main_against_the_real_gulfoillub_fixture_reports_no_match_honestly(screen, tmp_path, capsys):
    """End-to-end against the actual reverse-dcf-engine output: GULFOILLUB isn't in this
    repo's fixture universe, so the honest result is zero matches, not a fabricated one."""
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))

    exit_code = valuation.main(
        [
            "--screen", str(screen_path),
            "--contract", str(GULFOILLUB_CONTRACT),
            "--ticker", "GULFOILLUB",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "is not in this screen's universe" in out

    unchanged = json.loads(screen_path.read_text())
    assert all("valuation" not in c for c in unchanged["candidates"])


def test_main_defaults_out_to_overwriting_the_screen_in_place(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"valuation": SYNTHETIC_VALUATION}))

    valuation.main(["--screen", str(screen_path), "--contract", str(contract_path), "--ticker", "TATACHEM.NS"])

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["TATACHEM.NS"]["valuation"] == SYNTHETIC_VALUATION
