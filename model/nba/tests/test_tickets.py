import json
import sqlite3

import numpy as np
import pandas as pd

from common import tickets as tk
from nba import grading, ledger, sgp
from nba.config import CONFIG
from nba.store import SCHEMA, upsert

N = 4000


def leg(pid, market, p, price=-250, seed=0, kind="prop", **kw):
    rng = np.random.default_rng(seed)
    base = {"id": f"{pid}|{market}|{seed}", "kind": kind, "player_id": pid, "team_id": "T", "market": market, "line": 9.5, "side": "over",
            "p": p, "price": price, "hits": rng.random(N) < p, "active": None, "gate_ok": True, "eligible_player": True,
            "starter": True, "rung_rank": 1, "flagged_game": False, "p_blowout": p, "p_close": p, "script": None,
            "label": f"P{pid} 10+ {market}", "book": "bet365", "price_seen_at": "t", "reason": "r"}
    base.update(kw)
    return base


def test_every_rule_for_a_same_game_parlay_leg():
    ok = lambda l, **k: sgp.sgp_eligible(l, CONFIG, **k)
    assert ok(leg("a", "pts", 0.76))[0]
    assert ok(leg("a", "pts", 0.74))[1].endswith("under the floor")
    assert ok(leg("a", "pts", 0.8, eligible_player=False))[1] == "player not confirmed in"
    assert ok(leg("a", "pts", 0.8, gate_ok=False))[1] == "fails the shooting gate"
    assert ok(leg("a", "pts", 0.8, price=None))[1] == "no book price"
    assert ok(leg("a", "dd", 0.9, kind="dd"))[1] == "not a props-ticket market"            # never mixed into props tickets
    assert ok(leg("a", "pts", 0.8, flagged_game=True, p_blowout=0.6))[1] == "under the floor inside blowout simulations"
    assert ok(leg("a", "pts", 0.8, flagged_game=True, rung_rank=3))[1] == "starter's upper rung in a blowout-flagged game"
    assert ok(leg("a", "pts", 0.8, flagged_game=True, rung_rank=3, starter=False))[0]


def test_ticket_uses_joint_probability_and_limits():
    shared = np.random.default_rng(1).random(N) < 0.8
    pool = [leg("a", "pts", 0.8, hits=shared), leg("b", "fg3m", 0.8, hits=shared), leg("c", "ast", 0.8, hits=shared),
            leg("d", "pts", 0.8, hits=shared), leg("e", "fg3m", 0.75, seed=5), leg("a", "fg3m", 0.75, seed=6), leg("a", "ast", 0.75, seed=7)]
    t = tk.best_ticket(pool, 4, CONFIG)
    assert abs(t["joint"] - np.logical_and.reduce([l["hits"] for l in t["legs"]]).mean()) < 1e-12
    assert t["joint"] > 0.8 ** 4 + 0.1                                    # correlated legs: far above the naive product
    per = pd.Series([l["player_id"] for l in t["legs"]]).value_counts()
    assert per.max() <= CONFIG["max_legs_per_player"]
    assert t["price_is_estimate"] is True and t["ev"] is not None


def test_combo_is_not_stacked_with_its_own_component():
    pool = [leg("a", "pra", 0.8, seed=1), leg("a", "pts", 0.8, seed=2), leg("b", "fg3m", 0.8, seed=3), leg("c", "ast", 0.8, seed=4),
            leg("d", "fg3m", 0.8, seed=5)]
    assert not tk.allowed([pool[0], pool[1], pool[2], pool[3]], CONFIG)
    assert tk.allowed([pool[0], pool[2], pool[3], pool[4]], CONFIG)
    assert not tk.allowed([leg("a", "pts", 0.8, seed=1), leg("a", "pts", 0.9, seed=2, line=7.5)], CONFIG)   # two rungs of one market


def test_no_bet_is_a_valid_result():
    weak = [leg(x, "pts", 0.72, seed=i) for i, x in enumerate("abcdef")]
    assert tk.best_ticket(weak, 6, CONFIG) is None                         # six independent 72% legs cannot clear the joint minimum
    card = {"scripts": [], "matchup": "A @ B"}
    built = sgp.build_tickets(weak[:3], None, card, CONFIG)
    assert built["tickets"] == [] and any("no bet" in n for n in built["notes"])
    assert any("no game leg" in n or "props_4" in n for n in built["notes"])


def test_double_double_ticket_is_separate_and_singles_are_edges_only():
    legs = [leg(x, "pts", 0.8, seed=i) for i, x in enumerate("abcd")] + [leg("a", "dd", 0.82, kind="dd", price=-300, seed=9),
                                                                         leg("b", "pts", 0.45, price=150, seed=10, line=29.5)]
    built = sgp.build_tickets(legs, None, {"scripts": [], "matchup": "A @ B"}, dict(CONFIG, sgp_sizes=[4]))
    types = {t["type"]: t for t in built["tickets"]}
    assert set(types) == {"props_4", "double_double"}
    assert all(l["kind"] == "prop" for l in types["props_4"]["legs"]) and [l["market"] for l in types["double_double"]["legs"]] == ["dd"]
    assert [s["market"] for s in built["singles"]] == ["pts"] and built["singles"][0]["p"] < CONFIG["sgp_leg_floor"]
    assert 0 < built["singles"][0]["kelly_stake"] <= CONFIG["kelly_cap"]


def test_placed_ticket_is_timestamped_and_locked():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    ledger.init(con)
    upsert(con, "nba_tickets", [{"ticket_id": "t1", "run_id": "r", "run_at": "x", "game_id": "g", "type": "props_4", "leg_ids": "[]",
                                 "slip_json": "[]", "joint_prob": 0.4, "book_price": 200, "price_is_estimate": 1, "fair_price": 150,
                                 "ev": 0.2, "status": "proposed", "placed_at": None, "stake": None, "locked": 0}])
    assert ledger.place(con, "t1", stake=10, book_price=180)["ok"]
    row = con.execute("SELECT status, locked, placed_at, book_price, price_is_estimate FROM nba_tickets").fetchone()
    assert row[0] == "placed" and row[1] == 1 and row[2] and row[3] == 180 and row[4] == 0
    assert not ledger.place(con, "t1")["ok"]                                # cannot be placed (or re-priced) twice
    assert ledger.supersede(con, "g") == 0                                  # a re-run never touches a placed ticket


def test_grading_results_and_cause_tags():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    ledger.init(con)
    game = {"game_id": "g", "season": 2027, "date_et": "2026-11-10", "tip_utc": "2026-11-11T00:00:00+00:00", "known_at": "2026-11-11T02:30:00+00:00",
            "home_id": "H", "away_id": "A", "home": "NY", "away": "MIL", "venue": "", "neutral": 0, "completed": 1, "home_pts": 120,
            "away_pts": 100, "periods": 4, "hq1": 30, "hq2": 30, "hq3": 30, "hq4": 30, "aq1": 25, "aq2": 25, "aq3": 20, "aq4": 30,
            "max_lead_2h_home": 24, "max_lead_2h_away": 0, "close_last5": 0}
    upsert(con, "games", [game])
    box = lambda pid, **k: {"game_id": "g", "team_id": "H", "player_id": pid, "name": pid, "min": 34, "pts": 20, "reb": 5, "ast": 5,
                            "fg3m": 2, "stl": 1, "blk": 0, "fga": 16, "fgm": 7, "known_at": "x", **k}
    upsert(con, "player_games", [box("hit"), box("blow", min=24, pts=12), box("hurt", min=6, pts=2), box("cold", pts=11, fga=18, fgm=4),
                                 box("dnp", min=0, pts=0)])
    P = lambda pid, **k: {"run_id": "r", "run_at": "x", "game_id": "g", "player_id": pid, "name": pid, "min_mean": 34.0, "min_p10": 28.0,
                          "pts": 20.0, "exp_fg_pct": 0.47, **k}
    upsert(con, "nba_projections", [P(x) for x in ("hit", "blow", "hurt", "cold", "dnp")])
    L = lambda pid, **k: {"leg_id": pid, "run_id": "r", "run_at": "x", "game_id": "g", "kind": "prop", "player_id": pid, "team_id": "H",
                          "label": f"{pid} 15+ Points", "market": "pts", "line": 14.5, "side": "over", "model_prob": 0.75,
                          "sgp_eligible": 1, "gate_ok": 1, **k}
    upsert(con, "nba_legs", [L(x) for x in ("hit", "blow", "hurt", "cold", "dnp")] +
           [{**L("ml"), "kind": "game", "player_id": None, "market": "ml", "line": 0.0, "side": "team", "label": "NY Money Line"}])
    T = lambda tid, ids: {"ticket_id": tid, "run_id": "r", "run_at": "x", "game_id": "g", "type": "props_4", "leg_ids": json.dumps(ids),
                          "slip_json": json.dumps([{"description": i} for i in ids]), "joint_prob": 0.5, "status": "proposed", "locked": 0}
    upsert(con, "nba_tickets", [T("won", ["hit", "ml", "dnp"]), T("lost", ["hit", "blow", "hurt", "cold"]), T("void", ["dnp"])])
    card = grading.grade_date(con, "2026-11-10")
    res = dict(con.execute("SELECT leg_id, result FROM nba_legs").fetchall())
    assert res == {"hit": "won", "blow": "lost", "hurt": "lost", "cold": "lost", "dnp": "void", "ml": "won"}
    tr = {r[0]: (r[1], json.loads(r[2])) for r in con.execute("SELECT ticket_id, result, miss_causes FROM nba_tickets")}
    assert tr["won"][0] == "won" and tr["void"][0] == "void" and tr["lost"][0] == "lost"
    assert tr["lost"][1] == ["blowout", "injury in game", "shooting variance"]
    assert card["eligible_legs"]["n"] == 5 and card["eligible_legs"]["hit"] == 2 and "REPORT CARD" in card["text"]


def test_four_leg_slip_uses_four_players_and_rebounds_need_the_higher_floor():
    pool = [leg("a", "pts", 0.85, seed=1), leg("a", "ast", 0.84, seed=2), leg("b", "pts", 0.8, seed=3),
            leg("c", "pts", 0.8, seed=4), leg("d", "ast", 0.78, seed=5), leg("e", "fg3m", 0.76, seed=6)]
    cfg = {**CONFIG, "ticket_min_joint": {4: 0.0, 6: 0.0, 8: 0.0}}
    four = tk.best_ticket(pool, 4, cfg, require_price=False)
    assert len({l["player_id"] for l in four["legs"]}) == 4
    assert tk.allowed([pool[0], pool[1]], cfg, size=6) and not tk.allowed([pool[0], pool[1]], cfg, size=4)
    assert not sgp.sgp_eligible(leg("a", "reb", 0.74))[0] and sgp.sgp_eligible(leg("a", "reb", 0.76))[0]
    low = dict(CONFIG, sgp_leg_floor=0.70)                      # a market floor still applies above a lower general floor
    assert sgp.sgp_eligible(leg("a", "pts", 0.74), low)[0] and not sgp.sgp_eligible(leg("a", "reb", 0.74), low)[0]


def test_rebound_cap_and_second_four_leg_slip():
    reb = [leg(p, "reb", 0.85, seed=i) for i, p in enumerate("abcd")]
    assert not tk.allowed([reb[0]], CONFIG, size=4)                         # no rebound leg on a 4-leg slip
    assert tk.allowed([reb[0]], CONFIG, size=6) and not tk.allowed([reb[0], reb[1]], CONFIG, size=6)   # one at most elsewhere
    pool = [leg(p, m, 0.8 + i / 200, seed=10 + i) for i, (p, m) in enumerate(
        [("a", "pts"), ("b", "pts"), ("c", "ast"), ("d", "fg3m"), ("e", "pts"), ("f", "ast"), ("g", "fg3m"), ("h", "pts")])]
    cfg = dict(CONFIG, ticket_min_joint={4: 0.0, 5: 0.0, 6: 0.0})

    class S:
        game_id = "g"
    built = sgp.build_tickets(pool, S(), {"scripts": []}, cfg, require_price=True)
    by = {t["type"]: t for t in built["tickets"]}
    assert "props_8" not in by and {"props_4", "props_4b", "props_6"} <= set(by)
    a, b = ({l["player_id"] for l in by[k]["legs"]} for k in ("props_4", "props_4b"))
    assert len(a) == 4 and len(b) == 4 and not (a & b)                      # two independent slips
    assert all(l["market"] != "reb" for k in ("props_4", "props_4b") for l in by[k]["legs"])


def test_calibration_shift_is_fitted_shrunk_and_point_in_time():
    import sqlite3
    import numpy as np
    from nba import calibrate, ledger
    con = sqlite3.connect(":memory:")
    ledger.init(con)
    rng = np.random.default_rng(0)
    rows = []
    for i in range(400):                                  # forecasts of 75% that really hit 85%
        rows.append(("l%d" % i, "r1", "2026-01-01T00:00:00", "g%d" % (i % 40), "prop", "p%d" % i, "pts", "over", 0.75,
                     "won" if rng.random() < 0.85 else "lost", "2026-01-02T09:00:00"))
    con.executemany("INSERT INTO nba_legs (leg_id, run_id, run_at, game_id, kind, player_id, market, side, model_prob, result, graded_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    cal = calibrate.fit(con, CONFIG)
    c = cal["pts"]
    assert 0 < c["shift"] < c["measured"] and c["shift"] <= CONFIG["cal_max_shift"]          # shrunk and capped
    assert 0.75 < calibrate.apply(0.75, c["shift"]) < 0.85
    assert calibrate.fit(con, CONFIG, before="2026-01-02T00:00:00") == {}                    # nothing graded yet at that time
    assert calibrate.apply(0.75, 0.0) == 0.75 and "reb" not in cal


def test_all_games_slip_takes_one_ticket_from_every_game():
    from nba import run_slate
    def t(j, d):
        return {"joint": j, "decimal": d, "legs": [leg("a", "pts", 0.8, seed=i) for i in range(4)]}
    per = {g: {"matchup": g, 4: t(0.4, 3.0), 5: t(0.3, 4.0)} for g in ("g1", "g2", "g3", "g4")}
    on = dict(CONFIG, multi_all_games_legs=4)
    assert "multi_all" not in {s["type"] for s in run_slate.multi_game_slips(per, CONFIG)}     # off unless asked for
    slips = {s["type"]: s for s in run_slate.multi_game_slips(per, on)}
    big = slips["multi_all"]
    assert big["n_legs"] == 16 and len(big["parts"]) == 4 and abs(big["joint"] - 0.4 ** 4) < 1e-12
    assert "multi_12" in slips and len(slips["multi_12"]["parts"]) == 3
    three = {s["type"] for s in run_slate.multi_game_slips({g: per[g] for g in ("g1", "g2", "g3")}, on)}
    assert "multi_all" not in three                      # with three games it would repeat the 12-prop slip


def test_results_are_kept_off_the_site_file(tmp_path, monkeypatch):
    from nba import run_slate
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    ledger.init(con)
    monkeypatch.setattr(run_slate, "OUT", tmp_path)
    monkeypatch.setattr(run_slate, "HERE", tmp_path)
    (tmp_path / "data").mkdir()
    run_slate.write_track_file(con, dict(CONFIG, site_show_results=False))
    public = json.loads((tmp_path / "nba_track.json").read_text())
    assert public["slates"] == [] and public["totals"] == {}
    assert (tmp_path / "data" / "nba_track_private.json").exists()


def test_leg_far_above_the_book_price_is_kept_off_slips():
    ok, why = sgp.sgp_eligible(leg("a", "ast", 0.76, price=117))            # book implies 46%
    assert not ok and "above the book" in why
    assert sgp.sgp_eligible(leg("a", "ast", 0.80, price=-250))[0]            # book implies 71%: a normal gap
    assert sgp.sgp_eligible(leg("a", "ast", 0.76, price=117), dict(CONFIG, max_model_edge_vs_book=None))[0]


def test_cashed_showcase_lists_winners_with_example_stakes_and_the_full_count():
    from nba import run_slate
    leg_ = {"label": "A 10+ Points", "p": 0.8, "price": -300.0, "result": "won", "actual": 14.0}
    track = {"made_at": "t", "slates": [{"date": "2026-11-11", "tickets": [
        {"id": "w1", "game": "X @ Y", "type": "props_6", "result": "won", "joint": 0.3, "price": 400.0, "n": 6, "legs": [leg_]},
        {"id": "w2", "game": "X @ Y", "type": "props_4", "result": "won", "joint": 0.4, "price": 150.0, "n": 4, "legs": [leg_]},
        {"id": "l1", "game": "X @ Y", "type": "props_4b", "result": "lost", "joint": 0.4, "price": 120.0, "n": 4, "legs": [leg_]},
        {"id": "p1", "game": "X @ Y", "type": "props_4", "result": "pending", "joint": 0.4, "price": 120.0, "n": 4, "legs": [leg_]}]}]}
    c = run_slate.cashed_showcase(track, CONFIG)
    assert c["issued"] == 3 and c["cashed"] == 2 and [s["id"] for s in c["slips"]] == ["w1", "w2"]      # losers are counted, not listed
    long_, short = c["slips"]
    assert long_["stake"] == CONFIG["cashed_stake_long"] and abs(long_["returned"] - 250.0) < 1e-9
    assert short["stake"] == CONFIG["cashed_stake_short"] and abs(short["profit"] - 127.5) < 1e-9
    assert c["nights"] == [{"date": "2026-11-11", "issued": 3, "cashed": 2}]
    assert c["all_staked"] == 50 + 85 + 85 and abs(c["all_net"] - (250.0 + 212.5 - 220)) < 1e-9          # losers' stakes count against the total


def test_band_slips_land_in_their_price_band_and_a_band_out_of_reach_is_a_note():
    import numpy as np
    from nba import bands
    rng = np.random.default_rng(3)

    def leg_(i, p, price):
        return {"kind": "prop", "player_id": f"p{i}", "team_id": "1", "starter": True, "gate_ok": True, "eligible_player": True, "rung_rank": 1,
                "market": "pts", "line": 9.5, "side": "over", "p": p, "p_blowout": p, "p_close": p, "price": price, "hits": rng.random(4000) < p,
                "active": None, "script": None, "flagged_game": False, "label": f"P{i} 10+ Points", "id": f"g|pts|p{i}|over|9.5"}
    legs = [leg_(i, 0.80, -300.0) for i in range(8)] + [leg_(8, 0.60, 110.0)]            # the last leg is under the floor
    cfg = {**CONFIG, "price_band_slips": [{"key": "a", "min_price": 301, "max_price": 500}, {"key": "b", "min_price": 2000, "max_price": 3000}]}
    out, notes = bands.band_tickets(legs, cfg)
    assert [t["type"] for t in out] == ["a"] and len(out[0]["legs"]) == 6 and 301 <= out[0]["book_price"] <= 500
    assert all(l["p"] >= CONFIG["sgp_leg_floor"] for l in out[0]["legs"])
    assert len(notes) == 1 and notes[0].startswith("b: no bet")
    # the lotto slip joins each game's longest band slip; its chance is the product of the games' counted chances
    lot = bands.lotto({"g1": ("A @ B", out), "g2": ("C @ D", out)}, cfg)
    assert lot["n_legs"] == 12 and abs(lot["joint"] - out[0]["joint"] ** 2) < 1e-12
    assert bands.lotto({"g1": ("A @ B", out), "g2": ("C @ D", [])}, {**cfg, "lotto_games": 2}) is None   # too few games with a band slip
    big = {f"g{i}": (f"T{i} @ U{i}", out) for i in range(9)}
    assert bands.lotto(big, cfg)["n_legs"] == 6 * cfg["lotto_games"]                        # a 9-game slate still makes a 3-game lotto


def test_value_locks_keep_the_price_range_and_the_parlay_takes_one_leg_per_player():
    import numpy as np
    from nba import bands
    hits = np.ones(100, dtype=bool)

    def leg_(pid, market, p, price):
        return {"kind": "prop", "player_id": pid, "team_id": "1", "starter": True, "gate_ok": True, "eligible_player": True, "rung_rank": 1,
                "market": market, "line": 2.5, "side": "over", "p": p, "p_blowout": p, "p_close": p, "price": price, "hits": hits,
                "active": None, "script": None, "flagged_game": False, "label": f"{pid} {market}", "id": f"g|{market}|{pid}|over|2.5"}
    legs = [leg_("a", "pts", 0.80, -290.0), leg_("a", "reb", 0.79, -250.0), leg_("b", "reb", 0.78, -240.0), leg_("c", "reb", 0.77, -230.0),
            leg_("d", "pts", 0.90, -900.0), leg_("e", "pts", 0.70, -150.0)]
    v = bands.value_locks(legs, CONFIG)
    assert [l["player_id"] for l in v] == ["a", "a", "b", "c"]                            # -900 is outside the range; 70% is under the floor
    par = bands.value_parlay({"g1": ("A @ B", v), "g2": ("C @ D", [leg_("x", "ast", 0.76, -200.0), leg_("y", "pts", 0.76, -210.0)])},
                             {**CONFIG, "value_parlay_legs": 4, "value_parlay_min_legs": 4})
    picked = [l["label"] for p in par["parts"] for l in p["legs"]]
    assert picked == ["a pts", "b reb", "x ast", "y pts"]                                 # one leg per player, one rebound leg per game
