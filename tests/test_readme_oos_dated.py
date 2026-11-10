"""P185: the Finding's out-of-sample count is dated, since the segment grows by one bar a day."""
import re
from pathlib import Path

README = (Path(__file__).resolve().parents[1] / "README.md").read_text()


def test_finding_out_of_sample_clause_carries_its_date():
    finding = next(l for l in README.splitlines() if l.startswith("**Finding"))
    clause = finding[finding.index("since the rule froze"):]
    assert re.search(r"as of \d{1,2} \w{3} 2026", clause), clause


def test_out_of_sample_section_has_a_table_per_dated_run():
    section = README.split("### Out of sample")[1].split("\n### ")[0]
    assert len(re.findall(r"^\| RELIANCE\.NS \|", section, re.M)) >= 2
    assert "Run on 10 Nov 2026" in section
