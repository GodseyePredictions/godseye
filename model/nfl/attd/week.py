"""Weekly build: ATD + props for an upcoming slate -> card (markdown) + shipped-leg JSON for grading."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import data as D
from .context import fetch_forecasts
from .model import ATTDModel, TeamModel, add_structural, feats_for
from .pipeline import build_dataset, load_all, projected_actives
from .props import MARKETS, PropModel, add_prop_features, eligible, prop_feature_list
from .tickets import build_card, card_legs_json, card_markdown

ROOT = Path(__file__).resolve().parent.parent
from .model import FEATURE_GROUPS
PROP_GROUPS = list(FEATURE_GROUPS)   # standing rule (FACTORS.md): every factor group, every build


def role_gate(d: pd.DataFrame) -> pd.Series:
    touches = d.carries_std.fillna(0) + d.rec_std.fillna(0)
    ok = np.select([d.pos_group == "RB", d.pos_group.isin(["WR", "TE"]), d.pos_group == "QB"],
                   [touches >= 8, d.tgt_std.fillna(0) >= 4, d.pass_att_std.fillna(0) >= 20], False)
    return pd.Series(ok, index=d.index) & (d.n_prev_season >= 2)


def build_week(season, week, extra_out=(), factors="default", log=print):
    seasons = list(range(season - 5, season + 1))
    pbp, rosters, snaps, sched = load_all(seasons)
    inj = D.load_injuries([season])
    fut = projected_actives(season, week, rosters, snaps, inj, sched, extra_out)
    if fut.empty:
        raise SystemExit(f"No unplayed games for {season} week {week}.")
    forecasts = fetch_forecasts(sched, season, week)
    future = fut[["game_id", "season", "week", "team", "player_id", "position", "name"]]
    df, tgf, _ = build_dataset(pbp, rosters, snaps, sched, future=future, forecasts=forecasts)
    tm = TeamModel().fit(tgf[tgf.played])
    df = add_structural(tm.apply(df))
    df = add_prop_features(df, D.load_official_stats(seasons), pbp)
    df = df.merge(fut[["player_id", "game_id", "injury_status", "games_missed_last4", "games_back", "returning"]],
                  on=["player_id", "game_id"], how="left")
    hist, F = df[~df.is_future & df.label.notna()], df[df.is_future].copy()
    # projected starting QB = active QB with the most recent snap share
    q = F[F.pos_group == "QB"].sort_values(["offense_pct_lag1", "offense_pct_e3"], ascending=False)
    F.loc[q.drop_duplicates(["game_id", "team"]).index, "is_starter"] = 1
    F["singles_only"] = (F.injury_status == "Questionable") | F.returning.fillna(False).astype(bool)
    F["fresh_role"] = F.fresh_role.fillna(0).astype(int) if "fresh_role" in F else 0
    # Fix 5 (Week 9): WR/TE anytime TDs are singles only until their calibration passes a backtest
    F["atd_ticket_ok"] = ~F.singles_only & F.pos_group.isin(["RB", "QB"])
    F["role_ok"] = role_gate(F)

    log("  fitting ATD model")
    F["p_attd"] = ATTDModel(feats=feats_for(factors)).fit(hist).predict(F)
    from .pipeline import backup_qb_haircut
    F = backup_qb_haircut(F, season, week)
    feats = prop_feature_list(df, PROP_GROUPS)
    legs = []
    for mk in MARKETS:
        log(f"  fitting props: {mk}")
        m = PropModel(mk, feats).fit(hist)
        d = F[eligible(F, mk)]
        if len(d):
            legs.append(m.curve(d))
    L = pd.concat(legs)
    keep = ["game_id", "team", "opp", "player_id", "name", "pos_group", "market", "k", "p", "singles_only",
            "role_ok", "injury_status", "fresh_role"]
    L = L[keep].reset_index(drop=True)

    # 2026 pre-game hit rate on the exact rung (x/y)
    cur = hist[hist.season == season]
    vals = {mk: cur.groupby("player_id")[mk].apply(list) for mk in MARKETS}
    hits, n = [], []
    for r in L.itertuples(index=False):
        v = vals[r.market].get(r.player_id, [])
        hits.append(sum(x >= r.k for x in v)); n.append(len(v))
    L["season_hits"], L["season_n"] = hits, n
    L["season_rate"] = np.where(L.season_n > 0, L.season_hits / L.season_n.clip(lower=1), np.nan)
    # Fix 4: worst game and average-in-losses on this stat (season to date), for the floor gate
    mins = {mk: cur.groupby("player_id")[mk].min() for mk in MARKETS}
    loss = {mk: cur[cur.won == 0].groupby("player_id")[mk].mean() for mk in MARKETS} if "won" in cur else {}
    L["season_min"] = [mins[r.market].get(r.player_id, np.nan) for r in L.itertuples(index=False)]
    L["loss_mean"] = [loss.get(r.market, pd.Series(dtype=float)).get(r.player_id, np.nan) for r in L.itertuples(index=False)]

    A = F.assign(p=F.p_attd, market="atd", k=np.nan)[
        ["game_id", "team", "opp", "player_id", "name", "pos_group", "market", "k", "p", "singles_only", "role_ok",
         "injury_status", "lam_team_rush", "lam_team_pass", "rush_share", "rec_share", "fresh_role", "atd_ticket_ok"]]
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
    log("  building tickets")
    card = build_card(L, A, corr)
    ctx = F.drop_duplicates(["game_id", "team"])[["game_id", "team", "is_home", "slot", "roof_type", "is_turf",
                                                  "wx_cat", "temp", "wind", "travel_miles", "tz_shift",
                                                  "rest_days", "implied_filled", "def_out_total"]]
    hdr = {"season": season, "week": week, "built": datetime.now().strftime("%Y-%m-%d %H:%M")}
    md = card_markdown(card, hdr, ctx)
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    (out / f"card_{season}_wk{week}.md").write_text(md)
    (out / f"card_{season}_wk{week}.json").write_text(json.dumps(
        {"header": hdr, "legs": card_legs_json(card)}, indent=1, default=str))
    from .early import apply_role_flags
    L = apply_role_flags(L, season, week)
    L.to_csv(out / f"prop_ladders_{season}_wk{week}.csv", index=False)
    F.drop(columns=[c for c in F.columns if F[c].dtype == object and c not in
                    ("game_id", "team", "opp", "player_id", "name", "pos_group", "position", "injury_status",
                     "wx_cat", "slot", "roof_type")]).to_parquet(out / f"props_features_{season}_wk{week}.parquet")
    A.to_csv(out / f"atd_{season}_wk{week}.csv", index=False)
    return card, md, L, A
