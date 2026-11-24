"""Team defence by position for a season to date (box scores + play-by-play YAC). Ranks use the normal convention:
1 = best defence (fewest allowed). EXPERIMENTAL context for the matchup-read comparison; see FACTORS.md for the
backtest (passing-side splits lose ~80% of their gap week to week, TDs by position carry nothing, run defence ~40%)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DATA_DIR


def team_defense(season: int, before_week: int) -> pd.DataFrame:
    sw = pd.read_parquet(DATA_DIR / f"stats_week_{season}.parquet")
    sw = sw[(sw.season_type == "REG") & (sw.week < before_week)].copy()
    G = sw.groupby("opponent_team").week.nunique()
    out = pd.DataFrame({"g": G})

    def per_game(pos, cols):
        x = sw[sw.position == pos].groupby("opponent_team")[list(cols.values())].sum()
        return x.rename(columns={v: k for k, v in cols.items()}).div(G, axis=0)

    wr = per_game("WR", {"wr_rec": "receptions", "wr_yds": "receiving_yards", "wr_td": "receiving_tds", "wr_tgt": "targets"})
    te = per_game("TE", {"te_rec": "receptions", "te_yds": "receiving_yards", "te_td": "receiving_tds", "te_tgt": "targets"})
    rb = per_game("RB", {"rb_rec": "receptions", "rb_recyds": "receiving_yards", "rb_car": "carries", "rb_rush": "rushing_yards",
                         "rb_rushtd": "rushing_tds", "rb_rectd": "receiving_tds"})
    out = out.join([wr, te, rb])
    out["wr_ypr"] = out.wr_yds / out.wr_rec; out["te_ypr"] = out.te_yds / out.te_rec; out["rb_ypr"] = out.rb_recyds / out.rb_rec
    out["rb_ypc"] = out.rb_rush / out.rb_car
    q = sw.groupby("opponent_team").agg(att=("attempts", "sum"), pyds=("passing_yards", "sum"), ptd=("passing_tds", "sum"),
                                        ints=("passing_interceptions", "sum"), sacks=("sacks_suffered", "sum"))
    out["pass_att"] = q.att / G; out["pass_yds"] = q.pyds / G; out["pass_td"] = q.ptd / G
    out["ypa"] = q.pyds / q.att; out["sack_rate"] = q.sacks / (q.att + q.sacks); out["int_rate"] = q.ints / q.att
    qb = sw[sw.position == "QB"].groupby("opponent_team").rushing_tds.sum() / G
    out["qb_rushtd"] = qb
    # yards after catch by position from play-by-play
    try:
        pb = pd.read_parquet(DATA_DIR / f"pbp_{season}.parquet", columns=["season_type", "week", "defteam", "complete_pass", "receiver_player_id", "yards_after_catch"])
        pb = pb[(pb.season_type == "REG") & (pb.week < before_week) & (pb.complete_pass == 1)]
        pos = pd.read_parquet(DATA_DIR / f"roster_{season}.parquet", columns=["gsis_id", "position"]).dropna().drop_duplicates("gsis_id").set_index("gsis_id").position
        pb["pos"] = pb.receiver_player_id.map(pos).replace({"FB": "RB"})
        y = pb[pb.pos.isin(["WR", "TE", "RB"])].groupby(["defteam", "pos"]).yards_after_catch.sum().unstack().div(G, axis=0)
        out["wr_yac"] = y.get("WR"); out["te_yac"] = y.get("TE"); out["rb_yac"] = y.get("RB")
    except Exception as e:  # noqa: BLE001
        print("  [defense yac]", e)
    higher_is_better = {"sack_rate", "int_rate"}
    for c in [c for c in out.columns if c != "g"]:
        out["r_" + c] = out[c].rank(ascending=c not in higher_is_better, method="min").astype("Int64")
    return out


def summary(D: pd.DataFrame, team: str) -> list[str]:
    """Plain-language lines for one defence. Soft = bottom eight, stingy = top eight."""
    r = D.loc[team]; n = len(D)
    def tag(rank): return "stingy" if rank <= 8 else "soft" if rank >= n - 7 else "average"
    o = lambda k: f"{int(r['r_' + k])}{'th' if 10 <= int(r['r_' + k]) % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(int(r['r_' + k]) % 10, 'th')}"  # noqa: E731
    return [
        f"<b>Run defence ({tag(r.r_rb_rush)}):</b> {r.rb_rush:.0f} rush yds a game to backs ({o('rb_rush')}), {r.rb_ypc:.2f} a carry ({o('rb_ypc')}), {r.rb_rushtd:.2f} rushing TDs a game ({o('rb_rushtd')}).",
        f"<b>vs receivers ({tag(r.r_wr_yds)}):</b> {r.wr_rec:.1f} catches ({o('wr_rec')}) and {r.wr_yds:.0f} yds a game ({o('wr_yds')}), {r.wr_ypr:.1f} a catch ({o('wr_ypr')}), {r.wr_yac:.0f} YAC ({o('wr_yac')}), {r.wr_td:.2f} TDs ({o('wr_td')}).",
        f"<b>vs tight ends ({tag(r.r_te_yds)}):</b> {r.te_rec:.1f} catches ({o('te_rec')}) and {r.te_yds:.0f} yds ({o('te_yds')}), {r.te_td:.2f} TDs ({o('te_td')}).",
        f"<b>vs backs receiving ({tag(r.r_rb_recyds)}):</b> {r.rb_rec:.1f} catches ({o('rb_rec')}) and {r.rb_recyds:.0f} yds ({o('rb_recyds')}), {r.rb_ypr:.1f} a catch ({o('rb_ypr')}).",
        f"<b>Pass defence:</b> {r.pass_yds:.0f} yds a game ({o('pass_yds')}), {r.ypa:.2f} an attempt ({o('ypa')}), sack rate {r.sack_rate:.1%} ({o('sack_rate')}), interception rate {r.int_rate:.1%} ({o('int_rate')}), {r.pass_att:.0f} attempts faced ({o('pass_att')}).",
    ]
