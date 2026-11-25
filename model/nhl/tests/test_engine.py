"""Gates, game sim, props, correlation, tickets, grading and the backtest's calibration counter."""
import json

import numpy as np
import pandas as pd
import pytest

from nhl import context, correlation, gates, grade, props, tickets
from nhl.backtest import Calib
from nhl.ingest import nhl_api
from nhl.sim import game_sim


@pytest.fixture(scope="module")
def world(league):
    from nhl import store
    from nhl.config import copy_config
    cfg = copy_config()
    cfg["sim"]["n_sims"] = 6000
    cfg["props"]["min_toi_sec"] = 60
    con = store.connect(":memory:")
    for name, df in league.items():
        store.write(con, name, df.astype(object).where(df.notna(), None).to_dict("records"))
    names = [{"player_id": int(p), "name": f"Skater {p}", "pos": "C", "team": "X", "last_date": "2026-10-01"}
             for p in league["player_game_strength"].player_id.unique()]
    store.write(con, "players", names)
    tables = context.Tables.load(con, cfg)
    ctx = context.build(tables, "2026-12-31T00:00:00+00:00", 2026, cfg)
    gk = {t: context.goalie_input(ctx, (i + 1) * 100 + 13, f"{t} Goalie") for i, t in enumerate(["NYR", "NJD", "BOS"]) if t in ("NYR", "BOS")}
    gk = {"NYR": {**context.goalie_input(ctx, 113, "NYR Goalie"), "player_id": 113}, "BOS": {**context.goalie_input(ctx, 313, "BOS Goalie"), "player_id": 313}}
    gctx = {**ctx, "goalies": gk, "crew_factor": 1.0, "spots": {}, "absent": {}}
    lam = game_sim.team_lambdas("NYR", "BOS", gctx, cfg)
    S = game_sim.simulate(lam, "NYR", "BOS", ctx["K"], cfg)
    rosters = {t: context.roster(ctx, t, cfg) for t in ("NYR", "BOS")}
    PS = props.simulate(S, rosters, gctx, cfg, game_id=1, goalies=gk)
    return {"cfg": cfg, "ctx": gctx, "lam": lam, "S": S, "PS": PS, "rosters": rosters, "tables": tables}


# ------------------------------------------------------------------ game sim
def test_expected_goals_are_itemised_and_home_ice_moves_them(world):
    lam = world["lam"]
    for t in ("NYR", "BOS"):
        assert lam[t]["lam"] == pytest.approx(sum(lam[t]["goals"].values()))
        assert [s["what"] for s in lam[t]["steps"][:3]] == ["5v5 xG", "power-play xG", "shorthanded xG"]
        assert lam[t]["ev_sec"] + lam[t]["pp_sec"] + lam[t]["pk_sec"] == pytest.approx(3600)
    assert lam["NYR"]["pp_sec"] == pytest.approx(lam["BOS"]["pk_sec"])
    assert any(s["what"] == "home ice" for s in lam["NYR"]["steps"]) and any(s["what"] == "road" for s in lam["BOS"]["steps"])


def test_a_better_opposing_goalie_lowers_expected_goals(world):
    ctx, cfg = world["ctx"], world["cfg"]
    hot = {**ctx, "goalies": {**ctx["goalies"], "BOS": {"gsax60": 0.5, "league_xga60": 3.0, "name": "Wall"}}}
    assert game_sim.team_lambdas("NYR", "BOS", hot, cfg)["NYR"]["lam"] < game_sim.team_lambdas("NYR", "BOS", {**ctx, "goalies": {}}, cfg)["NYR"]["lam"]
    b2b = {**ctx, "spots": {"NYR": {"b2b": 1, "rest_diff": -2, "tz_shift": 0}, "BOS": {"b2b": 0}}}
    assert game_sim.team_lambdas("NYR", "BOS", b2b, cfg)["NYR"]["lam"] < world["lam"]["NYR"]["lam"]


def test_simulated_scores_add_up(world):
    S = world["S"]
    h, a = S.home, S.away
    assert (S.final[h] != S.final[a]).all()                                   # every game has a winner
    tied = S.reg[h] == S.reg[a]
    assert (S.went_ot == tied).all() and (np.abs(S.margin())[tied] == 1).all()
    assert ((S.goals[h]["ot"] + S.goals[a]["ot"])[tied & ~S.went_so] == 1).all()
    assert (S.final[h] >= S.reg[h]).all() and (S.sog[h] >= S.goals[h]["ev"] + S.goals[h]["pp"] + S.goals[h]["sh"]).all()
    en = S.goals[h]["en"] + S.goals[a]["en"]
    assert 0 <= en.mean() < 0.8 and 0.1 < S.went_ot.mean() < 0.35   # the made-up league has no empty-net history


def test_market_probabilities_are_coherent(world):
    S = world["S"]
    p = game_sim.market_probs(S)
    h, a = S.home, S.away
    assert p[("ml", h, 0.0)] + p[("ml", a, 0.0)] == pytest.approx(1.0)
    assert p[("ml3", h, 0.0)] + p[("ml3", a, 0.0)] + p[("ml3", "draw", 0.0)] == pytest.approx(1.0)
    assert p[("spread", h, -1.5)] + p[("spread", a, 1.5)] == pytest.approx(1.0)
    assert p[("total", "over", 5.5)] + p[("total", "under", 5.5)] == pytest.approx(1.0)
    assert p[("total", "over", 4.5)] > p[("total", "over", 5.5)] > p[("total", "over", 6.5)]
    assert p[("spread", h, -1.5)] < p[("ml", h, 0.0)] < p[("spread", h, 1.5)]
    assert p[("ml", h, 0.0)] == pytest.approx(game_sim.hits_for(S, "ml", h, 0.0).mean())


def test_edge_is_model_minus_no_vig_implied(world):
    S, cfg = world["S"], world["cfg"]
    rows = [{"book": "dk", "market": "ml", "player_name": S.home, "side": "team", "line": 0.0, "price": -110.0},
            {"book": "dk", "market": "ml", "player_name": S.away, "side": "team", "line": 0.0, "price": -110.0},
            {"book": "dk", "market": "total", "player_name": "", "side": "over", "line": 5.5, "price": -120.0}]
    out = game_sim.price_markets(S, rows, cfg)
    assert len(out) == 2 and {o["market"] for o in out} == {"ml"}            # the one-sided total cannot have its vig removed
    for o in out:
        assert o["implied_prob"] == 0.5 and o["edge"] == pytest.approx(o["model_prob"] - 0.5, abs=1e-4)
    assert out[0]["edge"] >= out[1]["edge"]


def test_trailing_teams_shoot_more_and_leading_teams_block_more(world):
    K = world["ctx"]["K"]
    assert K["se_sog"][0] > K["se_sog"][4] or abs(K["se_sog"][0] - K["se_sog"][4]) < 0.2   # the made-up league has no score effects
    assert len(K["period_share"]) == 3 and sum(K["period_share"]) == pytest.approx(1.0)
    assert 0.9 < K["home_ice"] < 1.2 and 0 < K["ot_decided"] <= 1


# ------------------------------------------------------------------ props
def test_points_are_goals_plus_assists_from_the_same_games(world):
    S, PS = world["S"], world["PS"]
    d = PS.data
    assert (d["pts"] == d["goals"] + d["ast"]).all()
    home = (PS.players.team == S.home).to_numpy()
    for team, mask in ((S.home, home), (S.away, ~home)):
        team_goals = sum(S.goals[team][k] for k in ("ev", "pp", "sh", "en", "ot"))
        assert (d["goals"][:, mask].sum(1) == team_goals).all()                 # every simulated goal has exactly one scorer
        assert (d["ast"][:, mask].sum(1) <= 2 * team_goals).all()
    assert (d["sog"] >= d["goals"]).all()


def test_saves_are_shots_minus_goals_and_pulled_goalies_keep_two_periods(world):
    S, PS = world["S"], world["PS"]
    g = PS.goalies[S.home]
    against = S.goals[S.away]["ev"] + S.goals[S.away]["pp"] + S.goals[S.away]["sh"] + S.goals[S.away]["ot"]
    full = S.sog[S.away] - against
    assert (g["saves"][~g["pulled"]] == full[~g["pulled"]]).all() and (g["saves"] >= 0).all()
    assert (g["saves"][g["pulled"]] <= full[g["pulled"]]).all()
    assert ((-S.lead_p2)[g["pulled"]] >= world["cfg"]["props"]["pull_deficit"]).all()


def test_shots_and_saves_move_together(world):
    S, PS = world["S"], world["PS"]
    home = (PS.players.team == S.home).to_numpy()
    home_shots = PS.data["sog"][:, home].sum(1)
    assert correlation.correlation(home_shots, PS.goalies[S.away]["saves"]) > 0.15
    assert abs(correlation.correlation(home_shots, PS.goalies[S.home]["saves"])) < 0.15


def test_blowouts_trim_the_top_line(world):
    S, cfg = world["S"], world["cfg"]
    P = world["rosters"][S.home]
    f = props.script_toi(S, S.home, P, cfg)
    top = P.top_line.to_numpy()
    assert top.sum() == cfg["props"]["top_line_forwards"] + cfg["props"]["top_pair_defence"]
    blow = S.lead_p2 >= cfg["sim"]["blowout_margin"]
    assert (f[np.ix_(blow, top)] < 1).all() and (f[:, ~top] == 1).all() and (f[np.ix_(S.lead_p2 < 0, top)] > 1).all()


# ------------------------------------------------------------------ correlation
def test_joint_is_counted_not_multiplied():
    rng = np.random.default_rng(0)
    a = rng.random(20000) < 0.7
    legs = [{"hits": a, "p": 0.7, "label": "a", "active": None}, {"hits": a.copy(), "p": 0.7, "label": "b", "active": None}]
    assert correlation.joint(legs) == pytest.approx(0.7, abs=0.01)             # the same event twice is still 70%, not 49%
    assert correlation.lift(legs) == pytest.approx(1 / 0.7, abs=0.03)
    b = rng.random(20000) < 0.7
    assert correlation.joint([legs[0], {"hits": b, "p": 0.7, "label": "c", "active": None}]) == pytest.approx(0.49, abs=0.015)
    assert correlation.pair_table(legs)[0]["corr"] == 1.0


# ------------------------------------------------------------------ gates
GAME = {"home": "NYR", "away": "BOS", "date_et": "2026-12-30", "start_utc": "2026-12-31T00:00:00Z"}


def goalie_row(team, status, name="G"):
    return {"team": team, "date_et": "2026-12-30", "status": status, "goalie": name, "player_id": 1}


def line_row(team, pid, unit="f1", when="2026-12-30T17:00:00Z", **kw):
    return {"team": team, "player_id": pid, "unit": unit, "category": "oi" if unit == "ir" else "ev", "source_time": when, "injury": None, "gtd": 0, **kw}


def test_goalie_gate_blocks_scoring_legs_but_not_shots(cfg):
    g = gates.game_gates(GAME, [goalie_row("NYR", "Confirmed"), goalie_row("BOS", "Likely")], [line_row("NYR", 100), line_row("BOS", 300)], cfg)
    assert not g["goalies_ok"] and g["goalies"]["NYR"]["ok"] and not g["goalies"]["BOS"]["ok"]
    assert any("BOS starting goalie is likely" in n for n in g["notes"])
    leg = lambda m: {"market": m, "team": "NYR", "player_id": 100, "rung_verified": False}
    assert gates.leg_passes(leg("sog"), g, {}, cfg)[0] and gates.leg_passes(leg("hits"), g, {}, cfg)[0]
    for m in ("pts", "ast", "goals", "saves", "total"):
        assert gates.leg_passes(leg(m), g, {}, cfg) == (False, "starting goalie not confirmed")


def test_lines_gate_injury_gate_and_ladder_gate(cfg):
    rows = [line_row("NYR", 100), line_row("NYR", 101, gtd=1), line_row("NYR", 102, unit="ir"), line_row("BOS", 300, when="2026-12-27T17:00:00Z")]
    g = gates.game_gates(GAME, [goalie_row("NYR", "Confirmed"), goalie_row("BOS", "Confirmed")], rows, cfg)
    assert g["goalies_ok"] and g["lines"]["NYR"]["ok"] and not g["lines"]["BOS"]["ok"]
    flags = gates.lineup_flags(rows)
    assert flags == {101: "game-time decision", 102: "injured reserve", 100: "line-mate is a game-time decision"}
    leg = lambda team, pid, m="sog", v=False: {"market": m, "team": team, "player_id": pid, "rung_verified": v}
    assert gates.leg_passes(leg("BOS", 300), g, flags, cfg) == (False, "lines not confirmed")
    assert gates.leg_passes(leg("NYR", 101), g, flags, cfg) == (False, "game-time decision")
    assert gates.leg_passes(leg("NYR", 105), g, flags, cfg)[0]
    assert gates.leg_passes(leg("BOS", 313, "saves"), g, flags, cfg)[0]          # a confirmed starter does not wait on skater lines
    cfg["gates"]["require_book_rung"] = True
    assert gates.leg_passes(leg("NYR", 105), g, flags, cfg) == (False, "rung not on the book's ladder")
    assert gates.leg_passes(leg("NYR", 105, v=True), g, flags, cfg)[0]


def test_a_missing_goalie_fails_the_gate(cfg):
    g = gates.game_gates(GAME, [], [], cfg)
    assert not g["goalies_ok"] and g["goalies"]["NYR"]["status"] == "not listed" and not g["lines"]["NYR"]["ok"]


# ------------------------------------------------------------------ tickets
def open_gates():
    ok = {"ok": True}
    return {"goalies_ok": True, "goalies": {"NYR": ok, "BOS": ok}, "lines": {"NYR": ok, "BOS": ok}, "notes": []}


def test_tickets_follow_the_rules(world):
    S, PS, cfg = world["S"], world["PS"], world["cfg"]
    summ = game_sim.summary(S, cfg)
    out = tickets.build(PS, S, open_gates(), {}, [], {**summ, "blowout_flag": False}, [], cfg)
    kinds = [t["kind"] for t in out["tickets"]]
    assert kinds[:2] == ["sgp4", "sgp6"] and "atg" in kinds and "closer" not in kinds
    for t in out["tickets"]:
        assert t["miss"] == pytest.approx(1 - t["chance"], abs=1e-4)
        if t["kind"].startswith("sgp"):
            assert len(t["legs"]) == int(t["kind"][3:])
            assert all(l["prob"] >= cfg["tickets"]["floor_prob"] for l in t["legs"])
            assert all(l["market"] != "goals" for l in t["legs"])                # scorers never sit in a props SGP
            assert len({l["player_id"] for l in t["legs"]}) == len(t["legs"])
            assert sum(l["market"] == "saves" for l in t["legs"]) <= 1
            assert not t["rungs_verified"] and not t["priced"]                   # no book ladder in hand: marked as such
        if t["kind"] == "atg":
            assert all(l["market"] == "goals" and "anytime goal scorer" in l["label"] for l in t["legs"])
    pool = {(l["market"], l["player_id"]): l for l in out["pool"]}
    assert len(pool) == len(out["pool"])                                         # one floor rung per player and market


def test_floor_rung_is_the_highest_rung_that_clears_the_floor(cfg):
    mk = lambda rung, p: {"market": "sog", "player_id": 1, "rung": rung, "p": p}
    got = tickets.floor_rungs([mk(2, 0.9), mk(3, 0.74), mk(4, 0.5), {"market": "goals", "player_id": 1, "rung": 1, "p": 0.9}], cfg)
    assert [(l["market"], l["rung"]) for l in got] == [("sog", 3)]


def test_blowout_guard_and_gates_remove_legs_with_a_reason(world):
    S, PS, cfg = world["S"], world["PS"], world["cfg"]
    summ = {**game_sim.summary(S, cfg), "blowout_flag": True, "favourite": S.home}
    legs, removed = tickets.build_legs(PS, S, open_gates(), {}, [], summ, cfg)
    reasons = {r["reason"] for r in removed}
    assert "blowout guard: saves on the goalie facing the favourite" in reasons
    assert "blowout guard: late ice time on the favourite's top line" in reasons
    assert not any(l["market"] == "saves" and l["team"] == S.away for l in legs)
    closed = {**open_gates(), "goalies_ok": False}
    legs, removed = tickets.build_legs(PS, S, closed, {}, [], {**summ, "blowout_flag": False}, cfg)
    assert {l["market"] for l in legs} <= {"sog", "hits", "blk"}


def test_book_rungs_replace_the_paper_ladder_and_a_closer_needs_an_edge(world):
    S, PS, cfg = world["S"], world["PS"], world["cfg"]
    pid = int(PS.players.player_id.iloc[0])
    rows = [{"market": "sog", "player_id": pid, "side": "over", "line": 0.5, "price": -400.0}]
    legs, _ = tickets.build_legs(PS, S, open_gates(), {}, rows, {**game_sim.summary(S, cfg), "blowout_flag": False}, cfg)
    mine = [l for l in legs if l["player_id"] == pid and l["market"] == "sog"]
    assert [(l["rung"], l["price"], l["rung_verified"]) for l in mine] == [(1, -400.0, True)]
    line = {"book": "dk", "market": "ml", "side": S.home, "line": 0.0, "price": 150.0, "model_prob": 0.6, "implied_prob": 0.4, "edge": 0.2, "tier": "strong"}
    out = tickets.build(PS, S, open_gates(), {}, [], {**game_sim.summary(S, cfg), "blowout_flag": False}, [line], cfg)
    closer = next(t for t in out["tickets"] if t["kind"] == "closer")
    assert closer["legs"][0]["label"] == f"{S.home} moneyline" and 0 < closer["kelly_stake"] <= cfg["tickets"]["kelly_cap"]
    small = tickets.build(PS, S, open_gates(), {}, [], {**game_sim.summary(S, cfg), "blowout_flag": False}, [{**line, "edge": 0.01}], cfg)
    assert not any(t["kind"] == "closer" for t in small["tickets"])


def test_same_line_points_rule(cfg):
    leg = lambda pid, slot, m="pts": {"market": m, "team": "NYR", "player_id": pid, "line_slot": slot, "p": 0.8}
    assert tickets.nhl_allowed([leg(1, "f1"), leg(2, "f1")], cfg)
    assert not tickets.nhl_allowed([leg(1, "f1"), leg(2, "f1"), leg(3, "f1", "ast")], cfg)
    assert tickets.nhl_allowed([leg(1, "f1"), leg(2, "f1"), leg(3, "f2")], cfg)
    assert not tickets.nhl_allowed([{**leg(1, "f1"), "p": 0.6}, {**leg(2, "f2"), "p": 0.6}], cfg)   # at most one leg under 65%


# ------------------------------------------------------------------ grading
def test_grading_legs_tickets_and_void(db, league):
    g = league["games"].iloc[-1]
    a = grade.actuals(db, int(g.game_id))
    pid = int(a["skaters"].sog.idxmax())
    shots = int(a["skaters"].at[pid, "sog"])
    gk = int(a["goalies"].index[0])
    legs = [{"label": "x", "market": "sog", "player_id": pid, "rung": shots, "prob": 0.7},
            {"label": "y", "market": "saves", "player_id": gk, "rung": int(a["goalies"].at[gk, "saves"]) + 1, "prob": 0.7},
            {"label": "z", "market": "hits", "player_id": 999999, "rung": 1, "prob": 0.7},
            {"label": "w", "market": "ml", "side": g.home, "line": 0.0, "prob": 0.5},
            {"label": "t", "market": "total", "side": "over", "line": g.home_goals + g.away_goals - 0.5, "prob": 0.5}]
    t = grade.grade_ticket({"id": "2026-10-23-A-B-sgp4", "kind": "sgp4", "chance": 0.3, "legs": legs}, a)
    assert [l["result"] for l in t["legs"]] == ["won", "lost", "void", "won" if g.home_goals > g.away_goals else "lost", "won"]
    assert t["result"] == "lost" and t["legs_counted"] == 4 and t["graded"]
    won = grade.grade_ticket({"id": "x", "kind": "sgp4", "chance": 0.3, "legs": [legs[0], legs[2]]}, a)
    assert won["result"] == "won" and won["legs_counted"] == 1
    assert grade.grade_ticket({"id": "x", "kind": "atg", "chance": 0.3, "legs": [legs[2]]}, a)["result"] == "void"
    assert grade.actuals(db, 1) is None


def test_report_card_compares_hit_rate_with_the_models_chance(tmp_path, monkeypatch):
    monkeypatch.setattr(grade, "REPORT", tmp_path / "card.json")
    led = {"tickets": [{"id": "2026-11-24-A-B-sgp4", "kind": "sgp4", "chance": 0.4, "graded": True, "result": "lost",
                        "legs": [{"market": "sog", "prob": 0.8, "result": "won"}, {"market": "sog", "prob": 0.7, "result": "lost"},
                                 {"market": "hits", "prob": 0.9, "result": "void"}]},
                       {"id": "2026-11-24-A-B-atg", "kind": "atg", "chance": 0.1, "graded": False, "legs": []}]}
    from datetime import date
    card = grade.report_card(led, date(2026, 11, 25))
    assert card["all_time"] == [{"market": "sog", "legs": 2, "won": 1, "hit_rate": 0.5, "model_avg": 0.75}]
    assert card["tickets"] == {"sgp4": {"tickets": 1, "won": 0, "void": 0, "model_avg": 0.4}}
    assert "not posted on the site" in card["note"] and json.loads((tmp_path / "card.json").read_text())["week"] == card["all_time"]


# ------------------------------------------------------------------ partner odds, backtest counter
def test_partner_game_lines_become_odds_rows():
    doc = {"bettingPartner": {"name": "DraftKings"}, "games": [{"gameId": 7, "homeTeam": {"abbrev": "EDM", "odds": [
        {"description": "PUCK_LINE", "value": -258.0, "qualifier": "+1.5"}, {"description": "OVER_UNDER", "value": -122.0, "qualifier": "O6.5"},
        {"description": "MONEY_LINE_2_WAY", "value": 100.0, "qualifier": ""}, {"description": "MONEY_LINE_3_WAY", "value": 330.0, "qualifier": "Draw"},
        {"description": "MONEY_LINE_3_WAY", "value": 135.0, "qualifier": ""}]}, "awayTeam": {"abbrev": "VGK", "odds": [
        {"description": "PUCK_LINE", "value": 210.0, "qualifier": "-1.5"}, {"description": "OVER_UNDER", "value": 102.0, "qualifier": "U6.5"},
        {"description": "MONEY_LINE_2_WAY", "value": -120.0, "qualifier": ""}, {"description": "MONEY_LINE_3_WAY", "value": 330.0, "qualifier": "Draw"}]}}]}
    rows = nhl_api.parse_partner_odds(doc, "2026-11-25T00:00:00+00:00")
    got = {(r["market"], r["player_name"], r["side"], r["line"]): r["price"] for r in rows}
    assert got == {("spread", "EDM", "team", 1.5): -258.0, ("total", "", "over", 6.5): -122.0, ("ml", "EDM", "team", 0.0): 100.0,
                   ("ml3", "Draw", "draw", 0.0): 330.0, ("ml3", "EDM", "team", 0.0): 135.0, ("spread", "VGK", "team", -1.5): 210.0,
                   ("total", "", "under", 6.5): 102.0, ("ml", "VGK", "team", 0.0): -120.0}
    assert {r["book"] for r in rows} == {"draftkings"} and {r["game_id"] for r in rows} == {7}


def test_calibration_counter():
    c = Calib()
    c.add(np.full(100, 0.72), np.r_[np.ones(72), np.zeros(28)])
    r = c.report()
    assert r["n"] == 100 and r["hit_rate"] == 0.72 and r["calibration_gap"] == pytest.approx(0.0, abs=1e-9)
    assert r["buckets"] == [{"bucket": "70-75%", "n": 100, "predicted": 0.72, "actual": 0.72}]
    c.add(np.full(100, 0.9), np.zeros(100))
    assert c.report()["calibration_gap"] == pytest.approx(0.45)
    assert Calib().report() == {"n": 0}
