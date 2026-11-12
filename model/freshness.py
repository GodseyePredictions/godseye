"""Roster freshness audit: find players the weekly snapshot has wrong before any pick is trusted.

The console's touchdown and prop numbers are a snapshot. Between the snapshot and kickoff, players
return, get ruled out, and change roles. This audit compares the snapshot against the latest
snap counts, injury reports and roster status, and raises an alert for:

  NOT_PRICED     a player with a real role this season who is on the active roster, is not ruled
                 out, and is missing from the snapshot (how Skattebo was missed)
  ROLE_AT_RISK   a priced teammate at the same position, whose number assumed the missing player was out
  PRICED_BUT_OUT a priced player now ruled Out or Doubtful, or off the active roster
  REPORT_PENDING a team whose injury report for the coming game is not posted yet, so the above
                 cannot be confirmed

An alert stays open until overrides.json names that player. game_markets.py keeps every player
with an open alert off slips and hybrids.

Usage: python3 freshness.py      writes output/freshness.json and prints the alerts
"""
import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
CONSOLE_DATA = HERE.parent / "public" / "console" / "data.js"
TEAM_FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}
SKILL = {"QB", "RB", "WR", "TE", "FB", "HB"}
MIN_ROLE = {"QB": 0.50, "RB": 0.30, "WR": 0.35, "TE": 0.35}   # share of offensive snaps, in games played
LOOKBACK = 6    # team games


def key(s: pd.Series) -> pd.Series:
    return s.fillna("").str.lower().str.replace(r"\b(jr|sr|ii|iii|iv)\b", "", regex=True).str.replace(r"[^a-z]", "", regex=True)


def k1(s: str) -> str:
    return re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", (s or "").lower()))


def loose1(name: str) -> str:
    """First initial plus surname, so "Sam Cosmi" and "Samuel Cosmi" are the same player."""
    clean = re.sub(r"[^a-z ]", "", re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", (name or "").lower())).strip()
    parts = clean.split(None, 1)
    return clean if len(parts) < 2 else parts[0][:1] + "." + parts[1].replace(" ", "")


def audit():
    D = json.loads(CONSOLE_DATA.read_text(encoding="utf8").strip()[len("const D = "):].rstrip(";"))
    season, week = D["meta"]["season"], D["meta"]["week"]
    resolved = set()
    if (HERE / "overrides.json").exists():
        for o in json.loads((HERE / "overrides.json").read_text())["overrides"]:
            resolved |= {k1(p["name"]) for p in o["players"]}

    snaps = pd.read_csv(HERE / f"data/snap_counts/snap_counts_{season}.csv")
    snaps["team"] = snaps.team.replace(TEAM_FIX)
    snaps["key"] = key(snaps.player)
    snaps["pos"] = snaps.position.replace({"FB": "RB", "HB": "RB"})
    snaps = snaps[snaps.position.isin(SKILL) & (snaps.week < week)]

    inj = pd.read_csv(HERE / f"data/injuries/injuries_{season}.csv", low_memory=False)
    inj["team"] = inj.team.replace(TEAM_FIX)
    inj["key"] = key(inj.full_name)
    inj["loose"] = inj.full_name.map(loose1)
    cur = inj[inj.week == week]
    posted = set(cur.team)
    report = {(r.team, k_): r for r in cur.itertuples() for k_ in (r.key, r.loose)}
    prev = {(r.team, k_): r for r in inj[inj.week < week].sort_values("week").itertuples() for k_ in (r.key, r.loose)}

    ros = pd.read_csv(HERE / f"data/rosters/roster_weekly_{season}.csv", low_memory=False)
    ros["team"] = ros.team.replace(TEAM_FIX)
    ros["key"] = key(ros.full_name)
    ros["loose"] = ros.full_name.map(loose1)
    latest = ros.sort_values("week").groupby(["team", "key"]).tail(1)
    active = {(r.team, k_): r.status for r in latest.itertuples() for k_ in (r.loose, r.key)}

    priced, priced_loose = {}, {}
    for p in D["players"]:
        priced.setdefault(p["team"], {})[k1(p["name"])] = p
        priced_loose.setdefault(p["team"], {})[loose1(p["name"])] = p
    playing = {t for g in D["games"] if not g.get("started") for t in (g["home"], g["away"])}
    game_of = {t: g["id"] for g in D["games"] for t in (g["home"], g["away"])}

    alerts = []
    for team in sorted(playing):
        ts = snaps[snaps.team == team]
        weeks = sorted(ts.week.unique())[-LOOKBACK:]
        if not weeks:
            continue
        recent = ts[ts.week.isin(weeks)]
        role = recent.groupby("key").agg(name=("player", "first"), pos=("pos", "first"), share=("offense_pct", "mean"),
                                         games=("week", "nunique"), last=("week", "max")).reset_index()
        team_priced = priced.get(team, {})
        team_loose = priced_loose.get(team, {})
        pending = team not in posted
        if not team_priced:
            alerts.append({"team": team, "game_id": game_of.get(team), "type": "TEAM_NOT_PRICED", "severity": "high", "resolved": False,
                           "why": f"The snapshot has no players at all for {team}. No touchdown, prop or hybrid pick can use this team."})
            continue
        # Only one quarterback plays, so only the usual starter (most snaps lately) can be "missing".
        qbs = recent[recent.pos == "QB"].groupby("key").offense_snaps.sum()
        usual_qb = qbs.idxmax() if len(qbs) else None
        missing_by_pos = {}
        for r in role.itertuples():
            need = MIN_ROLE.get(r.pos)
            if need is None or r.share < need or r.games < 2:
                continue
            if r.pos == "QB" and r.key != usual_qb:
                continue
            lk = loose1(r.name)
            rep = report.get((team, r.key)) or report.get((team, lk))
            status = None if rep is None or pd.isna(rep.report_status) else rep.report_status
            practice = None if rep is None or pd.isna(rep.practice_status) else rep.practice_status
            on_roster = active.get((team, r.key)) or active.get((team, lk))
            base = {"team": team, "game_id": game_of.get(team), "player": r.name, "pos": r.pos,
                    "snap_share_when_played": round(float(r.share), 2), "games_in_last_6": int(r.games), "last_played_week": int(r.last),
                    "report_status": status, "practice": practice, "roster_status": on_roster, "resolved": r.key in resolved}
            if r.key not in team_priced and lk not in team_loose:
                if on_roster != "ACT" or status in ("Out", "Doubtful"):
                    continue   # correctly left out
                was = prev.get((team, r.key)) or prev.get((team, lk))
                why = (f"played {r.share:.0%} of snaps in {r.games} of the last {len(weeks)} games, is on the active roster, "
                       + ("and is not ruled out on this week's report" + (f" ({practice.lower()})" if practice else "")
                          if not pending else "and this week's injury report is not posted yet")
                       + (f"; last listed {was.report_status} in week {was.week}" if was is not None and isinstance(was.report_status, str) else "")
                       + ", but the snapshot has no number for him.")
                alerts.append({**base, "type": "NOT_PRICED", "severity": "watch" if pending else "high", "why": why})
                missing_by_pos.setdefault(r.pos, []).append(r.name)
            else:
                p = team_priced.get(r.key) or team_loose[lk]
                if status in ("Out", "Doubtful") or (on_roster is not None and on_roster != "ACT"):
                    alerts.append({**base, "type": "PRICED_BUT_OUT", "severity": "high", "snapshot_p": p["p"],
                                   "why": f"priced at {p['p']:.0%} in the snapshot but now {status or 'off the active roster (' + str(on_roster) + ')'}."})
        for pos, names in missing_by_pos.items():
            for kname, p in team_priced.items():
                if p["pos"] == pos and not p.get("singles") and p["p"] >= 0.10:
                    alerts.append({"team": team, "game_id": game_of.get(team), "player": p["name"], "pos": pos, "type": "ROLE_AT_RISK",
                                   "severity": "watch" if pending else "high", "snapshot_p": p["p"], "resolved": kname in resolved,
                                   "why": f"priced at {p['p']:.0%} assuming {', '.join(names)} would not play. If he plays, this number is too high."})
        if pending:
            alerts.append({"team": team, "game_id": game_of.get(team), "type": "REPORT_PENDING", "severity": "info", "resolved": False,
                           "why": "This week's injury report is not posted yet. Re-run after it posts."})
    out = {"season": season, "week": week, "snapshot_built": D["meta"].get("built"), "snapshot_injuries_as_of": D["meta"].get("data_asof"),
           "teams_with_report_posted": sorted(posted & playing), "alerts": alerts,
           "open": [a for a in alerts if not a.get("resolved") and a["type"] != "REPORT_PENDING"]}
    # What the pick builders must keep off every slip, ticket and hybrid until the alert is cleared.
    out["hold_players"] = sorted({f"{a['team']}|{k1(a['player'])}" for a in out["open"] if a["type"] in ("ROLE_AT_RISK", "PRICED_BUT_OUT")})
    out["hold_games"] = sorted({a["game_id"] for a in out["open"]
                                if a.get("game_id") and (a["type"] == "TEAM_NOT_PRICED" or (a.get("pos") == "QB" and a["type"] in ("NOT_PRICED", "ROLE_AT_RISK", "PRICED_BUT_OUT")))})
    return out


JS = r"""/* Generated by model/freshness.py. Players with a confirmed roster alert become singles only,
   and precomputed tickets that include them are withdrawn. */
(function(){var H=__PAYLOAD__;var ids=new Set(Object.keys(H));
D.players.forEach(function(p){if(ids.has(p.id)){p.singles=true;p.hold=true;p.risk="ON HOLD: "+H[p.id]+" "+(p.risk||"");
  if(!(D.singles||[]).some(function(x){return x.name===p.name&&x.team===p.team}))(D.singles=D.singles||[]).push({name:p.name,team:p.team,pos:p.pos,p:p.p,why:"on hold: "+H[p.id]})}});
var has=function(t){return !!t&&Array.isArray(t.legs)&&t.legs.some(function(l){return ids.has(typeof l==="string"?l:l.id)})};
var clean=function(a){return Array.isArray(a)?a.filter(function(t){return !has(t)}):a};
var A=D.algo||{};["atd","atd_combos","props","sgp"].forEach(function(k){A[k]=clean(A[k])});
Object.keys(A.atd_styles||{}).forEach(function(k){A.atd_styles[k].tickets=clean(A.atd_styles[k].tickets)});
Object.keys(D.crossgame||{}).forEach(function(k){D.crossgame[k]=clean(D.crossgame[k])});
(D.script_sgp||[]).forEach(function(t){t.ladder=clean(t.ladder||[]);["hybrid","hybrid1","hybrid2"].forEach(function(k){if(has(t[k]))t[k]=null})});
D.meta.roster_alerts=H;})();
"""


def main():
    out = audit()
    # Confirmed alerts (the team's report is posted) also reach into the console's own tickets.
    D = json.loads(CONSOLE_DATA.read_text(encoding="utf8").strip()[len("const D = "):].rstrip(";"))
    ids = {(p["team"], k1(p["name"])): p["id"] for p in D["players"]}
    confirmed = {ids[(a["team"], k1(a["player"]))]: a["why"] for a in out["open"]
                 if a["severity"] == "high" and a["type"] in ("ROLE_AT_RISK", "PRICED_BUT_OUT") and (a["team"], k1(a["player"])) in ids}
    (CONSOLE_DATA.parent / "freshness-update.js").write_text(JS.replace("__PAYLOAD__", json.dumps(confirmed)), encoding="utf8")
    out["confirmed_holds_in_console"] = len(confirmed)
    (HERE / "output").mkdir(exist_ok=True)
    json.dump(out, open(HERE / "output/freshness.json", "w"), indent=1)
    print(f"snapshot built {out['snapshot_built']}; injuries as of {out['snapshot_injuries_as_of']}; reports posted for {out['teams_with_report_posted']}")
    for a in out["alerts"]:
        if a["type"] in ("REPORT_PENDING", "TEAM_NOT_PRICED"):
            continue
        print(f"[{a['severity']:5}] {a['type']:14} {a['team']:3} {a['player']:22} {a['pos']:2} {'RESOLVED' if a.get('resolved') else 'OPEN':8} {a['why']}")
    print("hold games:", out["hold_games"])
    print(len(out["hold_players"]), "players on hold;", len(out["open"]), "open alerts;", sum(a["type"] == "REPORT_PENDING" for a in out["alerts"]), "teams awaiting a report")


if __name__ == "__main__":
    main()
