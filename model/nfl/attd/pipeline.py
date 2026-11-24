"""End-to-end orchestration: build dataset, backtest, train production model, project a slate."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data as D
from .context import fetch_forecasts, game_context, player_context_splits
from .scheme import (injury_table, offense_defense_tables, personnel_injuries, rolling_scheme, rolling_tempo,
                     tempo_penalty_tables)
from .features import build_player_games, finalize, priors_for_new_players, team_features, team_game_table
from .model import (BASE_FEATS, FEATURE_GROUPS, GBM_FEATS, ATTDModel, TeamModel, add_structural,
                    calibration_table, metrics)
from .xtd import XTDModel, prep_plays


def load_all(seasons):
    pbp = D.load_pbp(seasons)
    rosters = D.load_rosters(seasons)
    snaps = D.load_snaps(seasons)
    sched = D.load_schedules()
    sched = sched[sched.season.isin(seasons)]
    return pbp, rosters, snaps, sched


def build_dataset(pbp, rosters, snaps, sched, xtd_fit_mask=None, future=None, forecasts=None):
    qb_ids = set(rosters.loc[rosters.position == "QB", "gsis_id"].dropna())
    rushes, targets = prep_plays(pbp, qb_ids)
    if xtd_fit_mask is not None:
        rushes_f, targets_f = rushes[xtd_fit_mask(rushes)], targets[xtd_fit_mask(targets)]
    else:
        rushes_f, targets_f = rushes, targets
    xm = XTDModel().fit(rushes_f, targets_f)

    base, rushes_s, targets_s = build_player_games(pbp, rosters, snaps, sched, xm, future)
    tg = team_game_table(pbp, rushes_s, targets_s, sched)
    tgf = team_features(tg)
    priors = priors_for_new_players(base)
    df = finalize(base, tgf, priors)
    df = add_environment(df, pbp, rosters, snaps, sched, tgf, forecasts)
    return df, tgf, xm


def add_environment(df, pbp, rosters, snaps, sched, tgf, forecasts=None):
    seasons = sorted(df.season.unique())
    # 1) stadium / weather / slot / travel
    ctx = game_context(sched, pbp, forecasts)
    df = df.merge(ctx, on=["game_id", "team"], how="left")
    # 2) shrunk player splits in this game's context (home/away x roof/surface/slot/weather)
    df = df.join(player_context_splits(df))
    # 3) OC / DC tendencies (rolling)
    ftn = D.load_ftn(seasons)
    off, dfn = offense_defense_tables(pbp, ftn, rosters)
    of, dr = rolling_scheme(tgf[["game_id", "season", "week", "team"]], off, dfn, D.load_coordinators())
    df = df.merge(of, on=["game_id", "team"], how="left")
    df = df.merge(dr.rename(columns={"def_team": "opp"}), on=["game_id", "opp"], how="left")
    # 3a) tempo & discipline: penalties, drive stalls after 3rd down, possession time, plays -> time on field
    toff, tdef = tempo_penalty_tables(pbp)
    tof, tdr = rolling_tempo(tgf[["game_id", "season", "week", "team"]], toff, tdef)
    df = df.merge(tof, on=["game_id", "team"], how="left")
    df = df.merge(tdr.rename(columns={"def_team": "opp"}), on=["game_id", "opp"], how="left")
    opp_t = tof.rename(columns={"team": "opp"}).add_prefix("opp_").rename(columns={"opp_game_id": "game_id", "opp_opp": "opp"})
    df = df.merge(opp_t[["game_id", "opp", "opp_plays_tp", "opp_sec_per_play_tp", "opp_top_sec_tp", "opp_third_conv_tp",
                         "opp_off_pen_rate_tp", "opp_stall3_rate_tp"]], on=["game_id", "opp"], how="left")
    lg_plays = df.plays_tp.mean()
    df["exp_plays"] = 0.5 * (df.plays_tp.fillna(lg_plays) + df.plays_allowed_tpd.fillna(lg_plays))
    df["exp_top_sec"] = 0.5 * (df.top_sec_tp.fillna(1800) + df.top_allowed_tpd.fillna(1800))
    df["exp_snaps"] = df.exp_plays * df.offense_pct_e3.fillna(0)
    df["exp_time_on_field"] = df.exp_top_sec * df.offense_pct_e3.fillna(0)
    df["pen_edge"] = df.def_pen_rate_tpd.fillna(0) - df.off_pen_rate_tp.fillna(0)    # free yards: their flags minus ours
    df["stall_edge"] = df.stall3_forced_tpd.fillna(0.6) - df.stall3_rate_tp.fillna(0.6)  # >0: we stall more vs this D than usual
    # matchup interactions: player's role x what this defense gives up
    df["mx_deep"] = df.sh_deep_tgt_e3 * df.deep_rate_allowed_dc
    df["mx_pos_td_allowed"] = np.select(
        [df.pos_group == "WR", df.pos_group == "TE", df.pos_group == "RB", df.pos_group == "QB"],
        [df.td_allowed_WR_dc, df.td_allowed_TE_dc, df.td_allowed_RB_dc, df.td_allowed_QB_dc], np.nan)
    df["mx_pos_tgt_pref"] = np.select(
        [df.pos_group == "WR", df.pos_group == "TE", df.pos_group == "RB"],
        [df.rztgt_WR_oc, df.rztgt_TE_oc, df.rztgt_RB_oc], df.qb_rz_run_oc)
    # 3b) who they're against: active-defender unit ratings (CB / S / LB / DL)
    from .defenders import defender_games, projected_defenders, unit_indices
    dg = defender_games(seasons, rosters, snaps)
    up = None
    if df.is_future.any():
        fut_wk = df[df.is_future][["season", "week"]].drop_duplicates()
        inj_all = D.load_injuries(seasons)
        up = pd.concat([projected_defenders(r.season, r.week, sched, rosters, snaps, inj_all, dg)
                        for r in fut_wk.itertuples()], ignore_index=True)
    ui, names = unit_indices(dg, up)
    df = df.merge(ui.rename(columns={"def_team": "opp"}), on=["game_id", "opp"], how="left")
    if names is not None and len(names):
        names.to_csv(D.DATA_DIR.parent / "outputs" / "defenders_upcoming.csv", index=False)
    # matchup interactions: this player's role x the unit he plays against
    pg = df.pos_group
    df["mx_cov_index"] = np.select([pg == "WR", pg == "TE", pg == "RB"],
                                   [df.def_CB_cov + 0.5 * df.def_S_cov, df.def_LB_cov + df.def_S_cov,
                                    df.def_LB_cov], np.nan)
    df["mx_ypt_allowed"] = np.select([pg == "WR", pg == "TE", pg == "RB"],
                                     [df.ypt_allowed_WR_dc, df.ypt_allowed_TE_dc, df.ypt_allowed_RB_dc], np.nan)
    df["mx_cr_allowed"] = np.select([pg == "WR", pg == "TE", pg == "RB"],
                                    [df.cr_allowed_WR_dc, df.cr_allowed_TE_dc, df.cr_allowed_RB_dc], np.nan)
    df["mx_tgt_x_ypt"] = df.sh_targets_e3 * df.mx_ypt_allowed
    df["mx_run_lane"] = df.ol_rb_ypc_oc.fillna(4.2) + df.dl_rb_ypc_allowed_dc.fillna(4.2) - 4.2
    df["mx_stuff"] = df.ol_stuff_rate_oc.fillna(0.18) + df.dl_stuff_forced_dc.fillna(0.18)
    df["mx_rush_x_lane"] = df.rush_share * df.mx_run_lane
    df["mx_pass_pro"] = df.ol_sack_rate_oc.fillna(0.07) + df.dl_sack_rate_dc.fillna(0.07)
    # Fix 1 (Week 9): team scenario risk — how volatile the offense's TD output has been, and script exposure
    tsd = tgf.sort_values(["season", "week"]).copy()
    tsd["team_td_sd"] = tsd.groupby(["team", "season"]).team_td.transform(
        lambda x: x.shift(1).expanding(min_periods=3).std())
    tsd["team_zero_rate"] = tsd.groupby(["team", "season"]).team_td.transform(
        lambda x: (x.shift(1) == 0).expanding(min_periods=3).mean())
    df = df.merge(tsd[["game_id", "team", "team_td_sd", "team_zero_rate"]], on=["game_id", "team"], how="left")
    df["abs_spread"] = df.spread.abs()
    df["dog_by_7"] = (df.spread <= -7).astype(int)
    # Fix 3 (Week 9): role freshness — did last game's share depart from his longer baseline?
    df["carry_share_jump"] = (df.sh_carries_lag1 - df.sh_carries_e3).abs()
    df["target_share_jump"] = (df.sh_targets_lag1 - df.sh_targets_e3).abs()
    df["snap_trend"] = df.offense_pct_lag1 - df.offense_pct_e3
    df["fresh_role"] = ((df.carry_share_jump > 0.15) | (df.target_share_jump > 0.15) |
                        (df.snap_trend.abs() > 0.20) | (df.n_prev_season < 3)).astype(int)
    # red-zone target concentration on the team (top-2 share of RZ targets, rolling) and this player's rank
    rz_rank = df.groupby(["game_id", "team"]).sh_tgt_rz_e3.rank(ascending=False)
    df["rz_tgt_rank"] = rz_rank
    df["rz_tgt_top2_share"] = df.groupby(["game_id", "team"]).sh_tgt_rz_e3.transform(lambda x: x.nlargest(2).sum())
    # 4) injuries: opponent defense + own offensive line
    inj_all = pd.concat([D.load_injuries(seasons), personnel_injuries(rosters, sched)], ignore_index=True)
    inj = injury_table(inj_all, snaps, rosters)
    di = inj[["season", "week", "team", "def_out_DL", "def_out_LB", "def_out_DB", "def_out_total",
              "def_starters_out"]].rename(columns={"team": "opp"})
    df = df.merge(di, on=["season", "week", "opp"], how="left")
    df = df.merge(inj[["season", "week", "team", "own_ol_out"]], on=["season", "week", "team"], how="left")
    for c in ["def_out_DL", "def_out_LB", "def_out_DB", "def_out_total", "def_starters_out", "own_ol_out"]:
        df[c] = df[c].fillna(0)
    return df


def backtest(seasons, test_seasons, ablation=True):
    pbp, rosters, snaps, sched = load_all(seasons)
    is_train = lambda d: ~d.season.isin(test_seasons)  # noqa: E731
    df, tgf, _ = build_dataset(pbp, rosters, snaps, sched, xtd_fit_mask=is_train)
    df = df[~df.is_future & df.label.notna()]

    tr_mask = ~tgf.season.isin(test_seasons) & tgf.played
    tm = TeamModel().fit(tgf[tr_mask])
    df = add_structural(tm.apply(df))

    fit = df[~df.season.isin(test_seasons)]
    test = df[df.season.isin(test_seasons)]
    m = ATTDModel().fit(fit)

    # baselines
    pos_rate = fit.groupby("pos_group").label.mean()
    p_pos = test.pos_group.map(pos_rate).values
    p_naive = np.clip(1 - np.exp(-test.td_e10.fillna(test.pos_group.map(pos_rate))), 1e-3, 0.9).values

    p_final = m.predict(test)
    rows = [metrics(test.label, p_pos, "baseline: position avg"),
            metrics(test.label, p_naive, "baseline: player rolling TD rate"),
            metrics(test.label, test.p_struct, "structural (team x share)"),
            metrics(test.label, p_final, "FINAL (structural + GBM)")]
    res = pd.DataFrame(rows).set_index("model")
    cal_tab = calibration_table(test.label.values, p_final)
    by_pos = pd.DataFrame([metrics(g.label, p_final[(test.pos_group == k).values], k)
                           for k, g in test.groupby("pos_group")]).set_index("model")
    imp = pd.Series(m.gbm.booster_.feature_importance("gain"), index=m.gbm.feature_name_) \
        .sort_values(ascending=False)
    out = test[["season", "week", "game_id", "team", "name", "pos_group", "label"]].assign(p=p_final)

    # Factor report card: out-of-sample value of each feature group
    abl = None
    if ablation:
        base_ll = metrics(test.label, p_final, "")["log_loss"]
        m0 = ATTDModel(feats=BASE_FEATS).fit(fit)
        ll0 = metrics(test.label, m0.predict(test), "")["log_loss"]
        rows = []
        for g, cols in FEATURE_GROUPS.items():
            add = ATTDModel(feats=BASE_FEATS + cols).fit(fit)
            drop = ATTDModel(feats=[c for c in GBM_FEATS if c not in cols]).fit(fit)
            rows.append({"factor_group": g, "n_features": len(cols),
                         "gain_when_added_to_base": ll0 - metrics(test.label, add.predict(test), "")["log_loss"],
                         "loss_when_removed_from_full": metrics(test.label, drop.predict(test), "")["log_loss"]
                         - base_ll})
        abl = pd.DataFrame(rows).set_index("factor_group")
        abl.attrs["base_ll"], abl.attrs["full_ll"] = ll0, base_ll
    return res, cal_tab, by_pos, imp, tm, out, abl


# --------------------------------------------------------------------------------------------
def projected_actives(season, week, rosters, snaps_df, injuries, sched, extra_out=(), lookback=4):
    """Who will suit up: on the weekly roster (ACT), not ruled Out/Doubtful, with recent offensive snaps."""
    games = sched[(sched.season == season) & (sched.week == week) & sched.home_score.isna()]
    teams = pd.concat([games[["game_id", "home_team"]].rename(columns={"home_team": "team"}),
                       games[["game_id", "away_team"]].rename(columns={"away_team": "team"})])

    r = rosters[rosters.season == season]
    wk = week if (r.week == week).any() else r.week.max()
    r = r[(r.week == wk) & (r.status == "ACT") & r.position.isin(D.SKILL_POS)]
    r = r[["gsis_id", "team", "position", "full_name"]].rename(columns={"gsis_id": "player_id",
                                                                         "full_name": "name"})
    # recent usage on offense
    m = D.id_map(rosters)
    s = snaps_df[(snaps_df.season == season) & (snaps_df.offense_snaps > 0)]
    s = s.merge(m, left_on="pfr_player_id", right_on="pfr_id")
    recent_weeks = sorted(s.week.unique())[-lookback:]
    used = set(s[s.week.isin(recent_weeks)].gsis_id)
    # returning players (Nov 19 2026: Montgomery Week 11, Etienne Week 10): on the active roster, snaps earlier this
    # season but none in the lookback, and listed on this week's report as practising. They re-enter the pool on their
    # stale role numbers and are flagged returning (singles only) by the games-back rule below.
    wk_inj = injuries[(injuries.season == season) & (injuries.week == week)]
    prac = wk_inj[wk_inj.practice_status.fillna("").str.contains("Full|Limited") & ~wk_inj.report_status.isin(["Out", "Doubtful"])]
    comeback = (set(s.gsis_id) - used) & set(prac.gsis_id)
    if comeback:
        nm = r[r.player_id.isin(comeback)]
        for x in nm.itertuples():
            print(f"  [returning] {x.name} ({x.team}): no snaps in the last {lookback} games, practising this week -> back in the pool")
    r = r[r.player_id.isin(used | comeback)]

    inj = injuries[(injuries.season == season) & (injuries.week == week)]
    status = inj.set_index("gsis_id").report_status.to_dict()
    r["injury_status"] = r.player_id.map(status)
    r = r[~r.injury_status.isin(["Out", "Doubtful"])]
    # manual personnel overrides (late trades / scratches / user reads) -> logged on the card
    _plog = []
    pf = D.DATA_DIR / "personnel.csv"
    P = pd.DataFrame(columns=["name", "team", "status", "note"])
    if pf.exists():
        P = pd.read_csv(pf)
        P = P[P.status.str.upper().isin(["OUT", "INACTIVE", "TRADED", "IR"])]
        # week scoping: OUT/INACTIVE reads apply only to the game week they were logged in (as_of within the 7 days
        # before that week's last game day); TRADED / IR carry forward. "Traded" in the note also counts as permanent.
        gdays = pd.to_datetime(sched[(sched.season == season) & (sched.week == week)].gameday)
        wk_end = gdays.max(); wk_start = wk_end - pd.Timedelta(days=7)
        asof = pd.to_datetime(P.get("as_of"), errors="coerce")
        perm = P.status.str.upper().isin(["TRADED", "IR"]) | P.note.fillna("").str.contains("traded", case=False)
        P = P[perm | ((asof > wk_start) & (asof <= wk_end))]
        for x in P.itertuples(index=False):
            hit = (r.name.str.lower() == str(x.name).lower()) & ((r.team == x.team) if isinstance(x.team, str) else True)
            if hit.any():
                print(f"  [personnel] {x.name} ({x.team}) -> {x.status}: {x.note}")
                _plog.append({"type": "override", "name": x.name, "team": x.team, "status": x.status, "note": x.note})
            r = r[~hit]
    if extra_out:
        low = {x.lower() for x in extra_out}
        r = r[~r.name.str.lower().isin(low)]
    # backup QB: if a team has no QB left in the pool (starter Out / overridden), pull in the depth-chart backup
    # even without recent snaps, so the game is never projected without a quarterback
    all_qb = rosters[(rosters.season == season) & (rosters.week == wk) & (rosters.status == "ACT")
                     & (rosters.position == "QB")][["gsis_id", "team", "position", "full_name", "years_exp"]] \
        .rename(columns={"gsis_id": "player_id", "full_name": "name"})
    if pf.exists():
        all_qb = all_qb[~all_qb.name.str.lower().isin(set(P.name.str.lower()))]
    all_qb = all_qb[~all_qb.player_id.isin(out_ids_qb := set(inj[inj.report_status.isin(["Out", "Doubtful"])].gsis_id))]
    season_snaps = s.groupby("gsis_id").agg(qb_games=("week", "nunique"), qb_pct=("offense_pct", "mean"))
    all_qb = all_qb.join(season_snaps, on="player_id").fillna({"qb_games": 0, "qb_pct": 0})
    for t in teams.team.unique():
        if not ((r.team == t) & (r.position == "QB")).any():
            cand = all_qb[all_qb.team == t].sort_values(["qb_pct", "years_exp"], ascending=False)
            if len(cand):
                b = cand.iloc[0]
                print(f"  [backup QB] {t}: {b['name']} projected to start ({int(b.qb_games)} games, "
                      f"{b.qb_pct:.0%} snaps this season)")
                _plog.append({"type": "backup_qb", "name": b["name"], "team": t, "games": int(b.qb_games),
                              "pct": float(b.qb_pct)})
                r = pd.concat([r, pd.DataFrame([{"player_id": b.player_id, "team": t, "position": "QB",
                                                 "name": b["name"], "injury_status": None}])], ignore_index=True)
    # return-from-absence: missed 2+ of the team's last 4 completed games (v1.9g rule -> singles only)
    tw = s[s.team.isin(r.team.unique())].groupby("team").week.apply(lambda x: sorted(x.unique())[-4:])
    played = s.groupby(["gsis_id", "team"]).week.apply(set)
    def missed(pid, team):
        wks = tw.get(team, [])
        return sum(w not in played.get((pid, team), set()) for w in wks)
    r["games_missed_last4"] = [missed(p, t) for p, t in zip(r.player_id, r.team)]
    # refined (Jacobs/Mason, user decision Nov 9 2026): a player is "returning" only while he has fewer than 2 games
    # played since his last missed team game. Once he has two full games back the role is the model's to price.
    tw_all = s[s.team.isin(r.team.unique())].groupby("team").week.apply(lambda x: sorted(x.unique()))
    def games_back(pid, team):
        wks = tw_all.get(team, []); pl = played.get((pid, team), set())
        missed_w = [w for w in wks if w not in pl]
        if not missed_w:
            return 99
        return sum(w in pl for w in wks if w > missed_w[-1])
    r["games_back"] = [games_back(p, t) for p, t in zip(r.player_id, r.team)]
    r["returning"] = (r.games_missed_last4 >= 1) & (r.games_back < 2)
    fut = r.merge(teams, on="team")
    fut["season"], fut["week"] = season, week
    import json as _json
    outs = inj[inj.report_status.isin(["Out", "Doubtful"]) & inj.position.isin(D.SKILL_POS)]
    _plog += [{"type": "injury", "name": x.full_name, "team": x.team, "status": x.report_status,
               "note": x.report_primary_injury} for x in outs.itertuples()]
    (D.DATA_DIR.parent / "outputs" / f"personnel_log_{season}_wk{week}.json").write_text(_json.dumps(_plog, indent=1))
    return fut


def backup_qb_haircut(f, season, week):
    """Backup-QB haircut (Week 10 report card, Nov 16 2026). Out of sample 2025-26 (weeks 4+), when the starter had
    under 25% of the team's season pass attempts, teammates priced >= 20% scored less than priced: WR/TE 28.6% priced
    vs 17.3% actual (n=133, -11 pts, se 3), RB 38.3% vs 31.2% (n=96). Shift on the logit scale, shrunk from the raw
    estimates (-0.65 / -0.31) for sample size; the quarterback himself is unchanged."""
    from .early import backup_qb_teams
    f = f.copy()
    bq = backup_qb_teams(season, week)
    f["backup_qb_team"] = f.team.isin(bq)
    f["p_attd_raw"] = f.p_attd
    shift = np.select([f.backup_qb_team & f.pos_group.isin(["WR", "TE"]), f.backup_qb_team & (f.pos_group == "RB")], [-0.5, -0.3], 0.0)
    lg = np.log(f.p_attd.clip(1e-4, 1 - 1e-4) / (1 - f.p_attd.clip(1e-4, 1 - 1e-4))) + shift
    f["p_attd"] = 1 / (1 + np.exp(-lg))
    return f


def project(season, week, extra_out=(), history_seasons=None, factors="default"):
    history_seasons = history_seasons or list(range(season - 5, season + 1))
    pbp, rosters, snaps, sched = load_all(history_seasons)
    inj = D.load_injuries([season])
    fut = projected_actives(season, week, rosters, snaps, inj, sched, extra_out)
    if fut.empty:
        raise SystemExit(f"No unplayed games found for {season} week {week}.")
    future = fut[["game_id", "season", "week", "team", "player_id", "position", "name"]]
    forecasts = fetch_forecasts(sched, season, week)
    df, tgf, _ = build_dataset(pbp, rosters, snaps, sched, future=future, forecasts=forecasts)

    tm = TeamModel().fit(tgf[tgf.played])
    df = add_structural(tm.apply(df))
    hist = df[~df.is_future & df.label.notna()]
    from .model import feats_for
    m = ATTDModel(feats=feats_for(factors)).fit(hist)

    f = df[df.is_future].copy()
    f["p_attd"] = m.predict(f)
    f = backup_qb_haircut(f, season, week)
    f = f.merge(fut[["player_id", "game_id", "injury_status", "games_missed_last4", "games_back", "returning"]],
                on=["player_id", "game_id"], how="left")
    f["singles_only"] = (f.injury_status == "Questionable") | f.returning.fillna(False).astype(bool)
    f["fair_american"] = f.p_attd.map(prob_to_american)
    # season TD record (games with a TD / games played this season) for the intel sheet
    cur = hist[hist.season == season].groupby("player_id").agg(season_td_games=("label", "sum"),
                                                               season_games=("label", "size"),
                                                               season_tds=("td", "sum"))
    f = f.merge(cur, on="player_id", how="left")
    tag = f"{season}_wk{week}"
    f.to_parquet(D.DATA_DIR.parent / "outputs" / f"projection_features_{tag}.parquet")
    cols = ["game_id", "team", "opp", "name", "position", "pos_group", "injury_status", "games_missed_last4", "games_back",
            "singles_only", "p_attd", "fair_american",
            "p_struct", "lam_team_rush", "lam_team_pass", "rush_share", "rec_share", "implied_filled",
            "is_home", "slot", "roof_type", "is_turf", "wx_cat", "temp", "wind", "travel_miles", "tz_shift",
            "body_clock_hour", "rest_days", "def_out_total", "def_starters_out", "own_ol_out",
            "split_home_away", "split_slot", "split_is_indoor", "split_wx_bad",
            "blitz_rate_dc", "rz_td_rate_allowed_dc", "proe_oc", "rz_pass_oc", "player_id"]
    return f[cols].sort_values("p_attd", ascending=False).reset_index(drop=True), tm


def prob_to_american(p):
    p = float(np.clip(p, 1e-4, 1 - 1e-4))
    return int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))


def american_to_decimal(a):
    a = float(a)
    return 1 + (a / 100 if a > 0 else 100 / -a)


def walkforward_season(season, weeks, factors="default", first=2021):
    """Pre-game predictions for every player-game in `weeks` of `season`, each week trained only on
    games completed before it (xTD play model included)."""
    from .model import feats_for
    pbp, rosters, snaps, sched = load_all(list(range(first, season + 1)))
    df, tgf, _ = build_dataset(pbp, rosters, snaps, sched,
                               xtd_fit_mask=lambda d: d.season < season)
    df = df[~df.is_future & df.label.notna()]
    out = []
    for w in weeks:
        before = lambda d: (d.season < season) | ((d.season == season) & (d.week < w))  # noqa: E731
        tm = TeamModel().fit(tgf[before(tgf) & tgf.played])
        d = add_structural(tm.apply(df))
        tr, te = d[before(d)], d[(d.season == season) & (d.week == w)]
        if te.empty:
            continue
        m = ATTDModel(feats=feats_for(factors)).fit(tr)
        out.append(te[["season", "week", "game_id", "team", "opp", "name", "position", "pos_group", "label",
                       "p_struct", "implied_filled"]].assign(p_attd=m.predict(te)))
        print(f"  week {w}: {len(te)} player-games", flush=True)
    return pd.concat(out, ignore_index=True)
