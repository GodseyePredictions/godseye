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


locks = []
for t in sorted(D["algo"]["sgp"], key=lambda t: -t["p"])[:3]:
    if G[t["game"]].get("started"):
        continue
    locks.append({"kind": "Same-game parlay", **game_label(t["game"]), "p": round(t["p"], 3), "tab": "sgp",
                  "legs": [{"text": f"{P[l['id']]['name']} {l['k']}+ {MK.get(l['mk'], l['mk'])}", "team": P[l["id"]]["team"],
                            "p": round(l["p"], 3), "record": f"cleared in {l['hits']} of {l['n']} games" if l.get("n") else ""}
                           for l in t["legs"]]})
pairs = [c for c in D["algo"]["atd_combos"] if c["n"] == 2 and not G[c["game"]].get("started")]
if pairs:
    c = max(pairs, key=lambda c: c["p"])
    locks.append({"kind": "Anytime TD double", **game_label(c["game"]), "p": round(c["p"], 3), "tab": "picks",
                  "legs": [atd_leg(i) for i in c["legs"]]})
four = next((t for t in D["algo"]["atd"] if t["n"] == 4), None)
if four:
    locks.append({"kind": "Anytime TD 4-leg", "matchup": "Across the slate", "when": f"Week {D['meta']['week']}",
                  "p": round(four["p"], 3), "tab": "picks", "legs": [atd_leg(i) for i in four["legs"]]})

out = {"season": D["meta"]["season"], "week": D["meta"]["week"], "built": D["meta"]["built"], "record": D["meta"]["record"],
       "locks": locks}
(ROOT / "model/output/locks.json").write_text(json.dumps(out, indent=1))
print(f"week {out['week']}: {len(locks)} tickets")
for l in locks:
    print(f"  {l['kind']:<20} {l['matchup']:<18} {l['p']:.0%}  " + "; ".join(x["text"] for x in l["legs"]))
