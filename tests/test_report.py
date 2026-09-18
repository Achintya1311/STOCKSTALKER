"""Report tests: table rendering, chart writing, and the CLI end to end
against the committed fixtures."""

import io
from pathlib import Path

import pytest
from rich.console import Console

from stockstalker import backtest, report, screener
from stockstalker.data.providers import FixtureProvider

ROOT_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def screen(cfg):
    return screener.build_screen(
        ["RELIANCE.NS", "TATACHEM.NS", "CROMPTON.NS"], "fixtures", cfg, "NSE", "2026-09-07"
    )


@pytest.fixture
def backtest_report(cfg):
    return backtest.run_backtest(
        ["RELIANCE.NS", "TATACHEM.NS", "CROMPTON.NS"], "fixtures", cfg, generated="2026-09-07"
    )


def render(table):
    buf = io.StringIO()
    Console(file=buf, width=200).print(table)
    return buf.getvalue()


def test_render_screen_table_lists_every_candidate(screen):
    text = render(report.render_screen_table(screen))
    assert "2026-09-07" in text
    for c in screen["candidates"]:
        assert c["ticker"] in text


def test_render_screen_table_handles_no_candidates():
    empty = {"generated": "2026-09-07", "universe": "NSE", "source": "fixtures", "candidates": []}
    text = render(report.render_screen_table(empty))
    assert "2026-09-07" in text


def test_render_screen_table_adds_valuation_columns_only_when_a_candidate_has_them(screen):
    text_without = render(report.render_screen_table(screen))
    assert "Implied CAGR" not in text_without

    gated = dict(screen)
    gated["candidates"] = [dict(c) for c in screen["candidates"]]
    gated["candidates"][0]["valuation"] = {
        "implied_cagr": -0.0049,
        "implied_ebit_margin": 0.1337,
        "implied_reinvestment": -0.1568,
        "breakeven_growth": 0.0352,
    }
    text_with = render(report.render_screen_table(gated))
    assert "Implied CAGR" in text_with
    assert "-0.49%" in text_with
    assert "+3.52%" in text_with


def test_render_screen_table_adds_risk_columns_only_when_a_candidate_has_them(screen):
    text_without = render(report.render_screen_table(screen))
    assert "VaR 95%" not in text_without

    gated = dict(screen)
    gated["candidates"] = [dict(c) for c in screen["candidates"]]
    gated["candidates"][0]["risk"] = {
        "var_95": -0.0915,
        "cvar_95": -0.1082,
        "max_dd_sim": -0.0596,
        "horizon_days": 20,
    }
    text_with = render(report.render_screen_table(gated))
    assert "VaR 95%" in text_with
    assert "-9.15%" in text_with
    assert "-10.82%" in text_with


def test_render_backtest_table_lists_every_result(backtest_report):
    text = render(report.render_backtest_table(backtest_report))
    assert "beat buy-and-hold" in text
    for r in backtest_report["results"]:
        assert r["ticker"] in text


def test_write_charts_draws_one_heatmap_per_ticker(tmp_path):
    errors = []
    paths = report.write_charts(["RELIANCE.NS", "TATACHEM.NS"], "fixtures", tmp_path, errors)
    assert len(paths) == 2
    assert not errors
    for path in paths:
        assert path.exists()
        assert path.stat().st_size > 0


def test_write_charts_records_a_bad_ticker_instead_of_raising(tmp_path):
    errors = []
    paths = report.write_charts(["NOSUCHTICKER.NS"], "fixtures", tmp_path, errors)
    assert paths == []
    assert len(errors) == 1
    assert "NOSUCHTICKER.NS" in errors[0]


def test_main_runs_offline_and_writes_charts(tmp_path, capsys):
    exit_code = report.main(["--output-dir", str(tmp_path), "--date", "2026-09-07"])
    assert exit_code == 0
    for ticker in ["RELIANCE_NS", "TATACHEM_NS", "CROMPTON_NS"]:
        assert (tmp_path / f"heatmap_{ticker}.png").exists()

    out = capsys.readouterr().out
    assert "RELIANCE.NS" in out
    assert "beat buy-and-hold" in out


def test_main_no_charts_skips_chart_files(tmp_path, capsys):
    exit_code = report.main(["--output-dir", str(tmp_path), "--date", "2026-09-07", "--no-charts"])
    assert exit_code == 0
    assert list(tmp_path.glob("*.png")) == []


def test_main_rejects_live_and_offline_together(tmp_path):
    with pytest.raises(SystemExit):
        report.main(["--live", "--offline", "--output-dir", str(tmp_path)])


def test_main_empty_universe_is_a_clean_failure(tmp_path):
    empty = tmp_path / "universe.txt"
    empty.write_text("# nothing here\n")
    exit_code = report.main(["--universe", str(empty), "--output-dir", str(tmp_path)])
    assert exit_code == 1


def test_main_requires_both_valuation_flags_together(tmp_path):
    with pytest.raises(SystemExit):
        report.main(["--output-dir", str(tmp_path), "--valuation-ticker", "RELIANCE.NS"])


def test_main_applies_the_real_gulfoillub_valuation_contract_and_reports_no_match(tmp_path, capsys):
    """End to end against reverse-dcf-engine's actual fixture output: GULFOILLUB isn't in
    this repo's 3-ticker universe, so the honest outcome is no match, printed as such."""
    contract = ROOT_FIXTURES / "valuation" / "GULFOILLUB.json"
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-07",
            "--no-charts",
            "--valuation-contract", str(contract),
            "--valuation-ticker", "GULFOILLUB",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "is not in this screen's universe" in out
    assert "Implied CAGR" not in out


def test_main_attaches_valuation_when_the_ticker_matches_the_universe(tmp_path, capsys):
    contract = tmp_path / "contract.json"
    contract.write_text('{"valuation": {"implied_cagr": 0.1, "implied_ebit_margin": 0.2, '
                         '"implied_reinvestment": 0.3, "breakeven_growth": 0.08}}')
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-07",
            "--no-charts",
            "--valuation-contract", str(contract),
            "--valuation-ticker", "RELIANCE.NS",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached reverse-dcf-engine's contract for RELIANCE.NS" in out
    # Column headers/values can wrap or truncate depending on the terminal width rich
    # detects (narrow in a captured, non-tty test run) -- assert on fragments that
    # survive either way rather than the exact rendered string.
    assert "CAGR" in out
    assert "growth" in out
    assert "8.00%" in out  # breakeven_growth, the narrower of the two new columns


def test_main_requires_both_risk_flags_together(tmp_path):
    with pytest.raises(SystemExit):
        report.main(["--output-dir", str(tmp_path), "--risk-ticker", "RELIANCE.NS"])


def test_main_applies_the_real_reliance_risk_contract_and_reports_a_match(tmp_path, capsys):
    """End to end against monte-carlo-risk-lab's actual fixture output: unlike the v0.7
    valuation gate's GULFOILLUB (outside this repo's universe), RELIANCE is one of this
    repo's own three universe tickers, so this is a genuine match."""
    contract = ROOT_FIXTURES / "risk" / "RELIANCE.json"
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-07",
            "--no-charts",
            "--risk-contract", str(contract),
            "--risk-ticker", "RELIANCE",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached monte-carlo-risk-lab's contract for RELIANCE" in out
    # Column headers/values can wrap or truncate depending on the terminal width rich
    # detects (narrow in a captured, non-tty test run) -- assert on fragments that
    # survive either way, same approach the valuation gate's test above uses.
    assert "VaR" in out
    assert "-9.15%" in out
