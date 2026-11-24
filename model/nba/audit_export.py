"""What the website needs to audit a user's own NBA slip: every rated rung, and how legs move together.

The slate's tickets carry a counted joint probability, but a user's slip can combine any legs. For those
the site needs two things from the same simulations the tickets came from:

  - the ladder: every offered player-prop rung for a confirmed player, with its model probability
    (calibrated, exactly as the ticket builder sees it);
  - the correlations: for each pair of (player, market) in a game, how the two simulated stat lines
    move together.

The correlation is a rank correlation of the simulated values over the simulations where both players
play, converted to the scale the site's joint-probability engine uses (r = 2 sin(pi * rho / 6)). It is
one number per pair, whatever the rungs. It is measured from tonight's simulations, never assumed.

Nothing here changes a projection, a probability or a ticket.
"""
import math

import numpy as np
import pandas as pd

from nba import sgp
from nba.config import CONFIG

# reasons a rung is rated but carries a warning; a rung that is only under the floor needs no note (the site applies the floor)
_NOTE_PREFIXES = ("fails the shooting gate", "under the floor inside blowout", "starter's upper rung", "model ")


def ladder(legs: list, cfg=CONFIG) -> list:
    """Every player-prop rung for a player confirmed in tonight. No verified availability, no leg."""
    out = []
    for l in legs:
        if l.get("kind") != "prop" or not l.get("eligible_player") or l.get("player_id") is None:
            continue
        ok, why = sgp.sgp_eligible(l, cfg, require_price=False)
        if not l.get("gate_ok", True):           # reported even when the rung is also under the floor
            note = "fails the shooting gate"
        else:
            note = why if (not ok and why.startswith(_NOTE_PREFIXES) and "minimum is under the floor" not in why) else None
        out.append({"player_id": str(l["player_id"]), "name": l.get("name"), "team_id": None if l.get("team_id") is None else str(l["team_id"]),
                    "market": l["market"], "line": float(l["line"]), "side": l["side"], "p": float(l["p"]),
                    "price": l.get("price"), "note": note})
    return out


def correlations(players, nodes: list, cfg=CONFIG) -> dict:
    """{"player_id:market|player_id:market": r} for every pair of nodes, keys in sorted order.

    Pairs weaker than cfg["audit_corr_min"] are left out (the site treats a missing pair as unrelated),
    as are pairs with too few simulations where both players play to measure anything.
    """
    nodes = sorted(set(nodes))
    if len(nodes) < 2:
        return {}
    vals = np.column_stack([players.values(pid, m).astype(float) for pid, m in nodes])
    act = np.column_stack([players.active(pid) for pid, _ in nodes])
    out = {}
    need = cfg["audit_min_active_sims"]
    floor = cfg["audit_corr_min"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if nodes[i] == nodes[j]:
                continue
            both = act[:, i] & act[:, j]
            if both.sum() < need:
                continue
            a, b = vals[both, i], vals[both, j]
            if a.std() == 0 or b.std() == 0:
                continue
            rho = float(np.corrcoef(pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy())[0, 1])
            if not math.isfinite(rho):
                continue
            r = 2.0 * math.sin(math.pi * rho / 6.0)
            if abs(r) >= floor:
                out[f"{nodes[i][0]}:{nodes[i][1]}|{nodes[j][0]}:{nodes[j][1]}"] = round(max(-0.99, min(0.99, r)), 3)
    return out


def block(legs: list, players, cfg=CONFIG) -> dict:
    """The audit data for one game: {"ladder": [...], "corr": {...}}."""
    lad = ladder(legs, cfg)
    nodes = [(l["player_id"], l["market"]) for l in lad]
    return {"ladder": lad, "corr": correlations(players, nodes, cfg) if players is not None else {}}
