"""Game-market model: moneylines, spreads, totals, interceptions and hybrid same-game parlays.

How it works, in order:

1. Ratings. Every week, each team gets opponent-adjusted ratings from games played before
   that week (recent games weighted more): efficiency (EPA per play, passing and rushing),
   success rate, points, pace, plays, time of possession, interception rate and penalties.
   Quarterbacks get their own rating, so a change of starter moves the forecast.
2. Fundamentals. A ridge regression turns those ratings, plus rest, home field, division
   games and weather, into a forecast of the margin and the total. It never sees the line.
3. Market blend. The closing line is a better forecast than any public model, so the final
   number is the line moved a fraction of the way toward the fundamentals. That fraction is
   fitted only on earlier seasons.
4. Probabilities, tickets and hybrids are built from the blended numbers.

Everything is scored walk-forward: a season is always forecast by models fitted on earlier
seasons only. The scorecard is written next to the picks.

Usage: python3 game_markets.py      (needs data/cache from features.py)
Writes output/game_markets.json.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import multivariate_normal, norm
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.preprocessing import StandardScaler

from features import CACHE, load_games
from matchups import UNIT_STATS
from nfl_model import run as elo_run

HERE = Path(__file__).parent
CONSOLE_DATA = HERE.parent / "public" / "console" / "data.js"

RATED = ["off_epa", "pass_epa", "rush_epa", "success", "points", "plays", "dropbacks",
         "sec_per_play", "sec_per_drive", "int_rate", "off_pen", "def_pen"]
J = {m: i for i, m in enumerate(RATED)}
HALF_LIFE, RIDGE, WINDOW = 16, 15, 90   # weeks; WINDOW is about three seasons
WEEKS_PER_SEASON = 30
FIRST_FUNDAMENTALS = 2018               # first season forecast by the fundamentals model
TEST_FROM = 2020                        # first season scored with the market blend
BREAK_EVEN_110 = 110 / 210

MARGIN_FEATURES = {
    "m_epa": "overall offence-versus-defence efficiency",
    "m_pass": "passing matchup",
    "m_rush": "rushing matchup",
    "m_success": "down-to-down success rate",
    "m_points": "scoring versus points allowed",
    "m_elo": "results-based team rating",
    "m_qb": "quarterback versus the team's usual starter",
    "m_top": "time of possession",
    "m_int": "interception risk",
    "m_pen": "penalties",
    "m_rest": "rest days",
    "m_home": "home field",
    "m_div": "division game",
    "m_homesplit": "each team's own home and road form",
    "m_run_in": "inside runs against the defensive front",
    "m_run_out": "outside runs against the edge",
    "m_stuff": "runs stuffed at the line",
    "m_explosive": "explosive runs",
    "m_wr_deep": "receivers deep against safeties and outside corners",
    "m_wr_mid": "receivers in the slot area against nickel and linebackers",
    "m_wr_out": "receivers short outside against corners",
    "m_te": "tight ends against linebackers and safeties",
    "m_rbrec": "backs as receivers",
    "m_protect": "pass protection against the pass rush",
    "m_scheme": "play-calling aimed at the opponent's weak side",
    "m_ol": "offensive line starters out",
    "m_olcont": "offensive line continuity",
    "m_def_out": "defensive starters out",
    "m_skill_out": "skill starters out",
}
# The seven checks every moneyline and spread pick must carry, and the inputs behind each.
CHECKS = {
    "Home vs away": ["m_homesplit"],
    "Personnel": ["m_qb", "m_ol", "m_olcont", "m_def_out", "m_skill_out"],
    "Offensive play-calling": ["m_scheme"],
    "Defensive play-calling and pressure": ["m_protect", "m_int"],
    "Running backs vs defensive line, with line health": ["m_run_in", "m_run_out", "m_stuff", "m_explosive", "m_ol"],
    "Receivers: deep, slot area, outside": ["m_wr_deep", "m_wr_mid", "m_wr_out"],
    "Tight ends vs linebackers and safeties": ["m_te"],
}
CHECK_INPUTS = sorted({f for fs in CHECKS.values() for f in fs})
SAFE_MIN_P = 0.65
ALT_OFFSETS = [-7.0, -3.0, 3.0, 7.0, 10.0]
TOTAL_FEATURES = {
    "t_points": "both teams' scoring and points allowed",
    "t_epa": "combined offensive efficiency",
    "t_pass": "combined passing efficiency",
    "t_pace": "pace of play",
    "t_plays": "expected play count",
    "t_qb": "quarterback changes",
    "t_int": "interception risk",
    "t_pen": "penalties",
    "t_top": "long drives",
    "t_wind": "wind",
    "t_indoor": "indoor game",
    "t_cold": "cold weather",
    "t_proe": "how often both offences choose to pass",
    "t_deep": "deep passing by both offences",
    "t_nohuddle": "no-huddle tempo",
    "t_pressure": "pass rush on both quarterbacks",
    "t_out": "offensive starters out",
}


def dec(american: float) -> float:
    return 1 + american / 100 if american > 0 else 1 + 100 / -american


def american(p: float) -> int:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def american_from_dec(d: float) -> int:
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))


# ----------------------------------------------------------------------------- ratings

def fit_ratings(train: pd.DataFrame, now: int, ix: dict) -> np.ndarray:
    """Weighted ridge fit of  stat = league + own[team] + faced[opp] + home_edge  for every rated stat at once."""
    n, k = len(train), len(ix)
    X = np.zeros((n, 2 * k + 2))
    X[:, 0] = 1
    X[:, 1] = train.home.values - 0.5
    X[np.arange(n), 2 + train.team.map(ix).values] = 1
    X[np.arange(n), 2 + k + train.opp.map(ix).values] = 1
    w = 0.5 ** ((now - train.t.values) / HALF_LIFE)
    pen = np.full(2 * k + 2, float(RIDGE))
    pen[:2] = 0
    A = X.T @ (X * w[:, None]) + np.diag(pen)
    return np.linalg.solve(A, X.T @ (train[RATED].values * w[:, None]))


def fit_units(train: pd.DataFrame, now: int, ix: dict) -> dict:
    """The same fit for each matchup stat, with every game weighted by the plays behind its number."""
    n, k = len(train), len(ix)
    X = np.zeros((n, 2 * k + 2))
    X[:, 0] = 1
    X[:, 1] = train.home.values - 0.5
    X[np.arange(n), 2 + train.team.map(ix).values] = 1
    X[np.arange(n), 2 + k + train.opp.map(ix).values] = 1
    decay = 0.5 ** ((now - train.t.values) / HALF_LIFE)
    pen = np.full(2 * k + 2, float(RIDGE))
    pen[:2] = 0
    out = {}
    for stat in UNIT_STATS:
        y, cnt = train[stat].values, train[stat + "_n"].values
        ok = ~np.isnan(y) & (cnt > 0)
        if ok.sum() < 200:
            out[stat] = None
            continue
        w = decay[ok] * cnt[ok] / cnt[ok].mean()
        Xo = X[ok]
        out[stat] = np.linalg.solve(Xo.T @ (Xo * w[:, None]) + np.diag(pen), Xo.T @ (w * y[ok]))
    return out


def unit_expect(U, ix, stat, team, opp, home):
    c = U.get(stat)
    if c is None:
        return np.nan
    return c[0] + c[1] * (home - 0.5) + c[2 + ix[team]] + c[2 + len(ix) + ix[opp]]


def home_splits(train: pd.DataFrame, now: int) -> dict:
    """How much better each team has played at home than on the road lately, shrunk toward zero."""
    r = train[(train.t >= now - 60) & train.home.isin([0.0, 1.0])]
    g = r.groupby(["team", "home"]).net_epa.agg(["mean", "size"]).unstack("home")
    out = {}
    for team in g.index:
        try:
            mh, ma, nh, na = g.loc[team, ("mean", 1.0)], g.loc[team, ("mean", 0.0)], g.loc[team, ("size", 1.0)], g.loc[team, ("size", 0.0)]
        except KeyError:
            continue
        if not (pd.isna(mh) or pd.isna(ma)):
            m = min(nh, na)
            out[team] = float((mh - ma) * m / (m + 16))
    return out


def expect(C, ix, stat, team, opp, home):
    k, j = len(ix), J[stat]
    return C[0, j] + C[1, j] * (home - 0.5) + C[2 + ix[team], j] + C[2 + k + ix[opp], j]


def qb_state(qb: pd.DataFrame, now: int):
    """Shrunk quarterback ratings from games before `now`, and each team's recent-starter baseline."""
    past = qb[qb.t < now]
    w = 0.5 ** ((now - past.t.values) / 40)
    g = pd.DataFrame({"qb": past.qb_id.values, "db": past.dropbacks.values * w,
                      "epa": past.epa.values * w, "ints": past.ints.values * w}).groupby("qb").sum()
    lg_epa, lg_int = g.epa.sum() / g.db.sum(), g.ints.sum() / g.db.sum()
    unknown = lg_epa - 0.08  # a passer with no record is usually a backup or a rookie
    rating = (g.epa + 150 * unknown) / (g.db + 150)
    int_rate = (g.ints + 300 * lg_int) / (g.db + 300)
    recent = past[past.t >= now - 60]
    wr = pd.Series(0.5 ** ((now - recent.t.values) / HALF_LIFE), index=recent.index)
    r = recent.qb_id.map(rating).fillna(unknown)
    base = (r * wr).groupby(recent.team).sum() / wr.groupby(recent.team).sum()
    return rating, int_rate, base, unknown, lg_int


def build_game_table():
    """One row per game (played games since 2016 plus the next unplayed week) with every model input."""
    tg = pd.read_csv(CACHE / "team_games.csv")
    tg = tg.merge(pd.read_csv(CACHE / "unit_games.csv"), on=["game_id", "team"], how="left")
    opp_epa = tg[["game_id", "team", "off_epa"]].rename(columns={"team": "opp", "off_epa": "opp_off_epa"})
    tg = tg.merge(opp_epa, on=["game_id", "opp"], how="left")
    tg["net_epa"] = tg.off_epa - tg.opp_off_epa
    pers_df = pd.read_csv(CACHE / "personnel.csv").fillna({"ol_out_names": "", "def_out_names": "", "skill_out_names": ""})
    pers = {(r.game_id, r.team): r for r in pers_df.itertuples(index=False)}
    qb = pd.read_csv(CACHE / "qb_games.csv")
    qb = qb[qb.game_id.isin(tg.game_id)]
    first = int(tg.season.min())
    tg["t"] = (tg.season - first) * WEEKS_PER_SEASON + tg.week
    qb["t"] = (qb.season - first) * WEEKS_PER_SEASON + qb.week
    teams = sorted(tg.team.unique())
    ix = {t: i for i, t in enumerate(teams)}

    games = load_games()
    games = games[games.home_team.isin(teams) & games.away_team.isin(teams)]
    elo = elo_run(games.sort_values(["gameday", "game_id"]).reset_index(drop=True))[["game_id", "model_margin"]]
    games = games.merge(elo, on="game_id")
    games["t"] = (games.season - first) * WEEKS_PER_SEASON + games.week
    played = games[games.result.notna() & games.spread_line.notna() & games.total_line.notna() & (games.season > first)]
    up = games[games.result.isna()].sort_values(["gameday", "game_id"])
    if len(up):
        f = up.iloc[0]
        up = up[(up.season == f.season) & (up.week == f.week)]
    todo = pd.concat([played, up]).sort_values(["t", "game_id"])

    console_wx = {}
    if CONSOLE_DATA.exists():
        D = json.loads(CONSOLE_DATA.read_text(encoding="utf8").strip()[len("const D = "):].rstrip(";"))
        console_wx = {g["id"]: g for g in D["games"]}

    rows, int_rows, detail = [], [], {}
    for t, wk in todo.groupby("t"):
        train = tg[(tg.t < t) & (tg.t >= t - WINDOW)]
        if len(train) < 300:
            continue
        C = fit_ratings(train, t, ix)
        U = fit_units(train, t, ix)
        splits = home_splits(train, t)
        k_ = len(ix)
        own = lambda s, team: np.nan if U.get(s) is None else U[s][0] + U[s][2 + ix[team]]         # this offence against an average defence
        faced = lambda s, team: np.nan if U.get(s) is None else U[s][0] + U[s][2 + k_ + ix[team]]  # an average offence against this defence
        q_rating, q_int, q_base, q_unknown, lg_int = qb_state(qb, t)
        for g in wk.itertuples(index=False):
            h, a = g.home_team, g.away_team
            hm = 0.5 if g.location == "Neutral" else 1.0
            am_ = 1.0 - hm
            e = lambda s, team, opp, home: expect(C, ix, s, team, opp, home)
            off = {s: (e(s, h, a, hm), e(s, a, h, am_)) for s in RATED}
            qh = q_rating.get(g.home_qb_id, q_unknown) - q_base.get(h, q_unknown)
            qa = q_rating.get(g.away_qb_id, q_unknown) - q_base.get(a, q_unknown)
            wx = console_wx.get(g.game_id, {})
            indoor = str(g.roof) in ("dome", "closed") or wx.get("wx") == "indoor"
            wind = g.wind if not pd.isna(g.wind) else wx.get("wind")
            temp = g.temp if not pd.isna(g.temp) else wx.get("temp")
            wind = 0.0 if indoor else (8.0 if wind is None or pd.isna(wind) else float(wind))
            temp = 68.0 if indoor else (55.0 if temp is None or pd.isna(temp) else float(temp))
            rest = 0.0 if pd.isna(g.home_rest) or pd.isna(g.away_rest) else float(np.clip(g.home_rest - g.away_rest, -7, 7))
            d = lambda s: off[s][0] - off[s][1]
            sm = lambda s: off[s][0] + off[s][1]
            u = {s_: (unit_expect(U, ix, s_, h, a, hm), unit_expect(U, ix, s_, a, h, am_)) for s_ in UNIT_STATS}
            ud = lambda s_: u[s_][0] - u[s_][1]
            us = lambda s_: u[s_][0] + u[s_][1]
            ph_, pa_ = pers.get((g.game_id, h)), pers.get((g.game_id, a))
            pv = lambda r, c: np.nan if r is None else float(getattr(r, c))
            lg_pass, lg_rush = C[0, J["pass_epa"]], C[0, J["rush_epa"]]
            fit_side = lambda i, team: (own("proe", team) - U["proe"][0]) * ((off["pass_epa"][i] - lg_pass) - (off["rush_epa"][i] - lg_rush)) if U.get("proe") is not None else np.nan
            if pd.isna(g.result):
                detail[g.game_id] = {}
                for team, opp, i, pr in ((h, a, 0, ph_), (a, h, 1, pa_)):
                    detail[g.game_id][team] = {
                        "venue": "neutral site" if hm == 0.5 else ("home" if team == h else "away"),
                        "home_road_split": splits.get(team),
                        "run_inside": u["run_in_epa"][i], "run_outside": u["run_out_epa"][i], "stuffed": u["stuff_rate"][i],
                        "explosive_run": u["explosive_run"][i],
                        "wr_deep": u["wr_deep_epa"][i], "wr_slot_area": u["wr_mid_epa"][i], "wr_outside": u["wr_out_epa"][i],
                        "te": u["te_epa"][i], "rb_receiving": u["rbrec_epa"][i], "pressure_allowed": u["pressure_rate"][i],
                        "pass_over_expected": own("proe", team), "deep_rate": own("deep_rate", team), "te_share": own("te_share", team),
                        "play_action": own("pa_rate", team), "motion": own("motion_rate", team), "no_huddle": own("nohuddle_rate", team),
                        "red_zone_pass": own("rz_pass_rate", team),
                        "defence_blitz": faced("blitz_rate", team), "defence_box": faced("box", team),
                        "defence_pressure": faced("pressure_rate", team), "defence_deep_allowed": faced("wr_deep_epa", team),
                        "defence_stuff": faced("stuff_rate", team),
                        "ol_out": pv(pr, "ol_out"), "def_out": pv(pr, "def_out"), "skill_out": pv(pr, "skill_out"),
                        "ol_continuity": pv(pr, "ol_continuity"),
                        "out_names": "" if pr is None else "; ".join(x for x in (pr.ol_out_names, pr.def_out_names, pr.skill_out_names) if x),
                    }
            rows.append({
                "game_id": g.game_id, "season": g.season, "week": g.week, "t": t, "gameday": g.gameday,
                "home": h, "away": a, "neutral": hm == 0.5, "result": g.result, "total": g.total,
                "spread_line": g.spread_line, "total_line": g.total_line,
                "home_ml": g.home_moneyline, "away_ml": g.away_moneyline,
                "home_spread_odds": g.home_spread_odds, "away_spread_odds": g.away_spread_odds,
                "over_odds": g.over_odds, "under_odds": g.under_odds,
                "home_qb": g.home_qb_name, "away_qb": g.away_qb_name, "home_qb_id": g.home_qb_id, "away_qb_id": g.away_qb_id,
                "qb_delta_home": qh, "qb_delta_away": qa,
                "m_epa": d("off_epa"), "m_pass": d("pass_epa"), "m_rush": d("rush_epa"), "m_success": d("success"),
                "m_points": d("points"), "m_elo": g.model_margin, "m_qb": qh - qa, "m_top": d("sec_per_drive"),
                "m_int": off["int_rate"][1] - off["int_rate"][0],
                "m_pen": (off["off_pen"][1] + expect(C, ix, "def_pen", a, h, am_)) - (off["off_pen"][0] + expect(C, ix, "def_pen", h, a, hm)),
                "m_rest": rest, "m_home": 0.0 if hm == 0.5 else 1.0, "m_div": float(g.div_game),
                "m_homesplit": 0.0 if hm == 0.5 else (splits.get(h, 0.0) + splits.get(a, 0.0)) / 2,
                "m_run_in": ud("run_in_epa"), "m_run_out": ud("run_out_epa"), "m_stuff": -ud("stuff_rate"),
                "m_explosive": ud("explosive_run"), "m_wr_deep": ud("wr_deep_epa"), "m_wr_mid": ud("wr_mid_epa"),
                "m_wr_out": ud("wr_out_epa"), "m_te": ud("te_epa"), "m_rbrec": ud("rbrec_epa"), "m_protect": -ud("pressure_rate"),
                "m_scheme": fit_side(0, h) - fit_side(1, a),
                "m_ol": pv(pa_, "ol_out") - pv(ph_, "ol_out"), "m_olcont": pv(ph_, "ol_continuity") - pv(pa_, "ol_continuity"),
                "m_def_out": pv(pa_, "def_out") - pv(ph_, "def_out"), "m_skill_out": pv(pa_, "skill_out") - pv(ph_, "skill_out"),
                "t_proe": us("proe"), "t_deep": us("deep_rate"), "t_nohuddle": us("nohuddle_rate"), "t_pressure": us("pressure_rate"),
                "t_out": pv(ph_, "ol_out") + pv(pa_, "ol_out") + pv(ph_, "skill_out") + pv(pa_, "skill_out"),
                "t_points": sm("points"), "t_epa": sm("off_epa"), "t_pass": sm("pass_epa"), "t_pace": -sm("sec_per_play"),
                "t_plays": sm("plays"), "t_qb": qh + qa, "t_int": sm("int_rate"),
                "t_pen": sm("off_pen") + expect(C, ix, "def_pen", h, a, hm) + expect(C, ix, "def_pen", a, h, am_),
                "t_top": sm("sec_per_drive"), "t_wind": wind, "t_indoor": float(indoor), "t_cold": float(temp < 35),
                "proj_home_top": off["sec_per_drive"][0], "proj_away_top": off["sec_per_drive"][1],
            })
            for team, opp, home, qid, qname, sign in ((h, a, hm, g.home_qb_id, g.home_qb_name, 1), (a, h, am_, g.away_qb_id, g.away_qb_name, -1)):
                int_rows.append({
                    "game_id": g.game_id, "season": g.season, "week": g.week, "team": team, "opp": opp,
                    "qb_id": qid, "qb": qname,
                    "i_team_rate": expect(C, ix, "int_rate", team, opp, home),
                    "i_qb_rate": q_int.get(qid, lg_int),
                    "i_dropbacks": expect(C, ix, "dropbacks", team, opp, home),
                    "i_dog": -sign * g.spread_line if not pd.isna(g.spread_line) else 0.0,
                    "i_total": g.total_line if not pd.isna(g.total_line) else 44.0,
                    "i_wind": wind,
                })
    G = pd.DataFrame(rows)
    # A pick needs every matchup input. Rows missing any are kept for fitting (gaps filled with
    # "no edge") but can never become a pick.
    need = CHECK_INPUTS + ["m_run_in", "m_wr_deep", "m_te"]
    G["checks_complete"] = G[need].notna().all(axis=1)
    fill = [c for c in list(MARGIN_FEATURES) + list(TOTAL_FEATURES) if c in G]
    G[fill] = G[fill].fillna(0.0)
    G.attrs["detail"] = detail
    I = pd.DataFrame(int_rows).merge(qb[["game_id", "team", "qb_id", "ints", "dropbacks"]], on=["game_id", "team", "qb_id"], how="left")
    return G, I, tg


# ----------------------------------------------------------------------------- models

def fundamentals(G: pd.DataFrame):
    """Walk-forward ridge forecasts of margin and total that never see the betting line."""
    G["f_margin"], G["f_total"] = np.nan, np.nan
    for i in range(len(CHECKS)):
        G[f"chk_{i}"] = np.nan
    last = {}
    for s in range(FIRST_FUNDAMENTALS, int(G.season.max()) + 1):
        tr = G[(G.season < s) & G.result.notna()]
        te = G.season == s
        if not te.any():
            continue
        for target, feats, out in (("result", list(MARGIN_FEATURES), "f_margin"), ("total", list(TOTAL_FEATURES), "f_total")):
            sc = StandardScaler().fit(tr[feats])
            m = RidgeCV(alphas=np.logspace(0, 4, 20)).fit(sc.transform(tr[feats]), tr[target])
            G.loc[te, out] = m.predict(sc.transform(G.loc[te, feats]))
            last[out] = (sc, m, feats)
        # Each check is the average of its inputs, measured in standard deviations from a typical game.
        mu, sd = tr[CHECK_INPUTS].mean(), tr[CHECK_INPUTS].std().replace(0, 1)
        z = (G.loc[te, CHECK_INPUTS] - mu) / sd
        for i, fs in enumerate(CHECKS.values()):
            G.loc[te, f"chk_{i}"] = z[fs].mean(axis=1)
        G.loc[te & ~G.neutral, "chk_0"] += 0.5   # the venue itself counts toward "Home vs away"
    return last


def blend(G: pd.DataFrame):
    """Move the market line toward the fundamentals by a weight learned on earlier seasons."""
    for c in ["b_margin", "b_total", "sd_margin", "sd_total", "sd_win", "w_margin", "w_total"] + [f"p_alt_{o:g}" for o in ALT_OFFSETS]:
        G[c] = np.nan
    for s in range(TEST_FROM, int(G.season.max()) + 1):
        tr = G[(G.season >= FIRST_FUNDAMENTALS) & (G.season < s) & G.result.notna()]
        te = G.season == s
        if not te.any():
            continue
        dm, dt = tr.f_margin - tr.spread_line, tr.f_total - tr.total_line
        wm = float(np.clip((dm * (tr.result - tr.spread_line)).sum() / (dm ** 2).sum(), 0, 1))
        wt = float(np.clip((dt * (tr.total - tr.total_line)).sum() / (dt ** 2).sum(), 0, 1))
        bm_tr = tr.spread_line + wm * dm
        sd_m = float((tr.result - bm_tr).std())
        sd_t = float((tr.total - (tr.total_line + wt * dt)).std())
        y = (tr.result > 0).astype(float)[tr.result != 0]
        grid = np.arange(10.0, 18.01, 0.25)
        ll = [-(y * np.log(norm.cdf(bm_tr[tr.result != 0] / sd)) + (1 - y) * np.log(1 - norm.cdf(bm_tr[tr.result != 0] / sd))).mean() for sd in grid]
        G.loc[te, "b_margin"] = G.loc[te, "spread_line"] + wm * (G.loc[te, "f_margin"] - G.loc[te, "spread_line"])
        G.loc[te, "b_total"] = G.loc[te, "total_line"] + wt * (G.loc[te, "f_total"] - G.loc[te, "total_line"])
        G.loc[te, ["sd_margin", "sd_total", "sd_win", "w_margin", "w_total"]] = [sd_m, sd_t, float(grid[int(np.argmin(ll))]), wm, wt]
        # Alternative lines use the actual spread of past misses, which keeps the bumps at 3 and 7.
        resid = (tr.result - bm_tr).values
        resid = np.sort(np.concatenate([resid, -resid]))
        G.attrs["resid"] = resid
        bm_te = G.loc[te, "b_margin"].values
        for off in ALT_OFFSETS:
            need = G.loc[te, "spread_line"].values - off          # home must win by more than this
            G.loc[te, f"p_alt_{off:g}"] = 1 - np.searchsorted(resid, need - bm_te, side="right") / len(resid)
    G["p_home_cover"] = norm.cdf((G.b_margin - G.spread_line) / G.sd_margin)
    G["p_over"] = norm.cdf((G.b_total - G.total_line) / G.sd_total)
    G["p_home_win"] = norm.cdf(G.b_margin / G.sd_win)
    ih = G.home_ml.apply(lambda x: np.nan if pd.isna(x) else 1 / dec(x))
    ia = G.away_ml.apply(lambda x: np.nan if pd.isna(x) else 1 / dec(x))
    G["mkt_home_win"] = ih / (ih + ia)


# ----------------------------------------------------------------------------- candidate legs

CHECK_NAMES = list(CHECKS)
PERSONNEL = CHECK_NAMES.index("Personnel")
POSITION_CHECK = {"RB": 4, "QB": 4, "WR": 5, "TE": 6}


def verdict(score: float) -> str:
    return "for" if score >= 0.35 else "against" if score <= -0.35 else "even"


def side_checks(g, home_side: bool):
    """The seven checks from one side's point of view, and how many lean its way."""
    sign = 1 if home_side else -1
    scores = [sign * getattr(g, f"chk_{i}") for i in range(len(CHECK_NAMES))]
    verdicts = [verdict(x) for x in scores]
    net = sum(v == "for" for v in verdicts) - sum(v == "against" for v in verdicts)
    return scores, verdicts, net


def with_checks(leg, g):
    scores, verdicts, net = side_checks(g, leg["home_side"])
    leg["complete"] = bool(g.checks_complete) and not any(pd.isna(x) for x in scores)
    leg["net_checks"] = int(net)
    leg["checks"] = [{"check": n, "score": None if pd.isna(x) else round(float(x), 2), "verdict": v}
                     for n, x, v in zip(CHECK_NAMES, scores, verdicts)]
    leg["safe"] = bool(leg["market"] == "ml" and leg["complete"] and leg["p"] >= SAFE_MIN_P and net >= 2
                       and verdicts[PERSONNEL] != "against")
    return leg


def favourite_legs(wk: pd.DataFrame):
    """Every strong favourite on the moneyline, whether or not its price is good value."""
    out = []
    for g in wk.itertuples(index=False):
        if pd.isna(g.home_ml) or pd.isna(g.away_ml) or pd.isna(g.p_home_win):
            continue
        home = g.p_home_win >= 0.5
        p = g.p_home_win if home else 1 - g.p_home_win
        if p < SAFE_MIN_P:
            continue
        team, opp = (g.home, g.away) if home else (g.away, g.home)
        price = g.home_ml if home else g.away_ml
        fair = g.mkt_home_win if home else 1 - g.mkt_home_win
        out.append(with_checks({"game_id": g.game_id, "market": "ml", "team": team, "opp": opp, "home_side": bool(home),
                                "label": f"{team} moneyline", "p": float(p), "price": int(price), "market_p": float(fair),
                                "edge": float(p - fair), "ev": float(p * dec(price) - 1), "dog": False}, g))
    return out


def price_or(x, default=-110.0):
    return default if x is None or pd.isna(x) else float(x)


def ml_legs(wk: pd.DataFrame):
    """The better-value side of each moneyline, by expected value at the listed price."""
    out = []
    for g in wk.itertuples(index=False):
        if pd.isna(g.home_ml) or pd.isna(g.away_ml) or pd.isna(g.p_home_win):
            continue
        sides = []
        for team, opp, p, price, fair, home in ((g.home, g.away, g.p_home_win, g.home_ml, g.mkt_home_win, True),
                                                (g.away, g.home, 1 - g.p_home_win, g.away_ml, 1 - g.mkt_home_win, False)):
            sides.append({"game_id": g.game_id, "market": "ml", "team": team, "opp": opp, "home_side": home,
                          "label": f"{team} moneyline", "p": float(p), "price": int(price), "market_p": float(fair),
                          "edge": float(p - fair), "ev": float(p * dec(price) - 1), "dog": price > 0})
        out.append(with_checks(max(sides, key=lambda x: x["ev"]), g))
    return out


def spread_legs(wk: pd.DataFrame):
    out = []
    for g in wk.itertuples(index=False):
        if pd.isna(g.p_home_cover):
            continue
        home = g.p_home_cover >= 0.5
        team, opp = (g.home, g.away) if home else (g.away, g.home)
        line = -g.spread_line if home else g.spread_line
        p = g.p_home_cover if home else 1 - g.p_home_cover
        price = price_or(g.home_spread_odds if home else g.away_spread_odds)
        out.append(with_checks({"game_id": g.game_id, "market": "spread", "team": team, "opp": opp, "home_side": bool(home),
                                "line": float(line), "label": f"{team} {line:+g}", "p": float(p), "price": int(price),
                                "market_p": 0.5, "edge": float(p - 0.5), "ev": float(p * dec(price) - 1), "dog": line > 0}, g))
    return out


def total_legs(wk: pd.DataFrame):
    out = []
    for g in wk.itertuples(index=False):
        if pd.isna(g.p_over):
            continue
        over = g.p_over >= 0.5
        p = g.p_over if over else 1 - g.p_over
        price = price_or(g.over_odds if over else g.under_odds)
        out.append({"game_id": g.game_id, "market": "total", "team": None, "opp": None, "over": bool(over),
                    "line": float(g.total_line), "label": f"{g.away} @ {g.home} {'over' if over else 'under'} {g.total_line:g}",
                    "p": float(p), "price": int(price), "market_p": 0.5, "edge": float(p - 0.5),
                    "ev": float(p * dec(price) - 1), "dog": False, "complete": bool(g.checks_complete), "net_checks": 0})
    return out


MIN_DOGS = {4: 1, 6: 2, 8: 2}


def ladder(legs, sizes=(4, 6, 8), need_dogs=True):
    """Nested tickets ranked by expected value. Heavy favourites are left out because they add risk
    for almost no payout, and each ticket must carry underdogs when any are available."""
    # No leg without its matchup checks. A favourite also needs the checks to lean its way at least
    # as often as against it; underdogs are there for the price, so they only need the checks done.
    usable = lambda l: l.get("complete", False) and (l["dog"] or l.get("net_checks", 0) >= 0)
    pool = sorted([l for l in legs if usable(l) and l["price"] >= -350 and l["p"] >= 0.30], key=lambda l: -l["ev"])
    chosen, tickets = [], []
    for n in sizes:
        if len(pool) < n:
            break
        while len(chosen) < n:
            rest = [l for l in pool if l not in chosen]
            dogs_short = need_dogs and sum(l["dog"] for l in chosen) < MIN_DOGS.get(n, 0)
            slots_left = n - len(chosen)
            dog_rest = [l for l in rest if l["dog"]]
            need = MIN_DOGS.get(n, 0) - sum(l["dog"] for l in chosen)
            pick = dog_rest[0] if (dogs_short and dog_rest and slots_left <= need) else rest[0]
            chosen.append(pick)
        tickets.append(list(chosen))
    return tickets


def ticket_summary(legs):
    p = float(np.prod([l["p"] for l in legs]))
    d = float(np.prod([dec(l["price"]) for l in legs]))
    return {"n": len(legs), "p": p, "fair_price": american(p), "market_price": american_from_dec(d),
            "market_decimal": round(d, 3), "ev": float(p * d - 1), "dogs": int(sum(l["dog"] for l in legs))}


# ----------------------------------------------------------------------------- scorecard

def bet_table(rows, thresholds, key):
    out = []
    for thr in thresholds:
        b = [r for r in rows if r[key] >= thr]
        n = len(b)
        if not n:
            continue
        won = sum(r["won"] for r in b)
        profit = sum((dec(r["price"]) - 1) if r["won"] else -1 for r in b)
        rate = won / n
        be = float(np.mean([1 / dec(r["price"]) for r in b]))
        out.append({"min_" + key: thr, "bets": n, "win_rate": round(rate, 4), "break_even": round(be, 4),
                    "roi": round(profit / n, 4), "z": round((rate - be) / math.sqrt(be * (1 - be) / n), 2)})
    return out


def scorecard(G: pd.DataFrame):
    T = G[(G.season >= TEST_FROM) & G.result.notna() & G.b_margin.notna()].copy()
    mae = lambda a, b: round(float((a - b).abs().mean()), 3)
    card = {
        "test_seasons": f"{TEST_FROM}-{int(T.season.max())}", "games": int(len(T)),
        "margin_miss_points": {"fundamentals_only": mae(T.result, T.f_margin), "market_line": mae(T.result, T.spread_line),
                               "blend": mae(T.result, T.b_margin)},
        "total_miss_points": {"fundamentals_only": mae(T.total, T.f_total), "market_line": mae(T.total, T.total_line),
                              "blend": mae(T.total, T.b_total)},
        "weight_on_fundamentals": {"margin": round(float(G.w_margin.dropna().iloc[-1]), 3), "total": round(float(G.w_total.dropna().iloc[-1]), 3)},
    }
    W = T[(T.result != 0) & T.mkt_home_win.notna()]
    y = (W.result > 0).astype(float)
    ll = lambda p: round(float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()), 4)
    card["moneyline_log_loss"] = {"model": ll(W.p_home_win.clip(0.02, 0.98)), "market": ll(W.mkt_home_win), "games": int(len(W))}

    res = {r.game_id: r for r in T.itertuples(index=False)}
    def settle(l):
        g = res[l["game_id"]]
        if l["market"] == "ml":
            return (g.result > 0) == l["home_side"] if g.result != 0 else None
        if l["market"] == "spread":
            m = g.result - g.spread_line
            return None if m == 0 else (m > 0) == l["home_side"]
        m = g.total - g.total_line
        return None if m == 0 else (m > 0) == l["over"]

    favs, safe_tickets = [], {2: [], 3: []}
    singles = {"ml": [], "spread": [], "total": []}
    tickets = {"ml": {4: [], 6: [], 8: []}, "spread": {4: [], 6: [], 8: []}, "total": {4: [], 6: [], 8: []}}
    for _, wk in T.groupby(["season", "week"]):
        fl = favourite_legs(wk)
        for l in fl:
            w = settle(l)
            if w is not None:
                favs.append({**l, "won": bool(w)})
        safe = sorted([l for l in fl if l["safe"]], key=lambda l: -l["p"])
        for n in (2, 3):
            if len(safe) >= n:
                tk = safe[:n]
                hit = all(settle(l) for l in tk)
                safe_tickets[n].append({"hit": hit, "payout": float(np.prod([dec(l["price"]) for l in tk])) if hit else 0.0,
                                        "p": float(np.prod([l["p"] for l in tk]))})
        for market, fn in (("ml", ml_legs), ("spread", spread_legs), ("total", total_legs)):
            legs = fn(wk)
            for l in legs:
                w = settle(l)
                if w is not None:
                    singles[market].append({**l, "won": bool(w)})
            for tk in ladder(legs, need_dogs=market != "total"):
                outcomes = [settle(l) for l in tk]
                live = [(l, o) for l, o in zip(tk, outcomes) if o is not None]  # pushes drop out of the parlay
                hit = all(o for _, o in live)
                payout = float(np.prod([dec(l["price"]) for l, _ in live])) if hit else 0.0
                tickets[market][len(tk)].append({"hit": hit, "payout": payout, "p": ticket_summary(tk)["p"]})

    def group(rows):
        t = bet_table([{**r, "one": 1.0} for r in rows], [1.0], "one")
        return {**{k: v for k, v in t[0].items() if k != "min_one"}, "average_forecast": round(float(np.mean([r["p"] for r in rows])), 4)} if t else None
    card["strong_favourites"] = {
        "rule": f"model win chance {SAFE_MIN_P:.0%} or higher",
        "all": group(favs),
        "safe_checks_lean_their_way": group([r for r in favs if r["safe"]]),
        "not_safe": group([r for r in favs if not r["safe"]]),
        "checks_net_negative": group([r for r in favs if r["net_checks"] < 0]),
    }
    card["safe_parlays"] = [{"legs": n, "weeks": len(r), "hit": int(sum(x["hit"] for x in r)),
                             "hits_expected": round(float(sum(x["p"] for x in r)), 1),
                             "roi": round(float(sum(x["payout"] for x in r) / len(r) - 1), 3)} for n, r in safe_tickets.items() if r]
    card["alternative_lines"] = []
    for off in ALT_OFFSETS:
        col = f"p_alt_{off:g}"
        m = T.result - (T.spread_line - off)
        ok = m != 0
        card["alternative_lines"].append({"points_moved": off, "games": int(ok.sum()),
                                          "average_forecast": round(float(T.loc[ok, col].mean()), 4),
                                          "actually_covered": round(float((m[ok] > 0).mean()), 4)})
    card["gate"] = {"games_tested": int(len(T)), "games_missing_a_check": int((~T.checks_complete).sum())}
    card["moneyline_singles"] = bet_table(singles["ml"], [-1.0, 0.0, 0.02, 0.05], "ev")
    v_dogs = [r for r in singles["ml"] if r["dog"] and r["ev"] >= 0]
    v_favs = [r for r in singles["ml"] if not r["dog"] and r["ev"] >= 0]
    card["moneyline_value_bets_split"] = {"underdogs": bet_table(v_dogs, [0.0], "ev"), "favourites": bet_table(v_favs, [0.0], "ev")}
    card["spread_singles"] = bet_table(singles["spread"], [0.0, 0.01, 0.02, 0.03], "edge")
    card["total_singles"] = bet_table(singles["total"], [0.0, 0.01, 0.02, 0.03], "edge")
    card["tickets"] = {}
    for market, by_n in tickets.items():
        card["tickets"][market] = []
        for n, rows in by_n.items():
            if not rows:
                continue
            card["tickets"][market].append({
                "legs": n, "weeks": len(rows), "hit": int(sum(r["hit"] for r in rows)),
                "hits_expected": round(float(sum(r["p"] for r in rows)), 1),
                "roi": round(float(sum(r["payout"] for r in rows) / len(rows) - 1), 3)})
    return card


# ----------------------------------------------------------------------------- interceptions

INT_FEATURES = ["i_team_rate", "i_qb_rate", "i_dropbacks", "i_dog", "i_total", "i_wind"]


def interceptions(I: pd.DataFrame):
    """Chance the starting quarterback throws at least one interception."""
    I = I.copy()
    I["y"] = (I.ints >= 1).astype(float)
    I["p_int"] = np.nan
    played = I.ints.notna() & (I.dropbacks >= 10)
    for s in range(FIRST_FUNDAMENTALS, int(I.season.max()) + 1):
        tr, te = I[(I.season < s) & played], I.season == s
        if not te.any():
            continue
        sc = StandardScaler().fit(tr[INT_FEATURES])
        m = LogisticRegression(C=0.3).fit(sc.transform(tr[INT_FEATURES]), tr.y)
        I.loc[te, "p_int"] = m.predict_proba(sc.transform(I.loc[te, INT_FEATURES]))[:, 1]
    T = I[(I.season >= TEST_FROM) & played & I.p_int.notna()]
    base = I[(I.season < TEST_FROM) & played].y.mean()
    ll = lambda p: float(-(T.y * np.log(p) + (1 - T.y) * np.log(1 - p)).mean())
    bins = [0, 0.42, 0.47, 0.52, 0.57, 0.62, 1]
    cal = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        b = T[(T.p_int >= lo) & (T.p_int < hi)]
        if len(b):
            cal.append({"forecast_range": f"{lo:.0%}-{hi:.0%}", "starts": int(len(b)),
                        "average_forecast": round(float(b.p_int.mean()), 3), "actually_threw_one": round(float(b.y.mean()), 3)})
    card = {"test_seasons": f"{TEST_FROM}-{int(T.season.max())}", "starts": int(len(T)),
            "base_rate": round(float(T.y.mean()), 3),
            "log_loss": {"model": round(ll(T.p_int), 4), "always_base_rate": round(ll(np.full(len(T), base)), 4)},
            "calibration": cal}
    return I, card


# ----------------------------------------------------------------------------- correlations

def tetrachoric(a: np.ndarray, b: np.ndarray) -> float:
    """Latent correlation between two yes/no outcomes, the form a Gaussian copula needs."""
    p1, p2, p11 = a.mean(), b.mean(), (a * b).mean()
    t1, t2 = norm.ppf(p1), norm.ppf(p2)
    f = lambda r: multivariate_normal.cdf([t1, t2], mean=[0, 0], cov=[[1, r], [r, 1]]) - p11
    try:
        return float(brentq(f, -0.95, 0.95, xtol=1e-4))
    except ValueError:
        return 0.0


def correlations(G: pd.DataFrame, I: pd.DataFrame):
    """How a touchdown or an interception moves with the game result, measured on past games."""
    skill = pd.read_csv(CACHE / "skill_games.csv")
    P = G[G.result.notna()][["game_id", "home", "away", "result", "total", "spread_line", "total_line"]]
    s = skill.merge(P, on="game_id")
    is_home = s.team == s.home
    margin = np.where(is_home, s.result, -s.result)
    line = np.where(is_home, s.spread_line, -s.spread_line)
    s["won"], s["cover"], s["over"] = (margin > 0).astype(float), (margin - line > 0).astype(float), (s.total > s.total_line).astype(float)
    out = {"n_player_games": int(len(s)), "atd": {}, "int": {}}
    for pos, grp in s.groupby("position"):
        out["atd"][pos] = {k: round(tetrachoric(grp.scored.values.astype(float), grp[k].values), 3) for k in ("won", "cover", "over")}
        out["atd"][pos]["n"] = int(len(grp))
    q = I[I.ints.notna() & (I.dropbacks >= 10)].merge(P, on="game_id")
    is_home = q.team == q.home
    margin = np.where(is_home, q.result, -q.result)
    line = np.where(is_home, q.spread_line, -q.spread_line)
    y = (q.ints >= 1).astype(float).values
    out["int"] = {"own_team_won": round(tetrachoric(y, (margin > 0).astype(float)), 3),
                  "own_team_cover": round(tetrachoric(y, (margin - line > 0).astype(float)), 3),
                  "over": round(tetrachoric(y, (q.total > q.total_line).astype(float).values), 3), "n": int(len(q))}
    return out


def joint_probability(ps, R, n=400_000, seed=7):
    """Chance every leg hits, for legs tied together by correlation matrix R (Gaussian copula)."""
    R = np.array(R, dtype=float)
    shrink = 1.0
    while True:
        try:
            L = np.linalg.cholesky(R)
            break
        except np.linalg.LinAlgError:
            shrink *= 0.9
            R = np.where(np.eye(len(ps)) == 1, 1.0, R * 0.9)
    z = np.random.default_rng(seed).standard_normal((n, len(ps))) @ L.T
    return float((z < norm.ppf(np.array(ps))).all(axis=1).mean())


# ----------------------------------------------------------------------------- this week

def reasons(g, side_home: bool, model, labels):
    """The inputs pulling the fundamentals forecast toward this side, in points."""
    sc, m, feats = model
    z = sc.transform(pd.DataFrame([{f: getattr(g, f) for f in feats}]))[0]
    contrib = m.coef_ * z * (1 if side_home else -1)
    order = np.argsort(-contrib)
    plus = [{"factor": labels[feats[i]], "points": round(float(contrib[i]), 1)} for i in order[:3] if contrib[i] >= 0.15]
    minus = [{"factor": labels[feats[i]], "points": round(float(contrib[i]), 1)} for i in order[::-1][:1] if contrib[i] <= -0.3]
    return plus, minus


def main():
    G, I, tg = build_game_table()
    models = fundamentals(G)
    blend(G)
    card = scorecard(G)
    I, int_card = interceptions(I)
    corr = correlations(G, I)

    up = G[G.result.isna()].copy()
    out = {"as_of": {"season": int(up.season.iloc[0]) if len(up) else None, "week": int(up.week.iloc[0]) if len(up) else None,
                     "trained_on": f"{int(tg.season.min())}-{int(tg.season.max())}", "team_games": int(len(tg))},
           "scorecard": card, "interception_scorecard": int_card, "correlations": corr,
           "games": [], "tickets": {}, "interceptions": [], "hybrids": []}

    D = json.loads(CONSOLE_DATA.read_text(encoding="utf8").strip()[len("const D = "):].rstrip(";")) if CONSOLE_DATA.exists() else None
    started = {g["id"] for g in D["games"] if g.get("started")} if D else set()
    up = up[~up.game_id.isin(started)]
    by_id = {g.game_id: g for g in up.itertuples(index=False)}

    detail, resid = G.attrs["detail"], G.attrs["resid"]
    f3 = lambda x: "n/a" if x is None or pd.isna(x) else f"{x:+.2f}"
    pc = lambda x: "n/a" if x is None or pd.isna(x) else f"{x:.0%}"
    n0 = lambda x: "n/a" if x is None or pd.isna(x) else f"{x:.0f}"

    def check_numbers(game_id, team, opp):
        """The figures behind each check, for this side and its opponent (EPA is expected points added per play)."""
        a, b = detail[game_id][team], detail[game_id][opp]
        return [
            f"{team} is {a['venue']}; plays {f3(a['home_road_split'])} EPA per play better at home than away, {opp} {f3(b['home_road_split'])}.",
            f"Starters out: {team} line {n0(a['ol_out'])}, defence {n0(a['def_out'])}, skill {n0(a['skill_out'])}; "
            f"{opp} line {n0(b['ol_out'])}, defence {n0(b['def_out'])}, skill {n0(b['skill_out'])}."
            + (f" {team} out: {a['out_names']}." if a["out_names"] else "") + (f" {opp} out: {b['out_names']}." if b["out_names"] else ""),
            f"{team} pass rate is {f3(a['pass_over_expected'] * 100 if a['pass_over_expected'] is not None else None)} percentage points against expected, "
            f"throws deep {pc(a['deep_rate'])}, play-action {pc(a['play_action'])}, motion {pc(a['motion'])}, "
            f"no-huddle {pc(a['no_huddle'])}, passes {pc(a['red_zone_pass'])} in the red zone.",
            f"{opp} defence blitzes {pc(b['defence_blitz'])} and pressures {pc(b['defence_pressure'])} of dropbacks; "
            f"{team} is expected to allow pressure on {pc(a['pressure_allowed'])}. {team} defence blitzes {pc(a['defence_blitz'])}; "
            f"{opp} expected to allow {pc(b['pressure_allowed'])}.",
            f"{team} runs vs {opp} front: inside {f3(a['run_inside'])}, outside {f3(a['run_outside'])} EPA per carry, "
            f"stuffed {pc(a['stuffed'])}, 10+ yards {pc(a['explosive_run'])}. {opp} vs {team} front: inside {f3(b['run_inside'])}, "
            f"outside {f3(b['run_outside'])}, stuffed {pc(b['stuffed'])}.",
            f"{team} receivers vs {opp} coverage, EPA per target: deep {f3(a['wr_deep'])}, slot area {f3(a['wr_slot_area'])}, "
            f"outside {f3(a['wr_outside'])}. {opp} receivers vs {team}: deep {f3(b['wr_deep'])}, slot area {f3(b['wr_slot_area'])}, outside {f3(b['wr_outside'])}.",
            f"{team} tight ends vs {opp}: {f3(a['te'])} EPA per target on {pc(a['te_share'])} of targets. {opp} tight ends vs {team}: {f3(b['te'])}.",
        ]

    def alt_ladder(g, home_side, line):
        m = g.b_margin if home_side else -g.b_margin
        out_ = []
        for off in (-6.0, -3.0, 0.0, 3.0, 6.0, 10.0):
            alt = line + off
            p_ = float(1 - np.searchsorted(resid, -alt - m, side="right") / len(resid))
            out_.append({"line": alt, "p": round(p_, 4), "fair_price": american(p_), "main": off == 0.0})
        return out_

    def decorate(leg):
        g = by_id[leg["game_id"]]
        if leg["market"] == "total":
            plus, minus = reasons(g, leg["over"], models["f_total"], TOTAL_FEATURES)
            lean = g.b_total - g.total_line
            leg["model_number"] = round(float(g.b_total), 1)
            leg["note"] = f"Model total {g.b_total:.1f} against a line of {g.total_line:g} ({lean:+.1f})."
        else:
            plus, minus = reasons(g, leg["home_side"], models["f_margin"], MARGIN_FEATURES)
            side = 1 if leg["home_side"] else -1
            leg["model_number"] = round(float(side * g.b_margin), 1)
            leg["note"] = (f"Model has {leg['team']} by {side * g.b_margin:+.1f}; the line has them by {side * g.spread_line:+.1f}."
                           if leg["market"] == "spread" else
                           f"Model {leg['p']:.1%} to win; the price implies {leg['market_p']:.1%} with the book's margin removed.")
            qd = g.qb_delta_home if leg["home_side"] else g.qb_delta_away
            qn = g.home_qb if leg["home_side"] else g.away_qb
            if abs(qd) >= 0.02 and isinstance(qn, str):
                leg["personnel"] = f"{qn} at quarterback rates {qd:+.2f} EPA per play against {leg['team']}'s recent starters."
            if D:
                hurt = [p["name"] for p in D["players"] if p["team"] == leg["team"] and p.get("inj")][:4]
                if hurt:
                    leg["injury_report"] = hurt
            for c_, text in zip(leg["checks"], check_numbers(leg["game_id"], leg["team"], leg["opp"])):
                c_["numbers"] = text
        leg["for"], leg["against"] = plus, minus
        for k in ("p", "market_p", "edge", "ev"):
            leg[k] = round(leg[k], 4)
        return leg

    all_legs = {"ml": ml_legs(up), "spread": spread_legs(up), "total": total_legs(up)}
    out["gate"] = {"picks_considered": sum(len(v) for v in all_legs.values()),
                   "dropped_missing_a_check": sum(not l.get("complete", False) for v in all_legs.values() for l in v)}

    favs_now = sorted([decorate(l) for l in favourite_legs(up)], key=lambda l: -l["p"])
    safe_now = [l for l in favs_now if l["safe"]]
    out["safe"] = {"rule": f"Model win chance {SAFE_MIN_P:.0%} or higher, every check available, at least two more checks for than against, and Personnel not against.",
                   "moneylines": safe_now, "other_favourites": [l for l in favs_now if not l["safe"]],
                   "parlays": [{"legs": safe_now[:n], **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in ticket_summary(safe_now[:n]).items()}}
                               for n in (2, 3) if len(safe_now) >= n], "spreads": []}
    for market, legs in all_legs.items():
        legs = [decorate(l) for l in legs]
        out["tickets"][market] = [{"legs": tk, **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in ticket_summary(tk).items()}}
                                  for tk in ladder(legs, need_dogs=market != "total")]
    for g in up.itertuples(index=False):
        find = lambda m: next((l for l in all_legs[m] if l["game_id"] == g.game_id), None)
        sp_ = find("spread")
        alts = alt_ladder(g, sp_["home_side"], sp_["line"]) if sp_ else []
        if sp_ and sp_.get("complete"):
            safer = next((a_ for a_ in alts if a_["p"] >= 0.70), None)
            if safer:
                out["safe"]["spreads"].append({"game_id": g.game_id, "team": sp_["team"], "main_line": sp_["line"], "main_p": sp_["p"],
                                               "safe_line": safer["line"], "p": safer["p"], "fair_price": safer["fair_price"],
                                               "net_checks": sp_["net_checks"]})
        out["games"].append({"game_id": g.game_id, "gameday": g.gameday, "away": g.away, "home": g.home,
                             "spread_home": float(-g.spread_line), "total_line": float(g.total_line),
                             "model_home_margin": round(float(g.b_margin), 1), "model_total": round(float(g.b_total), 1),
                             "fundamentals_home_margin": round(float(g.f_margin), 1), "fundamentals_total": round(float(g.f_total), 1),
                             "ml": find("ml"), "spread": find("spread"), "total": find("total"), "alt_spreads": alts})
    out["safe"]["spreads"].sort(key=lambda x: (-x["net_checks"], -x["p"]))

    # Interceptions: listed when the forecast sits in the top band, where past forecasts held up.
    INT_MIN = 0.57
    Iu = I[I.game_id.isin(up.game_id) & I.p_int.notna()]
    for r in Iu.sort_values("p_int", ascending=False).itertuples(index=False):
        out["interceptions"].append({
            "game_id": r.game_id, "team": r.team, "opp": r.opp, "qb": r.qb if isinstance(r.qb, str) else f"{r.team} quarterback",
            "p": round(float(r.p_int), 4), "fair_price": american(r.p_int), "recommended": bool(r.p_int >= INT_MIN),
            "inputs": {"qb_interception_rate": round(float(r.i_qb_rate), 4), "matchup_interception_rate": round(float(r.i_team_rate), 4),
                       "expected_dropbacks": round(float(r.i_dropbacks), 1), "points_underdog_by": round(float(r.i_dog), 1)}})
    out["interception_threshold"] = INT_MIN

    # Hybrid same-game parlays: a game leg tied to the console's touchdown legs with measured correlation.
    if D:
        atd_corr = D["corr"]["atd"]
        ints = {(x["game_id"], x["team"]): x for x in out["interceptions"]}

        def rho(a, b):
            ka, kb = a["kind"], b["kind"]
            if ka == "atd" and kb == "atd":
                if a["team"] != b["team"]:
                    return atd_corr.get("OPP", 0.03)
                return atd_corr.get("TM:" + "-".join(sorted([a["pos"], b["pos"]])), atd_corr.get("TM:default", -0.04))
            if ka != "atd" and kb != "atd":
                if {ka, kb} == {"game", "int"}:
                    g_, i_ = (a, b) if ka == "game" else (b, a)
                    base = corr["int"]["over"] if g_["market"] == "total" else corr["int"]["own_team_won" if g_["market"] == "ml" else "own_team_cover"]
                    if g_["market"] == "total":
                        return base if g_["over"] else -base
                    return base if g_["team"] == i_["team"] else -base
                return 0.0
            p_, o = (a, b) if ka == "atd" else (b, a)
            if o["kind"] == "int":
                return 0.0
            c = corr["atd"].get(p_["pos"], {})
            if o["market"] == "total":
                return c.get("over", 0) if o["over"] else -c.get("over", 0)
            base = c.get("won" if o["market"] == "ml" else "cover", 0)
            return base if p_["team"] == o["team"] else -base

        def build(kind, game_leg, extra):
            legs = [game_leg] + extra
            ps = [l["p"] for l in legs]
            R = [[1.0 if i == j else rho(a, b) for j, b in enumerate(legs)] for i, a in enumerate(legs)]
            pj, pi = joint_probability(ps, R), float(np.prod(ps))
            return {"kind": kind, "game_id": game_leg["game_id"],
                    "legs": [{k: v for k, v in l.items() if k in ("kind", "label", "p", "team", "pos", "player_id", "market", "price", "note", "matchup", "net_checks")} for l in legs],
                    "p": round(pj, 4), "p_if_independent": round(pi, 4), "correlation_lift": round(pj / pi, 3), "fair_price": american(pj)}

        for g in up.itertuples(index=False):
            roster = [p for p in D["players"] if p["game"] == g.game_id and not p.get("singles")]
            def tds(team, k):
                _, verdicts, _ = side_checks(g, team == g.home)
                mv = lambda p: verdicts[POSITION_CHECK.get(p["pos"], 4)]
                mine = sorted([p for p in roster if p["team"] == team], key=lambda p: -p["p"])
                ok = [p for p in mine if mv(p) != "against"]
                top = (ok if len(ok) >= k else mine)[:k]
                return [{"kind": "atd", "label": f"{p['name']} anytime TD", "p": float(p["p"]), "team": team, "pos": p["pos"],
                         "player_id": p["id"], "matchup": mv(p)} for p in top]
            def game_leg(market):
                l = next((x for x in all_legs[market] if x["game_id"] == g.game_id), None)
                return None if l is None else {**l, "kind": "game"}
            if not g.checks_complete:
                continue   # no hybrid without the matchup checks
            ml, sp, tot = game_leg("ml"), game_leg("spread"), game_leg("total")
            if ml and len(tds(ml["team"], 2)) == 2:
                out["hybrids"].append(build("Moneyline + 2 touchdowns", ml, tds(ml["team"], 2)))
            if sp and tds(sp["team"], 1):
                extra = tds(sp["team"], 1)
                it = ints.get((g.game_id, sp["opp"]))
                kind = "Spread + touchdown"
                if it and it["recommended"]:
                    extra.append({"kind": "int", "label": f"{it['qb']} to throw an interception", "p": it["p"], "team": sp["opp"]})
                    kind = "Spread + touchdown + interception"
                out["hybrids"].append(build(kind, sp, extra))
            if tot and tot["over"] and tds(g.home, 1) and tds(g.away, 1):
                out["hybrids"].append(build("Over + a touchdown from each team", tot, tds(g.home, 1) + tds(g.away, 1)))

    (HERE / "output").mkdir(exist_ok=True)
    json.dump(out, open(HERE / "output/game_markets.json", "w"), indent=1, default=lambda o: None if pd.isna(o) else o)
    print(json.dumps({"scorecard": card, "interceptions": int_card, "correlations": corr}, indent=1))
    for m in ("ml", "spread", "total"):
        for tk in out["tickets"][m]:
            print(m, tk["n"], [l["label"] + f" {l['p']:.0%} @{l['price']:+d}" for l in tk["legs"]], f"p={tk['p']:.3f} fair {tk['fair_price']:+d} mkt {tk['market_price']:+d} ev {tk['ev']:+.2f}")
    print("INT:", [(x["qb"], x["p"], x["recommended"]) for x in out["interceptions"][:6]])
    for h in out["hybrids"][:4]:
        print(h["kind"], [l["label"] for l in h["legs"]], h["p"], h["p_if_independent"], h["correlation_lift"])


if __name__ == "__main__":
    main()
