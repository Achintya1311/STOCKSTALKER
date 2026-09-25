"""Sizing gate (v0.4) tests: contract loading, ticker matching, and the CLI
end to end against the real markowitz-portfolio-optimizer fixture."""

import json
from pathlib import Path

import pytest

from stockstalker import screener
from stockstalker.gates import sizing

ROOT = Path(__file__).resolve().parent.parent
RELIANCE_CONTRACT = ROOT / "fixtures" / "sizing" / "RELIANCE.json"

# markowitz-portfolio-optimizer's own tests check this number against its
# sector-capped SLSQP solve; here it's just an opaque payload this repo
# passes through.
SYNTHETIC_SIZING = {
    "weight": 0.35,
    "method": "max_sharpe_ledoit_wolf",
    "constraint_binding": "none",
}


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def screen(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    return screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-09-25")


def test_load_contract_reads_the_real_markowitz_fixture():
    loaded = sizing.load_contract(RELIANCE_CONTRACT)
    assert set(loaded) == sizing.REQUIRED_SIZING_KEYS
    assert loaded["weight"] == pytest.approx(0.5)
    assert loaded["method"] == "max_sharpe_ledoit_wolf"
    assert loaded["constraint_binding"] == "Energy"


def test_load_contract_rejects_a_sizing_block_missing_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"sizing": {"weight": 0.3}}))
    with pytest.raises(ValueError, match="missing keys"):
        sizing.load_contract(bad)


def test_load_contract_rejects_a_file_with_no_sizing_block(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "v1"}))
    with pytest.raises(ValueError, match="no 'sizing' object"):
        sizing.load_contract(bad)


def test_apply_sizing_gate_attaches_the_block_to_the_matching_ticker_only(screen):
    gated, matched = sizing.apply_sizing_gate(screen, "RELIANCE.NS", SYNTHETIC_SIZING)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["sizing"] == SYNTHETIC_SIZING
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "sizing" not in candidate


def test_apply_sizing_gate_matches_without_the_ns_suffix(screen):
    """markowitz-portfolio-optimizer's tickers carry the yfinance suffix already
    (RELIANCE.NS), but the gate should still match case-insensitively and
    suffix-insensitively, same as every other gate in this repo."""
    gated, matched = sizing.apply_sizing_gate(screen, "reliance", SYNTHETIC_SIZING)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["sizing"] == SYNTHETIC_SIZING


def test_apply_sizing_gate_leaves_every_candidate_unchanged_when_ticker_is_outside_the_universe(screen):
    gated, matched = sizing.apply_sizing_gate(screen, "GULFOILLUB", SYNTHETIC_SIZING)
    assert matched is False
    assert gated["candidates"] == screen["candidates"]


def test_apply_sizing_gate_does_not_mutate_the_input_screen(screen):
    before = json.loads(json.dumps(screen))
    sizing.apply_sizing_gate(screen, "RELIANCE.NS", SYNTHETIC_SIZING)
    assert screen == before


def test_main_writes_the_gated_screen_when_the_ticker_matches(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"sizing": SYNTHETIC_SIZING}))
    out_path = tmp_path / "screen_gated.json"

    exit_code = sizing.main(
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
    assert by_ticker["RELIANCE.NS"]["sizing"] == SYNTHETIC_SIZING


def test_main_against_the_real_reliance_fixture_reports_a_genuine_match(screen, tmp_path, capsys):
    """End-to-end against the actual markowitz-portfolio-optimizer output: like v0.3's
    RELIANCE risk contract (and unlike v0.7's GULFOILLUB valuation contract, which is
    outside this repo's 3-ticker fixture universe), RELIANCE.NS is one of this repo's
    own universe tickers, so this is a real match, not a synthetic stand-in."""
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))

    exit_code = sizing.main(
        [
            "--screen", str(screen_path),
            "--contract", str(RELIANCE_CONTRACT),
            "--ticker", "RELIANCE",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached markowitz-portfolio-optimizer's contract" in out

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["sizing"]["weight"] == pytest.approx(0.5)
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "sizing" not in candidate


def test_main_defaults_out_to_overwriting_the_screen_in_place(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"sizing": SYNTHETIC_SIZING}))

    sizing.main(["--screen", str(screen_path), "--contract", str(contract_path), "--ticker", "TATACHEM.NS"])

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["TATACHEM.NS"]["sizing"] == SYNTHETIC_SIZING
