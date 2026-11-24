"""Cross-game SGP ladder: the best positively-correlated 2- or 3-leg stack from each game, combined across games.

Stack = floor-band bet365 legs from one game whose correlations help each other (QB pass yds / att / TDs with his
receivers' catches and yards, same-player carries + rush yards, a shootout pair across the line of scrimmage).
Ticket = stacks from different games multiplied (games are independent).  Two ladders:
  * props   : props legs only (standing rule: no TD legs in props parlays)
  * allpos  : each game's prop stack + that game's best eligible anytime-TD leg
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .correlation import leg_sigma, ticket_prob
from .tickets import pick_rungs

ROOT = Path(__file__).resolve().parent.parent
LADDER = (4, 6, 8, 10, 12)


def _corr_sum(L: pd.DataFrame, corr) -> float:
    S = leg_sigma(L, corr)
    n = len(L)
    return float(S[np.triu_indices(n, 1)].sum()) if n > 1 else 0.0


def best_stacks(legs: pd.DataFrame, game_id: str, corr: dict, size: int, top_pool=14, min_corr=0.0):
    """Best `size`-leg stack in one game: distinct players unless same player different market, maximise joint
    probability among stacks whose summed pairwise correlation is >= min_corr (so the legs help each other)."""
    pool = pick_rungs(legs[legs.game_id == game_id], "floor").sort_values("p", ascending=False)
    pool = pool.drop_duplicates(["player_id", "market"]).head(top_pool).reset_index(drop=True)
    best = None
    for combo in itertools.combinations(range(len(pool)), size):
        L = pool.iloc[list(combo)]
        if L.player_id.duplicated().any():              # distinct players: a stack, not one bet twice
            continue
        if L.market.value_counts().max() > 2:
            continue
        cs = _corr_sum(L, corr)
        if cs < min_corr:
            continue
        pj = ticket_prob(L, corr, n_sims=60_000)
        if best is None or pj > best[0]:
            best = (pj, L, cs)
    return best


def build_ladders(season, week, games: list[str], atd: pd.DataFrame | None = None, allpos=False):
    """allpos=False by default since Week 9: props parlays never carry TD legs (7 otherwise-perfect tickets died on one)."""
    if not allpos:
        atd = None
    L = pd.read_csv(ROOT / "outputs" / f"prop_ladders_{season}_wk{week}.csv")
    L = L[L.game_id.isin(games)]
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
    stacks = []
    for g in games:
        for size in (2, 3):
            b = best_stacks(L, g, corr, size)
            if b:
                pj, legs, cs = b
                stacks.append({"game_id": g, "size": size, "p": pj, "corr_sum": cs, "legs": legs,
                               "p_indep": float(legs.p.prod())})
    S = pd.DataFrame(stacks)
    out = {"props": [], "allpos": []}
    if S.empty:
        return out, S
    # props ladder: 2-leg stacks ranked by joint p, one per game, nested
    two = S[S["size"] == 2].sort_values("p", ascending=False)
    for n in LADDER:
        k = n // 2
        if len(two) < k:
            break
        picked = two.head(k)
        legs = pd.concat([r.legs for r in picked.itertuples()], ignore_index=True)
        pj = float(np.prod(picked.p))
        out["props"].append({"n": n, "games": list(picked.game_id), "legs": legs, "p": pj,
                             "p_indep": float(legs.p.prod())})
    # all-position ladder: 2-leg prop stack + best eligible ATD in the same game (3 per game)
    if atd is not None and len(atd):
        rows = []
        for r in two.itertuples():
            a = atd[(atd.game_id == r.game_id) & ~atd.singles_only.fillna(False).astype(bool)] \
                .sort_values("p", ascending=False)
            if a.empty:
                continue
            legs = pd.concat([r.legs, a.head(1)], ignore_index=True)
            pj = ticket_prob(legs, corr, n_sims=60_000)
            rows.append({"game_id": r.game_id, "legs": legs, "p": pj, "p_indep": float(legs.p.prod())})
        R = pd.DataFrame(rows).sort_values("p", ascending=False) if rows else pd.DataFrame()
        for n in (3, 6, 9, 12):
            k = n // 3
            if len(R) < k:
                break
            picked = R.head(k)
            legs = pd.concat([x.legs for x in picked.itertuples()], ignore_index=True)
            out["allpos"].append({"n": n, "games": list(picked.game_id), "legs": legs, "p": float(np.prod(picked.p)),
                                  "p_indep": float(legs.p.prod())})
    return out, S
