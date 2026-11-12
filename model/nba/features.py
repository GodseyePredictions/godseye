"""Pre-game features for every player and team in every game, built point-in-time.

The rule that keeps the future out: a game's numbers are filed under the moment the game ended
(`known_at`). A feature for a target game is looked up by that game's tip-off time and may only
take the latest state filed strictly before it. One lookup (`_asof`) does this for every feature,
so there is a single place where leakage could happen and one test that guards it.

Tonight's games are handled the same way: they are appended as rows with no results, and their
features come out of the same lookup.
"""
import numpy as np
import pandas as pd

from nba.config import CONFIG
from nba.schedule import team_schedule_features

BOX = ["min", "pts", "reb", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
       "rim_a", "rim_m", "mid_a", "mid_m", "c3_a", "c3_m", "ab3_a", "ab3_m", "q4_fga", "q4_pts", "sec_q4", "starter"]
TEAM_SUM = ["pts", "reb", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
            "rim_a", "rim_m", "mid_a", "mid_m", "c3_a", "c3_m", "ab3_a", "ab3_m"]
POS = {"PG": "G", "SG": "G", "G": "G", "SF": "F", "PF": "F", "F": "F", "C": "C"}


def _dt(s):
    return pd.to_datetime(s, utc=True)


def _asof(target: pd.DataFrame, state: pd.DataFrame, by: str | None) -> pd.DataFrame:
    """For each target row (keyed by `tip`), the latest state row with known < tip. Never equal, never later."""
    t = target.sort_values("tip")
    s = state.rename(columns={"known": "_state_known"}).sort_values("_state_known")
    out = pd.merge_asof(t, s, left_on="tip", right_on="_state_known", by=by, direction="backward", allow_exact_matches=False)
    return out.drop(columns=["_state_known"])


def team_games(games: pd.DataFrame, pg: pd.DataFrame, pending: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per team per game: results, box totals for and against, possessions."""
    g = games.copy()
    g["pending"] = 0
    if pending is not None and len(pending):
        p = pending[~pending.game_id.isin(g.game_id)].copy()
        p["pending"], p["known_at"] = 1, None
        g = pd.concat([g, p], ignore_index=True)
    sides = []
    for h in (1, 0):
        me, op = ("home", "away") if h else ("away", "home")
        mq, oq = ("h", "a") if h else ("a", "h")
        d = pd.DataFrame({"game_id": g.game_id, "season": g.season, "date_et": g.date_et, "tip": _dt(g.tip_utc),
                          "known": _dt(g.known_at), "team_id": g[f"{me}_id"], "opp_id": g[f"{op}_id"], "team": g[me],
                          "is_home": h * (1 - g.neutral.fillna(0)) + 0.5 * g.neutral.fillna(0), "side_home": h, "pending": g.pending,
                          "team_pts": g.get(f"{me}_pts"), "opp_pts": g.get(f"{op}_pts"), "periods": g.get("periods")})
        if "hq1" in g:
            d["q4_entry"] = sum(g[f"{mq}q{q}"] - g[f"{oq}q{q}"] for q in (1, 2, 3))
            d["max_lead_2h"] = g[f"max_lead_2h_{me}"]
            d["max_deficit_2h"] = g[f"max_lead_2h_{op}"]
            d["close_last5"] = g.close_last5
        sides.append(d)
    t = pd.concat(sides, ignore_index=True)
    t["margin"] = t.team_pts - t.opp_pts
    played = pg[pg["min"] > 0]
    tot = played.groupby(["game_id", "team_id"])[TEAM_SUM].sum().reset_index()
    t = t.merge(tot, on=["game_id", "team_id"], how="left")
    opp = tot.rename(columns={c: "o_" + c for c in TEAM_SUM}).rename(columns={"team_id": "opp_id"})
    t = t.merge(opp, on=["game_id", "opp_id"], how="left")
    own = t.fga - t.oreb + t.tov + 0.44 * t.fta
    other = t.o_fga - t.o_oreb + t.o_tov + 0.44 * t.o_fta
    t["poss"] = (own + other) / 2
    t["reg_min"] = 48 + 5 * (t.periods.fillna(4) - 4)
    return t


def player_rows(pg: pd.DataFrame, tg: pd.DataFrame, pending_rosters: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every box-score line (played or not) with its game context; tonight's rostered players appended."""
    cols = ["game_id", "team_id", "player_id", "name", "pos", "dnp", "reason"] + BOX
    p = pg[cols].copy()
    if pending_rosters is not None and len(pending_rosters):
        r = pending_rosters[["game_id", "team_id", "player_id", "name", "pos"]].copy()
        for c in BOX + ["dnp"]:
            r[c] = np.nan
        r["reason"] = None
        p = pd.concat([p, r], ignore_index=True)
    ctx = tg[["game_id", "team_id", "opp_id", "season", "date_et", "tip", "known", "is_home", "pending", "margin",
              "q4_entry", "poss", "reg_min", "periods"]]
    p = p.merge(ctx, on=["game_id", "team_id"], how="inner")
    p["grp"] = p.pos.map(POS).fillna("F")
    p["played"] = ((p["min"] > 0) & (p.pending == 0)).astype(int)
    return p


def player_state(p: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Pre-game form for every player row: season to date, last 5, last 10, last season."""
    pl = p[p.played == 1].sort_values(["player_id", "known"]).copy()
    pl["n"] = 1
    cols = BOX + ["n"]
    gs = pl.groupby(["player_id", "season"], sort=False)
    season = gs[cols].cumsum().add_prefix("s_")
    gp = pl.groupby("player_id", sort=False)
    l5 = gp[cols].rolling(cfg["form_games"], min_periods=1).sum().reset_index(level=0, drop=True).add_prefix("l5_")
    l10 = gp[cols].rolling(10, min_periods=1).sum().reset_index(level=0, drop=True).add_prefix("l10_")
    state = pd.concat([pl[["player_id", "known", "season", "team_id"]].rename(
        columns={"season": "state_season", "team_id": "last_team"}), season, l5, l10], axis=1)
    state["last_played"] = state["known"]
    out = _asof(p, state, "player_id")
    stale = out.state_season != out.season          # the latest state is from an earlier season
    for c in cols:
        out.loc[stale, "s_" + c] = 0.0
    out[[c for c in out if c.startswith("s_")]] = out[[c for c in out if c.startswith("s_")]].fillna(0.0)
    prev = pl.groupby(["player_id", "season"])[cols].sum().add_prefix("prev_").reset_index()
    prev["prev_team"] = pl.groupby(["player_id", "season"]).team_id.last().to_numpy()
    prev["season"] += 1
    out = out.merge(prev, on=["player_id", "season"], how="left")
    pc = [c for c in out if c.startswith("prev_") and c != "prev_team"]
    out[pc] = out[pc].fillna(0.0)
    # a player on a new team: last season's role says less about this one, so it gets less weight everywhere
    out["changed_team"] = (out.prev_team.notna() & (out.prev_team != out.team_id)).astype(int)
    out["prev_w"] = np.where(out.changed_team == 1, cfg["team_change_prev_factor"], 1.0)
    out["days_since_played"] = (out.tip - out.last_played).dt.total_seconds() / 86400
    return out


def team_state(tg: pd.DataFrame, pg_rows: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Pre-game team style for and against, season to date with last season as a prior, plus
    what each defence has allowed to guards, forwards and centres."""
    done = tg[tg.pending == 0].sort_values(["team_id", "known"]).copy()
    done["n"] = 1
    base = TEAM_SUM + ["o_" + c for c in TEAM_SUM] + ["poss", "reg_min", "team_pts", "opp_pts", "n"]
    season = done.groupby(["team_id", "season"], sort=False)[base].cumsum().add_prefix("ts_")
    state = pd.concat([done[["team_id", "known", "season"]].rename(columns={"season": "state_season"}), season], axis=1)
    out = _asof(tg, state, "team_id")
    stale = out.state_season != out.season
    ts = [c for c in out if c.startswith("ts_")]
    out.loc[stale, ts] = 0.0
    out[ts] = out[ts].fillna(0.0)
    prev = done.groupby(["team_id", "season"])[base].sum().add_prefix("tp_").reset_index()
    prev["season"] += 1
    out = out.merge(prev, on=["team_id", "season"], how="left")
    tp = [c for c in out if c.startswith("tp_")]
    out[tp] = out[tp].fillna(0.0)

    # allowed to each position group: sums of what opposing guards / forwards / centres did against this defence
    pl = pg_rows[pg_rows.played == 1]
    stats = ["min", "pts", "reb", "ast", "stl", "blk", "fga", "fg3a", "fg3m", "fta", "tov"]
    al = pl.groupby(["game_id", "opp_id", "grp"])[stats].sum().unstack("grp").fillna(0.0)
    al.columns = [f"al_{g}_{s}" for s, g in al.columns]
    al = al.reset_index().rename(columns={"opp_id": "team_id"})
    d2 = done[["game_id", "team_id", "known", "season"]].merge(al, on=["game_id", "team_id"], how="left").fillna(0.0)
    alc = [c for c in d2 if c.startswith("al_")]
    cum = d2.groupby(["team_id", "season"], sort=False)[alc].cumsum()
    st2 = pd.concat([d2[["team_id", "known", "season"]].rename(columns={"season": "al_season"}), cum], axis=1)
    out = _asof(out, st2, "team_id")
    out.loc[out.al_season != out.season, alc] = 0.0
    out[alc] = out[alc].fillna(0.0)
    prev2 = d2.groupby(["team_id", "season"])[alc].sum().add_prefix("p").reset_index()
    prev2["season"] += 1
    out = out.merge(prev2, on=["team_id", "season"], how="left")
    out[["p" + c for c in alc]] = out[["p" + c for c in alc]].fillna(0.0)
    return out


def league_state(tg: pd.DataFrame, pg_rows: pd.DataFrame) -> pd.DataFrame:
    """League totals over the 365 days before each date (strictly earlier dates only)."""
    done = tg[tg.pending == 0]
    base = TEAM_SUM + ["poss", "reg_min", "team_pts"]
    daily = done.groupby("date_et")[base].sum()
    pl = pg_rows[pg_rows.played == 1]
    stats = ["min", "pts", "reb", "ast", "stl", "blk", "fga", "fg3a", "fg3m", "fta", "tov"]
    pos = pl.groupby(["date_et", "grp"])[stats].sum().unstack("grp").fillna(0.0)
    pos.columns = [f"lg_{g}_{s}" for s, g in pos.columns]
    daily = daily.add_prefix("lg_").join(pos, how="outer").fillna(0.0)
    daily["lg_games"] = done.groupby("date_et").size()
    daily.index = pd.to_datetime(daily.index)
    all_days = pd.to_datetime(sorted(tg.date_et.unique()))
    daily = daily.reindex(daily.index.union(all_days)).fillna(0.0)
    roll = daily.rolling("365D", closed="left").sum()        # closed="left": the day itself is excluded
    roll.index = roll.index.strftime("%Y-%m-%d")
    return roll.reset_index().rename(columns={"index": "date_et"})


def build(frames: dict, pending_games: pd.DataFrame | None = None, pending_rosters: pd.DataFrame | None = None,
          cfg=CONFIG) -> dict:
    """Everything the models read. `frames` holds games, player_games and schedule."""
    games, pg = frames["games"], frames["player_games"]
    tg = team_games(games, pg, pending_games)
    sched = frames["schedule"]
    sf = team_schedule_features(sched, cfg)
    tg = tg.merge(sf[["game_id", "team_id", "rest_days", "b2b", "three_in_four", "travel_miles", "tz_change", "game_no"]],
                  on=["game_id", "team_id"], how="left")
    rows = player_rows(pg, tg, pending_rosters)
    P = player_state(rows, cfg)
    T = team_state(tg, rows, cfg)
    L = league_state(tg, rows)
    P = P.merge(tg[["game_id", "team_id", "b2b", "three_in_four", "rest_days", "travel_miles", "tz_change", "game_no"]],
                on=["game_id", "team_id"], how="left")
    return {"players": P.reset_index(drop=True), "teams": T.reset_index(drop=True), "league": L}
