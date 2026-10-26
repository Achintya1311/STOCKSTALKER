"""D40: every contract fixture says where it came from, and still matches it.

``fixtures/PROVENANCE.json`` names, for each sibling-contract fixture, the
repo, the exact command and the input it was generated from. Two checks:

- offline, always: every fixture file has an entry and every entry's file
  exists, so a new fixture cannot land without saying where it came from;
- against the sibling checkouts (``contracts.yml`` checks them out; skipped
  when one is absent): rerun each deterministic entry's command and compare
  the output with the committed copy, so a stale fixture fails here instead
  of going unnoticed for weeks (D39: the RELIANCE vol fixture sat on a
  synthetic chain for four weeks).
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
MANIFEST = FIXTURES / "PROVENANCE.json"
CONTRACT_DIRS = ("risk", "factor", "vol", "sentiment", "sizing", "valuation", "fundamentals")
REQUIRED_KEYS = {"repo", "env_var", "command", "inputs", "generated", "deterministic"}


def _entries() -> dict[str, dict]:
    return json.loads(MANIFEST.read_text())["fixtures"]


def test_every_contract_fixture_has_a_provenance_entry():
    on_disk = {
        str(p.relative_to(FIXTURES)) for d in CONTRACT_DIRS for p in (FIXTURES / d).glob("*.json")
    }
    entries = _entries()
    assert on_disk - set(entries) == set(), "fixtures with no provenance entry"
    assert set(entries) - on_disk == set(), "provenance entries for missing files"
    for name, entry in entries.items():
        assert REQUIRED_KEYS <= set(entry), name
        assert isinstance(entry["deterministic"], bool), name
        if entry["deterministic"]:
            assert entry["command"], name
            assert all("{out}" in " ".join(step) for step in entry["command"]), name
        else:
            assert entry.get("why_not_checked"), name


def _close(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(
            a, b, rel_tol=1e-9, abs_tol=1e-12
        )
    return a == b


def test_close_compares_nested_contracts():
    assert _close({"x": {"a": 0.1 + 0.2, "b": None}}, {"x": {"a": 0.3, "b": None}})
    assert not _close({"x": {"a": 0.3}}, {"x": {"a": 0.31}})
    assert not _close({"x": {"a": 0.3}}, {"x": {"a": 0.3, "extra": 1}})


def _sibling_root(entry: dict) -> Path:
    env = os.environ.get(entry["env_var"])
    return Path(env).expanduser().resolve() if env else ROOT.parent / entry["repo"]


DETERMINISTIC = sorted(name for name, e in _entries().items() if e["deterministic"])


@pytest.mark.parametrize("name", DETERMINISTIC)
def test_committed_fixture_matches_a_fresh_sibling_run(name, tmp_path):
    entry = _entries()[name]
    root = _sibling_root(entry)
    if not (root / "pyproject.toml").is_file():
        pytest.skip(f"{entry['repo']} is not checked out at {root}; contracts.yml checks it out")
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    if entry.get("writes_side_files"):
        # e.g. volsurface.history also appends to the sibling's own fixtures/history.
        scratch = tmp_path / entry["repo"]
        shutil.copytree(root, scratch, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "outputs"))
        root = scratch
    out = tmp_path / "out.json"
    for step in entry["command"]:
        args = [part.replace("{out}", str(out)) for part in step]
        proc = subprocess.run(
            [uv, "run", "--with-editable", ".", *args], cwd=root, capture_output=True, text=True, timeout=900
        )
        assert proc.returncode in entry.get("exit_codes", [0]), f"{' '.join(args)} failed:\n{proc.stderr[-2000:]}"
    fresh = json.loads(out.read_text())
    committed = json.loads((FIXTURES / name).read_text())
    assert _close(fresh, committed), (
        f"{name} no longer matches a fresh run of {entry['repo']} -- regenerate it with the "
        f"command in fixtures/PROVENANCE.json and update its 'generated' entry"
    )
