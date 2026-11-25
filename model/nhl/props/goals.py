"""Goals and assists, handed out from each simulated game's team goals.

For every simulated goal the scorer is drawn by individual expected goals x finishing at that strength.
Up to two assists follow, drawn by assist rate, with the scorer's line-mates (his forward line at even
strength, his unit on the power play) weighted up: they are the ones on the ice with him. So a player's
share of goals and assists follows his own rates and ice time, and line-mates score points together, which
is what the correlation engine needs. Without game-day lines there are no line-mates to weight.
"""
import numpy as np


def _pick(W: np.ndarray, rng) -> np.ndarray:
    """One column index per row, with probability proportional to the row's weights. Rows of zeros give -1."""
    cs = np.cumsum(W, axis=1)
    tot = cs[:, -1]
    u = rng.random(len(W)) * tot
    idx = (cs < u[:, None]).sum(1)
    return np.where(tot > 0, np.minimum(idx, W.shape[1] - 1), -1)


def _unit_ids(P, col) -> np.ndarray:
    """An integer per player: the same number for players on the same unit, -1 for none."""
    labels = {u: i for i, u in enumerate(sorted({str(x) for x in P[col] if isinstance(x, str)}))}
    return np.array([labels.get(x, -1) if isinstance(x, str) else -1 for x in P[col]])


def _weights(P, stat, strength):
    return P[f"{stat}60_{strength}"].to_numpy(float) * P[strength].to_numpy(float)


def allocate(S, team: str, P, K: dict, rng, linemate_boost: float = 4.0):
    """(goals, assists) as [n_sims, n_players] counts."""
    n, m = S.n, len(P)
    G, A = np.zeros((n, m), int), np.zeros((n, m), int)
    fin = P.finishing.to_numpy(float)
    is_f = (P.group == "F").to_numpy()
    ev_unit = np.where(is_f, _unit_ids(P, "ev_slot"), -1)       # forward lines only: defence pairs play with every line
    pp_unit = _unit_ids(P, "pp_unit")
    for kind, strength, unit in (("ev", "ev", ev_unit), ("pp", "pp", pp_unit), ("sh", "pk", None), ("en", "ev", None), ("ot", "ev", None)):
        cnt = S.goals[team][kind]
        N = int(cnt.sum())
        if not N:
            continue
        sim = np.repeat(np.arange(n), cnt)
        wg = _weights(P, "ixg", strength) * fin + 1e-9
        wa = (P[f"a160_{strength}"].to_numpy(float) + P[f"a260_{strength}"].to_numpy(float)) * P[strength].to_numpy(float) + 1e-9
        if kind == "ot":                                       # three-a-side overtime belongs to the top of the lineup
            wg, wa = wg * P.ev.to_numpy(float), wa * P.ev.to_numpy(float)
        scorer = rng.choice(m, N, p=wg / wg.sum())
        np.add.at(G, (sim, scorer), 1)
        W = np.tile(wa, (N, 1))
        if unit is not None:
            su = unit[scorer]
            W = W * np.where((unit[None, :] == su[:, None]) & (su[:, None] >= 0), linemate_boost, 1.0)
        rows = np.arange(N)
        W[rows, scorer] = 0
        a1 = _pick(W, rng)
        has1 = (a1 >= 0) & (rng.random(N) < K["a1_per_goal"])
        np.add.at(A, (sim[has1], a1[has1]), 1)
        W[rows[has1], a1[has1]] = 0
        a2 = _pick(W, rng)
        has2 = has1 & (a2 >= 0) & (rng.random(N) < K["a2_given_a1"])
        np.add.at(A, (sim[has2], a2[has2]), 1)
    return G, A
