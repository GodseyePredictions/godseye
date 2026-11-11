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
    assert ok(leg("a", "pts", 0.72))[0]
    assert ok(leg("a", "pts", 0.69))[1].endswith("under the floor")
    assert ok(leg("a", "pts", 0.8, eligible_player=False))[1] == "player not confirmed in"
    assert ok(leg("a", "pts", 0.8, gate_ok=False))[1] == "fails the shooting gate"
    assert ok(leg("a", "pts", 0.8, price=None))[1] == "no book price"
    assert ok(leg("a", "dd", 0.9, kind="dd"))[1] == "not a props-ticket market"            # never mixed into props tickets
    assert ok(leg("a", "pts", 0.8, flagged_game=True, p_blowout=0.6))[1] == "under the floor inside blowout simulations"
    assert ok(leg("a", "pts", 0.8, flagged_game=True, rung_rank=3))[1] == "starter's upper rung in a blowout-flagged game"
    assert ok(leg("a", "pts", 0.8, flagged_game=True, rung_rank=3, starter=False))[0]


def test_ticket_uses_joint_probability_and_limits():
    shared = np.random.default_rng(1).random(N) < 0.8
    pool = [leg("a", "pts", 0.8, hits=shared), leg("b", "reb", 0.8, hits=shared), leg("c", "ast", 0.8, hits=shared),
            leg("d", "pts", 0.8, hits=shared), leg("e", "reb", 0.75, seed=5), leg("a", "reb", 0.75, seed=6), leg("a", "ast", 0.75, seed=7)]
    t = tk.best_ticket(pool, 4, CONFIG)
    assert abs(t["joint"] - np.logical_and.reduce([l["hits"] for l in t["legs"]]).mean()) < 1e-12
    assert t["joint"] > 0.8 ** 4 + 0.1                                    # correlated legs: far above the naive product
    per = pd.Series([l["player_id"] for l in t["legs"]]).value_counts()
    assert per.max() <= CONFIG["max_legs_per_player"]
    assert t["price_is_estimate"] is True and t["ev"] is not None


def test_combo_is_not_stacked_with_its_own_component():
    pool = [leg("a", "pra", 0.8, seed=1), leg("a", "pts", 0.8, seed=2), leg("b", "reb", 0.8, seed=3), leg("c", "ast", 0.8, seed=4),
            leg("d", "reb", 0.8, seed=5)]
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
