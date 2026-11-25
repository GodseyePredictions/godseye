"""Shots on goal: shot attempts per 60 x attempts-to-SOG rate (already one rate per strength) x ice time,
then the opponent's shots allowed, the rink's SOG bias, and a scale toward the team's simulated total."""
import numpy as np


def by_strength(P, stat: str) -> np.ndarray:
    return sum(P[f"{stat}60_{s}"].to_numpy(float) * P[s].to_numpy(float) / 3600 for s in ("ev", "pp", "pk"))


def expected(P, lam_team: dict, ctx, team, opp, home, cfg):
    base = by_strength(P, "sog")
    tr = ctx["team_rates"]
    opp_idx = float(tr[(tr.team == opp) & (tr.strength == "all")].sog_a60_idx.iloc[0])
    arena = ctx["arena"].get((home, "sog"), 1.0)
    e = base * opp_idx * arena
    rec = cfg["props"]["team_reconcile"]
    scale = (lam_team["sog_mean"] / e.sum()) ** rec if e.sum() > 0 else 1.0
    notes = [{"what": f"{opp} shots allowed index", "factor": round(opp_idx, 3)}, {"what": f"{home} rink SOG bias", "factor": round(arena, 3)},
             {"what": "scaled toward the team's simulated shots", "factor": round(float(scale), 3)}]
    return e * scale, notes
