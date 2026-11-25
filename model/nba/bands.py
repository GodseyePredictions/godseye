"""Price-band slips, value locks and cross-game slips built from the same simulated games as the standard tickets
(owner, 24 November 2026).

- Band slips: for each configured price band, the 6-leg same-game slip with the highest counted chance whose
  listed price (leg prices multiplied) falls inside the band. Every leg clears the standing slip rules.
- Value locks: slip-eligible legs priced inside a configured range, strongest first.
- Cross-game slips: games do not affect each other, so the chance is each game's counted chance multiplied.
"""
from itertools import combinations

import numpy as np

from common import tickets as tk
from common.odds_math import decimal_to_american, fair_american, to_decimal

from nba import sgp
from nba.config import CONFIG


def _ticket(kind: str, legs: list, joint: float, decimal: float) -> dict:
    return {"type": kind, "legs": legs, "joint": joint, "decimal": decimal, "ev": joint * decimal - 1, "price_is_estimate": True,
            "fair_price": fair_american(joint), "book_price": decimal_to_american(decimal)}


def band_tickets(legs: list, cfg=CONFIG) -> tuple[list, list]:
    """One slip per price band, plus a note for every band no combination can reach."""
    bands, size = cfg.get("price_band_slips") or [], cfg["price_band_size"]
    if not bands:
        return [], []
    elig = [l for l in legs if sgp.sgp_eligible(l, cfg, True)[0]]
    pool = sorted(sgp.floor_rungs(elig), key=lambda l: -l["p"])[:cfg["price_band_pool"]]
    dec = np.array([to_decimal(l["price"]) for l in pool])
    lo = [to_decimal(b["min_price"]) for b in bands]
    hi = [to_decimal(b["max_price"]) for b in bands]
    best = [None] * len(bands)
    for idx in combinations(range(len(pool)), size):
        d = float(np.prod(dec[list(idx)]))
        i = next((i for i in range(len(bands)) if lo[i] <= d <= hi[i]), None)
        if i is None:
            continue
        combo = [pool[j] for j in idx]
        if not tk.allowed(combo, cfg, False, size):
            continue
        j = tk.joint(combo)
        if best[i] is None or j > best[i][0]:
            best[i] = (j, d, combo)
    out, notes = [], []
    for b, t in zip(bands, best):
        if t is None:
            notes.append(f"{b['key']}: no bet (no {size}-leg combination of qualifying legs is priced "
                         f"{b['min_price']:+d} to {b['max_price']:+d})")
        else:
            out.append(_ticket(b["key"], t[2], t[0], t[1]))
    return out, notes


def value_locks(legs: list, cfg=CONFIG) -> list:
    """Slip-eligible legs priced inside the value range, strongest first."""
    lo, hi = cfg["value_lock_price_range"]
    return sorted([l for l in legs if sgp.sgp_eligible(l, cfg, True)[0] and lo <= l["price"] <= hi], key=lambda l: -l["p"])


def _cross(kind: str, parts: list) -> dict:
    """parts: (game_id, matchup, legs). The slip's chance is the product of each game's counted chance."""
    done = [(gid, mu, ls, tk.joint(ls), float(np.prod([to_decimal(l["price"]) for l in ls]))) for gid, mu, ls in parts]
    joint = float(np.prod([p[3] for p in done]))
    dec = float(np.prod([p[4] for p in done]))
    return {"type": kind, "n_legs": sum(len(p[2]) for p in done), "joint": joint, "fair_price": fair_american(joint),
            "book_price": decimal_to_american(dec), "ev": joint * dec - 1, "price_is_estimate": True,
            "parts": [{"game_id": gid, "matchup": mu, "joint": j, "legs": [{k: v for k, v in l.items() if k not in ("hits", "active")} for l in ls]}
                      for gid, mu, ls, j, _ in done]}


def value_parlay(per_game: dict, cfg=CONFIG) -> dict | None:
    """The strongest value locks across the slate, one leg per player, within the per-slip rebound cap per game.
    per_game: {game_id: (matchup, value_locks)}."""
    n = cfg["value_parlay_legs"]
    reb_cap = cfg.get("max_legs_per_market", {}).get("reb")
    chosen, count = {}, 0
    for gid, mu, l in sorted(((g, mu, l) for g, (mu, ls) in per_game.items() for l in ls), key=lambda x: -x[2]["p"]):
        if count >= n:
            break
        cur = chosen.setdefault(gid, (mu, []))[1]
        if any(c["player_id"] == l["player_id"] for c in cur):
            continue
        if reb_cap is not None and l["market"] == "reb" and sum(c["market"] == "reb" for c in cur) >= reb_cap:
            continue
        cur.append(l)
        count += 1
    parts = [(gid, mu, ls) for gid, (mu, ls) in chosen.items() if ls]
    return _cross("value_locks", parts) if count >= cfg["value_parlay_min_legs"] else None


def lotto(per_game: dict, cfg=CONFIG) -> dict | None:
    """Every game's longest-priced band slip joined into one. per_game: {game_id: (matchup, band tickets)}."""
    order = [b["key"] for b in (cfg.get("price_band_slips") or [])][::-1]
    cands = []
    for gid, (mu, ts) in per_game.items():
        t = next((t for k in order for t in ts if t["type"] == k), None)
        if t is not None:
            cands.append((t["joint"], gid, mu, t["legs"]))
    n = cfg.get("lotto_games", 3)
    if len(cands) < min(n, len(per_game)):
        return None                          # every game it draws from needs a band slip
    # the games whose longest band slip the model rates highest, so a big slate does not make a 50-leg slip
    parts = [(gid, mu, legs) for _, gid, mu, legs in sorted(cands, key=lambda c: -c[0])[:n]]
    return _cross("lotto", parts) if len(parts) >= 2 else None
