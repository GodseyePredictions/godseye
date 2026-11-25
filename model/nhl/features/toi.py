"""Rolling ice-time projection per skater, split EV / PP / PK. Feeds every skater prop.

Base: the last 10 games shrunk toward the season (a player short of games this season leans on last
season). Then, when tonight's Daily Faceoff lines are in hand and fresh:

  * even strength moves by part of the gap between the usual minutes of the line or pair he is slotted on
    tonight and those of the line or pair his own minutes rank him on (same slot as usual: no change);
  * power play follows the unit: PP1 gets about 62% of the team's power-play time, PP2 the rest. A player
    already above his unit's share keeps part of the surplus; one below it is lifted to it; a player on
    neither unit keeps only a small share of his usual time;
  * a player on injured reserve or missing from the lineup is flagged `in_lineup = 0`.

Each row keeps the base beside the final number and says in `notes` what moved it. The game-script
trims (blowouts, trailing teams) come from the game sim in a later phase.
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from nhl.features.player_rates import collapse

SPLIT = ["ev", "pp", "pk"]
SLOTS = {"f1": ("F", 0, 3), "f2": ("F", 3, 6), "f3": ("F", 6, 9), "f4": ("F", 9, 12),
         "d1": ("D", 0, 2), "d2": ("D", 2, 4), "d3": ("D", 4, 6)}


def base(pgs: pd.DataFrame, season: int, cfg, collapsed: bool = False) -> pd.DataFrame:
    c = cfg["toi"]
    d = pgs[pgs.season.isin([season, season - 1])]
    d = d if collapsed else collapse(d)
    wide = d.pivot_table(index=["player_id", "game_id", "season", "known_at", "team", "group"], columns="strength", values="toi",
                         aggfunc="sum", fill_value=0).reset_index()
    for s in SPLIT:
        if s not in wide:
            wide[s] = 0
    wide = wide.sort_values("known_at")
    cur, prev = wide[wide.season == season], wide[wide.season == season - 1]
    n = cur.groupby("player_id").size()
    last = wide.groupby("player_id").tail(1).set_index("player_id")
    out = pd.DataFrame({"team": last.team, "group": last.group})
    out["gp"] = n.reindex(out.index).fillna(0).astype(int)
    rec = cur.groupby("player_id").tail(c["recent_games"])
    out["n_recent"] = rec.groupby("player_id").size().reindex(out.index).fillna(0).astype(int)
    top_up = (c["prior_games"] - out.gp).clip(lower=0)
    w = c["weight_recent"] * out.n_recent / c["recent_games"]
    for s in SPLIT:
        cur_sum = cur.groupby("player_id")[s].sum().reindex(out.index).fillna(0)
        prev_mean = prev.groupby("player_id")[s].mean().reindex(out.index)
        use_top = top_up.where(prev_mean.notna(), 0)
        season_mean = (cur_sum + prev_mean.fillna(0) * use_top) / (out.gp + use_top).replace(0, np.nan)
        recent_mean = rec.groupby("player_id")[s].mean().reindex(out.index)
        out[f"{s}_base"] = (w * recent_mean.fillna(season_mean) + (1 - w) * season_mean).round(1)
    return out.dropna(subset=["ev_base"]).reset_index()


def project(pgs: pd.DataFrame, season: int, cfg, lines: pd.DataFrame | None = None, team_pp_sec: dict | None = None,
            as_of: str | None = None, collapsed: bool = False) -> pd.DataFrame:
    """Seconds of EV / PP / PK ice time per game for every skater seen this season or last.

    lines: the latest Daily Faceoff rows per team (with player_id). team_pp_sec: {team: power-play seconds per game}."""
    c = cfg["toi"]
    out = base(pgs, season, cfg, collapsed)
    for s in SPLIT:
        out[s] = out[f"{s}_base"]
    out["ev_slot"], out["pp_unit"], out["in_lineup"], out["notes"] = None, None, None, ""
    if lines is not None and len(lines) and as_of:
        limit = (datetime.fromisoformat(as_of.replace("Z", "+00:00")) - timedelta(hours=c["lines_max_age_hours"]))
        t = pd.to_datetime(lines.source_time, utc=True, errors="coerce")
        lines = lines[(t >= limit) & lines.player_id.notna()]
    if lines is not None and len(lines):
        out = out.set_index("player_id")
        note = {p: [] for p in out.index}
        for team, L in lines.groupby("team"):
            L = L.assign(player_id=L.player_id.astype("int64"))
            mine = out[out.team == team]
            dressed = set(L[L.category.isin(["ev"]) & (L.unit != "g")].player_id)
            hurt = set(L[L.unit == "ir"].player_id)
            for p in mine.index:
                out.at[p, "in_lineup"] = int(p in dressed and p not in hurt)
                if p in hurt:
                    note[p].append("injured reserve")
            usual, ranked_slot = {}, {}
            for unit, (grp, a, b) in SLOTS.items():
                ranked = mine[mine.group == grp].sort_values("ev_base", ascending=False)
                if len(ranked) > a:
                    usual[unit] = ranked.ev_base.iloc[a:b].mean()
                    for p in ranked.index[a:b if unit not in ("f4", "d3") else None]:
                        ranked_slot[p] = unit                           # depth players beyond the last slot count as that slot
            for unit in SLOTS:
                for p in L[L.unit == unit].player_id:
                    if p in out.index and unit in usual and p in ranked_slot:
                        before = out.at[p, "ev_base"]
                        out.at[p, "ev"] = round(before + c["line_slot_weight"] * (usual[unit] - usual[ranked_slot[p]]), 1)
                        out.at[p, "ev_slot"] = unit
                        if ranked_slot[p] != unit:
                            note[p].append(f"{unit} tonight, usually {ranked_slot[p]} minutes: {out.at[p, 'ev'] - before:+.0f}s EV")
            pp = (team_pp_sec or {}).get(team)
            on_unit = {}
            for unit, share in (("pp1", c["pp1_share"]), ("pp2", c["pp2_share"])):
                for p in L[L.unit == unit].player_id:
                    on_unit.setdefault(p, (unit, share))
            for p in mine.index:
                if p in on_unit and pp:
                    unit, share = on_unit[p]
                    target, own = share * pp, out.at[p, "pp_base"]
                    out.at[p, "pp"] = round(target + c["pp_surplus_kept"] * max(0.0, own - target), 1)
                    out.at[p, "pp_unit"] = unit
                    note[p].append(f"{unit}: {share:.0%} of {pp:.0f}s team PP" + (", plus part of his surplus" if own > target else ""))
                elif p in dressed and (L.unit.isin(["pp1", "pp2"])).any():
                    out.at[p, "pp"] = round(out.at[p, "pp_base"] * c["pp_off_unit_factor"], 1)
                    if out.at[p, "pp_base"] >= 30:
                        note[p].append("on neither PP unit")
        out["notes"] = [", ".join(note[p]) for p in out.index]
        out = out.reset_index()
    out["total"] = out.ev + out.pp + out.pk
    return out.assign(season=season)
