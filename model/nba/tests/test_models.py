import numpy as np
import pandas as pd

from nba import game_sim as gs
from nba import inout, props
from nba import player_sim as ps
from nba.config import CONFIG

C = dict(tov_pp=0.135, fta_pp=0.22, fga_pp=0.885, r3=0.42, p3=0.36, p2=0.545, ft_pct=0.78, orb=0.25, stl_tov=0.55, blk_fg2a=0.09, ast_fgm=0.62)


def test_simulated_scores_are_built_from_the_events():
    s = gs.simulate("g", "h", "a", C, C, 100.0, 4.0, 226.0, 6000, 7, CONFIG)
    pts = 2 * s.box["fg2m"] + 3 * s.box["fg3m"] + s.box["ftm"]
    assert (pts == s.final).all() and (s.final[:, 0] != s.final[:, 1]).all()
    assert (s.box["fg2m"] <= s.box["fg2a"]).all() and (s.box["ast"] <= s.box["fg2m"] + s.box["fg3m"]).all()
    assert (s.box["stl"][:, 0] <= s.box["tov"][:, 1]).all() and (s.pts_q.sum(2) <= s.final).all()
    assert abs(s.margin.mean() - 4.0) < 0.8 and abs(s.total.mean() - 226.0) < 1.5
    assert 12.5 < s.margin.std() < 16.0 and 0.03 < (s.ot > 0).mean() < 0.09


def test_game_leg_probabilities_are_consistent():
    s = gs.simulate("g", "h", "a", C, C, 100.0, 6.0, 226.0, 6000, 3, CONFIG)
    ml = gs.game_leg_prob(s, "ml", side="home")
    assert abs(ml + gs.game_leg_prob(s, "ml", side="away") - 1) < 1e-9 and ml > 0.6
    sp = [gs.game_leg_prob(s, "spread", l, "home") for l in (-10.5, -4.5, 1.5, 7.5)]
    assert sp == sorted(sp) and sp[2] > ml > sp[1]
    tot = [gs.game_leg_prob(s, "total", l, "over") for l in (215.5, 225.5, 235.5)]
    assert tot == sorted(tot, reverse=True)
    assert abs(gs.game_leg_prob(s, "total", 225.5, "over") + gs.game_leg_prob(s, "total", 225.5, "under") - 1) < 1e-9


def test_blowout_states_follow_config():
    s = gs.simulate("g", "h", "a", C, C, 100.0, 14.0, 226.0, 6000, 5, CONFIG)
    b = s.blowout(CONFIG)
    assert (b[s.q4_entry >= CONFIG["blowout_q4_lead"]] != 0).all() and (b == 1).mean() > (b == -1).mean() * 4
    tight = dict(CONFIG, blowout_q4_lead=40, blowout_2h_checkpoint_lead=45)
    assert (s.blowout(tight) != 0).mean() < 0.05


def test_player_simulation_adds_up_to_the_team(simmed):
    card, sims, pl = simmed
    home = (pl.players.team_id == sims.home_id).to_numpy()
    for t, m in ((0, home), (1, ~home)):
        assert (pl.data["pts"][:, m].sum(1) == sims.final[:, t]).mean() > 0.97          # capped re-deals can drop a point rarely
        assert (pl.data["reb"][:, m].sum(1) == sims.box["oreb"][:, t] + sims.box["dreb"][:, t]).all()
        assert (pl.data["ast"][:, m].sum(1) == sims.box["ast"][:, t]).all()
        assert (pl.data["fg3m"][:, m].sum(1) <= sims.box["fg3m"][:, t]).all()
        assert (np.abs(pl.data["min"][:, m].sum(1) - (240 + 25 * sims.ot)) < 1.0).mean() > 0.99
    assert (pl.data["fgm"] <= pl.data["fga"]).all()


def test_combos_and_joint_come_from_the_same_games(simmed):
    card, sims, pl = simmed
    pid = pl.players.sort_values("e_min").player_id.iloc[-1]
    j = pl.col(pid)
    assert (pl.values(pid, "pra") == pl.data["pts"][:, j] + pl.data["reb"][:, j] + pl.data["ast"][:, j]).all()
    a, b = pl.hits(pid, "pts", 9.5), pl.hits(pid, "pra", 14.5)
    joint = ps.joint_prob([a, b])
    assert joint <= min(a.mean(), b.mean()) + 1e-9 and joint > a.mean() * b.mean()     # positively linked, so above the product
    dd = pl.values(pid, "dd")
    assert set(np.unique(dd)) <= {0, 1}
    tab = ps.correlation_table(["pts", "pra"], [a, b])
    assert tab.loc["pts", "pra"] > 0.3
    sp = ps.split_prob(pl, a, pl.active(pid))
    assert 0 <= sp["all"] <= 1


def test_minutes_distribution_and_blowout_effect(pipe, simmed):
    card, sims, pl = simmed
    S = ps.summary(pl)
    st = S[S.role == "starter"]
    assert (st.min_p10 < st.min_p50).all() and (st.min_p50 < st.min_p90).all() and len(st) >= 8
    assert set(S.role) <= {"starter", "sixth man", "rotation", "fringe"}
    m = pipe.models[2026]["minutes"]
    assert m.q4.shape == (3, len(CONFIG["q4_entry_buckets"]) - 1)
    assert 0 < m.given_final_margin(0, 0) < 2


def test_missing_teammate_moves_minutes_to_others():
    rows = []
    for g in range(30):
        out = g >= 20
        for k, (pos, mins) in enumerate([("G", 34), ("G", 30), ("F", 28), ("C", 26), ("G", 14)]):
            played = not (k == 0 and out and g < 29)
            m = mins + (8 if (out and k == 4) else 0)
            rows.append({"game_id": f"g{g:02d}", "team_id": "T", "player_id": f"p{k}", "name": f"P{k}", "grp": pos, "season": 2026,
                         "tip": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=2 * g), "pending": 0,
                         "played": int(played), "min": m if played else 0, "fga": 10 if played else 0, "fg3a": 3 if played else 0,
                         "fta": 2 if played else 0, "reb": 4 if played else 0, "ast": 3 if played else 0, "pts": 12 if played else 0,
                         "base_min": mins, "last_team": "T", "exp_out": int(k == 0 and g == 29)})
    P = pd.DataFrame(rows)
    io = inout.adjustments(P, CONFIG)
    last = io[io.game_id == "g29"].set_index("player_id")
    assert "p0" not in last.index                                   # the absent player gets no row
    assert last.loc["p4", "io_min"] > 0.05 and "P0 out" in last.loc["p4", "io_notes"] and "with/without" in last.loc["p4", "io_notes"]
    early = io[io.game_id == "g05"].set_index("player_id")
    assert abs(early.loc["p4", "io_min"]) < 1e-9                    # nobody out and no history of absences: no adjustment


def test_rate_adjustments_are_itemised_capped_and_gated(pipe):
    m = pipe.models[2026]
    gid = pipe.G[pipe.G.season == 2026].game_id.iloc[40]
    _, _, _, rows = pipe.game_inputs(gid, m)
    lim = np.log1p(CONFIG["max_total_adjustment"]) + 1e-9
    for s in props.VOLUME + ["fg2m", "fg3m"]:
        assert (rows["adj_" + s].abs() <= lim).all()
    r = rows.iloc[0]
    assert isinstance(r["items"], list) and all(len(i) == 3 for i in r["items"])
    assert set(rows.gate_pts.unique()) <= {0, 1}
    ok = rows.exp_fg_pct >= rows.base_fg_pct
    assert (rows.gate_pts == ok.astype(int)).all()
    off = props.fit(pipe.D[pipe.D.season < 2026], CONFIG, {**CONFIG["factor_groups_on"], "form": False})
    assert not any(k.startswith("form") for k in off.coefs["fg2a"])
