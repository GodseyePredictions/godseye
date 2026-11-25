"""The game simulation: expected goals by strength, adjustments, 20,000 simulated games, market prices.

Step 1  expected goals per team from 5v5, power-play and shorthanded rates and projected minutes.
Step 2  adjustments: opposing goalie (GSAx), home ice, rest and travel, absent regulars. Every one is itemised.
Step 3  simulate: goals and saved shots in each half-period, re-reading the score each time (score effects);
        the empty-net window; overtime and the shootout.
Step 4  price moneyline, 60-minute three-way, puck lines and totals from the simulated scores.

Everything the player props need comes out of the same simulated games: each team's goals by strength,
shots on goal, the score after two periods, and the hit and block multipliers the score produced.
"""
from dataclasses import dataclass, field

import numpy as np

from common.odds_math import fair_american, fair_probs


def _row(tr, team, strength):
    r = tr[(tr.team == team) & (tr.strength == strength)]
    return r.iloc[0] if len(r) else None


def team_lambdas(home: str, away: str, ctx: dict, cfg) -> dict:
    """Expected goals and shots for both teams, with what moved them. ctx: team_rates, K (fit), and per-game
    inputs: goalies {team: gsax60 or None}, crew_factor, spots {team: schedule row}, absent {team: share of xG out}."""
    tr, K, c = ctx["team_rates"], ctx["K"], cfg["sim"]
    out = {}
    lg = tr[tr.strength == "all"]
    for team, opp, is_home in ((home, away, 1), (away, home, 0)):
        t = {s: _row(tr, team, s) for s in ("ev5", "pp", "pk", "all")}
        o = {s: _row(tr, opp, s) for s in ("ev5", "pp", "pk", "all")}
        crew = ctx.get("crew_factor", 1.0)
        pp_sec = K["pp_sec_pg"] * t["all"].pen_drawn60_idx * o["all"].pen_taken60_idx * crew
        pk_sec = K["pp_sec_pg"] * t["all"].pen_taken60_idx * o["all"].pen_drawn60_idx * crew
        ev_sec = 3600 - pp_sec - pk_sec
        g, s = {}, {}
        g["ev"] = t["ev5"].xgf60 * o["ev5"].xga60_idx * ev_sec / 3600
        g["pp"] = t["pp"].xgf60 * o["pk"].xga60_idx * pp_sec / 3600
        g["sh"] = t["pk"].xgf60 * o["pp"].xga60_idx * pk_sec / 3600
        s["ev"] = t["ev5"].sog_f60 * o["ev5"].sog_a60_idx * ev_sec / 3600
        s["pp"] = t["pp"].sog_f60 * o["pk"].sog_a60_idx * pp_sec / 3600
        s["sh"] = t["pk"].sog_f60 * o["pp"].sog_a60_idx * pk_sec / 3600
        hs = K.get("home_sog", 1.0) if is_home else 1 / K.get("home_sog", 1.0)
        s = {k_: v * hs for k_, v in s.items()}
        steps = [{"what": "5v5 xG", "value": round(float(g["ev"]), 3)}, {"what": "power-play xG", "value": round(float(g["pp"]), 3)},
                 {"what": "shorthanded xG", "value": round(float(g["sh"]), 3)}]
        mult = K.get("season_goal_factor", 1.0)
        if abs(mult - 1) >= 0.005:
            steps.append({"what": "this season's goals per expected goal", "factor": round(mult, 4)})
        gs = (ctx.get("goalies") or {}).get(opp)
        if gs is not None and gs.get("gsax60") is not None:
            f = 1 - gs["gsax60"] / gs["league_xga60"]
            mult *= f
            steps.append({"what": f"facing {gs.get('name', 'the starter')} (GSAx/60 {gs['gsax60']:+.2f})", "factor": round(float(f), 4)})
        f = K["home_ice"] if is_home else 1 / K["home_ice"]
        mult *= f
        steps.append({"what": "home ice" if is_home else "road", "factor": round(float(f), 4)})
        sp, so = (ctx.get("spots") or {}).get(team), (ctx.get("spots") or {}).get(opp)
        if sp:
            if sp.get("b2b"):
                mult *= c["b2b_goals_for"]; steps.append({"what": "second night of a back-to-back", "factor": c["b2b_goals_for"]})
            if so and so.get("b2b"):
                mult *= c["b2b_goals_against"]; steps.append({"what": "opponent on a back-to-back", "factor": c["b2b_goals_against"]})
            rd = sp.get("rest_diff")
            if rd is not None and rd == rd and rd != 0 and not sp.get("b2b") and not (so or {}).get("b2b"):
                f = 1 + c["rest_diff_per_day"] * float(np.clip(rd, -2, 2))
                mult *= f; steps.append({"what": f"rest differential {rd:+.0f} days", "factor": round(f, 4)})
            tz = abs(sp.get("tz_shift") or 0)
            if tz:
                f = 1 - c["tz_per_hour"] * min(tz, 3)
                mult *= f; steps.append({"what": f"{tz:.0f} time zones since last game", "factor": round(f, 4)})
        out_share = (ctx.get("absent") or {}).get(team, {})
        if out_share.get("share"):
            f = 1 - c["injury_loss"] * out_share["share"]
            mult *= f
            steps.append({"what": "out: " + ", ".join(out_share["names"]), "factor": round(float(f), 4)})
        goals = {k: float(v * mult) for k, v in g.items()}
        out[team] = {"team": team, "opp": opp, "is_home": is_home, "goals": goals, "lam": sum(goals.values()),
                     "sog": {k: float(v) for k, v in s.items()}, "sog_mean": float(sum(s.values())),
                     "pp_sec": float(pp_sec), "pk_sec": float(pk_sec), "ev_sec": float(ev_sec), "steps": steps}
    return out


@dataclass
class Sims:
    home: str
    away: str
    n: int
    goals: dict = field(default_factory=dict)       # team -> {"ev","pp","sh","en","ot"} arrays of goals per simulated game
    reg: dict = field(default_factory=dict)         # team -> regulation goals (empty-net included)
    final: dict = field(default_factory=dict)       # team -> final score (overtime goal or shootout winner's goal included)
    sog: dict = field(default_factory=dict)         # team -> shots on goal against a goalie in net, overtime included
    sog_p2: dict = field(default_factory=dict)      # team -> the same through two periods
    ga_p2: dict = field(default_factory=dict)       # team -> goals against through two periods
    lead_p2: np.ndarray | None = None               # home lead after two periods
    f_hits: dict = field(default_factory=dict)      # team -> the score's multiplier on its hits
    f_blk: dict = field(default_factory=dict)
    f_sog: dict = field(default_factory=dict)       # team -> simulated shots over expected shots
    went_ot: np.ndarray | None = None
    went_so: np.ndarray | None = None
    lam: dict = field(default_factory=dict)

    def margin(self):
        return self.final[self.home] - self.final[self.away]

    def total(self):
        return self.final[self.home] + self.final[self.away]


def simulate(lam: dict, home: str, away: str, K: dict, cfg, n: int | None = None, seed: int | None = None) -> Sims:
    c = cfg["sim"]
    n = n or c["n_sims"]
    rng = np.random.default_rng(c["seed"] if seed is None else seed)
    S = Sims(home, away, n, lam=lam)
    teams = (home, away)
    mix = lambda sd: rng.gamma(1 / sd ** 2, sd ** 2, n) if sd > 0 else np.ones(n)
    pace = mix(c["pace_sd"])
    tm = {t: mix(c["team_sd"]) * pace for t in teams}
    shot_mix = {t: mix(c["shot_sd"]) for t in teams}
    G = {t: {k: np.zeros(n, int) for k in ("ev", "pp", "sh", "en", "ot")} for t in teams}
    saved = {t: np.zeros(n, int) for t in teams}            # shots by t that the goalie stopped
    lead = np.zeros(n, int)                                 # home lead
    fh = {t: np.zeros(n) for t in teams}
    fb = {t: np.zeros(n) for t in teams}
    halves = c["halves_per_period"]
    seg = 1200 / halves
    se_g, se_s, se_h, se_b = (np.array(K[x]) for x in ("se_goals", "se_sog", "se_hits", "se_blk"))
    non_goal = {t: {k: max(lam[t]["sog"][k] - lam[t]["goals"][k], 0.0) for k in ("ev", "pp", "sh")} for t in teams}
    total_w = 0.0

    def play(dur, share, late=False):
        nonlocal lead, total_w
        b = {home: np.clip(lead, -2, 2) + 2, away: np.clip(-lead, -2, 2) + 2}
        scored = {}
        hold = np.where(lead == 0, c["tied_late_factor"], 1.0) if late else 1.0     # tied late, both sides play for the point
        for t in teams:
            w = share * tm[t] * hold
            g_ev = rng.poisson(lam[t]["goals"]["ev"] * w * se_g[b[t]])
            g_pp = rng.poisson(lam[t]["goals"]["pp"] * w)
            g_sh = rng.poisson(lam[t]["goals"]["sh"] * w)
            G[t]["ev"] += g_ev; G[t]["pp"] += g_pp; G[t]["sh"] += g_sh
            ws = dur / 3600 * tm[t] * shot_mix[t]
            saved[t] += rng.poisson(non_goal[t]["ev"] * ws * se_s[b[t]]) + rng.poisson((non_goal[t]["pp"] + non_goal[t]["sh"]) * ws)
            fh[t] += se_h[b[t]] * dur; fb[t] += se_b[b[t]] * dur
            scored[t] = g_ev + g_pp + g_sh
        lead = lead + scored[home] - scored[away]
        total_w += dur

    en_win = c["en_window_sec"]
    for period in range(3):
        for h in range(halves):
            last = period == 2 and h == halves - 1
            dur = seg - (en_win if last else 0)
            play(dur, K["period_share"][period] * dur / 1200, late=last)
        if period == 1:
            S.lead_p2 = lead.copy()
            for t, o in ((home, away), (away, home)):
                S.sog_p2[t] = saved[t] + G[t]["ev"] + G[t]["pp"] + G[t]["sh"]
            S.ga_p2 = {home: G[away]["ev"] + G[away]["pp"] + G[away]["sh"], away: G[home]["ev"] + G[home]["pp"] + G[home]["sh"]}
    # ---- the last minutes: a side down one or two pulls its goalie
    step = c["en_step_sec"]
    p_en = 1 - np.exp(-K["en_g60"] * step / 3600)
    p_six = 1 - np.exp(-c["extra_attacker_g60"] * step / 3600)
    share_step = K["period_share"][2] * step / 1200
    for _ in range(int(en_win // step)):
        b = {home: np.clip(lead, -2, 2) + 2, away: np.clip(-lead, -2, 2) + 2}
        pulled = {home: (lead < 0) & (lead >= -c["en_max_deficit"]), away: (lead > 0) & (lead <= c["en_max_deficit"])}
        normal = ~(pulled[home] | pulled[away])
        d = np.zeros(n, int)
        for t, o in ((home, away), (away, home)):
            sgn = 1 if t == home else -1
            g_norm = rng.poisson(lam[t]["lam"] * share_step * tm[t] * se_g[b[t]] * np.where(lead == 0, c["tied_late_factor"], 1.0)) * normal
            G[t]["ev"] += g_norm
            saved[t] += rng.poisson(sum(non_goal[t].values()) * step / 3600 * tm[t]) * normal
            g_six = (rng.random(n) < p_six) & pulled[t]              # the side with the extra attacker scores
            G[t]["ev"] += g_six
            saved[t] += rng.poisson(c["extra_attacker_sog60"] * step / 3600, n) * pulled[t]
            g_en = (rng.random(n) < p_en) & pulled[o]                # into the empty net
            G[t]["en"] += g_en
            d += sgn * (g_norm + g_six + g_en)
            fh[t] += se_h[b[t]] * step; fb[t] += se_b[b[t]] * step
        lead = lead + d
    total_w += en_win
    for t in teams:
        S.reg[t] = G[t]["ev"] + G[t]["pp"] + G[t]["sh"] + G[t]["en"]
        S.f_hits[t], S.f_blk[t] = fh[t] / total_w, fb[t] / total_w
    # ---- overtime and shootout
    tied = S.reg[home] == S.reg[away]
    ratio = (lam[home]["lam"] / (lam[home]["lam"] + lam[away]["lam"]) - 0.5) * c["ot_strength_weight"] + 0.5
    ot_goal = tied & (rng.random(n) < K["ot_decided"])
    home_ot = rng.random(n) < ratio
    G[home]["ot"] = (ot_goal & home_ot).astype(int)
    G[away]["ot"] = (ot_goal & ~home_ot).astype(int)
    so = tied & ~ot_goal
    home_so = rng.random(n) < c["so_home_win"]
    S.went_ot, S.went_so = tied, so
    for t, won_so in ((home, so & home_so), (away, so & ~home_so)):
        S.goals[t] = G[t]
        S.final[t] = S.reg[t] + G[t]["ot"] + won_so.astype(int)
        ot_sog = rng.poisson(c["ot_sog_per_team"], n) * tied
        S.sog[t] = saved[t] + G[t]["ev"] + G[t]["pp"] + G[t]["sh"] + np.maximum(ot_sog, G[t]["ot"])
        S.f_sog[t] = S.sog[t] / max(lam[t]["sog_mean"], 1e-9)
    return S


def summary(S: Sims, cfg) -> dict:
    """What the sim says about the game: scores, blowout risk, overtime."""
    h, a = S.home, S.away
    c = cfg["sim"]
    blow = np.abs(S.lead_p2) >= c["blowout_margin"]
    fav = h if (S.final[h] > S.final[a]).mean() >= 0.5 else a
    fav_blow = (S.lead_p2 >= c["blowout_margin"]) if fav == h else (S.lead_p2 <= -c["blowout_margin"])
    return {"home": h, "away": a, "home_goals": round(float(S.final[h].mean()), 3), "away_goals": round(float(S.final[a].mean()), 3),
            "total": round(float(S.total().mean()), 3), "home_win": round(float((S.final[h] > S.final[a]).mean()), 4),
            "overtime": round(float(S.went_ot.mean()), 4), "shootout": round(float(S.went_so.mean()), 4),
            "home_sog": round(float(S.sog[h].mean()), 2), "away_sog": round(float(S.sog[a].mean()), 2),
            "empty_net_goals": round(float((S.goals[h]["en"] + S.goals[a]["en"]).mean()), 3),
            "blowout_prob": round(float(blow.mean()), 4), "favourite": fav, "favourite_blowout_prob": round(float(fav_blow.mean()), 4),
            "blowout_flag": bool(fav_blow.mean() >= c["blowout_flag_prob"])}


def market_probs(S: Sims) -> dict:
    """Model probabilities for the game lines, keyed like odds rows: (market, side-or-team, line)."""
    h, a = S.home, S.away
    m, tot = S.margin(), S.total()
    reg = S.reg[h] - S.reg[a]
    out = {("ml", h, 0.0): (m > 0).mean(), ("ml", a, 0.0): (m < 0).mean(),
           ("ml3", h, 0.0): (reg > 0).mean(), ("ml3", a, 0.0): (reg < 0).mean(), ("ml3", "draw", 0.0): (reg == 0).mean()}
    for line in (-3.5, -2.5, -1.5, 1.5, 2.5, 3.5):
        out[("spread", h, line)] = (m + line > 0).mean()
        out[("spread", a, line)] = (-m + line > 0).mean()
    for line in np.arange(3.5, 9.6, 0.5):
        out[("total", "over", float(line))] = (tot > line).mean()
        out[("total", "under", float(line))] = (tot < line).mean()
    return {k: float(v) for k, v in out.items()}


def hits_for(S: Sims, market: str, side: str, line: float) -> np.ndarray:
    """True/false in every simulated game for one game-line bet."""
    h, a = S.home, S.away
    m, tot = S.margin(), S.total()
    if market == "ml":
        return m > 0 if side == h else m < 0
    if market == "ml3":
        reg = S.reg[h] - S.reg[a]
        return reg == 0 if side == "draw" else (reg > 0 if side == h else reg < 0)
    if market == "spread":
        return (m if side == h else -m) + line > 0
    return tot > line if side == "over" else tot < line


def price_markets(S: Sims, odds_rows: list, cfg) -> list:
    """Edge = model probability minus implied probability with the vig removed, for every listed game line."""
    probs = market_probs(S)
    tiers = sorted(cfg["sim"]["edge_tiers"].items(), key=lambda kv: -kv[1])
    groups = {}
    for r in odds_rows:
        if r["market"] not in ("ml", "ml3", "spread", "total"):
            continue
        key = (r["book"], r["market"], abs(r["line"]) if r["market"] == "spread" else r["line"])
        groups.setdefault(key, []).append(r)
    out = []
    for (book, market, _), rows in groups.items():
        need = 3 if market == "ml3" else 2
        if len(rows) != need:
            continue
        fair = fair_probs([r["price"] for r in rows])
        for r, imp in zip(rows, fair):
            side = r["player_name"] if r["side"] in ("team", "draw") else r["side"]
            side = "draw" if r["side"] == "draw" else side
            p = probs.get((market, side, float(r["line"])))
            if p is None:
                p = float(hits_for(S, market, side, r["line"]).mean())
            edge = p - imp
            tier = next((name for name, lo in tiers if edge >= lo), None)
            out.append({"book": book, "market": market, "side": side, "line": r["line"], "price": r["price"], "model_prob": round(p, 4),
                        "implied_prob": round(imp, 4), "edge": round(edge, 4), "tier": tier, "fair_price": fair_american(p)})
    return sorted(out, key=lambda x: -x["edge"])
