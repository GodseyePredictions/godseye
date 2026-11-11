"""A small made-up league for the tests: 6 teams, 2 seasons, real table shapes. No network, no database file."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nba.config import CONFIG  # noqa: E402

ABBR = ["BOS", "NY", "LAL", "DEN", "MIA", "CHI"]
POSN = ["G", "G", "F", "F", "C", "G", "F", "C", "G", "F"]


def make_league(seed=0, games_per_season=22, seasons=(2025, 2026)):
    rng = np.random.default_rng(seed)
    teams = {a: str(i + 1) for i, a in enumerate(ABBR)}
    players = []
    for a in ABBR:
        for k in range(10):
            players.append({"player_id": f"{teams[a]}{k:02d}", "name": f"{a} Player{k}", "team": a, "pos": POSN[k],
                            "mins": [34, 33, 32, 30, 29, 22, 18, 15, 12, 8][k], "use": rng.uniform(0.25, 0.6)})
    games, sched, pg = [], [], []
    gid = 1000
    for season in seasons:
        day = datetime(season - 1, 10, 22, 23, 30, tzinfo=timezone.utc)
        for r in range(games_per_season):
            order = rng.permutation(ABBR)
            for h, a in zip(order[:3], order[3:]):
                gid += 1
                tip = day + timedelta(minutes=30 * int(rng.integers(0, 4)))
                g = {"game_id": str(gid), "season": season, "date_et": (tip - timedelta(hours=5)).date().isoformat(),
                     "tip_utc": tip.isoformat(timespec="seconds"), "home_id": teams[h], "away_id": teams[a], "home": h, "away": a,
                     "venue": f"{h} Arena", "neutral": 0}
                sched.append(dict(g))
                q = rng.integers(22, 34, (2, 4))
                box = {}
                for side, t in enumerate((h, a)):
                    roster = [p for p in players if p["team"] == t]
                    sit = set(rng.choice(8, size=int(rng.random() < 0.3), replace=False))
                    for k, p in enumerate(roster):
                        dnp = k in sit
                        m = 0.0 if dnp else float(max(4, p["mins"] + rng.normal(0, 4) + (3 if sit and k < 8 else 0)))
                        fga = 0 if dnp else int(rng.poisson(m * p["use"]))
                        fg3a = int(rng.binomial(fga, 0.38)); fg2a = fga - fg3a
                        fg3m, fg2m = int(rng.binomial(fg3a, 0.36)), int(rng.binomial(fg2a, 0.53))
                        fta = 0 if dnp else int(rng.poisson(m * 0.08)); ftm = int(rng.binomial(fta, 0.78))
                        rim = int(rng.binomial(fg2a, 0.55)); c3 = int(rng.binomial(fg3a, 0.25))
                        oreb, dreb = (0, 0) if dnp else (int(rng.poisson(m * 0.03)), int(rng.poisson(m * 0.11)))
                        q4 = 0.0 if dnp else m * 60 * 0.25
                        pg.append({"game_id": str(gid), "team_id": teams[t], "player_id": p["player_id"], "name": p["name"],
                                   "pos": p["pos"], "starter": int(k < 5 and not dnp), "dnp": int(dnp), "reason": None,
                                   "min": round(m), "pts": 2 * fg2m + 3 * fg3m + ftm, "reb": oreb + dreb, "oreb": oreb, "dreb": dreb,
                                   "ast": 0 if dnp else int(rng.poisson(m * 0.1)), "stl": 0 if dnp else int(rng.poisson(m * 0.03)),
                                   "blk": 0 if dnp else int(rng.poisson(m * 0.02)), "tov": 0 if dnp else int(rng.poisson(m * 0.05)),
                                   "pf": 0 if dnp else int(rng.poisson(m * 0.08)), "fgm": fg2m + fg3m, "fga": fga, "fg3m": fg3m,
                                   "fg3a": fg3a, "ftm": ftm, "fta": fta, "rim_a": rim, "rim_m": int(rng.binomial(rim, 0.64)),
                                   "mid_a": fg2a - rim, "mid_m": 0, "c3_a": c3, "c3_m": 0, "ab3_a": fg3a - c3, "ab3_m": 0,
                                   "sec_q1": q4, "sec_q2": q4, "sec_q3": q4, "sec_q4": q4, "sec_ot": 0.0,
                                   "q4_fga": int(fga * 0.25), "q4_pts": 0, "known_at": None})
                    box[side] = sum(x["pts"] for x in pg if x["game_id"] == str(gid) and x["team_id"] == teams[t])
                end = (tip + timedelta(hours=2, minutes=20)).isoformat(timespec="seconds")
                for x in pg[-20:]:
                    x["known_at"] = end
                hq = [box[0] // 4] * 3 + [box[0] - 3 * (box[0] // 4)]
                aq = [box[1] // 4] * 3 + [box[1] - 3 * (box[1] // 4)]
                if box[0] == box[1]:
                    box[0] += 1; hq[3] += 1
                games.append({**g, "known_at": end, "completed": 1, "home_pts": box[0], "away_pts": box[1], "periods": 4,
                              "hq1": hq[0], "hq2": hq[1], "hq3": hq[2], "hq4": hq[3], "aq1": aq[0], "aq2": aq[1], "aq3": aq[2], "aq4": aq[3],
                              "max_lead_2h_home": max(0, box[0] - box[1]), "max_lead_2h_away": max(0, box[1] - box[0]),
                              "close_last5": int(abs(box[0] - box[1]) <= 5)})
            day += timedelta(days=2)
    G = pd.DataFrame(games)
    officials = pd.DataFrame([{"game_id": g, "name": f"Ref {i % 7}", "known_at": t} for i, (g, t) in enumerate(zip(G.game_id, G.tip_utc))])
    inj = pd.DataFrame(columns=["report_utc", "game_date", "matchup", "team", "player_name", "status", "reason", "player_id"])
    return {"games": G, "player_games": pd.DataFrame(pg), "schedule": pd.DataFrame(sched), "officials": officials,
            "injury_reports": inj, "market_lines": pd.DataFrame(columns=["game_id", "known_at", "provider", "spread_home", "total", "ml_home", "ml_away"])}


@pytest.fixture(scope="session")
def league():
    return make_league()


@pytest.fixture(scope="session")
def pipe(league):
    from nba.pipeline import Pipeline
    p = Pipeline(league, cfg=CONFIG)
    p.fit(2026)
    return p


@pytest.fixture(scope="session")
def simmed(pipe):
    gid = pipe.G[pipe.G.season == 2026].sort_values("tip").game_id.iloc[30]
    return pipe.run_game(gid, pipe.models[2026], 1500)
