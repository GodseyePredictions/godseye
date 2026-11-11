"""Player simulation, run on top of the stored simulated games.

For each simulated game the team totals already exist (shots by type, makes, free throws, rebounds,
assists, steals, blocks). This module hands those exact totals out to the players who are on the floor
in that game, so:
  - a player's extra shots come out of his teammates' shots (team attempts add up),
  - assists are a share of the team's made shots in that game, rebounds a share of that game's misses,
    steals and blocks a share of the opponent's turnovers and two-point attempts,
  - pace, shooting luck, margin and garbage time are shared by everyone in that game.
Each player's share is minutes in that simulation x his rate tonight x a per-game wobble.
Probabilities are then counted, never multiplied.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from nba.config import CONFIG

STATS = ["pts", "reb", "ast", "fg3m", "stl", "blk"]
COMBOS = {"pra": ("pts", "reb", "ast"), "pr": ("pts", "reb"), "pa": ("pts", "ast")}


@dataclass
class PlayerSims:
    game_id: str
    players: pd.DataFrame      # one row per simulated player: player_id, name, team_id, role, e_min ...
    data: dict                 # stat -> (N, n_players) arrays; includes "min", "fga", "fg3a"
    blowout: np.ndarray        # (N,) +1 home blowout, -1 away blowout, 0 neither
    close: np.ndarray          # (N,) close-game flag

    def col(self, player_id: str) -> int:
        return int(np.where(self.players.player_id.to_numpy() == player_id)[0][0])

    def values(self, player_id: str, market: str) -> np.ndarray:
        j = self.col(player_id)
        if market in COMBOS:
            return sum(self.data[s][:, j] for s in COMBOS[market])
        if market in ("dd", "td"):
            cats = sum((self.data[s][:, j] >= 10).astype(int) for s in ("pts", "reb", "ast", "stl", "blk"))
            return (cats >= (2 if market == "dd" else 3)).astype(int)
        return self.data[market][:, j]

    def hits(self, player_id: str, market: str, line: float, side: str = "over") -> np.ndarray:
        v = self.values(player_id, market)
        return v > line if side in ("over", "yes") else v < line

    def active(self, player_id: str) -> np.ndarray:
        """Simulations in which the player takes the floor. A prop is void if he does not play,
        so every prop probability is counted over these simulations only."""
        return self.data["min"][:, self.col(player_id)] > 0

    def prob(self, player_id: str, market: str, line: float, side: str = "over") -> float:
        a = self.active(player_id)
        return float(self.hits(player_id, market, line, side)[a].mean()) if a.any() else 0.0


def _alloc(rng, totals: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Hand each simulation's team total to players in proportion to that simulation's weights."""
    w = np.maximum(weights, 0)
    s = w.sum(1, keepdims=True)
    p = np.where(s > 0, w / np.where(s > 0, s, 1), 1.0 / w.shape[1])
    return rng.multinomial(totals, p)


def _alloc_capped(rng, totals: np.ndarray, weights: np.ndarray, cap: np.ndarray) -> np.ndarray:
    """Like _alloc, but nobody can get more than his cap (makes cannot exceed attempts). Overflow is re-dealt."""
    got = np.minimum(_alloc(rng, totals, weights), cap)
    for _ in range(3):
        left = totals - got.sum(1)
        if not (left > 0).any():
            break
        room = cap - got
        got = got + np.minimum(_alloc(rng, np.maximum(left, 0), weights * (room > 0)), room)
    return got


def simulate_team(rng, R: pd.DataFrame, minutes: np.ndarray, box: dict, t: int, close: np.ndarray, cfg=CONFIG) -> dict:
    """R: one team's players with tonight's rates. minutes: (N, n). box: the game's simulated team totals."""
    N, n = minutes.shape
    sd = cfg["share_noise_sd"]
    def wob(key):
        return np.exp(rng.normal(0, sd[key], (N, n)) - sd[key] ** 2 / 2)
    usage = wob("usage")
    q4 = 1 + cfg["q4_usage_weight"] * (R.q4_usage_ratio.to_numpy() - 1)
    lift = np.where(close[:, None], q4[None, :], 1.0)       # in close games the fourth-quarter pecking order applies
    w2 = minutes * R.r_fg2a.to_numpy()[None, :] * usage * wob("fg2a") * lift
    w3 = minutes * R.r_fg3a.to_numpy()[None, :] * usage * wob("fg3a") * lift
    wf = minutes * R.r_fta.to_numpy()[None, :] * usage * wob("fta") * lift
    fg2a = _alloc(rng, box["fg2a"][:, t], w2)
    fg3a = _alloc(rng, box["fg3a"][:, t], w3)
    fta = _alloc(rng, box["fta"][:, t], wf)
    fg2m = _alloc_capped(rng, box["fg2m"][:, t], fg2a * R.p2.to_numpy()[None, :] * wob("make"), fg2a)
    fg3m = _alloc_capped(rng, box["fg3m"][:, t], fg3a * R.p3.to_numpy()[None, :] * wob("make"), fg3a)
    ftm = _alloc_capped(rng, box["ftm"][:, t], fta * R.pft.to_numpy()[None, :], fta)
    oreb = _alloc(rng, box["oreb"][:, t], minutes * R.r_oreb.to_numpy()[None, :] * wob("oreb"))
    dreb = _alloc(rng, box["dreb"][:, t], minutes * R.r_dreb.to_numpy()[None, :] * wob("dreb"))
    # an assist needs a made basket: the pool is this game's assisted makes, so a hot shooting night for the
    # team lifts every passer and a cold one lowers them
    fgm = fg2m + fg3m
    ast = _alloc(rng, box["ast"][:, t], minutes * R.r_ast.to_numpy()[None, :] * wob("ast"))
    stl = _alloc(rng, box["stl"][:, t], minutes * R.r_stl.to_numpy()[None, :] * wob("stl"))
    blk = _alloc(rng, box["blk"][:, t], minutes * R.r_blk.to_numpy()[None, :] * wob("blk"))
    return {"min": minutes, "pts": 2 * fg2m + 3 * fg3m + ftm, "reb": oreb + dreb, "ast": ast, "fg3m": fg3m, "stl": stl,
            "blk": blk, "fga": fg2a + fg3a, "fg3a": fg3a, "fgm": fgm, "fta": fta}


def simulate_game(sims, R_home: pd.DataFrame, R_away: pd.DataFrame, minutes_model, seed: int, cfg=CONFIG) -> PlayerSims:
    rng = np.random.default_rng(seed + 1)
    close = sims.close(cfg)
    out, frames = {}, []
    q4_min = []
    for t, R, sign in ((0, R_home, 1), (1, R_away, -1)):
        mm = minutes_model.simulate(R, sign * sims.q4_entry, sims.ot, rng)
        d = simulate_team(rng, R, mm["minutes"], sims.box, t, close, cfg)
        for k, v in d.items():
            out.setdefault(k, []).append(v)
        q4_min.append(mm["q4_minutes"])
        frames.append(R)
    data = {k: np.concatenate(v, axis=1) for k, v in out.items()}
    data["q4_min"] = np.concatenate(q4_min, axis=1)
    players = pd.concat(frames, ignore_index=True)
    return PlayerSims(sims.game_id, players, data, sims.blowout(cfg), close)


def joint_prob(hit_arrays: list[np.ndarray], active: np.ndarray | None = None) -> float:
    """Chance that every leg hits, counted over the simulated games (those where every leg's player plays)."""
    if not hit_arrays:
        return 0.0
    allhit = np.logical_and.reduce(hit_arrays)
    if active is not None:
        return float(allhit[active].mean()) if active.any() else 0.0
    return float(allhit.mean())


def correlation_table(labels: list[str], hit_arrays: list[np.ndarray]) -> pd.DataFrame:
    m = np.array(hit_arrays, float)
    ok = m.std(1) > 0
    c = np.full((len(labels), len(labels)), np.nan)
    if ok.sum() > 1:
        c[np.ix_(ok, ok)] = np.corrcoef(m[ok])
    return pd.DataFrame(c, index=labels, columns=labels).round(2)


def split_prob(ps: PlayerSims, hits: np.ndarray, active: np.ndarray | None = None) -> dict:
    """A leg's probability overall, inside blowout simulations and inside close-game simulations."""
    a = np.ones(len(hits), bool) if active is None else active
    b = (ps.blowout != 0) & a
    c = ps.close & a
    return {"all": float(hits[a].mean()) if a.any() else 0.0, "blowout": float(hits[b].mean()) if b.sum() >= 50 else None,
            "close": float(hits[c].mean()) if c.sum() >= 50 else None, "n_blowout": int(b.sum()), "n_close": int(c.sum())}


def summary(ps: PlayerSims) -> pd.DataFrame:
    """Per player: mean and percentiles of minutes, mean of each stat, blowout exposure."""
    P = ps.players[["player_id", "name", "team_id", "role", "e_min"]].copy()
    m = ps.data["min"]
    mm = np.where(m > 0, m, np.nan)                       # all figures are "if he plays"
    P["min_mean"] = np.nanmean(mm, 0)
    P["min_p10"], P["min_p50"], P["min_p90"] = np.nanpercentile(mm, 10, 0), np.nanpercentile(mm, 50, 0), np.nanpercentile(mm, 90, 0)
    P["p_play"] = (m > 0).mean(0)
    for s in STATS:
        P[s] = np.nanmean(np.where(m > 0, ps.data[s], np.nan), 0)
    b = ps.blowout != 0
    if b.sum() >= 30 and (~b).sum() >= 30:
        pra = ps.data["pts"] + ps.data["reb"] + ps.data["ast"]
        P["blowout_exposure"] = 1 - pra[b].mean(0) / np.maximum(pra[~b].mean(0), 1e-9)
        P["min_in_blowout"], P["min_otherwise"] = m[b].mean(0), m[~b].mean(0)
    else:
        P["blowout_exposure"], P["min_in_blowout"], P["min_otherwise"] = 0.0, np.nan, np.nan
    P["q4_min"] = ps.data["q4_min"].mean(0)
    return P
