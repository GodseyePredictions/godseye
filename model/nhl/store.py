"""SQLite storage for the NHL engine (nhl/data/nhl.sqlite), with point-in-time reads.

Every per-game table carries `known_at` (UTC): the moment its rows could first have been used.
`before(con, table, as_of)` hands back only rows known strictly before `as_of`, so a rate built
for a game never sees that game or anything after it. Raw responses are kept in nhl/data/raw.
"""
import sqlite3
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DB = HERE / "data" / "nhl.sqlite"
RAW = HERE / "data" / "raw"
MANUAL = HERE / "data" / "manual"
STRENGTHS = ("ev5", "evo", "pp", "pk")   # 5v5; other even strength (4v4, 3v3, empty net); power play; penalty kill

SCHEMA = """
CREATE TABLE IF NOT EXISTS schedule (
  game_id INTEGER PRIMARY KEY, season INTEGER, game_type INTEGER, date_et TEXT, start_utc TEXT, home TEXT, away TEXT,
  home_id INTEGER, away_id INTEGER, venue TEXT, venue_utc_offset REAL, neutral INTEGER, state TEXT);
CREATE TABLE IF NOT EXISTS games (
  game_id INTEGER PRIMARY KEY, season INTEGER, date_et TEXT, start_utc TEXT, known_at TEXT, home TEXT, away TEXT, venue TEXT,
  home_goals INTEGER, away_goals INTEGER, decided TEXT, seconds INTEGER,
  h1 INTEGER, h2 INTEGER, h3 INTEGER, hot INTEGER, a1 INTEGER, a2 INTEGER, a3 INTEGER, aot INTEGER,
  toi_source TEXT, xg_shots INTEGER);
CREATE TABLE IF NOT EXISTS team_game (
  game_id INTEGER, team TEXT, opp TEXT, is_home INTEGER, season INTEGER, date_et TEXT, known_at TEXT, venue TEXT,
  gf INTEGER, ga INTEGER, won INTEGER, decided TEXT, starter_id INTEGER, en_sec INTEGER, en_gf INTEGER, en_ga INTEGER,
  hits INTEGER, blocks INTEGER, sog INTEGER, cf INTEGER, pen_taken REAL, pen_drawn REAL, pim INTEGER,
  PRIMARY KEY (game_id, team));
CREATE TABLE IF NOT EXISTS team_game_strength (
  game_id INTEGER, team TEXT, strength TEXT, season INTEGER, date_et TEXT, known_at TEXT, is_home INTEGER,
  toi INTEGER, gf INTEGER, ga INTEGER, xgf REAL, xga REAL, cf INTEGER, ca INTEGER, ff INTEGER, fa INTEGER,
  sog_f INTEGER, sog_a INTEGER, hdf INTEGER, hda INTEGER, hits_f INTEGER, hits_a INTEGER, blk_f INTEGER, blk_a INTEGER,
  pen_taken REAL, pen_drawn REAL, PRIMARY KEY (game_id, team, strength));
CREATE TABLE IF NOT EXISTS team_game_score (
  game_id INTEGER, team TEXT, scope TEXT, lead INTEGER, season INTEGER, date_et TEXT, known_at TEXT,
  toi INTEGER, cf INTEGER, ca INTEGER, sog_f INTEGER, sog_a INTEGER, hits_f INTEGER, blk_f INTEGER, xgf REAL, xga REAL,
  PRIMARY KEY (game_id, team, scope, lead));
CREATE TABLE IF NOT EXISTS player_game_strength (
  game_id INTEGER, player_id INTEGER, strength TEXT, team TEXT, pos TEXT, season INTEGER, date_et TEXT, known_at TEXT,
  toi INTEGER, g INTEGER, a1 INTEGER, a2 INTEGER, sog INTEGER, icf INTEGER, iff INTEGER, ixg REAL, hits INTEGER,
  blocks INTEGER, pen_taken REAL, pen_drawn REAL, on_xgf REAL, on_xga REAL, on_gf INTEGER, on_ga INTEGER,
  on_cf INTEGER, on_ca INTEGER, PRIMARY KEY (game_id, player_id, strength));
CREATE TABLE IF NOT EXISTS goalie_game (
  game_id INTEGER, player_id INTEGER, team TEXT, season INTEGER, date_et TEXT, known_at TEXT, starter INTEGER,
  relieved INTEGER, toi INTEGER, sa INTEGER, ga INTEGER, saves INTEGER, xga REAL, unblocked INTEGER, xg_ga INTEGER,
  PRIMARY KEY (game_id, player_id));
CREATE TABLE IF NOT EXISTS players (player_id INTEGER PRIMARY KEY, name TEXT, pos TEXT, team TEXT, last_date TEXT);
CREATE TABLE IF NOT EXISTS officials (game_id INTEGER, name TEXT, role TEXT, date_et TEXT, known_at TEXT,
  PRIMARY KEY (game_id, name));
CREATE TABLE IF NOT EXISTS scratches (game_id INTEGER, team TEXT, player_id INTEGER, name TEXT, date_et TEXT, known_at TEXT,
  PRIMARY KEY (game_id, player_id));
CREATE TABLE IF NOT EXISTS toi_official (game_id INTEGER, player_id INTEGER, team TEXT, date_et TEXT, ev INTEGER, pp INTEGER,
  sh INTEGER, total INTEGER, PRIMARY KEY (game_id, player_id));
CREATE TABLE IF NOT EXISTS shots (
  game_id INTEGER, season INTEGER, sec INTEGER, period INTEGER, is_home INTEGER, shooter_id INTEGER, goalie_id INTEGER,
  xg REAL, goal INTEGER, on_goal INTEGER, empty_net INTEGER);
CREATE INDEX IF NOT EXISTS shots_game ON shots(game_id);
CREATE TABLE IF NOT EXISTS goalie_starts (
  date_et TEXT, team TEXT, opp TEXT, is_home INTEGER, goalie TEXT, player_id INTEGER, status TEXT, confirmed INTEGER,
  source_time TEXT, known_at TEXT, PRIMARY KEY (date_et, team, known_at));
CREATE TABLE IF NOT EXISTS lines (
  team TEXT, known_at TEXT, source_time TEXT, player TEXT, player_id INTEGER, unit TEXT, slot TEXT, category TEXT,
  injury TEXT, gtd INTEGER, PRIMARY KEY (team, known_at, unit, slot));
CREATE TABLE IF NOT EXISTS ref_assignments (date_et TEXT, away TEXT, home TEXT, name TEXT, role TEXT, known_at TEXT,
  PRIMARY KEY (date_et, home, name));
CREATE TABLE IF NOT EXISTS odds (
  known_at TEXT, source TEXT, book TEXT, game_id INTEGER, market TEXT, player_id INTEGER, player_name TEXT,
  side TEXT, line REAL, price REAL, is_close INTEGER DEFAULT 0,
  PRIMARY KEY (known_at, source, book, game_id, market, player_name, side, line));
CREATE TABLE IF NOT EXISTS nst (kind TEXT, situation TEXT, entity TEXT, known_at TEXT, data TEXT,
  PRIMARY KEY (kind, situation, entity, known_at));
CREATE INDEX IF NOT EXISTS pgs_player ON player_game_strength(player_id);
CREATE INDEX IF NOT EXISTS pgs_date ON player_game_strength(date_et);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or DB)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    return con


def write(con, table: str, rows: list[dict], *, replace: bool = True) -> int:
    """Insert rows (dicts sharing one set of keys). Rows with an existing primary key are replaced."""
    if not rows:
        return 0
    cols = list(rows[0])
    sql = f"INSERT OR {'REPLACE' if replace else 'IGNORE'} INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
    con.executemany(sql, [[r.get(c) for c in cols] for r in rows])
    con.commit()
    return len(rows)


def read(con, sql: str, params=()) -> pd.DataFrame:
    return pd.read_sql_query(sql, con, params=params)


def before(con, table: str, as_of: str, where: str = "1=1", params=()) -> pd.DataFrame:
    """Rows of a per-game table that were known strictly before `as_of` (UTC ISO time)."""
    return read(con, f"SELECT * FROM {table} WHERE known_at < ? AND {where}", [as_of, *params])
