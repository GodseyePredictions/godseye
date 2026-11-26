"""Saved responses (trimmed) for the parsers and a small made-up league for the features. No network."""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nhl import store  # noqa: E402
from nhl.config import copy_config  # noqa: E402
from nhl.features import game_logs  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
TEAMS = ["NYR", "NJD", "BOS", "MTL", "LAK", "VAN"]


def fixture_json(name):
    return json.loads((FIX / name).read_text())


def fixture_text(name):
    return (FIX / name).read_text()


def paper_config():
    """The engine with paper ladders: most tests check the maths, not the book."""
    c = copy_config()
    c["gates"]["require_book_rung"] = False
    return c


@pytest.fixture
def cfg():
    return paper_config()


def roster_for(team, k):
    """Nine forwards (three lines), four defence (two pairs), one goalie. Ids: team number, then slot."""
    r = {}
    for j in range(14):
        pos = "C" if j < 9 else ("D" if j < 13 else "G")
        r[k * 100 + j] = {"team": team, "pos": pos, "name": f"{team} Skater{j}"}
    return r


def make_game(gid, day, home, away, rng, *, penalty=True, hit_boost=None, shooter_boost=None, seconds=3600):
    """A parsed game plus its shift chart and MoneyPuck-style shots. Lines roll every 40 seconds, pairs every 60.
    With `penalty`, the away side is a man short from 600 to 720, so the home side has exactly 120 seconds of power play."""
    kh, ka = TEAMS.index(home) + 1, TEAMS.index(away) + 1
    roster = roster_for(home, kh) | roster_for(away, ka)
    shifts, events, shots = [], [], []
    for k, team in ((kh, home), (ka, away)):
        shifts.append((k * 100 + 13, 0, seconds))
        for t in range(0, seconds, 40):
            line = (t // 40) % 3
            for j in range(3):
                pid = k * 100 + line * 3 + j
                if penalty and team == away and j == 2 and t < 720 and t + 40 > 600:
                    for a, b in ((t, min(t + 40, 600)), (max(t, 720), t + 40)):
                        if b > a:
                            shifts.append((pid, a, b))
                    continue
                shifts.append((pid, t, min(t + 40, seconds)))
        for t in range(0, seconds, 60):
            pair = (t // 60) % 2
            for j in range(2):
                shifts.append((k * 100 + 9 + pair * 2 + j, t, min(t + 60, seconds)))
    if penalty:
        events.append({"sec": 600, "period": 1, "type": "penalty", "team": away, "code": "1551", "by": ka * 100 + 2,
                       "drawn": kh * 100, "pen_type": "MIN", "desc": "tripping", "minutes": 2})
    goals = {home: 0, away: 0}
    for t in range(20, seconds, 20):
        for k, team, opp_k in ((kh, home, ka), (ka, away, kh)):
            line = (t - 1) // 40 % 3
            shooter = k * 100 + line * 3 + int(rng.integers(0, 2))
            per = min(t // 1200 + 1, 3)
            p_shot = 0.45 * (shooter_boost or {}).get(team, 1.0)
            if rng.random() < p_shot:
                kind = rng.choice(["shot-on-goal", "missed-shot", "blocked-shot", "goal"], p=[0.5, 0.22, 0.24, 0.04])
                ev = {"sec": t, "period": per, "type": str(kind), "team": team, "code": "1551", "shooter": shooter,
                      "goalie": opp_k * 100 + 13 if kind in ("shot-on-goal", "goal") else None,
                      "blocker": opp_k * 100 + 9 + ((t - 1) // 60 % 2) * 2 if kind == "blocked-shot" else None, "a1": None, "a2": None}
                if kind == "goal":
                    goals[team] += 1
                    ev["a1"] = k * 100 + line * 3 + 2
                events.append(ev)
                if kind != "blocked-shot":
                    shots.append({"game_id": gid, "season": day.year if day.month > 7 else day.year - 1, "sec": t, "period": per,
                                  "is_home": int(team == home), "shooter_id": shooter, "goalie_id": opp_k * 100 + 13,
                                  "xg": 0.25 if kind == "goal" else 0.06, "goal": int(kind == "goal"),
                                  "on_goal": int(kind != "missed-shot"), "empty_net": 0})
            if rng.random() < 0.25 * (hit_boost or 1.0):
                events.append({"sec": t, "period": per, "type": "hit", "team": team, "code": "1551", "hitter": k * 100 + line * 3})
    if goals[home] == goals[away]:
        goals[home] += 1
        events.append({"sec": seconds - 5, "period": 3, "type": "goal", "team": home, "code": "1551", "shooter": kh * 100 + 6,
                       "goalie": ka * 100 + 13, "blocker": None, "a1": None, "a2": None})
    start = datetime(day.year, day.month, day.day, 23, 0, tzinfo=timezone.utc)
    game = {"game_id": gid, "season": day.year if day.month > 7 else day.year - 1, "date_et": day.isoformat(),
            "start_utc": start.isoformat().replace("+00:00", "Z"), "state": "OFF", "home": home, "away": away,
            "home_goals": goals[home], "away_goals": goals[away], "venue": f"{home} Arena", "decided": "REG", "seconds": seconds,
            "roster": roster, "events": sorted(events, key=lambda e: e["sec"])}
    return game, shifts, pd.DataFrame(shots)


def make_league(cfg, seasons=(2025, 2026), rounds=10, seed=1, loud_rink="VAN", loud=1.6):
    """Every team hosts every other once per round-robin pass. `loud_rink` credits 60% more hits to both sides."""
    rng = np.random.default_rng(seed)
    tables = {t: [] for t in ("games", "team_game", "team_game_strength", "team_game_score", "player_game_strength", "goalie_game")}
    sched, officials = [], []
    gid = 0
    for season in seasons:
        day = date(season, 10, 8)
        for r in range(rounds):
            order = list(rng.permutation(TEAMS))
            for home, away in zip(order[:3], order[3:]):
                gid += 1
                g_id = season * 1_000_000 + 20000 + gid
                game, shifts, shots = make_game(g_id, day, home, away, rng, hit_boost=loud if home == loud_rink else None)
                out = game_logs.build_game(game, shifts, shots, {}, cfg)
                for t in tables:
                    tables[t] += out[t]
                sched.append({"game_id": g_id, "season": season, "game_type": 2, "date_et": day.isoformat(),
                              "start_utc": game["start_utc"], "home": home, "away": away, "home_id": 0, "away_id": 0,
                              "venue": game["venue"], "venue_utc_offset": -8.0 if home in ("LAK", "VAN") else -5.0, "neutral": 0,
                              "state": "OFF"})
                known = out["games"][0]["known_at"]
                for name in (f"Ref {gid % 4}", f"Ref {(gid + 1) % 4}"):
                    officials.append({"game_id": g_id, "name": name, "role": "referee", "date_et": day.isoformat(), "known_at": known})
            day += timedelta(days=2 if r % 3 else 1)
    return {k: pd.DataFrame(v) for k, v in tables.items()} | {"schedule": pd.DataFrame(sched), "officials": pd.DataFrame(officials)}


@pytest.fixture(scope="session")
def league():
    return make_league(copy_config())


@pytest.fixture
def db(league):
    con = store.connect(":memory:")
    for name, df in league.items():
        store.write(con, name, df.astype(object).where(df.notna(), None).to_dict("records"))
    return con
