"""Calibration from graded slates.

The ledger keeps every leg's raw model probability and its result. For each market this fits one shift on
the log-odds scale so that forecasts match what happened, shrinks it toward zero in proportion to sample
size (standing rule 8) and caps it. Only legs already graded are used, so nothing from tonight's games
can leak in (rule 7). Several rungs on one player in one game count as a single sample.
"""
import math

import numpy as np
import pandas as pd

from nba.config import CONFIG


def apply(p: float, shift: float) -> float:
    """Move a probability by `shift` on the log-odds scale."""
    if not shift or p <= 0.0 or p >= 1.0:
        return p
    return 1.0 / (1.0 + math.exp(-(math.log(p / (1.0 - p)) + shift)))


def _fit_shift(p: np.ndarray, hit: np.ndarray) -> float:
    """Maximum-likelihood shift s for hit ~ sigmoid(logit(p) + s), by Newton steps."""
    z, s = np.log(p / (1 - p)), 0.0
    for _ in range(25):
        q = 1 / (1 + np.exp(-(z + s)))
        grad, hess = float((hit - q).sum()), float((q * (1 - q)).sum())
        if hess <= 0:
            break
        step = grad / hess
        s += step
        if abs(step) < 1e-6:
            break
    return s


def fit(con, cfg=CONFIG, before: str | None = None) -> dict:
    """{market: {shift, measured, samples, legs, forecast, hit_rate}} from graded over legs. `before` limits
    the fit to legs graded earlier than that time."""
    if not cfg.get("calibration_on"):
        return {}
    L = pd.read_sql("SELECT run_at, game_id, leg_id, player_id, market, side, COALESCE(model_prob_raw, model_prob) p, result, graded_at "
                    "FROM nba_legs WHERE kind='prop' AND side='over' AND result IN ('won','lost')", con)
    if before:
        L = L[L.graded_at < before]
    if L.empty:
        return {}
    L = L.sort_values("run_at").drop_duplicates(["game_id", "leg_id"], keep="last")       # the last run of each game
    L = L[(L.p >= cfg["cal_min_prob"]) & (L.p <= cfg["cal_max_prob"]) & L.market.isin(cfg["calibration_markets"])]
    out = {}
    for m, d in L.groupby("market"):
        n = int(d.groupby(["game_id", "player_id"]).ngroups)
        if n < cfg["cal_min_n"]:
            continue
        hit = (d.result == "won").to_numpy(float)
        measured = _fit_shift(d.p.to_numpy(float), hit)
        shift = measured * n / (n + cfg["cal_shrink_n"])
        shift = float(np.clip(shift, -cfg["cal_max_shift"], cfg["cal_max_shift"]))
        out[m] = {"shift": round(shift, 4), "measured": round(float(measured), 4), "samples": n, "legs": int(len(d)),
                  "forecast": round(float(d.p.mean()), 3), "hit_rate": round(float(hit.mean()), 3)}
    return out


def describe(cal: dict) -> str:
    """One line for the slip notes: what the step does to a 75% forecast in each market."""
    if not cal:
        return ""
    words = {"pts": "points", "reb": "rebounds", "ast": "assists", "fg3m": "threes"}
    parts = [f"{words.get(m, m)} 75% reads {apply(0.75, c['shift']):.0%} ({c['samples']} graded samples)" for m, c in sorted(cal.items())]
    return "Calibration from graded slates: " + "; ".join(parts)
