"""The gate between the NFL algorithm and the web app: bad or rule-breaking data must be refused."""
import copy
import json
from pathlib import Path

import pytest

from attd.site_check import check

REPO = Path(__file__).resolve().parents[3]


def good():
    """A small, valid week: one upcoming game, two players, one of each kind of ticket."""
    return {
        "meta": {"season": 2026, "week": 12},
        "games": [{"id": "2026_12_AAA_BBB", "away": "AAA", "home": "BBB", "started": False}],
        "players": [
            {"id": "p1", "name": "Back One", "game": "2026_12_AAA_BBB", "p": 0.55},
            {"id": "p2", "name": "Catcher Two", "game": "2026_12_AAA_BBB", "p": 0.40},
        ],
        "props": {
            "p1": {"rush_yds": {"k": [20, 30, 40, 50], "p": [0.95, 0.88, 0.78, 0.66]},
                   "carries": {"k": [10, 15], "p": [0.92, 0.74]}},
            "p2": {"rec_yds": {"k": [20, 30, 40], "p": [0.90, 0.80, 0.71]},
                   "rec": {"k": [2, 3], "p": [0.90, 0.76]}},
        },
        "corr": {"atd": {}, "legs": {}},
        "algo": {
            "atd": [{"n": 2, "legs": ["p1", "p2"], "p": 0.24}],
            "atd_combos": [{"game": "2026_12_AAA_BBB", "n": 2, "legs": ["p1", "p2"], "p": 0.24}],
            "atd_styles": {"chalk": {"label": "Chalk", "tickets": [{"n": 2, "legs": ["p1", "p2"], "p": 0.24}]}},
            "sgp": [{"game": "2026_12_AAA_BBB", "p": 0.52, "legs": [
                {"id": "p1", "mk": "rush_yds", "k": 40, "p": 0.78},
                {"id": "p1", "mk": "carries", "k": 15, "p": 0.74},
                {"id": "p2", "mk": "rec_yds", "k": 30, "p": 0.80},
                {"id": "p2", "mk": "rec", "k": 3, "p": 0.76}]}],
            "props": [{"ticket": "2026_12_AAA_BBB|floor2", "p": 0.70, "legs": [
                {"id": "p1", "mk": "rush_yds", "k": 30}, {"id": "p2", "mk": "rec", "k": 2}]}],
        },
        "singles": [], "rules": {},
    }


def errors_after(change):
    d = good()
    change(d)
    return check(d, 2026, 12)[0]


def test_valid_week_passes():
    errors, warnings = check(good(), 2026, 12)
    assert errors == [] and warnings == []


def test_missing_section_is_refused():
    d = good()
    del d["props"]
    assert "props" in check(d)[0][0]


def test_wrong_week_is_refused():
    errors, _ = check(good(), 2026, 13)
    assert any("week 12" in e for e in errors)


def test_probability_out_of_range():
    assert errors_after(lambda d: d["players"][0].update(p=1.2))
    assert errors_after(lambda d: d["players"][0].update(p=None))


def test_player_on_unknown_game():
    assert errors_after(lambda d: d["players"][0].update(game="2026_12_XXX_YYY"))


def test_ladder_must_fall_as_rungs_rise():
    def bump(d):
        d["props"]["p1"]["rush_yds"]["p"][2] = 0.93   # 40+ more likely than 30+
    assert any("more likely" in e for e in errors_after(bump))


def test_ladder_lengths_must_match():
    assert errors_after(lambda d: d["props"]["p1"]["rush_yds"]["p"].pop())


def test_yardage_rungs_are_multiples_of_five():
    def odd(d):
        d["props"]["p2"]["rec_yds"]["k"] = [22, 30, 40]
    assert any("multiples of 5" in e for e in errors_after(odd))


def test_rush_and_receiving_ladders_start_at_twenty():
    def low(d):
        d["props"]["p1"]["rush_yds"] = {"k": [10, 20], "p": [0.99, 0.95]}
    assert any("starts below 20" in e for e in errors_after(low))


def test_ticket_cannot_beat_its_weakest_leg():
    assert any("weakest leg" in e for e in errors_after(lambda d: d["algo"]["sgp"][0].update(p=0.80)))
    assert any("weakest leg" in e for e in errors_after(lambda d: d["algo"]["atd"][0].update(p=0.45)))
    assert any("weakest leg" in e for e in errors_after(lambda d: d["algo"]["props"][0].update(p=0.95)))


def test_no_touchdown_leg_in_a_props_sgp():
    def td(d):
        d["algo"]["sgp"][0]["legs"][0] = {"id": "p1", "mk": "atd", "k": None, "p": 0.55}
    assert any("touchdown leg" in e for e in errors_after(td))


def test_at_most_one_leg_under_65():
    def one(d):
        d["algo"]["sgp"][0]["legs"][0]["p"] = 0.60
        d["algo"]["sgp"][0]["p"] = 0.40
    def two(d):
        one(d)
        d["algo"]["sgp"][0]["legs"][1]["p"] = 0.62
    assert errors_after(one) == []
    assert any("under 65%" in e for e in errors_after(two))


def test_leg_under_the_floor_is_reported_not_refused():
    d = good()
    d["algo"]["sgp"][0]["legs"][0]["p"] = 0.68
    errors, warnings = check(d, 2026, 12)
    assert errors == [] and any("70% floor" in w for w in warnings)


def test_props_ticket_leg_must_be_a_real_rung():
    def ghost(d):
        d["algo"]["props"][0]["legs"][0]["k"] = 35
    assert any("not a rung" in e for e in errors_after(ghost))


def test_unknown_player_on_a_ticket():
    assert errors_after(lambda d: d["algo"]["atd"][0]["legs"].append("nobody"))


def test_all_games_started_is_a_warning():
    d = good()
    d["games"][0]["started"] = True
    errors, warnings = check(d, 2026, 12)
    assert errors == [] and any("kicked off" in w for w in warnings)


def test_check_does_not_change_the_data():
    d = good()
    before = copy.deepcopy(d)
    check(d, 2026, 12)
    assert d == before


def test_the_data_on_the_site_passes():
    """Whatever is committed for the web app must itself pass the gate."""
    f = REPO / "public" / "console" / "data.js"
    if not f.exists():
        pytest.skip("no console data in this checkout")
    src = f.read_text(encoding="utf8")
    data = json.loads(src[src.index("{"):src.rindex("}") + 1])
    errors, _ = check(data, data["meta"]["season"], data["meta"]["week"])
    assert errors == []


def test_one_plus_receptions_is_refused():
    # bet365's receptions milestones start at 2+, so a 1+ rung must never reach the site
    def change(d):
        d["props"]["p2"]["rec"] = {"k": [1, 2, 3], "p": [0.97, 0.90, 0.76]}
    errs = errors_after(change)
    assert any("ladder starts below 2+" in e for e in errs)
