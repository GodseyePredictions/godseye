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
    from nhl.tests.conftest import paper_config
    cfg = paper_config()
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
    assert out["multi_part"] and len(out["multi_part"]["legs"]) == cfg["tickets"]["multi"]["legs_per_game"]
    for t in out["tickets"]:
        assert t["miss"] == pytest.approx(1 - t["chance"], abs=1e-4)
        if t["kind"].startswith("sgp"):
            assert len(t["legs"]) == int(t["kind"][3:])
            assert all(l["prob"] >= cfg["tickets"]["floor_prob"] for l in t["legs"])
            players = [l["player_id"] for l in t["legs"] if l["player_id"] is not None]
            assert len(set(players)) == len(players)                             # one leg per player
            assert sum(l["market"] == "saves" for l in t["legs"]) <= 1 and sum(l["market"] == "hits" for l in t["legs"]) <= 3
            assert sum(l["market"] in ("ml", "spread") for l in t["legs"]) <= 1 and sum(l["market"] == "total" for l in t["legs"]) <= 1
            assert not t["rungs_verified"] and not t["priced"]                   # no book ladder in hand: marked as such
        if t["kind"] == "atg":
            assert all(l["market"] == "goals" and "anytime goal scorer" in l["label"] for l in t["legs"])
    pool = {(l["market"], l["player_id"], l["side"]): l for l in out["pool"]}
    assert len(pool) == len(out["pool"])                                         # one floor rung per player and market, one line per side


def test_floor_rung_is_the_highest_rung_that_clears_the_floor(cfg):
    mk = lambda rung, p: {"market": "sog", "player_id": 1, "rung": rung, "p": p}
    got = tickets.floor_rungs([mk(2, 0.9), mk(3, 0.74), mk(4, 0.5), {"market": "goals", "player_id": 1, "rung": 1, "p": 0.4}], cfg)
    assert [(l["market"], l["rung"]) for l in got] == [("sog", 3)]                # a 40% scorer is not a floor rung
    gl = lambda line, p, v: {"kind": "game", "market": "total", "side": "over", "line": line, "p": p, "rung_verified": v}
    assert tickets.floor_rungs([gl(4.5, 0.82, False), gl(5.5, 0.71, False)], cfg)[0]["line"] == 5.5      # the tightest line that clears
    assert tickets.floor_rungs([gl(4.5, 0.82, True), gl(5.5, 0.71, False)], cfg)[0]["line"] == 4.5       # the book's own line first


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
    assert {l["market"] for l in legs} <= {"sog", "hits", "blk"}                 # no sides, totals, saves or scoring props


def test_book_rungs_replace_the_paper_ladder_and_the_closer_ignores_price(world):
    S, PS, cfg = world["S"], world["PS"], world["cfg"]
    pid = int(PS.players.player_id.iloc[0])
    rows = [{"market": "sog", "player_id": pid, "side": "over", "line": 0.5, "price": -400.0}]
    legs, _ = tickets.build_legs(PS, S, open_gates(), {}, rows, {**game_sim.summary(S, cfg), "blowout_flag": False}, cfg)
    mine = [l for l in legs if l["player_id"] == pid and l["market"] == "sog"]
    assert [(l["rung"], l["price"], l["rung_verified"]) for l in mine] == [(1, -400.0, True)]
    summ = {**game_sim.summary(S, cfg), "blowout_flag": False}
    dog = S.away if summ["favourite"] == S.home else S.home
    book = [{"market": "spread", "player_name": dog, "side": "team", "line": 1.5, "price": p, "book": "fd"} for p in (-250.0,)]
    p_dog = float(game_sim.hits_for(S, "spread", dog, 1.5).mean())
    for price in (-250.0, +300.0):                                                 # the price changes nothing about the pick
        out = tickets.build(PS, S, open_gates(), {}, [{**book[0], "price": price}], summ, [], cfg)
        closer = [t for t in out["tickets"] if t["kind"] == "closer"]
        if p_dog >= cfg["tickets"]["closer_min_prob"]:
            assert closer and closer[0]["legs"][0]["label"] == f"{dog} +1.5 puck line"
        else:
            assert not closer
    out = tickets.build(PS, S, open_gates(), {}, [], summ, [], cfg)
    assert not any(t["kind"] == "closer" for t in out["tickets"])                  # no listed line, no closer


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


def test_saves_legs_need_the_higher_floor_and_totals_are_not_closers(world):
    cfg = world["cfg"]
    mk = lambda m, p: {"market": m, "player_id": 1, "rung": 20, "p": p}
    assert tickets.floor_rungs([mk("saves", 0.80)], cfg) == []                   # 80% clears 70% but not the saves floor
    assert len(tickets.floor_rungs([mk("saves", 0.86), mk("sog", 0.71)], cfg)) == 2
    S, PS = world["S"], world["PS"]
    rows = [{"market": "total", "player_name": "", "side": "under", "line": 9.5, "price": -900.0, "book": "fd"}]
    out = tickets.build(PS, S, open_gates(), {}, rows, {**game_sim.summary(S, cfg), "blowout_flag": False}, [], cfg)
    assert not any(t["kind"] == "closer" for t in out["tickets"])                  # totals are never closers


def test_started_games_keep_their_locked_slips(tmp_path, monkeypatch, db, cfg):
    from nhl import slate
    monkeypatch.setattr(slate, "SLATE", tmp_path / "s.json"); monkeypatch.setattr(slate, "LEDGER", tmp_path / "l.json")
    monkeypatch.setattr(slate, "SITE", tmp_path / "site.json"); monkeypatch.setattr(slate, "OUT", tmp_path)
    g = db.execute("SELECT game_id, date_et FROM schedule ORDER BY start_utc DESC LIMIT 1").fetchone()
    kept = {"game_id": g[0], "label": "kept", "home": "A", "away": "B", "start_utc": "x", "venue": None, "paper": True, "notes": [],
            "gates": {"goalies": {}, "lines": {}}, "referees": {"referees": []}, "sim": {}, "expected": {}, "fair": {}, "game_lines": [],
            "goalies": {}, "tickets": [], "removed_count": 0, "projections": []}
    (tmp_path / "s.json").write_text(json.dumps({"date": g[1], "games": [kept]}))
    cfg["sim"]["n_sims"] = 500
    out = slate.run(db, cfg, g[1], as_of="2027-01-01T00:00:00+00:00")
    assert [x["label"] for x in out["games"] if x["game_id"] == g[0]] == ["kept"]
    assert json.loads((tmp_path / "site.json").read_text())["games"][0]["label"] == "kept"


def test_slip_rules_for_game_lines_and_saves(cfg):
    leg = lambda m, team, **k: {"market": m, "team": team, "player_id": k.get("pid"), "p": 0.8, "line_slot": None}
    assert tickets.nhl_allowed([leg("ml", "NYR"), leg("total", None)], cfg)
    assert not tickets.nhl_allowed([leg("ml", "NYR"), leg("spread", "NYR")], cfg)                  # one side only
    assert not tickets.nhl_allowed([leg("total", None), leg("total", None)], cfg)
    assert not tickets.nhl_allowed([leg("saves", "NYR", pid=1), leg("ml", "NYR")], cfg)            # a goalie's saves over and his team to win
    assert tickets.nhl_allowed([leg("saves", "NYR", pid=1), leg("ml", "BOS")], cfg)


def test_multi_game_slips_and_the_lotto(world):
    S, PS, cfg = world["S"], world["PS"], world["cfg"]
    games = []
    for i, label in enumerate(("A @ B", "C @ D", "E @ F", "G @ H")):
        out = tickets.build(PS, S, open_gates(), {}, [], {**game_sim.summary(S, cfg), "blowout_flag": False}, [], cfg)
        games.append({"game_id": i, "label": label, "legs": out["legs"], "multi_part": out["multi_part"], "gates_ok": i != 3})
    multis = tickets.multi_game(games, cfg)
    assert [t["kind"] for t in multis] == ["multi2", "multi3"]
    two = multis[0]
    assert len(two["legs"]) == 2 * cfg["tickets"]["multi"]["legs_per_game"] and 3 not in two["game_ids"]   # a game that failed a gate is not used
    part = games[0]["multi_part"]["joint"]
    assert two["chance"] == pytest.approx(part * part, abs=1e-4)                                   # counted inside a game, multiplied across games
    assert {l["game"] for l in two["legs"]} == set(two["games"])
    lot = tickets.lotto(games, cfg)
    if lot:                                                                                        # the made-up league may not hold enough longshots
        m = cfg["tickets"]["multi"]
        assert 1 / lot["chance"] >= m["lotto_min_decimal"] and len(set(lot["game_ids"])) >= m["lotto_min_games"]
        assert all(m["lotto_leg_prob"][0] <= l["prob"] <= m["lotto_leg_prob"][1] for l in lot["legs"])
    assert tickets.lotto(games[:1], cfg) is None and tickets.multi_game(games[:1], cfg) == []


def test_preview_notes_the_gates_but_keeps_the_legs(world, cfg):
    g = gates.game_gates(GAME, [goalie_row("NYR", "Unconfirmed"), goalie_row("BOS", "Unconfirmed")], [], cfg)
    leg = {"market": "pts", "team": "NYR", "player_id": 100, "rung_verified": False}
    assert gates.leg_passes(leg, g, {}, cfg) == (False, "starting goalie not confirmed")
    cfg["gates"]["preview"] = True
    assert gates.leg_passes(leg, g, {}, cfg)[0] and gates.leg_passes({**leg, "market": "ml", "player_id": None}, g, {}, cfg)[0]
    assert gates.leg_passes(leg, g, {100: "injured reserve"}, cfg) == (False, "injured reserve")   # injuries still remove a leg


def test_multi_game_grading_and_cashed_slips(db, league, tmp_path, monkeypatch):
    g1, g2 = league["games"].iloc[-1], league["games"].iloc[-2]
    acts = {int(g.game_id): grade.actuals(db, int(g.game_id)) for g in (g1, g2)}
    legs = []
    for gid, a in acts.items():
        pid = int(a["skaters"].sog.idxmax())
        legs.append({"label": f"x{gid}", "market": "sog", "player_id": pid, "rung": 1, "prob": 0.8, "game_id": gid})
    t = grade.grade_ticket({"id": "2026-10-23-multi2", "kind": "multi2", "title": "2-game slip", "chance": 0.4, "fair_price": 150,
                            "games": ["a", "b"], "game_ids": list(acts), "made_at": "t", "legs": legs}, acts)
    assert t["result"] == "won" and t["legs_won"] == 2 and ";" in t["final"]
    monkeypatch.setattr(grade, "CASHED", tmp_path / "c.json")
    lost = {**t, "id": "2026-10-23-lotto", "result": "lost"}
    late = {**t, "id": "2026-10-23-late", "made_after_start": True}
    c = grade.cashed({"tickets": [t, lost, late, {"id": "x", "graded": False}]})
    assert [s["id"] for s in c["slips"]] == ["2026-10-23-multi2"]                                  # winners only, and never one made after puck drop
    assert "losing slips are not shown" in c["note"] and c["slips"][0]["game"] == "a + b"


def test_every_slip_leg_carries_its_reasons(world):
    from nhl import explain
    S, PS, cfg = world["S"], world["PS"], world["cfg"]
    summ = {**game_sim.summary(S, cfg), "blowout_flag": False}
    recent = explain.recent_form(world["tables"], "2026-12-31T00:00:00+00:00")
    ex = explain.Explainer(PS, S, world["lam"], world["ctx"], recent, [], summ, S.n)
    out = tickets.build(PS, S, open_gates(), {}, [], summ, [], cfg, explain=ex)
    for t in out["tickets"]:
        for l in t["legs"]:
            assert len(l["why"]) >= 3 and l["why"][-1].startswith("Hit in ")
    pid = int(PS.players.player_id.iloc[0])
    assert len(recent[pid]["sog"]) == 10 and "saves" in recent[113]
    why = ex({"kind": "prop", "market": "sog", "player_id": pid, "rung": 1, "p": 0.9, "mean": 2.0, "rung_verified": False})
    assert any(w.startswith("Reached 1+ in") for w in why) and any("per 60" in w for w in why)
    side = ex({"kind": "game", "market": "spread", "side": S.home, "line": 1.5, "p": 0.8, "rung_verified": False})
    assert any("win by two or more" in w for w in side) and side[0].startswith("Simulated score")


def test_early_card_is_logged_and_a_plain_preview_is_not(tmp_path, monkeypatch, db, cfg):
    from nhl import slate
    for name in ("SLATE", "LEDGER", "SITE", "CASHED"):
        monkeypatch.setattr(slate, name, tmp_path / f"{name}.json")
    monkeypatch.setattr(slate, "OUT", tmp_path)
    g = db.execute("SELECT date_et, start_utc FROM schedule ORDER BY start_utc DESC LIMIT 1").fetchone()
    cfg["sim"]["n_sims"] = 400
    cfg["props"]["min_toi_sec"] = 60
    cfg["gates"]["preview"] = True
    out = slate.run(db, cfg, g[0], as_of="2026-10-23T12:00:00+00:00")
    assert out["preview"] and not out["early"] and not (tmp_path / "LEDGER.json").exists()
    cfg["gates"]["issue_early"] = True
    out = slate.run(db, cfg, g[0], as_of="2026-10-23T12:00:00+00:00")
    led = json.loads((tmp_path / "LEDGER.json").read_text())["tickets"]
    assert out["early"] and not out["preview"] and led and all(t["early"] and not t["graded"] for t in led)
    assert json.loads((tmp_path / "SITE.json").read_text())["early"] is True


def test_gated_run_reissues_unconfirmed_games_as_early(tmp_path, monkeypatch, db, cfg):
    from nhl import slate
    for name in ("SLATE", "LEDGER", "SITE", "CASHED"):
        monkeypatch.setattr(slate, name, tmp_path / f"{name}.json")
    monkeypatch.setattr(slate, "OUT", tmp_path)
    g = db.execute("SELECT date_et FROM schedule ORDER BY start_utc DESC LIMIT 1").fetchone()
    cfg["sim"]["n_sims"] = 400
    cfg["props"]["min_toi_sec"] = 60
    cfg["gates"]["early_fallback"] = False
    strict = slate.run(db, cfg, g[0], as_of="2026-10-23T12:00:00+00:00")         # no goalies or lines in the store: nothing confirmed
    assert all(not x.get("early") for x in strict["games"]) and not strict["mixed"]
    assert all({l["market"] for t in x["tickets"] for l in t["legs"]} <= {"goals"} for x in strict["games"])
    cfg["gates"]["early_fallback"] = True
    out = slate.run(db, cfg, g[0], as_of="2026-10-23T12:00:00+00:00")
    assert out["mixed"] and all(x["early"] for x in out["games"])
    assert any(len(t["legs"]) >= 4 for x in out["games"] for t in x["tickets"])
    led = json.loads((tmp_path / "LEDGER.json").read_text())["tickets"]
    assert led and all(t["early"] for t in led if t["kind"].startswith("sgp"))
    site = json.loads((tmp_path / "SITE.json").read_text())
    assert site["mixed"] and all(x["early"] for x in site["games"])
    assert not any(t["kind"].startswith("multi") for t in out["multi"])               # 2- and 3-game slips use confirmed games only


# ------------------------------------------------------------------ the four steps (owner, 25 November 2026)
def test_only_listed_rungs_with_their_book_price(world):
    S, PS = world["S"], world["PS"]
    cfg = {**world["cfg"], "gates": {**world["cfg"]["gates"], "require_book_rung": True}}
    pid = int(PS.players.player_id.iloc[0])
    rows = [{"market": "sog", "player_id": pid, "side": "over", "line": 1.5, "price": -150.0, "book": "betmgm"},
            {"market": "sog", "player_id": pid, "side": "over", "line": 1.5, "price": -140.0, "book": "fanduel"},
            {"market": "sog", "player_id": pid, "side": "over", "line": 2.5, "price": 120.0, "book": "betmgm"}]
    legs, removed = tickets.build_legs(PS, S, open_gates(), {}, rows, {**game_sim.summary(S, cfg), "blowout_flag": False}, cfg)
    props = [l for l in legs if l.get("kind") == "prop"]
    assert {(l["rung"], l["price"], l["book"]) for l in props} == {(2, -140.0, "fanduel"), (3, 120.0, "betmgm")}   # FanDuel first
    assert all(l["price"] is not None for l in legs)                                   # nothing without a listed price
    assert any(r["reason"] == "rung not on the book's ladder" for r in removed)


def test_matchup_marks_and_rungs(world):
    cfg = world["cfg"]
    m = cfg["tickets"]["matchup"]
    assert tickets.matchup_grade(m["strong"], cfg) == "strong" and tickets.matchup_grade(1.0, cfg) == "neutral"
    assert tickets.matchup_grade(m["weak"], cfg) == "weak"
    leg = lambda rung, p, grade, pid=1: {"market": "sog", "player_id": pid, "rung": rung, "p": p, "matchup": grade}
    pool = tickets.floor_rungs([leg(2, 0.85, "neutral"), leg(3, 0.66, "neutral")], cfg)
    assert [l["rung"] for l in pool] == [2]                                          # neutral: the floor rung
    pool = tickets.floor_rungs([leg(2, 0.85, "strong"), leg(3, 0.66, "strong")], cfg)
    assert [l["rung"] for l in pool] == [3] and pool[0]["rung_reason"].startswith("strong")   # strong: one rung up
    assert tickets.floor_rungs([leg(1, 0.66, "strong")], cfg) == []                  # but never in place of a floor rung
    assert tickets.floor_rungs([leg(2, 0.95, "weak")], cfg) == []                    # weak: off the slip
    f = tickets.matchup_factors(world["PS"], world["S"], cfg)
    assert {k[0] for k in f} >= {"sog", "hits", "blk", "pts", "ast", "goals", "saves"} and all(v > 0 for v in f.values())


def test_slip_price_is_the_book_legs_multiplied():
    assert tickets.legs_price([-110, -110]) == 264
    assert tickets.legs_price([+100]) == 100 and tickets.legs_price([-200]) == -200
    assert tickets.legs_price([-110, None]) is None and tickets.legs_price([]) is None


def test_lotto_is_ranged_by_book_prices_not_chosen_by_them(world):
    S, PS = world["S"], world["PS"]
    cfg = {**world["cfg"], "gates": {**world["cfg"]["gates"], "require_book_rung": True}}
    games = []
    for i in range(4):
        out = tickets.build(PS, S, open_gates(), {}, [], {**game_sim.summary(S, cfg), "blowout_flag": False}, [], world["cfg"])
        legs = [{**l, "price": 150.0, "book": "fanduel"} for l in out["legs"]]
        games.append({"game_id": i, "label": f"G{i}", "legs": legs, "multi_part": out["multi_part"], "gates_ok": True})
    lot = tickets.lotto(games, cfg)
    if lot:
        d = 1.0
        for l in lot["legs"]:
            d *= 2.5
        assert d >= cfg["tickets"]["multi"]["lotto_min_decimal"] and lot["book_price"] >= 5000
    unpriced = [{**g, "legs": [{**l, "price": None} for l in g["legs"]]} for g in games]
    assert tickets.lotto(unpriced, cfg) is None                                        # no listed price, no lotto leg
