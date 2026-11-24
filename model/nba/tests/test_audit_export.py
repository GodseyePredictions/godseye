"""The audit export: every confirmed player's rated rungs, and correlations measured from the simulations."""
import numpy as np
import pandas as pd

from nba import audit_export
from nba.config import CONFIG
from nba.player_sim import PlayerSims


def made_up_game(n=20000, seed=3):
    """Two teams of three. Pace lifts everyone; a guard's assists feed his centre's points; one team's
    rebounds come out of the other's; one bench player sits out a third of the time."""
    rng = np.random.default_rng(seed)
    pace = rng.normal(0, 1, n)
    feed = rng.normal(0, 1, n)
    board = rng.normal(0, 1, n)
    P = pd.DataFrame({"player_id": ["h1", "h2", "h3", "a1", "a2", "a3"], "name": ["Home Guard", "Home Centre", "Home Bench", "Away Guard", "Away Centre", "Away Bench"],
                      "team_id": ["1", "1", "1", "2", "2", "2"], "role": ["starter"] * 2 + ["bench"] + ["starter"] * 2 + ["bench"],
                      "e_min": [34, 32, 18, 35, 31, 16], "gate_pts": [1] * 6, "gate_fg3m": [1] * 6})
    lam = {"pts": [24, 18, 8, 26, 16, 7], "reb": [4, 11, 3, 5, 10, 3], "ast": [8, 2, 2, 7, 3, 1], "fg3m": [3, 0.3, 1.2, 2.5, 0.4, 1.0]}
    data = {}
    for s, base in lam.items():
        cols = []
        for j, b in enumerate(base):
            x = 0.18 * pace
            if s == "ast" and j == 0 or s == "pts" and j == 1:
                x = x + 0.25 * feed
            if s == "reb":
                x = x + (0.2 if j < 3 else -0.2) * board
            cols.append(rng.poisson(b * np.exp(x - 0.02)))
        data[s] = np.column_stack(cols).astype(float)
    mins = np.tile(np.array([34, 32, 18, 35, 31, 16], float), (n, 1))
    mins[rng.random(n) < 0.33, 2] = 0
    for s in lam:
        data[s][mins == 0] = 0
    data["min"] = mins
    for s in ("stl", "blk"):
        data[s] = rng.poisson(1.0, (n, 6)).astype(float)
    return PlayerSims("g1", P, data, np.zeros(n, int), np.ones(n, bool))


def leg(ps, pid, market, line, side="over", eligible=True, gate_ok=True):
    hits, act = ps.hits(pid, market, line, side), ps.active(pid)
    return {"kind": "prop", "player_id": pid, "team_id": ps.players.set_index("player_id").team_id[pid], "name": pid, "market": market, "line": line,
            "side": side, "p": float(hits[act].mean()), "p_blowout": None, "p_close": None, "price": -200.0, "eligible_player": eligible,
            "gate_ok": gate_ok, "flagged_game": False, "starter": True, "rung_rank": 1, "hits": hits, "active": act}


def test_ladder_lists_only_confirmed_players_props():
    ps = made_up_game(4000)
    legs = [leg(ps, "h1", "ast", 5.5), leg(ps, "h1", "ast", 7.5), leg(ps, "h2", "pts", 14.5, eligible=False),
            leg(ps, "a1", "fg3m", 1.5, gate_ok=False), {**leg(ps, "a2", "reb", 7.5), "kind": "dd"},
            {"kind": "game", "player_id": None, "market": "total", "line": 220.5, "side": "over", "p": 0.5, "eligible_player": True}]
    lad = audit_export.ladder(legs)
    assert [(l["player_id"], l["market"], l["line"]) for l in lad] == [("h1", "ast", 5.5), ("h1", "ast", 7.5), ("a1", "fg3m", 1.5)]
    assert lad[0]["p"] == legs[0]["p"] and lad[0]["note"] is None
    assert lad[2]["note"] == "fails the shooting gate"
    low = audit_export.ladder([{**leg(ps, "h1", "ast", 12.5)}])[0]
    assert low["p"] < CONFIG["sgp_leg_floor"] and low["note"] is None      # under the floor is the site's call, not a note


def test_correlations_are_measured_from_the_simulations():
    ps = made_up_game()
    nodes = [("h1", "ast"), ("h2", "pts"), ("h1", "pts"), ("a1", "pts"), ("h2", "reb"), ("a2", "reb"), ("h3", "pts"), ("h1", "pra")]
    c = audit_export.correlations(ps, nodes)
    key = lambda a, b: "|".join(sorted([f"{a[0]}:{a[1]}", f"{b[0]}:{b[1]}"]))  # noqa: E731
    assert all(k == "|".join(sorted(k.split("|"))) for k in c), "keys are stored in sorted order"
    assert all(-1 < v < 1 for v in c.values())
    feed = c[key(("h1", "ast"), ("h2", "pts"))]
    pace_only = c[key(("h1", "pts"), ("a1", "pts"))]
    assert feed > pace_only > 0.02, (feed, pace_only)                        # the guard-to-centre link is on top of shared pace
    assert c[key(("h2", "reb"), ("a2", "reb"))] < -0.05                      # one team's boards come out of the other's
    assert c[key(("h1", "pra"), ("h1", "pts"))] > 0.6                        # a combo moves with its own parts
    # the bench player's pairs are measured only where he plays, and still exist
    assert key(("h3", "pts"), ("h1", "pts")) in c
    # too few shared simulations: no number is given
    assert audit_export.correlations(ps, nodes, {**CONFIG, "audit_min_active_sims": 10**9}) == {}
    assert audit_export.correlations(ps, [("h1", "ast")]) == {}


def test_block_is_plain_data_and_matches_counted_joints_in_direction():
    ps = made_up_game()
    legs = [leg(ps, "h1", "ast", 6.5), leg(ps, "h2", "pts", 15.5), leg(ps, "a2", "reb", 8.5), leg(ps, "h2", "reb", 9.5)]
    b = audit_export.block(legs, ps)
    import json
    json.dumps(b, allow_nan=False)
    assert len(b["ladder"]) == 4 and b["corr"]
    # positively linked legs hit together more often than independence says; negatively linked ones less
    a, c = legs[0], legs[1]
    assert (a["hits"] & c["hits"]).mean() > a["hits"].mean() * c["hits"].mean()
    r1, r2 = legs[2], legs[3]
    assert (r1["hits"] & r2["hits"]).mean() < r1["hits"].mean() * r2["hits"].mean()
    assert audit_export.block(legs, None)["corr"] == {}
