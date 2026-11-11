"""Team game-script metrics for the NFL: time of possession and penalties.

For each metric a team gets two opponent-adjusted ratings, fitted on
play-by-play since 2021 with recent games weighted more:

  time of possession   offence: seconds per drive it holds the ball
                       defence: seconds per drive it allows
  offensive penalties  how many its offence commits / how many the defence it faces draws
  defensive penalties  how many its defence commits / how many the offence it faces draws

Each rating is "per game (or per drive) versus the league average, against an
average opponent". Ratings are checked walk-forward: every week is predicted
using only earlier games, and compared with simply guessing the league average.

Usage: python3 team_metrics.py        (needs data from fetch_data.py)
Writes output/team_metrics.json.
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ST_PLAYS = {"kickoff", "punt", "extra_point", "field_goal"}
TUNE_SEASONS = (2022, 2023)   # settings are chosen on these seasons
TEST_FROM = 2024              # and scored on seasons from here on
WEEKS_PER_SEASON = 30         # spacing so an off-season counts as a long gap

METRICS = {
    # name: (column, what the two fitted effects mean)
    "top_per_drive": "sec_per_drive",
    "off_pen": "off_pen",
    "off_pen_yds": "off_pen_yds",
    "def_pen": "def_pen",
    "def_pen_yds": "def_pen_yds",
}


def clock_to_seconds(s: pd.Series) -> pd.Series:
    parts = s.str.split(":", expand=True).astype(float)
    return parts[0] * 60 + parts[1]


def load_team_games() -> pd.DataFrame:
    """One row per team per game: possession and penalty totals."""
    cols = ["game_id", "season", "week", "season_type", "home_team", "away_team", "posteam", "defteam",
            "fixed_drive", "drive_time_of_possession", "play_type", "special_teams_play",
            "penalty", "penalty_team", "penalty_yards"]
    frames = [pd.read_csv(f, usecols=cols, low_memory=False)
              for f in sorted(glob.glob(str(HERE / "data/pbp/play_by_play_*.csv.gz")))]
    if not frames:
        raise SystemExit("No play-by-play files found. Run: python3 fetch_data.py")
    pbp = pd.concat(frames, ignore_index=True)
    pbp = pbp[pbp.posteam.notna()]

    drives = (pbp.dropna(subset=["drive_time_of_possession"])
              .drop_duplicates(["game_id", "posteam", "fixed_drive"]).copy())
    drives["sec"] = clock_to_seconds(drives.drive_time_of_possession)
    top = drives.groupby(["game_id", "posteam"]).agg(top_sec=("sec", "sum"), drives=("sec", "size")).reset_index()
    top = top.rename(columns={"posteam": "team"})

    pen = pbp[(pbp.penalty == 1) & pbp.penalty_team.notna()].copy()
    special = (pen.special_teams_play == 1) | pen.play_type.isin(ST_PLAYS)
    pen["phase"] = np.where(special, "st", np.where(pen.penalty_team == pen.posteam, "off", "def"))
    pc = (pen.groupby(["game_id", "penalty_team", "phase"])
          .agg(n=("penalty", "size"), yds=("penalty_yards", "sum")).unstack("phase", fill_value=0))
    pc.columns = [f"{ph}_pen" if k == "n" else f"{ph}_pen_yds" for k, ph in pc.columns]
    pc = pc.reset_index().rename(columns={"penalty_team": "team"})

    meta = pbp.drop_duplicates("game_id")[["game_id", "season", "week", "season_type", "home_team", "away_team"]]
    rows = []
    for g in meta.itertuples(index=False):
        rows.append({"game_id": g.game_id, "season": g.season, "week": g.week, "team": g.home_team, "opp": g.away_team, "home": 1})
        rows.append({"game_id": g.game_id, "season": g.season, "week": g.week, "team": g.away_team, "opp": g.home_team, "home": 0})
    tg = pd.DataFrame(rows).merge(top, on=["game_id", "team"], how="left").merge(pc, on=["game_id", "team"], how="left")
    for c in ["off_pen", "off_pen_yds", "def_pen", "def_pen_yds", "st_pen", "st_pen_yds"]:
        tg[c] = tg.get(c, 0)
        tg[c] = tg[c].fillna(0)
    tg = tg.dropna(subset=["top_sec"])
    tg["sec_per_drive"] = tg.top_sec / tg.drives
    game_top = tg.groupby("game_id").top_sec.transform("sum")
    tg["top_share"] = tg.top_sec / game_top
    tg["t"] = (tg.season - tg.season.min()) * WEEKS_PER_SEASON + tg.week
    return tg.sort_values(["t", "game_id"]).reset_index(drop=True)


def fit(train: pd.DataFrame, col: str, now: int, half_life: float, ridge: float, teams: list[str]):
    """Weighted ridge fit of  y = league + own[team] + faced[opp] + home_edge * home."""
    n, k = len(train), len(teams)
    ix = {t: i for i, t in enumerate(teams)}
    X = np.zeros((n, 2 * k + 2))
    X[:, 0] = 1
    X[:, 1] = train.home.values - 0.5
    X[np.arange(n), 2 + train.team.map(ix).values] = 1
    X[np.arange(n), 2 + k + train.opp.map(ix).values] = 1
    w = 0.5 ** ((now - train.t.values) / half_life)
    pen = np.full(2 * k + 2, ridge)
    pen[:2] = 0
    A = X.T @ (X * w[:, None]) + np.diag(pen)
    b = X.T @ (w * train[col].values)
    coef = np.linalg.solve(A, b)
    return {"league": coef[0], "home": coef[1],
            "own": dict(zip(teams, coef[2:2 + k])), "faced": dict(zip(teams, coef[2 + k:]))}


def predict(m, team, opp, home):
    return m["league"] + m["home"] * (home - 0.5) + m["own"].get(team, 0) + m["faced"].get(opp, 0)


def walk_forward(tg, col, half_life, ridge, teams, seasons):
    """Predict every team-game in `seasons` from earlier games only."""
    out = []
    for t in sorted(tg[tg.season.isin(seasons)].t.unique()):
        train = tg[tg.t < t]
        if len(train) < 200:
            continue
        m = fit(train, col, t, half_life, ridge, teams)
        w = 0.5 ** ((t - train.t.values) / half_life)
        base = float(np.average(train[col].values, weights=w))
        for r in tg[tg.t == t].itertuples(index=False):
            out.append((getattr(r, col), predict(m, r.team, r.opp, r.home), base, r.game_id, r.team))
    return pd.DataFrame(out, columns=["actual", "pred", "base", "game_id", "team"])


def score(df):
    err_m, err_b = df.actual - df.pred, df.actual - df.base
    return {"games": int(len(df) / 2),
            "avg_miss_model": round(float(err_m.abs().mean()), 3),
            "avg_miss_league_average": round(float(err_b.abs().mean()), 3),
            "skill_vs_league_average": round(float(1 - (err_m ** 2).mean() / (err_b ** 2).mean()), 4),
            "correlation": round(float(np.corrcoef(df.actual, df.pred)[0, 1]), 3)}


def implied(ml):
    return -ml / (-ml + 100) if ml < 0 else 100 / (ml + 100)


def main():
    tg = load_team_games()
    teams = sorted(tg[tg.season == tg.season.max()].team.unique())
    tg = tg[tg.team.isin(teams) & tg.opp.isin(teams)]
    test_seasons = [s for s in sorted(tg.season.unique()) if s >= TEST_FROM]

    settings, validation, models = {}, {}, {}
    now = int(tg.t.max()) + 1
    for name, col in METRICS.items():
        best = None
        for hl in (8, 16, 30):
            for ridge in (2, 6, 15, 40):
                wf = walk_forward(tg, col, hl, ridge, teams, TUNE_SEASONS)
                mse = float(((wf.actual - wf.pred) ** 2).mean())
                if best is None or mse < best[0]:
                    best = (mse, hl, ridge)
        _, hl, ridge = best
        settings[name] = {"half_life_weeks": hl, "ridge": ridge}
        validation[name] = score(walk_forward(tg, col, hl, ridge, teams, test_seasons))
        models[name] = fit(tg, col, now, hl, ridge, teams)

    # Possession share, checked the same way: predicted from the two teams' seconds-per-drive forecasts.
    s = settings["top_per_drive"]
    wf = walk_forward(tg, "sec_per_drive", s["half_life_weeks"], s["ridge"], teams, test_seasons)
    g = wf.merge(wf, on="game_id", suffixes=("", "_o"))
    g = g[g.team != g.team_o]
    share_pred = g.pred / (g.pred + g.pred_o)
    share_act = tg.set_index(["game_id", "team"]).top_share.reindex(list(zip(g.game_id, g.team))).values
    validation["top_share"] = {
        "games": int(len(g) / 2),
        "avg_miss_model": round(float(np.abs(share_act - share_pred).mean()), 4),
        "avg_miss_league_average": round(float(np.abs(share_act - 0.5).mean()), 4),
        "skill_vs_league_average": round(float(1 - ((share_act - share_pred) ** 2).mean() / ((share_act - 0.5) ** 2).mean()), 4),
        "correlation": round(float(np.corrcoef(share_act, share_pred)[0, 1]), 3),
    }

    # The point spread says more about possession than the ratings do (favourites sit on the
    # ball late), so the possession forecast blends the two. Weights are fitted on walk-forward
    # forecasts before the test seasons, and scored on the test seasons.
    lines = pd.read_csv(HERE / "data/games.csv")[["game_id", "spread_line"]]
    wf_all = walk_forward(tg, "sec_per_drive", s["half_life_weeks"], s["ridge"], teams,
                          [x for x in sorted(tg.season.unique()) if x >= TUNE_SEASONS[0]])
    b = wf_all.merge(wf_all, on="game_id", suffixes=("", "_o"))
    b = b[b.team != b.team_o].merge(tg[["game_id", "team", "top_share", "home", "season"]], on=["game_id", "team"]).merge(lines, on="game_id")
    b["rate"] = b.pred / (b.pred + b.pred_o) - 0.5
    b["fav"] = np.where(b.home == 1, b.spread_line, -b.spread_line)  # points this team is favoured by
    b = b.dropna(subset=["fav"])
    tr, te = b[b.season < TEST_FROM], b[b.season >= TEST_FROM]
    w_blend, *_ = np.linalg.lstsq(np.c_[tr[["rate", "fav"]]], tr.top_share - 0.5, rcond=None)
    p_te = 0.5 + np.c_[te[["rate", "fav"]]] @ w_blend
    validation["top_share_with_spread"] = {
        "games": int(len(te) / 2),
        "avg_miss_model": round(float(np.abs(te.top_share - p_te).mean()), 4),
        "avg_miss_league_average": round(float(np.abs(te.top_share - 0.5).mean()), 4),
        "skill_vs_league_average": round(float(1 - ((te.top_share - p_te) ** 2).mean() / ((te.top_share - 0.5) ** 2).mean()), 4),
        "correlation": round(float(np.corrcoef(te.top_share, p_te)[0, 1]), 3),
    }
    w_blend, *_ = np.linalg.lstsq(np.c_[b[["rate", "fav"]]], b.top_share - 0.5, rcond=None)
    settings["possession_blend"] = {"weight_on_ratings": round(float(w_blend[0]), 3),
                                    "share_per_point_of_spread": round(float(w_blend[1]), 5)}

    def ranks(d, low_is_good):
        order = sorted(d, key=lambda t: d[t], reverse=not low_is_good)
        return {t: i + 1 for i, t in enumerate(order)}

    top, op, opy, dp, dpy = (models[k] for k in METRICS)
    r_to, r_td = ranks(top["own"], False), ranks(top["faced"], True)
    r_op, r_dp = ranks(op["own"], True), ranks(dp["own"], True)
    last = tg[tg.season == tg.season.max()].groupby("team")
    team_out = {}
    for t in teams:
        team_out[t] = {
            "games_this_season": int(last.size().get(t, 0)),
            "top_share_this_season": round(float(last.top_share.mean().get(t, np.nan)), 4),
            "top_offence_sec_per_drive": round(top["own"][t], 1), "top_offence_rank": r_to[t],
            "top_defence_sec_per_drive": round(top["faced"][t], 1), "top_defence_rank": r_td[t],
            "off_pen_per_game": round(op["league"] + op["own"][t], 2), "off_pen_rank": r_op[t],
            "off_pen_yds_per_game": round(opy["league"] + opy["own"][t], 1),
            "off_pen_drawn_by_defence": round(op["faced"][t], 2),
            "def_pen_per_game": round(dp["league"] + dp["own"][t], 2), "def_pen_rank": r_dp[t],
            "def_pen_yds_per_game": round(dpy["league"] + dpy["own"][t], 1),
            "def_pen_drawn_by_offence": round(dp["faced"][t], 2),
        }

    # Upcoming week, with the betting market's lines alongside.
    games = pd.read_csv(HERE / "data/games.csv")
    up = games[games.result.isna() & games.home_team.isin(teams)].sort_values(["gameday", "game_id"])
    games_out = []
    if len(up):
        first = up.iloc[0]
        for gm in up[(up.season == first.season) & (up.week == first.week)].itertuples(index=False):
            h, a = gm.home_team, gm.away_team
            neutral = gm.location == "Neutral"
            sh = predict(top, h, a, 0.5 if neutral else 1)
            sa = predict(top, a, h, 0.5 if neutral else 0)
            share = sh / (sh + sa)
            basis = "ratings only (no spread posted)"
            if not pd.isna(gm.spread_line):
                share = 0.5 + w_blend[0] * (share - 0.5) + w_blend[1] * gm.spread_line
                basis = "ratings and spread"
            market = None
            if not pd.isna(gm.spread_line) and not pd.isna(gm.total_line):
                market = {"home_spread": float(-gm.spread_line), "total": float(gm.total_line),
                          "home_implied_points": round((gm.total_line + gm.spread_line) / 2, 1),
                          "away_implied_points": round((gm.total_line - gm.spread_line) / 2, 1)}
                if not pd.isna(gm.home_moneyline) and not pd.isna(gm.away_moneyline):
                    ph, pa = implied(gm.home_moneyline), implied(gm.away_moneyline)
                    market.update({"home_moneyline": int(gm.home_moneyline), "away_moneyline": int(gm.away_moneyline),
                                   "home_win_chance_no_margin": round(ph / (ph + pa), 4)})
            side = lambda t, o, hm: {
                "off_pen": round(predict(op, t, o, hm), 2), "off_pen_yds": round(predict(opy, t, o, hm), 1),
                "def_pen": round(predict(dp, t, o, hm), 2), "def_pen_yds": round(predict(dpy, t, o, hm), 1)}
            games_out.append({
                "game_id": gm.game_id, "gameday": gm.gameday, "away": a, "home": h, "market": market,
                "possession": {"basis": basis, "home_share": round(share, 4), "home_minutes": round(share * 60, 1),
                               "away_minutes": round((1 - share) * 60, 1)},
                "penalties": {"home": side(h, a, 0.5 if neutral else 1), "away": side(a, h, 0.5 if neutral else 0)},
            })

    out = {
        "as_of": {"season": int(tg.season.max()), "through_week": int(tg[tg.season == tg.season.max()].week.max()),
                  "seasons_used": f"{int(tg.season.min())}-{int(tg.season.max())}", "team_games": int(len(tg))},
        "league_average": {"sec_per_drive": round(top["league"], 1),
                           "off_pen_per_game": round(op["league"], 2), "off_pen_yds_per_game": round(opy["league"], 1),
                           "def_pen_per_game": round(dp["league"], 2), "def_pen_yds_per_game": round(dpy["league"], 1)},
        "settings": settings,
        "validation": {"test_seasons": f"{TEST_FROM}-{int(tg.season.max())}", **validation},
        "teams": team_out,
        "games": games_out,
    }
    (HERE / "output").mkdir(exist_ok=True)
    json.dump(out, open(HERE / "output/team_metrics.json", "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("as_of", "league_average", "settings", "validation")}, indent=1))
    print(json.dumps(games_out[0], indent=1) if games_out else "no upcoming games")
    best = sorted(team_out, key=lambda t: team_out[t]["top_offence_rank"])[:5]
    print("top-5 possession offences:", [(t, team_out[t]["top_offence_sec_per_drive"]) for t in best])


if __name__ == "__main__":
    main()
