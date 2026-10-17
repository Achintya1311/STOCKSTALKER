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
