"""Goalie saves: the opponent's simulated shots on goal minus the goals that beat him, overtime included
(shootout attempts are not saves). Pull risk: a starter far behind after two periods is replaced in a share
of those games and keeps only the saves he had made by then."""
import numpy as np


def draw(S, team: str, cfg, rng) -> dict:
    opp = S.away if team == S.home else S.home
    c = cfg["props"]
    against = S.goals[opp]["ev"] + S.goals[opp]["pp"] + S.goals[opp]["sh"] + S.goals[opp]["ot"]
    full = S.sog[opp] - against
    deficit = -(S.lead_p2 if team == S.home else -S.lead_p2)
    pulled = (deficit >= c["pull_deficit"]) & (rng.random(S.n) < c["pull_prob"])
    through_two = S.sog_p2[opp] - S.ga_p2[team]
    return {"saves": np.where(pulled, through_two, full), "pulled": pulled, "pull_prob": round(float(pulled.mean()), 4),
            "expected_saves": round(float(np.where(pulled, through_two, full).mean()), 2)}
