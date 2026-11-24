"""Live / final grading of shipped tickets from ESPN box scores (public site API)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
TEAM_FIX = {"LAR": "LA", "WSH": "WAS", "JAX": "JAX", "LV": "LV"}
MK_STAT = {"carries": "car", "rush_yds": "rush_yds", "rec": "rec", "rec_yds": "rec_yds", "pass_att": "att",
           "pass_yds": "pass_yds", "pass_td": "pass_td", "atd": "td"}
MK_LABEL = {"carries": "carries", "rush_yds": "rush yds", "rec": "rec", "rec_yds": "rec yds", "pass_att": "pass att",
            "pass_yds": "pass yds", "pass_td": "pass TDs", "atd": "ATD"}


def nkey(s):
    return re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()))


def _get(url):
    r = subprocess.run(["curl", "-sS", "-m", "30", url], capture_output=True, text=True)
    return json.loads(r.stdout)


def fetch_day(date_yyyymmdd: str):
    sb = _get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_yyyymmdd}")
    games, rows = {}, []
    for e in sb["events"]:
        c = e["competitions"][0]
        st = c["status"]["type"]
        tm = {t["homeAway"]: t["team"]["abbreviation"] for t in c["competitors"]}
        sc = {t["homeAway"]: t.get("score") for t in c["competitors"]}
        away, home = TEAM_FIX.get(tm["away"], tm["away"]), TEAM_FIX.get(tm["home"], tm["home"])
        gid = f"2026_09_{away}_{home}"
        games[gid] = {"espn": e["id"], "state": st["state"], "detail": st["shortDetail"], "final": st["completed"],
                      "score": f"{away} {sc['away']} – {home} {sc['home']}"}
        if st["state"] == "pre":
            continue
        s = _get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={e['id']}")
        stats = {}
        for t in s.get("boxscore", {}).get("players", []):
            team = TEAM_FIX.get(t["team"]["abbreviation"], t["team"]["abbreviation"])
            for cat in t["statistics"]:
                for a in cat["athletes"]:
                    k = (nkey(a["athlete"]["displayName"]), team)
                    d = stats.setdefault(k, {"name": a["athlete"]["displayName"], "team": team, "game_id": gid,
                                             "car": 0, "rush_yds": 0, "rec": 0, "rec_yds": 0, "att": 0, "pass_yds": 0,
                                             "pass_td": 0, "td": 0})
                    v = dict(zip(cat["keys"], a["stats"]))
                    if cat["name"] == "rushing":
                        d["car"] = int(v["rushingAttempts"]); d["rush_yds"] = int(v["rushingYards"])
                        d["td"] += int(v["rushingTouchdowns"])
                    elif cat["name"] == "receiving":
                        d["rec"] = int(v["receptions"]); d["rec_yds"] = int(v["receivingYards"])
                        d["td"] += int(v["receivingTouchdowns"])
                    elif cat["name"] == "passing":
                        d["att"] = int(v["completions/passingAttempts"].split("/")[1])
                        d["pass_yds"] = int(v["passingYards"]); d["pass_td"] = int(v["passingTouchdowns"])
        rows += list(stats.values())
    return games, pd.DataFrame(rows)


def grade_leg(leg, stats: pd.DataFrame, game):
    """leg: dict(name, team, mk, k). Returns (status, actual) with status in hit / pending / miss / n/a."""
    if game is None or game["state"] == "pre":
        return "pending", None
    row = stats[(stats.nk == nkey(leg["name"])) & (stats.team == leg["team"])]
    actual = int(row.iloc[0][MK_STAT[leg["mk"]]]) if len(row) else 0
    need = 1 if leg["mk"] == "atd" else leg["k"]
    if actual >= need:
        return "hit", actual
    return ("miss" if game["final"] else "pending"), actual


def load_shipped():
    """Every ticket shipped today, as lists of legs."""
    html = (OUT / "site" / "gods_eye.html").read_text()
    D = json.loads(re.search(r"const D = (\{.*?\});\nconst MK", html, re.S).group(1))
    P = {p["id"]: p for p in D["players"]}
    G = {g["id"]: g for g in D["games"]}

    def L(l):
        p = P[l["id"]]
        return {"name": p["name"], "team": p["team"], "game_id": p["game"], "mk": l["mk"], "k": l.get("k"),
                "p": l.get("p") or (p["p"] if l["mk"] == "atd" else None)}
    tickets = []
    for st, v in D["algo"]["atd_styles"].items():
        for t in v["tickets"]:
            tickets.append({"group": f"ATD {v['label']}", "name": f"{t['n']}-leg", "p": t["p"],
                            "legs": [L({"id": i, "mk": "atd"}) for i in t["legs"]]})
    for key, lab in (("props", "Cross-game props"), ("allpos", "Cross-game all-position")):
        for t in D["crossgame"].get(key, []):
            tickets.append({"group": lab, "name": f"{t['n']}-leg", "p": t["p"], "legs": [L(l) for l in t["legs"]]})
    for t in D["algo"]["sgp"]:
        g = G[t["game"]]
        tickets.append({"group": "Algo SGP", "name": f"{g['away']}@{g['home']}", "p": t["p"], "legs": [L(l) for l in t["legs"]]})
    for t in D["algo"]["props"]:
        if t["ticket"].startswith("combo"):
            tickets.append({"group": "Props combo", "name": t["ticket"], "p": t["p"], "legs": [L(l) for l in t["legs"]]})
    board = [L({"id": p["id"], "mk": "atd"}) for p in D["players"][:16]]
    return tickets, board, G


def report(date_yyyymmdd="20261108"):
    games, stats = fetch_day(date_yyyymmdd)
    stats["nk"] = stats.name.map(nkey) if len(stats) else []
    tickets, board, G = load_shipped()
    lines = [f"# Live grade — {date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:]}", "",
             "| Game | Status | Score |", "|---|---|---|"]
    for gid, g in games.items():
        lines.append(f"| {gid[8:].replace('_', ' @ ')} | {g['detail']} | {g['score']} |")

    def mark(s):
        return {"hit": "✓", "miss": "✗", "pending": "…"}[s]
    summary = []
    lines += ["", "## Tickets", ""]
    cur = None
    for t in tickets:
        res = [grade_leg(l, stats, games.get(l["game_id"])) for l in t["legs"]]
        sts = [r[0] for r in res]
        state = "DEAD" if "miss" in sts else ("CASHED" if all(s == "hit" for s in sts) else
                                              f"{sts.count('hit')}/{len(sts)} hit, {sts.count('pending')} open")
        if t["group"] != cur:
            lines.append(f"\n### {t['group']}"); cur = t["group"]
        legs_txt = " · ".join(
            f"{l['name']} {'ATD' if l['mk'] == 'atd' else str(l['k']) + '+ ' + MK_LABEL[l['mk']]} "
            f"{mark(r[0])}{'(' + str(r[1]) + ')' if r[1] is not None else ''}" for l, r in zip(t["legs"], res))
        lines.append(f"- **{t['name']}** ({t['p']:.1%}): **{state}** — {legs_txt}")
        summary.append({"group": t["group"], "ticket": t["name"], "state": state})
    lines += ["", "## ATD board top 16", ""]
    hits = [grade_leg(l, stats, games.get(l["game_id"])) for l in board]
    for l, r in zip(board, hits):
        lines.append(f"- {l['name']} ({l['team']}) {l['p']:.0%} {mark(r[0])}")
    n_hit = sum(r[0] == "hit" for r in hits); n_fin = sum(r[0] in ("hit", "miss") for r in hits)
    lines.append(f"\nBoard: {n_hit} scored so far; {n_fin} of 16 decided.")
    # leg-level calibration so far (decided legs only)
    legs_all = [(l, grade_leg(l, stats, games.get(l["game_id"]))) for t in tickets for l in t["legs"]]
    seen, dec = set(), []
    for l, r in legs_all:
        k = (l["name"], l["mk"], l["k"])
        if k in seen or r[0] == "pending" or l["p"] is None:
            continue
        seen.add(k); dec.append((l["p"], r[0] == "hit"))
    if dec:
        lines.append(f"\nDecided legs so far: {sum(h for _, h in dec)}/{len(dec)} = {sum(h for _, h in dec) / len(dec):.0%} "
                     f"hit vs {sum(p for p, _ in dec) / len(dec):.0%} expected.")
    txt = "\n".join(lines)
    (OUT / f"live_grade_{date_yyyymmdd}.md").write_text(txt)
    return txt, pd.DataFrame(summary), stats, games
