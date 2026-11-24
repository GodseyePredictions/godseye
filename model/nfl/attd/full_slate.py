"""Full-slate comparison: algorithm slips vs matchup-read slips vs the agreed (consensus) slips, plus ATDs with the
run-defence matchup. EXPERIMENTAL reads; the consensus build keeps every probability as the model's."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .atd_slip import CUSHION, _pick_style, joint
from .defense_report import team_defense
from .early import apply_overrides, atd_parlay_pool, backup_qb_teams
from .matchup import reads as _reads
from .script_sgp import build_script_sgps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"


def build(season: int, week: int, games: list[str]) -> dict:
    F = apply_overrides(pd.read_parquet(OUT / f"projection_features_{season}_wk{week}.parquet"))
    L = apply_overrides(pd.read_csv(OUT / f"prop_ladders_{season}_wk{week}.csv"))
    A = apply_overrides(pd.read_csv(OUT / f"atd_{season}_wk{week}.csv"))
    PF = pd.read_parquet(OUT / f"props_features_{season}_wk{week}.parquet")
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
    corr_atd = json.loads((ROOT / "models" / "correlations.json").read_text())
    bq = backup_qb_teams(season, week)
    D = team_defense(season, week)
    Aok = A[~A.singles_only.fillna(False).astype(bool)]
    per = []
    for g in games:
        try:
            R = _reads(season, week, g, L, PF)
            m = build_script_sgps(L, Aok, PF, g, corr, hold_pass=tuple(bq))
            r = build_script_sgps(L, Aok, PF, g, corr, hold_pass=tuple(bq), reads=R, read_mode="steer")
            c = build_script_sgps(L, Aok, PF, g, corr, hold_pass=tuple(bq), reads=R, read_mode="consensus")
        except Exception as e:  # noqa: BLE001
            print("  [full slate]", g, e); continue
        key = lambda df: set(zip(df.player_id, df.market, df.k.fillna(-1)))  # noqa: E731
        def lad(o, n): return next((t for t in o["ladder"] if t["n"] == n), None)
        cmp = {}
        for n in (4, 6, 8):
            a, b, cc = lad(m, n), lad(r, n), lad(c, n)
            cmp[n] = {"model": a, "reads": b, "final": cc or a, "final_is": "agreed" if cc else "model (too few agreed legs)",
                      "same_as_model": bool(a and cc and key(a["legs"]) == key(cc["legs"]))}
        per.append({"game": g, "model": m, "reads": r, "final": c, "cmp": cmp, "R": R})
    # ---- ATDs: model board + run-defence matchup tick for backs
    W = F[F.game_id.isin(games)].copy()
    n = len(D)
    W["opp_run_rank"] = W.opp.map(D.r_rb_rush); W["opp_rushtd_rank"] = W.opp.map(D.r_rb_rushtd)
    W["matchup"] = np.where((W.pos_group == "RB") & (W.opp_run_rank >= n - 9), "soft run defence",
                            np.where((W.pos_group == "RB") & (W.opp_run_rank <= 8), "stingy run defence", ""))
    ok, held = atd_parlay_pool(W, bq)
    ok = ok[ok.pos_group.isin(["RB", "QB"]) & (ok.p_attd >= 0.20)]
    model_pick = _pick_style(ok.sort_values("p_attd", ascending=False), 10, "chalk")
    lg = np.log(ok.p_attd / (1 - ok.p_attd)) + np.where(ok.matchup == "soft run defence", 0.20, np.where(ok.matchup == "stingy run defence", -0.20, 0.0))
    final_pick = _pick_style(ok.assign(_s=lg).sort_values("_s", ascending=False), 10, "chalk")
    def tickets(pk):
        out = []
        for k in (4, 6, 8, 10):
            legs = pk.head(k)
            if len(legs) == k:
                out.append({"n": k, "legs": legs, "p": joint(legs, corr_atd), "p_indep": float(legs.p_attd.prod())})
        return out
    board = W[W.p_attd >= 0.25].sort_values("p_attd", ascending=False).assign(play=lambda d: d.p_attd - d.pos_group.map(CUSHION).fillna(0.05))
    return {"games": games, "per_game": per, "D": D, "atd_model": tickets(model_pick), "atd_final": tickets(final_pick),
            "board": board, "held": held, "bq": bq, "W": W}
