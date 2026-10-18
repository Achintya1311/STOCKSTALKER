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
``factors.gulfoillub``) on the same pattern. Day 23 adds the valuation path
(``generate_valuation_contract``, against reverse-dcf-engine's
``reverse_dcf.solve --live-financials`` -- the Day 23 yfinance-financials
adapter, a simplified "reverse DCF lite"). Unlike risk/factor, the
valuation subprocess itself calls out to yfinance (for the financials, not
just the price this repo already supplies as ``prices_csv``), so a missing
sibling, missing ``uv``, *or* no live network reachable from inside that
subprocess are all ordinary, expected failure modes here -- not just the
first two.

Day 24 adds two more paths, both deliberately *not* a live network fetch:

- ``generate_vol_contract``, against implied-vol-surface's
  ``volsurface.history --provider nse_raw`` -- it only ever solves a raw
  NSE option-chain capture someone has already committed (P12's
  home-connection job; D8's cloud-IP block makes a live NSE fetch from
  this subprocess pointless). ``run.build_contract_sections`` only calls
  this for a ticker that genuinely is an F&O underlying (fo_mktlots.csv) --
  a non-F&O ticker keeps the existing "no listed options" reason and never
  reaches this path at all. Unlike the other three satellites, this repo
  has no ``pyproject.toml``/installable layout yet (a gap, not fixed here,
  out of Day 24's scope) -- so this is the one path that runs via ``uv run
  --with-requirements requirements.txt`` instead of ``--with-editable .``;
  ``python -m volsurface.history`` still resolves the local ``volsurface``
  package because ``uv`` runs it with that checkout as the working
  directory, the same working equivalent P18 already documented.
- ``generate_sentiment_contract``, against headline-sentiment-vs-price's
  ``sentiment.contract`` CLI (default ``vader`` model) -- it reads that
  repo's own growing, committed headline corpus (D3/D10's daily GitHub
  Actions scrape), never a live fetch of its own. A ticker nobody's corpus
  mentions is a real, honest "coverage: none" result (the same shape
  GULFOILLUB's own committed fixture already reports), not a failure, so
  this path needs no "unreachable" framing the way valuation's does.

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
REVERSE_DCF_ENV_VAR = "STOCKSTALKER_REVERSE_DCF_ROOT"
DEFAULT_REVERSE_DCF_ROOT = ROOT.parent / "reverse-dcf-engine"
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


def resolve_reverse_dcf_root(override: str | Path | None = None) -> Path:
    """The reverse-dcf-engine checkout to shell out to.

    Explicit ``override`` wins, then ``$STOCKSTALKER_REVERSE_DCF_ROOT``,
    then the sibling directory this hub's own checkouts use
    (``REPOS_ROOT/reverse-dcf-engine``, next to this repo's own root).
    """
    if override:
        return Path(override)
    env = os.environ.get(REVERSE_DCF_ENV_VAR)
    if env:
        return Path(env)
    return DEFAULT_REVERSE_DCF_ROOT


def generate_valuation_contract(ticker: str, prices_csv: Path, out_path: Path, reverse_dcf_root: Path) -> str | None:
    """Run reverse-dcf-engine's ``reverse_dcf.solve --live-financials`` against
    ``prices_csv`` (for the target price) and a live yfinance fetch (for the
    financials -- see that repo's ``reverse_dcf.live_financials``, Day 23),
    writing its ``--contract`` output to ``out_path``.

    Returns ``None`` on success (``out_path`` now holds the contract), or a
    one-line reason on failure. Never raises -- every failure mode (sibling
    missing, ``uv`` missing, the subprocess itself failing or timing out,
    *or* no live network reachable for yfinance from inside that subprocess)
    is a normal, expected outcome for a ticker this path hasn't been proven
    for yet, not a crash.
    """
    if not reverse_dcf_root.is_dir():
        return f"reverse-dcf-engine is not checked out at {reverse_dcf_root}"
    if not (reverse_dcf_root / "reverse_dcf" / "solve.py").is_file():
        return f"{reverse_dcf_root} does not look like the reverse-dcf-engine checkout (no reverse_dcf/solve.py)"

    uv = shutil.which("uv")
    if uv is None:
        return (
            "uv is not on PATH -- reverse_dcf depends on scipy, which is not "
            "one of this repo's own dependencies, so its CLI can only be run "
            "through uv's own ephemeral venv (uv run --with-editable .)"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        uv, "run", "--with-editable", ".", "python", "-m", "reverse_dcf.solve",
        "--ticker", ticker.upper(),
        "--live-financials",
        "--prices-csv", str(prices_csv.resolve()),
        "--contract", str(out_path.resolve()),
    ]
    try:
        result = subprocess.run(
            cmd, cwd=reverse_dcf_root, capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"reverse-dcf-engine subprocess failed to run: {exc}"

    # reverse_dcf.solve's own main() reports a "price unreachable" result
    # (price_reachable=False in the contract) as a real, honest finding, not
    # an error -- see that repo's solve() docstring. The contract file
    # actually existing is the real signal of success, not the exit code.
    if not out_path.exists():
        stderr_lines = result.stderr.strip().splitlines()
        stderr_tail = stderr_lines[-1] if stderr_lines else ""
        detail = f": {stderr_tail}" if stderr_tail else ""
        return f"reverse-dcf-engine subprocess exited {result.returncode} without writing a contract{detail}"
    return None


IV_SURFACE_ENV_VAR = "STOCKSTALKER_IV_SURFACE_ROOT"
DEFAULT_IV_SURFACE_ROOT = ROOT.parent / "implied-vol-surface"
SENTIMENT_ENV_VAR = "STOCKSTALKER_SENTIMENT_ROOT"
DEFAULT_SENTIMENT_ROOT = ROOT.parent / "headline-sentiment-vs-price"


def resolve_iv_surface_root(override: str | Path | None = None) -> Path:
    """The implied-vol-surface checkout to shell out to.

    Explicit ``override`` wins, then ``$STOCKSTALKER_IV_SURFACE_ROOT``,
    then the sibling directory this hub's own checkouts use
    (``REPOS_ROOT/implied-vol-surface``, next to this repo's own root).
    """
    if override:
        return Path(override)
    env = os.environ.get(IV_SURFACE_ENV_VAR)
    if env:
        return Path(env)
    return DEFAULT_IV_SURFACE_ROOT


def raw_capture_exists(ticker: str, iv_surface_root: Path) -> bool:
    """Whether implied-vol-surface has at least one committed raw NSE
    capture file for ``ticker`` (P12's home-connection job writes
    ``fixtures/chains/raw/<SYMBOL>/<stamp>_<expiry>.json``)."""
    capture_dir = iv_surface_root / "fixtures" / "chains" / "raw" / ticker.upper()
    return capture_dir.is_dir() and any(capture_dir.glob("*.json"))


def generate_vol_contract(ticker: str, out_path: Path, iv_surface_root: Path) -> str | None:
    """Run implied-vol-surface's ``volsurface.history --provider nse_raw``
    against its own committed raw NSE captures for ``ticker``, writing its
    ``--contract`` output to ``out_path``.

    Returns ``None`` on success (``out_path`` now holds the v0.6 vol
    contract), or a one-line reason on failure. Never raises. Checking
    ``raw_capture_exists`` first, before touching ``uv`` or spawning a
    subprocess, means the common case (no raw capture for this ticker --
    true for every ticker except NIFTY/RELIANCE today) fails fast with the
    specific "no captured chain" reason ``run.vol_no_capture_reason``
    otherwise has to construct itself, and never attempts a live NSE fetch
    this subprocess has no better chance at than ``stockstalker`` itself
    does (D8's permanent cloud-IP block).
    """
    if not iv_surface_root.is_dir():
        return f"implied-vol-surface is not checked out at {iv_surface_root}"
    if not (iv_surface_root / "volsurface" / "history.py").is_file():
        return f"{iv_surface_root} does not look like the implied-vol-surface checkout (no volsurface/history.py)"
    if not raw_capture_exists(ticker, iv_surface_root):
        return (
            f"no captured chain: no raw NSE option-chain capture for {ticker.upper()} "
            f"in {iv_surface_root.name}/fixtures/chains/raw (home-connection capture only, P12)"
        )

    uv = shutil.which("uv")
    if uv is None:
        return (
            "uv is not on PATH -- volsurface depends on scipy, which is not one of "
            "this repo's own dependencies, so its CLI can only be run through "
            "uv's own ephemeral venv (uv run --with-requirements requirements.txt)"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # implied-vol-surface has no pyproject.toml/installable layout yet (a
    # gap, not fixed here -- out of Day 24's scope), so this is the one
    # satellite that can't use the `uv run --with-editable .` pattern
    # Day 21/22/23 used; `--with-requirements requirements.txt` builds the
    # same kind of ephemeral venv from its plain requirements file, and
    # `python -m volsurface.history` still resolves the local package
    # because uv runs it with this checkout as the working directory (P18's
    # documented working equivalent for a repo with no installable layout).
    # --out is redirected to a path under our own output_dir, never the
    # sibling's own fixtures/history/ -- this path must never write into a
    # tracked file inside the sibling checkout.
    history_out = out_path.parent / f"{ticker.upper()}_vol_history.json"
    cmd = [
        uv, "run", "--with-requirements", "requirements.txt", "python", "-m", "volsurface.history",
        "--underlying", ticker.upper(),
        "--provider", "nse_raw",
        "--contract", str(out_path.resolve()),
        "--out", str(history_out.resolve()),
    ]
    try:
        result = subprocess.run(
            cmd, cwd=iv_surface_root, capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"implied-vol-surface subprocess failed to run: {exc}"

    if not out_path.exists():
        stderr_lines = result.stderr.strip().splitlines()
        stderr_tail = stderr_lines[-1] if stderr_lines else ""
        detail = f": {stderr_tail}" if stderr_tail else ""
        return f"implied-vol-surface subprocess exited {result.returncode} without writing a contract{detail}"
    return None


def resolve_sentiment_root(override: str | Path | None = None) -> Path:
    """The headline-sentiment-vs-price checkout to shell out to.

    Explicit ``override`` wins, then ``$STOCKSTALKER_SENTIMENT_ROOT``, then
    the sibling directory this hub's own checkouts use
    (``REPOS_ROOT/headline-sentiment-vs-price``, next to this repo's own
    root).
    """
    if override:
        return Path(override)
    env = os.environ.get(SENTIMENT_ENV_VAR)
    if env:
        return Path(env)
    return DEFAULT_SENTIMENT_ROOT


def generate_sentiment_contract(ticker: str, out_path: Path, sentiment_root: Path) -> str | None:
    """Run headline-sentiment-vs-price's ``sentiment.contract`` (default
    ``vader`` model) against its own committed, growing headline corpus for
    ``ticker``, writing its ``--contract`` output to ``out_path``.

    Returns ``None`` on success (``out_path`` now holds the v0.5 sentiment
    contract -- a real "coverage: none" zero for a ticker nobody's corpus
    mentions counts as success, the same honest shape GULFOILLUB's own
    committed fixture already has), or a one-line reason on failure. Never
    raises -- a missing sibling or missing ``uv`` are the only realistic
    failure modes here, since this CLI reads a fixture already committed in
    the sibling checkout rather than making any network call of its own.
    """
    if not sentiment_root.is_dir():
        return f"headline-sentiment-vs-price is not checked out at {sentiment_root}"
    if not (sentiment_root / "sentiment" / "contract.py").is_file():
        return (
            f"{sentiment_root} does not look like the headline-sentiment-vs-price "
            "checkout (no sentiment/contract.py)"
        )

    uv = shutil.which("uv")
    if uv is None:
        return (
            "uv is not on PATH -- sentiment depends on nltk/pandas, which are not "
            "among this repo's own dependencies, so its CLI can only be run "
            "through uv's own ephemeral venv (uv run --with-editable .)"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ticker_yf = ticker.upper() if ticker.upper().endswith(".NS") else f"{ticker.upper()}.NS"
    cmd = [
        uv, "run", "--with-editable", ".", "python", "-m", "sentiment.contract",
        "--ticker", ticker_yf,
        "--out", str(out_path.resolve()),
    ]
    try:
        result = subprocess.run(
            cmd, cwd=sentiment_root, capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"headline-sentiment-vs-price subprocess failed to run: {exc}"

    if not out_path.exists():
        stderr_lines = result.stderr.strip().splitlines()
        stderr_tail = stderr_lines[-1] if stderr_lines else ""
        detail = f": {stderr_tail}" if stderr_tail else ""
        return f"headline-sentiment-vs-price subprocess exited {result.returncode} without writing a contract{detail}"
    return None


if __name__ == "__main__":  # pragma: no cover - no standalone CLI, imported by stockstalker.run
    sys.exit("stockstalker.live_contracts has no CLI of its own; see stockstalker.run")
