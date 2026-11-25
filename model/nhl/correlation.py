"""Same-game parlay probability: the share of simulated games in which every leg hits together.

Never the product of the single-leg probabilities: every leg is a true/false column over the same 20,000
simulated games, so shots, saves, points and the score move together exactly as the sim moved them.
"""
import numpy as np

from common.tickets import joint  # noqa: F401  (re-exported: the shared counter)


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a.astype(float), b.astype(float))[0, 1])


def lift(legs: list) -> float:
    """Joint chance over the product of the single chances: above 1 means the legs help each other."""
    prod = float(np.prod([l["hits"].mean() for l in legs]))
    return float(joint(legs) / prod) if prod > 0 else 0.0


def pair_table(legs: list) -> list:
    out = []
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            out.append({"a": legs[i]["label"], "b": legs[j]["label"], "corr": round(correlation(legs[i]["hits"], legs[j]["hits"]), 3)})
    return out
