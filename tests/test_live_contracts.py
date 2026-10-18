"""Day 21 (C1): tests for the subprocess wiring that generates a risk
contract on the fly from monte-carlo-risk-lab's own CLI.

``subprocess.run`` and ``shutil.which`` are monkeypatched throughout, so
these tests exercise the plumbing (sibling missing, uv missing, a nonzero
exit that still writes a contract file, a genuine failure, a timeout)
deterministically and fast, without ever invoking uv or a real sibling
checkout. The one test that does exercise the real thing end to end lives
in test_live_risk_contract_smoke.py and skips cleanly when the sibling
checkout isn't actually present -- the same pattern
test_live_provider_smoke.py already uses for a real yfinance call.
"""

from __future__ import annotations

import json
import subprocess

from stockstalker import live_contracts


def test_resolve_risk_lab_root_prefers_explicit_override(tmp_path):
    assert live_contracts.resolve_risk_lab_root(tmp_path) == tmp_path


def test_resolve_risk_lab_root_reads_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(live_contracts.RISK_LAB_ENV_VAR, str(tmp_path))
    assert live_contracts.resolve_risk_lab_root() == tmp_path


def test_resolve_risk_lab_root_defaults_to_the_sibling_checkout(monkeypatch):
    monkeypatch.delenv(live_contracts.RISK_LAB_ENV_VAR, raising=False)
    assert live_contracts.resolve_risk_lab_root() == live_contracts.ROOT.parent / "monte-carlo-risk-lab"


def test_generate_risk_contract_reports_a_missing_sibling_checkout(tmp_path):
    missing = tmp_path / "does-not-exist"
    error = live_contracts.generate_risk_contract(tmp_path / "prices.csv", tmp_path / "risk.json", missing)
    assert error is not None
    assert "not checked out" in error


def test_generate_risk_contract_reports_a_checkout_without_mcsim(tmp_path):
    fake_root = tmp_path / "fake-risk-lab"
    fake_root.mkdir()
    error = live_contracts.generate_risk_contract(tmp_path / "prices.csv", tmp_path / "risk.json", fake_root)
    assert error is not None
    assert "does not look like" in error


def _fake_risk_lab(tmp_path):
    root = tmp_path / "fake-risk-lab"
    (root / "mcsim").mkdir(parents=True)
    (root / "mcsim" / "portfolio.py").write_text("# stub, never actually run in this test file\n")
    return root


def test_generate_risk_contract_reports_uv_missing(monkeypatch, tmp_path):
    root = _fake_risk_lab(tmp_path)
    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: None)
    error = live_contracts.generate_risk_contract(tmp_path / "prices.csv", tmp_path / "risk.json", root)
    assert error is not None
    assert "uv is not on PATH" in error


def test_generate_risk_contract_succeeds_when_the_contract_file_lands(monkeypatch, tmp_path):
    # mcsim.portfolio's own main() exits 1 when the Kupiec test rejects the
    # VaR model at a requested confidence -- a real finding, not an error
    # (see that repo's README Day 5 result) -- so success must be judged by
    # the contract file actually landing, not by the subprocess exit code.
    root = _fake_risk_lab(tmp_path)
    out_path = tmp_path / "out" / "risk.json"
    contract = {"risk": {"var_95": -0.1, "cvar_95": -0.15, "max_dd_sim": -0.05, "horizon_days": 20}}

    def fake_run(cmd, cwd, capture_output, text, timeout):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(contract))
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_risk_contract(tmp_path / "prices.csv", out_path, root)
    assert error is None
    assert json.loads(out_path.read_text()) == contract


def test_generate_risk_contract_reports_failure_when_no_file_is_written(monkeypatch, tmp_path):
    root = _fake_risk_lab(tmp_path)
    out_path = tmp_path / "out" / "risk.json"

    def fake_run(cmd, cwd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, returncode=2, stdout="", stderr="Traceback...\nValueError: boom")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_risk_contract(tmp_path / "prices.csv", out_path, root)
    assert error is not None
    assert "exited 2" in error
    assert "boom" in error
    assert not out_path.exists()


def test_generate_risk_contract_reports_a_timeout(monkeypatch, tmp_path):
    root = _fake_risk_lab(tmp_path)

    def fake_run(cmd, cwd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_risk_contract(tmp_path / "prices.csv", tmp_path / "risk.json", root)
    assert error is not None
    assert "failed to run" in error


# -- Day 22 (C1): same wiring, fama-french-factor-model's factors.stock -----


def test_resolve_factor_model_root_prefers_explicit_override(tmp_path):
    assert live_contracts.resolve_factor_model_root(tmp_path) == tmp_path


def test_resolve_factor_model_root_reads_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(live_contracts.FACTOR_MODEL_ENV_VAR, str(tmp_path))
    assert live_contracts.resolve_factor_model_root() == tmp_path


def test_resolve_factor_model_root_defaults_to_the_sibling_checkout(monkeypatch):
    monkeypatch.delenv(live_contracts.FACTOR_MODEL_ENV_VAR, raising=False)
    assert live_contracts.resolve_factor_model_root() == live_contracts.ROOT.parent / "fama-french-factor-model"


def test_generate_factor_contract_reports_a_missing_sibling_checkout(tmp_path):
    missing = tmp_path / "does-not-exist"
    error = live_contracts.generate_factor_contract("TATAELXSI", tmp_path / "prices.csv", tmp_path / "factor.json", missing)
    assert error is not None
    assert "not checked out" in error


def test_generate_factor_contract_reports_a_checkout_without_factors_stock(tmp_path):
    fake_root = tmp_path / "fake-factor-model"
    fake_root.mkdir()
    error = live_contracts.generate_factor_contract("TATAELXSI", tmp_path / "prices.csv", tmp_path / "factor.json", fake_root)
    assert error is not None
    assert "does not look like" in error


def _fake_factor_model(tmp_path):
    root = tmp_path / "fake-factor-model"
    (root / "factors").mkdir(parents=True)
    (root / "factors" / "stock.py").write_text("# stub, never actually run in this test file\n")
    return root


def test_generate_factor_contract_reports_uv_missing(monkeypatch, tmp_path):
    root = _fake_factor_model(tmp_path)
    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: None)
    error = live_contracts.generate_factor_contract("TATAELXSI", tmp_path / "prices.csv", tmp_path / "factor.json", root)
    assert error is not None
    assert "uv is not on PATH" in error


def test_generate_factor_contract_succeeds_when_the_contract_file_lands(monkeypatch, tmp_path):
    root = _fake_factor_model(tmp_path)
    out_path = tmp_path / "out" / "factor.json"
    contract = {
        "factor": {
            "alpha_annual": -0.17698,
            "alpha_t": -0.98,
            "significant": False,
            "loadings": {"mkt": 0.522, "smb": 1.007, "hml": 1.326, "wml": -0.369},
        }
    }

    def fake_run(cmd, cwd, capture_output, text, timeout):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(contract))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_factor_contract("TATAELXSI", tmp_path / "prices.csv", out_path, root)
    assert error is None
    assert json.loads(out_path.read_text()) == contract


def test_generate_factor_contract_reports_failure_when_no_file_is_written(monkeypatch, tmp_path):
    root = _fake_factor_model(tmp_path)
    out_path = tmp_path / "out" / "factor.json"

    def fake_run(cmd, cwd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, returncode=2, stdout="", stderr="Traceback...\nValueError: boom")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_factor_contract("TATAELXSI", tmp_path / "prices.csv", out_path, root)
    assert error is not None
    assert "exited 2" in error
    assert "boom" in error
    assert not out_path.exists()


def test_generate_factor_contract_reports_a_timeout(monkeypatch, tmp_path):
    root = _fake_factor_model(tmp_path)

    def fake_run(cmd, cwd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_factor_contract("TATAELXSI", tmp_path / "prices.csv", tmp_path / "factor.json", root)
    assert error is not None
    assert "failed to run" in error


# -- Day 23 (C1): same wiring, reverse-dcf-engine's reverse_dcf.solve -------


def test_resolve_reverse_dcf_root_prefers_explicit_override(tmp_path):
    assert live_contracts.resolve_reverse_dcf_root(tmp_path) == tmp_path


def test_resolve_reverse_dcf_root_reads_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(live_contracts.REVERSE_DCF_ENV_VAR, str(tmp_path))
    assert live_contracts.resolve_reverse_dcf_root() == tmp_path


def test_resolve_reverse_dcf_root_defaults_to_the_sibling_checkout(monkeypatch):
    monkeypatch.delenv(live_contracts.REVERSE_DCF_ENV_VAR, raising=False)
    assert live_contracts.resolve_reverse_dcf_root() == live_contracts.ROOT.parent / "reverse-dcf-engine"


def test_generate_valuation_contract_reports_a_missing_sibling_checkout(tmp_path):
    missing = tmp_path / "does-not-exist"
    error = live_contracts.generate_valuation_contract(
        "TATAELXSI", tmp_path / "prices.csv", tmp_path / "valuation.json", missing
    )
    assert error is not None
    assert "not checked out" in error


def test_generate_valuation_contract_reports_a_checkout_without_reverse_dcf(tmp_path):
    fake_root = tmp_path / "fake-reverse-dcf"
    fake_root.mkdir()
    error = live_contracts.generate_valuation_contract(
        "TATAELXSI", tmp_path / "prices.csv", tmp_path / "valuation.json", fake_root
    )
    assert error is not None
    assert "does not look like" in error


def _fake_reverse_dcf(tmp_path):
    root = tmp_path / "fake-reverse-dcf"
    (root / "reverse_dcf").mkdir(parents=True)
    (root / "reverse_dcf" / "solve.py").write_text("# stub, never actually run in this test file\n")
    return root


def test_generate_valuation_contract_reports_uv_missing(monkeypatch, tmp_path):
    root = _fake_reverse_dcf(tmp_path)
    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: None)
    error = live_contracts.generate_valuation_contract(
        "TATAELXSI", tmp_path / "prices.csv", tmp_path / "valuation.json", root
    )
    assert error is not None
    assert "uv is not on PATH" in error


def test_generate_valuation_contract_succeeds_when_the_contract_file_lands(monkeypatch, tmp_path):
    # reverse_dcf.solve's own main() reports price_reachable=False as a
    # real finding, not an error (CRITIQUES.md V2) -- success must be
    # judged by the contract file actually landing, not the exit code.
    root = _fake_reverse_dcf(tmp_path)
    out_path = tmp_path / "out" / "valuation.json"
    contract = {
        "valuation": {
            "implied_cagr": None,
            "implied_ebit_margin": 0.22,
            "implied_reinvestment": None,
            "breakeven_growth": None,
            "price_reachable": False,
            "financials_source": "yfinance, consolidated, 4-5 years",
        }
    }

    def fake_run(cmd, cwd, capture_output, text, timeout):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(contract))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_valuation_contract("TATAELXSI", tmp_path / "prices.csv", out_path, root)
    assert error is None
    assert json.loads(out_path.read_text()) == contract


def test_generate_valuation_contract_reports_failure_when_no_file_is_written(monkeypatch, tmp_path):
    root = _fake_reverse_dcf(tmp_path)
    out_path = tmp_path / "out" / "valuation.json"

    def fake_run(cmd, cwd, capture_output, text, timeout):
        return subprocess.CompletedProcess(
            cmd, returncode=1,
            stdout="",
            stderr="! could not fetch live financials for TATAELXSI: no live network reachable\n",
        )

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_valuation_contract("TATAELXSI", tmp_path / "prices.csv", out_path, root)
    assert error is not None
    assert "exited 1" in error
    assert "no live network reachable" in error
    assert not out_path.exists()


def test_generate_valuation_contract_reports_a_timeout(monkeypatch, tmp_path):
    root = _fake_reverse_dcf(tmp_path)

    def fake_run(cmd, cwd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_valuation_contract(
        "TATAELXSI", tmp_path / "prices.csv", tmp_path / "valuation.json", root
    )
    assert error is not None
    assert "failed to run" in error


# Day 24 (C1): vol, against implied-vol-surface's volsurface.history
# --provider nse_raw -- the only live path that only ever solves a raw
# capture already on disk, never a fresh fetch.


def test_resolve_iv_surface_root_prefers_explicit_override(tmp_path):
    assert live_contracts.resolve_iv_surface_root(tmp_path) == tmp_path


def test_resolve_iv_surface_root_reads_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(live_contracts.IV_SURFACE_ENV_VAR, str(tmp_path))
    assert live_contracts.resolve_iv_surface_root() == tmp_path


def test_resolve_iv_surface_root_defaults_to_the_sibling_checkout(monkeypatch):
    monkeypatch.delenv(live_contracts.IV_SURFACE_ENV_VAR, raising=False)
    assert live_contracts.resolve_iv_surface_root() == live_contracts.ROOT.parent / "implied-vol-surface"


def _fake_iv_surface(tmp_path):
    root = tmp_path / "fake-iv-surface"
    (root / "volsurface").mkdir(parents=True)
    (root / "volsurface" / "history.py").write_text("# stub, never actually run in this test file\n")
    return root


def _commit_raw_capture(root, ticker):
    capture_dir = root / "fixtures" / "chains" / "raw" / ticker.upper()
    capture_dir.mkdir(parents=True)
    (capture_dir / "2026-10-16T2319_27-Oct-2026.json").write_text(
        json.dumps({"captured_at": "2026-10-16T23:19:00", "source": "home-connection", "payload": {}})
    )


def test_raw_capture_exists_is_false_with_no_directory(tmp_path):
    assert live_contracts.raw_capture_exists("TATAELXSI", tmp_path) is False


def test_raw_capture_exists_is_true_once_a_capture_file_is_committed(tmp_path):
    _commit_raw_capture(tmp_path, "RELIANCE")
    assert live_contracts.raw_capture_exists("RELIANCE", tmp_path) is True


def test_generate_vol_contract_reports_a_missing_sibling_checkout(tmp_path):
    missing = tmp_path / "does-not-exist"
    error = live_contracts.generate_vol_contract("RELIANCE", tmp_path / "vol.json", missing)
    assert error is not None
    assert "not checked out" in error


def test_generate_vol_contract_reports_a_checkout_without_volsurface(tmp_path):
    fake_root = tmp_path / "fake-iv-surface"
    fake_root.mkdir()
    error = live_contracts.generate_vol_contract("RELIANCE", tmp_path / "vol.json", fake_root)
    assert error is not None
    assert "does not look like" in error


def test_generate_vol_contract_reports_no_captured_chain_before_touching_uv_or_subprocess(monkeypatch, tmp_path):
    # No raw capture committed for this ticker -- this must fail fast on
    # the directory check, never spawning a subprocess or even checking
    # for uv, since there is nothing a subprocess could solve.
    root = _fake_iv_surface(tmp_path)

    def boom(*args, **kwargs):
        raise AssertionError("must not touch uv/subprocess when no raw capture exists")

    monkeypatch.setattr(live_contracts.shutil, "which", boom)
    monkeypatch.setattr(live_contracts.subprocess, "run", boom)
    error = live_contracts.generate_vol_contract("TATAELXSI", tmp_path / "vol.json", root)
    assert error is not None
    assert "no captured chain" in error
    assert "TATAELXSI" in error


def test_generate_vol_contract_reports_uv_missing(monkeypatch, tmp_path):
    root = _fake_iv_surface(tmp_path)
    _commit_raw_capture(root, "RELIANCE")
    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: None)
    error = live_contracts.generate_vol_contract("RELIANCE", tmp_path / "vol.json", root)
    assert error is not None
    assert "uv is not on PATH" in error


def test_generate_vol_contract_succeeds_when_the_contract_file_lands(monkeypatch, tmp_path):
    root = _fake_iv_surface(tmp_path)
    _commit_raw_capture(root, "RELIANCE")
    out_path = tmp_path / "out" / "vol.json"
    contract = {"vol": {"atm_iv_30d": 0.25, "skew_25d": -0.01, "term_slope": -0.02, "iv_rank_1y": None}}

    def fake_run(cmd, cwd, capture_output, text, timeout):
        assert "--with-requirements" in cmd  # no pyproject.toml in this sibling (P22-equivalent gap)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(contract))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_vol_contract("RELIANCE", out_path, root)
    assert error is None
    assert json.loads(out_path.read_text()) == contract


def test_generate_vol_contract_reports_failure_when_no_file_is_written(monkeypatch, tmp_path):
    root = _fake_iv_surface(tmp_path)
    _commit_raw_capture(root, "RELIANCE")
    out_path = tmp_path / "out" / "vol.json"

    def fake_run(cmd, cwd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="error: boom\n")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_vol_contract("RELIANCE", out_path, root)
    assert error is not None
    assert "exited 1" in error
    assert "boom" in error
    assert not out_path.exists()


def test_generate_vol_contract_reports_a_timeout(monkeypatch, tmp_path):
    root = _fake_iv_surface(tmp_path)
    _commit_raw_capture(root, "RELIANCE")

    def fake_run(cmd, cwd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_vol_contract("RELIANCE", tmp_path / "vol.json", root)
    assert error is not None
    assert "failed to run" in error


# Day 24 (C1): sentiment, against headline-sentiment-vs-price's
# sentiment.contract -- reads that repo's own committed, growing corpus,
# never a live fetch of its own.


def test_resolve_sentiment_root_prefers_explicit_override(tmp_path):
    assert live_contracts.resolve_sentiment_root(tmp_path) == tmp_path


def test_resolve_sentiment_root_reads_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(live_contracts.SENTIMENT_ENV_VAR, str(tmp_path))
    assert live_contracts.resolve_sentiment_root() == tmp_path


def test_resolve_sentiment_root_defaults_to_the_sibling_checkout(monkeypatch):
    monkeypatch.delenv(live_contracts.SENTIMENT_ENV_VAR, raising=False)
    assert live_contracts.resolve_sentiment_root() == live_contracts.ROOT.parent / "headline-sentiment-vs-price"


def _fake_sentiment(tmp_path):
    root = tmp_path / "fake-sentiment"
    (root / "sentiment").mkdir(parents=True)
    (root / "sentiment" / "contract.py").write_text("# stub, never actually run in this test file\n")
    return root


def test_generate_sentiment_contract_reports_a_missing_sibling_checkout(tmp_path):
    missing = tmp_path / "does-not-exist"
    error = live_contracts.generate_sentiment_contract("TATAELXSI", tmp_path / "sentiment.json", missing)
    assert error is not None
    assert "not checked out" in error


def test_generate_sentiment_contract_reports_a_checkout_without_sentiment(tmp_path):
    fake_root = tmp_path / "fake-sentiment"
    fake_root.mkdir()
    error = live_contracts.generate_sentiment_contract("TATAELXSI", tmp_path / "sentiment.json", fake_root)
    assert error is not None
    assert "does not look like" in error


def test_generate_sentiment_contract_reports_uv_missing(monkeypatch, tmp_path):
    root = _fake_sentiment(tmp_path)
    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: None)
    error = live_contracts.generate_sentiment_contract("TATAELXSI", tmp_path / "sentiment.json", root)
    assert error is not None
    assert "uv is not on PATH" in error


def test_generate_sentiment_contract_passes_the_yfinance_suffixed_ticker(monkeypatch, tmp_path):
    root = _fake_sentiment(tmp_path)
    out_path = tmp_path / "out" / "sentiment.json"
    contract = {"sentiment": {"score_7d": None, "headline_count_7d": 0, "model": "vader", "coverage": "none"}}
    seen_cmd = {}

    def fake_run(cmd, cwd, capture_output, text, timeout):
        seen_cmd["cmd"] = cmd
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(contract))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_sentiment_contract("tataelxsi", out_path, root)
    assert error is None
    assert json.loads(out_path.read_text()) == contract
    assert "TATAELXSI.NS" in seen_cmd["cmd"]


def test_generate_sentiment_contract_reports_failure_when_no_file_is_written(monkeypatch, tmp_path):
    root = _fake_sentiment(tmp_path)
    out_path = tmp_path / "out" / "sentiment.json"

    def fake_run(cmd, cwd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="error: boom\n")

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_sentiment_contract("TATAELXSI", out_path, root)
    assert error is not None
    assert "exited 1" in error
    assert "boom" in error
    assert not out_path.exists()


def test_generate_sentiment_contract_reports_a_timeout(monkeypatch, tmp_path):
    root = _fake_sentiment(tmp_path)

    def fake_run(cmd, cwd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(live_contracts.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(live_contracts.subprocess, "run", fake_run)
    error = live_contracts.generate_sentiment_contract("TATAELXSI", tmp_path / "sentiment.json", root)
    assert error is not None
    assert "failed to run" in error
