"""Risk gate (v0.3) tests: contract loading, ticker matching, and the CLI
end to end against the real monte-carlo-risk-lab fixture."""

import json
from pathlib import Path

import pytest

from stockstalker import screener
from stockstalker.gates import risk

ROOT = Path(__file__).resolve().parent.parent
RELIANCE_CONTRACT = ROOT / "fixtures" / "risk" / "RELIANCE.json"

# monte-carlo-risk-lab's own tests check these numbers against Black-Scholes
# and the Kupiec backtest; here they're just an opaque payload this repo
# passes through.
SYNTHETIC_RISK = {
    "var_95": -0.032,
    "cvar_95": -0.048,
    "max_dd_sim": -0.21,
    "horizon_days": 20,
}


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def screen(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    return screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-09-18")


def test_load_contract_reads_the_real_monte_carlo_risk_lab_fixture():
    loaded = risk.load_contract(RELIANCE_CONTRACT)
    assert set(loaded) == risk.REQUIRED_RISK_KEYS
    assert loaded["var_95"] == pytest.approx(-0.09153951300729178)


def test_load_contract_rejects_a_risk_block_missing_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"risk": {"var_95": -0.03}}))
    with pytest.raises(ValueError, match="missing keys"):
        risk.load_contract(bad)


def test_load_contract_rejects_a_file_with_no_risk_block(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "v1"}))
    with pytest.raises(ValueError, match="no 'risk' object"):
        risk.load_contract(bad)


def test_apply_risk_gate_attaches_the_block_to_the_matching_ticker_only(screen):
    gated, matched = risk.apply_risk_gate(screen, "RELIANCE.NS", SYNTHETIC_RISK)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["risk"] == SYNTHETIC_RISK
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "risk" not in candidate


def test_apply_risk_gate_matches_without_the_ns_suffix(screen):
    """monte-carlo-risk-lab's tickers carry no yfinance suffix (e.g. RELIANCE, not RELIANCE.NS)."""
    gated, matched = risk.apply_risk_gate(screen, "reliance", SYNTHETIC_RISK)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["risk"] == SYNTHETIC_RISK


def test_apply_risk_gate_leaves_every_candidate_unchanged_when_ticker_is_outside_the_universe(screen):
    gated, matched = risk.apply_risk_gate(screen, "GULFOILLUB", SYNTHETIC_RISK)
    assert matched is False
    assert gated["candidates"] == screen["candidates"]


def test_apply_risk_gate_does_not_mutate_the_input_screen(screen):
    before = json.loads(json.dumps(screen))
    risk.apply_risk_gate(screen, "RELIANCE.NS", SYNTHETIC_RISK)
    assert screen == before


def test_main_writes_the_gated_screen_when_the_ticker_matches(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"risk": SYNTHETIC_RISK}))
    out_path = tmp_path / "screen_gated.json"

    exit_code = risk.main(
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
    assert by_ticker["RELIANCE.NS"]["risk"] == SYNTHETIC_RISK


def test_main_against_the_real_reliance_fixture_reports_a_genuine_match(screen, tmp_path, capsys):
    """End-to-end against the actual monte-carlo-risk-lab output: unlike v0.7's GULFOILLUB
    (researched by reverse-dcf-engine but outside this repo's fixture universe), RELIANCE
    is one of this repo's own three universe tickers, so this is a real match, not a
    synthetic stand-in."""
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))

    exit_code = risk.main(
        [
            "--screen", str(screen_path),
            "--contract", str(RELIANCE_CONTRACT),
            "--ticker", "RELIANCE",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached monte-carlo-risk-lab's contract" in out

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["risk"]["var_95"] == pytest.approx(-0.09153951300729178)
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "risk" not in candidate


def test_main_defaults_out_to_overwriting_the_screen_in_place(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"risk": SYNTHETIC_RISK}))

    risk.main(["--screen", str(screen_path), "--contract", str(contract_path), "--ticker", "TATACHEM.NS"])

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["TATACHEM.NS"]["risk"] == SYNTHETIC_RISK


# -- Day 5 (R5): the Kupiec/99% gap caveat -----------------------------------


def test_kupiec_note_cites_the_real_rejection_for_reliance_and_gulfoillub():
    reliance_note = risk.kupiec_note("RELIANCE")
    assert reliance_note is not None
    assert "REJECTED at 99%" in reliance_note
    assert "not rejected at 95%" in reliance_note

    gulf_note = risk.kupiec_note("GULFOILLUB")
    assert gulf_note is not None
    assert "REJECTED at both 95%" in gulf_note


def test_kupiec_note_matches_without_the_ns_suffix():
    assert risk.kupiec_note("reliance.ns") == risk.kupiec_note("RELIANCE")


def test_kupiec_note_is_none_for_an_unlisted_ticker():
    assert risk.kupiec_note("TATACHEM") is None
