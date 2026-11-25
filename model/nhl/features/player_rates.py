"""Skater per-60 rates by strength (EV / PP / PK) and goalie GSAx, as of a date.

Skaters: the season sample is this season plus last season at reduced weight. Each rate is shrunk toward
the league rate for the player's position group (forwards or defence) in proportion to ice time, then
moved toward the last 10 games, with that recent form itself shrunk by how much ice time it covers.
Sample sizes (games, minutes) sit beside every rate.

Goalies: goals saved above expected (MoneyPuck xG against minus goals against, on unblocked shots with
the goalie in net), shrunk toward league average. Under `goalie_min_starts` the goalie is priced as
league average and flagged.
"""
import numpy as np
import pandas as pd

STATS = ["sog", "icf", "iff", "ixg", "g", "a1", "a2", "hits", "blocks", "pen_taken", "pen_drawn", "on_xgf", "on_xga", "on_gf", "on_ga",
         "on_cf", "on_ca"]
ON_ICE = [c for c in STATS if c.startswith("on_")]
EV = {"ev5": "ev", "evo": "ev", "pp": "pp", "pk": "pk"}


def collapse(pgs: pd.DataFrame) -> pd.DataFrame:
    """ev5 + evo -> ev: one row per (game, player, ev/pp/pk). `toi_on` is the ice time that has on-ice
    numbers behind it: zero for a game built without a shift chart, so those games do not water down on-ice rates."""
    d = pgs.assign(strength=pgs.strength.map(EV), group=np.where(pgs.pos == "D", "D", "F"),
                   toi_on=np.where(pgs.on_xgf.notna(), pgs.toi, 0))
    keys = ["game_id", "player_id", "strength", "team", "group", "season", "date_et", "known_at"]
    return d.groupby(keys, as_index=False)[["toi", "toi_on"] + STATS].sum(min_count=1)


def build(pgs: pd.DataFrame, season: int, cfg, collapsed: bool = False) -> pd.DataFrame:
    """pgs: player_game_strength rows known before the date being priced (or `collapse`d already)."""
    c = cfg["rates"]
    d = pgs[pgs.season.isin([season, season - 1])]
    d = d.copy() if collapsed else collapse(d)
    d[STATS] = d[STATS].fillna(0.0)
    d["w"] = np.where(d.season == season, 1.0, c["prior_season_weight"])
    cur = d[d.season == season]
    last_games = (cur.drop_duplicates(["player_id", "game_id"]).sort_values("known_at").groupby("player_id")
                  .tail(c["recent_games"])[["player_id", "game_id"]])
    rec = cur.merge(last_games, on=["player_id", "game_id"])
    key = ["player_id", "strength"]
    cols = ["toi", "toi_on"] + STATS
    wd = d[cols].mul(d.w, axis=0).join(d[key + ["group"]])
    S = wd.groupby(key)[cols].sum()
    R = rec.groupby(key)[cols].sum().reindex(S.index).fillna(0)
    latest = d.sort_values("known_at").groupby("player_id").tail(1).set_index("player_id")
    pid = S.index.get_level_values("player_id")
    out = pd.DataFrame(index=S.index)
    out["team"], out["group"] = latest.team.reindex(pid).to_numpy(), latest.group.reindex(pid).to_numpy()
    out["gp"] = cur.groupby("player_id").game_id.nunique().reindex(pid).fillna(0).astype(int).to_numpy()
    out["gp_prev"] = d[d.season == season - 1].groupby("player_id").game_id.nunique().reindex(pid).fillna(0).astype(int).to_numpy()
    out["toi_min"] = (S.toi / 60).round(1)
    out["toi_recent_min"] = (R.toi / 60).round(1)
    out["toi_on_ice_min"] = (S.toi_on / 60).round(1)
    lg = wd.groupby(["group", "strength"])[cols].sum()
    lg_idx = pd.MultiIndex.from_arrays([out["group"], S.index.get_level_values("strength")])
    prior_sec = S.index.get_level_values("strength").map(c["player_prior_toi_min"]).to_numpy() * 60.0
    for col in STATS:
        t = "toi_on" if col in ON_ICE else "toi"
        st, rt = S[t].to_numpy(), R[t].to_numpy()
        w_recent = c["player_weight_recent"] * rt / (rt + prior_sec + 1e-9)
        lg_rate = (lg[col] / lg[t] * 3600).reindex(lg_idx).to_numpy()
        ps = prior_sec * c.get("player_prior_scale", {}).get(col, 1.0)
        shrunk = (S[col].to_numpy() + lg_rate * ps / 3600) / (st + ps) * 3600
        recent = np.where(rt > 0, R[col].to_numpy() / np.maximum(rt, 1) * 3600, shrunk)
        out[f"{col}60"] = (1 - w_recent) * shrunk + w_recent * recent
        out[f"{col}60_raw"] = np.where(st > 0, S[col].to_numpy() / np.maximum(st, 1) * 3600, np.nan)
    out["sog_per_attempt"] = out.sog60 / out.icf60
    out["assists_per_on_xgf"] = (out.a160 + out.a260) / out.on_xgf60
    tot = wd.groupby("player_id")[["g", "ixg"]].sum()
    k = c["finishing_prior_xg"]
    out["finishing"] = ((tot.g + k) / (tot.ixg + k)).reindex(pid).to_numpy()
    return out.reset_index().assign(season=season)


def goalies(gg: pd.DataFrame, season: int, cfg) -> pd.DataFrame:
    """gg: goalie_game rows known before the date being priced."""
    c = cfg["rates"]
    d = gg[gg.season.isin([season, season - 1])].copy()
    if d.empty:
        return pd.DataFrame()
    d["w"] = np.where(d.season == season, 1.0, c["prior_season_weight"])
    cols = ["toi", "sa", "ga", "xga", "unblocked", "xg_ga"]
    S = d[cols].mul(d.w, axis=0).join(d[["player_id"]]).groupby("player_id").sum()
    out = pd.DataFrame(index=S.index)
    out["team"] = d.sort_values("known_at").groupby("player_id").team.last()
    out["starts"] = d[d.starter == 1].groupby("player_id").game_id.nunique().reindex(S.index).fillna(0).astype(int)
    out["starts_season"] = d[(d.starter == 1) & (d.season == season)].groupby("player_id").game_id.nunique().reindex(S.index).fillna(0).astype(int)
    out["toi_min"] = (S.toi / 60).round(1)
    out["unblocked"] = S.unblocked.round(1)
    out["sv_pct"] = 1 - S.ga / S.sa.where(S.sa > 0)
    out["gsax"] = (S.xga - S.xg_ga).round(2)
    out["gsax60_raw"] = (S.xga - S.xg_ga) / S.toi.where(S.toi > 0) * 3600
    league_per60 = S.unblocked.sum() / S.toi.sum() * 3600
    enough = out.starts >= c["goalie_min_starts"]
    per_shot = (S.xga - S.xg_ga) / (S.unblocked + c["goalie_prior_shots"])
    out["below_min_sample"] = (~enough).astype(int)
    out["gsax60"] = np.where(enough, per_shot * league_per60, 0.0)
    out["league_xga60"] = S.xga.sum() / S.toi.sum() * 3600
    return out.reset_index().assign(season=season)
