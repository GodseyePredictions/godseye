"""Walk-forward backtest of the whole pipeline.

For each test season the models are fitted on earlier seasons only, then every game of the season is run
exactly as it would have been on the day: features from before tip-off, the official injury report as it
stood before tip-off, the game simulated, players simulated on top, legs and tickets built.

There are no historical book prices in this project (no odds key, and ESPN drops old lines), so:
  - legs are a fixed grid of thresholds, not book rungs;
  - tickets are graded on hit rate against their modelled joint probability;
  - there is no closing-line comparison and no real ROI. Nothing here should be read as profit.

Usage (from model/):  python3 -m nba.backtest [n_sims]      writes output/backtest_*.{json,csv.gz}
"""
import json
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from nba import player_sim as ps
from nba import props, sgp
from nba.config import CONFIG
from nba.pipeline import Pipeline
from nba.store import HERE, connect, load_frames

OUT = HERE / "output"
PL: Pipeline = None
GAME_GRID = [("ml", 0.0, "home"), ("ml", 0.0, "away")] + \
            [("spread", l, s) for l in (-10.5, -7.5, -4.5, -1.5, 1.5, 4.5, 7.5, 10.5) for s in ("home", "away")] + \
            [("total", l, s) for l in (205.5, 212.5, 219.5, 226.5, 233.5, 240.5) for s in ("over", "under")]


def game_offers(g) -> pd.DataFrame:
    rows = []
    for m, l, s in GAME_GRID:
        rows.append({"market": m, "player_id": (g.home_id if s == "home" else g.away_id) if m != "total" else None,
                     "player_name": s, "side": "team" if m != "total" else s, "line": l, "price": None, "book": "grid", "known_at": None})
    return pd.DataFrame(rows)


def one_game(args):
    gid, season, n = args
    cfg = PL.cfg
    card, sims, players = PL.run_game(gid, PL.models[season], n)
    g, pred = card["game"], card["pred"]
    bl = sims.blowout(cfg)
    act_blow = int((abs(g.q4_entry) >= cfg["blowout_q4_lead"]) or max(g.max_lead, g.max_deficit) >= cfg["blowout_2h_lead"])
    m = sims.margin
    G = {"game_id": gid, "season": season, "date": g.date_et, "game_no": g.game_no, "model_margin": pred.model_margin,
         "model_total": pred.model_total, "rating_margin": g.r_margin, "p_home": float((m > 0).mean()), "sim_margin_sd": float(m.std()),
         "sim_total_sd": float(sims.total.std()), "m_p10": float(np.percentile(m, 10)), "m_p90": float(np.percentile(m, 90)),
         "t_p10": float(np.percentile(sims.total, 10)), "t_p90": float(np.percentile(sims.total, 90)),
         "p_blowout": float((bl != 0).mean()), "p_close": float(sims.close(cfg).mean()), "margin": g.margin, "total": g.total,
         "blowout": act_blow, "close": g.close_last5, "ot": int(g.periods > 4), "p_ot": float((sims.ot > 0).mean()),
         "sim_poss": float(sims.poss.mean()), "poss": g.poss}
    if players is None:
        return G, [], [], [], []
    act = PL.D[(PL.D.game_id == gid)].set_index("player_id")
    R = players.players
    S = ps.summary(players)
    played = act.played.reindex(R.player_id).fillna(0).to_numpy() == 1
    amin = act["min"].reindex(R.player_id).to_numpy()
    mins = players.data["min"]
    team_out = R.groupby("team_id").n_rot_out.transform("max").to_numpy()
    prow = []
    for j in np.where(played & (R.e_min.to_numpy() >= 8))[0]:
        on = mins[:, j] > 0
        mj = mins[on, j] if on.sum() > 50 else mins[:, j]
        prow.append({"game_id": gid, "season": season, "player_id": R.player_id[j], "role": R.role[j], "e_min": R.e_min[j],
                     "base_min": R.base_min[j], "min_mean": float(mj.mean()), "p10": float(np.percentile(mj, 10)),
                     "p50": float(np.percentile(mj, 50)), "p90": float(np.percentile(mj, 90)), "act": amin[j],
                     "starter_out": int(team_out[j] > 0), "blowout": act_blow,
                     **{f"sim_{s}": float(players.data[s][on, j].mean() if on.sum() > 50 else players.data[s][:, j].mean()) for s in ps.STATS},
                     **{f"act_{s}": float(act[s].reindex([R.player_id[j]]).iloc[0]) for s in ps.STATS}})
    # legs on the calibration grid, for players who took the floor
    cand = R[played & (R.e_min >= 12)]
    offers = pd.concat([sgp.grid_offers(cand, cfg), game_offers(g)], ignore_index=True)
    names = {g.home_id: g.home_abbr, g.away_id: g.away_abbr}
    legs = sgp.build_legs(offers, sims, players, None, names, cfg)
    lrow = []
    flagged = int((bl != 0).mean() >= cfg["blowout_flag_prob"])
    for l in legs:
        if l["kind"] == "game":
            mg = g.margin if l["side"] != "away" else -g.margin
            side = "home" if l["team_id"] == g.home_id else "away"
            val = (g.margin if side == "home" else -g.margin)
            hit = {"ml": val > 0, "spread": val + l["line"] > 0}.get(l["market"], (g.total > l["line"]) if l["side"] == "over" else (g.total < l["line"]))
            l["actual_hit"] = bool(hit)
            lrow.append((gid, season, g.game_no, None, l["market"], l["line"], l["side"], l["p"], int(hit), None, 1, "", 0.0, flagged, 0))
            continue
        a = act.loc[l["player_id"]]
        v = sum(a[s] for s in ps.COMBOS[l["market"]]) if l["market"] in ps.COMBOS else a[l["market"]]
        hit = v > l["line"]
        l["actual_hit"] = bool(hit)
        r = R[R.player_id == l["player_id"]].iloc[0]
        lrow.append((gid, season, g.game_no, l["player_id"], l["market"], l["line"], "over", l["p"], int(hit), l["p_blowout"],
                     int(l["gate_ok"]), r.role, float(r.e_min), flagged, int(r.n_rot_out > 0)))
    drow = []
    for j in np.where(played & (R.e_min.to_numpy() >= 20))[0]:
        pid = R.player_id[j]
        a = act.loc[pid]
        cats = sum(int(a[s] >= 10) for s in ("pts", "reb", "ast", "stl", "blk"))
        drow.append((gid, season, pid, players.prob(pid, "dd", 0.5, "yes"), int(cats >= 2), players.prob(pid, "td", 0.5, "yes"), int(cats >= 3)))
    # tickets, built with the live rules but without prices
    trow = []
    built = sgp.build_tickets(legs, sims, sgp.script_card(card, sims, players, cfg), cfg, require_price=False)
    for t in built["tickets"]:
        if t["type"] == "double_double":
            continue
        trow.append((gid, season, t["type"], len(t["legs"]), t["joint"], int(all(l["actual_hit"] for l in t["legs"])),
                     float(np.mean([l["p"] for l in t["legs"]])), flagged))
    dd_legs = []
    for pid, pdd, hdd, ptd, htd in [(d[2], d[3], d[4], d[5], d[6]) for d in drow]:
        if pdd >= cfg["sgp_leg_floor"]:
            dd_legs.append((pdd, hdd, players.hits(pid, "dd", 0.5, "yes") | ~players.active(pid)))
    if dd_legs:
        dd_legs = sorted(dd_legs, key=lambda x: -x[0])[:cfg["dd_ticket_max_legs"]]
        jp = float(np.logical_and.reduce([d[2] for d in dd_legs]).mean())
        trow.append((gid, season, "double_double", len(dd_legs), jp, int(all(d[1] for d in dd_legs)), float(np.mean([d[0] for d in dd_legs])), flagged))
    # correlations for common pairs: top guard assists with top centre points, two top scorers, top scorer with game total
    corr = []
    for tid in (g.home_id, g.away_id):
        idx = np.where((R.team_id.to_numpy() == tid) & played)[0]
        if len(idx) < 3:
            continue
        top = idx[np.argsort(-R.e_min.to_numpy()[idx])]
        pts = players.data["pts"]
        sc = top[np.argsort(-pts[:, top].mean(0))][:2]
        gd = [j for j in top if R.grp[j] == "G"][:1]
        cn = [j for j in top if R.grp[j] == "C"][:1]
        def z(stat, j):
            x = players.data[stat][:, j]
            return (act[stat].reindex([R.player_id[j]]).iloc[0] - x.mean()) / max(x.std(), 1e-6)
        pairs = [("two top scorers' points", "pts", sc[0], "pts", sc[1])]
        if gd and cn and gd[0] != cn[0]:
            pairs.append(("guard assists with centre points", "ast", gd[0], "pts", cn[0]))
        for name, s1, j1, s2, j2 in pairs:
            corr.append((name, float(np.corrcoef(players.data[s1][:, j1], players.data[s2][:, j2])[0, 1]), z(s1, j1) * z(s2, j2)))
        tot = sims.total
        x = pts[:, sc[0]]
        corr.append(("top scorer's points with game total", float(np.corrcoef(x, tot)[0, 1]),
                     z("pts", sc[0]) * (g.total - tot.mean()) / tot.std()))
    return G, prow, lrow, drow, (trow, corr)


LEG_COLS = ["game_id", "season", "game_no", "player_id", "market", "line", "side", "p", "hit", "p_blowout", "gate_ok", "role", "e_min",
            "flagged", "starter_out"]


def run(n_sims: int | None = None, seasons=(2025, 2026), limit: int | None = None, cfg=CONFIG, stride: int = 1) -> dict:
    global PL
    n = n_sims or cfg["n_sims_backtest"]
    con = connect()
    t0 = time.time()
    PL = Pipeline(load_frames(con), cfg=cfg)
    for s in seasons:
        PL.fit(s)
    jobs = []
    for s in seasons:
        ids = PL.G[(PL.G.season == s) & (PL.G.pending == 0)].sort_values("tip").game_id.tolist()
        jobs += [(g, s, n) for g in (ids[:limit] if limit else ids)[::stride]]
    t1 = time.time()
    with Pool(4) as pool:
        res = pool.map(one_game, jobs, chunksize=20)
    sim_secs = time.time() - t1
    G = pd.DataFrame([r[0] for r in res])
    Pm = pd.DataFrame([x for r in res for x in r[1]])
    Lg = pd.DataFrame([x for r in res for x in r[2]], columns=LEG_COLS)
    Dd = pd.DataFrame([x for r in res for x in r[3]], columns=["game_id", "season", "player_id", "p_dd", "dd", "p_td", "td"])
    Tk = pd.DataFrame([x for r in res if r[4] for x in r[4][0]], columns=["game_id", "season", "type", "n_legs", "joint", "hit", "avg_leg_p", "flagged"])
    Cr = pd.DataFrame([x for r in res if r[4] for x in r[4][1]], columns=["pair", "sim_corr", "zz"])
    OUT.mkdir(exist_ok=True)
    for name, df in (("games", G), ("minutes", Pm), ("legs", Lg), ("dd", Dd), ("tickets", Tk), ("corr", Cr)):
        df.to_csv(OUT / f"backtest_{name}.csv.gz", index=False)
    return {"games": G, "minutes": Pm, "legs": Lg, "dd": Dd, "tickets": Tk, "corr": Cr,
            "timing": {"build_and_fit_s": round(t1 - t0, 1), "simulate_s": round(sim_secs, 1), "games": len(jobs), "n_sims": n,
                       "s_per_game_per_core": round(sim_secs * 4 / max(len(jobs), 1), 3)}}


if __name__ == "__main__":
    r = run(int(sys.argv[1]) if len(sys.argv) > 1 else None, stride=int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    print(json.dumps(r["timing"], indent=1))
    L = r["legs"]
    P = L[L.player_id.notna()]
    P = P.assign(b=(P.p * 10).astype(int).clip(0, 9))
    print(P.groupby("b").agg(n=("hit", "size"), p=("p", "mean"), hit=("hit", "mean")).round(3))
    print(P[P.p >= 0.7].groupby("market").agg(n=("hit", "size"), p=("p", "mean"), hit=("hit", "mean")).round(3))
    M = r["minutes"]
    print("minutes MAE", (M.min_mean - M.act).abs().mean().round(2), "base MAE", (M.base_min - M.act).abs().mean().round(2),
          "above p10", (M.act > M.p10).mean().round(3), "above p50", (M.act > M.p50).mean().round(3), "above p90", (M.act > M.p90).mean().round(3))
    G = r["games"]
    print("margin sd actual-vs-model", (G.margin - G.model_margin).std().round(2), "sim sd", G.sim_margin_sd.mean().round(2),
          "| total", (G.total - G.model_total).std().round(2), G.sim_total_sd.mean().round(2),
          "| in 10-90 margin", ((G.margin > G.m_p10) & (G.margin < G.m_p90)).mean().round(3),
          "total", ((G.total > G.t_p10) & (G.total < G.t_p90)).mean().round(3),
          "| blowout pred/actual", G.p_blowout.mean().round(3), G.blowout.mean().round(3), "close", G.p_close.mean().round(3), G.close.mean().round(3),
          "OT", G.p_ot.mean().round(3), G.ot.mean().round(3), "poss", G.sim_poss.mean().round(1), G.poss.mean().round(1))
    print(r["tickets"].groupby("type").agg(n=("hit", "size"), joint=("joint", "mean"), hit=("hit", "mean")).round(3))
    for role, d in M.groupby("role"):
        print(role, len(d), "MAE", (d.min_mean - d.act).abs().mean().round(2), "bias", (d.min_mean - d.act).mean().round(2),
              ">p10", (d.act > d.p10).mean().round(3), ">p50", (d.act > d.p50).mean().round(3), ">p90", (d.act > d.p90).mean().round(3))
    for s in ps.STATS:
        print(s, "mean sim", M["sim_" + s].mean().round(2), "actual", M["act_" + s].mean().round(2), "MAE", (M["sim_" + s] - M["act_" + s]).abs().mean().round(2))
