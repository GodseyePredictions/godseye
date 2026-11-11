"""godseye NFL model v1: margin-based team ratings (Elo family).

Each team carries one rating in points. The expected home margin is
    home_rating - away_rating + home_field + rest_edge
After a game, both ratings move toward the result. Ratings regress to
the league mean between seasons. Everything is computed walk-forward:
a prediction for a game only uses games played before it.
"""
from dataclasses import dataclass
import math
import pandas as pd

SIGMA = 13.5  # typical spread of NFL final margins around the expectation, in points


@dataclass
class Params:
    k: float = 0.06            # share of the prediction error added to ratings
    home_field: float = 1.8    # points
    rest_per_day: float = 0.12 # points per extra day of rest, capped
    carryover: float = 0.62    # share of rating kept between seasons
    blowout_cap: float = 24.0  # margins beyond this teach nothing extra


def win_prob(margin: float, sigma: float = SIGMA) -> float:
    """Chance the home team wins given an expected margin."""
    return 0.5 * (1 + math.erf(margin / (sigma * math.sqrt(2))))


def load_games(path: str) -> pd.DataFrame:
    g = pd.read_csv(path)
    g = g[g["game_type"].notna()].sort_values(["gameday", "game_id"]).reset_index(drop=True)
    return g


def run(games: pd.DataFrame, p: Params = Params()) -> pd.DataFrame:
    """Walk through games in date order; return one row per game with the
    pre-game model margin. Unplayed games get a prediction but no update."""
    ratings: dict[str, float] = {}
    season = None
    rows = []
    for g in games.itertuples(index=False):
        if g.season != season:
            season = g.season
            ratings = {t: r * p.carryover for t, r in ratings.items()}
        h = ratings.setdefault(g.home_team, 0.0)
        a = ratings.setdefault(g.away_team, 0.0)
        hfa = 0.0 if g.location == "Neutral" else p.home_field
        rest = 0.0
        if not (pd.isna(g.home_rest) or pd.isna(g.away_rest)):
            rest = p.rest_per_day * max(-7, min(7, g.home_rest - g.away_rest))
        pred = h - a + hfa + rest
        rows.append({"game_id": g.game_id, "model_margin": pred,
                     "home_rating": h, "away_rating": a})
        if not pd.isna(g.result):
            actual = max(-p.blowout_cap, min(p.blowout_cap, g.result))
            delta = p.k * (actual - pred)
            ratings[g.home_team] = h + delta
            ratings[g.away_team] = a - delta
    return games.merge(pd.DataFrame(rows), on="game_id")
