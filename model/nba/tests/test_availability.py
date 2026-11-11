import pandas as pd

from nba import availability as av
from nba.config import CONFIG
from nba.ids import TEAMS
from nba.store import PointInTime
from nba.tests.conftest import make_league


def setup():
    f = make_league(seed=7)
    g = f["games"].sort_values("tip_utc").iloc[-1]
    hist = {k: (v[v.game_id != g.game_id] if "game_id" in v else v) for k, v in f.items()}
    game = {"game_id": g.game_id, "date_et": g.date_et, "home_id": g.home_id, "away_id": g.away_id,
            "home_name": TEAMS[g.home][0], "away_name": TEAMS[g.away][0]}
    star = hist["player_games"][(hist["player_games"].team_id == g.home_id)].sort_values("min").player_id.iloc[-1]
    return hist, game, g, star


def report(game, g, rows, when="2030-01-01T17:00:00+00:00"):
    base = [{"report_utc": when, "game_date": game["date_et"], "matchup": "A@B", "team": game["away_name"], "player_name": "",
             "status": "x", "reason": None, "player_id": None}]
    base[0]["status"] = "Available"; base[0]["player_name"] = "nobody"
    return pd.DataFrame(base + [{"report_utc": when, "game_date": game["date_et"], "matchup": "A@B", "team": game["home_name"],
                                 "player_name": "p", "status": s, "reason": r, "player_id": pid} for pid, s, r in rows])


def test_statuses_and_eligibility():
    hist, game, g, star = setup()
    other = hist["player_games"][(hist["player_games"].team_id == g.home_id) & (hist["player_games"].player_id != star)].player_id.iloc[0]
    hist["injury_reports"] = report(game, g, [(star, "Questionable", "Injury/Illness - Left Ankle; Sprain"), (other, "Probable", "Rest")])
    d = av.gate(PointInTime("2031-01-01T00:00:00+00:00", frames=hist), game).set_index("player_id")
    assert d.loc[star, "status"] == "questionable" and d.loc[star, "ticket_eligible"] == 0 and d.loc[star, "projected"] == 1
    assert d.loc[other, "status"] == "questionable"                       # probable is not confirmed
    rest = d[(d.team_id == g.home_id) & ~d.index.isin([star, other])]
    assert (rest.status == "confirmed_in").all() and (rest.ticket_eligible == 1).all()


def test_team_that_has_not_filed_is_unknown():
    hist, game, g, star = setup()
    hist["injury_reports"] = pd.DataFrame([{"report_utc": "2030-01-01T17:00:00+00:00", "game_date": game["date_et"], "matchup": "A@B",
                                            "team": game["home_name"], "player_name": "", "status": "NOT YET SUBMITTED",
                                            "reason": None, "player_id": None}])
    d = av.gate(PointInTime("2031-01-01T00:00:00+00:00", frames=hist), game)
    assert (d[d.team_id == g.home_id].status == "unknown").all() and d[d.team_id == g.home_id].ticket_eligible.sum() == 0


def test_questionable_to_out_removes_legs_and_recalculates_teammates():
    hist, game, g, star = setup()
    pit = PointInTime("2031-01-01T00:00:00+00:00", frames=hist)
    hist["injury_reports"] = report(game, g, [(star, "Questionable", "knee")])
    before = av.gate(pit, game)
    hist["injury_reports"] = report(game, g, [(star, "Out", "knee")], when="2030-01-01T18:00:00+00:00")
    after = av.gate(PointInTime("2031-01-01T00:00:00+00:00", frames=hist), game)
    ch = av.changes(before, after)
    assert len(ch) == 1 and ch[0]["player_id"] == star and ch[0]["from"] == "questionable" and ch[0]["to"] == "out"
    assert ch[0]["remove_legs"] is True
    mates = set(after[(after.team_id == g.home_id) & (after.player_id != star) & (after.projected == 1)].player_id)
    assert set(ch[0]["recalculate"]) == mates and len(mates) >= 5 and star not in mates
    legs = [{"player_id": star, "market": "pts"}, {"player_id": next(iter(mates)), "market": "reb"}, {"player_id": None, "market": "total"}]
    keep, gone = av.apply_to_legs(legs, after)
    assert [l["player_id"] for l in gone] == [star] and len(keep) == 2


def test_teammates_are_recalculated_when_a_star_goes_out():
    """End to end through the models: mark the star out and his teammates' minutes go up."""
    from nba.pipeline import Pipeline
    f = make_league(seed=7)
    g = f["games"].sort_values("tip_utc").iloc[-1]
    star = f["player_games"][(f["player_games"].team_id == g.home_id)].groupby("player_id")["min"].mean().idxmax()
    res = {}
    for label, out in (("in", {}), ("out", {g.game_id: {star}})):
        p = Pipeline(f, live_status={"out": out, "filed": {g.game_id: {g.home_id, g.away_id}}}, cfg=CONFIG)
        m = p.fit(2027)
        _, _, _, rows = p.game_inputs(g.game_id, m)
        res[label] = rows[rows.team_id == g.home_id].set_index("player_id").e_min
    assert star in res["in"].index and star not in res["out"].index
    common = res["out"].index
    assert res["out"].sum() > res["in"].reindex(common).sum() + 5


def test_return_from_absence_and_restriction_notes():
    assert av.restriction_from_text("He will be on a minutes restriction of 24 minutes tonight") == 24.0
    assert av.restriction_from_text("Expected to be limited; minutes cap in place") is True
    assert av.restriction_from_text("Out with a sprained ankle") is None
