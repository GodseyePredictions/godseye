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
from nhl.slate import LEDGER, OUT

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
    legs = [grade_leg(l, a) for l in t["legs"]]
    live = [l for l in legs if l["result"] != "void"]
    result = "void" if not live else ("won" if all(l["result"] == "won" for l in live) else "lost")
    return {**t, "legs": legs, "graded": True, "result": result, "legs_won": sum(l["result"] == "won" for l in live),
            "legs_counted": len(live), "final": f"{a['away']} {a['away_goals']}, {a['home']} {a['home_goals']} ({a['decided']})",
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
        gid = t["game_id"]
        if gid not in cache:
            cache[gid] = actuals(con, gid)
        if cache[gid] is None:
            waiting.append(t["id"])
            continue
        ledger["tickets"][i] = grade_ticket(t, cache[gid])
        graded.append(ledger["tickets"][i])
    LEDGER.write_text(json.dumps(ledger, indent=1, default=str))
    report_card(ledger)
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
