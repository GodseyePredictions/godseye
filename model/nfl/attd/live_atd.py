"""Live anytime-TD pricing for games in progress.

P(scores from now) = 1 - exp(-lambda_rem), where
  lambda_rem = [team_rush_TD_rate x rush_share x script_rush + team_pass_TD_rate x rec_share x script_pass]
               x fraction_of_game_left x pace_adjust
Team TD rates and player shares are the pre-game model's; the script multipliers come from the live margin
(trailing teams throw, leading teams run and bleed clock); fraction_of_game_left from the live clock; pace_adjust
from the game's scoring so far vs the pre-game total.  A player with no touches by the second half is flagged.
"""
from __future__ import annotations

import json
import re
import subprocess

import numpy as np
import pandas as pd

from .live import TEAM_FIX, nkey

QTR_SECS = 900


def script(margin: float, qtr: int):
    """(rush multiplier, pass multiplier) for a team at `margin` (positive = leading)."""
    if margin >= 17 and qtr >= 4:
        return 1.05, 0.55
    if margin >= 9:
        return 1.20, 0.80
    if margin >= 1:
        return 1.05, 0.95
    if margin <= -17 and qtr >= 4:
        return 0.55, 1.15
    if margin <= -9:
        return 0.75, 1.25
    if margin <= -1:
        return 0.90, 1.10
    return 1.0, 1.0


def live_state(date="20261108"):
    sb = json.loads(subprocess.run(["curl", "-sS", "-m", "30",
                                    f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date}"],
                                   capture_output=True, text=True).stdout)
    out = {}
    for e in sb["events"]:
        c = e["competitions"][0]
        st = c["status"]
        if st["type"]["state"] != "in":
            continue
        tm = {t["homeAway"]: TEAM_FIX.get(t["team"]["abbreviation"], t["team"]["abbreviation"]) for t in c["competitors"]}
        sc = {TEAM_FIX.get(t["team"]["abbreviation"], t["team"]["abbreviation"]): int(t["score"]) for t in c["competitors"]}
        qtr = st["period"]
        m, s = (st["displayClock"] or "0:00").split(":")
        secs_left = int(m) * 60 + int(s) + max(0, 4 - qtr) * QTR_SECS
        gid = f"2026_09_{tm['away']}_{tm['home']}"
        out[gid] = {"qtr": qtr, "clock": st["displayClock"], "secs_left": secs_left, "frac_left": secs_left / 3600,
                    "score": sc, "away": tm["away"], "home": tm["home"], "detail": st["type"]["shortDetail"]}
    return out


def price(F: pd.DataFrame, stats: pd.DataFrame, state: dict, min_p=0.10) -> pd.DataFrame:
    rows = []
    stats = stats.assign(nk=stats.name.map(nkey)) if len(stats) else stats
    for gid, g in state.items():
        q = F[F.game_id == gid]
        if q.empty:
            continue
        total_line = q.total_line.iloc[0] if "total_line" in q else np.nan
        pts = sum(g["score"].values())
        played = 1 - g["frac_left"]
        exp_so_far = (total_line if not np.isnan(total_line) else 45) * played
        pace = float(np.clip((pts + 7) / (exp_so_far + 7), 0.7, 1.4)) if played > 0.25 else 1.0
        for r in q.itertuples():
            margin = g["score"][r.team] - g["score"][r.opp]
            mr, mp = script(margin, g["qtr"])
            # anchor to the full pre-game model: lam0 reproduces p_attd at kickoff; script shifts the rush/pass mix
            rush_part, pass_part = r.lam_team_rush * r.rush_share, r.lam_team_pass * r.rec_share
            mix = (rush_part * mr + pass_part * mp) / max(rush_part + pass_part, 1e-9)
            lam0 = -np.log(max(1 - r.p_attd, 1e-6))
            lam = lam0 * mix * g["frac_left"] * pace
            p = 1 - np.exp(-lam)
            row = stats[(stats.nk == nkey(r.name)) & (stats.team == r.team)] if len(stats) else pd.DataFrame()
            car = int(row.car.iloc[0]) if len(row) else 0
            rec = int(row.rec.iloc[0]) if len(row) else 0
            td = int(row.td.iloc[0]) if len(row) else 0
            touches = car + rec
            exp_touch = (r.carries_e3 + r.targets_e3 * 0.65) * played
            usage = "" if exp_touch < 3 else ("no touches: check status" if touches == 0 and played > 0.4 else
                                              ("light usage" if touches < 0.5 * exp_touch else
                                               ("heavy usage" if touches > 1.4 * exp_touch else "")))
            if p >= min_p:
                rows.append({"game": gid[8:].replace("_", "@"), "state": f"Q{g['qtr']} {g['clock']}",
                             "score": f"{g['away']} {g['score'][g['away']]}–{g['home']} {g['score'][g['home']]}",
                             "team": r.team, "player": r.name, "pos": r.pos_group, "margin": margin,
                             "pregame": r.p_attd, "p_live": p, "scored": td, "touches": f"{car} car / {rec} rec",
                             "usage": usage, "script": ("trailing" if margin < 0 else "leading" if margin > 0 else "tied")})
    return pd.DataFrame(rows).sort_values("p_live", ascending=False)


def fair(p):
    p = float(np.clip(p, 1e-4, 1 - 1e-4))
    a = int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))
    return f"+{a}" if a > 0 else str(a)
