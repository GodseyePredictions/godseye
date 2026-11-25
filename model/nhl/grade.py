"""Nightly grading and the weekly report card.

Every ticket in the ledger whose game is final is graded from the engine's own per-game tables (the NHL's
play-by-play): shots, points, assists, goals, hits and blocks per skater, saves per goalie (overtime
included, shootout attempts not), and the final score for game lines. A leg on a player who did not play
is void and the ticket is graded on its other legs. Results are logged, not posted on the site.
"""
import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from nhl import store
from nhl.slate import CASHED, LEDGER, OUT

REPORT = OUT / "nhl_report_card.json"
SKATER = {"sog": "SUM(sog)", "goals": "SUM(g)", "ast": "SUM(a1 + a2)", "pts": "SUM(g + a1 + a2)", "hits": "SUM(hits)", "blk": "SUM(blocks)"}


def actuals(con, game_id: int) -> dict | None:
    g = store.read(con, "SELECT * FROM games WHERE game_id=?", [game_id])
    if g.empty:
        return None
    g = g.iloc[0]
    sk = store.read(con, f"SELECT player_id, {', '.join(f'{v} {k}' for k, v in SKATER.items())} FROM player_game_strength "
                         f"WHERE game_id=? GROUP BY player_id", [game_id]).set_index("player_id")
    gk = store.read(con, "SELECT player_id, saves FROM goalie_game WHERE game_id=?", [game_id]).set_index("player_id")
    return {"home": g.home, "away": g.away, "home_goals": int(g.home_goals), "away_goals": int(g.away_goals), "decided": g.decided,
            "reg_home": int(g.h1 + g.h2 + g.h3), "reg_away": int(g.a1 + g.a2 + g.a3), "skaters": sk, "goalies": gk}


def grade_leg(leg: dict, a: dict) -> dict:
    """Adds `actual` and `result` (won, lost or void) to a leg."""
    m = leg["market"]
    out = dict(leg)
    if m in SKATER or m == "saves":
        table = a["goalies"] if m == "saves" else a["skaters"]
        if leg["player_id"] not in table.index:
            return {**out, "actual": None, "result": "void"}
        v = int(table.at[leg["player_id"], "saves" if m == "saves" else m])
        return {**out, "actual": v, "result": "won" if v >= leg["rung"] else "lost"}
    margin = a["home_goals"] - a["away_goals"]
    total = a["home_goals"] + a["away_goals"]
    side = leg["side"]
    if m == "ml":
        won, actual = (margin > 0) == (side == a["home"]), f"{a['away']} {a['away_goals']}, {a['home']} {a['home_goals']}"
    elif m == "ml3":
        reg = a["reg_home"] - a["reg_away"]
        won = reg == 0 if side == "draw" else ((reg > 0) if side == a["home"] else (reg < 0))
        actual = f"regulation {a['reg_away']}-{a['reg_home']}"
    elif m == "spread":
        won, actual = ((margin if side == a["home"] else -margin) + leg["line"]) > 0, f"margin {margin:+d} for {a['home']}"
    else:
        if total == leg["line"]:
            return {**out, "actual": total, "result": "void"}
        won, actual = (total > leg["line"]) == (side == "over"), total
    return {**out, "actual": actual, "result": "won" if won else "lost"}


def grade_ticket(t: dict, a: dict) -> dict:
    """`a`: one game's actuals, or {game_id: actuals} for a multi-game slip (each leg names its game)."""
    multi = "home" not in a
    legs = [grade_leg(l, a[l["game_id"]] if multi else a) for l in t["legs"]]
    live = [l for l in legs if l["result"] != "void"]
    result = "void" if not live else ("won" if all(l["result"] == "won" for l in live) else "lost")
    return {**t, "legs": legs, "graded": True, "result": result, "legs_won": sum(l["result"] == "won" for l in live),
            "legs_counted": len(live),
            "final": "; ".join(f"{x['away']} {x['away_goals']}, {x['home']} {x['home_goals']} ({x['decided']})" for x in (a.values() if multi else [a])),
            "graded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def run(con) -> dict:
    """Grade every ungraded ticket whose game is in the store. Returns what was graded and what is still waiting."""
    if not LEDGER.exists():
        return {"graded": [], "waiting": []}
    ledger = json.loads(LEDGER.read_text())
    graded, waiting, cache = [], [], {}
    for i, t in enumerate(ledger["tickets"]):
        if t.get("graded"):
            continue
        ids = t.get("game_ids") or [t["game_id"]]
        for gid in ids:
            if gid not in cache:
                cache[gid] = actuals(con, gid)
        if any(cache[gid] is None for gid in ids):
            waiting.append(t["id"])
            continue
        ledger["tickets"][i] = grade_ticket(t, {gid: cache[gid] for gid in ids} if t.get("game_ids") else cache[ids[0]])
        graded.append(ledger["tickets"][i])
    LEDGER.write_text(json.dumps(ledger, indent=1, default=str))
    report_card(ledger)
    cashed(ledger)
    return {"graded": graded, "waiting": waiting}


def report_card(ledger: dict, today: date | None = None) -> dict:
    """Per market: legs, hit rate against the average chance the model gave them, over the last 7 days and overall."""
    today = today or datetime.now(timezone.utc).date()
    rows = []
    for t in ledger["tickets"]:
        if not t.get("graded"):
            continue
        d = date.fromisoformat(t["id"][:10])
        for l in t["legs"]:
            if l["result"] != "void":
                rows.append({"date": d, "market": l["market"], "prob": l["prob"], "won": int(l["result"] == "won"), "ticket": t["kind"]})
    legs = pd.DataFrame(rows)

    def card(d):
        if d.empty:
            return []
        g = d.groupby("market").agg(legs=("won", "size"), won=("won", "sum"), hit_rate=("won", "mean"), model_avg=("prob", "mean"))
        return [{"market": m, "legs": int(r.legs), "won": int(r.won), "hit_rate": round(float(r.hit_rate), 4),
                 "model_avg": round(float(r.model_avg), 4)} for m, r in g.iterrows()]

    tickets = [t for t in ledger["tickets"] if t.get("graded")]
    by_kind = {}
    for t in tickets:
        k = by_kind.setdefault(t["kind"], {"tickets": 0, "won": 0, "void": 0, "model_avg": 0.0})
        k["tickets"] += 1; k["won"] += t["result"] == "won"; k["void"] += t["result"] == "void"; k["model_avg"] += t["chance"]
    for k in by_kind.values():
        k["model_avg"] = round(k["model_avg"] / k["tickets"], 4)
    out = {"as_of": today.isoformat(), "week": card(legs[legs.date > today - timedelta(days=7)]) if len(legs) else [],
           "all_time": card(legs), "tickets": by_kind,
           "note": "private: results are reported to the owner, not posted on the site"}
    REPORT.write_text(json.dumps(out, indent=1))
    return out


def cashed(ledger: dict) -> dict:
    """The winning slips, for the site's "Cashed slips" tab (owner, 24 November 2026). Winning slips only: the page
    says so, shows no count of slips issued or lost, and the full record stays in the private report card."""
    slips = []
    for t in ledger["tickets"]:
        if t.get("graded") and t.get("result") == "won" and not t.get("made_after_start"):
            slips.append({"id": t["id"], "date": t["id"][:10], "title": t["title"], "game": t.get("game") or " + ".join(t.get("games", [])),
                          "final": t["final"], "made_at": t["made_at"], "chance": t["chance"], "fair_price": t["fair_price"],
                          "rungs_verified": t.get("rungs_verified", False), "priced": t.get("priced", False),
                          "legs": [{"label": l["label"], "prob": l["prob"], "actual": l["actual"], "price": l.get("price")} for l in t["legs"]
                                   if l["result"] == "won"]})
    out = {"slips": sorted(slips, key=lambda s: s["id"], reverse=True),
           "note": "winning slips only; losing slips are not shown here"}
    CASHED.write_text(json.dumps(out, indent=1, default=str))
    return out
