"""P181: the tear sheet names the nearest-expiry basis of the vol figures and shows their tenors."""

from stockstalker import run


def test_atm_iv_label_names_the_nearest_expiry_basis():
    label, text = run.contract_field("vol", "atm_iv_30d", 0.2197, {})
    assert "nearest 30 days" in label
    assert "30-day" not in label
    assert text == "21.97%"


def test_tenor_fields_have_labels():
    label, text = run.contract_field("vol", "atm_tenor_days", 14, {})
    assert label.startswith("Days to that expiry") and text == "14"
    label, text = run.contract_field("vol", "term_slope_tenor_days", [14, 50], {})
    assert "nearest, farthest" in label and text == "14; 50"
    assert run.contract_field("vol", "term_slope_tenor_days", None, {})[1] == "n/a"
