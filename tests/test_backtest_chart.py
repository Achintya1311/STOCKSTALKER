"""P138: a chart of the screen's own test, the random same-size exposure draws.

The site's Technical screen card showed GULFOILLUB against its peers, a
stock the screen never tested. ``backtest --chart`` draws, per screened
name, the 2,000 random same-size exposure returns with the screen's own
return and percentile marked.
"""

import json

import numpy as np
import pytest

from stockstalker import backtest, screener
from stockstalker.viz import random_exposure


def test_keep_draws_returns_the_draws_behind_the_reported_percentile():
    cfg = screener.load_config(screener.CONFIG_PATH)
    r = backtest.backtest_ticker("TATACHEM.NS", "fixtures", cfg, keep_draws=True)
    draws = r["random_draws"]
    assert len(draws) == backtest.DEFAULT_RANDOM_EXPOSURE_DRAWS
    # strategy_return is rounded to 4 places, so allow one draw either side
    assert abs(float((draws < r["strategy_return"]).mean()) - r["exposure_matched_percentile"]) <= 1 / len(draws)
    assert "random_draws" not in backtest.backtest_ticker("TATACHEM.NS", "fixtures", cfg)


def test_plot_writes_one_panel_per_ticker(tmp_path):
    rng = np.random.default_rng(0)
    panels = [
        {"ticker": t, "random_draws": rng.normal(0, 0.1, 500), "strategy_return": 0.05,
         "exposure_matched_percentile": 0.7, "days_long": 100, "days_tested": 400}
        for t in ("A.NS", "B.NS", "C.NS")
    ]
    out = random_exposure.plot_random_exposure(panels, tmp_path / "chart.png")
    assert out.exists() and out.stat().st_size > 1000
    fig_axes = random_exposure.panel_titles(panels)
    assert fig_axes == ["A: 70th percentile", "B: 70th percentile", "C: 70th percentile"]


def test_plot_refuses_no_panels(tmp_path):
    with pytest.raises(ValueError):
        random_exposure.plot_random_exposure([], tmp_path / "x.png")


def test_cli_chart_writes_png_and_keeps_draws_out_of_the_report(tmp_path):
    assert backtest.main(["--offline", "--chart", "--output-dir", str(tmp_path), "--date", "2026-10-30"]) == 0
    assert (tmp_path / "backtest_2026-10-30_random_exposure.png").exists()
    report = json.loads((tmp_path / "backtest_2026-10-30.json").read_text())
    assert all("random_draws" not in r for r in report["results"])


def test_titles_use_ordinals():
    titles = random_exposure.panel_titles(
        [{"ticker": t, "exposure_matched_percentile": q} for t, q in (("X.NS", 0.01), ("Y.NS", 0.22), ("Z.NS", 0.113))]
    )
    assert titles == ["X: 1st percentile", "Y: 22nd percentile", "Z: 11th percentile"]
