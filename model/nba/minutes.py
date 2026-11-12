"""Minutes and role model.

Minutes are a distribution, and they depend on how the game goes. The model has four parts:

1. Expected minutes in an ordinary game: baseline (season, last 10, last 5) moved by teammate in/out,
   back-to-backs, three-in-four, travel, the return-from-injury ramp and foul risk. Coefficients are fitted.
2. Game state: how the first three quarters and the fourth quarter stretch or shrink for starters, bench
   and fringe players given the margin entering the fourth. A team's own habit (its coach's) is added on
   top, shrunk toward the league. Sources carry no coach name, so the team stands in for the coach and a
   mid-stream coaching change is not seen.
3. Spread: the real distribution of actual / expected minutes, kept separately for games with foul
   trouble (5+ fouls), drawn with each player's own foul-trouble probability against tonight's opponent.
4. Team total: minutes in each simulated game add up to 240 plus overtime.

Everything is conditional on the player taking the floor. Whether he plays at all is the availability gate's job.
Not modelled, because no source supplies it: age (so "older players" load management is not a factor;
each player's own back-to-back history is) and stated minutes restrictions before 2026-27.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.linear_model import LogisticRegression, Ridge

from nba.config import CONFIG

ROLES = ["starter", "bench", "fringe"]
X_COLS = ["io_min", "b2b", "three_in_four", "long_trip", "ret0", "ret1", "ret2", "ret3", "ret4", "base_c", "start_share",
          "heavy_b2b", "questionable", "foul_risk", "own_b2b_hist"]


def role_of(start_share, exp_min, cfg=CONFIG):
    return np.where(start_share >= cfg["role_starter_share"], 0, np.where(exp_min >= cfg["role_rotation_min"], 1, 2))


def bucket(margin, edges):
    return np.clip(np.searchsorted(np.array(edges[1:-1]), margin, side="right"), 0, len(edges) - 2)


def design(P: pd.DataFrame, T: pd.DataFrame, L: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Add the minutes model's inputs to the master player frame."""
    P = P.copy()
    P["start_share"] = (P.l5_starter / P.l5_n.replace(0, np.nan)).fillna((P.prev_starter / P.prev_n.replace(0, np.nan))).fillna(0)
    P["long_trip"] = (P.travel_miles.fillna(0) >= 1500).astype(int)
    for k in range(5):
        P[f"ret{k}"] = (P.ret_games == k).astype(int)
    P["base_c"] = (P.base_min.fillna(0) - 24) / 10
    P["heavy_b2b"] = ((P.base_min >= 32) & (P.b2b == 1)).astype(int)
    # foul risk: the player's own foul rate x how often tonight's opponent gets to the line
    lg = L.set_index("date_et")
    lg_pf = (lg.lg_pf / (lg.lg_reg_min * 5).replace(0, np.nan)).reindex(P.date_et).to_numpy()
    lg_fta = (lg.lg_fta / lg.lg_poss.replace(0, np.nan)).reindex(P.date_et).to_numpy()
    k = 400
    pf_rate = (P.s_pf + cfg["last_season_weight"] * P.prev_pf + k * np.nan_to_num(lg_pf, nan=0.085)) / \
              (P.s_min + cfg["last_season_weight"] * P.prev_min + k)
    opp = T.set_index(["game_id", "team_id"])
    o_fta = ((opp.ts_fta + opp.tp_fta * 0.3) / (opp.ts_poss + opp.tp_poss * 0.3).replace(0, np.nan))
    idx = pd.MultiIndex.from_arrays([P.game_id, P.opp_id])
    opp_idx = (o_fta.reindex(idx).to_numpy() / lg_fta)
    P["pf_rate"] = pf_rate
    P["opp_foul_idx"] = np.clip(np.nan_to_num(opp_idx, nan=1.0), 0.8, 1.25)
    P["foul_risk"] = (P.pf_rate * 36 * P.opp_foul_idx - 3.0).clip(-2, 3)
    # the player's own history on back-to-backs is only used when tonight is one
    P["own_b2b_hist"] = 0.0
    q = (P.s_sec_q4 + 0.24 * 60 * 150) / (P.s_min * 60 + 60 * 150)
    P["q4_share"] = q.clip(0.10, 0.34)
    return P


def play_design(D: pd.DataFrame) -> np.ndarray:
    """Inputs for "does he play tonight": minutes level, share of team games played, played the last game, listed questionable."""
    team_n = D.groupby(["game_id", "team_id"]).s_n.transform("max").replace(0, np.nan)
    share = (D.s_n / team_n).fillna(0.5).clip(0, 1)
    recent = (D.days_since_played.fillna(99) <= D.rest_days.fillna(1) + 1.6).astype(float)
    b = D.base_min.fillna(0)
    return np.c_[b / 10, np.minimum(b, 12) / 10, share, recent, D.questionable.fillna(0), D.report_filed.fillna(0)]


@dataclass
class MinutesModel:
    coef: np.ndarray = None
    intercept: float = 1.0
    q123: np.ndarray = None           # [role, q4-entry bucket] multiplier on quarters 1-3
    q4: np.ndarray = None             # [role, q4-entry bucket] multiplier on the fourth quarter
    by_final: np.ndarray = None       # [role, final-margin bucket] multiplier on total minutes
    team_q4: dict = field(default_factory=dict)   # (team_id, "lead"/"trail") -> extra multiplier for starters
    pools: dict = field(default_factory=dict)     # (role, foul_trouble) -> sorted ratios
    foul_scale: float = 1.0
    play: object = None               # chance a listed player takes the floor at all
    cfg: dict = None

    def play_prob(self, D: pd.DataFrame) -> np.ndarray:
        return self.play.predict_proba(play_design(D))[:, 1]

    def expected(self, D: pd.DataFrame) -> np.ndarray:
        X = D[X_COLS].fillna(0).to_numpy(float)
        ratio = np.clip(self.intercept + X @ self.coef, 0.3, 1.8)
        e = D.base_min.fillna(0).to_numpy() * ratio
        cap = D.get("minutes_restriction")
        if cap is not None:
            c = pd.to_numeric(cap, errors="coerce").to_numpy()
            e = np.where(c > 0, np.minimum(e, c), e)
        return np.clip(e, 0, 42)

    def foul_trouble_prob(self, D: pd.DataFrame, e0: np.ndarray) -> np.ndarray:
        lam = D.pf_rate.to_numpy() * D.opp_foul_idx.to_numpy() * e0
        return np.clip((1 - poisson.cdf(4, lam)) * self.foul_scale, 0, 0.6)

    def state_mult(self, role: np.ndarray, q4_share: np.ndarray, team_id, q4_entry: np.ndarray) -> np.ndarray:
        """Multiplier on expected minutes for each simulated game. Returns (n_sims, n_players)."""
        b = bucket(q4_entry, self.cfg["q4_entry_buckets"])                       # (N,)
        m123 = self.q123[role[None, :], b[:, None]]
        m4 = self.q4[role[None, :], b[:, None]].copy()
        lead = self.team_q4.get((team_id, "lead"), 1.0)
        trail = self.team_q4.get((team_id, "trail"), 1.0)
        big = self.cfg["blowout_q4_lead"]
        st = (role == 0)[None, :]
        m4 = np.where(st & (q4_entry[:, None] >= big), m4 * lead, m4)
        m4 = np.where(st & (q4_entry[:, None] <= -big), m4 * trail, m4)
        return (1 - q4_share[None, :]) * m123 + q4_share[None, :] * m4

    def given_final_margin(self, role: int, margin: float) -> float:
        return float(self.by_final[role, bucket(np.array([margin]), self.cfg["margin_buckets"])[0]])

    def simulate(self, D: pd.DataFrame, q4_entry: np.ndarray, ot: np.ndarray, rng) -> dict:
        """Minutes for one team's players in every simulated game. D: that team's players expected to play."""
        e0 = D.e_min.to_numpy()
        role = D.role_i.to_numpy()
        mult = self.state_mult(role, D.q4_share.to_numpy(), D.team_id.iloc[0], q4_entry)
        N, n = mult.shape
        pft = D.p_foul.to_numpy()
        ft = rng.random((N, n)) < pft[None, :]
        u = rng.random((N, n))
        noise = np.empty((N, n))
        for r in range(3):
            cols = np.where(role == r)[0]
            if not len(cols):
                continue
            for flag in (0, 1):
                pool = self.pools[(r, flag)]
                sel = ft[:, cols] == bool(flag)
                vals = pool[np.minimum((u[:, cols] * len(pool)).astype(int), len(pool) - 1)]
                noise[:, cols] = np.where(sel, vals, noise[:, cols]) if flag else vals
        m = e0[None, :] * mult * noise
        if "p_play" in D:
            m = m * (rng.random((N, n)) < D.p_play.to_numpy()[None, :])
        target = 240.0 + 25.0 * ot
        cap = (48.0 + 5.0 * ot)[:, None]
        # bring each simulated game to 240: a surplus comes mostly off the bench, a shortfall is shared by all
        sw = D.squeeze_w.to_numpy()[None, :] if "squeeze_w" in D else 1.0
        for _ in range(3):
            over = m.sum(1) - target
            w = m * np.where(over[:, None] > 0, sw, 1.0)
            m = np.clip(m - over[:, None] * w / np.maximum(w.sum(1), 1e-9)[:, None], 0, cap)
        for _ in range(3):
            m = np.minimum(m * (target / np.maximum(m.sum(1), 1e-9))[:, None], cap)
        q4m = e0[None, :] * D.q4_share.to_numpy()[None, :] * self.q4[role[None, :], bucket(q4_entry, self.cfg["q4_entry_buckets"])[:, None]]
        return {"minutes": m, "foul_trouble": ft, "q4_minutes": q4m}


def fit(D: pd.DataFrame, cfg=CONFIG) -> MinutesModel:
    """D: designed frame restricted to training games, played rows."""
    listed = D[(D.exp_out == 0) & D.base_min.notna() & (D.pending == 0)]
    play = LogisticRegression(C=1.0, max_iter=500).fit(play_design(listed), listed.played)
    d = D[(D.played == 1) & (D.base_min >= 5) & D.q4_entry.notna()].copy()
    y = (d["min"] / d.base_min).clip(0, 2.5)
    reg = Ridge(alpha=5.0).fit(d[X_COLS].fillna(0), y, sample_weight=d.base_min)
    M = MinutesModel(coef=reg.coef_, intercept=float(reg.intercept_), cfg=cfg, play=play)
    d["e0"] = M.expected(d)
    d["role_i"] = role_of(d.start_share, d.e0, cfg)
    d = d[d.sec_q4.notna()]
    b = bucket(d.q4_entry.to_numpy(), cfg["q4_entry_buckets"])
    nb = len(cfg["q4_entry_buckets"]) - 1
    e4 = d.e0 * d.q4_share
    e123 = d.e0 * (1 - d.q4_share)
    a4 = d.sec_q4 / 60
    a123 = (d["min"] - d.sec_q4 / 60).clip(lower=0)      # includes any overtime minutes
    M.q4, M.q123 = np.ones((3, nb)), np.ones((3, nb))
    for r in range(3):
        for k in range(nb):
            s = (d.role_i == r) & (b == k)
            if s.sum() > 50:
                M.q4[r, k] = a4[s].sum() / e4[s].sum()
                M.q123[r, k] = a123[s].sum() / e123[s].sum()
    fb = bucket(d.margin.to_numpy(), cfg["margin_buckets"])
    nf = len(cfg["margin_buckets"]) - 1
    M.by_final = np.ones((3, nf))
    for r in range(3):
        for k in range(nf):
            s = (d.role_i == r) & (fb == k)
            if s.sum() > 50:
                M.by_final[r, k] = d["min"][s].sum() / d.e0[s].sum()
    # team (coach) habit for starters in fourth quarters that start as blowouts
    big, prior = cfg["blowout_q4_lead"], cfg["team_effect_prior_games"]
    st = d[d.role_i == 0]
    lg4 = M.q4[0, bucket(st.q4_entry.to_numpy(), cfg["q4_entry_buckets"])]
    st = st.assign(exp4=(st.e0 * st.q4_share) * lg4, act4=st.sec_q4 / 60)
    for side, mask in (("lead", st.q4_entry >= big), ("trail", st.q4_entry <= -big)):
        g = st[mask].groupby("team_id").agg(a=("act4", "sum"), e=("exp4", "sum"), n=("game_id", "nunique"))
        per_game = (g.e / g.n).mean() if len(g) else 1.0
        for t, r in g.iterrows():
            M.team_q4[(t, side)] = float((r.a + prior * per_game) / (r.e + prior * per_game))
    # spread
    full = M.state_mult_rows(d)
    ratio = (d["min"] / (d.e0 * full).clip(lower=1)).clip(0, 3).to_numpy()
    ftg = (d.pf >= 5).to_numpy()
    for r in range(3):
        for flag in (0, 1):
            v = ratio[(d.role_i.to_numpy() == r) & (ftg == bool(flag))]
            v = v if len(v) >= 200 else ratio[d.role_i.to_numpy() == r]
            M.pools[(r, flag)] = np.quantile(v, np.linspace(0.00125, 0.99875, 400))
    lam = d.pf_rate * d.opp_foul_idx * d.e0
    pred = (1 - poisson.cdf(4, lam)).mean()
    M.foul_scale = float(ftg.mean() / max(pred, 1e-6))
    return M


def _state_mult_rows(self, d: pd.DataFrame) -> np.ndarray:
    b = bucket(d.q4_entry.to_numpy(), self.cfg["q4_entry_buckets"])
    r = d.role_i.to_numpy()
    q = d.q4_share.to_numpy()
    m4 = self.q4[r, b].copy()
    big = self.cfg["blowout_q4_lead"]
    lead = np.array([self.team_q4.get((t, "lead"), 1.0) for t in d.team_id])
    trail = np.array([self.team_q4.get((t, "trail"), 1.0) for t in d.team_id])
    m4 = np.where((r == 0) & (d.q4_entry.to_numpy() >= big), m4 * lead, m4)
    m4 = np.where((r == 0) & (d.q4_entry.to_numpy() <= -big), m4 * trail, m4)
    return (1 - q) * self.q123[r, b] + q * m4


MinutesModel.state_mult_rows = _state_mult_rows


def apply(M: MinutesModel, D: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Pre-game minutes inputs for target rows: expected minutes (team reconciled to 240), role, foul risk, flags."""
    D = D.copy()
    D["e_min"] = M.expected(D)
    D.loc[D.exp_out == 1, "e_min"] = 0.0
    D["p_play"] = np.where(D.exp_out == 1, 0.0, M.play_prob(D))
    # Expected minutes are "if he plays"; the team's 240 are shared among those who do. The gap between the
    # listed players' total and 240 is absorbed mostly by players with little evidence this season (their
    # baseline still leans on last season's role), so an established starter is not shaved because the
    # bench's numbers are stale. (Letting the whole bench absorb it first was tried and rejected: it made
    # sixth men 2 minutes too high.)
    key = [D.game_id, D.team_id]
    k = cfg["min_prior_games"]
    unsure = cfg["reconcile_floor"] + (k / (D.s_n.fillna(0) + k)) ** 2
    ep = D.e_min * D.p_play
    excess = ep.groupby(key).transform("sum") - 240.0
    # when the listed minutes are too many, an established starter gives up little; when too few, everyone shares
    shield = np.where((D.start_share >= cfg["role_starter_share"]) & (D.s_n.fillna(0) >= 5), 1 - cfg["reconcile_starter_shield"], 1.0)
    unsure = np.where(excess > 0, unsure * shield, unsure)
    D["squeeze_w"] = shield
    lam = excess / (ep * unsure).groupby(key).transform("sum").replace(0, np.nan)
    D["e_min"] *= (1 - lam.fillna(0) * unsure).clip(0.5, 1.3)
    tot = (D.e_min * D.p_play).groupby(key).transform("sum")
    D["e_min"] *= (240.0 / tot.replace(0, np.nan)).clip(0.9, 1.1).fillna(1.0)
    D["e_min"] = D.e_min.clip(upper=41.5)
    D["role_i"] = role_of(D.start_share, D.e_min, cfg)
    D["p_foul"] = M.foul_trouble_prob(D, D.e_min.to_numpy())
    sixth = (D.role_i == 1) & (D.e_min >= cfg["role_sixth_min"])
    D["role"] = np.where(D.role_i == 0, "starter", np.where(sixth, "sixth man", np.where(D.role_i == 1, "rotation", "fringe")))
    s_avg = D.s_min / D.s_n.replace(0, np.nan)
    l5 = D.l5_min / D.l5_n.replace(0, np.nan)
    s_start = (D.s_starter / D.s_n.replace(0, np.nan))
    reasons = []
    for r in D[["io_min", "io_notes", "ret_games", "start_share"]].assign(d5=(l5 - s_avg), ss=s_start).itertuples():
        why = []
        if abs(r.io_min) >= 0.08 and r.io_notes:
            why.append(r.io_notes.split(";")[0].split(":")[0])
        if r.ret_games < cfg["return_ramp_games"]:
            why.append(f"game {int(r.ret_games) + 1} back from an absence")
        if pd.notna(r.ss) and abs(r.start_share - r.ss) >= 0.5:
            why.append("moved into the starting five" if r.start_share > r.ss else "moved to the bench")
        if pd.notna(r.d5) and abs(r.d5) >= cfg["role_change_minutes"]:
            why.append(f"last-5 minutes {r.d5:+.0f} vs season")
        reasons.append("; ".join(why))
    D["role_change_reason"] = reasons
    D["role_change"] = (D.role_change_reason != "").astype(int)
    return D
