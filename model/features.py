"""Turn raw play-by-play into the small tables the game-market models read.

Writes to data/cache/:
  team_games.csv   one row per team per game: efficiency, pace, possession, turnovers, penalties
  qb_games.csv     one row per starting quarterback per game: dropbacks, EPA, interceptions
  skill_games.csv  one row per skill player per game with a real role: scored a TD or not

Usage: python3 features.py     (needs data from fetch_data.py; takes a few minutes)
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
CACHE = HERE / "data" / "cache"
ST_PLAYS = {"kickoff", "punt", "extra_point", "field_goal"}
OLD_NAMES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}  # games.csv keeps old abbreviations; play-by-play does not

COLS = ["game_id", "season", "week", "home_team", "away_team", "posteam", "defteam", "play_type",
        "epa", "success", "qb_dropback", "interception", "sack", "fumble_lost", "passer_player_id",
        "rusher_player_id", "receiver_player_id", "td_player_id", "touchdown", "rush_attempt", "pass_attempt",
        "fixed_drive", "drive_time_of_possession", "special_teams_play", "penalty", "penalty_team", "penalty_yards",
        "complete_pass", "rushing_yards", "receiving_yards", "passing_yards"]


def load_games() -> pd.DataFrame:
    g = pd.read_csv(HERE / "data/games.csv")
    for c in ("home_team", "away_team"):
        g[c] = g[c].replace(OLD_NAMES)
    return g


def season_tables(path: str):
    pbp = pd.read_csv(path, usecols=COLS, low_memory=False)
    pbp = pbp[pbp.posteam.notna()]
    scrim = pbp[pbp.play_type.isin(["run", "pass"])]
    drop = scrim[scrim.qb_dropback == 1]

    key = ["game_id", "posteam"]
    t = scrim.groupby(key).agg(plays=("epa", "size"), off_epa=("epa", "mean"), success=("success", "mean"),
                               fumbles_lost=("fumble_lost", "sum")).reset_index()
    d = drop.groupby(key).agg(dropbacks=("epa", "size"), pass_epa=("epa", "mean"),
                              ints=("interception", "sum"), sacks=("sack", "sum")).reset_index()
    r = scrim[scrim.qb_dropback != 1].groupby(key).agg(rushes=("epa", "size"), rush_epa=("epa", "mean")).reset_index()

    drives = pbp.dropna(subset=["drive_time_of_possession"]).drop_duplicates(["game_id", "posteam", "fixed_drive"]).copy()
    parts = drives.drive_time_of_possession.str.split(":", expand=True).astype(float)
    drives["sec"] = parts[0] * 60 + parts[1]
    top = drives.groupby(key).agg(top_sec=("sec", "sum"), drives=("sec", "size")).reset_index()

    pen = pbp[(pbp.penalty == 1) & pbp.penalty_team.notna()].copy()
    special = (pen.special_teams_play == 1) | pen.play_type.isin(ST_PLAYS)
    pen["phase"] = np.where(special, "st", np.where(pen.penalty_team == pen.posteam, "off", "def"))
    pc = pen[pen.phase != "st"].groupby(["game_id", "penalty_team", "phase"]).agg(
        n=("penalty", "size"), yds=("penalty_yards", "sum")).unstack("phase", fill_value=0)
    pc.columns = [f"{ph}_pen" if k == "n" else f"{ph}_pen_yds" for k, ph in pc.columns]
    pc = pc.reset_index().rename(columns={"penalty_team": "posteam"})

    team = t.merge(d, on=key, how="left").merge(r, on=key, how="left").merge(top, on=key, how="left").merge(pc, on=key, how="left")
    team = team.rename(columns={"posteam": "team"})

    # Quarterbacks: every passer's dropbacks in the game (the starter is picked later from games.csv)
    qb = drop.dropna(subset=["passer_player_id"]).groupby(["game_id", "posteam", "passer_player_id"]).agg(
        dropbacks=("epa", "size"), epa=("epa", "sum"), ints=("interception", "sum")).reset_index()
    qb = qb.rename(columns={"posteam": "team", "passer_player_id": "qb_id"})

    # Skill players: opportunities (carries + targets) and whether they scored a rushing or receiving TD
    ru = scrim[scrim.rush_attempt == 1].dropna(subset=["rusher_player_id"]).groupby(
        ["game_id", "posteam", "rusher_player_id"]).size().rename("opps").reset_index().rename(columns={"rusher_player_id": "player_id"})
    re = scrim[scrim.pass_attempt == 1].dropna(subset=["receiver_player_id"]).groupby(
        ["game_id", "posteam", "receiver_player_id"]).size().rename("opps").reset_index().rename(columns={"receiver_player_id": "player_id"})
    opp = pd.concat([ru, re]).groupby(["game_id", "posteam", "player_id"]).opps.sum().reset_index()
    td = scrim[(scrim.touchdown == 1) & scrim.td_player_id.notna() & (scrim.interception != 1) & (scrim.fumble_lost != 1)]
    td = td[(td.td_player_id == td.rusher_player_id) | (td.td_player_id == td.receiver_player_id)]
    tds = td.groupby(["game_id", "posteam", "td_player_id"]).size().rename("tds").reset_index().rename(columns={"td_player_id": "player_id"})
    skill = opp.merge(tds, on=["game_id", "posteam", "player_id"], how="left").fillna({"tds": 0})
    skill = skill.rename(columns={"posteam": "team"})

    # Prop stats per player per game, for measuring how props move with the game result
    rush = scrim[scrim.rush_attempt == 1].dropna(subset=["rusher_player_id"]).groupby(["game_id", "posteam", "rusher_player_id"]).agg(
        carries=("epa", "size"), rush_yds=("rushing_yards", "sum")).reset_index().rename(columns={"rusher_player_id": "player_id"})
    rec = scrim[scrim.pass_attempt == 1].dropna(subset=["receiver_player_id"]).groupby(["game_id", "posteam", "receiver_player_id"]).agg(
        rec=("complete_pass", "sum"), rec_yds=("receiving_yards", "sum")).reset_index().rename(columns={"receiver_player_id": "player_id"})
    pas = scrim[scrim.pass_attempt == 1].dropna(subset=["passer_player_id"]).groupby(["game_id", "posteam", "passer_player_id"]).agg(
        pass_att=("epa", "size"), pass_yds=("passing_yards", "sum")).reset_index().rename(columns={"passer_player_id": "player_id"})
    props = rush.merge(rec, on=["game_id", "posteam", "player_id"], how="outer").merge(pas, on=["game_id", "posteam", "player_id"], how="outer")
    props = props.rename(columns={"posteam": "team"}).fillna(0)
    props["season"] = int(pbp.season.iloc[0])
    return team, qb, skill, props


def main():
    files = sorted(glob.glob(str(HERE / "data/pbp/play_by_play_*.csv.gz")))
    if not files:
        raise SystemExit("No play-by-play files found. Run: python3 fetch_data.py 2015 2026")
    teams, qbs, skills, propss = [], [], [], []
    for f in files:
        t, q, s, pr = season_tables(f)
        teams.append(t); qbs.append(q); skills.append(s); propss.append(pr)
        print(Path(f).name, len(t))
    team, qb, skill = pd.concat(teams), pd.concat(qbs), pd.concat(skills)

    g = load_games()
    g = g[g.result.notna()]
    sides = pd.concat([
        g.assign(team=g.home_team, opp=g.away_team, home=np.where(g.location == "Neutral", 0.5, 1.0),
                 points=g.home_score, points_against=g.away_score, starter_id=g.home_qb_id, rest=g.home_rest),
        g.assign(team=g.away_team, opp=g.home_team, home=np.where(g.location == "Neutral", 0.5, 0.0),
                 points=g.away_score, points_against=g.home_score, starter_id=g.away_qb_id, rest=g.away_rest),
    ])[["game_id", "season", "week", "gameday", "team", "opp", "home", "points", "points_against", "starter_id", "rest"]]
    team = sides.merge(team, on=["game_id", "team"], how="inner")
    for c in ("off_pen", "off_pen_yds", "def_pen", "def_pen_yds"):
        team[c] = team[c].fillna(0)
    team["sec_per_drive"] = team.top_sec / team.drives
    team["sec_per_play"] = team.top_sec / team.plays
    team["int_rate"] = team.ints / team.dropbacks
    team["won"] = (team.points > team.points_against).astype(int)

    starters = sides[["game_id", "team", "starter_id", "season", "week"]].rename(columns={"starter_id": "qb_id"})
    starters = starters[starters.game_id.isin(team.game_id)]
    qb = starters.merge(qb, on=["game_id", "team", "qb_id"], how="left").fillna({"dropbacks": 0, "epa": 0, "ints": 0})

    pos = pd.read_csv(HERE / "data/players.csv", usecols=["gsis_id", "position"], low_memory=False)
    skill = skill.merge(pos.rename(columns={"gsis_id": "player_id"}), on="player_id", how="left")
    skill = skill[skill.position.isin(["RB", "WR", "TE", "QB", "FB"]) & (skill.opps >= 4)]
    skill["position"] = skill.position.replace({"FB": "RB"})
    skill["scored"] = (skill.tds > 0).astype(int)

    CACHE.mkdir(parents=True, exist_ok=True)
    team.round(5).to_csv(CACHE / "team_games.csv", index=False)
    qb.round(4).to_csv(CACHE / "qb_games.csv", index=False)
    skill[["game_id", "team", "player_id", "position", "opps", "scored"]].to_csv(CACHE / "skill_games.csv", index=False)
    props = pd.concat(propss).merge(pos.rename(columns={"gsis_id": "player_id"}), on="player_id", how="left")
    props = props[props.position.isin(["RB", "WR", "TE", "QB"])]
    props.to_csv(CACHE / "prop_games.csv", index=False)
    print(f"team_games {len(team)}, qb_games {len(qb)}, skill_games {len(skill)}")
    print(team[["off_epa", "pass_epa", "rush_epa", "int_rate", "sec_per_play", "plays"]].describe().round(3).loc[["mean", "std"]])


if __name__ == "__main__":
    main()
