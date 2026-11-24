"""Head-to-head report card: ledger engine (shipped prices) vs this model on the same player-games."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ledger import norm, parse


def _ll(y, p):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def head_to_head(ledger_path, wf: pd.DataFrame):
    L = parse(ledger_path)
    W = wf.copy()
    W["key"] = norm(W.name)
    L["key"] = norm(L.name)
    m = L.merge(W[["week", "team", "key", "p_attd", "label", "pos_group"]], on=["week", "team", "key"], how="left")
    unmatched = m[m.p_attd.isna()][["build", "week", "name", "team"]]
    m = m[m.p_attd.notna()].copy()
    rows = []
    for b, g in m.groupby("build", sort=False):
        y = g.scored.values
        rows.append({"build": b, "n": len(g), "hit_rate": y.mean(), "ledger_avg_p": g.p_ledger.mean(),
                     "new_avg_p": g.p_attd.mean(), "ledger_logloss": _ll(y, g.p_ledger.values),
                     "new_logloss": _ll(y, g.p_attd.values),
                     "ledger_brier": np.mean((g.p_ledger - y) ** 2), "new_brier": np.mean((g.p_attd - y) ** 2)})
    by_build = pd.DataFrame(rows).set_index("build")
    shipped = m[m.build.str.contains("shipped")]
    pos = shipped.groupby("pos").apply(lambda g: pd.Series({
        "n": len(g), "hit": g.scored.mean(), "ledger_p": g.p_ledger.mean(), "new_p": g.p_attd.mean(),
        "ledger_ll": _ll(g.scored.values, g.p_ledger.values), "new_ll": _ll(g.scored.values, g.p_attd.values)}))
    # biggest disagreements on shipped legs
    shipped = shipped.assign(diff=shipped.p_attd - shipped.p_ledger)
    disagree = shipped.reindex(shipped["diff"].abs().sort_values(ascending=False).index) \
        [["build", "week", "name", "team", "pos", "p_ledger", "p_attd", "scored"]].head(25)
    return by_build, pos, disagree, unmatched, m


def weekly_boards(wf: pd.DataFrame, top=16):
    """What this model's own top-N board would have done each week."""
    rows = []
    for w, g in wf.groupby("week"):
        if g.game_id.nunique() < 3:
            continue
        b = g.nlargest(top, "p_attd")
        rows.append({"week": w, "top_n": len(b), "hits": int(b.label.sum()), "expected": b.p_attd.sum(),
                     "top8_hits": int(b.head(8).label.sum()), "top8_expected": b.head(8).p_attd.sum()})
    return pd.DataFrame(rows).set_index("week")


def props_head_to_head(ledger_path, wf_props: pd.DataFrame, season=2026):
    """Ledger props legs vs this model's walk-forward price for the exact same player/market/rung."""
    from .ledger import parse_props
    L = parse_props(ledger_path)
    L["game_id"] = [f"{season}_{w:02d}_{g.split('@')[0]}_{g.split('@')[1]}" for w, g in zip(L.week, L.game)]
    L["key"] = norm(L.name)
    W = wf_props.copy()
    W["key"] = norm(W.name)
    m = L.merge(W[["game_id", "key", "market", "k", "p", "x"]], on=["game_id", "key", "market", "k"], how="left")
    unmatched = m[m.p.isna()]
    m = m[m.p.notna()].copy()
    m["hit_check"] = (m.x >= m.k).astype(int)
    rows = []
    for b, g in m.groupby("build", sort=False):
        y = g.hit.values
        rows.append({"build": b, "n": len(g), "hit": y.mean(), "ledger_p": g.p_ledger.mean(), "new_p": g.p.mean(),
                     "ledger_ll": _ll(y, g.p_ledger.values), "new_ll": _ll(y, g.p.values),
                     "ledger_brier": float(np.mean((g.p_ledger - y) ** 2)), "new_brier": float(np.mean((g.p - y) ** 2))})
    return pd.DataFrame(rows).set_index("build"), m, unmatched
