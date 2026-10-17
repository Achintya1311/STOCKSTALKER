"""Factor gate (v0.2) tests: contract loading, ticker matching, and the CLI
end to end against the real fama-french-factor-model fixture."""

import json
from pathlib import Path

import pytest

from stockstalker import screener
from stockstalker.gates import factor

ROOT = Path(__file__).resolve().parent.parent
RELIANCE_CONTRACT = ROOT / "fixtures" / "factor" / "RELIANCE.json"

# fama-french-factor-model's own tests check these numbers against the
# underlying OLS regression; here they're just an opaque payload this repo
# passes through.
SYNTHETIC_FACTOR = {
    "alpha_annual": 0.021,
    "alpha_t": 1.3,
    "significant": False,
    "loadings": {"mkt": 1.05, "smb": 0.42, "hml": -0.18, "mom": 0.09},
}


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def screen(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    return screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-09-20")


def test_load_contract_reads_the_real_fama_french_fixture():
    loaded = factor.load_contract(RELIANCE_CONTRACT)
    assert set(loaded) == factor.REQUIRED_FACTOR_KEYS
    assert loaded["alpha_annual"] == pytest.approx(-0.03862101486966241)
    assert loaded["significant"] is False
    assert set(loaded["loadings"]) == {"mkt", "smb", "hml", "rmw", "cma", "mom"}


def test_load_contract_rejects_a_factor_block_missing_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"factor": {"alpha_annual": 0.02}}))
    with pytest.raises(ValueError, match="missing keys"):
        factor.load_contract(bad)


def test_load_contract_rejects_a_file_with_no_factor_block(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "v1"}))
    with pytest.raises(ValueError, match="no 'factor' object"):
        factor.load_contract(bad)


def test_apply_factor_gate_attaches_the_block_to_the_matching_ticker_only(screen):
    gated, matched = factor.apply_factor_gate(screen, "RELIANCE.NS", SYNTHETIC_FACTOR)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["factor"] == SYNTHETIC_FACTOR
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "factor" not in candidate


def test_apply_factor_gate_matches_without_the_ns_suffix(screen):
    """fama-french-factor-model's tickers carry no yfinance suffix (e.g. RELIANCE, not RELIANCE.NS)."""
    gated, matched = factor.apply_factor_gate(screen, "reliance", SYNTHETIC_FACTOR)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["factor"] == SYNTHETIC_FACTOR


def test_apply_factor_gate_leaves_every_candidate_unchanged_when_ticker_is_outside_the_universe(screen):
    gated, matched = factor.apply_factor_gate(screen, "GULFOILLUB", SYNTHETIC_FACTOR)
    assert matched is False
    assert gated["candidates"] == screen["candidates"]


def test_apply_factor_gate_does_not_mutate_the_input_screen(screen):
    before = json.loads(json.dumps(screen))
    factor.apply_factor_gate(screen, "RELIANCE.NS", SYNTHETIC_FACTOR)
    assert screen == before


def test_main_writes_the_gated_screen_when_the_ticker_matches(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"factor": SYNTHETIC_FACTOR}))
    out_path = tmp_path / "screen_gated.json"

    exit_code = factor.main(
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
    assert by_ticker["RELIANCE.NS"]["factor"] == SYNTHETIC_FACTOR


def test_main_against_the_real_reliance_fixture_reports_a_genuine_match(screen, tmp_path, capsys):
    """End-to-end against the actual fama-french-factor-model output: like v0.3's RELIANCE
    match (and unlike v0.7's GULFOILLUB non-match), RELIANCE is one of this repo's own
    three universe tickers, so this is a real match, not a synthetic stand-in."""
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))

    exit_code = factor.main(
        [
            "--screen", str(screen_path),
            "--contract", str(RELIANCE_CONTRACT),
            "--ticker", "RELIANCE",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached fama-french-factor-model's contract" in out

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["factor"]["alpha_annual"] == pytest.approx(-0.03862101486966241)
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "factor" not in candidate


def test_main_defaults_out_to_overwriting_the_screen_in_place(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"factor": SYNTHETIC_FACTOR}))

    factor.main(["--screen", str(screen_path), "--contract", str(contract_path), "--ticker", "TATACHEM.NS"])

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["TATACHEM.NS"]["factor"] == SYNTHETIC_FACTOR


# -- Day 5 (R6): significance wording and the old-method label -------------


def test_significance_label_renders_words_not_booleans():
    assert factor.significance_label(True) == "significant"
    assert factor.significance_label(False) == "not significant"


def test_method_label_flags_reliance_as_old_method():
    note = factor.method_label("RELIANCE")
    assert note is not None
    assert "Ken French" in note
    assert "old method" in note


def test_method_label_matches_without_the_ns_suffix():
    assert factor.method_label("reliance.ns") == factor.method_label("RELIANCE")


def test_method_label_is_none_for_the_new_iima_method():
    assert factor.method_label("GULFOILLUB") is None
