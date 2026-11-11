"""Unit-level matchup tables: run game, target areas, play-calling, pressure and personnel.

Writes to data/cache/:
  unit_games.csv   one row per team per game. Each stat has a value and the play count behind it:
                     run game      inside and outside run EPA, stuffed-run rate, explosive-run rate
                     targets       WR deep, WR short middle (slot area), WR short outside, TE, RB
                     pressure      sacks and QB hits per dropback
                     play-calling  pass rate over expected, deep rate, shotgun, no-huddle, red-zone pass
                                   rate, TE share; from charting since 2022: play-action, motion,
                                   screens, blitzes faced, defenders in the box
  personnel.csv    one row per team per game: how many of the usual five linemen, eleven defenders and
                   top skill players were ruled Out or Doubtful on that week's injury report

Public data does not record who lined up in the slot or which defender covered whom, so "slot" is
measured by where the ball went (short middle) and coverage by what each defence allows there.

Usage: python3 matchups.py     (needs fetch_data.py to have run)
"""
import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd

from features import CACHE, OLD_NAMES, load_games

HERE = Path(__file__).parent
TEAM_FIX = {**OLD_NAMES, "LAR": "LA", "JAC": "JAX", "HST": "HOU", "BLT": "BAL", "CLV": "CLE", "ARZ": "ARI", "SL": "LA"}
COLS = ["game_id", "play_id", "posteam", "play_type", "epa", "qb_dropback", "qb_scramble", "sack", "qb_hit",
        "run_location", "run_gap", "pass_location", "pass_length", "air_yards", "receiver_player_id",
        "pass_oe", "shotgun", "no_huddle", "yardline_100", "yards_gained", "pass_attempt"]
OL, DEF, SKILL = {"T", "G", "C", "OL"}, {"DE", "DT", "NT", "DL", "LB", "CB", "S", "DB"}, {"WR", "TE", "RB", "HB", "FB"}

# stat -> (numerator rows, how to summarise): built below as value + "_n" count columns
UNIT_STATS = ["run_in_epa", "run_out_epa", "stuff_rate", "explosive_run", "wr_deep_epa", "wr_mid_epa", "wr_out_epa",
              "te_epa", "rbrec_epa", "pressure_rate", "proe", "deep_rate", "shotgun_rate", "nohuddle_rate",
              "rz_pass_rate", "te_share", "pa_rate", "motion_rate", "screen_rate", "blitz_rate", "box"]


def norm_name(s: pd.Series) -> pd.Series:
    return s.fillna("").str.lower().str.replace(r"\b(jr|sr|ii|iii|iv)\b", "", regex=True).str.replace(r"[^a-z]", "", regex=True)


def agg(df, value, name):
    """Mean of `value` per team-game, with the number of plays it rests on."""
    g = df.groupby(["game_id", "posteam"])[value].agg(["mean", "size"]).reset_index()
    return g.rename(columns={"mean": name, "size": name + "_n", "posteam": "team"})


def season_units(path: str, pos: pd.DataFrame) -> pd.DataFrame:
    pbp = pd.read_csv(path, usecols=COLS, low_memory=False)
    pbp = pbp[pbp.posteam.notna() & pbp.play_type.isin(["run", "pass"])]
    season = int(re.search(r"(\d{4})", Path(path).name).group(1))
    ftn_path = HERE / f"data/ftn_charting/ftn_charting_{season}.csv"
    if ftn_path.exists():
        ftn = pd.read_csv(ftn_path, usecols=["nflverse_game_id", "nflverse_play_id", "is_motion", "is_play_action",
                                             "is_screen_pass", "n_blitzers", "n_defense_box"])
        pbp = pbp.merge(ftn.rename(columns={"nflverse_game_id": "game_id", "nflverse_play_id": "play_id"}), on=["game_id", "play_id"], how="left")

    runs = pbp[(pbp.play_type == "run") & (pbp.qb_scramble != 1)].copy()
    runs["stuffed"] = (runs.yards_gained <= 0).astype(float)
    runs["explosive"] = (runs.yards_gained >= 10).astype(float)
    inside = runs[(runs.run_gap == "guard") | (runs.run_location == "middle")]
    outside = runs[runs.run_gap.isin(["tackle", "end"])]

    tg = pbp[(pbp.pass_attempt == 1) & pbp.receiver_player_id.notna() & pbp.air_yards.notna()].merge(
        pos, left_on="receiver_player_id", right_on="gsis_id", how="left")
    deep = tg.air_yards >= 15
    wr, te, rb = tg.position == "WR", tg.position == "TE", tg.position.isin(["RB", "FB"])
    tg["is_deep"], tg["is_te"] = deep.astype(float), te.astype(float)

    drop = pbp[pbp.qb_dropback == 1].copy()
    drop["pressured"] = ((drop.sack == 1) | (drop.qb_hit == 1)).astype(float)
    rz = pbp[pbp.yardline_100 <= 20].copy()
    rz["is_pass"] = (rz.qb_dropback == 1).astype(float)

    parts = [
        agg(inside, "epa", "run_in_epa"), agg(outside, "epa", "run_out_epa"),
        agg(runs, "stuffed", "stuff_rate"), agg(runs, "explosive", "explosive_run"),
        agg(tg[wr & deep], "epa", "wr_deep_epa"), agg(tg[wr & ~deep & (tg.pass_location == "middle")], "epa", "wr_mid_epa"),
        agg(tg[wr & ~deep & (tg.pass_location != "middle")], "epa", "wr_out_epa"),
        agg(tg[te], "epa", "te_epa"), agg(tg[rb], "epa", "rbrec_epa"),
        agg(drop, "pressured", "pressure_rate"), agg(pbp[pbp.pass_oe.notna()].assign(p=lambda d: d.pass_oe / 100), "p", "proe"),
        agg(tg, "is_deep", "deep_rate"), agg(pbp, "shotgun", "shotgun_rate"), agg(pbp, "no_huddle", "nohuddle_rate"),
        agg(rz, "is_pass", "rz_pass_rate"), agg(tg, "is_te", "te_share"),
    ]
    if "is_motion" in pbp.columns:
        ch = pbp[pbp.is_motion.notna()].copy()
        chd = ch[ch.qb_dropback == 1].copy()
        chd["blitz"] = (chd.n_blitzers > 0).astype(float)
        for c in ("is_play_action", "is_screen_pass"):
            chd[c] = chd[c].astype(float)
        ch["is_motion"] = ch.is_motion.astype(float)
        parts += [agg(chd, "is_play_action", "pa_rate"), agg(ch, "is_motion", "motion_rate"), agg(chd, "is_screen_pass", "screen_rate"),
                  agg(chd, "blitz", "blitz_rate"), agg(ch[ch.play_type == "run"], "n_defense_box", "box")]
    out = parts[0]
    for p in parts[1:]:
        out = out.merge(p, on=["game_id", "team"], how="outer")
    return out


def personnel_table(sides: pd.DataFrame) -> pd.DataFrame:
    """Starters ruled Out or Doubtful before each game, from the usual players over the prior four games."""
    snaps = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(str(HERE / "data/snap_counts/snap_counts_*.csv")))])
    snaps["team"] = snaps.team.replace(TEAM_FIX)
    snaps["key"] = norm_name(snaps.player)
    inj = pd.concat([pd.read_csv(f, low_memory=False) for f in sorted(glob.glob(str(HERE / "data/injuries/injuries_*.csv")))])
    inj = inj[inj.report_status.isin(["Out", "Doubtful"])].copy()
    inj["team"] = inj.team.replace(TEAM_FIX)
    inj["key"] = norm_name(inj.full_name)
    out_set = {(r.season, r.week, r.team): set() for r in inj[["season", "week", "team"]].drop_duplicates().itertuples()}
    out_names = {}
    for r in inj.itertuples():
        out_set[(r.season, r.week, r.team)].add(r.key)
        out_names[(r.season, r.week, r.team, r.key)] = (r.full_name, r.position)

    snaps["order"] = snaps.season * 100 + snaps.week
    rows = []
    for team, sg in snaps.groupby("team"):
        game_orders = np.sort(sg.order.unique())
        by_order = {o: g for o, g in sg.groupby("order")}
        for s in sides[sides.team == team].itertuples():
            cur = s.season * 100 + s.week
            prior = game_orders[game_orders < cur][-4:]
            if len(prior) < 2:
                continue
            recent = pd.concat([by_order[o] for o in prior])
            def usual(positions, col, k):
                r = recent[recent.position.isin(positions)].groupby("key").agg(snaps=(col, "sum"), name=("player", "first"), pos=("position", "first"))
                return r.sort_values("snaps", ascending=False).head(k)
            ol, de, sk = usual(OL, "offense_snaps", 5), usual(DEF, "defense_snaps", 11), usual(SKILL, "offense_snaps", 5)
            outs = out_set.get((s.season, s.week, team), set())
            last = by_order[prior[-1]]
            last_ol = set(last[last.position.isin(OL)].sort_values("offense_snaps", ascending=False).head(5).key)
            miss = lambda grp: [f"{r['name']} ({r['pos']})" for k, r in grp.iterrows() if k in outs]
            rows.append({"game_id": s.game_id, "team": team,
                         "ol_out": len(miss(ol)), "def_out": len(miss(de)), "skill_out": len(miss(sk)),
                         "ol_continuity": len(last_ol & set(ol.index)) / 5,
                         "ol_out_names": "; ".join(miss(ol)), "def_out_names": "; ".join(miss(de)), "skill_out_names": "; ".join(miss(sk))})
    return pd.DataFrame(rows)


def main():
    pos = pd.read_csv(HERE / "data/players.csv", usecols=["gsis_id", "position"], low_memory=False)
    units = pd.concat([season_units(f, pos) for f in sorted(glob.glob(str(HERE / "data/pbp/play_by_play_*.csv.gz")))])
    for s in UNIT_STATS:
        if s not in units:
            units[s], units[s + "_n"] = np.nan, 0
        units[s + "_n"] = units[s + "_n"].fillna(0)
    CACHE.mkdir(parents=True, exist_ok=True)
    units.round(5).to_csv(CACHE / "unit_games.csv", index=False)

    g = load_games()
    g = g[g.season >= 2015]
    sides = pd.concat([g.assign(team=g.home_team), g.assign(team=g.away_team)])[["game_id", "season", "week", "team"]]
    pers = personnel_table(sides)
    pers.to_csv(CACHE / "personnel.csv", index=False)
    print(f"unit_games {len(units)}, personnel {len(pers)}")
    print(units[UNIT_STATS].describe().round(3).loc[["count", "mean"]].T.to_string())
    print(pers[["ol_out", "def_out", "skill_out", "ol_continuity"]].describe().round(2).loc[["mean", "max"]])
    cur = pers[pers.game_id.str.startswith("2026_10")]
    print(cur[cur.ol_out + cur.def_out + cur.skill_out > 0][["team", "ol_out_names", "def_out_names", "skill_out_names"]].head(8).to_string())


if __name__ == "__main__":
    main()
