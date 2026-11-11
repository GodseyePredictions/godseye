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
}
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

    rows, int_rows = [], []
    for t, wk in todo.groupby("t"):
        train = tg[(tg.t < t) & (tg.t >= t - WINDOW)]
        if len(train) < 300:
            continue
        C = fit_ratings(train, t, ix)
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
    I = pd.DataFrame(int_rows).merge(qb[["game_id", "team", "qb_id", "ints", "dropbacks"]], on=["game_id", "team", "qb_id"], how="left")
    return G, I, tg


# ----------------------------------------------------------------------------- models

def fundamentals(G: pd.DataFrame):
    """Walk-forward ridge forecasts of margin and total that never see the betting line."""
    G["f_margin"], G["f_total"] = np.nan, np.nan
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
    return last


def blend(G: pd.DataFrame):
    """Move the market line toward the fundamentals by a weight learned on earlier seasons."""
    for c in ("b_margin", "b_total", "sd_margin", "sd_total", "sd_win", "w_margin", "w_total"):
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
    G["p_home_cover"] = norm.cdf((G.b_margin - G.spread_line) / G.sd_margin)
    G["p_over"] = norm.cdf((G.b_total - G.total_line) / G.sd_total)
    G["p_home_win"] = norm.cdf(G.b_margin / G.sd_win)
    ih = G.home_ml.apply(lambda x: np.nan if pd.isna(x) else 1 / dec(x))
    ia = G.away_ml.apply(lambda x: np.nan if pd.isna(x) else 1 / dec(x))
    G["mkt_home_win"] = ih / (ih + ia)


# ----------------------------------------------------------------------------- candidate legs

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
        out.append(max(sides, key=lambda x: x["ev"]))
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
        out.append({"game_id": g.game_id, "market": "spread", "team": team, "opp": opp, "home_side": bool(home),
                    "line": float(line), "label": f"{team} {line:+g}", "p": float(p), "price": int(price),
                    "market_p": 0.5, "edge": float(p - 0.5), "ev": float(p * dec(price) - 1), "dog": line > 0})
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
                    "ev": float(p * dec(price) - 1), "dog": False})
    return out


MIN_DOGS = {4: 1, 6: 2, 8: 2}


def ladder(legs, sizes=(4, 6, 8), need_dogs=True):
    """Nested tickets ranked by expected value. Heavy favourites are left out because they add risk
    for almost no payout, and each ticket must carry underdogs when any are available."""
    pool = sorted([l for l in legs if l["price"] >= -350 and l["p"] >= 0.30], key=lambda l: -l["ev"])
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

    singles = {"ml": [], "spread": [], "total": []}
    tickets = {"ml": {4: [], 6: [], 8: []}, "spread": {4: [], 6: [], 8: []}, "total": {4: [], 6: [], 8: []}}
    for _, wk in T.groupby(["season", "week"]):
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

    card["moneyline_singles"] = bet_table(singles["ml"], [-1.0, 0.0, 0.02, 0.05], "ev")
    dogs = [r for r in singles["ml"] if r["dog"] and r["ev"] >= 0]
    favs = [r for r in singles["ml"] if not r["dog"] and r["ev"] >= 0]
    card["moneyline_value_bets_split"] = {"underdogs": bet_table(dogs, [0.0], "ev"), "favourites": bet_table(favs, [0.0], "ev")}
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
        leg["for"], leg["against"] = plus, minus
        for k in ("p", "market_p", "edge", "ev"):
            leg[k] = round(leg[k], 4)
        return leg

    all_legs = {"ml": ml_legs(up), "spread": spread_legs(up), "total": total_legs(up)}
    for market, legs in all_legs.items():
        legs = [decorate(l) for l in legs]
        out["tickets"][market] = [{"legs": tk, **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in ticket_summary(tk).items()}}
                                  for tk in ladder(legs, need_dogs=market != "total")]
    for g in up.itertuples(index=False):
        find = lambda m: next((l for l in all_legs[m] if l["game_id"] == g.game_id), None)
        out["games"].append({"game_id": g.game_id, "gameday": g.gameday, "away": g.away, "home": g.home,
                             "spread_home": float(-g.spread_line), "total_line": float(g.total_line),
                             "model_home_margin": round(float(g.b_margin), 1), "model_total": round(float(g.b_total), 1),
                             "fundamentals_home_margin": round(float(g.f_margin), 1), "fundamentals_total": round(float(g.f_total), 1),
                             "ml": find("ml"), "spread": find("spread"), "total": find("total")})

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
                    "legs": [{k: v for k, v in l.items() if k in ("kind", "label", "p", "team", "pos", "player_id", "market", "price", "note")} for l in legs],
                    "p": round(pj, 4), "p_if_independent": round(pi, 4), "correlation_lift": round(pj / pi, 3), "fair_price": american(pj)}

        for g in up.itertuples(index=False):
            roster = [p for p in D["players"] if p["game"] == g.game_id and not p.get("singles")]
            def tds(team, k):
                top = sorted([p for p in roster if p["team"] == team], key=lambda p: -p["p"])[:k]
                return [{"kind": "atd", "label": f"{p['name']} anytime TD", "p": float(p["p"]), "team": team, "pos": p["pos"], "player_id": p["id"]} for p in top]
            def game_leg(market):
                l = next((x for x in all_legs[market] if x["game_id"] == g.game_id), None)
                return None if l is None else {**l, "kind": "game"}
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
