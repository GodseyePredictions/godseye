#!/usr/bin/env python3
"""ATTD engine CLI.

  python run.py download                       # pull/refresh nflverse data
  python run.py backtest                       # out-of-sample evaluation + fit leg correlations
  python run.py project --season 2026 --week 9 [--out "Player A,Player B"] [--odds odds.csv]
"""
import argparse
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
CORR = ROOT / "models" / "correlations.json"


def cmd_refresh(a):
    from attd.watch import refresh
    refresh(a.season, a.week, pull=not a.no_pull)


def cmd_download(a):
    from attd.data import download
    download(range(a.first, a.season + 1), force_current=a.season)


def cmd_backtest(a):
    from attd import correlation as C
    from attd.pipeline import backtest
    seasons = list(range(a.first, a.season + 1))
    tests = [int(x) for x in a.test.split(",")]
    res, cal, by_pos, imp, tm, out, abl = backtest(seasons, tests)
    corr = C.fit_correlations(out)
    CORR.parent.mkdir(exist_ok=True)
    C.save(corr, CORR)
    OUT.mkdir(exist_ok=True)
    out.to_csv(OUT / "backtest_predictions.csv", index=False)
    lines = ["# ATTD backtest (out-of-sample: " + a.test + ")", "", "## Model comparison",
             res.round(4).to_markdown(), "", "## Calibration (final model)", cal.round(3).to_markdown(),
             "", "## By position", by_pos.round(4).to_markdown(), "", "## Top features (gain)",
             imp.head(25).round(0).to_frame("gain").to_markdown(), "",
             f"Team TD residual same-game correlation: {tm.game_corr:.3f}", "",
             "## Factor report card (out-of-sample log-loss change; positive = factor helps)",
             f"Base model log loss {abl.attrs['base_ll']:.4f} -> full model {abl.attrs['full_ll']:.4f}", "",
             abl.round(5).to_markdown(), "",
             "## Leg correlations (Gaussian copula rho)",
             pd.Series({k: v for k, v in corr.items() if not k.startswith("_")}).round(3)
             .to_frame("rho").to_markdown()]
    (OUT / "backtest_report.md").write_text("\n".join(lines))
    print("\n".join(lines))


def cmd_project(a):
    from attd import correlation as C
    from attd.parlay import attach_odds, build_parlays
    from attd.pipeline import project
    extra = [x.strip() for x in a.out.split(",")] if a.out else []
    groups = a.factors if a.factors in ("default", "all", "none") else [g.strip() for g in a.factors.split(",")]
    proj, tm = project(a.season, a.week, extra_out=extra, factors=groups)
    OUT.mkdir(exist_ok=True)
    tag = f"{a.season}_wk{a.week}"
    proj.to_csv(OUT / f"projections_{tag}.csv", index=False)
    games = proj.drop_duplicates(["game_id", "team"])[["game_id", "team", "is_home", "slot", "roof_type",
                                                         "is_turf", "wx_cat", "temp", "wind", "travel_miles",
                                                         "tz_shift", "rest_days", "implied_filled",
                                                         "def_out_total"]].sort_values("game_id")
    print("\n=== Game environment (def_out_total = opponent defensive snap-share ruled Out/Doubtful) ===")
    print(games.round(1).to_string(index=False))
    show = proj[proj.p_attd >= a.min_p][["game_id", "team", "name", "position", "injury_status", "p_attd",
                                          "fair_american", "singles_only", "split_home_away", "split_slot", "split_wx_bad"]]
    print(f"\n=== ATTD projections {a.season} week {a.week} (p >= {a.min_p}) ===")
    print(show.round(3).to_string(index=False))
    if a.odds:
        corr = C.load(CORR) if CORR.exists() else {"OPP": 0.05, "TM:default": -0.05}
        legs = attach_odds(proj, pd.read_csv(a.odds))
        legs.to_csv(OUT / f"edges_{tag}.csv", index=False)
        print("\n=== Single-leg edges ===")
        print(legs[["name", "team", "p_attd", "odds", "fair_american", "implied", "edge", "ev", "kelly"]]
              .round(3).to_string(index=False))
        par = build_parlays(legs, corr, sgp_haircut=a.sgp_haircut, min_leg_p=a.min_leg_p)
        if len(par):
            par.to_csv(OUT / f"parlays_{tag}.csv", index=False)
            print("\n=== Best parlays (ranked by quarter-Kelly log growth) ===")
            print(par.round(4).to_string(index=False))
        else:
            print("\nNo +EV legs available to build parlays.")


def cmd_card(a):
    from attd.week import build_week
    extra = [x.strip() for x in a.out.split(",")] if a.out else []
    card, md, L, A = build_week(a.season, a.week, extra_out=extra)
    print(md)
    print(f"\nSaved outputs/card_{a.season}_wk{a.week}.md (+ .json for grading)")


def cmd_slip(a):
    from attd.atd_slip import am, build_slip, ticket_sets
    from attd.slip_pdf import render
    sc = pd.read_csv(ROOT / "data" / "schedules.csv")
    g = sc[(sc.season == a.season) & (sc.week == a.week) & sc.home_score.isna()]
    if a.day:
        g = g[g.gameday == a.day]
    proj = pd.read_csv(OUT / f"projections_{a.season}_wk{a.week}.csv")
    P, T, _ = ticket_sets(proj, g.game_id.tolist())
    when = pd.Timestamp(a.day).strftime("%A %b %-d %Y") if a.day else f"Week {a.week}"
    title = f"ATD Slip — Week {a.week}, {when}"
    notes = [l.strip() for l in open(ROOT / "attd" / "slip_notes.txt") if l.strip()]
    name = f"ATD_Slip_{a.season}_Wk{a.week}" + (f"_{a.day}" if a.day else "")
    render(OUT / f"{name}.pdf", P, T, g, title, notes, n_games=len(g))
    (OUT / f"{name}.md").write_text(build_slip(proj, g.game_id.tolist(), title))
    for t in T:
        print(f"{t['n']}-leg {t['p']:.2%} fair {am(t['p'])}")
    print(f"Saved outputs/{name}.pdf")


def cmd_site(a):
    from attd.site import write_site
    p = write_site(a.season, a.week)
    print(f"Wrote {p} ({p.stat().st_size // 1024} KB). Publish/redeploy it as the God's Eye artifact.")


def cmd_grade_card(a):
    from attd.grading import grade_card
    print(grade_card(a.season, a.week))


def cmd_grade(a):
    from attd.grade import head_to_head, weekly_boards
    from attd.pipeline import walkforward_season
    wf_path = OUT / f"walkforward_{a.season}.csv"
    if a.rebuild or not wf_path.exists():
        walkforward_season(a.season, range(1, 23)).to_csv(wf_path, index=False)
    wf = pd.read_csv(wf_path)
    bb, pos, dis, un, m = head_to_head(a.ledger, wf)
    print(bb.round(3).to_string()); print(pos.round(3).to_string()); print(dis.round(2).to_string(index=False))
    print(weekly_boards(wf).round(1).to_string())
    m.to_csv(OUT / "ledger_head_to_head.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("grade")
    g.add_argument("--season", type=int, default=2026)
    g.add_argument("--ledger", default=str(ROOT / "ledger" / "NFL-Algo-Complete-Ledger.md"))
    g.add_argument("--rebuild", action="store_true")
    c = sp.add_parser("card", help="full weekly pack: props SGPs + ATD tickets + combos")
    c.add_argument("--season", type=int, default=2026)
    c.add_argument("--week", type=int, required=True)
    c.add_argument("--out", default="")
    sl = sp.add_parser("slip", help="ATD slip PDF with 4/6/8/10/12-leg correlated tickets")
    sl.add_argument("--season", type=int, default=2026)
    sl.add_argument("--week", type=int, required=True)
    sl.add_argument("--day", default="", help="YYYY-MM-DD to restrict to one day's games")
    si = sp.add_parser("site", help="regenerate the God's Eye Predictions page from the latest build")
    si.add_argument("--season", type=int, default=2026)
    si.add_argument("--week", type=int, required=True)
    rf = sp.add_parser("refresh", help="re-pull injuries/rosters/lines/forecasts, diff vs last snapshot, flag shipped legs")
    rf.add_argument("--season", type=int, default=2026)
    rf.add_argument("--week", type=int, required=True)
    rf.add_argument("--no-pull", action="store_true")
    gc = sp.add_parser("grade-card", help="grade a saved card against official stat lines")
    gc.add_argument("--season", type=int, default=2026)
    gc.add_argument("--week", type=int, required=True)
    for name in ("download", "backtest", "project"):
        p = sp.add_parser(name)
        p.add_argument("--season", type=int, default=2026)
        p.add_argument("--first", type=int, default=2021)
        if name == "backtest":
            p.add_argument("--test", default="2025,2026")
        if name == "project":
            p.add_argument("--week", type=int, required=True)
            p.add_argument("--out", default="", help="comma-separated player names to force inactive")
            p.add_argument("--odds", default="", help="CSV with columns player,odds (American)")
            p.add_argument("--min-p", type=float, default=0.15)
            p.add_argument("--min-leg-p", type=float, default=0.18)
            p.add_argument("--sgp-haircut", type=float, default=0.0)
            p.add_argument("--factors", default="default",
                           help="default | all | none | comma list of groups, e.g. stadium_weather,game_time")
    a = ap.parse_args()
    {"download": cmd_download, "backtest": cmd_backtest, "project": cmd_project, "grade": cmd_grade,
     "card": cmd_card, "grade-card": cmd_grade_card, "slip": cmd_slip, "site": cmd_site, "refresh": cmd_refresh}[a.cmd](a)


if __name__ == "__main__":
    main()
