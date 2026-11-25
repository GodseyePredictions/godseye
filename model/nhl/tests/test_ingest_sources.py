"""MoneyPuck, Daily Faceoff, Scouting the Refs, Natural Stat Trick exports, odds and ladders, and name matching."""
import io
import zipfile

import pandas as pd
import pytest

from nhl import ids
from nhl.ingest import dailyfaceoff, moneypuck, nst, odds, refs
from nhl.tests.conftest import fixture_text


# ------------------------------------------------------------------ MoneyPuck
def shots_zip(rows):
    cols = moneypuck.COLS + ["shotType"]
    text = ",".join(cols) + "\n" + "\n".join(",".join(str(r.get(c, "")) for c in cols) for r in rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("shots_2026.csv", text)
    return buf.getvalue()


def test_moneypuck_shots_use_the_nhl_game_id_and_drop_playoffs():
    base = {"season": 2026, "game_id": 20378, "isPlayoffGame": 0, "period": 1, "time": 151, "isHomeTeam": 1.0,
            "shooterPlayerId": 8478414.0, "goalieIdForShot": 8475660, "xGoal": 0.0712, "goal": 0, "shotWasOnGoal": 1.0,
            "shotOnEmptyNet": 0, "shotType": "WRIST"}
    d = moneypuck.parse_shots(shots_zip([base, {**base, "game_id": 30111, "isPlayoffGame": 1},
                                         {**base, "time": 3590, "goalieIdForShot": 0, "shotOnEmptyNet": 1, "goal": 1, "xGoal": 0.9}]))
    assert len(d) == 2 and set(d.game_id) == {2026020378}
    assert d.iloc[0].to_dict() == {"game_id": 2026020378, "season": 2026, "sec": 151, "period": 1, "is_home": 1,
                                   "shooter_id": 8478414, "goalie_id": 8475660, "xg": 0.0712, "goal": 0, "on_goal": 1, "empty_net": 0}
    assert d.iloc[1].empty_net == 1 and d.iloc[1].goalie_id == 0


# ------------------------------------------------------------------ Daily Faceoff
def test_goalies_confirmed_only_when_labelled_confirmed(cfg):
    rows = dailyfaceoff.parse_goalies(fixture_text("df_goalies.html"), cfg, "2026-11-24T22:00:00+00:00")
    by = {r["team"]: r for r in rows}
    assert by["EDM"]["goalie"] == "Devon Levi" and by["EDM"]["status"] == "Confirmed" and by["EDM"]["confirmed"] == 1
    assert by["VGK"]["goalie"] == "Carter Hart" and by["VGK"]["status"] == "Likely" and by["VGK"]["confirmed"] == 0
    assert by["EDM"]["is_home"] == 1 and by["EDM"]["opp"] == "VGK" and by["EDM"]["date_et"] == "2026-11-24"


def test_lines_units_and_injured_reserve():
    rows = dailyfaceoff.parse_lines(fixture_text("df_lines.html"), "2026-11-24T22:00:00+00:00")
    units = pd.DataFrame(rows).groupby("unit").size().to_dict()
    assert units == {"f1": 3, "f2": 3, "f3": 3, "f4": 3, "d1": 2, "d2": 2, "d3": 2, "g": 2, "pp1": 5, "pp2": 5, "pk1": 4,
                     "pk2": 4, "ir": 3}
    assert {r["team"] for r in rows} == {"NJD"}
    assert next(r for r in rows if r["player"] == "Timo Meier" and r["category"] == "ev")["unit"] == "f1"
    assert all(r["injury"] == "ir" for r in rows if r["unit"] == "ir")


def test_a_changed_page_is_an_error_not_an_empty_night(cfg):
    with pytest.raises(dailyfaceoff.PageChanged):
        dailyfaceoff.parse_goalies("<html>redesigned</html>", cfg)
    with pytest.raises(dailyfaceoff.PageChanged):
        dailyfaceoff.parse_lines('<script id="__NEXT_DATA__">{"props":{"pageProps":{"combinations":{}}}}</script>')


def test_team_slugs_match_daily_faceoff():
    assert [ids.slug(t) for t in ("STL", "MTL", "NJD", "UTA", "VGK")] == \
           ["st-louis-blues", "montreal-canadiens", "new-jersey-devils", "utah-mammoth", "vegas-golden-knights"]


# ------------------------------------------------------------------ referees
def test_referee_post_is_found_and_read():
    url = refs.find_post(fixture_text("refs_index.html"), "2026-11-24")
    assert url and url.endswith("11-24-26/")
    assert refs.find_post(fixture_text("refs_index.html"), "2026-11-25") is None
    rows = refs.parse_post(fixture_text("refs_post.html"), "2026-11-24", "2026-11-24T20:00:00+00:00")
    assert {(r["away"], r["home"]) for r in rows} == {("VGK", "EDM")}
    assert sorted(r["name"] for r in rows if r["role"] == "referee") == ["Corey Syvret", "Michael Markovic"]
    assert sum(r["role"] == "linesperson" for r in rows) == 2


def test_referee_rates_are_shrunk_and_the_crew_is_capped(cfg):
    tg = pd.DataFrame([{"game_id": g, "pen_taken": p} for g, p in [(1, 5), (1, 5), (2, 3), (2, 3), (3, 3), (3, 3)]])
    offs = pd.DataFrame([{"game_id": 1, "name": "Whistle Happy", "role": "referee"}, {"game_id": 2, "name": "Lets Them Play", "role": "referee"},
                         {"game_id": 3, "name": "Lets Them Play", "role": "referee"}, {"game_id": 1, "name": "A Linesperson", "role": "linesperson"}])
    r = refs.ref_rates(offs, tg, cfg).set_index("name")
    assert "A Linesperson" not in r.index
    league = (10 + 6 + 6) / 3
    k = cfg["refs"]["prior_games"]
    assert r.at["Whistle Happy", "factor"] == pytest.approx(1 + (10 / league - 1) * 1 / (1 + k))
    assert r.at["Lets Them Play", "factor"] < 1 < r.at["Whistle Happy", "factor"]
    crew = refs.crew_factor(["Whistle Happy", "Never Seen"], r.reset_index(), cfg)
    assert crew["referees"][1] == {"name": "Never Seen", "games": 0, "factor": 1.0}
    assert crew["factor"] == pytest.approx((r.at["Whistle Happy", "factor"] + 1) / 2)
    wild = pd.DataFrame([{"name": "X", "games": 500, "pens_pg": 20, "league_pg": 7, "factor": 2.5}])
    assert refs.crew_factor(["X"], wild, cfg)["factor"] == 1 + cfg["refs"]["factor_cap"]


# ------------------------------------------------------------------ Natural Stat Trick
def test_nst_export_is_read_and_a_badly_named_file_is_refused(tmp_path):
    f = tmp_path / "team_5v5.csv"
    f.write_text('"","Team","GP","TOI","CF","CA","CF%","xGF","xGA"\n"1","New Jersey Devils","22","1068.5","1041","960","52.02%","45.1","41.3"\n')
    rows = nst.read_export(f, "2026-11-24T12:00:00+00:00")
    assert len(rows) == 1 and (rows[0]["kind"], rows[0]["situation"], rows[0]["entity"]) == ("team", "5v5", "New Jersey Devils")
    import json
    assert json.loads(rows[0]["data"])["CF%"] == 52.02 and json.loads(rows[0]["data"])["xGF"] == 45.1
    bad = tmp_path / "export.csv"
    bad.write_text("Team,GP\nX,1\n")
    with pytest.raises(ValueError):
        nst.read_export(bad)


def test_nst_refusal_is_reported_not_worked_around(cfg, tmp_path, monkeypatch):
    import urllib.error
    from common.http import FetchError

    def refused(*a, **k):
        try:
            raise urllib.error.HTTPError("u", 403, "Forbidden", None, None)
        except urllib.error.HTTPError as e:
            raise FetchError("403 for www.naturalstattrick.com") from e
    monkeypatch.setattr(nst, "get", refused)
    with pytest.raises(nst.NstBlocked):
        nst.fetch(nst.team_table_url(2026), tmp_path, cfg)


# ------------------------------------------------------------------ odds and ladders
SHEET = """game,player,market,rung or line,price
CBJ@NJD,Timo Meier,Shots on Goal,3+,-150
CBJ@NJD,Timo Meier,shots,4+,+140
CBJ@NJD,Jack Hughes,Points,1+,-220
CBJ@NJD,Jake Allen,Saves,o24.5,-115
CBJ@NJD,Brenden Dillon,Hits,2+,-130
CBJ@NJD,New Jersey Devils,Puck Line,-1.5,+165
CBJ@NJD,,Total,o5.5,-110
CBJ@NJD,NJD,Moneyline,,-140
CBJ@NJD,Timo Meier,Anytime Goal Scorer,,+175
"""


def test_ladder_sheet_rungs_become_lines():
    good, bad = odds.read_csv(SHEET, "2026-11-23T20:00:00+00:00")
    assert bad == [] and len(good) == 9
    by = {(r["player_name"], r["market"], r["line"]): r for r in good}
    assert by[("Timo Meier", "sog", 2.5)]["side"] == "over" and by[("Timo Meier", "sog", 3.5)]["price"] == 140
    assert by[("Brenden Dillon", "hits", 1.5)]["book"] == "bet365"
    assert by[("NJD", "spread", -1.5)]["side"] == "team" and by[("NJD", "ml", 0.0)]["side"] == "team"
    assert by[("Timo Meier", "atg", 0.5)]["side"] == "yes" and by[("", "total", 5.5)]["side"] == "over"


def test_ladder_sheet_rejects_bad_rows_and_says_why():
    text = SHEET + "CBJ@NJD,Timo Meier,Shots on Goal,3+,-150\nCBJ@NJD,Jack Hughes,Faceoffs Won,8+,-110\n" \
                   "CBJ@NJD,Jack Hughes,Points,lots,-110\nCBJ@NJD,Jack Hughes,Points,2+,evens\nCBJ vs Narnia,Jack Hughes,Points,2+,+200\n" \
                   "CBJ@NJD,,Total,6+,-110\nCBJ@NJD,Toronto Maple Leafs,Puck Line,-1.5,+150\n"
    good, bad = odds.read_csv(text)
    assert len(good) == 9 and len(bad) == 7
    assert "duplicate" in bad[0] and "not one the NHL engine handles" in bad[1] and "neither a rung" in bad[2]
    assert "not a valid price" in bad[3] and "two NHL teams" in bad[4] and "milestone rung" in bad[5] and "puck line needs" in bad[6]
    assert odds.read_csv("player,price\nX,-110\n") == ([], ["sheet rejected: missing column(s) game, market, rung or line"])


def test_rows_resolve_to_scheduled_games_and_exact_players():
    good, _ = odds.read_csv(SHEET)
    sched = [{"game_id": 2026020378, "date_et": "2026-11-23", "home": "NJD", "away": "CBJ"}]
    index = ids.PlayerIndex([{"player_id": 1, "name": "Timo Meier", "team": "NJD"}, {"player_id": 2, "name": "Jack Hughes", "team": "NJD"},
                             {"player_id": 3, "name": "Jake Allen", "team": "NJD"}])
    out, bad = odds.resolve(good, sched, index, "2026-11-23")
    assert bad == ["Brenden Dillon: no exact player match"]
    assert len(out) == 8 and {r["game_id"] for r in out} == {2026020378}
    assert all("_home" not in r for r in out)
    out, bad = odds.resolve(good, sched, index, "2026-11-25")
    assert out == [] and len(bad) == 9 and "not on the schedule" in bad[0]


def test_api_rows_and_market_list():
    event = {"home_team": "New Jersey Devils", "away_team": "Columbus Blue Jackets", "commence_time": "2026-11-24T00:00:00Z",
             "bookmakers": [{"key": "bet365", "markets": [
                 {"key": "h2h", "outcomes": [{"name": "New Jersey Devils", "price": -140}, {"name": "Columbus Blue Jackets", "price": 120}]},
                 {"key": "spreads", "outcomes": [{"name": "New Jersey Devils", "price": 165, "point": -1.5}]},
                 {"key": "totals", "outcomes": [{"name": "Over", "price": -110, "point": 5.5}]},
                 {"key": "player_shots_on_goal_alternate", "outcomes": [{"name": "Over", "description": "Timo Meier", "price": -150, "point": 2.5}]},
                 {"key": "player_goal_scorer_anytime", "outcomes": [{"name": "Yes", "description": "Timo Meier", "price": 175}]},
                 {"key": "some_new_market", "outcomes": [{"name": "Over", "price": 100, "point": 1}]}]}]}
    rows = odds.rows_from_api(event, "2026-11-23T20:00:00+00:00")
    assert [(r["market"], r["player_name"], r["side"], r["line"]) for r in rows] == [
        ("ml", "NJD", "team", 0.0), ("ml", "CBJ", "team", 0.0), ("spread", "NJD", "team", -1.5), ("total", "", "over", 5.5),
        ("sog", "Timo Meier", "over", 2.5), ("atg", "Timo Meier", "yes", 0.5)]
    out, bad = odds.resolve(rows, [{"game_id": 7, "date_et": "2026-11-23", "home": "NJD", "away": "CBJ"}],
                            ids.PlayerIndex([{"player_id": 1, "name": "Timo Meier", "team": "NJD"}]))
    assert bad == [] and len(out) == 6 and out[4]["player_id"] == 1
    m = odds.all_api_markets()
    assert "player_total_saves_alternate" in m and "player_goal_scorer_anytime_alternate" not in m and "h2h" in m
    assert odds.API.endswith("/icehockey_nhl")


# ------------------------------------------------------------------ names
def test_names_match_exactly_or_not_at_all():
    assert ids.team("Montréal Canadiens") == "MTL" and ids.team("St. Louis Blues") == "STL" and ids.team("VEG") == "VGK"
    assert ids.team("Utah Hockey Club") == "UTA" and ids.team("Hartford Whalers") is None
    index = ids.PlayerIndex([{"player_id": 1, "name": "Sebastian Aho", "team": "CAR"}, {"player_id": 2, "name": "Sebastian Aho", "team": "PIT"},
                             {"player_id": 3, "name": "Tim Stützle", "team": "OTT"}])
    assert index.find("Sebastian Aho", "CAR") == 1 and index.find("Sebastian Aho", "PIT") == 2
    assert index.find("Sebastian Aho") is None and index.find("Tim Stutzle", "OTT") == 3 and index.find("T. Stutzle", "OTT") is None
    assert ("T. Stutzle", "OTT") in index.unmatched
    by_hand = ids.PlayerIndex([{"player_id": 4, "name": "Matt Savoie", "team": "EDM"}], {"Matthew Savoie": "Matt Savoie"})
    assert by_hand.find("Matthew Savoie", "EDM") == 4
