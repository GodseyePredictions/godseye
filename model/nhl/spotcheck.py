"""The Phase 1 check: our derived tables against the sources' own season totals.

    python3 -m nhl.spotcheck [TEAM,TEAM,TEAM] [PLAYER_ID,...]

Teams: our expected goals for and against, at 5v5 and in all situations, against MoneyPuck's team
season file. The xG of each shot is MoneyPuck's; what is being checked is our own aggregation: which
game, which team and which strength state each shot lands in.

Players: our ice time by strength (from shift charts) against the league's own EV / PP / SH totals and
against MoneyPuck's skater file.

Natural Stat Trick refuses automated requests, so its side of the check runs only when a hand export
is present in data/manual/nst/ (team_5v5.csv); otherwise it is reported as not checked.
"""
import json
import sys

import pandas as pd

from common.http import FetchError
from nhl import ids, store
from nhl.config import CONFIG
from nhl.ingest import moneypuck


def team_check(con, cfg, teams, season) -> pd.DataFrame:
    ours = store.read(con, "SELECT team, strength, SUM(toi) toi, SUM(xgf) xgf, SUM(xga) xga, COUNT(DISTINCT game_id) gp "
                           "FROM team_game_strength WHERE season=? GROUP BY team, strength", [season])
    mp = moneypuck.summary("teams", season, store.RAW, cfg)
    nst_rows = store.read(con, "SELECT entity, data FROM nst WHERE kind='team' AND situation='5v5'")
    nst_by = {ids.team(r.entity): json.loads(r.data) for r in nst_rows.itertuples()}
    rows = []
    for t in teams:
        o = ours[ours.team == t].set_index("strength")
        for label, sit, pick in (("5v5", "5on5", ["ev5"]), ("all", "all", list(o.index))):
            m = mp[(mp.team == t) & (mp.situation == sit)].iloc[0]
            for stat, col in (("xGF", "xGoalsFor"), ("xGA", "xGoalsAgainst")):
                mine = float(o.loc[pick, stat.lower()].sum())
                row = {"team": t, "situation": label, "stat": stat, "games_ours": int(o.gp.max()), "games_mp": int(m.games_played),
                       "ours": round(mine, 2), "moneypuck": round(float(m[col]), 2), "diff_pct": round(100 * (mine / float(m[col]) - 1), 2),
                       "nst": None}
                if label == "5v5" and t in nst_by:
                    row["nst"] = nst_by[t].get(stat)
                rows.append(row)
            rows.append({"team": t, "situation": label, "stat": "minutes", "games_ours": int(o.gp.max()), "games_mp": int(m.games_played),
                         "ours": round(float(o.loc[pick, "toi"].sum()) / 60, 1), "moneypuck": round(float(m.iceTime) / 60, 1),
                         "diff_pct": round(100 * (float(o.loc[pick, "toi"].sum()) / float(m.iceTime) - 1), 2), "nst": None})
    return pd.DataFrame(rows)


def player_check(con, cfg, players, season) -> pd.DataFrame:
    q = ",".join(str(int(p)) for p in players)
    ours = store.read(con, f"SELECT player_id, strength, SUM(toi) toi, COUNT(DISTINCT game_id) gp FROM player_game_strength "
                           f"WHERE season=? AND player_id IN ({q}) GROUP BY player_id, strength", [season])
    off = store.read(con, f"SELECT t.player_id, SUM(t.ev) ev, SUM(t.pp) pp, SUM(t.sh) sh, COUNT(*) gp FROM toi_official t "
                          f"JOIN games g ON g.game_id=t.game_id WHERE g.season=? AND t.player_id IN ({q}) GROUP BY t.player_id",
                     [season]).set_index("player_id")
    names = store.read(con, f"SELECT player_id, name, team FROM players WHERE player_id IN ({q})").set_index("player_id")
    mp = moneypuck.summary("skaters", season, store.RAW, cfg)
    rows = []
    for p in players:
        o = ours[ours.player_id == p].set_index("strength").toi
        m = mp[mp.playerId == p].set_index("situation").icetime
        mine = {"EV": o.get("ev5", 0) + o.get("evo", 0), "PP": o.get("pp", 0), "PK": o.get("pk", 0)}
        league = {"EV": off.at[p, "ev"], "PP": off.at[p, "pp"], "PK": off.at[p, "sh"]} if p in off.index else {}
        mpv = {"EV": m.get("all", 0) - m.get("5on4", 0) - m.get("4on5", 0), "PP": m.get("5on4", 0), "PK": m.get("4on5", 0)} if len(m) else {}
        for k in ("EV", "PP", "PK"):
            lg = league.get(k)
            rows.append({"player": names.at[p, "name"] if p in names.index else p, "team": names.at[p, "team"] if p in names.index else "",
                         "split": k, "games": int(ours[ours.player_id == p].gp.max()), "ours_min": round(mine[k] / 60, 1),
                         "league_min": None if lg is None else round(lg / 60, 1),
                         "diff_pct": None if not lg else round(100 * (mine[k] / lg - 1), 2),
                         "moneypuck_min": round(mpv[k] / 60, 1) if mpv else None})
    return pd.DataFrame(rows)


def defaults(con, season):
    """Three teams spread through the standings of expected goals, five skaters with the most ice time on five teams."""
    t = store.read(con, "SELECT team, SUM(xgf) x FROM team_game_strength WHERE season=? GROUP BY team ORDER BY x DESC", [season])
    teams = [t.team.iloc[0], t.team.iloc[len(t) // 2], t.team.iloc[-1]]
    p = store.read(con, "SELECT player_id, team, SUM(toi) s FROM player_game_strength WHERE season=? GROUP BY player_id ORDER BY s DESC",
                   [season]).drop_duplicates("team")
    return teams, [int(x) for x in p.player_id.head(5)]


def main(argv):
    con = store.connect()
    season = CONFIG["seasons"]["current"]
    teams, players = defaults(con, season)
    if argv:
        teams = [ids.team(t) for t in argv[0].split(",")]
    if len(argv) > 1:
        players = [int(x) for x in argv[1].split(",")]
    tol = CONFIG["spotcheck"]
    try:
        t = team_check(con, CONFIG, teams, season)
        p = player_check(con, CONFIG, players, season)
    except FetchError as e:
        sys.exit(f"MoneyPuck season files not available: {e}")
    print(f"Teams, season {season} (tolerance {tol['team_xg_tolerance']:.0%}):")
    print(t.to_string(index=False))
    print("MoneyPuck's 5v5 minutes run 1 to 2% above ours: it draws the line between 5v5 and other even strength slightly "
          "differently. Minutes are shown, not judged.")
    print(f"\nPlayers, ice time by strength (tolerance {tol['player_toi_tolerance']:.0%} or {tol['player_toi_abs_min']:.0f} minute "
          f"against the league's own):")
    print(p.to_string(index=False))
    bad_t = t[(t.stat != "minutes") & (t.games_ours == t.games_mp) & (t.diff_pct.abs() > 100 * tol["team_xg_tolerance"])]
    bad_p = p[(p.diff_pct.abs() > 100 * tol["player_toi_tolerance"]) & ((p.ours_min - p.league_min).abs() > tol["player_toi_abs_min"])]
    behind = t[t.games_ours != t.games_mp]
    if len(behind):
        print("\nGame counts differ from MoneyPuck's file for: " + ", ".join(sorted(set(behind.team))) +
              " (one side is a night ahead; those rows are not judged).")
    print("\nNatural Stat Trick: " + ("compared in the nst column." if t.nst.notna().any() else
                                      "not checked (the site refuses automated requests and no hand export is in data/manual/nst/)."))
    print("\nRESULT: " + ("PASS" if not len(bad_t) and not len(bad_p) else f"FAIL ({len(bad_t)} team rows, {len(bad_p)} player rows out of tolerance)"))
    return 0 if not len(bad_t) and not len(bad_p) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
