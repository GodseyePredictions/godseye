"""The four gates. Any fail removes the leg.

1. Starting goalie confirmed for both teams: without it, no leg on that game's totals, saves or scoring props.
2. Game-day line combinations and power-play units in hand for the player's team.
3. Injury and scratch check passed for the player and his key line-mates.
4. The rung exists on the book's ladder. With no ladder in hand the engine can run in paper mode
   (gates.require_book_rung false): the leg is kept on the spec's standard milestone rungs and marked
   "rung not verified", so a slip can be tested and graded but is not a bet the book is known to offer.
"""
from datetime import datetime, timedelta

GOALIE_DEPENDENT = {"total", "saves", "pts", "ast", "goals", "atg", "ml", "ml3", "spread"}
SCORING_PROPS = {"saves", "pts", "ast", "goals", "atg", "total"}


def _t(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def game_gates(game: dict, goalie_rows: list, lines_rows: list, cfg) -> dict:
    """goalie_rows / lines_rows: the latest Daily Faceoff rows for the two teams."""
    c = cfg["gates"]
    start = _t(game["start_utc"])
    out = {"goalies": {}, "lines": {}, "notes": []}
    for team in (game["home"], game["away"]):
        g = next((r for r in goalie_rows if r["team"] == team and r["date_et"] == game["date_et"]), None)
        ok = bool(g and g["status"] in c["goalie_statuses"] and g.get("goalie"))
        out["goalies"][team] = {"ok": ok, "goalie": g and g.get("goalie"), "player_id": g and g.get("player_id"),
                                "status": g["status"] if g else "not listed"}
        if not ok:
            out["notes"].append(f"{team} starting goalie is {g['status'].lower() if g else 'not listed'}: no totals, saves or scoring props")
        L = [r for r in lines_rows if r["team"] == team]
        fresh = bool(L) and L[0].get("source_time") and _t(L[0]["source_time"]) >= start - timedelta(hours=c["lines_max_age_hours"])
        out["lines"][team] = {"ok": bool(fresh), "updated": L[0].get("source_time") if L else None}
        if not fresh:
            out["notes"].append(f"{team} lines are {'stale' if L else 'missing'}: no legs on its skaters")
    out["goalies_ok"] = all(v["ok"] for v in out["goalies"].values())
    return out


def lineup_flags(lines_rows: list) -> dict:
    """player_id -> why he fails the injury check (injured reserve, game-time decision, or a line-mate who is)."""
    bad = {}
    by_slot = {}
    for r in lines_rows:
        if r.get("player_id") is None:
            continue
        p = int(r["player_id"])
        if r["unit"] == "ir" or r.get("injury"):
            bad[p] = "injured reserve" if r["unit"] == "ir" else str(r["injury"])
        elif r.get("gtd"):
            bad[p] = "game-time decision"
        if r["category"] == "ev" and r["unit"] != "g":
            by_slot.setdefault((r["team"], r["unit"]), []).append(p)
    for mates in by_slot.values():
        hurt = [p for p in mates if p in bad]
        for p in mates:
            if hurt and p not in bad:
                bad[p] = "line-mate is a game-time decision"
    return bad


def leg_passes(leg: dict, gates: dict, flags: dict, cfg) -> tuple[bool, str]:
    """(passes, reason it does not). `leg`: market, team, player_id, rung_verified."""
    if leg["market"] in SCORING_PROPS and not gates["goalies_ok"]:
        return False, "starting goalie not confirmed"
    if leg.get("player_id") is not None and leg["market"] != "saves":
        if not gates["lines"][leg["team"]]["ok"]:
            return False, "lines not confirmed"
        if leg["player_id"] in flags:
            return False, flags[leg["player_id"]]
    if cfg["gates"]["require_book_rung"] and not leg.get("rung_verified"):
        return False, "rung not on the book's ladder"
    return True, ""
