"""Offensive play-calling (OC) and defensive scheme (DC) tendencies, plus injury-adjusted personnel.

All tendencies are measured from charted play data, then rolled forward with a shifted EWMA so a game's
features only use earlier games.  If data/coordinators.csv (season,team,oc,dc) exists, tendencies are
keyed on the coordinator: they follow him to a new team and reset when a team changes coordinators.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import _shift_ewm

HL = 5.0
DL_POS, LB_POS, DB_POS = {"DE", "DT", "NT", "DL"}, {"LB", "ILB", "OLB", "MLB"}, {"CB", "S", "SS", "FS", "DB"}
OL_POS = {"T", "G", "C", "OT", "OG", "OL"}


def _plays(pbp, ftn):
    p = pbp[pbp.play_type.isin(["run", "pass"]) & (pbp.two_point_attempt != 1) & (pbp.qb_kneel != 1)
            & (pbp.qb_spike != 1)].copy()
    if ftn is not None and len(ftn):
        f = ftn.rename(columns={"nflverse_game_id": "game_id", "nflverse_play_id": "play_id"})
        f["play_id"] = pd.to_numeric(f.play_id, errors="coerce")
        p = p.merge(f.drop_duplicates(["game_id", "play_id"]), on=["game_id", "play_id"], how="left")
    for c in ["n_defense_box", "is_motion", "is_play_action", "is_screen_pass", "is_rpo", "n_blitzers",
              "n_pass_rushers", "is_qb_out_of_pocket"]:
        if c not in p:
            p[c] = np.nan
        p[c] = pd.to_numeric(p[c], errors="coerce").astype(float)
    p["is_pass"] = (p["pass"] == 1).astype(float)
    p["rz"] = p.yardline_100 <= 20
    p["i10"] = p.yardline_100 <= 10
    p["off_td"] = ((p.touchdown == 1) & (p.td_team == p.posteam)).astype(float)
    att = (p["pass"] == 1) & (p.sack != 1) & p.air_yards.notna()
    p["att"] = att.astype(float)
    p["deep"] = np.where(att, (p.air_yards >= 20).astype(float), np.nan)
    p["short"] = np.where(att, (p.air_yards <= 5).astype(float), np.nan)
    p["middle"] = np.where(att, (p.pass_location == "middle").astype(float), np.nan)
    p["air"] = np.where(att, p.air_yards, np.nan)
    p["yac"] = np.where(p.complete_pass == 1, p.yards_after_catch, np.nan)
    p["deep_td"] = np.where(att, ((p.air_yards >= 20) & (p.off_td == 1)).astype(float), np.nan)
    p["blitz"] = np.where(p.qb_dropback == 1, (p.n_blitzers > 0).astype(float), np.nan)
    p["rushers"] = np.where(p.qb_dropback == 1, p.n_pass_rushers, np.nan)
    p["box_run"] = np.where(p.rush == 1, p.n_defense_box, np.nan)
    p["light_box"] = np.where(p.rush == 1, (p.n_defense_box <= 6).astype(float), np.nan)
    p["heavy_box"] = np.where(p.rush == 1, (p.n_defense_box >= 8).astype(float), np.nan)
    p["pa"] = np.where(p.qb_dropback == 1, p.is_play_action, np.nan)
    p["screen"] = np.where(att, p.is_screen_pass, np.nan)
    p["rz_pass"] = np.where(p.rz, p.is_pass, np.nan)
    p["gl_pass"] = np.where(p.i10, p.is_pass, np.nan)
    p["rz_proe"] = np.where(p.rz, p.pass_oe, np.nan)
    # Fix 1/4: script-conditional play calling
    diff = p.posteam_score - p.defteam_score if "posteam_score" in p else pd.Series(np.nan, index=p.index)
    p["trail_pass"] = np.where(diff <= -10, p.is_pass, np.nan)
    p["lead_run"] = np.where(diff >= 10, 1 - p.is_pass, np.nan)
    return p


def _rz_drives(p):
    d = p.groupby(["game_id", "posteam", "defteam", "fixed_drive"]).agg(
        min_yl=("yardline_100", "min"), td=("off_td", "max")).reset_index()
    d = d[d.min_yl <= 20]
    return d.groupby(["game_id", "posteam", "defteam"]).agg(rz_trips=("td", "size"), rz_tds=("td", "sum")) \
        .reset_index()


def _top_seconds(x):
    try:
        m, s = str(x).split(":"); return int(m) * 60 + int(s)
    except Exception:  # noqa: BLE001
        return np.nan


def tempo_penalty_tables(pbp):
    """Per game and team: penalties (offence committed / defence committed), drive stalls after a failed 3rd down
    (punt, field goal), 3rd-down conversion, plays, drives, time of possession, seconds per play.
    Offence keyed (game_id, team); the same numbers 'allowed' keyed (game_id, def_team)."""
    q = pbp[pbp.posteam.notna() & (pbp.posteam != "")].copy()
    live = q.play_type.isin(["run", "pass", "no_play", "punt", "field_goal", "qb_kneel", "qb_spike"])
    q = q[live]
    q["off_pen"] = ((q.penalty == 1) & (q.penalty_team == q.posteam)).astype(float)
    q["def_pen"] = ((q.penalty == 1) & (q.penalty_team == q.defteam)).astype(float)
    q["off_pen_yds"] = np.where(q.off_pen == 1, q.penalty_yards.fillna(0), 0.0)
    q["def_pen_yds"] = np.where(q.def_pen == 1, q.penalty_yards.fillna(0), 0.0)
    q["scrim"] = q.play_type.isin(["run", "pass"]).astype(float)
    q["third"] = ((q.third_down_converted == 1) | (q.third_down_failed == 1)).astype(float)
    q["third_conv"] = np.where(q.third == 1, q.third_down_converted.fillna(0), np.nan)
    # drives
    d = q.groupby(["game_id", "posteam", "fixed_drive"]).agg(
        res=("fixed_drive_result", "first"), fail3=("third_down_failed", "max"),
        top=("drive_time_of_possession", "first"), nplays=("scrim", "sum")).reset_index()
    d["top_sec"] = d.top.map(_top_seconds)
    d["punt_after3"] = ((d.fail3 == 1) & (d.res == "Punt")).astype(float)
    d["fg_after3"] = ((d.fail3 == 1) & (d.res == "Field goal")).astype(float)
    d["stall3"] = np.where(d.fail3 == 1, (d.res.isin(["Punt", "Field goal"])).astype(float), np.nan)
    d["punt"] = (d.res == "Punt").astype(float); d["fg"] = (d.res == "Field goal").astype(float)
    drv = d.groupby(["game_id", "posteam"]).agg(
        drives=("fixed_drive", "nunique"), punt_rate=("punt", "mean"), fg_rate=("fg", "mean"),
        punt_after3=("punt_after3", "sum"), fg_after3=("fg_after3", "sum"), stall3_rate=("stall3", "mean"),
        top_sec=("top_sec", "sum")).reset_index()
    pl = q.groupby(["game_id", "posteam"]).agg(
        plays=("scrim", "sum"), off_pen=("off_pen", "sum"), off_pen_yds=("off_pen_yds", "sum"),
        def_pen=("def_pen", "sum"), def_pen_yds=("def_pen_yds", "sum"), third_conv=("third_conv", "mean"),
        thirds=("third", "sum")).reset_index()
    t = pl.merge(drv, on=["game_id", "posteam"], how="left")
    t["off_pen_rate"] = t.off_pen / t.plays.replace(0, np.nan)
    t["opp_def_pen_rate"] = t.def_pen / t.plays.replace(0, np.nan)   # penalties the defence they faced committed
    t["sec_per_play"] = t.top_sec / t.plays.replace(0, np.nan)
    t["punt_after3_pd"] = t.punt_after3 / t.drives.replace(0, np.nan)
    t["fg_after3_pd"] = t.fg_after3 / t.drives.replace(0, np.nan)
    off = t.rename(columns={"posteam": "team"})[["game_id", "team", "plays", "drives", "top_sec", "sec_per_play",
                                                  "off_pen_rate", "off_pen_yds", "third_conv", "punt_rate", "fg_rate",
                                                  "punt_after3_pd", "fg_after3_pd", "stall3_rate"]]
    # defence view: what the opposing offence did against this defence + this defence's own penalties
    dft = t.merge(q[["game_id", "posteam", "defteam"]].drop_duplicates(), on=["game_id", "posteam"])
    dfn = dft.rename(columns={"defteam": "def_team"})
    dfn = dfn.assign(def_pen_rate=dfn.opp_def_pen_rate, def_pen_yds=dfn.def_pen_yds,
                     plays_allowed=dfn.plays, top_allowed=dfn.top_sec, third_conv_allowed=dfn.third_conv,
                     punts_forced=dfn.punt_rate, stall3_forced=dfn.stall3_rate)
    dfn = dfn[["game_id", "def_team", "def_pen_rate", "def_pen_yds", "plays_allowed", "top_allowed",
               "third_conv_allowed", "punts_forced", "stall3_forced"]]
    return off, dfn


TEMPO_OFF = ["plays", "drives", "top_sec", "sec_per_play", "off_pen_rate", "off_pen_yds", "third_conv", "punt_rate",
             "fg_rate", "punt_after3_pd", "fg_after3_pd", "stall3_rate"]
TEMPO_DEF = ["def_pen_rate", "def_pen_yds", "plays_allowed", "top_allowed", "third_conv_allowed", "punts_forced",
             "stall3_forced"]


def rolling_tempo(skeleton: pd.DataFrame, off, dfn):
    """Team-keyed (not coordinator-keyed): discipline and tempo belong to the roster and head coach."""
    sk = skeleton[["game_id", "season", "week", "team"]].drop_duplicates()
    sk = sk.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    o = sk.merge(off, on=["game_id", "team"], how="left")
    d = sk.rename(columns={"team": "def_team"}).merge(dfn, on=["game_id", "def_team"], how="left")
    of = pd.concat([o[["game_id", "team"]], _shift_ewm(o, "team", TEMPO_OFF, HL, "_tp")], axis=1)
    df_ = pd.concat([d[["game_id", "def_team"]], _shift_ewm(d, "def_team", TEMPO_DEF, HL, "_tpd")], axis=1)
    return of, df_


def offense_defense_tables(pbp, ftn, rosters):
    p = _plays(pbp, ftn)
    pos = rosters.dropna(subset=["gsis_id"]).drop_duplicates("gsis_id", keep="last") \
        .set_index("gsis_id").position
    p["tgt_pos"] = p.receiver_player_id.map(pos).replace({"FB": "RB"})
    p["td_pos"] = np.where(p.off_td == 1, p.td_player_id.map(pos).replace({"FB": "RB"}), None)
    for k in ("WR", "TE", "RB"):
        p[f"tgt_{k}"] = np.where(p.att == 1, (p.tgt_pos == k).astype(float), np.nan)
        p[f"rztgt_{k}"] = np.where((p.att == 1) & p.rz, (p.tgt_pos == k).astype(float), np.nan)
    for k in ("WR", "TE", "RB", "QB"):
        p[f"td_{k}"] = (p.td_pos == k).astype(float)
    qb_ids = set(pos[pos == "QB"].index)
    p["qb_design_run"] = ((p.rush == 1) & p.rusher_player_id.isin(qb_ids) & (p.qb_scramble != 1)).astype(float)
    p["qb_rz_run"] = np.where(p.rz & (p.rush == 1), p.rusher_player_id.isin(qb_ids).astype(float), np.nan)

    # unit-vs-unit efficiency (OL vs DL, coverage vs WR/TE/RB)
    rpos = p.rusher_player_id.map(pos).replace({"FB": "RB"})
    rb_run = (p.rush == 1) & (rpos == "RB")
    p["rb_ypc"] = np.where(rb_run, p.yards_gained, np.nan)
    p["stuff"] = np.where(rb_run, (p.yards_gained <= 0).astype(float), np.nan)
    p["sacked"] = np.where(p.qb_dropback == 1, p.sack.fillna(0), np.nan)
    p["oop"] = np.where(p.qb_dropback == 1, p.is_qb_out_of_pocket, np.nan)
    p["explosive"] = np.where(p.att == 1, (p.yards_gained >= 20).astype(float), np.nan)
    for k in ("WR", "TE", "RB"):
        tk = (p.att == 1) & (p.tgt_pos == k)
        p[f"ypt_{k}"] = np.where(tk, p.yards_gained.fillna(0), np.nan)
        p[f"cr_{k}"] = np.where(tk, p.complete_pass.fillna(0), np.nan)
    keys_o = ["game_id", "posteam"]
    off = p.groupby(keys_o).agg(
        proe=("pass_oe", "mean"), rz_pass=("rz_pass", "mean"), gl_pass=("gl_pass", "mean"),
        rz_proe=("rz_proe", "mean"), deep_rate=("deep", "mean"), short_rate=("short", "mean"),
        middle_rate=("middle", "mean"), adot=("air", "mean"), yac_pc=("yac", "mean"),
        shotgun=("shotgun", "mean"), no_huddle=("no_huddle", "mean"), pa_rate=("pa", "mean"),
        screen_rate=("screen", "mean"), rpo_rate=("is_rpo", "mean"), motion_rate=("is_motion", "mean"),
        qb_design_run=("qb_design_run", "mean"), qb_rz_run=("qb_rz_run", "mean"),
        trail_pass=("trail_pass", "mean"), lead_run=("lead_run", "mean"),
        tgt_WR=("tgt_WR", "mean"), tgt_TE=("tgt_TE", "mean"), tgt_RB=("tgt_RB", "mean"),
        rztgt_WR=("rztgt_WR", "mean"), rztgt_TE=("rztgt_TE", "mean"), rztgt_RB=("rztgt_RB", "mean"),
        ol_rb_ypc=("rb_ypc", "mean"), ol_stuff_rate=("stuff", "mean"), ol_sack_rate=("sacked", "mean"),
        ol_pressure_rate=("oop", "mean"), explosive_rate=("explosive", "mean"),
    ).reset_index().rename(columns={"posteam": "team"})
    rz = _rz_drives(p)
    off = off.merge(rz.drop(columns="defteam").rename(columns={"posteam": "team"}), on=["game_id", "team"],
                    how="left")
    off["rz_td_rate"] = off.rz_tds / off.rz_trips

    dfn = p.groupby(["game_id", "defteam"]).agg(
        blitz_rate=("blitz", "mean"), rushers=("rushers", "mean"), box_run=("box_run", "mean"),
        light_box=("light_box", "mean"), heavy_box=("heavy_box", "mean"),
        proe_faced=("pass_oe", "mean"), deep_rate_allowed=("deep", "mean"), deep_td_allowed=("deep_td", "sum"),
        yac_allowed=("yac", "mean"), adot_allowed=("air", "mean"),
        td_allowed_WR=("td_WR", "sum"), td_allowed_TE=("td_TE", "sum"), td_allowed_RB=("td_RB", "sum"),
        td_allowed_QB=("td_QB", "sum"),
        dl_rb_ypc_allowed=("rb_ypc", "mean"), dl_stuff_forced=("stuff", "mean"), dl_sack_rate=("sacked", "mean"),
        dl_pressure_rate=("oop", "mean"), explosive_allowed=("explosive", "mean"),
        ypt_allowed_WR=("ypt_WR", "mean"), ypt_allowed_TE=("ypt_TE", "mean"), ypt_allowed_RB=("ypt_RB", "mean"),
        cr_allowed_WR=("cr_WR", "mean"), cr_allowed_TE=("cr_TE", "mean"), cr_allowed_RB=("cr_RB", "mean"),
    ).reset_index().rename(columns={"defteam": "def_team"})
    drz = rz.groupby(["game_id", "defteam"])[["rz_trips", "rz_tds"]].sum().reset_index() \
        .rename(columns={"defteam": "def_team"})
    dfn = dfn.merge(drz, on=["game_id", "def_team"], how="left")
    dfn["rz_td_rate_allowed"] = dfn.rz_tds / dfn.rz_trips
    dfn = dfn.drop(columns=["rz_trips", "rz_tds"])
    off = off.drop(columns=["rz_trips", "rz_tds"])
    return off, dfn


OFF_COLS = ["proe", "rz_pass", "gl_pass", "rz_proe", "deep_rate", "short_rate", "middle_rate", "adot", "yac_pc",
            "shotgun", "no_huddle", "pa_rate", "screen_rate", "rpo_rate", "motion_rate", "qb_design_run",
            "qb_rz_run", "tgt_WR", "tgt_TE", "tgt_RB", "rztgt_WR", "rztgt_TE", "rztgt_RB", "rz_td_rate",
            "ol_rb_ypc", "ol_stuff_rate", "ol_sack_rate", "ol_pressure_rate", "explosive_rate", "trail_pass", "lead_run"]
DEF_COLS = ["blitz_rate", "rushers", "box_run", "light_box", "heavy_box", "proe_faced", "deep_rate_allowed",
            "deep_td_allowed", "yac_allowed", "adot_allowed", "td_allowed_WR", "td_allowed_TE",
            "td_allowed_RB", "td_allowed_QB", "rz_td_rate_allowed",
            "dl_rb_ypc_allowed", "dl_stuff_forced", "dl_sack_rate", "dl_pressure_rate", "explosive_allowed",
            "ypt_allowed_WR", "ypt_allowed_TE", "ypt_allowed_RB", "cr_allowed_WR", "cr_allowed_TE", "cr_allowed_RB"]


def rolling_scheme(skeleton: pd.DataFrame, off, dfn, coords=None):
    """skeleton: [game_id, season, week, team, opp] incl. future games.
    Returns (offense features keyed game_id,team) and (defense features keyed game_id,def_team)."""
    sk = skeleton[["game_id", "season", "week", "team"]].drop_duplicates()
    sk = sk.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    o = sk.merge(off, on=["game_id", "team"], how="left")
    d = sk.rename(columns={"team": "def_team"}).merge(dfn, on=["game_id", "def_team"], how="left")
    o["okey"], d["dkey"] = o.team, d.def_team
    if coords is not None:
        c = coords.set_index(["season", "team"])
        o["okey"] = [c.oc.get((s, t), t) if (s, t) in c.index else t for s, t in zip(o.season, o.team)]
        d["dkey"] = [c.dc.get((s, t), t) if (s, t) in c.index else t for s, t in zip(d.season, d.def_team)]
    of = _shift_ewm(o, "okey", OFF_COLS, HL, "_oc")
    # Fix 2 (Week 9): red-zone play-calling over the last ~3 games, alongside the season roll
    of3 = _shift_ewm(o, "okey", ["rz_pass", "gl_pass", "rz_td_rate", "rztgt_WR", "rztgt_TE", "rztgt_RB",
                                 "trail_pass", "lead_run"], 1.5, "_oc3")
    of = pd.concat([of, of3], axis=1)
    of["rz_pass_trend"] = of.rz_pass_oc3 - of.rz_pass_oc
    df_ = _shift_ewm(d, "dkey", DEF_COLS, HL, "_dc")
    of = pd.concat([o[["game_id", "team"]], of], axis=1)
    df_ = pd.concat([d[["game_id", "def_team"]], df_], axis=1)
    return of, df_


# --------------------------------------------------------------------------------------------
def personnel_injuries(rosters, sched, path=None):
    """Rows in data/personnel.csv (user reads / ESPN pregame scratches) as synthetic injury-report rows, so late
    defensive and OL scratches reach injury_table (def_out_*, own_ol_out). OUT/INACTIVE apply to the game week the
    read was logged in; IR/TRADED carry forward to the end of that season."""
    from pathlib import Path
    from .data import DATA_DIR
    pf = Path(path) if path else DATA_DIR / "personnel.csv"
    cols = ["season", "week", "team", "gsis_id", "position", "full_name", "report_status"]
    if not pf.exists():
        return pd.DataFrame(columns=cols)
    P = pd.read_csv(pf)
    P = P[P.status.astype(str).str.upper().isin(["OUT", "INACTIVE", "TRADED", "IR"])].copy()
    P["as_of"] = pd.to_datetime(P.get("as_of"), errors="coerce")
    P = P.dropna(subset=["as_of"])
    nm = lambda x: x.astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)  # noqa: E731
    ro = rosters.drop_duplicates(["season", "team", "gsis_id"])[["season", "team", "gsis_id", "position", "full_name"]]
    ro = ro.assign(nkey=nm(ro.full_name))
    gd = sched.assign(gameday=pd.to_datetime(sched.gameday)).groupby(["season", "week"]).gameday.max()
    rows = []
    for x in P.itertuples(index=False):
        season = int(x.as_of.year) if x.as_of.month >= 3 else int(x.as_of.year) - 1
        if season not in gd.index.get_level_values(0):
            continue
        wk = gd.loc[season]
        later = wk[wk >= x.as_of.normalize()]
        if later.empty:
            continue
        w0 = int(later.index[0])
        perm = str(x.status).upper() in ("TRADED", "IR") or "traded" in str(x.note).lower()
        weeks = range(w0, int(wk.index.max()) + 1) if perm else [w0]
        hit = ro[(ro.season == season) & (ro.nkey == nm(pd.Series([x.name]))[0])]
        if isinstance(x.team, str) and x.team:
            hit = hit[hit.team == x.team]
        for h in hit.itertuples(index=False):
            for w in weeks:
                rows.append((season, w, h.team, h.gsis_id, h.position, h.full_name, "Out"))
    return pd.DataFrame(rows, columns=cols)


def injury_table(injuries, snaps, rosters):
    """Per (season, week, team): snap-weighted Out/Doubtful players by unit, using each player's
    average snap share over the team's previous 4 games."""
    from .data import id_map
    inj = injuries[injuries.report_status.isin(["Out", "Doubtful"])][
        ["season", "week", "team", "gsis_id", "position"]].drop_duplicates()
    m = id_map(rosters)
    inj = inj.merge(m, on="gsis_id", how="left")
    # fallback: many linemen/defenders lack a PFR id in rosters -> match on season+team+name
    nm = lambda x: x.str.lower().str.replace(r"[^a-z]", "", regex=True).str.replace(r"(jr|sr|ii|iii|iv)$", "", regex=True)  # noqa: E731
    full = injuries.drop_duplicates("gsis_id").set_index("gsis_id").full_name
    inj["nkey"] = nm(inj.gsis_id.map(full).fillna(""))
    sk = snaps[["season", "team", "player", "pfr_player_id"]].drop_duplicates(["season", "team", "player"])
    sk["nkey"] = nm(sk.player)
    sk = sk.drop_duplicates(["season", "team", "nkey"]).set_index(["season", "team", "nkey"]).pfr_player_id
    fb = pd.Series([sk.get((a, b, c)) for a, b, c in zip(inj.season, inj.team, inj.nkey)], index=inj.index)
    inj["pfr_id"] = inj.pfr_id.fillna(fb)
    sn = snaps[["season", "week", "pfr_player_id", "defense_pct", "offense_pct"]] \
        .rename(columns={"pfr_player_id": "pfr_id", "week": "sw"})
    x = inj.merge(sn, on=["season", "pfr_id"], how="left")
    x = x[(x.sw < x.week) & (x.sw >= x.week - 4) | x.sw.isna()]
    w = x.groupby(["season", "week", "team", "gsis_id", "position"]).agg(
        dpct=("defense_pct", "mean"), opct=("offense_pct", "mean")).reset_index().fillna({"dpct": 0, "opct": 0})
    w["unit"] = np.select([w.position.isin(DL_POS), w.position.isin(LB_POS), w.position.isin(DB_POS),
                           w.position.isin(OL_POS)], ["DL", "LB", "DB", "OL"], "OTHER")
    t = w.pivot_table(index=["season", "week", "team"], columns="unit", values="dpct", aggfunc="sum",
                      fill_value=0)
    out = pd.DataFrame(index=t.index)
    for u in ("DL", "LB", "DB"):
        out[f"def_out_{u}"] = t[u] if u in t else 0.0
    out["def_out_total"] = out[["def_out_DL", "def_out_LB", "def_out_DB"]].sum(axis=1)
    starters = w[(w.dpct >= 0.6)].groupby(["season", "week", "team"]).size()
    out["def_starters_out"] = starters.reindex(out.index).fillna(0)
    ol = w[w.unit == "OL"].groupby(["season", "week", "team"]).opct.sum()
    out = out.reset_index()
    olf = ol.rename("own_ol_out").reset_index()
    out = out.merge(olf, on=["season", "week", "team"], how="outer").fillna(0)
    return out
