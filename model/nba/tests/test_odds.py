import sqlite3

import pandas as pd
import pytest

from common import odds_feed as of
from common import odds_math as om
from nba.store import SCHEMA, upsert
from nba.tests.test_ids import slate

SHEET = """player,market,rung or line,price
Nikola Jokic,Points,25+,-150
Nikola Jokic,Points,30+,+120
Nikola Jokic,Rebounds,Over 11.5,1.83
Shai Gilgeous-Alexander,Points + Assists,35+,10/11
Nikola Jokic,Triple Double,,+250
Denver Nuggets,Spread,-4.5,-110
,Total,Over 229.5,-110
Nikola Jokic,Fantasy Points,40+,-110
Nikola Jokic,Assists,ten,-110
Nikola Jokic,Assists,8+,abc
Nikola Jokic,Points,25+,-150
,Points,20+,-110
Nikola Jokic,Steals,1.5,-110
Nobody Real,Points,10+,-200
"""


def test_odds_math_matches_the_site_library():
    assert om.to_decimal(-110) == pytest.approx(1.9091, abs=1e-4) and om.to_decimal(250) == 3.5
    assert om.implied_prob(-110) == pytest.approx(0.5238, abs=1e-4)
    assert sum(om.fair_probs([-110, -110])) == pytest.approx(1.0)
    assert om.expected_value(0.6, -110) == pytest.approx(0.1455, abs=1e-4)
    assert om.kelly_stake(0.5, -110) == 0.0 and om.kelly_stake(0.6, 100, 0.25) == pytest.approx(0.05)
    assert om.closing_line_value(-110, -130) > 0 > om.closing_line_value(-130, -110)
    assert om.parse_price("1.91") == -110 and om.parse_price("+250") == 250 and om.parse_price("10/11") == -110
    assert om.fair_american(0.75) == -300
    with pytest.raises(ValueError):
        om.to_decimal(0)


def test_pasted_sheet_is_validated_row_by_row(tmp_path):
    rows, bad = of.read_csv(SHEET, known_at="2026-11-11T20:00:00+00:00")
    assert len(rows) == 8
    r = {(x["player_name"], x["market"], x["line"]): x for x in rows}
    assert r[("Nikola Jokic", "pts", 24.5)]["side"] == "over" and r[("Nikola Jokic", "pts", 24.5)]["price"] == -150
    assert r[("Nikola Jokic", "reb", 11.5)]["price"] == -120
    assert r[("Shai Gilgeous-Alexander", "pa", 34.5)]["price"] == -110
    assert r[("Nikola Jokic", "td", 0.5)]["side"] == "yes"
    assert r[("Denver Nuggets", "spread", -4.5)]["side"] == "team" and r[("", "total", 229.5)]["side"] == "over"
    msg = " | ".join(bad)
    for needle in ("row 9: market 'Fantasy Points'", "row 10: 'ten' is neither", "row 11: price 'abc'", "row 12: duplicate",
                   "row 13: player is blank", "row 14: line 1.5 needs over or under"):
        assert needle in msg, needle
    ids = slate(tmp_path)
    good, bad2 = of.resolve(rows, ids, "g1", ["7", "25"])
    assert len(good) == 7 and any("Nobody Real" in b for b in bad2)          # unmatched player dropped and reported
    assert {g["player_id"] for g in good if g["market"] == "pts"} == {"101"}
    assert [g["player_id"] for g in good if g["market"] == "spread"] == ["7"]


def test_sheet_with_missing_columns_is_rejected():
    rows, bad = of.read_csv("player,market,price\nA,Points,-110\n")
    assert rows == [] and "missing column(s) rung or line" in bad[0]


def test_api_rows_keep_only_offered_rungs():
    event = {"home_team": "Denver Nuggets", "away_team": "Oklahoma City Thunder", "commence_time": "2026-11-12T02:00:00Z",
             "bookmakers": [{"key": "bet365", "markets": [
                 {"key": "player_points_alternate", "outcomes": [{"name": "Over", "description": "Nikola Jokic", "point": 24.5, "price": -180},
                                                                 {"name": "Over", "description": "Nikola Jokic", "point": 29.5, "price": 110}]},
                 {"key": "player_rebounds", "outcomes": [{"name": "Over", "description": "Nikola Jokic", "point": 11.5, "price": -115},
                                                         {"name": "Under", "description": "Nikola Jokic", "point": 11.5, "price": -105}]},
                 {"key": "player_double_double", "outcomes": [{"name": "Yes", "description": "Nikola Jokic", "price": -900},
                                                              {"name": "No", "description": "Nikola Jokic", "price": 550}]},
                 {"key": "h2h", "outcomes": [{"name": "Denver Nuggets", "price": -160}, {"name": "Oklahoma City Thunder", "price": 135}]},
                 {"key": "alternate_totals", "outcomes": [{"name": "Over", "point": 225.5, "price": -150}]}]},
                 {"key": "draftkings", "markets": [{"key": "h2h", "outcomes": [{"name": "Denver Nuggets", "price": -165}]}]}]}
    rows = of.rows_from_api(event, "2026-11-11T20:00:00+00:00", "bet365")
    assert {r["book"] for r in rows} == {"bet365"} and len(rows) == 8
    pts = sorted(r["line"] for r in rows if r["market"] == "pts")
    assert pts == [24.5, 29.5]                                              # nothing in between is invented
    assert [r["side"] for r in rows if r["market"] == "dd"] == ["yes"]


def test_closing_price_is_the_last_one_before_tip():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    base = {"source": "csv", "book": "bet365", "game_id": "g1", "market": "pts", "player_id": "101", "player_name": "Nikola Jokic",
            "side": "over", "line": 24.5, "is_close": 0}
    upsert(con, "odds", [{**base, "known_at": "2026-11-11T18:00:00+00:00", "price": -150},
                         {**base, "known_at": "2026-11-11T23:50:00+00:00", "price": -170},
                         {**base, "known_at": "2026-11-12T00:30:00+00:00", "price": -400}])     # after tip: in-play, never the close
    assert of.mark_closing(con, "g1", "2026-11-12T00:00:00+00:00") == 1
    got = pd.read_sql("SELECT price FROM odds WHERE is_close=1", con).price.tolist()
    assert got == [-170]
