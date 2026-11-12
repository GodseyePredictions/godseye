"""SQLite storage for the NBA module, with point-in-time reads.

Every table carries the moment each row became known (`known_at`, UTC). Game results become
known when the game ends. `PointInTime(as_of)` hands back only rows known strictly before
`as_of`, so a feature built for a game can be asked "what did we know before tip-off" and get
exactly that. All model code reads through PointInTime; nothing reads the tables directly.
"""
import sqlite3
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DB = HERE / "data" / "nba.sqlite"
RAW = HERE / "data" / "raw"

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
  game_id TEXT PRIMARY KEY, season INTEGER, date_et TEXT, tip_utc TEXT, known_at TEXT,
  home_id TEXT, away_id TEXT, home TEXT, away TEXT, venue TEXT, neutral INTEGER, completed INTEGER,
  home_pts INTEGER, away_pts INTEGER, periods INTEGER,
  hq1 INTEGER, hq2 INTEGER, hq3 INTEGER, hq4 INTEGER, aq1 INTEGER, aq2 INTEGER, aq3 INTEGER, aq4 INTEGER,
  max_lead_2h_home INTEGER, max_lead_2h_away INTEGER, close_last5 INTEGER);
CREATE TABLE IF NOT EXISTS player_games (
  game_id TEXT, team_id TEXT, player_id TEXT, name TEXT, pos TEXT, starter INTEGER, dnp INTEGER, reason TEXT,
  min REAL, pts INTEGER, reb INTEGER, oreb INTEGER, dreb INTEGER, ast INTEGER, stl INTEGER, blk INTEGER,
  tov INTEGER, pf INTEGER, fgm INTEGER, fga INTEGER, fg3m INTEGER, fg3a INTEGER, ftm INTEGER, fta INTEGER,
  rim_a INTEGER, rim_m INTEGER, mid_a INTEGER, mid_m INTEGER, c3_a INTEGER, c3_m INTEGER, ab3_a INTEGER, ab3_m INTEGER,
  sec_q1 REAL, sec_q2 REAL, sec_q3 REAL, sec_q4 REAL, sec_ot REAL, q4_fga INTEGER, q4_pts INTEGER,
  known_at TEXT, PRIMARY KEY (game_id, player_id));
CREATE TABLE IF NOT EXISTS officials (game_id TEXT, name TEXT, known_at TEXT, PRIMARY KEY (game_id, name));
CREATE TABLE IF NOT EXISTS injury_reports (
  report_utc TEXT, game_date TEXT, matchup TEXT, team TEXT, player_name TEXT, status TEXT, reason TEXT,
  player_id TEXT, PRIMARY KEY (report_utc, team, player_name));
CREATE TABLE IF NOT EXISTS starters (game_id TEXT, team_id TEXT, player_id TEXT, source TEXT, known_at TEXT,
  PRIMARY KEY (game_id, player_id, source));
CREATE TABLE IF NOT EXISTS ref_assignments (date_et TEXT, matchup TEXT, name TEXT, role TEXT, known_at TEXT,
  PRIMARY KEY (date_et, matchup, name));
CREATE TABLE IF NOT EXISTS market_lines (game_id TEXT, known_at TEXT, provider TEXT, spread_home REAL, total REAL,
  ml_home REAL, ml_away REAL, PRIMARY KEY (game_id, known_at, provider));
CREATE TABLE IF NOT EXISTS odds (
  known_at TEXT, source TEXT, book TEXT, game_id TEXT, market TEXT, player_id TEXT, player_name TEXT,
  side TEXT, line REAL, price REAL, is_close INTEGER DEFAULT 0,
  PRIMARY KEY (known_at, source, book, game_id, market, player_name, side, line));
CREATE TABLE IF NOT EXISTS availability (
  game_id TEXT, player_id TEXT, team_id TEXT, status TEXT, reason TEXT, minutes_restriction REAL,
  games_since_return INTEGER, games_missed INTEGER, source_time TEXT, known_at TEXT,
  PRIMARY KEY (game_id, player_id, known_at));
CREATE TABLE IF NOT EXISTS schedule (game_id TEXT PRIMARY KEY, season INTEGER, date_et TEXT, tip_utc TEXT,
  home_id TEXT, away_id TEXT, home TEXT, away TEXT, venue TEXT, neutral INTEGER);
CREATE INDEX IF NOT EXISTS pg_player ON player_games(player_id);
"""

TIMED = {"games": "known_at", "player_games": "known_at", "officials": "known_at", "injury_reports": "report_utc",
         "starters": "known_at", "ref_assignments": "known_at", "market_lines": "known_at", "odds": "known_at",
         "availability": "known_at"}


def connect(path: Path = DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def upsert(con: sqlite3.Connection, table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = list(rows[0].keys())
    sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
    plain = lambda v: v.item() if hasattr(v, "item") else v        # numpy numbers would be stored as raw bytes
    con.executemany(sql, [[plain(r.get(c)) for c in cols] for r in rows])
    con.commit()
    return len(rows)


class PointInTime:
    """A read-only view of the data as it stood just before `as_of` (ISO UTC time).

    Tables can come from the database or from data frames already in memory (the backtest
    loads once and slices many times). Either way the same rule applies: known_at < as_of.
    """

    def __init__(self, as_of: str, con: sqlite3.Connection | None = None, frames: dict | None = None):
        self.as_of = as_of
        self._con, self._frames = con, frames or {}

    def table(self, name: str) -> pd.DataFrame:
        col = TIMED.get(name)
        if name in self._frames:
            df = self._frames[name]
            return df if col is None else df[df[col] < self.as_of]
        if col is None:
            return pd.read_sql(f"SELECT * FROM {name}", self._con)
        return pd.read_sql(f"SELECT * FROM {name} WHERE {col} < ?", self._con, params=[self.as_of])


def load_frames(con: sqlite3.Connection, names=("games", "player_games", "officials", "injury_reports",
                                                   "market_lines", "schedule")) -> dict:
    return {n: pd.read_sql(f"SELECT * FROM {n}", con) for n in names}
