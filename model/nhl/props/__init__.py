"""Player props, drawn inside the game sim's own simulated games.

Every prop is projected ice time by strength x per-60 rate x opponent adjustment x game-script adjustment
x arena factor. Counting props (shots, hits, blocks) are drawn around each simulated game's own script;
goals and assists are handed out from that game's simulated team goals, so points are a joint draw; saves
are the opponent's simulated shots minus the goals that got through.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from nhl.props import assists, blocks, goals, hits, points, saves, shots

SKATER_MARKETS = ("sog", "pts", "ast", "goals", "hits", "blk")


@dataclass
class PlayerSims:
    game_id: int
    players: pd.DataFrame                    # one row per priced skater: player_id, name, team, group, ev, pp, pk, units, notes
    data: dict = field(default_factory=dict)  # market -> [n_sims, n_players] counts
    goalies: dict = field(default_factory=dict)  # team -> {"player_id", "name", "saves": [n_sims], "pulled": [n_sims], "notes"}
    expected: dict = field(default_factory=dict)  # market -> itemised expectation per player

    def column(self, player_id: int) -> int:
        return int(np.flatnonzero(self.players.player_id.to_numpy() == player_id)[0])

    def prob(self, market: str, player_id: int, rung: int) -> float:
        return float((self.data[market][:, self.column(player_id)] >= rung).mean())


def script_toi(S, team: str, P: pd.DataFrame, cfg) -> np.ndarray:
    """[n_sims, n_players] ice-time multiplier: the top line sits late in a blowout and is leaned on when trailing."""
    c = cfg["props"]
    lead = S.lead_p2 if team == S.home else -S.lead_p2
    top = P.top_line.to_numpy(bool)
    f = np.ones((S.n, len(P)))
    f[np.ix_(lead >= cfg["sim"]["blowout_margin"], top)] -= c["blowout_top_line_trim"]
    f[np.ix_(lead < 0, top)] += c["trailing_top_line_boost"]
    return f


def count_draw(E: np.ndarray, per_sim: np.ndarray, toi_f: np.ndarray, disp: float, rng) -> np.ndarray:
    """Poisson around each simulated game's own expectation; `disp` adds a gamma spread (negative binomial)."""
    mean = E[None, :] * per_sim[:, None] * toi_f
    if disp > 0:
        mean = mean * rng.gamma(1 / disp, disp, mean.shape)
    return rng.poisson(mean)


def simulate(S, rosters: dict, ctx: dict, cfg, seed: int | None = None, game_id: int = 0, goalies: dict | None = None) -> PlayerSims:
    """rosters: {team: skater frame from context.roster()}. goalies: {team: {"player_id", "name"}} for the starters."""
    rng = np.random.default_rng((cfg["sim"]["seed"] if seed is None else seed) + 7)
    frames, data, expected = [], {m: [] for m in SKATER_MARKETS}, {m: [] for m in ("sog", "hits", "blk")}
    for team in (S.home, S.away):
        P = rosters[team].reset_index(drop=True)
        opp = S.away if team == S.home else S.home
        tf = script_toi(S, team, P, cfg)
        e_sog, n_sog = shots.expected(P, S.lam[team], ctx, team, opp, S.home, cfg)
        e_hit, n_hit = hits.expected(P, ctx, team, opp, S.home, cfg)
        e_blk, n_blk = blocks.expected(P, ctx, team, opp, S.home, cfg)
        d = cfg["props"]["dispersion"]
        sog = count_draw(e_sog, S.f_sog[team], tf, d["sog"], rng)
        g, a = goals.allocate(S, team, P, ctx["K"], rng, cfg["props"]["linemate_boost"])
        sog = np.maximum(sog, g)                               # a goal is a shot on goal
        data["sog"].append(sog)
        data["hits"].append(count_draw(e_hit, S.f_hits[team], tf, d["hits"], rng))
        data["blk"].append(count_draw(e_blk, S.f_blk[team] * S.f_sog[opp], tf, d["blk"], rng))
        data["goals"].append(g)
        data["ast"].append(assists.from_allocation(a))
        data["pts"].append(points.joint(g, a))
        for m, e, notes in (("sog", e_sog, n_sog), ("hits", e_hit, n_hit), ("blk", e_blk, n_blk)):
            expected[m] += [{"player_id": int(p), "expected": round(float(x), 3), "steps": notes} for p, x in zip(P.player_id, e)]
        frames.append(P)
    out = PlayerSims(game_id, pd.concat(frames, ignore_index=True), {m: np.concatenate(v, axis=1) for m, v in data.items()},
                     expected=expected)
    for team in (S.home, S.away):
        gk = (goalies or {}).get(team) or {}
        out.goalies[team] = {**gk, **saves.draw(S, team, cfg, rng)}
    return out
