"""MoneyPuck: shot-level expected goals (the source of every xG and GSAx number in the engine) and
the season summary files used to spot-check our own tables.

One zip of shots per season (peter-tanner.com hosts MoneyPuck's downloads). Each row is an unblocked
shot attempt with MoneyPuck's xGoal, the shooter, the goalie and the game clock. We aggregate those
ourselves by game, strength state and player, so every rate can be rebuilt as of any date.
"""
import io
import zipfile

import pandas as pd

from common.http import get

SHOTS = "https://peter-tanner.com/moneypuck/downloads/shots_{season}.zip"
SUMMARY = "https://moneypuck.com/moneypuck/playerData/seasonSummary/{season}/regular/{kind}.csv"
COLS = ["season", "game_id", "isPlayoffGame", "period", "time", "isHomeTeam", "shooterPlayerId", "goalieIdForShot",
        "xGoal", "goal", "shotWasOnGoal", "shotOnEmptyNet"]


def parse_shots(zip_bytes: bytes) -> pd.DataFrame:
    """Regular-season shots, keyed by the NHL's game id."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    d = pd.read_csv(z.open(z.namelist()[0]), usecols=COLS)
    d = d[d.isPlayoffGame == 0]
    return pd.DataFrame({
        "game_id": (d.season * 1_000_000 + d.game_id).astype("int64"), "season": d.season.astype(int),
        "sec": d.time.astype(int), "period": d.period.astype(int), "is_home": d.isHomeTeam.astype(int),
        "shooter_id": d.shooterPlayerId.fillna(0).astype("int64"), "goalie_id": d.goalieIdForShot.fillna(0).astype("int64"),
        "xg": d.xGoal.astype(float), "goal": d.goal.astype(int), "on_goal": d.shotWasOnGoal.fillna(0).astype(int),
        "empty_net": d.shotOnEmptyNet.fillna(0).astype(int)})


def shots(season: int, root, cfg, current: bool = False) -> pd.DataFrame:
    url = SHOTS.format(season=season)
    body, _ = get(url, root, min_interval=cfg["sources"]["min_interval"]["peter-tanner.com"], retries=cfg["sources"]["retries"],
                  timeout=180, max_age=cfg["sources"]["moneypuck_max_age_sec"] if current else None)
    return parse_shots(body)


def summary(kind: str, season: int, root, cfg) -> pd.DataFrame:
    """MoneyPuck's own season totals: kind is teams, skaters or goalies. One row per (entity, situation)."""
    body, _ = get(SUMMARY.format(season=season, kind=kind), root, min_interval=cfg["sources"]["min_interval"]["moneypuck.com"],
                  retries=cfg["sources"]["retries"], timeout=120, max_age=cfg["sources"]["moneypuck_max_age_sec"])
    return pd.read_csv(io.BytesIO(body))
