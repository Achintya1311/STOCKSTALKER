"""Front door Day 1: subject price section, peer table, and the CLI end to
end against the committed GULFOILLUB / lubricant-peer fixtures."""

import io
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
    assert "Not yet included" in text


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
