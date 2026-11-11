"""Assemble the master pre-game frame every model reads: features, expected absences from the
injury report (point-in-time), baseline minutes, teammate in/out adjustments and return-from-injury counters."""
from datetime import timedelta

import numpy as np
import pandas as pd

from nba import features, inout
from nba.config import CONFIG
from nba.ids import TEAMS


def report_view(inj: pd.DataFrame, games: pd.DataFrame, abbr_to_id: dict, cfg=CONFIG):
    """For each game: who the last report before (tip - lead) lists as out/doubtful/questionable,
    and which teams had filed. Returns (out, questionable, filed) dicts keyed by game_id."""
    out, ques, filed = {}, {}, {}
    if inj is None or inj.empty:
        return out, ques, filed
    name_to_id = {TEAMS[a][0]: tid for a, tid in abbr_to_id.items() if a in TEAMS}
    inj = inj.assign(rt=pd.to_datetime(inj.report_utc, utc=True), team_id=inj.team.map(name_to_id))
    by_date = {d: x for d, x in inj.groupby("game_date")}
    lead = timedelta(minutes=cfg["injury_report_lead_min"])
    for g in games.itertuples():
        d = by_date.get(g.date_et)
        if d is None:
            continue
        cut = pd.Timestamp(g.tip_utc) - lead
        d = d[(d.rt <= cut) & d.team_id.isin([g.home_id, g.away_id])]
        if d.empty:
            continue
        d = d[d.rt == d.rt.max()]
        sub = d[d.status != "NOT YET SUBMITTED"]
        not_filed = set(d[d.status == "NOT YET SUBMITTED"].team_id)
        filed[g.game_id] = {t for t in (g.home_id, g.away_id) if t not in not_filed}
        st = sub.status.str.lower().map(cfg["status_map"])
        out[g.game_id] = set(sub[st.isin(["out", "doubtful"])].player_id.dropna())
        ques[g.game_id] = set(sub[st == "questionable"].player_id.dropna())
    return out, ques, filed


def return_counter(P: pd.DataFrame, gap_days: float = 7.0) -> pd.Series:
    """Games played since coming back from an absence, as known before each game (0 = first game back).
    99 = no recent absence. A summer break is not an absence."""
    pl = P[P.played == 1].sort_values(["player_id", "tip"])
    gap = pl.groupby("player_id").tip.diff().dt.total_seconds() / 86400
    new_season = pl.groupby("player_id").season.diff().fillna(1) != 0
    back = (gap >= gap_days) & ~new_season
    blk = back.groupby(pl.player_id).cumsum()
    cnt = pl.groupby([pl.player_id, blk]).cumcount()
    after = pd.Series(np.where(blk > 0, cnt, 99), index=pl.index)          # counter value of that game itself
    state = pd.DataFrame({"player_id": pl.player_id, "known": pl.known, "ret_after": after, "st_season": pl.season})
    m = features._asof(P[["player_id", "tip", "season", "days_since_played"]].assign(_i=P.index), state, "player_id")
    same = m.st_season == m.season
    val = np.where(~same, 99, np.where(m.days_since_played >= gap_days, 0, np.minimum(m.ret_after.fillna(99) + 1, 99)))
    return pd.Series(val, index=m._i).reindex(P.index)


def master(frames: dict, pending_games=None, pending_rosters=None, live_out: dict | None = None,
           live_ques: dict | None = None, live_filed: dict | None = None, cfg=CONFIG) -> dict:
    F = features.build(frames, pending_games, pending_rosters, cfg)
    P, T = F["players"], F["teams"]
    games = frames["games"]
    all_games = games if pending_games is None else pd.concat([games, pending_games[~pending_games.game_id.isin(games.game_id)]])
    abbr = dict(zip(frames["schedule"].home, frames["schedule"].home_id))
    out, ques, filed = report_view(frames.get("injury_reports"), all_games, abbr, cfg)
    for d, live in ((out, live_out), (ques, live_ques), (filed, live_filed)):
        if live:
            d.update(live)
    P = P.copy()
    P["base_min"] = inout.baseline_minutes(P, cfg)
    P["exp_out"] = inout.status_quo_out(P, out, filed)
    P["questionable"] = [int(p in ques.get(g, ())) for g, p in zip(P.game_id, P.player_id)]
    P["report_filed"] = [int(t in filed.get(g, ())) for g, t in zip(P.game_id, P.team_id)]
    P["ret_games"] = return_counter(P)
    io = inout.adjustments(P, cfg)
    P = P.merge(io, on=["game_id", "player_id"], how="left")
    for c in io.columns[2:-1]:
        P[c] = P[c].fillna(0.0)
    P["io_notes"] = P.io_notes.fillna("")
    return {"players": P, "teams": T, "league": F["league"], "out": out, "ques": ques, "filed": filed}
