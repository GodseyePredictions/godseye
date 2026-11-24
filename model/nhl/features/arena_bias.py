"""Arena scorer bias for hits, blocked shots and shots on goal.

Home scorekeepers log these, and some rinks inflate them. For each rink: what both teams were credited
with per 60 minutes in that team's home games, against what both teams were credited with in the same
team's road games, over the last three seasons. The ratio is shrunk toward 1.00 by the number of home
games and held within +/-25%. The factor applies to both teams in that building.
"""
import pandas as pd


def build(team_game: pd.DataFrame, games: pd.DataFrame, neutral_ids, cfg) -> pd.DataFrame:
    """team_game and games: rows known before the date being priced. One row per (rink's home team, stat)."""
    c = cfg["arena_bias"]
    if team_game.empty:
        return pd.DataFrame(columns=["team", "stat", "home_games", "road_games", "home_per60", "road_per60", "raw", "factor"])
    seasons = sorted(team_game.season.unique())[-c["seasons"]:]
    tg = team_game[team_game.season.isin(seasons) & ~team_game.game_id.isin(set(neutral_ids))]
    both = tg.groupby("game_id")[c["stats"]].sum()                      # both teams' credited events in each game
    g = games.set_index("game_id")[["home", "away", "seconds"]].join(both, how="inner")
    rows = []
    for team in sorted(set(g.home)):
        h, r = g[g.home == team], g[g.away == team]
        for stat in c["stats"]:
            if not len(h) or not len(r) or not r[stat].sum():
                continue
            hp, rp = h[stat].sum() / h.seconds.sum() * 3600, r[stat].sum() / r.seconds.sum() * 3600
            raw = hp / rp
            f = 1 + (raw - 1) * len(h) / (len(h) + c["prior_games"])
            rows.append({"team": team, "stat": stat, "home_games": len(h), "road_games": len(r), "home_per60": round(hp, 3),
                         "road_per60": round(rp, 3), "raw": round(raw, 4),
                         "factor": round(min(1 + c["cap"], max(1 - c["cap"], f)), 4)})
    return pd.DataFrame(rows)
