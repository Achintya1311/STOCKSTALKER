"""Screener tests: config loading, scoring, filtering, ranking, and the
CLI end to end against the committed fixtures."""

import json

import pandas as pd
import pytest

from stockstalker import screener
from stockstalker.data.providers import FixtureProvider


@pytest.fixture
def cfg():
    return screener.load_config(screener.CONFIG_PATH)


@pytest.fixture
def reliance():
    return FixtureProvider().fetch("RELIANCE.NS")


def test_load_config_reads_the_committed_rules_file(cfg):
    assert cfg["weights"]["trend"] == pytest.approx(0.4)
    assert cfg["trend"]["fast"] == 20
    assert cfg["momentum"]["rsi_period"] == 14


def test_load_config_fills_missing_sections_from_defaults(tmp_path):
    path = tmp_path / "partial.yaml"
    path.write_text("weights:\n  trend: 1.0\n  momentum: 0.0\n  volume: 0.0\n")
    cfg = screener.load_config(path)
    assert cfg["weights"] == {"trend": 1.0, "momentum": 0.0, "volume": 0.0}
    assert cfg["trend"] == screener.DEFAULT_CONFIG["trend"]
    assert cfg["filters"] == screener.DEFAULT_CONFIG["filters"]


def test_load_config_fills_missing_keys_within_a_present_section(tmp_path):
    path = tmp_path / "partial.yaml"
    path.write_text("trend:\n  fast: 5\n")
    cfg = screener.load_config(path)
    assert cfg["trend"]["fast"] == 5
    assert cfg["trend"]["slow"] == screener.DEFAULT_CONFIG["trend"]["slow"]


def test_load_universe_skips_blanks_and_comments(tmp_path):
    path = tmp_path / "universe.txt"
    path.write_text("# comment\nRELIANCE.NS\n\nTATACHEM.NS\n")
    assert screener.load_universe(path) == ["RELIANCE.NS", "TATACHEM.NS"]


def test_load_universe_missing_file_is_empty(tmp_path):
    assert screener.load_universe(tmp_path / "nope.txt") == []


def test_compute_signals_bounded(reliance, cfg):
    signals = screener.compute_signals(reliance, cfg)
    assert set(signals) == {"trend", "momentum", "volume"}
    assert all(-1.0 <= v <= 1.0 for v in signals.values())


def test_blended_score_all_positive_signals_is_one():
    score = screener.blended_score(
        {"trend": 1.0, "momentum": 1.0, "volume": 1.0},
        {"trend": 0.4, "momentum": 0.35, "volume": 0.25},
    )
    assert score == 1.0


def test_blended_score_all_negative_signals_is_zero():
    score = screener.blended_score(
        {"trend": -1.0, "momentum": -1.0, "volume": -1.0},
        {"trend": 0.4, "momentum": 0.35, "volume": 0.25},
    )
    assert score == 0.0


def test_blended_score_neutral_signals_is_a_half():
    score = screener.blended_score(
        {"trend": 0.0, "momentum": 0.0, "volume": 0.0},
        {"trend": 0.4, "momentum": 0.35, "volume": 0.25},
    )
    assert score == 0.5


def test_blended_score_weights_need_not_sum_to_one():
    a = screener.blended_score({"trend": 1.0, "momentum": 0.0, "volume": 0.0}, {"trend": 2, "momentum": 2, "volume": 1})
    b = screener.blended_score({"trend": 1.0, "momentum": 0.0, "volume": 0.0}, {"trend": 0.4, "momentum": 0.4, "volume": 0.2})
    assert a == pytest.approx(b)


def test_blended_score_falls_back_to_equal_weight_when_weights_are_all_zero():
    score = screener.blended_score(
        {"trend": 1.0, "momentum": -1.0, "volume": 0.0}, {"trend": 0.0, "momentum": 0.0, "volume": 0.0}
    )
    assert score == 0.5


def test_liquidity_metrics_matches_manual_mean(reliance):
    metrics = screener.liquidity_metrics(reliance, window=20)
    tail = reliance.tail(20)
    assert metrics["adv_20d"] == pytest.approx(float(tail["volume"].mean()), abs=0.01)
    assert metrics["turnover_20d"] == pytest.approx(
        float((tail["close"] * tail["volume"]).mean()), abs=0.01
    )


def test_apply_filters_drops_below_min_adv():
    candidates = [
        {"ticker": "A", "score": 0.9, "liquidity": {"adv_20d": 100}},
        {"ticker": "B", "score": 0.9, "liquidity": {"adv_20d": 100_000}},
    ]
    kept = screener.apply_filters(candidates, {"min_adv_20d": 1000, "min_score": 0.0})
    assert [c["ticker"] for c in kept] == ["B"]


def test_apply_filters_drops_below_min_score():
    candidates = [
        {"ticker": "A", "score": 0.2, "liquidity": {"adv_20d": 100}},
        {"ticker": "B", "score": 0.8, "liquidity": {"adv_20d": 100}},
    ]
    kept = screener.apply_filters(candidates, {"min_adv_20d": 0, "min_score": 0.5})
    assert [c["ticker"] for c in kept] == ["B"]


def test_rank_orders_by_score_descending_and_stamps_rank():
    candidates = [{"ticker": "A", "score": 0.2}, {"ticker": "B", "score": 0.9}, {"ticker": "C", "score": 0.5}]
    ranked = screener.rank(candidates)
    assert [c["ticker"] for c in ranked] == ["B", "C", "A"]
    assert [c["rank"] for c in ranked] == [1, 2, 3]


def test_build_screen_ranks_the_real_universe(cfg):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    errors = []
    screen = screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-09-07", errors)
    assert screen["schema"] == "v1"
    assert screen["generated"] == "2026-09-07"
    assert screen["source"] == "fixtures"
    assert not errors
    assert len(screen["candidates"]) == len(tickers)
    for c in screen["candidates"]:
        assert set(c) >= {"ticker", "rank", "score", "signals", "liquidity"}
        assert 0.0 <= c["score"] <= 1.0
    ranks = [c["rank"] for c in screen["candidates"]]
    assert ranks == sorted(ranks)


def test_build_screen_records_a_fetch_error_without_failing_the_run(cfg):
    errors = []
    screen = screener.build_screen(
        ["RELIANCE.NS", "NOPE.NS"], "fixtures", cfg, "NSE", "2026-09-07", errors
    )
    assert [c["ticker"] for c in screen["candidates"]] == ["RELIANCE.NS"]
    assert len(errors) == 1
    assert "NOPE.NS" in errors[0]


def test_write_json_round_trips_the_screen(cfg, tmp_path):
    screen = screener.build_screen(["RELIANCE.NS"], "fixtures", cfg, "NSE", "2026-09-07")
    path = tmp_path / "screen.json"
    screener.write_json(screen, path)
    assert json.loads(path.read_text()) == screen


def test_write_csv_has_one_row_per_candidate(cfg, tmp_path):
    tickers = screener.load_universe(screener.UNIVERSE_PATH)
    screen = screener.build_screen(tickers, "fixtures", cfg, "NSE", "2026-09-07")
    path = tmp_path / "screen.csv"
    screener.write_csv(screen, path)
    rows = pd.read_csv(path)
    assert len(rows) == len(screen["candidates"])
    assert list(rows.columns) == [
        "rank", "ticker", "score", "trend", "momentum", "volume", "adv_20d", "turnover_20d"
    ]


def test_write_markdown_reports_errors_and_empty_screens(tmp_path):
    empty_screen = {"generated": "2026-09-07", "universe": "NSE", "source": "fixtures", "candidates": []}
    path = tmp_path / "screen.md"
    screener.write_markdown(empty_screen, ["BAD.NS: no fixture"], path)
    text = path.read_text()
    assert "No candidates cleared" in text
    assert "BAD.NS: no fixture" in text


def test_main_runs_offline_against_the_real_fixtures_and_writes_all_three_files(tmp_path):
    exit_code = screener.main(
        [
            "--output-dir", str(tmp_path),
            "--date", "2026-09-07",
        ]
    )
    assert exit_code == 0
    assert (tmp_path / "screen_2026-09-07.json").exists()
    assert (tmp_path / "screen_2026-09-07.csv").exists()
    assert (tmp_path / "screen_2026-09-07.md").exists()

    payload = json.loads((tmp_path / "screen_2026-09-07.json").read_text())
    assert payload["schema"] == "v1"
    assert len(payload["candidates"]) == 3


def test_main_rejects_live_and_offline_together(tmp_path, capsys):
    with pytest.raises(SystemExit):
        screener.main(["--live", "--offline", "--output-dir", str(tmp_path)])


def test_main_empty_universe_is_a_clean_failure(tmp_path):
    empty = tmp_path / "universe.txt"
    empty.write_text("# nothing here\n")
    exit_code = screener.main(["--universe", str(empty), "--output-dir", str(tmp_path)])
    assert exit_code == 1
