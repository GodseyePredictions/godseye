"""The slate pipeline in one place, in the order the standing rules require:
data -> availability -> game script (team projection + simulation) -> minutes -> player rates -> player simulation.

`Pipeline` builds every pre-game input once for all games in the frames (past games and, when given,
tonight's). `fit(before_season)` fits the models on earlier seasons only. `run_game` simulates one game.
"""
import zlib

import numpy as np
import pandas as pd

from nba import game_sim as gs
from nba import minutes as mn
from nba import player_sim as ps
from nba import prep, props
from nba.config import CONFIG

CLASH_KEYS = ["tov_pp", "fta_pp", "fga_pp", "r3", "p3", "p2", "ft_pct", "orb", "stl_tov", "blk_fg2a", "ast_fgm"]


class Pipeline:
    def __init__(self, frames: dict, pending_games=None, pending_rosters=None, live_status: dict | None = None, cfg=CONFIG):
        self.cfg = cfg
        live_status = live_status or {}
        self.M = prep.master(frames, pending_games, pending_rosters, live_status.get("out"), live_status.get("ques"),
                             live_status.get("filed"), cfg)
        P, T, L = self.M["players"], self.M["teams"], self.M["league"]
        self.T, self.L = T, L
        self.G = gs.game_table(P, T, L, frames.get("officials"), cfg)
        self.C = gs.clash(gs.team_style(T, L, cfg))
        self.D = props.design(mn.design(P, T, L, cfg), T, L, self.C, self.G, cfg)
        self.market = frames.get("market_lines")
        self.models = {}

    def fit(self, before_season: int, groups_on: dict | None = None):
        """Fit every model on seasons before `before_season` (finished games only)."""
        tr = self.D[(self.D.season < before_season) & (self.D.pending == 0)]
        g = self.G[(self.G.season < before_season) & (self.G.pending == 0)]
        m = {"minutes": mn.fit(tr, self.cfg), "team": gs.fit_team_model(g), "rates": props.fit(tr, self.cfg, groups_on)}
        self.models[before_season] = m
        return m

    def game_inputs(self, game_id: str, models: dict):
        g = self.G[self.G.game_id == game_id].iloc[0]
        pred = gs.blend(models["team"].predict(self.G[self.G.game_id == game_id]), self.market, [g.game_no], self.cfg).iloc[0]
        c = self.C[self.C.game_id == game_id].set_index("team_id")
        rows = self.D[(self.D.game_id == game_id) & (self.D.exp_out == 0) & self.D.base_min.notna()]
        # a player with no minutes yet this season (after the opening weeks) is not projected: there is nothing current to go on
        rows = rows[(rows.s_n > 0) | (rows.game_no <= 5)]
        rows = mn.apply(models["minutes"], rows, self.cfg)
        rows = rows[rows.e_min >= 2.0]
        rows = props.apply(models["rates"], rows, self.cfg)
        return g, pred, c, rows

    def run_game(self, game_id: str, models: dict, n_sims: int | None = None, margin=None, total=None):
        """Simulate one game. Returns (card inputs, GameSims, PlayerSims). `margin`/`total` override the blend."""
        n_sims = n_sims or self.cfg["n_sims"]
        g, pred, c, rows = self.game_inputs(game_id, models)
        seed = zlib.crc32(str(game_id).encode())
        ch = {k: float(c.loc[g.home_id, k]) for k in CLASH_KEYS}
        ca = {k: float(c.loc[g.away_id, k]) for k in CLASH_KEYS}
        sims = gs.simulate(game_id, g.home_id, g.away_id, ch, ca, float(pred.model_poss),
                           float(pred.blend_margin if margin is None else margin),
                           float(pred.blend_total if total is None else total), n_sims, seed, self.cfg)
        Rh, Ra = rows[rows.team_id == g.home_id].reset_index(drop=True), rows[rows.team_id == g.away_id].reset_index(drop=True)
        if len(Rh) < 5 or len(Ra) < 5:
            return {"game": g, "pred": pred, "rows": rows}, sims, None
        players = ps.simulate_game(sims, Rh, Ra, models["minutes"], seed, self.cfg)
        return {"game": g, "pred": pred, "rows": rows}, sims, players
