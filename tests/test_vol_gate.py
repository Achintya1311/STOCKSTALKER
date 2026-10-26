"""Vol gate (v0.6) tests: contract loading, ticker matching, and the CLI
end to end against the real implied-vol-surface fixture."""

import json
from pathlib import Path

import pytest

from stockstalker import screener
from stockstalker.gates import vol

ROOT = Path(__file__).resolve().parent.parent
RELIANCE_CONTRACT = ROOT / "fixtures" / "vol" / "RELIANCE.json"

# implied-vol-surface's own tests check these numbers against its IV solver
# and surface fit; here they're just an opaque payload this repo passes
# through.
SYNTHETIC_VOL = {
    "atm_iv_30d": 0.28,
    "skew_25d": 0.04,
    "term_slope": -0.02,
    "iv_rank_1y": 0.62,
}


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def screen(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    return screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-09-28")


def test_load_contract_reads_the_real_implied_vol_surface_fixture():
    loaded = vol.load_contract(RELIANCE_CONTRACT)
    assert set(loaded) == vol.REQUIRED_VOL_KEYS
    assert loaded["atm_iv_30d"] == pytest.approx(0.2801038061895711)
    # Honest gap, not a bug: no real trailing-year history exists yet
    # (see implied-vol-surface's README Limitations).
    assert loaded["iv_rank_1y"] is None


def test_load_contract_rejects_a_vol_block_missing_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"vol": {"atm_iv_30d": 0.2}}))
    with pytest.raises(ValueError, match="missing keys"):
        vol.load_contract(bad)


def test_load_contract_rejects_a_file_with_no_vol_block(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "v1"}))
    with pytest.raises(ValueError, match="no 'vol' object"):
        vol.load_contract(bad)


def test_load_contract_accepts_a_present_but_null_iv_rank_1y(tmp_path):
    """A missing key is rejected; a present key with value null (the honest
    gap this integration ships) is not the same thing and must be accepted."""
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"vol": {**SYNTHETIC_VOL, "iv_rank_1y": None}}))
    loaded = vol.load_contract(ok)
    assert loaded["iv_rank_1y"] is None


def test_apply_vol_gate_attaches_the_block_to_the_matching_ticker_only(screen):
    gated, matched = vol.apply_vol_gate(screen, "RELIANCE.NS", SYNTHETIC_VOL)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["vol"] == SYNTHETIC_VOL
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "vol" not in candidate


def test_apply_vol_gate_matches_without_the_ns_suffix(screen):
    """implied-vol-surface's tickers carry no yfinance suffix (e.g. RELIANCE, not RELIANCE.NS)."""
    gated, matched = vol.apply_vol_gate(screen, "reliance", SYNTHETIC_VOL)
    assert matched is True
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["vol"] == SYNTHETIC_VOL


def test_apply_vol_gate_leaves_every_candidate_unchanged_when_ticker_is_outside_the_universe(screen):
    gated, matched = vol.apply_vol_gate(screen, "GULFOILLUB", SYNTHETIC_VOL)
    assert matched is False
    assert gated["candidates"] == screen["candidates"]


def test_apply_vol_gate_does_not_mutate_the_input_screen(screen):
    before = json.loads(json.dumps(screen))
    vol.apply_vol_gate(screen, "RELIANCE.NS", SYNTHETIC_VOL)
    assert screen == before


def test_main_writes_the_gated_screen_when_the_ticker_matches(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"vol": SYNTHETIC_VOL}))
    out_path = tmp_path / "screen_gated.json"

    exit_code = vol.main(
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
    assert by_ticker["RELIANCE.NS"]["vol"] == SYNTHETIC_VOL


def test_main_against_the_real_reliance_fixture_reports_a_genuine_match(screen, tmp_path, capsys):
    """End-to-end against the actual implied-vol-surface output: like v0.3's and v0.2's
    integrations (and unlike v0.7's GULFOILLUB non-match), RELIANCE is one of this repo's
    own three universe tickers, so this is a real match, not a synthetic stand-in."""
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))

    exit_code = vol.main(
        [
            "--screen", str(screen_path),
            "--contract", str(RELIANCE_CONTRACT),
            "--ticker", "RELIANCE",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached implied-vol-surface's contract" in out

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["RELIANCE.NS"]["vol"]["atm_iv_30d"] == pytest.approx(0.2801038061895711)
    assert by_ticker["RELIANCE.NS"]["vol"]["iv_rank_1y"] is None
    for ticker, candidate in by_ticker.items():
        if ticker != "RELIANCE.NS":
            assert "vol" not in candidate


def test_main_defaults_out_to_overwriting_the_screen_in_place(screen, tmp_path):
    screen_path = tmp_path / "screen.json"
    screen_path.write_text(json.dumps(screen))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({"vol": SYNTHETIC_VOL}))

    vol.main(["--screen", str(screen_path), "--contract", str(contract_path), "--ticker", "TATACHEM.NS"])

    gated = json.loads(screen_path.read_text())
    by_ticker = {c["ticker"]: c for c in gated["candidates"]}
    assert by_ticker["TATACHEM.NS"]["vol"] == SYNTHETIC_VOL


def test_committed_fixture_comes_from_a_real_nse_capture():
    # D39: the 28 Sep fixture came from implied-vol-surface's synthetic chain
    # (atm 0.2150, term slope -0.0199). Regenerated from the real 2026-10-24
    # capture (data_date 2026-10-23, source nse).
    loaded = vol.load_contract(RELIANCE_CONTRACT)
    assert loaded["skew_25d"] == pytest.approx(0.020981022241451375)
    assert loaded["term_slope"] == pytest.approx(0.11364992822803338)
