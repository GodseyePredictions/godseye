"""Ticket builder: bet365 milestone rungs, the spec's ticket rules, one set of tickets per game.

Per game: a 4-leg and a 6-leg props SGP (floor rungs at 70%+, best legs from either side), an anytime goal
scorer ticket on its own, and a game-line closer when the sim's edge over the listed price clears the bar.
Legs are searched with the shared helper's rules plus the NHL ones: at most two points legs from one line,
no saves leg on a goalie when the blowout flag is up against him, no late-ice-time props on the favourite's
top line in a flagged blowout, and at most one leg under 65%.
"""
from itertools import combinations

import numpy as np

from common.odds_math import expected_value, fair_american, kelly_stake
from common.tickets import allowed, joint, score
from nhl import correlation, gates as gates_mod
from nhl.sim import game_sim

LABEL = {"sog": "shots on goal", "pts": "points", "ast": "assists", "hits": "hits", "blk": "blocked shots", "saves": "saves", "goals": "goals"}
PROP_MARKETS = ("sog", "pts", "ast", "hits", "blk")
LATE_TOI = {"sog", "pts", "ast", "goals"}


def ladders(odds_rows: list, cfg) -> dict:
    """{(market, player_id): [(rung, price)]} from the book's rows, over side only (a milestone is one-sided)."""
    out = {}
    for r in odds_rows:
        if r.get("player_id") is not None and r["side"] in ("over", "yes"):
            market = "goals" if r["market"] == "atg" else r["market"]       # anytime scorer is "1+ goals"
            out.setdefault((market, int(r["player_id"])), []).append((int(r["line"] + 0.5), r["price"]))
    return out


def build_legs(PS, S, gates: dict, flags: dict, odds_rows: list, summary: dict, cfg) -> tuple[list, list]:
    """Every candidate leg that passes the gates, and the ones removed with the reason."""
    c = cfg["tickets"]
    book = ladders(odds_rows, cfg)
    legs, removed = [], []
    P = PS.players
    fav = summary["favourite"]
    dog = S.away if fav == S.home else S.home

    def add(market, team, pid, name, counts, extra):
        rungs = book.get((market, pid))
        verified = rungs is not None
        if not verified:
            rungs = [(1, None)] if market == "goals" else [(r, None) for r in c["paper_ladders"].get(market, [])]
        for rung, price in sorted(rungs):
            hits = counts >= rung
            leg = {"kind": "prop", "market": market, "team": team, "player_id": pid, "player": name, "rung": rung, "price": price,
                   "p": float(hits.mean()), "hits": hits, "active": None, "rung_verified": verified,
                   "label": f"{name} {rung}+ {LABEL[market]}", **extra}
            ok, why = gates_mod.leg_passes(leg, gates, flags, cfg)
            if ok and summary["blowout_flag"]:
                if market == "saves" and team == dog and c["saves_cap_blowout"]:
                    ok, why = False, "blowout guard: saves on the goalie facing the favourite"
                elif market in LATE_TOI and team == fav and extra.get("top_line"):
                    ok, why = False, "blowout guard: late ice time on the favourite's top line"
            (legs if ok else removed).append(leg if ok else {"label": leg["label"], "p": round(leg["p"], 4), "reason": why})

    for j, r in enumerate(P.itertuples()):
        for m in PROP_MARKETS + ("goals",):
            add(m, r.team, int(r.player_id), r.name, PS.data[m][:, j],
                {"line_slot": r.ev_slot, "top_line": bool(r.top_line), "script": f"shots:{r.team}" if m == "sog" else None})
    for team, g in PS.goalies.items():
        if g.get("player_id") is None:
            continue
        opp = S.away if team == S.home else S.home
        add("saves", team, int(g["player_id"]), g["name"], g["saves"], {"line_slot": None, "top_line": False, "script": f"shots:{opp}"})
    return legs, removed


def floor_rungs(legs: list, cfg) -> list:
    """For each player and market, the highest rung that still clears the floor: the floor rung."""
    c = cfg["tickets"]
    best = {}
    for l in legs:
        if l["market"] == "goals" or l["p"] < c.get("floor_prob_by_market", {}).get(l["market"], c["floor_prob"]):
            continue
        k = (l["market"], l["player_id"])
        if k not in best or l["rung"] > best[k]["rung"]:
            best[k] = l
    return list(best.values())


def nhl_allowed(combo, cfg) -> bool:
    c = cfg["tickets"]
    if sum(l["p"] < c["sub65_prob"] for l in combo) > c["max_sub65_legs"]:
        return False
    per_line = {}
    for l in combo:
        if l["market"] in ("pts", "ast") and l.get("line_slot"):
            k = (l["team"], l["line_slot"])
            per_line[k] = per_line.get(k, 0) + 1
    return not per_line or max(per_line.values()) <= c["max_legs_same_line_points"]


def best_sgp(pool: list, size: int, cfg) -> dict | None:
    """Highest expected value when every leg has a price; otherwise the highest joint chance."""
    c = cfg["tickets"]
    priced = all(l.get("price") is not None for l in pool) and bool(pool)
    rank = (lambda l: -(l["p"] * (1 + l["price"] / 100 if l["price"] > 0 else 1 + 100 / -l["price"]))) if priced else (lambda l: -l["p"])
    pool = sorted(pool, key=rank)[:c["sgp_candidate_pool"]]
    best, key = None, None
    for combo in combinations(pool, size):
        if not allowed(combo, c, False, size) or not nhl_allowed(combo, cfg):
            continue
        s = score(list(combo))
        if s["joint"] < c["ticket_min_joint"].get(size, 0.0):
            continue
        k = s["ev"] if priced and s["ev"] is not None else s["joint"]
        if key is None or k > key:
            best, key = {"legs": list(combo), **s}, k
    return best


def _leg_out(l: dict) -> dict:
    return {"label": l["label"], "market": l["market"], "team": l.get("team"), "player": l.get("player"), "player_id": l.get("player_id"),
            "rung": l.get("rung"), "side": l.get("side"), "line": l.get("line"), "prob": round(l["p"], 4), "price": l.get("price"),
            "fair_price": fair_american(l["p"]), "rung_verified": bool(l.get("rung_verified", True))}


def _ticket(kind, title, legs, cfg, extra=None) -> dict:
    j = joint(legs)
    prices = [l.get("price") for l in legs]
    return {"kind": kind, "title": title, "legs": [_leg_out(l) for l in legs], "chance": round(j, 4), "miss": round(1 - j, 4),
            "fair_price": fair_american(j), "lift": round(correlation.lift(legs), 3) if len(legs) > 1 else 1.0,
            "pairs": correlation.pair_table(legs) if 1 < len(legs) <= 6 else [],
            "priced": all(p is not None for p in prices), "rungs_verified": all(l.get("rung_verified", True) for l in legs), **(extra or {})}


def build(PS, S, gates: dict, flags: dict, odds_rows: list, summary: dict, game_lines: list, cfg) -> dict:
    """All of one game's tickets, plus what was removed and why."""
    c = cfg["tickets"]
    legs, removed = build_legs(PS, S, gates, flags, odds_rows, summary, cfg)
    pool = floor_rungs(legs, cfg)
    out = {"tickets": [], "removed": removed, "pool": [{k: v for k, v in _leg_out(l).items()} for l in sorted(pool, key=lambda l: -l["p"])]}
    for size in c["sizes"]:
        t = best_sgp(pool, size, cfg)
        if t:
            out["tickets"].append(_ticket(f"sgp{size}", f"{size}-leg props SGP", t["legs"], cfg))
        else:
            out.setdefault("notes", []).append(f"no {size}-leg props SGP: {len(pool)} floor rungs passed the gates, "
                                               f"or none reached the {c['ticket_min_joint'].get(size, 0):.0%} joint floor")
    scorers = sorted([l for l in legs if l["market"] == "goals" and l["rung"] == 1 and l["p"] >= c["atg_min_prob"]], key=lambda l: -l["p"])
    if not scorers:
        scorers = sorted([l for l in legs if l["market"] == "goals" and l["rung"] == 1], key=lambda l: -l["p"])
    priced = [l for l in scorers if l.get("price") is not None]
    if priced:
        scorers = sorted(priced, key=lambda l: -expected_value(l["p"], l["price"]))
    if scorers:
        pick = [{**l, "label": f"{l['player']} anytime goal scorer"} for l in scorers[:c["atg_legs"]]]
        out["tickets"].append(_ticket("atg", "Anytime goal scorer", pick, cfg))
    closers = [g for g in game_lines if g["edge"] >= c["closer_min_edge"] and g["market"] in c["closer_markets"]]
    if closers and gates["goalies_ok"]:
        g = closers[0]
        hits = game_sim.hits_for(S, g["market"], g["side"], g["line"])
        name = {"ml": f"{g['side']} moneyline", "spread": f"{g['side']} {g['line']:+g}", "total": f"{g['side'].title()} {g['line']:g}"}[g["market"]]
        leg = {"kind": "game", "market": g["market"], "side": g["side"], "line": g["line"], "price": g["price"], "p": float(hits.mean()),
               "hits": hits, "label": name, "rung_verified": True, "team": g["side"] if g["market"] != "total" else None}
        stake = min(kelly_stake(leg["p"], g["price"], c["kelly_fraction"]), c["kelly_cap"])
        out["tickets"].append(_ticket("closer", "Game-line closer", [leg], cfg,
                                      {"book": g["book"], "edge": g["edge"], "tier": g["tier"], "implied_prob": g["implied_prob"],
                                       "ev": round(expected_value(leg["p"], g["price"]), 4), "kelly_stake": round(stake, 4)}))
    elif closers:
        out.setdefault("notes", []).append("game-line closer withheld: starting goalie not confirmed")
    return out
