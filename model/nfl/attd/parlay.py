"""Edge finding + correlation-aware parlay construction."""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .correlation import build_sigma, joint_prob

__all__ = ["attach_odds", "build_parlays"]


def american_to_decimal(a):
    a = float(a)
    return 1 + (a / 100 if a > 0 else 100 / -a)


def decimal_to_american(d):
    return int(round((d - 1) * 100)) if d >= 2 else int(round(-100 / (d - 1)))


def attach_odds(proj: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    """odds: columns [player, odds] (American). Matches on case-insensitive name."""
    o = odds.copy()
    o["key"] = o.player.str.lower().str.replace(r"[^a-z]", "", regex=True)
    p = proj.copy()
    p["key"] = p.name.str.lower().str.replace(r"[^a-z]", "", regex=True)
    m = p.merge(o[["key", "odds"]], on="key", how="inner")
    missing = set(o.key) - set(m.key)
    if missing:
        print(f"  [warn] {len(missing)} odds rows had no projection match: {sorted(missing)[:10]}")
    m["dec"] = m.odds.map(american_to_decimal)
    m["implied"] = 1 / m.dec
    m["edge"] = m.p_attd - m.implied
    m["ev"] = m.p_attd * m.dec - 1
    m["kelly"] = ((m.dec - 1) * m.p_attd - (1 - m.p_attd)) / (m.dec - 1)
    return m.drop(columns="key").sort_values("ev", ascending=False)


def build_parlays(legs: pd.DataFrame, corr: dict, sizes=(2, 3, 4), top_legs=14, min_leg_p=0.18,
                  sgp_haircut=0.0, n_out=25, max_per_game=None):
    """Enumerate parlays from the best +EV legs and price each with the correlation model.

    legs needs: name, team, game_id, pos_group, p_attd, dec.
    Standing rule: Questionable players and players returning from a 2+ game absence are singles only.
    sgp_haircut: same-game parlays are rarely paid at full product-of-odds; e.g. 0.25 assumes the
                 book cuts the SGP payout 25% vs. multiplying legs.  Set from the actual SGP quote.
    """
    ok = ~legs.get("singles_only", pd.Series(False, index=legs.index)).fillna(False).astype(bool)
    pool = legs[ok & (legs.p_attd >= min_leg_p) & (legs.ev > 0)].nlargest(top_legs, "ev").reset_index(drop=True)
    rows = []
    for k in sizes:
        for combo in itertools.combinations(range(len(pool)), k):
            L = pool.iloc[list(combo)]
            if max_per_game and L.game_id.value_counts().max() > max_per_game:
                continue
            pj = 1.0
            for _, G in L.groupby("game_id"):      # games are independent; correlate within game only
                pj *= joint_prob(G.p_attd.values, build_sigma(G, corr), n_sims=300_000)
            p_ind = float(np.prod(L.p_attd.values))
            dec = float(np.prod(L.dec.values))
            if L.game_id.duplicated().any():
                dec = 1 + (dec - 1) * (1 - sgp_haircut)
            ev = pj * dec - 1
            kelly = max(0.0, (pj * dec - 1) / (dec - 1))
            rows.append({"legs": " + ".join(L.name), "n": k, "p_joint": pj, "p_if_indep": p_ind,
                         "corr_lift": pj / p_ind, "dec": dec, "american": decimal_to_american(dec),
                         "fair_american": decimal_to_american(1 / pj), "ev": ev, "kelly": kelly,
                         "same_game": bool(L.game_id.duplicated().any())})
    if not rows:
        return pd.DataFrame()
    r = pd.DataFrame(rows)
    # Rank by expected log-growth at quarter Kelly (balances EV against variance)
    f = 0.25 * r.kelly
    r["growth"] = r.p_joint * np.log1p(f * (r.dec - 1)) + (1 - r.p_joint) * np.log1p(-f)
    return r.sort_values("growth", ascending=False).head(n_out).reset_index(drop=True)
