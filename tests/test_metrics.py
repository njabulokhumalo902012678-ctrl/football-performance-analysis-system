"""Formula tests against hand-checked examples (acceptance item 7 and 8)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.metrics import run_selftests, per90, ratio_pct, minutes_played, fmt


def test_all_builtin_examples_pass():
    bad = [r for r in run_selftests() if not r[1]]
    assert not bad, bad


def test_per90_formula():
    assert per90(1, 45) == 2.0
    assert per90(3, 270) == 1.0
    assert per90(1, 0) is None and per90(1, None) is None


def test_percentage_formulas():
    assert ratio_pct(2, 4) == 50.0
    assert abs(ratio_pct(10, 12) - 83.3333333) < 1e-5
    assert ratio_pct(0, 0) is None and ratio_pct(3, None) is None


def test_minutes_rules():
    app = dict(role="starter", sub_on_minute=None, sub_off_minute=None, dismissed_minute=None, appearance_status="played", minutes_uncertain=0)
    assert minutes_played(app)[0] == 90
    assert minutes_played(dict(app, sub_off_minute=70))[0] == 70
    assert minutes_played(dict(app, dismissed_minute=55))[0] == 55
    assert minutes_played(dict(app, role="substitute", sub_on_minute=75))[0] == 15
    assert minutes_played(dict(app, role="substitute"))[0] is None          # unknown, not invented
    assert minutes_played(dict(app, minutes_uncertain=1))[0] is None
    assert minutes_played(dict(app, appearance_status="unused_substitute"))[0] == 0


def test_missing_data_is_never_shown_as_zero():
    assert fmt({"value": None, "status": "not_collected", "note": ""}) == "Not collected"
    assert fmt({"value": None, "status": "na", "note": ""}) == "N/A"
    assert fmt({"value": 0, "status": "ok", "note": ""}) == "0"
