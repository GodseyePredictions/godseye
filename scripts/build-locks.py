"""Pick this week's showcase tickets for the landing page from the NFL algorithm's own output.

Usage: python3 -I scripts/build-locks.py        (re-run after importing a new console export)
Reads public/console/data.js, writes model/output/locks.json.

Nothing is hand-picked: the page shows the algorithm's three highest-probability game SGPs,
its highest-probability anytime-touchdown pair and its 4-leg anytime-touchdown ticket,
each with the model's own chance of cashing, plus the season record of the algorithm's tickets.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MK = {"atd": "Anytime TD", "carries": "carries", "rush_yds": "rush yds", "rec": "receptions", "rec_yds": "rec yds",
      "pass_att": "pass attempts", "pass_yds": "pass yds", "pass_td": "pass TDs"}

src = (ROOT / "public/console/data.js").read_text(encoding="utf8")
D = json.loads(src[src.index("{"):src.rindex("}") + 1])
P = {p["id"]: p for p in D["players"]}
G = {g["id"]: g for g in D["games"]}


def game_label(gid):
    g = G[gid]
    return {"matchup": f"{g['away']} @ {g['home']}", "when": f"{g['weekday']} {g['kick']}"}


def atd_leg(pid):
    p = P[pid]
    return {"text": f"{p['name']} Anytime TD", "team": p["team"], "p": round(p["p"], 3)}


# The roster audit decides who may be shown. A ticket is skipped if it uses a player with an open
# roster alert or one changed by a logged read, or if its game is on hold.
import re

_key = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", (n or "").lower()))
excluded, hold_games = set(), set()
fresh_path, over_path = ROOT / "model/output/freshness.json", ROOT / "model/overrides.json"
if fresh_path.exists():
    F = json.loads(fresh_path.read_text())
    held = set(F.get("hold_players", []))
    excluded |= {p["id"] for p in D["players"] if f"{p['team']}|{_key(p['name'])}" in held}
    hold_games = set(F.get("hold_games", []))
if over_path.exists():
    excluded |= {p["id"] for o in json.loads(over_path.read_text())["overrides"] for p in o["players"]}
leg_ids = lambda t: [l if isinstance(l, str) else l["id"] for l in t["legs"]]
clear = lambda t: not (set(leg_ids(t)) & excluded) and t.get("game") not in hold_games

locks = []
for t in sorted([t for t in D["algo"]["sgp"] if clear(t)], key=lambda t: -t["p"])[:3]:
    if G[t["game"]].get("started"):
        continue
    locks.append({"kind": "Same-game parlay", **game_label(t["game"]), "p": round(t["p"], 3), "tab": "sgp",
                  "legs": [{"text": f"{P[l['id']]['name']} {l['k']}+ {MK.get(l['mk'], l['mk'])}", "team": P[l["id"]]["team"],
                            "p": round(l["p"], 3), "record": f"cleared in {l['hits']} of {l['n']} games" if l.get("n") else ""}
                           for l in t["legs"]]})
pairs = [c for c in D["algo"]["atd_combos"] if c["n"] == 2 and not G[c["game"]].get("started") and clear(c)]
if pairs:
    c = max(pairs, key=lambda c: c["p"])
    locks.append({"kind": "Anytime TD double", **game_label(c["game"]), "p": round(c["p"], 3), "tab": "picks",
                  "legs": [atd_leg(i) for i in c["legs"]]})
four = next((t for t in D["algo"]["atd"] if t["n"] == 4 and clear(t)), None)
if four:
    locks.append({"kind": "Anytime TD 4-leg", "matchup": "Across the slate", "when": f"Week {D['meta']['week']}",
                  "p": round(four["p"], 3), "tab": "picks", "legs": [atd_leg(i) for i in four["legs"]]})

# ---- featured players: the algorithm's own numbers for four names on the landing page
FEATURED = ["Patrick Mahomes", "Josh Allen", "Ja'Marr Chase", "Kenneth Walker III"]
UNITS = {"pass_yds": "pass yds", "pass_td": "pass TD", "rec": "receptions", "rec_yds": "rec yds", "rush_yds": "rush yds", "carries": "carries"}
SHOW = {"QB": ["pass_td", "pass_yds", "rush_yds"], "WR": ["rec", "rec_yds"], "TE": ["rec", "rec_yds"], "RB": ["rush_yds", "carries", "rec"]}


def floor_rung(pid, mk, floor=0.70):
    """The highest rung of a market the model still gives 70% or better."""
    pr = D["props"].get(pid, {}).get(mk)
    if not pr:
        return None
    ok = [(k, p, h) for k, p, h in zip(pr["k"], pr["p"], pr["hits"]) if p >= floor]
    if not ok:
        return None
    k, p, h = ok[-1]
    return {"text": f"{k}+ {UNITS[mk]}", "p": round(p, 3), "record": f"{h} of {pr['n']} games"}


def slug(name):
    return "".join(c for c in name.lower().replace(" ", "-") if c.isalnum() or c == "-")


stars = []
for name in FEATURED:
    p = next((x for x in D["players"] if x["name"] == name), None)
    if not p:
        stars.append({"name": name, "slug": slug(name), "on_slate": False})
        continue
    g = G[p["game"]]
    lines = [x for x in (floor_rung(p["id"], mk) for mk in SHOW.get(p["pos"], [])) if x]
    stars.append({"name": name, "slug": slug(name), "on_slate": True, "team": p["team"], "pos": p["pos"],
                  "game": f"{g['away']} @ {g['home']}", "when": f"{g['weekday']} {g['kick']}", "atd": round(p["p"], 3),
                  "singles_only": bool(p.get("singles")), "lines": lines})
photos = sorted(f.stem for f in (ROOT / "public/players").glob("*.jpg")) if (ROOT / "public/players").exists() else []

out = {"stars": stars, "photos": photos, "season": D["meta"]["season"], "week": D["meta"]["week"], "built": D["meta"]["built"], "record": D["meta"]["record"],
       "locks": locks}
(ROOT / "model/output/locks.json").write_text(json.dumps(out, indent=1))
print(f"week {out['week']}: {len(locks)} tickets ({len(excluded)} players and {len(hold_games)} games excluded by the roster audit)")
for l in locks:
    print(f"  {l['kind']:<20} {l['matchup']:<18} {l['p']:.0%}  " + "; ".join(x["text"] for x in l["legs"]))
