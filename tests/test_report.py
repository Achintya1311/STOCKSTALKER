"""Report tests: table rendering, chart writing, and the CLI end to end
against the committed fixtures."""

import io

import pytest
from rich.console import Console

from stockstalker import backtest, report, screener
from stockstalker.data.providers import FixtureProvider


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
