"""Front door Day 1: subject price section, peer table, and the CLI end to
end against the committed GULFOILLUB / lubricant-peer fixtures."""

import io
import json
import re
from pathlib import Path

import pandas as pd
import pytest
from rich.console import Console

from stockstalker import run, screener
from stockstalker.data.providers import FixtureProvider

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def gulfoillub():
    return FixtureProvider().fetch("GULFOILLUB.NS")


def render(table):
    buf = io.StringIO()
    Console(file=buf, width=200).print(table)
    return buf.getvalue()


def test_to_yf_ticker_adds_suffix_once():
    assert run.to_yf_ticker("gulfoillub") == "GULFOILLUB.NS"
    assert run.to_yf_ticker("GULFOILLUB.NS") == "GULFOILLUB.NS"


def test_trailing_return_matches_manual_close_ratio(gulfoillub):
    window = run.TRADING_DAYS_PER_YEAR
    expected = gulfoillub["close"].iloc[-1] / gulfoillub["close"].iloc[-(window + 1)] - 1
    assert run.trailing_return(gulfoillub) == pytest.approx(expected, abs=1e-4)


def test_trailing_return_is_none_below_window():
    short = pd.DataFrame(
        {
            "open": [1.0] * 10,
            "high": [1.0] * 10,
            "low": [1.0] * 10,
            "close": list(range(1, 11)),
            "volume": [100] * 10,
        }
    )
    assert run.trailing_return(short, window=252) is None


def test_trailing_volatility_is_nonnegative(gulfoillub):
    vol = run.trailing_volatility(gulfoillub)
    assert vol is not None
    assert vol >= 0


def test_trailing_volatility_is_none_below_window():
    short = pd.DataFrame(
        {
            "open": [1.0] * 10,
            "high": [1.0] * 10,
            "low": [1.0] * 10,
            "close": list(range(1, 11)),
            "volume": [100] * 10,
        }
    )
    assert run.trailing_volatility(short, window=252) is None


def test_build_subject_section_reuses_screener_scoring(cfg, gulfoillub):
    subject = run.build_subject_section("GULFOILLUB", "fixtures", cfg)
    signals = screener.compute_signals(gulfoillub, cfg)
    assert subject["ticker"] == "GULFOILLUB"
    assert subject["score"] == screener.blended_score(signals, cfg["weights"])
    assert subject["signals"] == {k: round(v, 4) for k, v in signals.items()}
    assert subject["liquidity"] == screener.liquidity_metrics(gulfoillub)


def test_build_subject_section_reports_insufficient_history_instead_of_a_score(
    cfg, monkeypatch
):
    from stockstalker import backtest

    required = backtest.burn_in_period(cfg) + 1
    short = pd.DataFrame(
        {
            "open": [1.0] * 10,
            "high": [1.0] * 10,
            "low": [1.0] * 10,
            "close": list(range(1, 11)),
            "volume": [100] * 10,
        },
        index=pd.date_range("2026-10-01", periods=10, freq="D"),
    )
    monkeypatch.setattr(run, "load", lambda *a, **k: short)
    subject = run.build_subject_section("NEWLISTING", "fixtures", cfg)
    assert subject["score"] is None
    assert subject["signals"] is None
    assert subject["history_reason"] == f"not enough history for a score yet (10 bars, need {required})"
    assert subject["close"] == 10.0


def test_build_peer_table_covers_subject_and_every_peer(cfg):
    rows = run.build_peer_table(["GULFOILLUB", *run.DEFAULT_PEERS], "fixtures")
    assert [r["ticker"] for r in rows] == ["GULFOILLUB", "CASTROLIND", "SOTL", "GANDHAR"]
    for r in rows:
        assert r["return_1y"] is not None
        assert r["volatility_1y"] is not None
        assert r["adv_20d"] >= 0


def test_build_peer_table_records_fetch_errors_without_raising():
    errors = []
    rows = run.build_peer_table(["GULFOILLUB", "NOPE"], "fixtures", errors)
    assert [r["ticker"] for r in rows] == ["GULFOILLUB"]
    assert len(errors) == 1
    assert "NOPE" in errors[0]


def test_render_subject_table_includes_ticker_and_score(cfg):
    subject = run.build_subject_section("GULFOILLUB", "fixtures", cfg)
    text = render(run.render_subject_table(subject))
    assert "GULFOILLUB" in text
    assert f"{subject['score']:.4f}" in text


def test_render_subject_table_shows_history_reason_instead_of_crashing():
    subject = {
        "ticker": "NEWLISTING",
        "as_of": "2026-10-23",
        "close": 10.0,
        "score": None,
        "signals": None,
        "history_reason": "not enough history for a score yet (10 bars, need 51)",
        "liquidity": {"adv_20d": 0.0, "turnover_20d": 0.0},
    }
    text = render(run.render_subject_table(subject))
    assert "NEWLISTING" in text
    assert "not enough history for a score yet (10 bars, need 51)" in text


def test_write_tearsheet_shows_history_reason_instead_of_crashing(tmp_path):
    subject = {
        "ticker": "NEWLISTING",
        "as_of": "2026-10-23",
        "close": 10.0,
        "score": None,
        "signals": None,
        "history_reason": "not enough history for a score yet (10 bars, need 51)",
        "liquidity": {"adv_20d": 0.0, "turnover_20d": 0.0},
    }
    path = tmp_path / "tearsheet.md"
    run.write_tearsheet(subject, [], "2026-10-23", path)
    text = path.read_text()
    assert "not enough history for a score yet (10 bars, need 51)" in text


def test_render_peer_table_shows_na_for_missing_stats():
    rows = [{"ticker": "GANDHAR", "return_1y": None, "volatility_1y": None, "adv_20d": 123.0}]
    text = render(run.render_peer_table(rows))
    assert "n/a" in text
    assert "GANDHAR" in text


def test_write_tearsheet_contains_subject_and_peers(cfg, tmp_path):
    subject = run.build_subject_section("GULFOILLUB", "fixtures", cfg)
    peer_rows = run.build_peer_table(["GULFOILLUB", *run.DEFAULT_PEERS], "fixtures")
    path = tmp_path / "tearsheet.md"
    run.write_tearsheet(subject, peer_rows, "2026-10-12", path)
    text = path.read_text()
    assert "GULFOILLUB" in text
    for ticker in ["CASTROLIND", "SOTL", "GANDHAR"]:
        assert ticker in text
    assert "Contract sections" in text


def test_write_tearsheet_carries_the_disclaimer(tmp_path):
    subject = {
        "ticker": "NEWLISTING",
        "as_of": "2026-10-23",
        "close": 10.0,
        "score": None,
        "signals": None,
        "history_reason": "not enough history for a score yet (10 bars, need 51)",
        "liquidity": {"adv_20d": 0.0, "turnover_20d": 0.0},
    }
    path = tmp_path / "tearsheet.md"
    run.write_tearsheet(subject, [], "2026-10-23", path)
    text = path.read_text()
    assert (
        "Educational research on historical data. Not investment advice. "
        "Not a SEBI-registered research analyst." in text
    )


def test_cli_end_to_end_writes_tearsheet(tmp_path, capsys):
    rc = run.main(
        [
            "--ticker",
            "GULFOILLUB",
            "--offline",
            "--date",
            "2026-10-12",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out_path = tmp_path / "tearsheet_GULFOILLUB_2026-10-12.md"
    assert out_path.exists()
    text = out_path.read_text()
    assert "GULFOILLUB" in text
    captured = capsys.readouterr()
    assert "tear sheet:" in captured.out


def test_cli_rejects_live_and_offline_together():
    with pytest.raises(SystemExit):
        run.main(["--ticker", "GULFOILLUB", "--live", "--offline"])


@pytest.mark.parametrize("flag", ["--refresh", "--no-cache"])
def test_cli_refresh_flag_threads_use_cache_false_through(tmp_path, monkeypatch, flag):
    """D11: ``--refresh``/``--no-cache`` must reach every ``load()``/
    ``local_csv_path()`` call site through ``use_cache``, not just be parsed
    and ignored.
    """
    seen_use_cache = {}

    def fake_build_subject_section(ticker, provider_name, cfg, use_cache=True):
        seen_use_cache["subject"] = use_cache
        return real_build_subject_section(ticker, provider_name, cfg, use_cache=use_cache)

    def fake_build_peer_table(tickers, provider_name, errors=None, use_cache=True):
        seen_use_cache["peers"] = use_cache
        return real_build_peer_table(tickers, provider_name, errors, use_cache=use_cache)

    real_build_subject_section = run.build_subject_section
    real_build_peer_table = run.build_peer_table
    monkeypatch.setattr(run, "build_subject_section", fake_build_subject_section)
    monkeypatch.setattr(run, "build_peer_table", fake_build_peer_table)

    rc = run.main(["--ticker", "GULFOILLUB", "--offline", flag, "--output-dir", str(tmp_path)])

    assert rc == 0
    assert seen_use_cache == {"subject": False, "peers": False}


def test_cli_without_refresh_defaults_to_use_cache_true(tmp_path, monkeypatch):
    seen_use_cache = {}
    real_build_subject_section = run.build_subject_section

    def fake_build_subject_section(ticker, provider_name, cfg, use_cache=True):
        seen_use_cache["subject"] = use_cache
        return real_build_subject_section(ticker, provider_name, cfg, use_cache=use_cache)

    monkeypatch.setattr(run, "build_subject_section", fake_build_subject_section)

    rc = run.main(["--ticker", "GULFOILLUB", "--offline", "--output-dir", str(tmp_path)])

    assert rc == 0
    assert seen_use_cache == {"subject": True}


def test_cli_reports_missing_ticker_without_traceback(capsys):
    rc = run.main(["--ticker", "NOPE", "--offline"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "NOPE" in captured.out


# -- Day 2: contract sections ------------------------------------------------


def test_contract_namespaces_excludes_sizing_on_purpose():
    namespaces = [n for n, _, _ in run.CONTRACT_NAMESPACES]
    assert namespaces == ["valuation", "fundamentals", "risk", "factor", "vol", "sentiment"]
    assert "sizing" not in namespaces


def test_build_contract_section_reads_real_fixture_for_subject():
    section = run.build_contract_section(
        "valuation", run.gate_valuation, "reverse-dcf-engine", "GULFOILLUB", FIXTURES
    )
    assert section["available"] is True
    assert section["source"] == "reverse-dcf-engine"
    # reverse-dcf-engine's V2 fix (CRITIQUES.md V1) replaced the fixed
    # reinvestment rate that produced the old -0.49% figure; at GULFOILLUB's
    # own committed market price the growth-consistent model finds no
    # implied growth at all, reported as None, not a crash -- see that
    # repo's own tests/test_solve.py for the full finding.
    assert section["data"]["implied_cagr"] is None
    assert section["data"]["price_reachable"] is False


def test_build_contract_section_reports_missing_fixture_with_reason():
    # CROMPTON is a real NSE F&O underlying (confirmed against the
    # committed fo_mktlots.csv) with no implied-vol-surface fixture
    # committed yet -- the generic "not built yet" path, not D2's
    # F&O-underlying check.
    section = run.build_contract_section(
        "vol", run.gate_vol, "implied-vol-surface", "CROMPTON", FIXTURES
    )
    assert section["available"] is False
    assert "CROMPTON" in section["reason"]
    assert "not found" in section["reason"]


def test_build_contract_section_vol_for_subject_is_no_listed_options_not_unverified():
    # Day 5 (D2): fo_mktlots.csv, NSE's own lot-size snapshot, settles
    # GULFOILLUB's F&O-underlying status without touching the blocked
    # option-chain endpoint at all -- GULFOILLUB's SYMBOL is absent from
    # the committed snapshot, so this is a definite "no listed options",
    # not the old "unverified" hedge.
    section = run.build_contract_section(
        "vol", run.gate_vol, "implied-vol-surface", "GULFOILLUB", FIXTURES
    )
    assert section["available"] is False
    assert "no listed options" in section["reason"]
    assert "not an NSE F&O underlying" in section["reason"]
    assert "unverified" not in section["reason"]


def test_build_contract_section_vol_no_listed_options_applies_to_any_non_fo_ticker():
    # Not just GULFOILLUB -- CASTROLIND (a lubricant peer, also absent
    # from fo_mktlots.csv) gets the same honest message, not a generic
    # "fixture not found" that implies one might simply be missing.
    section = run.build_contract_section(
        "vol", run.gate_vol, "implied-vol-surface", "CASTROLIND", FIXTURES
    )
    assert section["available"] is False
    assert "no listed options" in section["reason"]


def test_load_fo_underlyings_contains_known_fo_names_not_the_lubricant_peers():
    underlyings = run.load_fo_underlyings()
    assert "RELIANCE" in underlyings
    assert "CROMPTON" in underlyings
    assert "GULFOILLUB" not in underlyings
    assert "CASTROLIND" not in underlyings


def test_fo_mktlots_list_date_reads_the_committed_metadata():
    # D42: fetch-fo-mktlots.yml refreshes the list monthly, so read the date from the
    # committed metadata rather than pinning one month's value.
    meta = json.loads(run.FO_MKTLOTS_META_PATH.read_text())
    assert run.fo_mktlots_list_date() == meta["list_last_modified"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", run.fo_mktlots_list_date())


def test_build_contract_section_reads_real_fixture_for_subject_sentiment():
    # Day 6: headline-sentiment-vs-price's GULFOILLUB contract is a real,
    # honest zero -- the ticker table has no rule for GULFOILLUB, so no
    # headline in the ~50-headline fixture corpus resolves to it. That is
    # a genuine "coverage: none" result, not a stand-in or a skipped day.
    section = run.build_contract_section(
        "sentiment", run.gate_sentiment, "headline-sentiment-vs-price", "GULFOILLUB", FIXTURES
    )
    assert section["available"] is True
    assert section["source"] == "headline-sentiment-vs-price"
    assert section["data"]["coverage"] == "none"
    assert section["data"]["score_7d"] is None
    assert section["data"]["headline_count_7d"] == 0


def test_build_contract_section_reads_real_fixture_for_subject_risk():
    # Day 3: monte-carlo-risk-lab's GULFOILLUB fixture is a genuine match,
    # not a synthetic stand-in -- same shape as valuation/fundamentals above.
    section = run.build_contract_section(
        "risk", run.gate_risk, "monte-carlo-risk-lab", "GULFOILLUB", FIXTURES
    )
    assert section["available"] is True
    assert section["source"] == "monte-carlo-risk-lab"
    assert section["data"]["horizon_days"] == 20


def test_build_contract_section_reads_real_fixture_for_subject_factor():
    # Day 5: fama-french-factor-model's GULFOILLUB fixture is a genuine
    # IIMA FF3+WML regression, not a synthetic stand-in -- same shape as
    # valuation/fundamentals/risk above.
    section = run.build_contract_section(
        "factor", run.gate_factor, "fama-french-factor-model", "GULFOILLUB", FIXTURES
    )
    assert section["available"] is True
    assert section["source"] == "fama-french-factor-model"
    assert section["data"]["loadings"]["wml"] == pytest.approx(0.011272064937160637)


def test_build_contract_section_reports_malformed_fixture_with_reason(tmp_path):
    namespace_dir = tmp_path / "risk"
    namespace_dir.mkdir()
    (namespace_dir / "GULFOILLUB.json").write_text(json.dumps({"risk": {"var_95": -0.1}}))
    section = run.build_contract_section(
        "risk", run.gate_risk, "monte-carlo-risk-lab", "GULFOILLUB", tmp_path
    )
    assert section["available"] is False
    assert "missing keys" in section["reason"]


def test_build_contract_sections_covers_every_namespace_for_subject():
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    assert [s["namespace"] for s in sections] == [
        "valuation",
        "fundamentals",
        "risk",
        "factor",
        "vol",
        "sentiment",
    ]
    available = {s["namespace"] for s in sections if s["available"]}
    # valuation and fundamentals shipped Day 2; risk shipped Day 3; factor
    # shipped Day 5; sentiment shipped Day 6 (a real zero-headline result,
    # not a stand-in). vol stays unavailable -- fo_mktlots.csv (fix-phase
    # Day 5) confirms GULFOILLUB genuinely has no listed options, not just
    # an unbuilt fixture.
    assert available == {"valuation", "fundamentals", "risk", "factor", "sentiment"}
    for section in sections:
        if not section["available"]:
            assert section["reason"]
            if section["namespace"] == "vol":
                assert "no listed options" in section["reason"]


def test_render_contract_section_available_shows_fields():
    section = run.build_contract_section(
        "fundamentals", run.gate_fundamentals, "three-statement-model", "GULFOILLUB", FIXTURES
    )
    text = render(run.render_contract_section(section))
    assert "fundamentals" in text
    assert "balance_check" in text
    assert "passed" in text


def test_render_contract_section_unavailable_is_a_one_line_reason():
    section = {"namespace": "vol", "available": False, "reason": "no fixture for GULFOILLUB"}
    rendered = run.render_contract_section(section)
    assert isinstance(rendered, str)
    assert "not available" in rendered
    assert "no fixture for GULFOILLUB" in rendered


def test_contract_sections_markdown_never_shows_sizing(cfg):
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    lines = run.contract_sections_markdown(sections, "GULFOILLUB")
    text = "\n".join(lines)
    assert "### Valuation" in text
    assert "### Fundamentals" in text
    assert "### Risk" in text
    assert "Not available" in text
    assert "left out on purpose" in text
    assert "### Sizing" not in text


def test_contract_sections_markdown_notes_the_kupiec_gap_for_gulfoillub_risk(cfg):
    # R5: the risk contract only ships the 95% VaR/CVaR; the tear sheet
    # states the known 99%/Kupiec gap right under that section rather
    # than letting the number sit unremarked.
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    lines = run.contract_sections_markdown(sections, "GULFOILLUB")
    text = "\n".join(lines)
    assert "Kupiec" in text
    assert "REJECTED at both 95%" in text


def test_contract_sections_markdown_labels_reliance_factor_as_old_method(cfg):
    # R6: RELIANCE's factor contract is still the old Ken French USD
    # regression; the tear sheet says so wherever that contract shows up,
    # not just in fama-french-factor-model's own README.
    sections = run.build_contract_sections("RELIANCE", FIXTURES)
    lines = run.contract_sections_markdown(sections, "RELIANCE")
    text = "\n".join(lines)
    assert "old method" in text
    assert "Ken French" in text


def test_contract_sections_markdown_renders_significance_as_words(cfg):
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    lines = run.contract_sections_markdown(sections, "GULFOILLUB")
    text = "\n".join(lines)
    assert "not significant" in text
    assert "| significant | True |" not in text
    assert "| significant | False |" not in text


def test_cli_end_to_end_includes_contract_sections(tmp_path):
    rc = run.main(
        [
            "--ticker",
            "GULFOILLUB",
            "--offline",
            "--date",
            "2026-10-12",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    text = (tmp_path / "tearsheet_GULFOILLUB_2026-10-12.md").read_text()
    assert "## Contract sections" in text
    assert "### Valuation" in text
    assert "balance_check" in text
    assert "Not available" in text
    assert "sizing" in text.lower()


def test_cli_end_to_end_prints_sizing_exclusion_and_risk_caveat_to_console(tmp_path, capsys):
    # R7: the sizing-exclusion reason used to live only in the tear sheet;
    # R5: the Kupiec gap note for the default subject (GULFOILLUB) should
    # reach the terminal too, not just the markdown file.
    rc = run.main(
        [
            "--ticker",
            "GULFOILLUB",
            "--offline",
            "--date",
            "2026-10-12",
            "--output-dir",
            str(tmp_path),
            "--no-charts",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "left out on purpose" in out
    assert "Kupiec" in out


# -- Day 7: rebased/drawdown/volatility charts -------------------------------


def test_write_charts_writes_three_pngs(tmp_path):
    paths = run.write_charts("GULFOILLUB", run.DEFAULT_PEERS, "fixtures", tmp_path)
    assert len(paths) == 3
    for path in paths:
        assert path.exists()
        assert path.stat().st_size > 0
    names = {p.name for p in paths}
    assert names == {
        "rebased_GULFOILLUB.png",
        "drawdown_GULFOILLUB.png",
        "volatility_GULFOILLUB.png",
    }


def test_write_charts_records_peer_fetch_errors_without_raising(tmp_path):
    errors = []
    paths = run.write_charts("GULFOILLUB", ["NOPE"], "fixtures", tmp_path, errors)
    # The rebased chart still renders with just the subject; a missing peer
    # is recorded, not fatal.
    assert len(paths) == 3
    assert len(errors) == 1
    assert "NOPE" in errors[0]


def test_write_charts_returns_nothing_when_subject_itself_fails(tmp_path):
    errors = []
    paths = run.write_charts("NOPE", run.DEFAULT_PEERS, "fixtures", tmp_path, errors)
    assert paths == []
    assert any("NOPE" in e for e in errors)


def test_write_tearsheet_lists_chart_files(cfg, tmp_path):
    subject = run.build_subject_section("GULFOILLUB", "fixtures", cfg)
    peer_rows = run.build_peer_table(["GULFOILLUB", *run.DEFAULT_PEERS], "fixtures")
    chart_paths = run.write_charts("GULFOILLUB", run.DEFAULT_PEERS, "fixtures", tmp_path)
    path = tmp_path / "tearsheet.md"
    run.write_tearsheet(subject, peer_rows, "2026-10-12", path, chart_paths=chart_paths)
    text = path.read_text()
    assert "## Charts" in text
    assert "rebased_GULFOILLUB.png" in text
    assert "drawdown_GULFOILLUB.png" in text
    assert "volatility_GULFOILLUB.png" in text


def test_cli_end_to_end_writes_charts_by_default(tmp_path, capsys):
    rc = run.main(
        [
            "--ticker",
            "GULFOILLUB",
            "--offline",
            "--date",
            "2026-10-12",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    assert (tmp_path / "rebased_GULFOILLUB.png").exists()
    assert (tmp_path / "drawdown_GULFOILLUB.png").exists()
    assert (tmp_path / "volatility_GULFOILLUB.png").exists()
    text = (tmp_path / "tearsheet_GULFOILLUB_2026-10-12.md").read_text()
    assert "## Charts" in text
    captured = capsys.readouterr()
    assert "chart:" in captured.out


def test_cli_no_charts_skips_png_output(tmp_path):
    rc = run.main(
        [
            "--ticker",
            "GULFOILLUB",
            "--offline",
            "--date",
            "2026-10-12",
            "--output-dir",
            str(tmp_path),
            "--no-charts",
        ]
    )
    assert rc == 0
    assert not (tmp_path / "rebased_GULFOILLUB.png").exists()
    text = (tmp_path / "tearsheet_GULFOILLUB_2026-10-12.md").read_text()
    assert "## Charts" not in text


# -- Day 20 (C1): any-stock tear sheet, price section ------------------------
#
# GULFOILLUB and its three lubricant peers are all the committed fixtures
# exercised so far; every test above could pass even if the front door were
# secretly hard-wired to that one sector. TATAELXSI is a real NSE F&O
# underlying (fo_mktlots.csv) with no connection to GULFOILLUB or its peer
# list, fetched live via yfinance and committed as a fixture precisely to
# prove the price section (signals, score, liquidity, 1y return/volatility)
# is a real "any ticker" computation, not a GULFOILLUB-shaped special case.


def test_build_subject_section_works_for_a_ticker_outside_the_lubricant_sector(cfg):
    subject = run.build_subject_section("TATAELXSI", "fixtures", cfg)
    assert subject["ticker"] == "TATAELXSI"
    assert subject["close"] > 0
    assert set(subject["signals"]) == {"trend", "momentum", "volume"}
    assert subject["liquidity"]["adv_20d"] > 0


def test_cli_builds_a_full_tearsheet_for_a_non_lubricant_ticker(tmp_path, capsys):
    # No --peers override: the default lubricant peer list is irrelevant to
    # a tech stock, and the CLI must still run end to end without it.
    # --risk-lab-root points at a directory that doesn't exist, so this
    # stays deterministic regardless of whether a real monte-carlo-risk-lab
    # sibling checkout happens to sit next to this repo in the environment
    # running the test (Day 21/C1 made risk the one namespace that no
    # longer needs a committed fixture when that sibling is present and
    # reachable -- see test_cli_end_to_end_generates_a_live_risk_section_
    # for_an_uncommitted_ticker below for that path).
    rc = run.main(
        [
            "--ticker",
            "TATAELXSI",
            "--peers",
            "",
            "--offline",
            "--date",
            "2026-10-17",
            "--output-dir",
            str(tmp_path),
            "--no-charts",
            "--risk-lab-root",
            str(tmp_path / "no-such-sibling-checkout"),
        ]
    )
    assert rc == 0
    text = (tmp_path / "tearsheet_TATAELXSI_2026-10-17.md").read_text()
    assert "TATAELXSI" in text
    # Every contract namespace has no fixture for this ticker and no usable
    # fallback either, so each one must render its own one-line reason --
    # never a placeholder or a blank section, and never another ticker's
    # contract.
    for namespace in [n for n, _, _ in run.CONTRACT_NAMESPACES]:
        assert f"### {namespace.capitalize()}" in text
    assert "Not available" in text
    captured = capsys.readouterr()
    assert "tear sheet:" in captured.out


def test_vol_reason_distinguishes_no_listed_options_from_no_contract_yet():
    # CASTROLIND is absent from fo_mktlots.csv -- a definite "not F&O at
    # all". TATAELXSI is present in it (a real F&O underlying) but has no
    # implied-vol-surface fixture committed -- the generic "not built yet"
    # reason, not the F&O-absence one. Conflating the two would misreport
    # a real F&O stock as having no listed options.
    castrolind = run.build_contract_section(
        "vol", run.gate_vol, "implied-vol-surface", "CASTROLIND", FIXTURES
    )
    tataelxsi = run.build_contract_section(
        "vol", run.gate_vol, "implied-vol-surface", "TATAELXSI", FIXTURES
    )
    assert "no listed options" in castrolind["reason"]
    assert "no listed options" not in tataelxsi["reason"]
    assert "not found" in tataelxsi["reason"]
    assert "TATAELXSI" in run.load_fo_underlyings()


def test_build_peer_table_dedupes_a_subject_that_is_also_a_default_peer():
    # CASTROLIND is both a valid --ticker and one of GULFOILLUB's own
    # DEFAULT_PEERS. Running the CLI on CASTROLIND with the untouched
    # default --peers must not print the same ticker's row twice.
    rows = run.build_peer_table(["CASTROLIND", *run.DEFAULT_PEERS], "fixtures")
    assert [r["ticker"] for r in rows] == ["CASTROLIND", "SOTL", "GANDHAR"]


def test_build_peer_table_dedup_is_case_insensitive():
    rows = run.build_peer_table(["castrolind", "CASTROLIND", "SOTL"], "fixtures")
    assert [r["ticker"] for r in rows] == ["CASTROLIND", "SOTL"]


# -- Day 21 (C1): any-stock tear sheet, risk section -------------------------
#
# monte-carlo-risk-lab's GULFOILLUB/RELIANCE risk fixtures are hand-verified
# and committed; this day adds a live fallback, generated on the fly as a
# subprocess into the sibling checkout, for a ticker with no committed
# fixture. ``run.generate_risk_contract`` is monkeypatched throughout so
# these tests exercise this repo's own wiring deterministically, without
# ever invoking uv or a real sibling checkout -- that real, end-to-end path
# is exercised separately in test_live_risk_contract_smoke.py, which skips
# cleanly when no sibling checkout is actually present (same pattern as
# test_live_provider_smoke.py for yfinance).

LIVE_RISK_CONTRACT = {
    "risk": {"var_95": -0.1, "cvar_95": -0.15, "max_dd_sim": -0.05, "horizon_days": 20}
}


def _fake_generate_risk_contract(prices_csv, out_path, risk_lab_root):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(LIVE_RISK_CONTRACT))
    return None


def test_build_live_risk_section_returns_none_when_price_data_is_missing(tmp_path):
    assert run.build_live_risk_section("NOTATICKER", "fixtures", tmp_path) is None


def test_build_live_risk_section_accepts_a_plain_string_root(tmp_path):
    # argparse hands --risk-lab-root to build_contract_sections as a plain
    # str, not a Path (the bug this guards against: generate_risk_contract
    # called .is_dir() on that str directly and crashed with AttributeError
    # before even reaching the "sibling missing" reason it was meant to
    # report).
    missing_root_as_str = str(tmp_path / "no-such-sibling-checkout")
    section = run.build_live_risk_section("TATAELXSI", "fixtures", tmp_path, risk_lab_root=missing_root_as_str)
    assert section is None


def test_build_live_risk_section_returns_none_on_generation_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_risk_contract", lambda *a, **k: "sibling missing")
    section = run.build_live_risk_section("TATAELXSI", "fixtures", tmp_path, risk_lab_root=tmp_path)
    assert section is None


def test_build_live_risk_section_builds_an_available_section(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_risk_contract", _fake_generate_risk_contract)
    section = run.build_live_risk_section("TATAELXSI", "fixtures", tmp_path, risk_lab_root=tmp_path)
    assert section == {
        "namespace": "risk",
        "available": True,
        "source": "monte-carlo-risk-lab (live)",
        "data": LIVE_RISK_CONTRACT["risk"],
    }
    assert (tmp_path / "contracts" / "TATAELXSI" / "risk.json").exists()


def test_build_contract_sections_never_regenerates_a_committed_risk_fixture(monkeypatch):
    # The hand-verified GULFOILLUB/RELIANCE risk fixtures must never be
    # regenerated live -- live generation must not even be attempted when
    # the committed fixture already answers the namespace.
    def fail(*a, **k):
        raise AssertionError("must not attempt live generation when a committed fixture exists")

    monkeypatch.setattr(run, "generate_risk_contract", fail)
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    risk_section = next(s for s in sections if s["namespace"] == "risk")
    assert risk_section["available"] is True
    assert risk_section["source"] == "monte-carlo-risk-lab"


def test_build_contract_sections_falls_back_to_live_generation_for_an_uncommitted_ticker(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(run, "generate_risk_contract", _fake_generate_risk_contract)
    sections = run.build_contract_sections(
        "TATAELXSI", FIXTURES, provider_name="fixtures", output_dir=tmp_path, risk_lab_root=tmp_path
    )
    risk_section = next(s for s in sections if s["namespace"] == "risk")
    assert risk_section["available"] is True
    assert risk_section["source"] == "monte-carlo-risk-lab (live)"
    assert risk_section["data"] == LIVE_RISK_CONTRACT["risk"]


def test_build_contract_sections_keeps_not_available_when_live_generation_also_fails(monkeypatch):
    monkeypatch.setattr(run, "generate_risk_contract", lambda *a, **k: "sibling missing")
    sections = run.build_contract_sections("TATAELXSI", FIXTURES)
    risk_section = next(s for s in sections if s["namespace"] == "risk")
    assert risk_section["available"] is False
    assert "not found" in risk_section["reason"]


def test_cli_end_to_end_generates_a_live_risk_section_for_an_uncommitted_ticker(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_risk_contract", _fake_generate_risk_contract)
    rc = run.main(
        [
            "--ticker",
            "TATAELXSI",
            "--peers",
            "",
            "--offline",
            "--date",
            "2026-10-17",
            "--output-dir",
            str(tmp_path),
            "--no-charts",
            "--risk-lab-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    text = (tmp_path / "tearsheet_TATAELXSI_2026-10-17.md").read_text()
    assert "### Risk" in text
    assert "monte-carlo-risk-lab (live)" in text
    assert "var_95" in text
    assert (tmp_path / "contracts" / "TATAELXSI" / "risk.json").exists()


# -- Day 22 (C1): any-stock tear sheet, factor section ------------------------
#
# Same pattern as Day 21's risk section above: fama-french-factor-model's
# GULFOILLUB/RELIANCE factor fixtures are hand-verified and committed; this
# day adds a live fallback, generated on the fly as a subprocess into the
# sibling checkout (via the Day 22 `factors.stock` CLI), for a ticker with
# no committed fixture. ``run.generate_factor_contract`` is monkeypatched
# throughout; the real, end-to-end path is exercised separately in
# test_live_factor_contract_smoke.py.

LIVE_FACTOR_CONTRACT = {
    "factor": {
        "alpha_annual": -0.17698,
        "alpha_t": -0.98,
        "significant": False,
        "loadings": {"mkt": 0.522, "smb": 1.007, "hml": 1.326, "wml": -0.369},
    }
}


def _fake_generate_factor_contract(ticker, prices_csv, out_path, factor_model_root):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(LIVE_FACTOR_CONTRACT))
    return None


def test_build_live_factor_section_returns_none_when_price_data_is_missing(tmp_path):
    assert run.build_live_factor_section("NOTATICKER", "fixtures", tmp_path) is None


def test_build_live_factor_section_accepts_a_plain_string_root(tmp_path):
    missing_root_as_str = str(tmp_path / "no-such-sibling-checkout")
    section = run.build_live_factor_section("TATAELXSI", "fixtures", tmp_path, factor_model_root=missing_root_as_str)
    assert section is None


def test_build_live_factor_section_returns_none_on_generation_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_factor_contract", lambda *a, **k: "sibling missing")
    section = run.build_live_factor_section("TATAELXSI", "fixtures", tmp_path, factor_model_root=tmp_path)
    assert section is None


def test_build_live_factor_section_builds_an_available_section(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_factor_contract", _fake_generate_factor_contract)
    section = run.build_live_factor_section("TATAELXSI", "fixtures", tmp_path, factor_model_root=tmp_path)
    assert section == {
        "namespace": "factor",
        "available": True,
        "source": "fama-french-factor-model (live)",
        "data": LIVE_FACTOR_CONTRACT["factor"],
    }
    assert (tmp_path / "contracts" / "TATAELXSI" / "factor.json").exists()


def test_build_contract_sections_never_regenerates_a_committed_factor_fixture(monkeypatch):
    # The hand-verified GULFOILLUB/RELIANCE factor fixtures must never be
    # regenerated live -- live generation must not even be attempted when
    # the committed fixture already answers the namespace.
    def fail(*a, **k):
        raise AssertionError("must not attempt live generation when a committed fixture exists")

    monkeypatch.setattr(run, "generate_factor_contract", fail)
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    factor_section = next(s for s in sections if s["namespace"] == "factor")
    assert factor_section["available"] is True
    assert factor_section["source"] == "fama-french-factor-model"


def test_build_contract_sections_falls_back_to_live_factor_generation_for_an_uncommitted_ticker(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(run, "generate_factor_contract", _fake_generate_factor_contract)
    sections = run.build_contract_sections(
        "TATAELXSI", FIXTURES, provider_name="fixtures", output_dir=tmp_path, factor_model_root=tmp_path
    )
    factor_section = next(s for s in sections if s["namespace"] == "factor")
    assert factor_section["available"] is True
    assert factor_section["source"] == "fama-french-factor-model (live)"
    assert factor_section["data"] == LIVE_FACTOR_CONTRACT["factor"]


def test_build_contract_sections_keeps_not_available_when_live_factor_generation_also_fails(monkeypatch):
    monkeypatch.setattr(run, "generate_factor_contract", lambda *a, **k: "sibling missing")
    sections = run.build_contract_sections("TATAELXSI", FIXTURES)
    factor_section = next(s for s in sections if s["namespace"] == "factor")
    assert factor_section["available"] is False
    assert "not found" in factor_section["reason"]


def test_cli_end_to_end_generates_a_live_factor_section_for_an_uncommitted_ticker(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_factor_contract", _fake_generate_factor_contract)
    rc = run.main(
        [
            "--ticker",
            "TATAELXSI",
            "--peers",
            "",
            "--offline",
            "--date",
            "2026-10-17",
            "--output-dir",
            str(tmp_path),
            "--no-charts",
            "--factor-model-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    text = (tmp_path / "tearsheet_TATAELXSI_2026-10-17.md").read_text()
    assert "### Factor" in text
    assert "fama-french-factor-model (live)" in text
    assert "alpha_annual" in text
    assert (tmp_path / "contracts" / "TATAELXSI" / "factor.json").exists()


# -- Day 23 (C1): any-stock tear sheet, valuation section (reverse DCF lite) --
#
# Same pattern as Day 21/22's risk/factor sections above: reverse-dcf-engine's
# GULFOILLUB valuation fixture is hand-verified and committed; this day adds
# a live fallback, generated on the fly as a subprocess into the sibling
# checkout (via the Day 23 `reverse_dcf.solve --live-financials` CLI), for a
# ticker with no committed fixture. ``run.generate_valuation_contract`` is
# monkeypatched throughout; the real, end-to-end path (which makes its own
# live yfinance call from inside the subprocess, not just a prices CSV) is
# exercised separately in test_live_valuation_contract_smoke.py.

LIVE_VALUATION_CONTRACT = {
    "valuation": {
        "implied_cagr": None,
        "implied_ebit_margin": 0.2239,
        "implied_reinvestment": None,
        "breakeven_growth": None,
        "price_reachable": False,
        "financials_source": "yfinance, consolidated, 4-5 years",
    }
}


def _fake_generate_valuation_contract(ticker, prices_csv, out_path, reverse_dcf_root):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(LIVE_VALUATION_CONTRACT))
    return None


def test_build_live_valuation_section_returns_none_when_price_data_is_missing(tmp_path):
    assert run.build_live_valuation_section("NOTATICKER", "fixtures", tmp_path) is None


def test_build_live_valuation_section_accepts_a_plain_string_root(tmp_path):
    missing_root_as_str = str(tmp_path / "no-such-sibling-checkout")
    section = run.build_live_valuation_section(
        "TATAELXSI", "fixtures", tmp_path, reverse_dcf_root=missing_root_as_str
    )
    assert section is None


def test_build_live_valuation_section_returns_none_on_generation_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_valuation_contract", lambda *a, **k: "sibling missing")
    section = run.build_live_valuation_section("TATAELXSI", "fixtures", tmp_path, reverse_dcf_root=tmp_path)
    assert section is None


def test_build_live_valuation_section_builds_an_available_section(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_valuation_contract", _fake_generate_valuation_contract)
    section = run.build_live_valuation_section("TATAELXSI", "fixtures", tmp_path, reverse_dcf_root=tmp_path)
    assert section == {
        "namespace": "valuation",
        "available": True,
        "source": "reverse-dcf-engine (live)",
        "data": LIVE_VALUATION_CONTRACT["valuation"],
    }
    assert (tmp_path / "contracts" / "TATAELXSI" / "valuation.json").exists()


def test_build_contract_sections_never_regenerates_a_committed_valuation_fixture(monkeypatch):
    # The hand-verified GULFOILLUB valuation fixture must never be
    # regenerated live -- live generation must not even be attempted when
    # the committed fixture already answers the namespace.
    def fail(*a, **k):
        raise AssertionError("must not attempt live generation when a committed fixture exists")

    monkeypatch.setattr(run, "generate_valuation_contract", fail)
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    valuation_section = next(s for s in sections if s["namespace"] == "valuation")
    assert valuation_section["available"] is True
    assert valuation_section["source"] == "reverse-dcf-engine"


def test_build_contract_sections_falls_back_to_live_valuation_generation_for_an_uncommitted_ticker(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(run, "generate_valuation_contract", _fake_generate_valuation_contract)
    sections = run.build_contract_sections(
        "TATAELXSI", FIXTURES, provider_name="fixtures", output_dir=tmp_path, reverse_dcf_root=tmp_path
    )
    valuation_section = next(s for s in sections if s["namespace"] == "valuation")
    assert valuation_section["available"] is True
    assert valuation_section["source"] == "reverse-dcf-engine (live)"
    assert valuation_section["data"] == LIVE_VALUATION_CONTRACT["valuation"]


def test_build_contract_sections_keeps_not_available_when_live_valuation_generation_also_fails(monkeypatch):
    monkeypatch.setattr(run, "generate_valuation_contract", lambda *a, **k: "sibling missing")
    sections = run.build_contract_sections("TATAELXSI", FIXTURES)
    valuation_section = next(s for s in sections if s["namespace"] == "valuation")
    assert valuation_section["available"] is False
    assert "not found" in valuation_section["reason"]


def test_cli_end_to_end_generates_a_live_valuation_section_for_an_uncommitted_ticker(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_valuation_contract", _fake_generate_valuation_contract)
    rc = run.main(
        [
            "--ticker",
            "TATAELXSI",
            "--peers",
            "",
            "--offline",
            "--date",
            "2026-10-17",
            "--output-dir",
            str(tmp_path),
            "--no-charts",
            "--reverse-dcf-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    text = (tmp_path / "tearsheet_TATAELXSI_2026-10-17.md").read_text()
    assert "### Valuation" in text
    assert "reverse-dcf-engine (live)" in text
    assert "financials source: yfinance, consolidated, 4-5 years" in text
    assert (tmp_path / "contracts" / "TATAELXSI" / "valuation.json").exists()


# -- Day 24 (C1): any-stock tear sheet, options and sentiment --
#
# vol: unlike risk/factor/valuation, this live path only ever solves a raw
# NSE chain capture already committed in the sibling checkout (P12's
# home-connection job) -- it never attempts a fresh fetch, so a ticker with
# no raw capture gets a distinct "no captured chain" reason, not the
# generic "fixture not found" every other namespace falls back to.
# sentiment: reads the sibling's own growing corpus; a zero-match ticker is
# a real, available "coverage: none" result, not "not available".
# ``run.generate_vol_contract``/``run.generate_sentiment_contract`` are
# monkeypatched throughout; the real, end-to-end paths are exercised
# separately in test_live_vol_contract_smoke.py and
# test_live_sentiment_contract_smoke.py.

LIVE_VOL_CONTRACT = {
    "vol": {"atm_iv_30d": 0.2485, "skew_25d": -0.0046, "term_slope": -0.0136, "iv_rank_1y": None}
}


def _fake_generate_vol_contract(ticker, out_path, iv_surface_root):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(LIVE_VOL_CONTRACT))
    return None


def test_vol_no_capture_reason_names_the_ticker_and_the_sibling():
    reason = run.vol_no_capture_reason("TATAELXSI", Path("/x/implied-vol-surface"))
    assert "no captured chain" in reason
    assert "TATAELXSI" in reason
    assert "implied-vol-surface" in reason


def test_build_live_vol_section_returns_none_on_generation_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_vol_contract", lambda *a, **k: "no captured chain: ...")
    section = run.build_live_vol_section("TATAELXSI", tmp_path, iv_surface_root=tmp_path)
    assert section is None


def test_build_live_vol_section_accepts_a_plain_string_root(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_vol_contract", lambda *a, **k: "no captured chain: ...")
    missing_root_as_str = str(tmp_path / "no-such-sibling-checkout")
    section = run.build_live_vol_section("TATAELXSI", tmp_path, iv_surface_root=missing_root_as_str)
    assert section is None


def test_build_live_vol_section_builds_an_available_section(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_vol_contract", _fake_generate_vol_contract)
    section = run.build_live_vol_section("RELIANCE", tmp_path, iv_surface_root=tmp_path)
    assert section == {
        "namespace": "vol",
        "available": True,
        "source": "implied-vol-surface (live)",
        "data": LIVE_VOL_CONTRACT["vol"],
    }
    assert (tmp_path / "contracts" / "RELIANCE" / "vol.json").exists()


def test_build_contract_sections_never_regenerates_a_committed_vol_fixture(monkeypatch):
    # RELIANCE's hand-verified vol fixture must never be regenerated live.
    def fail(*a, **k):
        raise AssertionError("must not attempt live generation when a committed fixture exists")

    monkeypatch.setattr(run, "generate_vol_contract", fail)
    sections = run.build_contract_sections("RELIANCE", FIXTURES)
    vol_section = next(s for s in sections if s["namespace"] == "vol")
    assert vol_section["available"] is True
    assert vol_section["source"] == "implied-vol-surface"


def test_build_contract_sections_never_attempts_live_vol_for_a_non_fo_ticker(monkeypatch):
    # GULFOILLUB is confirmed absent from fo_mktlots.csv (D2) -- the
    # "no listed options" reason is a checked fact, never a reason to try
    # to solve a chain that can't exist.
    def fail(*a, **k):
        raise AssertionError("must not attempt live generation for a non-F&O ticker")

    monkeypatch.setattr(run, "generate_vol_contract", fail)
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    vol_section = next(s for s in sections if s["namespace"] == "vol")
    assert vol_section["available"] is False
    assert "no listed options" in vol_section["reason"]


def test_build_contract_sections_falls_back_to_live_vol_generation_for_an_fo_ticker(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_vol_contract", _fake_generate_vol_contract)
    # TATAELXSI is a real F&O underlying (fo_mktlots.csv) with no committed
    # fixtures/vol/TATAELXSI.json.
    sections = run.build_contract_sections(
        "TATAELXSI", FIXTURES, output_dir=tmp_path, iv_surface_root=tmp_path
    )
    vol_section = next(s for s in sections if s["namespace"] == "vol")
    assert vol_section["available"] is True
    assert vol_section["source"] == "implied-vol-surface (live)"
    assert vol_section["data"] == LIVE_VOL_CONTRACT["vol"]


def test_build_contract_sections_reports_no_captured_chain_when_live_vol_generation_fails(monkeypatch):
    monkeypatch.setattr(run, "generate_vol_contract", lambda *a, **k: "no captured chain: ...")
    sections = run.build_contract_sections("TATAELXSI", FIXTURES)
    vol_section = next(s for s in sections if s["namespace"] == "vol")
    assert vol_section["available"] is False
    assert "no captured chain" in vol_section["reason"]
    assert "TATAELXSI" in vol_section["reason"]
    # Never the old generic "fixture not found" wording for an F&O ticker --
    # that phrasing implied a fixture might simply be missing, when the real
    # reason is that nobody has captured this ticker's chain at all.
    assert "not found" not in vol_section["reason"]


def test_cli_end_to_end_generates_a_live_vol_section_for_an_fo_ticker(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_vol_contract", _fake_generate_vol_contract)
    rc = run.main(
        [
            "--ticker", "TATAELXSI",
            "--peers", "",
            "--offline",
            "--date", "2026-10-17",
            "--output-dir", str(tmp_path),
            "--no-charts",
            "--iv-surface-root", str(tmp_path),
        ]
    )
    assert rc == 0
    text = (tmp_path / "tearsheet_TATAELXSI_2026-10-17.md").read_text()
    assert "### Vol" in text
    assert "implied-vol-surface (live)" in text
    assert (tmp_path / "contracts" / "TATAELXSI" / "vol.json").exists()


LIVE_SENTIMENT_CONTRACT = {
    "sentiment": {"score_7d": None, "headline_count_7d": 0, "model": "vader", "coverage": "none"}
}


def _fake_generate_sentiment_contract(ticker, out_path, sentiment_root):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(LIVE_SENTIMENT_CONTRACT))
    return None


def test_build_live_sentiment_section_returns_none_on_generation_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_sentiment_contract", lambda *a, **k: "sibling missing")
    section = run.build_live_sentiment_section("TATAELXSI", tmp_path, sentiment_root=tmp_path)
    assert section is None


def test_build_live_sentiment_section_accepts_a_plain_string_root(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_sentiment_contract", lambda *a, **k: "sibling missing")
    missing_root_as_str = str(tmp_path / "no-such-sibling-checkout")
    section = run.build_live_sentiment_section("TATAELXSI", tmp_path, sentiment_root=missing_root_as_str)
    assert section is None


def test_build_live_sentiment_section_builds_an_available_section_with_honest_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_sentiment_contract", _fake_generate_sentiment_contract)
    section = run.build_live_sentiment_section("TATAELXSI", tmp_path, sentiment_root=tmp_path)
    assert section == {
        "namespace": "sentiment",
        "available": True,
        "source": "headline-sentiment-vs-price (live)",
        "data": LIVE_SENTIMENT_CONTRACT["sentiment"],
    }
    assert (tmp_path / "contracts" / "TATAELXSI" / "sentiment.json").exists()


def test_build_contract_sections_never_regenerates_a_committed_sentiment_fixture(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("must not attempt live generation when a committed fixture exists")

    monkeypatch.setattr(run, "generate_sentiment_contract", fail)
    sections = run.build_contract_sections("GULFOILLUB", FIXTURES)
    sentiment_section = next(s for s in sections if s["namespace"] == "sentiment")
    assert sentiment_section["available"] is True
    assert sentiment_section["source"] == "headline-sentiment-vs-price"


def test_build_contract_sections_falls_back_to_live_sentiment_generation_for_an_uncommitted_ticker(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(run, "generate_sentiment_contract", _fake_generate_sentiment_contract)
    sections = run.build_contract_sections(
        "TATAELXSI", FIXTURES, output_dir=tmp_path, sentiment_root=tmp_path
    )
    sentiment_section = next(s for s in sections if s["namespace"] == "sentiment")
    assert sentiment_section["available"] is True
    assert sentiment_section["source"] == "headline-sentiment-vs-price (live)"
    assert sentiment_section["data"] == LIVE_SENTIMENT_CONTRACT["sentiment"]


def test_build_contract_sections_keeps_not_available_when_live_sentiment_generation_also_fails(monkeypatch):
    monkeypatch.setattr(run, "generate_sentiment_contract", lambda *a, **k: "sibling missing")
    sections = run.build_contract_sections("TATAELXSI", FIXTURES)
    sentiment_section = next(s for s in sections if s["namespace"] == "sentiment")
    assert sentiment_section["available"] is False
    assert "not found" in sentiment_section["reason"]


def test_cli_end_to_end_generates_a_live_sentiment_section_for_an_uncommitted_ticker(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "generate_sentiment_contract", _fake_generate_sentiment_contract)
    rc = run.main(
        [
            "--ticker", "TATAELXSI",
            "--peers", "",
            "--offline",
            "--date", "2026-10-17",
            "--output-dir", str(tmp_path),
            "--no-charts",
            "--sentiment-root", str(tmp_path),
        ]
    )
    assert rc == 0
    text = (tmp_path / "tearsheet_TATAELXSI_2026-10-17.md").read_text()
    assert "### Sentiment" in text
    assert "headline-sentiment-vs-price (live)" in text
    assert "coverage" in text
    assert (tmp_path / "contracts" / "TATAELXSI" / "sentiment.json").exists()


# -- Day 24 (C1): fundamentals has no live-generation path at all --


def test_contract_section_note_names_fundamentals_scope_unconditionally():
    available_section = run.build_contract_section(
        "fundamentals", run.gate_fundamentals, "three-statement-model", "GULFOILLUB", FIXTURES
    )
    assert available_section["available"] is True
    note = run.contract_section_note(available_section, "GULFOILLUB")
    assert note.endswith(run.FUNDAMENTALS_SCOPE_NOTE)
    assert "GULFOILLUB" in note
    assert "built by hand" in note

    unavailable_section = run.build_contract_section(
        "fundamentals", run.gate_fundamentals, "three-statement-model", "TATAELXSI", FIXTURES
    )
    assert unavailable_section["available"] is False
    assert run.contract_section_note(unavailable_section, "TATAELXSI") == run.FUNDAMENTALS_SCOPE_NOTE


def test_fundamentals_note_says_the_figures_are_a_dated_forecast():
    """D48: fy3_* is the third forecast year, not a reported one; say which years."""
    section = run.build_contract_section(
        "fundamentals", run.gate_fundamentals, "three-statement-model", "GULFOILLUB", FIXTURES
    )
    note = run.contract_section_note(section, "GULFOILLUB")
    assert "FY2026-27 forecast" in note
    assert "FY2023-24 actuals" in note
    assert "net cash" in note


def test_fundamentals_note_falls_back_without_year_keys():
    section = {"namespace": "fundamentals", "available": True, "data": {"balance_check": "passed"}}
    assert run.contract_section_note(section, "X") == run.FUNDAMENTALS_SCOPE_NOTE


def test_cli_prints_the_fundamentals_scope_note_for_any_ticker(tmp_path):
    rc = run.main(
        [
            "--ticker", "TATAELXSI",
            "--peers", "",
            "--offline",
            "--date", "2026-10-17",
            "--output-dir", str(tmp_path),
            "--no-charts",
            "--risk-lab-root", str(tmp_path / "no-such-sibling-checkout"),
            "--factor-model-root", str(tmp_path / "no-such-sibling-checkout"),
            "--reverse-dcf-root", str(tmp_path / "no-such-sibling-checkout"),
            "--iv-surface-root", str(tmp_path / "no-such-sibling-checkout"),
            "--sentiment-root", str(tmp_path / "no-such-sibling-checkout"),
        ]
    )
    assert rc == 0
    text = (tmp_path / "tearsheet_TATAELXSI_2026-10-17.md").read_text()
    assert run.FUNDAMENTALS_SCOPE_NOTE in text


# -- Day 147 (V16, V17): the valuation section states its own basis --


def test_valuation_note_names_price_date_base_year_and_the_fixed_margin():
    section = run.build_contract_section(
        "valuation", run.gate_valuation, "reverse-dcf-engine", "GULFOILLUB", FIXTURES
    )
    note = run.contract_section_note(section, "GULFOILLUB")
    assert "solved against ₹1,054.00 (2026-10-26)" in note
    assert "FY2023-24 financials" in note
    assert "implied_ebit_margin is the FY2023-24 EBIT margin held fixed (an input, not solved)" in note
    assert "financials source: hand-entered, 10-year (GULFOILLUB base case)" in note


def test_valuation_note_without_basis_keys_keeps_the_old_source_note():
    section = {
        "namespace": "valuation",
        "available": True,
        "data": {"financials_source": "yfinance, consolidated, 4-5 years"},
    }
    assert run.contract_section_note(section, "X") == "financials source: yfinance, consolidated, 4-5 years"


# -- Day 148 (R24, P97): contract rows carry a label, a unit and a horizon --


def _gulfoillub_tearsheet(tmp_path):
    rc = run.main(
        [
            "--ticker", "GULFOILLUB",
            "--offline",
            "--date", "2026-10-26",
            "--output-dir", str(tmp_path),
            "--no-charts",
        ]
    )
    assert rc == 0
    return (tmp_path / "tearsheet_GULFOILLUB_2026-10-26.md").read_text()


def test_risk_rows_name_their_horizon_and_statistic(tmp_path):
    text = _gulfoillub_tearsheet(tmp_path)
    assert "| VaR 95%, 20-day, simulated (var_95) | -11.72% |" in text
    assert "| Mean simulated 20-day max drawdown (max_dd_sim) | -8.61% |" in text
    assert "| 1-day parametric VaR 95% backtest, Kupiec (kupiec_95) |" in text


def test_valuation_rows_are_in_rupees_and_percent(tmp_path):
    text = _gulfoillub_tearsheet(tmp_path)
    assert "| EBIT margin, base year, held fixed: an input (implied_ebit_margin) | 13.37% |" in text
    assert "| Highest price the model reaches, 10y, ₹/share (max_achievable_price_10y) | ₹904.98 |" in text
    assert "| Price reachable at a constant 10y growth rate (price_reachable) | No |" in text
    assert "+904.9835" not in text


def test_fundamentals_ratio_prints_as_a_multiple(tmp_path):
    text = _gulfoillub_tearsheet(tmp_path)
    assert "(net_debt_ebitda_fy3) | -1.69x |" in text


def test_unknown_contract_keys_render_unchanged():
    assert run.contract_field("risk", "brand_new_key", 0.5, {}) == ("brand_new_key", "+0.5000")


# -- Day 149 (D49, P98): liquidity in rupees, and the factor section names its basis --


def test_peer_rows_carry_rupee_turnover(cfg):
    rows = run.build_peer_table(["GULFOILLUB", *run.DEFAULT_PEERS], "fixtures")
    by_ticker = {r["ticker"]: r for r in rows}
    for r in rows:
        assert r["turnover_20d"] > 0
    # in rupees SOTL trades more than GANDHAR, though GANDHAR trades more shares (D49)
    assert by_ticker["SOTL"]["turnover_20d"] > by_ticker["GANDHAR"]["turnover_20d"]
    assert by_ticker["GANDHAR"]["adv_20d"] > by_ticker["SOTL"]["adv_20d"]


def test_fmt_crore_formats_rupees_in_crore():
    assert run._fmt_crore(46_900_000.0) == "₹4.69 cr"
    assert run._fmt_crore(None) == "n/a"


def test_subject_and_peer_tables_label_turnover_and_shares(cfg):
    subject = run.build_subject_section("GULFOILLUB", "fixtures", cfg)
    rows = run.build_peer_table(["GULFOILLUB", *run.DEFAULT_PEERS], "fixtures")
    for text in (render(run.render_subject_table(subject)), render(run.render_peer_table(rows))):
        assert "Turnover (20d avg, ₹ cr)" in text
        assert "ADV (20d, shares)" in text
    assert run._fmt_crore(subject["liquidity"]["turnover_20d"]) in render(run.render_subject_table(subject))


def test_tearsheet_header_and_peer_rows_show_rupee_turnover(cfg, tmp_path):
    subject = run.build_subject_section("GULFOILLUB", "fixtures", cfg)
    rows = run.build_peer_table(["GULFOILLUB", *run.DEFAULT_PEERS], "fixtures")
    path = tmp_path / "tearsheet.md"
    run.write_tearsheet(subject, rows, "2026-10-26", path)
    text = path.read_text()
    turnover = run._fmt_crore(subject["liquidity"]["turnover_20d"])
    assert f"20-day average turnover {turnover}" in text
    assert "| Turnover (20d avg, ₹ cr) | ADV (20d, shares) |" in text
    for r in rows:
        assert f"| {run._fmt_crore(r['turnover_20d'])} | {r['adv_20d']:,.0f} |" in text


def test_peer_table_without_turnover_shows_na():
    rows = [{"ticker": "GANDHAR", "return_1y": None, "volatility_1y": None, "adv_20d": 123.0}]
    assert "n/a" in render(run.render_peer_table(rows))


def test_factor_note_names_the_factor_set_and_window():
    section = run.build_contract_section("factor", run.gate_factor, "fama-french-factor-model", "GULFOILLUB", FIXTURES)
    assert run.contract_section_note(section, "GULFOILLUB") == (
        "IIMA India factors (MF/SMB/HML/WML), monthly, 2014-08 to 2025-12, 137 months"
    )


def test_factor_note_keeps_the_old_method_label_for_reliance():
    section = {"namespace": "factor", "available": True, "data": {"alpha_annual": 0.0}}
    assert run.contract_section_note(section, "RELIANCE") == run.gate_factor.method_label("RELIANCE")
    assert run.contract_section_note(section, "X") is None
