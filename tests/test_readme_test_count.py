"""P166: the README's Reproduce block must not pin a test count.

It said "492 passed, 2 skipped on 27 Oct 2026" while the suite had grown to
533 tests by 5 Nov; the count moves with every fix day and with which
sibling checkouts are present, so the line only goes stale.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reproduce_block_pins_no_test_count():
    for line in (ROOT / "README.md").read_text().splitlines():
        if line.lstrip().startswith("pytest"):
            assert not re.search(r"\d+ passed", line), line
