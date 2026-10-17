"""v0.3 -- VaR/CVaR risk envelope on the screen.

monte-carlo-risk-lab publishes one ticker's risk envelope as a file, not a
Python object: ``{"risk": {"var_95", "cvar_95", "max_dd_sim", "horizon_days"}}``
(see that repo's ``mcsim.portfolio.to_contract`` and its ``--contract`` CLI
flag). This module reads that file and attaches it to the one candidate in a
``schema/v1.json`` screen output whose ticker matches, under the ``risk`` key
schema/v1.json already reserves for it.

Communication stays by file: this module never imports ``mcsim``, and nothing
here fails if the satellite's researched ticker is outside today's screened
universe -- the two repos build their fixture sets independently, so a screen
with no matching candidate is an expected, reported outcome, not an error.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_RISK_KEYS = {
    "var_95",
    "cvar_95",
    "max_dd_sim",
    "horizon_days",
}


def load_contract(path: str | Path) -> dict[str, float]:
    """Read and validate a monte-carlo-risk-lab ``--contract`` JSON file."""
    raw = json.loads(Path(path).read_text())
    risk = raw.get("risk")
    if not isinstance(risk, dict):
        raise ValueError(f"{path}: no 'risk' object at the top level")
    missing = REQUIRED_RISK_KEYS - set(risk)
    if missing:
        raise ValueError(f"{path}: risk block missing keys: {sorted(missing)}")
    return risk


def _normalize_ticker(ticker: str) -> str:
    """NSE names show up with (this repo) and without (monte-carlo-risk-lab) the yfinance '.NS' suffix."""
    return ticker.upper().removesuffix(".NS")


# R5: the v0.3 contract shape (``REQUIRED_RISK_KEYS`` above) only ever
# carried the 95% historical VaR/CVaR. monte-carlo-risk-lab's own Kupiec
# proportion-of-failures backtest of the *parametric* 1-day VaR, run and
# reported in that repo's README, never traveled into this file -- a reader
# of the gated screen or front door had no way to know it failed without
# going back to that README. Day 6 (CRITIQUES.md R5) added ``var_99``,
# ``cvar_99``, ``kupiec_95`` and ``kupiec_99`` to the contract itself (new
# keys, additive -- ``REQUIRED_RISK_KEYS`` is unchanged) and regenerated
# both fixtures, so the real backtest now renders directly from the
# contract's own fields (``render_contract_section``/``contract_sections_markdown``
# in ``stockstalker.run`` already print every key in a contract generically).
# This static table is kept only as a fallback for a contract that hasn't
# been regenerated yet -- see ``kupiec_note`` below.
KUPIEC_NOTES: dict[str, str] = {
    "RELIANCE": (
        "Kupiec backtest (monte-carlo-risk-lab README): parametric 1-day VaR "
        "not rejected at 95% (20/500 exceptions vs 25.0 expected, LR=1.127, "
        "p=0.29) but REJECTED at 99% (10/500 vs 5.0 expected, LR=3.914, "
        "p=0.048). This contract ships only the 95% VaR/CVaR."
    ),
    "GULFOILLUB": (
        "Kupiec backtest (monte-carlo-risk-lab README): parametric 1-day VaR "
        "REJECTED at both 95% (114/3,006 vs 150.3 expected, LR=10.032, "
        "p=0.0015) and 99% (44/3,006 vs 30.1 expected, LR=5.713, p=0.0168). "
        "This contract ships only the 95% VaR/CVaR."
    ),
}


def _kupiec_verdict_note(risk: dict[str, Any]) -> str:
    """Render the real ``kupiec_95``/``kupiec_99`` fields a Day-6 contract carries
    as the same one-line, human-readable verdict ``KUPIEC_NOTES`` used to hand-write --
    sourced to the file's own numbers this time, not a hardcoded guess."""
    k95, k99 = risk["kupiec_95"], risk["kupiec_99"]
    r95, r99 = k95["reject_at_5pct"], k99["reject_at_5pct"]

    def fragment(level: str, k: dict[str, Any]) -> str:
        word = "REJECTED" if k["reject_at_5pct"] else "not rejected"
        return (
            f"{word} at {level}% ({k['n_exceptions']}/{k['n_obs']:,} vs "
            f"{k['expected_exceptions']:.1f} expected, LR={k['lr_stat']:.3f}, p={k['p_value']:.4f})"
        )

    if r95 and r99:
        verdict = f"REJECTED at both 95% ({fragment('95', k95).split('(', 1)[1]} and 99% ({fragment('99', k99).split('(', 1)[1]}"
    elif not r95 and not r99:
        verdict = f"not rejected at either 95% ({fragment('95', k95).split('(', 1)[1]} or 99% ({fragment('99', k99).split('(', 1)[1]}"
    else:
        first, second = ("95", "99") if r95 else ("99", "95")
        k_first, k_second = (k95, k99) if r95 else (k99, k95)
        verdict = f"{fragment(first, k_first)} but {fragment(second, k_second)}"

    return f"Kupiec backtest (this contract's own fields): parametric 1-day VaR {verdict}."


def kupiec_note(ticker: str, risk: dict[str, Any] | None = None) -> str | None:
    """A one-line verdict summary of the Kupiec backtest for this ticker's VaR model.

    ``risk`` is the loaded contract block for this ticker, when the caller has
    it to hand. Once it carries ``kupiec_99`` (Day 6), the verdict is computed
    straight from those real fields instead of a hardcoded guess -- see
    ``_kupiec_verdict_note``. Falls back to the static, README-sourced table
    for any contract that still only has the v0.3 shape, or when the caller
    passes no ``risk`` at all (the pre-Day-6 call shape).
    """
    if risk is not None and "kupiec_99" in risk:
        return _kupiec_verdict_note(risk)
    return KUPIEC_NOTES.get(_normalize_ticker(ticker))


def apply_risk_gate(screen: dict[str, Any], ticker: str, risk: dict[str, float]) -> tuple[dict[str, Any], bool]:
    """Return a copy of ``screen`` with ``risk`` attached to the candidate matching ``ticker``.

    Every other candidate passes through unchanged. Returns the screen dict
    unchanged (aside from the copy) plus a bool the caller can report on.
    """
    target = _normalize_ticker(ticker)
    gated_candidates = []
    matched = False
    for candidate in screen["candidates"]:
        candidate = dict(candidate)
        if _normalize_ticker(candidate["ticker"]) == target:
            candidate["risk"] = dict(risk)
            matched = True
        gated_candidates.append(candidate)
    gated = dict(screen)
    gated["candidates"] = gated_candidates
    return gated, matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screen", required=True, help="path to a schema/v1.json-shaped screen output")
    parser.add_argument("--contract", required=True, help="path to monte-carlo-risk-lab's --contract JSON output")
    parser.add_argument("--ticker", required=True, help="the ticker that contract was solved for")
    parser.add_argument("--out", default=None, help="defaults to overwriting --screen in place")
    args = parser.parse_args(argv)

    screen = json.loads(Path(args.screen).read_text())
    risk = load_contract(args.contract)
    gated, matched = apply_risk_gate(screen, args.ticker, risk)

    out_path = Path(args.out) if args.out else Path(args.screen)
    out_path.write_text(json.dumps(gated, indent=2) + "\n")

    if matched:
        print(f"risk gate: attached monte-carlo-risk-lab's contract for {args.ticker} to 1 candidate -> {out_path}")
    else:
        print(
            f"risk gate: {args.ticker} is not in this screen's universe -- "
            f"no candidate updated, {out_path} written unchanged"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
