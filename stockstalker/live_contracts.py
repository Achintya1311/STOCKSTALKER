"""Day 21 (C1): generate a monte-carlo-risk-lab risk contract on the fly,
for a ticker with no committed ``fixtures/risk/<TICKER>.json``, by running
that repo's own ``mcsim.portfolio`` CLI as a subprocess against the sibling
checkout.

Communication stays by file, same as every other contract namespace --
this module never imports ``mcsim``. The only new thing is that the file
is generated on demand (into ``outputs/contracts/<TICKER>/risk.json``, a
build artifact, never committed) instead of being read from a fixture
someone already ran the CLI against and committed by hand. A committed
fixture (``fixtures/risk/GULFOILLUB.json``/``RELIANCE.json``) always wins
over this path -- see ``stockstalker.run.build_contract_sections``.

The subprocess is launched with ``uv run --with-editable .`` from inside
the sibling checkout, not ``sys.executable``: ``mcsim`` depends on
``scipy``, which this repo's own interpreter does not install (confirmed
Day 21 -- ``pip show scipy`` here comes back empty), the same packaging
boundary P18/P17 already documented for running a satellite's tests. This
genuinely needs a second checkout on disk, which GitHub Actions does not
provide (a workflow only checks out the one repo it runs in) -- that is
expected, not a bug. The caller falls back to the existing "no fixture"
reason when the sibling checkout, ``uv``, or the subprocess itself isn't
available, the same honest degradation every other contract namespace
already has for a ticker nobody has built a fixture for yet.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK_LAB_ENV_VAR = "STOCKSTALKER_RISK_LAB_ROOT"
DEFAULT_RISK_LAB_ROOT = ROOT.parent / "monte-carlo-risk-lab"
SUBPROCESS_TIMEOUT_SECONDS = 180


def resolve_risk_lab_root(override: str | Path | None = None) -> Path:
    """The monte-carlo-risk-lab checkout to shell out to.

    Explicit ``override`` wins, then ``$STOCKSTALKER_RISK_LAB_ROOT``, then
    the sibling directory this hub's own checkouts use
    (``REPOS_ROOT/monte-carlo-risk-lab``, next to this repo's own root).
    """
    if override:
        return Path(override)
    env = os.environ.get(RISK_LAB_ENV_VAR)
    if env:
        return Path(env)
    return DEFAULT_RISK_LAB_ROOT


def generate_risk_contract(prices_csv: Path, out_path: Path, risk_lab_root: Path) -> str | None:
    """Run monte-carlo-risk-lab's ``mcsim.portfolio`` against ``prices_csv``,
    writing its ``--contract`` output to ``out_path``.

    Returns ``None`` on success (``out_path`` now holds the contract), or a
    one-line reason on failure. Never raises -- every failure mode (sibling
    missing, ``uv`` missing, the subprocess itself failing or timing out) is
    a normal, expected outcome for a ticker this path hasn't been proven
    for yet, not a crash.
    """
    if not risk_lab_root.is_dir():
        return f"monte-carlo-risk-lab is not checked out at {risk_lab_root}"
    if not (risk_lab_root / "mcsim" / "portfolio.py").is_file():
        return f"{risk_lab_root} does not look like the monte-carlo-risk-lab checkout (no mcsim/portfolio.py)"

    uv = shutil.which("uv")
    if uv is None:
        return (
            "uv is not on PATH -- mcsim depends on scipy, which is not one of "
            "this repo's own dependencies, so its CLI can only be run through "
            "uv's own ephemeral venv (uv run --with-editable .)"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        uv, "run", "--with-editable", ".", "python", "-m", "mcsim.portfolio",
        "--fixture", str(prices_csv.resolve()),
        "--contract", str(out_path.resolve()),
    ]
    try:
        result = subprocess.run(
            cmd, cwd=risk_lab_root, capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"monte-carlo-risk-lab subprocess failed to run: {exc}"

    # mcsim.portfolio's own main() returns 1 when the Kupiec backtest
    # rejects the VaR model at one of the requested confidence levels -- a
    # real, honest finding (see that repo's README Day 5 result), not a
    # subprocess error. The contract file actually existing is the real
    # signal of success, not the exit code.
    if not out_path.exists():
        stderr_lines = result.stderr.strip().splitlines()
        stderr_tail = stderr_lines[-1] if stderr_lines else ""
        detail = f": {stderr_tail}" if stderr_tail else ""
        return f"monte-carlo-risk-lab subprocess exited {result.returncode} without writing a contract{detail}"
    return None


if __name__ == "__main__":  # pragma: no cover - no standalone CLI, imported by stockstalker.run
    sys.exit("stockstalker.live_contracts has no CLI of its own; see stockstalker.run")
