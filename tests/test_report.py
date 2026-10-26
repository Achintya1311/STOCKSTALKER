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


def test_render_screen_table_adds_vol_columns_only_when_a_candidate_has_them(screen):
    text_without = render(report.render_screen_table(screen))
    assert "ATM IV(30d)" not in text_without

    gated = dict(screen)
    gated["candidates"] = [dict(c) for c in screen["candidates"]]
    gated["candidates"][0]["vol"] = {
        "atm_iv_30d": 0.2150,
        "skew_25d": 0.0108,
        "term_slope": -0.0199,
        "iv_rank_1y": None,
    }
    text_with = render(report.render_screen_table(gated))
    assert "ATM IV(30d)" in text_with
    assert "21.50%" in text_with
    assert "+0.0108" in text_with


def test_render_screen_table_adds_sentiment_columns_only_when_a_candidate_has_them(screen):
    text_without = render(report.render_screen_table(screen))
    assert "Sent. score(7d)" not in text_without

    gated = dict(screen)
    gated["candidates"] = [dict(c) for c in screen["candidates"]]
    gated["candidates"][0]["sentiment"] = {
        "score_7d": 0.296,
        "headline_count_7d": 1,
        "model": "vader",
        "coverage": "partial",
    }
    text_with = render(report.render_screen_table(gated))
    assert "Sent. score(7d)" in text_with
    assert "+0.296" in text_with


def test_render_screen_table_adds_fundamentals_columns_only_when_a_candidate_has_them(screen):
    text_without = render(report.render_screen_table(screen))
    assert "Rev. CAGR(FY3)" not in text_without

    gated = dict(screen)
    gated["candidates"] = [dict(c) for c in screen["candidates"]]
    gated["candidates"][0]["fundamentals"] = {
        "fy3_revenue_cagr": 0.1539,
        "fy3_ebit_margin": 0.1282,
        "net_debt_ebitda_fy3": -1.6879,
        "balance_check": "passed",
    }
    text_with = render(report.render_screen_table(gated))
    assert "Rev. CAGR(FY3)" in text_with
    assert "+15.39%" in text_with
    assert "-1.69" in text_with


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
    # R5: this contract ships only the 95% VaR/CVaR; the Kupiec gap at
    # 99% (and, for RELIANCE, not at 95%) is stated on the console too.
    assert "Kupiec" in out
    assert "REJECTED at 99%" in out


def test_main_requires_both_factor_flags_together(tmp_path):
    with pytest.raises(SystemExit):
        report.main(["--output-dir", str(tmp_path), "--factor-ticker", "RELIANCE.NS"])


def test_main_applies_the_real_reliance_factor_contract_and_reports_a_match(tmp_path, capsys):
    """End to end against fama-french-factor-model's actual fixture output: like the v0.3
    risk gate's RELIANCE (and unlike the v0.7 valuation gate's GULFOILLUB, outside this
    repo's universe), RELIANCE.NS is one of this repo's own three universe tickers, so
    this is a genuine match."""
    contract = ROOT_FIXTURES / "factor" / "RELIANCE.json"
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-07",
            "--no-charts",
            "--factor-contract", str(contract),
            "--factor-ticker", "RELIANCE",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached fama-french-factor-model's contract for RELIANCE" in out
    assert "Alpha" in out
    # R6: the boolean "significant" field reads as words, not True/False
    # (a narrow captured terminal can still wrap or truncate "not
    # significant" across table cells, same as the VaR/ATM column
    # fragments above dodge -- "True"/"False" never appearing is the
    # behavior that actually matters), and RELIANCE's contract is flagged
    # as the old Ken French method wherever it is shown, including here.
    assert "True" not in out
    assert "False" not in out
    assert "old method" in out
    assert "Ken French" in out


def test_main_requires_both_sizing_flags_together(tmp_path):
    with pytest.raises(SystemExit):
        report.main(["--output-dir", str(tmp_path), "--sizing-ticker", "RELIANCE.NS"])


def test_main_applies_the_real_reliance_sizing_contract_and_reports_a_match(tmp_path, capsys):
    """End to end against markowitz-portfolio-optimizer's actual fixture output: like the
    v0.3 risk gate's RELIANCE (and unlike the v0.7 valuation gate's GULFOILLUB, outside
    this repo's universe), RELIANCE.NS is one of this repo's own three universe tickers,
    so this is a genuine match."""
    contract = ROOT_FIXTURES / "sizing" / "RELIANCE.json"
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-07",
            "--no-charts",
            "--sizing-contract", str(contract),
            "--sizing-ticker", "RELIANCE",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached markowitz-portfolio-optimizer's contract for RELIANCE" in out
    assert "Weight" in out
    assert "50.00%" in out
    assert "Energy" in out


def test_main_requires_both_vol_flags_together(tmp_path):
    with pytest.raises(SystemExit):
        report.main(["--output-dir", str(tmp_path), "--vol-ticker", "RELIANCE.NS"])


def test_main_applies_the_real_reliance_vol_contract_and_reports_a_match(tmp_path, capsys):
    """End to end against implied-vol-surface's actual fixture output: like the v0.3
    risk gate's and v0.4 sizing gate's RELIANCE (and unlike the v0.7 valuation gate's
    GULFOILLUB, outside this repo's universe), RELIANCE.NS is one of this repo's own
    three universe tickers, so this is a genuine match."""
    contract = ROOT_FIXTURES / "vol" / "RELIANCE.json"
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-07",
            "--no-charts",
            "--vol-contract", str(contract),
            "--vol-ticker", "RELIANCE",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached implied-vol-surface's contract for RELIANCE" in out
    # Column headers/values can wrap or truncate depending on the terminal width rich
    # detects (narrow in a captured, non-tty test run) -- assert on fragments that
    # survive either way, same approach the risk/sizing gates' tests above use.
    assert "ATM" in out
    assert "28.01%" in out


def test_main_requires_both_sentiment_flags_together(tmp_path):
    with pytest.raises(SystemExit):
        report.main(["--output-dir", str(tmp_path), "--sentiment-ticker", "RELIANCE.NS"])


def test_main_applies_the_real_infy_sentiment_contract_and_reports_no_match(tmp_path, capsys):
    """End to end against headline-sentiment-vs-price's actual fixture output: like the
    v0.7 valuation gate's GULFOILLUB, INFY.NS isn't in this repo's 3-ticker universe
    (RELIANCE/TATACHEM/CROMPTON), so the honest outcome is no match, printed as such."""
    contract = ROOT_FIXTURES / "sentiment" / "INFY.json"
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-29",
            "--no-charts",
            "--sentiment-contract", str(contract),
            "--sentiment-ticker", "INFY.NS",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "is not in this screen's universe" in out
    assert "Sent. score(7d)" not in out


def test_main_attaches_sentiment_when_the_ticker_matches_the_universe(tmp_path, capsys):
    contract = tmp_path / "contract.json"
    contract.write_text(
        '{"sentiment": {"score_7d": 0.31, "headline_count_7d": 12, "model": "finbert", "coverage": "partial"}}'
    )
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-29",
            "--no-charts",
            "--sentiment-contract", str(contract),
            "--sentiment-ticker", "RELIANCE.NS",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached headline-sentiment-vs-price's contract for RELIANCE.NS" in out


def test_main_requires_both_fundamentals_flags_together(tmp_path):
    with pytest.raises(SystemExit):
        report.main(["--output-dir", str(tmp_path), "--fundamentals-ticker", "RELIANCE.NS"])


def test_main_applies_the_real_gulfoillub_fundamentals_contract_and_reports_no_match(tmp_path, capsys):
    """End to end against three-statement-model's actual fixture output: like the v0.7
    valuation gate's GULFOILLUB, this ticker isn't in this repo's 3-ticker universe
    (RELIANCE/TATACHEM/CROMPTON), so the honest outcome is no match, printed as such."""
    contract = ROOT_FIXTURES / "fundamentals" / "GULFOILLUB.json"
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-10-11",
            "--no-charts",
            "--fundamentals-contract", str(contract),
            "--fundamentals-ticker", "GULFOILLUB",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "is not in this screen's universe" in out
    assert "Rev. CAGR(FY3)" not in out


def test_main_attaches_fundamentals_when_the_ticker_matches_the_universe(tmp_path, capsys):
    contract = tmp_path / "contract.json"
    contract.write_text(
        '{"fundamentals": {"fy3_revenue_cagr": 0.11, "fy3_ebit_margin": 0.19, '
        '"net_debt_ebitda_fy3": 1.8, "balance_check": "passed"}}'
    )
    exit_code = report.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-10-11",
            "--no-charts",
            "--fundamentals-contract", str(contract),
            "--fundamentals-ticker", "RELIANCE.NS",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "attached three-statement-model's contract for RELIANCE.NS" in out
