"""Day 21/22 (C1): generate a satellite's contract on the fly, for a ticker
with no committed ``fixtures/<namespace>/<TICKER>.json``, by running that
repo's own CLI as a subprocess against its sibling checkout.

Communication stays by file, same as every other contract namespace --
this module never imports ``mcsim`` or ``factors``. The only new thing is
that the file is generated on demand (into
``outputs/contracts/<TICKER>/<namespace>.json``, a build artifact, never
committed) instead of being read from a fixture someone already ran the
CLI against and committed by hand. A committed fixture (e.g.
``fixtures/risk/GULFOILLUB.json``, ``fixtures/factor/RELIANCE.json``)
always wins over this path -- see ``stockstalker.run.build_contract_sections``.

Day 21 added the risk path (``generate_risk_contract``, against
monte-carlo-risk-lab's ``mcsim.portfolio``). Day 22 adds the factor path
(``generate_factor_contract``, against fama-french-factor-model's
``factors.stock`` -- the Day 22 ticker-agnostic generalisation of
``factors.gulfoillub``) on the same pattern.

Each subprocess is launched with ``uv run --with-editable .`` from inside
the sibling checkout, not ``sys.executable``: ``mcsim`` depends on
``scipy`` and ``factors`` depends on ``statsmodels``, neither of which
this repo's own interpreter installs (confirmed Day 21/22 -- ``pip show
scipy``/``pip show statsmodels`` here both come back empty), the same
packaging boundary P18/P17 already documented for running a satellite's
tests. This genuinely needs a second checkout on disk, which GitHub
Actions does not provide (a workflow only checks out the one repo it runs
in) -- that is expected, not a bug. The caller falls back to the existing
"no fixture" reason when the sibling checkout, ``uv``, or the subprocess
itself isn't available, the same honest degradation every other contract
namespace already has for a ticker nobody has built a fixture for yet.
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
FACTOR_MODEL_ENV_VAR = "STOCKSTALKER_FACTOR_MODEL_ROOT"
DEFAULT_FACTOR_MODEL_ROOT = ROOT.parent / "fama-french-factor-model"
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


def resolve_factor_model_root(override: str | Path | None = None) -> Path:
    """The fama-french-factor-model checkout to shell out to.

    Explicit ``override`` wins, then ``$STOCKSTALKER_FACTOR_MODEL_ROOT``,
    then the sibling directory this hub's own checkouts use
    (``REPOS_ROOT/fama-french-factor-model``, next to this repo's own root).
    """
    if override:
        return Path(override)
    env = os.environ.get(FACTOR_MODEL_ENV_VAR)
    if env:
        return Path(env)
    return DEFAULT_FACTOR_MODEL_ROOT


def generate_factor_contract(ticker: str, prices_csv: Path, out_path: Path, factor_model_root: Path) -> str | None:
    """Run fama-french-factor-model's ``factors.stock`` against ``prices_csv``,
    writing its ``--contract`` output to ``out_path``.

    ``factors.stock`` (Day 22) is the ticker-agnostic generalisation of
    ``factors.gulfoillub`` -- same IIMA-factor regression, any price CSV.
    Returns ``None`` on success (``out_path`` now holds the contract), or a
    one-line reason on failure. Never raises -- every failure mode (sibling
    missing, ``uv`` missing, the subprocess itself failing or timing out) is
    a normal, expected outcome for a ticker this path hasn't been proven
    for yet, not a crash.
    """
    if not factor_model_root.is_dir():
        return f"fama-french-factor-model is not checked out at {factor_model_root}"
    if not (factor_model_root / "factors" / "stock.py").is_file():
        return f"{factor_model_root} does not look like the fama-french-factor-model checkout (no factors/stock.py)"

    uv = shutil.which("uv")
    if uv is None:
        return (
            "uv is not on PATH -- factors depends on statsmodels, which is not one "
            "of this repo's own dependencies, so its CLI can only be run through "
            "uv's own ephemeral venv (uv run --with-editable .)"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        uv, "run", "--with-editable", ".", "python", "-m", "factors.stock",
        "--ticker", ticker.upper(),
        "--prices", str(prices_csv.resolve()),
        "--model", "ff3wml",
        "--contract", str(out_path.resolve()),
    ]
    try:
        result = subprocess.run(
            cmd, cwd=factor_model_root, capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"fama-french-factor-model subprocess failed to run: {exc}"

    if not out_path.exists():
        stderr_lines = result.stderr.strip().splitlines()
        stderr_tail = stderr_lines[-1] if stderr_lines else ""
        detail = f": {stderr_tail}" if stderr_tail else ""
        return f"fama-french-factor-model subprocess exited {result.returncode} without writing a contract{detail}"
    return None


if __name__ == "__main__":  # pragma: no cover - no standalone CLI, imported by stockstalker.run
    sys.exit("stockstalker.live_contracts has no CLI of its own; see stockstalker.run")
