"""Fundamentals gate (v0.8) tests: contract loading, ticker matching, and the
CLI end to end against the real three-statement-model fixture."""

import json
from pathlib import Path

import pytest

from stockstalker import screener
from stockstalker.gates import fundamentals

ROOT = Path(__file__).resolve().parent.parent
GULFOILLUB_CONTRACT = ROOT / "fixtures" / "fundamentals" / "GULFOILLUB.json"

# three-statement-model's own tests exercise the real linkage; here these are
# just an opaque payload this repo passes through.
SYNTHETIC_FUNDAMENTALS = {
    "fy3_revenue_cagr": 0.11,
    "fy3_ebit_margin": 0.19,
    "net_debt_ebitda_fy3": 1.8,
    "balance_check": "passed",
}


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def screen(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    return screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-10-11")


def test_load_contract_reads_the_real_three_statement_model_fixture():
    loaded = fundamentals.load_contract(GULFOILLUB_CONTRACT)
    assert fundamentals.REQUIRED_FUNDAMENTALS_KEYS <= set(loaded)
    assert loaded["balance_check"] == "passed"
    assert loaded["fy3_revenue_cagr"] == pytest.approx(0.15390188144032124)


def test_load_contract_rejects_a_fundamentals_block_missing_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"fundamentals": {"fy3_revenue_cagr": 0.1}}))
    with pytest.raises(ValueError, match="missing keys"):
        fundamentals.load_contract(bad)


def test_load_contract_rejects_a_file_with_no_fundamentals_block(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "v1"}))
    with pytest.raises(ValueError, match="no 'fundamentals' object"):
        fundamentals.load_contract(bad)


def test_apply_fundamentals_gate_attaches_the_block_to_the_matching_ticker_only(screen):
    gated, matched = fundamentals.apply_fundamentals_gate(screen, "RELIANCE.NS", SYNTHETIC_FUNDAMENTALS)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["fundamentals"] == SYNTHETIC_FUNDAMENTALS
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "fundamentals" not in candidate


def test_apply_fundamentals_gate_matches_without_the_ns_suffix(screen):
    """three-statement-model's tickers carry no yfinance suffix (e.g. GULFOILLUB, not GULFOILLUB.NS)."""
    gated, matched = fundamentals.apply_fundamentals_gate(screen, "reliance", SYNTHETIC_FUNDAMENTALS)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["fundamentals"] == SYNTHETIC_FUNDAMENTALS


def test_apply_fundamentals_gate_leaves_every_candidate_unchanged_when_ticker_is_outside_the_universe(screen):
    """The real GULFOILLUB contract against this repo's 3-ticker fixture universe: no overlap,
    and that is an expected outcome to report, not an error -- the same shape v0.7's
    reverse-dcf-engine integration already recorded."""
    gated, matched = fundamentals.apply_fundamentals_gate(screen, "GULFOILLUB", SYNTHETIC_FUNDAMENTALS)
    assert matched is False
    assert gated["candidates"] == screen["candidates"]


def test_apply_fundamentals_gate_does_not_mutate_the_input_screen(screen):
    before = json.loads(json.dumps(screen))
    fundamentals.apply_fundamentals_gate(screen, "RELIANCE.NS", SYNTHETIC_FUNDAMENTALS)
    assert screen == before


def test_main_writes_the_gated_screen_when_the_ticker_matches(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"fundamentals": SYNTHETIC_FUNDAMENTALS}))
    out_path = tmp_path / "screen_gated.json"

    exit_code = fundamentals.main(
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
    assert by_ticker["RELIANCE.NS"]["fundamentals"] == SYNTHETIC_FUNDAMENTALS


def test_main_against_the_real_gulfoillub_fixture_reports_no_match_honestly(screen, tmp_path, capsys):
    """End-to-end against the actual three-statement-model output: GULFOILLUB isn't in this
    repo's fixture universe, so the honest result is zero matches, not a fabricated one."""
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))

    exit_code = fundamentals.main(
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
    assert all("fundamentals" not in c for c in unchanged["candidates"])


def test_main_defaults_out_to_overwriting_the_screen_in_place(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"fundamentals": SYNTHETIC_FUNDAMENTALS}))

    fundamentals.main(["--screen", str(screen_path), "--contract", str(contract_path), "--ticker", "TATACHEM.NS"])

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["TATACHEM.NS"]["fundamentals"] == SYNTHETIC_FUNDAMENTALS
