"""Ticket builder shared by sports: choose legs for a same-game parlay from simulated outcomes.

A leg carries the true/false result of every simulated game (`hits`). A ticket's chance is the share of
simulated games in which all its legs are true. Probabilities are never multiplied together.
Slip legs come out in the site's shape (src/lib/bets.ts: description, odds, game) so the tracker can take them.
"""
from itertools import combinations

import numpy as np

from common.odds_math import expected_value, fair_american, kelly_stake, to_decimal

COMBO_PARTS = {"pra": {"pts", "reb", "ast"}, "pr": {"pts", "reb"}, "pa": {"pts", "ast"}}


def joint(legs) -> float:
    """Share of simulated games in which every leg hits, among games where every leg's player plays
    (a leg on a player who does not play is void, so those games are not part of the bet)."""
    allhit = np.logical_and.reduce([l["hits"] for l in legs])
    acts = [l["active"] for l in legs if l.get("active") is not None]
    if acts:
        a = np.logical_and.reduce(acts)
        return float(allhit[a].mean()) if a.any() else 0.0
    return float(allhit.mean())


def product_price(legs) -> float | None:
    """Decimal price if the legs were unrelated. This is NOT the book's same-game price."""
    if any(l.get("price") is None for l in legs):
        return None
    d = 1.0
    for l in legs:
        d *= to_decimal(l["price"])
    return d


def allowed(combo, cfg, allow_combo_component=False) -> bool:
    per_player, scripts = {}, {}
    for l in combo:
        if l.get("player_id") is not None and l["kind"] == "prop":
            per_player.setdefault(l["player_id"], []).append(l["market"])
        if l.get("script"):
            scripts[l["script"]] = scripts.get(l["script"], 0) + 1
    if any(len(v) > cfg["max_legs_per_player"] for v in per_player.values()):
        return False
    if any(len(set(v)) < len(v) for v in per_player.values()):          # two rungs of one market for one player
        return False
    if scripts and max(scripts.values()) > cfg["max_legs_same_script"]:
        return False
    for mk in per_player.values():
        if len([m for m in mk if m in COMBO_PARTS]) > 1:               # two combo legs on one player are the same bet twice
            return False
        if not allow_combo_component and any(m in COMBO_PARTS and COMBO_PARTS[m] & set(mk) for m in mk):
            return False
    return True


def score(combo, sgp_price_decimal=None) -> dict:
    p = joint(combo)
    price = sgp_price_decimal or product_price(combo)
    return {"joint": p, "decimal": price, "ev": (p * price - 1) if price else None,
            "price_is_estimate": sgp_price_decimal is None}


def best_ticket(pool: list, size: int, cfg: dict, require_price: bool = True, extra: list | None = None) -> dict | None:
    """Best `size`-leg ticket from the pool: highest expected value among combinations whose joint chance
    clears the configured minimum. With no prices (backtest only) the highest joint chance wins."""
    pool = sorted(pool, key=lambda l: -(l["p"] * to_decimal(l["price"]) if l.get("price") else l["p"]))[:cfg["sgp_candidate_pool"]]
    floor = cfg["ticket_min_joint"].get(size + (1 if extra else 0), 0.0)
    best, best_key = None, None
    # a combo may sit with its own component only when prices show it adds value; without prices it never does
    for allow in ((False, True) if require_price else (False,)):
        for combo in combinations(pool, size):
            legs = list(combo) + (extra or [])
            if not allowed(legs, cfg, allow):
                continue
            s = score(legs)
            if s["joint"] < floor or (require_price and s["ev"] is None):
                continue
            key = s["ev"] if s["ev"] is not None else s["joint"]
            bar = best_key if not allow or best_key is None else best_key + cfg["combo_component_ev_gain"]
            if best_key is None or key > bar:
                best, best_key = {"legs": legs, **s}, key
    return best


def singles(legs: list, cfg: dict) -> list:
    """Edge rungs: any offered price with positive expected value, with a quarter-Kelly stake."""
    out = []
    for l in legs:
        if l.get("price") is None or l["p"] < cfg.get("single_min_prob", 0.0):
            continue
        ev = expected_value(l["p"], l["price"])
        if ev >= cfg["single_min_ev"]:
            stake = min(kelly_stake(l["p"], l["price"], cfg["kelly_fraction"]), cfg["kelly_cap"])
            out.append({**{k: v for k, v in l.items() if k != "hits"}, "ev": ev, "kelly_stake": stake,
                        "fair_price": fair_american(l["p"])})
    return sorted(out, key=lambda x: -x["ev"])


def slip_legs(ticket: dict, game_label: str) -> list:
    """The site's Leg shape: {description, odds, game}."""
    return [{"description": l["label"], "odds": l.get("price"), "game": game_label} for l in ticket["legs"]]
