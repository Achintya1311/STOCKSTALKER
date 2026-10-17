"""Front door Day 1: subject price section, peer table, and the CLI end to
end against the committed GULFOILLUB / lubricant-peer fixtures."""

import io
import json
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
    assert run.fo_mktlots_list_date() == "2026-09-29"


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
