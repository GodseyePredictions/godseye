"""Data acquisition + loading from nflverse public releases."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.environ.get("ATTD_DATA", Path(__file__).resolve().parent.parent / "data"))
BASE = "https://github.com/nflverse/nflverse-data/releases/download"
SKILL_POS = {"QB", "RB", "FB", "WR", "TE"}

PBP_COLS = [
    "game_id", "season", "week", "season_type", "posteam", "defteam", "home_team", "away_team",
    "play_type", "rush", "pass", "sack", "qb_scramble", "two_point_attempt", "qb_kneel", "qb_spike",
    "rusher_player_id", "receiver_player_id", "passer_player_id",
    "yardline_100", "down", "ydstogo", "goal_to_go", "air_yards", "yards_gained",
    "touchdown", "td_team", "td_player_id", "return_touchdown", "complete_pass", "fixed_drive",
    "play_id", "pass_length", "pass_location", "xpass", "pass_oe", "shotgun", "no_huddle",
    "yards_after_catch", "weather", "temp", "wind", "roof", "surface", "qb_dropback",
    "posteam_score", "defteam_score", "score_differential", "home_score", "away_score",
    "penalty", "penalty_team", "penalty_yards", "punt_attempt", "field_goal_attempt", "third_down_converted",
    "third_down_failed", "fixed_drive_result", "drive_time_of_possession", "drive_play_count",
]


def _files(seasons):
    for y in seasons:
        yield f"pbp/play_by_play_{y}.parquet", f"pbp_{y}.parquet"
        yield f"weekly_rosters/roster_weekly_{y}.parquet", f"roster_{y}.parquet"
        yield f"snap_counts/snap_counts_{y}.parquet", f"snaps_{y}.parquet"
        yield f"injuries/injuries_{y}.parquet", f"inj_{y}.parquet"
        yield f"stats_player/stats_player_week_{y}.parquet", f"stats_week_{y}.parquet"
        if y >= 2022:
            yield f"ftn_charting/ftn_charting_{y}.parquet", f"ftn_{y}.parquet"
    yield "schedules/games.csv", "schedules.csv"


def download(seasons, force_current: int | None = None):
    """Download nflverse files. Always re-pulls the current season + schedules (they change weekly)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for remote, local in _files(seasons):
        dest = DATA_DIR / local
        stale = force_current is not None and (str(force_current) in local or local == "schedules.csv")
        if dest.exists() and not stale:
            continue
        print(f"  downloading {remote}")
        subprocess.run(["curl", "-sSfL", "-o", str(dest), f"{BASE}/{remote}"], check=False)


def _read_many(prefix, seasons, cols=None):
    out = []
    for y in seasons:
        f = DATA_DIR / f"{prefix}_{y}.parquet"
        if f.exists():
            out.append(pd.read_parquet(f, columns=cols))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def load_pbp(seasons):
    p = _read_many("pbp", seasons, PBP_COLS)
    return p[p.season_type.isin(["REG", "POST"])].reset_index(drop=True)


def load_rosters(seasons):
    return _read_many("roster", seasons)


def load_snaps(seasons):
    return _read_many("snaps", seasons)


def load_injuries(seasons):
    return _read_many("inj", seasons)


def load_ftn(seasons):
    return _read_many("ftn", seasons, ["nflverse_game_id", "nflverse_play_id", "n_defense_box", "is_motion",
                                       "is_play_action", "is_screen_pass", "is_rpo", "n_blitzers",
                                       "n_pass_rushers", "is_qb_out_of_pocket"])


STAT_MAP = {"carries": "carries", "rushing_yards": "rush_yds", "receptions": "rec", "targets": "tgt",
            "receiving_yards": "rec_yds", "attempts": "pass_att", "completions": "pass_cmp",
            "passing_yards": "pass_yds", "passing_tds": "pass_td", "passing_interceptions": "ints"}


def load_official_stats(seasons):
    """Official per-game box-score lines (what books settle on), keyed (game_id, player_id)."""
    s = _read_many("stats_week", seasons, ["player_id", "game_id", "season", "week"] + list(STAT_MAP))
    return s.rename(columns=STAT_MAP).drop(columns=["season", "week"]).drop_duplicates(["game_id", "player_id"])


def load_coordinators():
    """Optional user-maintained file data/coordinators.csv with columns season,team,oc,dc.
    When present, scheme tendencies follow the coordinator (across teams, reset on a change)."""
    f = DATA_DIR / "coordinators.csv"
    return pd.read_csv(f) if f.exists() else None


def load_schedules():
    s = pd.read_csv(DATA_DIR / "schedules.csv", low_memory=False)
    return s[s.game_type.isin(["REG", "WC", "DIV", "CON", "SB"])]


def id_map(rosters: pd.DataFrame) -> pd.DataFrame:
    """pfr_id -> gsis_id lookup (snap counts are keyed on PFR ids)."""
    m = rosters.dropna(subset=["pfr_id", "gsis_id"])[["pfr_id", "gsis_id"]].drop_duplicates("pfr_id")
    return m
