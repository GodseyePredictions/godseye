"""Rebuild the console's per-game SGPs and props tickets after players are withdrawn.

Overrides and confirmed roster alerts withdraw every precomputed ticket that used an affected
player. Withdrawing alone would leave that game empty, so this step rebuilds the same three
things for each affected game from the players who are still eligible:

  Game SGPs         one best leg per slot (QB, RB rush, WR, TE, RB receiving)
  Script SGPs       the 4, 6 and 8-leg ladder and the two touchdown hybrids
  Props SGPs        the floor and aggressive tickets shown under Algorithm picks

Legs come from the console's own prop ladders and are priced with its own correlations.
Players who are singles only, estimated by an override, or on hold are never used.

Usage: python3 rebuild_console.py     writes ../public/console/rebuild-update.js
Run after apply_overrides.py and freshness.py.
"""
import json
from pathlib import Path

import numpy as np

from apply_overrides import apply, plan
from freshness import audit, k1
from game_markets import joint_probability

HERE = Path(__file__).parent
CONSOLE = HERE.parent / "public" / "console"
MK = {"carries": "carries", "rush_yds": "rush yds", "rec": "receptions", "rec_yds": "rec yds",
      "pass_att": "pass att", "pass_yds": "pass yds", "pass_td": "pass TDs"}
SLOTS = [("QB", "QB", ["pass_yds", "pass_td"]), ("RB rush", "RB", ["rush_yds"]), ("WR", "WR", ["rec", "rec_yds"]),
         ("TE", "TE", ["rec", "rec_yds"]), ("RB receiving", "RB", ["rec", "rec_yds"])]


def main():
    raw = json.loads((CONSOLE / "data.js").read_text(encoding="utf8").strip()[len("const D = "):].rstrip(";"))
    stale = set(plan(raw)["stale_ids"])                      # players changed by an override
    D = apply(json.loads(json.dumps(raw)))
    fresh = audit()
    P = {p["id"]: p for p in D["players"]}
    ids = {(p["team"], k1(p["name"])): p["id"] for p in D["players"]}
    confirmed = {ids[(a["team"], k1(a["player"]))] for a in fresh["open"]
                 if a["severity"] == "high" and a["type"] in ("ROLE_AT_RISK", "PRICED_BUT_OUT") and (a["team"], k1(a["player"])) in ids}
    held = {i for (t, n), i in ids.items() if f"{t}|{n}" in set(fresh["hold_players"])}
    withdrawn = stale | confirmed
    excluded = withdrawn | held
    games = sorted({P[i]["game"] for i in withdrawn if i in P})
    atd_corr, leg_corr = D["corr"]["atd"], D["corr"]["legs"]

    def rho(a, b):
        pa, pb = P[a["id"]], P[b["id"]]
        same = a["id"] == b["id"]
        rel = "SELF" if same else ("TM" if pa["team"] == pb["team"] else "OPP")
        if a["mk"] == "atd" and b["mk"] == "atd":
            if rel == "OPP":
                return atd_corr.get("OPP", 0.03)
            return atd_corr.get("TM:" + "-".join(sorted([pa["pos"], pb["pos"]])), atd_corr.get("TM:default", -0.04))
        if same and a["mk"] == b["mk"]:
            return 0.95
        key = rel + "|" + "|".join(sorted([f"{a['mk']}@{pa['pos']}", f"{b['mk']}@{pb['pos']}"]))
        if key in leg_corr:
            return leg_corr[key]
        return leg_corr.get("_rel", {}).get("SELF", 0.3) if same else 0.0

    def joint(legs):
        if len(legs) == 1:
            return legs[0]["p"]
        R = [[1.0 if i == j else rho(a, b) for j, b in enumerate(legs)] for i, a in enumerate(legs)]
        return joint_probability([l["p"] for l in legs], R, n=200_000)

    def rung(pid, mk, lo, hi, target):
        m = D["props"].get(pid, {}).get(mk)
        if not m:
            return None
        band = [(abs(p - target), i) for i, p in enumerate(m["p"]) if lo <= p <= hi]
        if not band:
            return None
        i = min(band)[1]
        return {"id": pid, "mk": mk, "k": int(m["k"][i]), "p": float(m["p"][i]),
                "hits": int(m["hits"][i]) if m.get("hits") else None, "n": m.get("n")}

    payload = {"sgp": {}, "script": {}, "props": {}, "games": games}
    for gid in games:
        roster = [p for p in D["players"] if p["game"] == gid and not p.get("singles") and p["id"] not in excluded]
        left_out = sorted({P[i]["name"] for i in excluded if i in P and P[i]["game"] == gid})
        marker = f"<b>Rebuilt after roster changes:</b> built without {', '.join(left_out)}, whose numbers are estimates or on hold."

        def why(leg):
            p = P[leg["id"]]
            parts = p.get("parts") or {}
            line = (f"<b>This line:</b> {leg['k']}+ {MK[leg['mk']]}: cleared in {leg['hits']} of {leg['n']} games this season; model {leg['p']:.0%}."
                    if leg.get("n") else f"<b>This line:</b> {leg['k']}+ {MK[leg['mk']]}; model {leg['p']:.0%}.")
            return [marker, line] + [parts[k] for k in ("outlook", "matchup", "scheme", "game") if parts.get(k)]

        floor = {}   # best floor-band line per player and market
        for p in roster:
            for mk in D["props"].get(p["id"], {}):
                r = rung(p["id"], mk, 0.70, 0.88, 0.78)
                if r:
                    floor[(p["id"], mk)] = r

        # --- Game SGP: one best leg per slot, distinct players
        used, legs = set(), []
        for slot, pos, mks in SLOTS:
            cands = sorted([r for (pid, mk), r in floor.items() if P[pid]["pos"] == pos and mk in mks and pid not in used], key=lambda r: -r["p"])
            if not cands:
                continue
            best = cands[0]
            used.add(best["id"])
            alts = [{"id": c["id"], "mk": c["mk"], "k": c["k"], "p": c["p"]} for c in cands[1:] if c["id"] != best["id"]][:2]
            legs.append({"slot": slot, **best, "alts": alts, "why": why(best)})
        if len(legs) < len(SLOTS):   # fill empty slots with the next best legs from other players
            spare = sorted([r for (pid, mk), r in floor.items() if pid not in used], key=lambda r: -r["p"])
            for r in spare:
                if len(legs) >= len(SLOTS):
                    break
                if r["id"] in used:
                    continue
                used.add(r["id"])
                legs.append({"slot": f"{P[r['id']]['pos']} (fill)", **r, "alts": [], "why": why(r)})
        if len(legs) >= 2:
            payload["sgp"][gid] = {"game": gid, "p": round(joint(legs), 4), "p_indep": round(float(np.prod([l["p"] for l in legs])), 5),
                                   "legs": legs, "rebuilt": True}

        # --- Script ladder: legs by probability, at most two per player
        ranked, per = [], {}
        for r in sorted(floor.values(), key=lambda r: -r["p"]):
            if per.get(r["id"], 0) < 2:
                ranked.append({**r, "fit": 0.0, "why": []})
                per[r["id"]] = per.get(r["id"], 0) + 1
        ladder = [{"n": n, "p": round(joint(ranked[:n]), 5), "p_indep": round(float(np.prod([l["p"] for l in ranked[:n]])), 5), "legs": ranked[:n]}
                  for n in (4, 6, 8) if len(ranked) >= n]
        tds, seen = [], set()
        for p in sorted(roster, key=lambda p: -p["p"]):   # one scorer per team, the console's own rule
            if p["team"] not in seen and p["pos"] in ("RB", "WR", "TE"):
                tds.append({"id": p["id"], "mk": "atd", "k": None, "p": float(p["p"]), "fit": 0.0, "why": [], "hits": None, "n": None})
                seen.add(p["team"])
        hybrids = {}
        for name, n_td in (("hybrid1", 1), ("hybrid2", 2)):
            if len(tds) >= n_td and len(ranked) >= 4:
                hl = tds[:n_td] + ranked[:4]
                hybrids[name] = {"p": round(joint(hl), 5), "legs": hl}
        payload["script"][gid] = {"ladder": ladder, "hybrid1": hybrids.get("hybrid1"), "hybrid2": hybrids.get("hybrid2"),
                                  "note": f"Rebuilt after roster changes, without {', '.join(left_out)}."}

        # --- Props tickets under Algorithm picks: distinct players
        def distinct(rows, n):
            out, got = [], set()
            for r in rows:
                if r["id"] not in got:
                    out.append({"id": r["id"], "mk": r["mk"], "k": r["k"], "p": r["p"]})
                    got.add(r["id"])
                if len(out) == n:
                    break
            return out if len(out) == n else None

        by_p = sorted(floor.values(), key=lambda r: -r["p"])
        bold = sorted([r for p in roster for mk in D["props"].get(p["id"], {}) for r in [rung(p["id"], mk, 0.50, 0.69, 0.60)] if r], key=lambda r: -r["p"])
        tickets = []
        for name, rows, n in (("floor4", by_p, 4), ("floor6", by_p, 6), ("aggressive4", bold, 4)):
            legs_ = distinct(rows, n)
            if legs_:
                tickets.append({"ticket": f"{gid}|{name}", "p": round(joint(legs_), 4), "legs": [{k: l[k] for k in ("id", "mk", "k")} for l in legs_]})
        payload["props"][gid] = tickets
        print(gid, "rebuilt without", left_out)
        if gid in payload["sgp"]:
            print("  SGP:", [(P[l["id"]]["name"], l["k"], l["mk"], round(l["p"], 2)) for l in payload["sgp"][gid]["legs"]], payload["sgp"][gid]["p"])
        print("  ladder:", [(x["n"], x["p"]) for x in ladder], "| hybrids:", {k: v["p"] for k, v in hybrids.items()}, "| props tickets:", [(t["ticket"].split("|")[1], t["p"]) for t in tickets])

    js = ("/* Generated by model/rebuild_console.py. Rebuilds per-game SGPs and props tickets after players are withdrawn. */\n"
          f"(function(){{var U={json.dumps(payload)};var order={{}};D.games.forEach(function(g,i){{order[g.id]=i}});\n"
          "U.games.forEach(function(gid){\n"
          " D.algo.sgp=(D.algo.sgp||[]).filter(function(t){return t.game!==gid});if(U.sgp[gid])D.algo.sgp.push(U.sgp[gid]);\n"
          " D.algo.props=(D.algo.props||[]).filter(function(t){return String(t.ticket).indexOf(gid+'|')!==0}).concat(U.props[gid]||[]);\n"
          " var s=(D.script_sgp||[]).find(function(t){return t.game===gid});var r=U.script[gid];\n"
          " if(s&&r){s.ladder=r.ladder;s.hybrid1=r.hybrid1;s.hybrid2=r.hybrid2;s.notes=(s.notes||[]).concat([r.note])}});\n"
          "D.algo.sgp.sort(function(a,b){return order[a.game]-order[b.game]});\n"
          "D.script_sgp=(D.script_sgp||[]).filter(function(t){return t.ladder&&t.ladder.length});})();\n")
    (CONSOLE / "rebuild-update.js").write_text(js, encoding="utf8")


if __name__ == "__main__":
    main()
