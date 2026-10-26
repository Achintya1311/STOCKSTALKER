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
    # Day 6 (R5): the real fixture now also carries var_99/cvar_99/kupiec_95/kupiec_99 --
    # additive, so the v0.3 keys this gate has always required are still all present.
    assert risk.REQUIRED_RISK_KEYS <= set(loaded)
    assert loaded["var_95"] == pytest.approx(-0.09153951300729178)


def test_load_contract_still_accepts_a_v03_shaped_block_with_no_day6_keys(tmp_path):
    """Backward compatible: a contract that never got regenerated still loads."""
    old_shaped = tmp_path / "old.json"
    old_shaped.write_text(json.dumps({"risk": SYNTHETIC_RISK}))
    loaded = risk.load_contract(old_shaped)
    assert set(loaded) == risk.REQUIRED_RISK_KEYS


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
    """No ``risk`` payload passed (the old call shape): still falls back to the
    static, README-sourced table, so any caller that hasn't been touched yet
    keeps working exactly as before Day 6."""
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


# -- Day 6 (R5): once the contract itself carries kupiec_95/kupiec_99, the note
# is computed from those real fields instead of the hardcoded, README-sourced
# table (which would otherwise go stale the moment the backtest is re-run).


def test_kupiec_note_computes_the_verdict_from_the_real_contract_once_it_carries_kupiec_99():
    real_risk = risk.load_contract(RELIANCE_CONTRACT)
    assert "kupiec_99" in real_risk
    note = risk.kupiec_note("RELIANCE", real_risk)
    assert note is not None
    assert "not rejected at 95%" in note
    assert "REJECTED at 99%" in note
    assert "10/500" in note


def test_kupiec_note_computes_the_double_rejection_for_gulfoillub():
    gulf_risk = risk.load_contract(ROOT / "fixtures" / "risk" / "GULFOILLUB.json")
    note = risk.kupiec_note("GULFOILLUB", gulf_risk)
    assert note is not None
    assert "REJECTED at both 95%" in note
    assert "114/3,006" in note
    assert "44/3,006" in note


def test_kupiec_note_falls_back_to_the_static_table_for_a_v03_shaped_contract():
    assert risk.kupiec_note("RELIANCE", SYNTHETIC_RISK) == risk.kupiec_note("RELIANCE")


def test_kupiec_note_fallback_ignores_an_unrelated_risk_payload_without_kupiec_99():
    assert risk.kupiec_note("TATACHEM", SYNTHETIC_RISK) is None


# D36: monte-carlo-risk-lab's pre-registered out-of-sample backtest (GARCH-t vs
# constant-volatility Gaussian) travels in an additive ``oos_var`` block; the
# note adds one method-only sentence from it when present.


def test_kupiec_note_adds_the_out_of_sample_result_for_gulfoillub():
    gulf_risk = risk.load_contract(ROOT / "fixtures" / "risk" / "GULFOILLUB.json")
    assert gulf_risk["oos_var"]["n_test"] == 2506
    note = risk.kupiec_note("GULFOILLUB", gulf_risk)
    assert "REJECTED at both 95%" in note  # the in-sample result stays
    assert "Out of sample (pre-registered, 2,506 test days" in note
    assert "GARCH(1,1)-t passes all criteria" in note
    assert "21 vs 25.1 expected" in note
    assert "constant-volatility Gaussian fails" in note
    assert "42 vs 25.1" in note


def test_kupiec_note_is_unchanged_without_an_oos_var_block():
    real_risk = risk.load_contract(RELIANCE_CONTRACT)
    assert "oos_var" not in real_risk
    assert "Out of sample" not in risk.kupiec_note("RELIANCE", real_risk)
