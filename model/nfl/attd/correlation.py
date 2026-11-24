"""Empirical leg-correlation model for ATTD parlays (Gaussian copula).

Each leg i hits when latent Z_i < Phi^-1(p_i).  Z ~ N(0, Sigma), with Sigma_ij determined by the
relationship between the two players (same team & position pair, or opponents in the same game).
Correlations are estimated by maximum likelihood on out-of-sample predicted marginals and realized
outcomes, then shrunk toward their parent class by sample size.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

_GL_X, _GL_W = np.polynomial.legendre.leggauss(24)


def bvn_cdf(a, b, rho):
    """Phi2(a, b; rho) via Plackett's identity, vectorized (rho scalar or array, |rho| < 0.95)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    rho = np.broadcast_to(np.asarray(rho, float), a.shape)
    base = norm.cdf(a) * norm.cdf(b)
    t = (_GL_X[:, None] + 1) / 2 * rho[None, :]          # nodes on [0, rho]
    w = _GL_W[:, None] * rho[None, :] / 2
    den = 1 - t ** 2
    f = np.exp(-(a ** 2 - 2 * t * a * b + b ** 2) / (2 * den)) / (2 * np.pi * np.sqrt(den))
    return base + (w * f).sum(0)


def pair_key(pos_a, pos_b, same_team):
    if not same_team:
        return "OPP"
    a, b = sorted([pos_a, pos_b])
    return f"TM:{a}-{b}"


def _pairs(out: pd.DataFrame, pmin=0.04):
    d = out[out.p > pmin][["game_id", "team", "pos_group", "p", "label"]].reset_index(drop=True)
    d["i"] = d.index
    pr = d.merge(d, on="game_id")
    pr = pr[pr.i_x < pr.i_y]
    pr["same"] = pr.team_x == pr.team_y
    pr["key"] = [pair_key(a, b, s) for a, b, s in zip(pr.pos_group_x, pr.pos_group_y, pr.same)]
    return pr


def _mle_rho(q, grid=np.linspace(-0.35, 0.45, 81)):
    a, b = norm.ppf(q.p_x.clip(1e-4, 1 - 1e-4)), norm.ppf(q.p_y.clip(1e-4, 1 - 1e-4))
    yx, yy = q.label_x.values, q.label_y.values
    best, ll_best = 0.0, -np.inf
    for r in grid:
        p11 = bvn_cdf(a, b, r)
        p10, p01 = q.p_x.values - p11, q.p_y.values - p11
        p00 = 1 - q.p_x.values - q.p_y.values + p11
        P = np.where(yx == 1, np.where(yy == 1, p11, p10), np.where(yy == 1, p01, p00))
        ll = np.log(np.clip(P, 1e-9, 1)).sum()
        if ll > ll_best:
            best, ll_best = r, ll
    return float(best)


def fit_correlations(out: pd.DataFrame, k_shrink=1500) -> dict:
    pr = _pairs(out)
    rho_tm = _mle_rho(pr[pr.same])
    rho_opp = _mle_rho(pr[~pr.same])
    res = {"OPP": rho_opp, "TM:default": rho_tm, "_n": {}}
    for k, q in pr[pr.same].groupby("key"):
        r = _mle_rho(q)
        w = len(q) / (len(q) + k_shrink)
        res[k] = w * r + (1 - w) * rho_tm
        res["_n"][k] = int(len(q))
    res["_n"]["OPP"] = int((~pr.same).sum())
    return res


def save(c, path: Path):
    path.write_text(json.dumps(c, indent=2))


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def build_sigma(legs: pd.DataFrame, corr: dict) -> np.ndarray:
    n = len(legs)
    S = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            li, lj = legs.iloc[i], legs.iloc[j]
            if li.game_id != lj.game_id:
                continue
            k = pair_key(li.pos_group, lj.pos_group, li.team == lj.team)
            S[i, j] = S[j, i] = corr.get(k, corr["TM:default"] if k != "OPP" else corr["OPP"])
    # project to nearest PSD correlation matrix if needed
    w, V = np.linalg.eigh(S)
    if w.min() < 1e-6:
        S = V @ np.diag(np.clip(w, 1e-6, None)) @ V.T
        d = np.sqrt(np.diag(S))
        S = S / np.outer(d, d)
    return S


def joint_prob(p: np.ndarray, S: np.ndarray, n_sims=400_000, seed=7) -> float:
    """P(all legs hit) under the Gaussian copula."""
    if len(p) == 1:
        return float(p[0])
    if len(p) == 2:
        a = norm.ppf(np.clip(p, 1e-6, 1 - 1e-6))
        return float(bvn_cdf(a[:1], a[1:], S[0, 1])[0])
    rng = np.random.default_rng(seed)
    L = np.linalg.cholesky(S)
    Z = rng.standard_normal((n_sims, len(p))) @ L.T
    return float(np.mean(np.all(Z < norm.ppf(np.clip(p, 1e-6, 1 - 1e-6)), axis=1)))


# ============================================================================================
# Multi-market legs (props + ATD) — residual correlations by relationship and market
# ============================================================================================
def pit_from_curve(C: pd.DataFrame) -> pd.DataFrame:
    """Mid-PIT of the observed outcome under the model's exceedance curve -> normal score z.
    C: long frame with [game_id, player_id, market, k, p, x]."""
    out = []
    for (g, pid, mk), q in C.groupby(["game_id", "player_id", "market"], sort=False):
        ks, S = q.k.values, q.p.values
        step = ks[1] - ks[0] if len(ks) > 1 else 1
        kk = np.concatenate([[ks[0] - step], ks, [ks[-1] + step]])
        SS = np.concatenate([[min(1.0, S[0] + (1 - S[0]) * 0.8)], S, [S[-1] * 0.5]])
        x = q.x.iloc[0]
        s_x, s_x1 = np.interp(x, kk, SS, left=1.0, right=0.0), np.interp(x + step, kk, SS, left=1.0, right=0.0)
        u = 1 - 0.5 * (s_x + s_x1)
        out.append((g, pid, mk, float(np.clip(u, 0.005, 0.995))))
    r = pd.DataFrame(out, columns=["game_id", "player_id", "market", "u"])
    r["z"] = norm.ppf(r.u)
    return r


def pit_binary(p, y):
    u = np.where(y == 1, 1 - p / 2, (1 - p) / 2)
    return norm.ppf(np.clip(u, 0.005, 0.995))


def leg_key(a_pos, a_mk, b_pos, b_mk, rel):
    x, y = sorted([f"{a_mk}@{a_pos}", f"{b_mk}@{b_pos}"])
    return f"{rel}|{x}|{y}"


def fit_multi_correlations(Z: pd.DataFrame, k_shrink=150) -> dict:
    """Z: [game_id, team, player_id, pos_group, market, z]. Returns {key: rho, '_rel': {...}, '_n': {...}}."""
    Z = Z.reset_index(drop=True).assign(i=lambda d: d.index)
    P = Z.merge(Z, on="game_id")
    P = P[P.i_x < P.i_y]
    P = P[~((P.player_id_x == P.player_id_y) & (P.market_x == P.market_y))]
    P["rel"] = np.where(P.player_id_x == P.player_id_y, "SELF", np.where(P.team_x == P.team_y, "TM", "OPP"))
    P["key"] = [leg_key(a, b, c, d, r) for a, b, c, d, r in
                zip(P.pos_group_x, P.market_x, P.pos_group_y, P.market_y, P.rel)]
    res, n = {}, {}
    rel_mean = {r: float(np.corrcoef(g.z_x, g.z_y)[0, 1]) for r, g in P.groupby("rel")}
    for k, g in P.groupby("key"):
        r = float(np.corrcoef(g.z_x, g.z_y)[0, 1]) if len(g) > 20 else 0.0
        prior = 0.0 if k.startswith("OPP") or k.startswith("TM") else rel_mean.get("SELF", 0.3)
        w = len(g) / (len(g) + k_shrink)
        res[k] = round(w * r + (1 - w) * prior, 4)
        n[k] = int(len(g))
    res["_rel"], res["_n"] = rel_mean, n
    return res


def leg_sigma(legs: pd.DataFrame, corr: dict) -> np.ndarray:
    """legs: [game_id, team, player_id, pos_group, market]. Cross-game = 0."""
    n = len(legs)
    S = np.eye(n)
    L = legs.reset_index(drop=True)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = L.iloc[i], L.iloc[j]
            if a.game_id != b.game_id:
                continue
            rel = "SELF" if a.player_id == b.player_id else ("TM" if a.team == b.team else "OPP")
            k = leg_key(a.pos_group, a.market, b.pos_group, b.market, rel)
            S[i, j] = S[j, i] = corr.get(k, 0.0 if rel != "SELF" else corr["_rel"].get("SELF", 0.3))
    w, V = np.linalg.eigh(S)
    if w.min() < 1e-6:
        S = V @ np.diag(np.clip(w, 1e-6, None)) @ V.T
        d = np.sqrt(np.diag(S))
        S = S / np.outer(d, d)
    return S


def ticket_prob(legs: pd.DataFrame, corr: dict, n_sims=200_000, seed=11) -> float:
    """Joint hit probability: copula within each game, independent across games."""
    pj = 1.0
    for _, G in legs.groupby("game_id"):
        pj *= joint_prob(G.p.values, leg_sigma(G, corr), n_sims=n_sims, seed=seed)
    return pj
