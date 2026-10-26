"""D42: fixtures/fo_mktlots.csv gets a refresh path (fetch-fo-mktlots.yml)."""

import json

import pytest

from stockstalker import fo_mktlots
from stockstalker.run import FO_MKTLOTS_PATH, load_fo_underlyings


def test_the_committed_list_passes_validation():
    fo_mktlots.validate(FO_MKTLOTS_PATH.read_text())


@pytest.mark.parametrize(
    "text, reason",
    [
        ("", "empty"),
        ("<html>Access Denied</html>", "SYMBOL"),
        ("UNDERLYING ,SYMBOL ,OCT-26\nNIFTY 50 ,NIFTY ,65\n", "rows"),
    ],
)
def test_a_blocked_or_truncated_response_is_refused(text, reason):
    with pytest.raises(ValueError, match=reason):
        fo_mktlots.validate(text)


def test_build_meta_records_the_fetch_and_the_lists_own_date():
    meta = fo_mktlots.build_meta("Mon, 29 Sep 2026 18:05:11 GMT", "2026-11-03")
    assert meta["fetched_at"] == "2026-11-03"
    assert meta["list_last_modified"] == "2026-09-29"
    assert meta["source"] == fo_mktlots.URL


def test_build_meta_without_a_last_modified_header_says_unknown():
    assert fo_mktlots.build_meta(None, "2026-11-03")["list_last_modified"] == "unknown"


def test_cli_from_file_rewrites_both_files_and_the_parser_still_reads_them(tmp_path, capsys):
    csv_out, meta_out = tmp_path / "fo.csv", tmp_path / "meta.json"
    code = fo_mktlots.main(
        ["--from-file", str(FO_MKTLOTS_PATH), "--csv", str(csv_out), "--meta", str(meta_out),
         "--last-modified", "Mon, 29 Sep 2026 18:05:11 GMT", "--today", "2026-10-26"]
    )
    assert code == 0
    assert csv_out.read_text() == FO_MKTLOTS_PATH.read_text()
    assert json.loads(meta_out.read_text())["list_last_modified"] == "2026-09-29"
    assert load_fo_underlyings(csv_out) == load_fo_underlyings(FO_MKTLOTS_PATH)
    assert "underlyings" in capsys.readouterr().out


def test_cli_refuses_to_overwrite_with_a_bad_response(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("<html>Access Denied</html>")
    csv_out = tmp_path / "fo.csv"
    with pytest.raises(SystemExit):
        fo_mktlots.main(["--from-file", str(bad), "--csv", str(csv_out), "--meta", str(tmp_path / "m.json")])
    assert not csv_out.exists()
