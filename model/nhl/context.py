"""Everything the sim and the props need for one date, built from rows known before `as_of`.

`Tables` holds the per-game tables in memory (loaded once); `build` cuts them at `as_of` and derives the
rates, projections and league constants. The live slate and the walk-forward backtest both go through here,
so a backtested game sees exactly what a live one would have seen.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from nhl import ids, store
from nhl.features import arena_bias, player_rates, schedule as schedule_spots, team_rates, toi
from nhl.ingest import refs
from nhl.sim import fit

PER_GAME = ("games", "team_game", "team_game_strength", "team_game_score", "player_game_strength", "goalie_game", "officials")
RATE_STATS = ("sog", "hits", "blocks", "ixg", "a1", "a2", "on_xgf")


@dataclass
class Tables:
    frames: dict
    schedule: pd.DataFrame
    players: pd.DataFrame
    spots: pd.DataFrame

    @classmethod
    def load(cls, con, cfg):
        frames = {t: store.read(con, f"SELECT * FROM {t}") for t in PER_GAME}
        sched = store.read(con, "SELECT * FROM schedule")
        return cls(frames, sched, store.read(con, "SELECT * FROM players"), schedule_spots.build(sched, ids.TEAMS, cfg))

    def collapsed(self) -> pd.DataFrame:
        """player_game_strength with ev5 + evo folded into ev, done once."""
        if "_pgs_ev" not in self.frames:
            self.frames["_pgs_ev"] = player_rates.collapse(self.frames["player_game_strength"])
        return self.frames["_pgs_ev"]

    def before(self, name: str, as_of: str) -> pd.DataFrame:
        f = self.frames[name]
        return f[f.known_at < as_of]


def build(tables: Tables, as_of: str, season: int, cfg, lines: pd.DataFrame | None = None, K: dict | None = None) -> dict:
    tgs, tg, games = tables.before("team_game_strength", as_of), tables.before("team_game", as_of), tables.before("games", as_of)
    pgs = tables.collapsed()
    pgs = pgs[(pgs.known_at < as_of) & (pgs.season >= season - 1)]
    gg, offs = tables.before("goalie_game", as_of), tables.before("officials", as_of)
    tr = team_rates.build(tgs, season, cfg)
    pr = player_rates.build(pgs, season, cfg, collapsed=True)
    pp_sec = dict(zip(tr[tr.strength == "pp"].team, tr[tr.strength == "pp"].toi_pg))
    proj = toi.project(pgs, season, cfg, lines, pp_sec, as_of, collapsed=True)
    ab = arena_bias.build(tg, games, tables.schedule[tables.schedule.neutral == 1].game_id, cfg)
    if K is None:
        tot = pgs[["g", "a1", "a2"]].sum()
        K = fit.fit(games, tg, tables.before("team_game_score", as_of), tgs, {"g": float(tot.g), "a1": float(tot.a1), "a2": float(tot.a2)},
                    season, cfg["sim"]["season_goal_prior_xg"])
    cur = pgs[pgs.season == season][["game_id", "team", "player_id", "known_at"]].drop_duplicates(["game_id", "player_id"])
    order = cur.drop_duplicates(["game_id", "team"]).sort_values("known_at")
    recent_games = {t: list(g.game_id.tail(cfg["sim"]["injury_recent_games"])) for t, g in order.groupby("team")}
    return {"as_of": as_of, "season": season, "team_rates": tr, "player_rates": pr, "goalie_rates": player_rates.goalies(gg, season, cfg),
            "toi": proj, "arena": {(r.team, r.stat): r.factor for r in ab.itertuples()}, "ref_rates": refs.ref_rates(offs, tg, cfg),
            "K": K, "appearances": cur, "recent_games": recent_games, "names": dict(zip(tables.players.player_id, tables.players.name)),
            "lines": lines}


def wide_rates(ctx: dict) -> pd.DataFrame:
    if "_wide" not in ctx:
        pr = ctx["player_rates"]
        cols = [f"{s}60" for s in RATE_STATS]
        w = pr.pivot(index="player_id", columns="strength", values=cols)
        w.columns = [f"{c}_{s}" for c, s in w.columns]
        fin = pr.drop_duplicates("player_id").set_index("player_id")[["finishing", "gp"]]
        ctx["_wide"] = w.join(fin).fillna(0.0)
    return ctx["_wide"]


def roster(ctx: dict, team: str, cfg, dressed: set | None = None) -> pd.DataFrame:
    """The skaters priced for one team tonight. `dressed`: the players known to be in (backtest, or lines).
    Without it: tonight's Daily Faceoff lineup when there is one, else whoever played in the team's last games."""
    c = cfg["props"]
    t = ctx["toi"]
    if dressed is not None:
        P = t[t.player_id.isin(dressed)].copy()
    elif t[(t.team == team) & t.in_lineup.notna()].shape[0]:
        P = t[(t.team == team) & (t.in_lineup == 1)].copy()
    else:
        last = ctx["recent_games"].get(team, [])[-c["dress_recent_team_games"]:]
        a = ctx["appearances"]
        seen = set(a[a.game_id.isin(last) & (a.team == team)].player_id)
        P = t[t.player_id.isin(seen) & (t.team == team)].copy()
    P = P[P.total >= c["min_toi_sec"]]
    P["team"] = team
    P = P.merge(wide_rates(ctx), left_on="player_id", right_index=True, how="inner")
    P["name"] = P.player_id.map(ctx["names"]).fillna(P.player_id.astype(str))
    rank = P.groupby("group").ev.rank(ascending=False, method="first")
    P["top_line"] = ((P.group == "F") & (rank <= c["top_line_forwards"])) | ((P.group == "D") & (rank <= c["top_pair_defence"]))
    return P.reset_index(drop=True)


def absent_share(ctx: dict, team: str, dressed_ids: set, cfg) -> dict:
    """Share of the team's expected goals carried by regulars who are not dressed tonight, counting only the part
    of their absence the team's recent games do not already show."""
    games = ctx["recent_games"].get(team, [])
    if not games:
        return {}
    a = ctx["appearances"]
    played = a[a.game_id.isin(games) & (a.team == team)].groupby("player_id").size() / len(games)
    w = wide_rates(ctx)
    t = ctx["toi"].set_index("player_id")
    vol = lambda p: sum(w.at[p, f"ixg60_{s}"] * t.at[p, f"{s}_base"] for s in ("ev", "pp", "pk")) if p in w.index and p in t.index else 0.0
    total = sum(vol(p) * f for p, f in played.items())
    out = [(p, vol(p) * f) for p, f in played.items() if p not in dressed_ids and f >= 0.5]
    out = [(p, v) for p, v in out if v > 0]
    if not out or total <= 0:
        return {}
    return {"share": float(sum(v for _, v in out) / total), "names": [str(ctx["names"].get(p, p)) for p, _ in sorted(out, key=lambda x: -x[1])[:4]]}


def goalie_input(ctx: dict, player_id, name: str | None = None) -> dict | None:
    g = ctx["goalie_rates"]
    if player_id is None or g.empty or player_id not in set(g.player_id):
        lg = float(g.league_xga60.iloc[0]) if len(g) else 2.9
        return {"gsax60": 0.0, "league_xga60": lg, "name": name or "an unrated goalie", "below_min_sample": 1, "starts": 0}
    r = g[g.player_id == player_id].iloc[0]
    return {"gsax60": float(r.gsax60), "league_xga60": float(r.league_xga60), "name": name or ctx["names"].get(player_id, str(player_id)),
            "below_min_sample": int(r.below_min_sample), "starts": int(r.starts), "player_id": int(player_id)}


def spots_for(tables: Tables, game_id: int) -> dict:
    s = tables.spots[tables.spots.game_id == game_id]
    return {r["team"]: r for r in s.to_dict("records")}
