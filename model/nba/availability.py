"""Availability gate: who is confirmed in, questionable, doubtful, out or unknown for a game.

Sources, each with its timestamp: the official NBA injury report (status), the box-score history
(games missed, games since return) and, on the day, ESPN's injury notes (minutes restrictions).
Only players the gate marks "confirmed in" may appear on a ticket. Questionable players are
still projected, but flagged and held off tickets until a later report confirms them.

Limits, stated plainly:
- The official report does not publish minutes restrictions. They are read from ESPN's free-text
  injury notes when a note says so, which catches some and misses others. History has none.
- No free source we can reach confirms starters before tip-off. "confirmed in" therefore means
  "cleared to play", not "confirmed starter". Starter status comes from the role model.
"""
import re

import pandas as pd

from nba.config import CONFIG

ORDER = ["confirmed_in", "questionable", "doubtful", "out", "unknown"]


def roster(pit, team_id: str, last_games: int = 15) -> pd.DataFrame:
    """Players whose most recent box-score line (played or not) is with this team in its recent games."""
    pg, g = pit.table("player_games"), pit.table("games")
    if g.empty:
        return pd.DataFrame(columns=["player_id", "name", "pos"])
    order = g.set_index("game_id").tip_utc
    pg = pg.assign(tip=pg.game_id.map(order)).sort_values("tip")
    latest = pg.drop_duplicates("player_id", keep="last")
    team_games = g[(g.home_id == team_id) | (g.away_id == team_id)].sort_values("tip_utc").game_id.tail(last_games)
    r = latest[(latest.team_id == team_id) & latest.game_id.isin(team_games)]
    return r[["player_id", "name", "pos"]].reset_index(drop=True)


def absence_history(pit, team_id: str, player_ids) -> dict:
    """For each player: games missed in his latest absence and games played since he came back."""
    pg, g = pit.table("player_games"), pit.table("games")
    tg = g[(g.home_id == team_id) | (g.away_id == team_id)].sort_values("tip_utc").game_id.tolist()
    played = pg[(pg.dnp == 0) & (pg["min"] > 0) & pg.game_id.isin(tg)]
    sets = played.groupby("player_id").game_id.apply(set).to_dict()
    out = {}
    for pid in player_ids:
        seq = [gid in sets.get(pid, ()) for gid in tg]
        since = missed = 0
        i = len(seq) - 1
        while i >= 0 and seq[i]:
            since += 1; i -= 1
        while i >= 0 and not seq[i]:
            missed += 1; i -= 1
        if i < 0 and missed:        # never played for this team before the gap: new arrival, not an injury return
            missed = 0
        out[pid] = {"games_since_return": since, "games_missed": missed, "currently_out_games": 0 if since else missed}
    return out


def restriction_from_text(text: str | None, cfg=CONFIG):
    """Minutes cap if a note states one, True if it mentions a restriction without a number, else None."""
    if not text:
        return None
    t = text.lower()
    if "minute" not in t or not re.search(r"restrict|limit|cap", t):
        return None
    m = re.search(cfg["restriction_pattern"], t)
    return float(m.group(1)) if m else True


def gate(pit, game: dict, espn_notes: dict | None = None, cfg=CONFIG) -> pd.DataFrame:
    """Status for every rostered player of both teams, from what was known before `pit.as_of`.

    game: game_id, date_et, home_id, away_id, home (full names resolved by the caller into `team_names`)."""
    rep = pit.table("injury_reports")
    rep = rep[rep.game_date == game["date_et"]]
    latest_time = rep.report_utc.max() if len(rep) else None
    rep = rep[rep.report_utc == latest_time] if latest_time else rep
    rows = []
    for tid, tname in ((game["home_id"], game["home_name"]), (game["away_id"], game["away_name"])):
        team_rep = rep[rep.team == tname]
        filed = len(rep) > 0 and not (team_rep.status == "NOT YET SUBMITTED").any()
        listed = {r.player_id: r for r in team_rep.itertuples() if r.player_id}
        ros = roster(pit, tid)
        hist = absence_history(pit, tid, ros.player_id)
        for p in ros.itertuples():
            h = hist[p.player_id]
            if p.player_id in listed:
                r = listed[p.player_id]
                status, reason = cfg["status_map"].get(r.status.lower(), "unknown"), r.reason
            elif filed:
                status, reason = cfg["unlisted_status"], None
            else:
                status, reason = cfg["unsubmitted_status"], ("team has not filed its report" if len(rep) else "no report yet")
            note = (espn_notes or {}).get(p.player_id)
            restr = restriction_from_text(reason, cfg) or restriction_from_text(note, cfg)
            ramp = h["games_missed"] >= cfg["absence_min_games"] and h["games_since_return"] < cfg["return_ramp_games"]
            rows.append({"game_id": game["game_id"], "player_id": p.player_id, "team_id": tid, "name": p.name, "pos": p.pos,
                         "status": status, "reason": reason,
                         "minutes_restriction": (restr if isinstance(restr, float) else (-1.0 if restr else None)),
                         "games_since_return": h["games_since_return"] if ramp or h["games_missed"] else None,
                         "games_missed": h["games_missed"], "on_ramp": int(ramp), "source_time": latest_time,
                         "ticket_eligible": int(status in cfg["ticket_statuses"]),
                         "projected": int(status in cfg["projected_statuses"])})
        for r in team_rep.itertuples():      # listed but not on our roster view (new signing, two-way, unmatched name)
            if r.player_name and (not r.player_id or r.player_id not in set(ros.player_id)):
                rows.append({"game_id": game["game_id"], "player_id": r.player_id, "team_id": tid, "name": r.player_name,
                             "pos": None, "status": cfg["status_map"].get(r.status.lower(), "unknown"), "reason": r.reason,
                             "minutes_restriction": None, "games_since_return": None, "games_missed": None, "on_ramp": 0,
                             "source_time": latest_time, "ticket_eligible": 0, "projected": 0})
    return pd.DataFrame(rows)


def changes(before: pd.DataFrame, after: pd.DataFrame) -> list[dict]:
    """Status changes between two runs of the gate, each with who must be recalculated."""
    if before is None or before.empty:
        return []
    b = before.dropna(subset=["player_id"]).set_index("player_id").status.to_dict()
    out = []
    for r in after.dropna(subset=["player_id"]).itertuples():
        old = b.get(r.player_id)
        if old is not None and old != r.status:
            mates = after[(after.team_id == r.team_id) & (after.player_id != r.player_id) & (after.projected == 1)]
            out.append({"player_id": r.player_id, "name": r.name, "team_id": r.team_id, "game_id": r.game_id,
                        "from": old, "to": r.status, "recalculate": mates.player_id.tolist(),
                        "remove_legs": r.status not in CONFIG["ticket_statuses"]})
    return out


def apply_to_legs(legs: list[dict], gate_df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Split legs into (still eligible, removed) under the current gate. Game legs have no player."""
    ok = set(gate_df[gate_df.ticket_eligible == 1].player_id)
    keep = [l for l in legs if l.get("player_id") is None or l["player_id"] in ok]
    return keep, [l for l in legs if l not in keep]
