"""Anytime-TD slip versions and hedges for a kick-off window: ground, air, mixed, matchup-weighted, favourites, plus
hedges (same-team air cover for the ground ticket, either-scorer pairs, round robins). Probabilities are the model's;
the matchup index only changes the order legs are taken in."""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from .atd_slip import CUSHION, _pick_style, joint
from .correlation import build_sigma
from .defense_report import team_defense
from .early import apply_overrides, atd_parlay_pool, backup_qb_teams

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"


def _z(s):
    s = s.astype(float); sd = s.std()
    return (s - s.mean()) / sd if sd and sd > 0 else s * 0


def _sim(legs, corr, n=200000, seed=7):
    """Simulated hit matrix for a set of legs under the ATD copula."""
    S = build_sigma(legs, corr); rng = np.random.default_rng(seed)
    z = rng.multivariate_normal(np.zeros(len(legs)), S, size=n, method="cholesky")
    return z < norm.ppf(legs.p_attd.values)[None, :]


def build(season, week, games):
    F = apply_overrides(pd.read_parquet(OUT / f"projection_features_{season}_wk{week}.parquet"))
    corr = json.loads((ROOT / "models" / "correlations.json").read_text())
    bq = backup_qb_teams(season, week); D = team_defense(season, week); nD = len(D)
    W = F[F.game_id.isin(games)].copy()
    # ---- matchup index (order only). Backs: own line vs their front, opponent run defence, goal-line share.
    # Pass-catchers: expected dropbacks, pass protection, yards per target allowed to the position, end-zone target share.
    g = lambda c, d=0.0: W[c].astype(float).fillna(d) if c in W.columns else pd.Series(d, index=W.index)  # noqa: E731
    W["opp_run_rank"] = W.opp.map(D.r_rb_rush); W["opp_wr_rank"] = W.opp.map(D.r_wr_yds); W["opp_te_rank"] = W.opp.map(D.r_te_yds)
    W["opp_sack_rank"] = W.opp.map(D.r_sack_rate); W["opp_att_faced"] = W.opp.map(D.pass_att)
    pass_rate = (0.58 + g("proe_oc") / 100).clip(0.4, 0.75)
    W["exp_dropbacks"] = g("exp_plays", 62) * pass_rate
    rb = W.pos_group == "RB"; pc = W.pos_group.isin(["WR", "TE"])
    W["mx"] = 0.0
    W.loc[rb, "mx"] = (0.35 * _z(g("ol_rb_ypc_oc", 4.2)[rb]) + 0.35 * _z(g("dl_rb_ypc_allowed_dc", 4.2)[rb])
                       + 0.30 * _z(W.opp_run_rank[rb]) + 0.25 * _z(g("sh_rush_i10_e3")[rb]) - 0.15 * _z(g("dl_stuff_forced_dc")[rb])).clip(-2, 2)
    ypt = np.where(W.pos_group == "TE", g("ypt_allowed_TE_dc", 7.2), g("ypt_allowed_WR_dc", 8.1))
    W.loc[pc, "mx"] = (0.35 * _z(W.exp_dropbacks[pc]) + 0.30 * _z(pd.Series(ypt, index=W.index)[pc]) + 0.35 * _z(g("sh_ez_tgt_e3")[pc])
                       - 0.20 * _z(g("dl_sack_rate_dc", 0.07)[pc]) + 0.15 * _z(g("rz_pass_oc", 0.55)[pc])).clip(-2, 2)
    W["mx_tag"] = np.where(W.mx >= 0.6, "strong", np.where(W.mx <= -0.6, "weak", "neutral"))
    W["play"] = W.p_attd - W.pos_group.map(CUSHION).fillna(0.05)
    ok, held = atd_parlay_pool(W, bq)
    ok = ok[ok.p_attd >= 0.20]
    lg = lambda d: np.log(d.p_attd / (1 - d.p_attd))  # noqa: E731

    def ticket(pool, n, style="chalk"):
        legs = _pick_style(pool, n, style)
        return None if len(legs) < n else {"n": n, "legs": legs, "p": joint(legs, corr), "p_indep": float(legs.p_attd.prod())}

    V = {}
    ground = ok[ok.pos_group.isin(["RB", "QB"])]
    adj = np.where((ground.pos_group == "RB") & (ground.opp_run_rank >= nD - 9), 0.2, np.where((ground.pos_group == "RB") & (ground.opp_run_rank <= 8), -0.2, 0.0))
    ground = ground.assign(_s=lg(ground) + adj).sort_values("_s", ascending=False)
    air = ok[ok.pos_group.isin(["WR", "TE"])].sort_values("play", ascending=False)
    allp = ok.sort_values("p_attd", ascending=False)
    mxp = ok.assign(_s=lg(ok) + 0.30 * ok.mx - np.where(ok.pos_group == "WR", 0.25, np.where(ok.pos_group == "TE", 0.17, 0.12))).sort_values("_s", ascending=False)
    fav = ok[ok.implied_filled >= 25.5].sort_values("p_attd", ascending=False)
    for key, name, pool, style, note in (
            ("ground", "Ground · backs and quarterbacks", ground, "chalk", "The standard ticket: one back or quarterback per team, run-defence matchup in the order."),
            ("air", "Air · receivers and tight ends", air, "chalk", "Pass-catchers only, one per team, ranked on the play-at probability."),
            ("mixed", "Mixed · half backs, half pass-catchers", allp, "balanced", "No position more than half the legs."),
            ("matchup", "Matchup-weighted · any position", mxp, "chalk", "Ranked on the model plus the matchup index: line play and run defence for backs; dropbacks, pass protection, yards per target allowed and end-zone share for pass-catchers."),
            ("fav", "Favourites · teams implied 25.5+", fav, "chalk", "Only offences the market expects to score most.")):
        V[key] = {"name": name, "note": note, "tickets": [t for t in (ticket(pool, 4, style), ticket(pool, 6, style)) if t]}
    # ---- combo: the most likely mix of ground and air at each size (3+1, 4+2, 5+3), one player per team
    gb = ok[ok.pos_group.isin(["RB", "QB"])].sort_values("p_attd", ascending=False).drop_duplicates("team").set_index("team")
    ab = ok[ok.pos_group.isin(["WR", "TE"])].sort_values("p_attd", ascending=False).drop_duplicates("team").set_index("team")
    teams = sorted(set(gb.index) | set(ab.index)); combo = []
    for n, na in ((4, 1), (6, 2), (8, 3)):
        top = None
        for Tm in combinations(teams, n):
            if any(t not in gb.index and t not in ab.index for t in Tm): continue
            for Am in combinations([t for t in Tm if t in ab.index], na):
                if any(t not in gb.index for t in Tm if t not in Am): continue
                pr = float(np.prod([ab.loc[t].p_attd for t in Am]) * np.prod([gb.loc[t].p_attd for t in Tm if t not in Am]))
                if top is None or pr > top[0]: top = (pr, Tm, Am)
        if top:
            _, Tm, Am = top
            legs = pd.concat([gb.loc[[t for t in Tm if t not in Am]].reset_index(), ab.loc[list(Am)].reset_index()])
            combo.append({"n": n, "legs": legs, "p": joint(legs, corr), "p_indep": float(legs.p_attd.prod()), "mix": f"{n - na} ground + {na} air"})
    V["combo"] = {"name": "Combo · ground and air", "note": "The most likely mix at each size: 3 ground + 1 air, 4 + 2, 5 + 3. One player per team.", "tickets": combo}
    # ---- hedges
    H = {}
    # swap hedges: three primary slips; in each, the two least likely legs are swapped for the next-best scorer on the
    # same team, so the hedge slip wins when that team's touchdown goes to the other man
    prim = []
    if V["ground"]["tickets"]: prim.append(("Ground 4-leg", V["ground"]["tickets"][0]["legs"]))
    for t in combo:
        if t["n"] in (4, 6): prim.append((f"Combo {t['n']}-leg ({t['mix']})", t["legs"]))
    swaps = []
    for nm, legs in prim[:3]:
        legs = legs.reset_index(drop=True); weak = legs.sort_values("p_attd").head(2)
        hedge = legs.copy(); changes = []
        for r in weak.itertuples():
            alt = ok[(ok.team == r.team) & (ok.player_id != r.player_id) & ~ok.player_id.isin(hedge.player_id)].sort_values("p_attd", ascending=False).head(1)
            if alt.empty: continue
            hedge = pd.concat([hedge[hedge.player_id != r.player_id], alt]).reset_index(drop=True)
            changes.append((r.name, float(r.p_attd), alt.iloc[0]["name"], float(alt.iloc[0].p_attd)))
        uni = pd.concat([legs, hedge]).drop_duplicates("player_id").reset_index(drop=True)
        hit = _sim(uni, corr, n=150000); ix = {pid: i for i, pid in enumerate(uni.player_id)}
        a = hit[:, [ix[x] for x in legs.player_id]].all(1); b = hit[:, [ix[x] for x in hedge.player_id]].all(1)
        swaps.append({"name": nm, "primary": legs, "hedge": hedge, "changes": changes, "p_primary": float(a.mean()), "p_hedge": float(b.mean()), "p_either": float((a | b).mean())})
    H["swaps"] = swaps
    g4 = V["ground"]["tickets"][0]["legs"] if V["ground"]["tickets"] else None
    if g4 is not None:
        # air cover: the best clean pass-catcher on each ground team
        cover = air[air.team.isin(g4.team)].drop_duplicates("team")
        cover = cover.set_index("team").reindex(g4.team.values).dropna(subset=["p_attd"]).reset_index()
        if len(cover) == len(g4):
            both = pd.concat([g4, cover]); hit = _sim(both.reset_index(drop=True), corr)
            a, b = hit[:, :len(g4)].all(1), hit[:, len(g4):].all(1)
            H["air_cover"] = {"ground": g4, "cover": cover, "p_ground": float(a.mean()), "p_cover": float(b.mean()), "p_either": float((a | b).mean())}
        # round robins on the ground 4-leg
        hit = _sim(g4.reset_index(drop=True), corr); k = hit.sum(1)
        rr3 = [{"legs": g4.iloc[list(ix)], "p": joint(g4.iloc[list(ix)], corr)} for ix in combinations(range(4), 3)]
        rr2 = [{"legs": g4.iloc[list(ix)], "p": joint(g4.iloc[list(ix)], corr)} for ix in combinations(range(4), 2)]
        H["round_robin"] = {"legs": g4, "dist": {int(i): float((k == i).mean()) for i in range(5)}, "by3": rr3, "by2": rr2,
                            "p_ge3": float((k >= 3).mean()), "p_ge2": float((k >= 2).mean())}
    # either-scorer pairs: lead back + top pass-catcher of the same team (singles hedge)
    pairs = []
    for t, q in ok.groupby("team"):
        r = q[q.pos_group == "RB"].sort_values("p_attd", ascending=False).head(1); c = q[q.pos_group.isin(["WR", "TE"])].sort_values("p_attd", ascending=False).head(1)
        if len(r) and len(c):
            two = pd.concat([r, c]).reset_index(drop=True); hit = _sim(two, corr, n=100000)
            pairs.append({"team": t, "back": r.iloc[0], "catcher": c.iloc[0], "p_either": float(hit.any(1).mean()), "p_both": float(hit.all(1).mean())})
    H["pairs"] = sorted(pairs, key=lambda x: -x["p_either"])
    # shootout doubles: best opposite-team pair in each game
    sh = []
    for gid, q in ok.groupby("game_id"):
        best = None
        for i, j in combinations(range(min(len(q), 8)), 2):
            two = q.sort_values("p_attd", ascending=False).iloc[[i, j]]
            if two.team.nunique() < 2: continue
            pj = joint(two, corr)
            if best is None or pj > best["p"]: best = {"game": gid, "legs": two, "p": pj, "p_indep": float(two.p_attd.prod())}
        if best: sh.append(best)
    H["shootout"] = sorted(sh, key=lambda x: -x["p"])
    board = W[W.p_attd >= 0.25].sort_values("p_attd", ascending=False)
    return {"games": games, "versions": V, "hedges": H, "board": board, "held": held, "bq": bq, "W": W}
