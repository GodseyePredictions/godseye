"""Export everything the God's Eye page needs into one JSON blob and inject it into the HTML template."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .atd_slip import CUSHION, joint
from .intel import intel, load_defenders, risk_line
from .pick_slip import SIZES, _kick, select_picks

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"


def _f(x, nd=3):
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return None
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def legs_js(df):
    return [{"id": r.player_id, "mk": r.market, "k": None if pd.isna(r.k) else int(r.k), "p": round(float(r.p), 4),
             "fit": round(float(r.fit), 2), "why": list(r.fit_why), "hits": None if pd.isna(r.season_hits) else int(r.season_hits),
             "n": None if pd.isna(r.season_n) else int(r.season_n)} for r in df.itertuples()]


def build_data(season: int, week: int) -> dict:
    F = pd.read_parquet(OUT / f"projection_features_{season}_wk{week}.parquet")
    sched = pd.read_csv(ROOT / "data" / "schedules.csv")
    S = sched[(sched.season == season) & (sched.week == week) & sched.home_score.isna()].set_index("game_id")
    # games already kicked off (ET kickoff before now) stay on the site for building/grading but leave the ticket pools
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York"))
    kick = pd.to_datetime(S.gameday + " " + S.gametime).dt.tz_localize("America/New_York")
    S = S.assign(started=(kick <= now_et).values)
    F = F[F.game_id.isin(S.index)].copy()
    F_all = F.copy()
    F = F[~F.game_id.isin(S[S.started].index)].copy()   # ticket pools: upcoming games only
    corr_atd = json.loads((ROOT / "models" / "correlations.json").read_text())
    corr_legs = {k: v for k, v in json.loads((ROOT / "models" / "leg_correlations.json").read_text()).items()
                 if not k.startswith("_n")}

    games = []
    for g, r in S.sort_values(["gameday", "gametime"]).iterrows():
        q = F[F.game_id == g]
        h = q[q.is_home == 1].iloc[0] if (q.is_home == 1).any() else None
        imp = q.groupby("team").implied_filled.first().to_dict()
        games.append({
            "id": g, "away": r.away_team, "home": r.home_team, "day": r.gameday, "weekday": r.weekday,
            "started": bool(r.started),
            "kick": _kick(r.gametime), "venue": r.stadium, "spread_home": _f(r.spread_line, 1),
            "total": _f(r.total_line, 1),
            "implied": {k: _f(v, 1) for k, v in imp.items()},
            "roof": None if h is None else str(h.roof_type), "turf": None if h is None else int(h.is_turf),
            "wx": None if h is None else str(h.wx_cat), "temp": None if h is None else _f(h.temp, 0),
            "wind": None if h is None else _f(h.wind, 0), "slot": None if h is None else str(h.slot),
            "qb": {t: (lambda q: None if q.empty else q.iloc[0]["name"])(
                F[(F.game_id == g) & (F.team == t) & (F.pos_group == "QB")].sort_values(
                    ["offense_pct_lag1", "offense_pct_e3"], ascending=False)) for t in (r.away_team, r.home_team)}})

    players = []
    DF = load_defenders()
    for _, r in F_all.sort_values("p_attd", ascending=False).iterrows():
        bullets = intel(r, F_all, DF, S.loc[r.game_id], market="atd")
        risk = risk_line(r, "atd").replace("<b>Risk:</b> ", "")
        players.append({
            "id": r.player_id, "name": r["name"], "team": r.team, "opp": r.opp, "game": r.game_id,
            "pos": r.pos_group, "home": int(r.is_home), "p": _f(r.p_attd, 4),
            "singles": bool(r.singles_only) if not pd.isna(r.singles_only) else False,
            "inj": r.injury_status if isinstance(r.injury_status, str) else None,
            "missed4": int(r.games_missed_last4) if not pd.isna(r.games_missed_last4) else 0,
            "back": int(r.games_back) if "games_back" in F.columns and not pd.isna(r.games_back) else 99,
            "cushion": CUSHION.get(r.pos_group, 0.04),
            "intel": {
                "snap": _f(r.offense_pct_e3, 2), "carries": _f(r.carries_e3, 1), "targets": _f(r.targets_e3, 1),
                "i10": _f(r.rush_i10_e3, 2), "i10_sh": _f(r.sh_rush_i10_e3, 2), "rz_car_sh": _f(r.sh_rush_rz_e3, 2),
                "rz_tgt": _f(r.tgt_rz_e3, 2), "rz_tgt_sh": _f(r.sh_tgt_rz_e3, 2), "ez_tgt": _f(r.ez_tgt_e3, 2),
                "ez_sh": _f(r.sh_ez_tgt_e3, 2), "xtd": _f(r.xtd_e3, 2), "td": _f(r.td_e3, 2),
                "season_tds": _f(r.season_tds, 0), "td_games": _f(r.season_td_games, 0),
                "games": _f(r.season_games, 0), "team_rush_td": _f(r.lam_team_rush, 2),
                "team_pass_td": _f(r.lam_team_pass, 2), "rush_share": _f(r.rush_share, 2),
                "rec_share": _f(r.rec_share, 2), "spread": _f(r.spread, 1), "implied": _f(r.implied_filled, 1)},
            "why": bullets, "risk": risk,
            "parts": dict(zip(["outlook", "role", "form", "matchup", "scheme", "game"], bullets)),
            "riskm": {mk: risk_line(r, mk).replace("<b>Risk:</b> ", "") for mk in
                      ("carries", "rush_yds", "rec", "rec_yds", "pass_att", "pass_yds", "pass_td")}})

    # prop ladders (from the weekly card build, personnel overrides applied)
    props = {}
    lad = OUT / f"prop_ladders_{season}_wk{week}.csv"
    if lad.exists():
        L = pd.read_csv(lad)
        L = L[L.game_id.isin(S.index) & L.player_id.isin(F_all.player_id)]
        for (pid, mk), q in L.groupby(["player_id", "market"]):
            q = q.sort_values("k")
            props.setdefault(pid, {})[mk] = {
                "k": [int(x) for x in q.k], "p": [round(float(x), 4) for x in q.p],
                "hits": [int(x) for x in q.season_hits], "n": int(q.season_n.iloc[0])}

    # per-player volume numbers (recent EWMA + season-to-date) for props intel in the SGP builder
    pf0 = OUT / f"props_features_{season}_wk{week}.parquet"
    if pf0.exists():
        PF0 = pd.read_parquet(pf0).drop_duplicates("player_id").set_index("player_id")
        stats = ["carries", "rush_yds", "rec", "tgt", "rec_yds", "pass_att", "pass_yds", "pass_td"]
        for pl in players:
            if pl["id"] in PF0.index:
                r = PF0.loc[pl["id"]]
                pl["vol"] = {s: [_f(r.get(f"{s}_p3"), 1), _f(r.get(f"{s}_std"), 1)] for s in stats}

    # last-5 hit strip per (player, market, rung) from official box scores this season
    try:
        SW = pd.read_parquet(ROOT / "data" / f"stats_week_{season}.parquet")
        SW = SW[SW.season_type == "REG"].sort_values("week")
        smap = {"carries": "carries", "rush_yds": "rushing_yards", "rec": "receptions", "rec_yds": "receiving_yards",
                "pass_att": "attempts", "pass_yds": "passing_yards", "pass_td": "passing_tds"}
        hist = {pid: g for pid, g in SW.groupby("player_id")}
        for pid, mk_d in props.items():
            g = hist.get(pid)
            for mk, m in mk_d.items():
                if g is None or smap[mk] not in g:
                    m["l5"] = []
                    continue
                vals = g[smap[mk]].fillna(0).tail(5).tolist()
                m["l5"] = [[int(v >= k) for v in vals] for k in m["k"]]
    except Exception as e:  # noqa: BLE001
        print("  [l5] skipped:", e)
    # weekly track record: model's top-16 ATD board, hits vs expected (walk-forward, no look-ahead)
    weekly = []
    wf = OUT / f"walkforward_{season}.csv"
    if wf.exists():
        W = pd.read_csv(wf)
        for w, g in W.groupby("week"):
            if g.game_id.nunique() < 3:
                continue
            b = g.nlargest(16, "p_attd")
            weekly.append({"week": int(w), "hits": int(b.label.sum()), "expected": round(float(b.p_attd.sum()), 1)})
    # algorithm picks: nested ATD parlays + per-game props tickets from the saved card
    from .atd_slip import STYLES, _pick_style
    from .early import atd_parlay_pool, backup_qb_teams, build_window
    bq_teams = backup_qb_teams(season, week)
    from .early import apply_overrides as _ao
    ok, held_all = atd_parlay_pool(_ao(F), bq_teams)
    algo_atd, algo_atd_styles = [], {}
    for st, meta in STYLES.items():
        sizes = (4, 6, 8) if st == "air" else SIZES
        picks_s = _pick_style(ok, max(sizes), st)
        tk = []
        for n in sizes:
            legs = picks_s.head(n)
            if len(legs) < n:
                break
            tk.append({"n": n, "legs": list(legs.player_id), "p": round(joint(legs, corr_atd), 5)})
        algo_atd_styles[st] = {"label": meta["label"], "desc": meta["desc"], "tickets": tk}
    algo_atd = algo_atd_styles["chalk"]["tickets"]
    # single-game / short-slate fallback: in-game ATD doubles and trebles among parlay-eligible RB/QB legs
    from itertools import combinations
    atd_combos = []
    for g in S.index:
        # in-game scorers: all positions, ranked on the play-at probability (model minus the position cushion)
        el = ok[(ok.game_id == g) & (ok.p_attd >= 0.20)]
        el = el.assign(_play=el.p_attd - el.pos_group.map(CUSHION).fillna(0.05)).sort_values("_play", ascending=False)
        el = el.head(7)
        for n in (2, 3, 4):
            for idx in combinations(range(len(el)), n):
                legs = el.iloc[list(idx)]
                pj = joint(legs, corr_atd)
                atd_combos.append({"game": g, "n": n, "legs": list(legs.player_id), "p": round(pj, 5),
                                   "p_indep": round(float(legs.p_attd.prod()), 5)})
    atd_combos.sort(key=lambda t: (t["n"], -t["p"]))
    atd_combos = [t for n in (2, 3, 4) for t in [x for x in atd_combos if x["n"] == n][:3]]
    algo_props = []
    cj = OUT / f"card_{season}_wk{week}.json"
    if cj.exists():
        legs = pd.DataFrame(json.loads(cj.read_text())["legs"])
        legs = legs[legs.game_id.isin(S.index) & legs.player_id.isin(F.player_id)]
        for t, q in legs.groupby("ticket", sort=False):
            if "|floor" in t or "|aggressive" in t or t.startswith("combo"):
                algo_props.append({"ticket": t, "p": _f(q.ticket_p.iloc[0], 4),
                                   "legs": [{"id": r.player_id, "mk": r.market, "k": None if pd.isna(r.k) else int(r.k)}
                                            for r in q.itertuples()]})
    # algorithm SGP per game (best leg per position slot) with per-leg intel
    algo_sgp_out = []
    pf = OUT / f"props_features_{season}_wk{week}.parquet"
    if lad.exists() and pf.exists():
        from .intel import MK_LABEL
        from .tickets import algo_sgp
        corr_all = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
        L = pd.read_csv(lad)
        L = L[L.game_id.isin(S.index) & L.player_id.isin(F.player_id)]
        PF = pd.read_parquet(pf)
        DF = load_defenders()
        for g in [x["id"] for x in games]:
            C, alts, pj, pi = algo_sgp(L, g, corr_all)
            if C.empty:
                continue
            legs_out = []
            for r in C.itertuples():
                fr = PF[(PF.player_id == r.player_id) & (PF.game_id == g)]
                why = []
                if len(fr):
                    rung = (f"<b>This line:</b> {int(r.k)}+ {MK_LABEL[r.market]}: cleared in {int(r.season_hits)} of "
                            f"{int(r.season_n)} games this season; model {r.p:.0%}.")
                    why = intel(fr.iloc[0], PF[PF.game_id.isin(S.index)], DF, S.loc[g], market=r.market, rung_line=rung)
                    why.append(risk_line(fr.iloc[0], r.market))
                legs_out.append({"slot": r.slot, "id": r.player_id, "mk": r.market, "k": int(r.k), "p": round(r.p, 4),
                                 "hits": int(r.season_hits), "n": int(r.season_n), "why": why,
                                 "alts": [{"id": a["player_id"], "mk": a["market"], "k": int(a["k"]),
                                           "p": round(a["p"], 4)} for a in alts.get(r.slot, [])]})
            algo_sgp_out.append({"game": g, "legs": legs_out, "p": round(pj, 5), "p_indep": round(pi, 5)})
    # personnel log + singles-only list for the platform
    plog_f = OUT / f"personnel_log_{season}_wk{week}.json"
    plog = json.loads(plog_f.read_text()) if plog_f.exists() else []
    teams_on_slate = {t for g in games for t in (g["away"], g["home"])}
    plog = [x for x in plog if x.get("team") in teams_on_slate]
    singles = [{"name": p["name"], "team": p["team"], "pos": p["pos"], "p": p["p"],
                "why": p["inj"] or f"returning: {p['back']} game{'s' if p['back'] != 1 else ''} back since his last absence (rule: fewer than 2)"}
               for p in players if p["singles"]]
    inj_f = ROOT / "data" / "inj_2026.parquet"
    data_asof = datetime.fromtimestamp(inj_f.stat().st_mtime, tz=timezone.utc).strftime("%a %b %-d, %H:%M UTC") \
        if inj_f.exists() else None
    rules = {
        "factors": [
            ["Where the match is", "stadium, international, travel miles"],
            ["Time zones / body clock", "time-zone shift, kickoff hour on the team's home clock"],
            ["Kickoff slot", "early / afternoon / night / international morning"],
            ["Turf vs grass, indoor vs outdoor", "surface and roof"],
            ["Weather", "NWS kickoff-hour forecast: sun, cloud, rain, snow, fog, temperature, wind; indoor = neutral"],
            ["Home vs away", "plus each player's home/away × roof / surface / slot / weather splits (shrunk)"],
            ["Rest", "short week, off a bye"],
            ["OC play-calling", "pass rate over expected (all / red zone / inside 10), WR-TE-RB target split, deep / short / screens, play-action, RPO, motion, pace, QB runs"],
            ["DC scheme", "blitz rate, pass rushers, box counts, deep / YAC / aDOT allowed, TDs allowed by position, red-zone TD% allowed"],
            ["WR vs corners & safeties", "active CB + S ratings (pass breakups, INTs), unit availability, yards/target and catch rate allowed to WRs"],
            ["RB: O-line vs D-line / LBs", "own yards per carry and stuff rate vs the front's YPC allowed, stuffs, sacks; active DL + LB ratings"],
            ["TE vs linebackers & safeties", "active LB + S ratings, yards/target and catch rate allowed to TEs"],
            ["Who they're against", "the named defenders projected to play, with recent production"],
            ["Injuries, both sides", "opponent defenders out (snap-weighted), own O-line out, official report + personnel overrides"],
            ["Player route profile", "deep / short target share, air yards, YAC"],
            ["Market anchor", "Vegas implied team total and spread"]],
        "standing": [
            "Rosters and injuries refreshed before every build; official inactives applied ~90 min before kickoff, then re-run.",
            "bet365 milestones only: yards from 20+ in 10s, carries 10/15/20/25, pass yards by 25 from 150, attempts by 5, receptions from 1+, passing TDs 1+/2+/3+.",
            "Props parlays never contain TD legs; ATDs are their own ticket.",
            "Picks come from the engine only: no analyst or media picks. User reads go into the personnel file and are logged on this page.",
            "Grading is as shipped: no retroactive swaps. Every graded week produces an algorithm change.",
            "Questionable players, and players returning from a 2+ game absence (missed 2+ of the team's last 4), are singles only.",
            "One player per team on ATD parlays (teammates split TDs). Cross-game props combos: ≤2 legs per game, ≤1 per team.",
            "When a starting QB is out, the depth-chart backup is projected to start (singles only until he has recent starts).",
            "Backup-QB offences are kept off anytime-TD parlays, and their passing and receiving legs are kept off the script SGPs (interim rule after the Week 9 Monday grade). Rushing legs stay; the players remain on the board as singles.",
            "A back who inherits the job this week (under 7 carries a game recently) is an anytime-TD single, not a parlay leg, until he has a real workload on record.",
            "ESPN's injury feed is swept before each build; players it rules out ahead of the official file are logged as overrides."],
        "pending": [
            "Backup-QB downgrade: receivers are not yet explicitly repriced when a backup starts; the Vegas total carries most of it. A QB-quality factor is proposed and needs a backtest before it goes live."],
        "stats": [
            ["ATD model, 2025–26 holdout (n ≈ 9,900 player-games)", "log loss 0.387, AUC 0.76; position-average baseline 0.444"],
            ["ATD vs your old engine, 223 shipped legs", "0.646 vs 0.652 log loss, not a significant gap (CI −0.026 to +0.036)"],
            ["Props vs your old engine, 525 shipped legs", "0.586 vs 0.632 log loss, significant (CI +0.013 to +0.077)"],
            ["Props floor band (70–88%), 2025–26 holdout", "priced ~79%, hit 76–81% by market; receiving yards ran ~2 pts hot"],
            ["Passing TDs, 2025–26 holdout", "1+ priced 74% hit 78%; 2+ priced 44% hit 44%; floor band priced 79% hit 80%"],
            ["Factor groups", "no single group clears noise in walk-forward tests; all are kept on because together they cost ~0.0002 log loss and drive the intel"]],
    }
    # script-first SGPs per upcoming game: 4/6/8/10 ladder + hybrids (1 ATD + 4 props, 2 ATDs + 4 props)
    script_out = []
    if lad.exists() and pf.exists():
        from .script_sgp import build_lotto, build_script_sgps
        corr_all = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
        from .early import apply_overrides
        L2 = apply_overrides(pd.read_csv(lad)); PF2 = pd.read_parquet(pf)
        A2 = apply_overrides(pd.read_csv(OUT / f"atd_{season}_wk{week}.csv")) if (OUT / f"atd_{season}_wk{week}.csv").exists() else pd.DataFrame()
        # matchup-read overlay: only for games the user has switched it on for (data/matchup_read_games.txt)
        rg_f = ROOT / "data" / "matchup_read_games.txt"
        read_games = {}
        if rg_f.exists():
            for ln in rg_f.read_text().split():
                a = ln.split(","); read_games[a[0]] = a[1] if len(a) > 1 else "steer"
        from .script_sgp import build_aggressive
        for g in [x["id"] for x in games if not x["started"]]:
            try:
                from .matchup import build_game as _bg, reads as _reads
                o, _mode = _bg(season, week, L2, A2, PF2, g, corr_all, hold_pass=tuple(bq_teams), modes=read_games)
                Rg = _reads(season, week, g, L2, PF2) if _mode else None
                ag = build_aggressive(L2, PF2, g, corr_all, hold_pass=tuple(bq_teams), reads=Rg) if read_games.get(g) == "steer" else {"tickets": []}
                agd = {f"ag{t['n']}": {"p": round(t["p"], 5), "legs": legs_js(t["legs"])} for t in ag["tickets"]}
            except Exception as e:  # noqa: BLE001
                print("  [script sgp]", g, e); continue
            script_out.append({"game": g, "notes": o["profile"]["notes"],
                               "ladder": [{"n": t["n"], "p": round(t["p"], 5), "p_indep": round(t["p_indep"], 5), "legs": legs_js(t["legs"])} for t in o["ladder"]],
                               "hybrid1": None if not o["hybrid1"] else {"p": round(o["hybrid1"]["p"], 5), "legs": legs_js(o["hybrid1"]["legs"])},
                               "hybrid2": None if not o["hybrid2"] else {"p": round(o["hybrid2"]["p"], 5), "legs": legs_js(o["hybrid2"]["legs"])},
                               "lotto": (lambda lt: None if not lt else {"p": round(lt["p"], 5), "legs": legs_js(lt["legs"])})(
                                   build_lotto(L2, g, corr_all, n=10, hold_pass=tuple(bq_teams), reads=Rg)),
                               "reads": read_games.get(g, False), **agd,
                               **{k2: (None if not o.get(k1) else {"p": round(o[k1]["p"], 5), "legs": legs_js(o[k1]["legs"])})
                                  for k1, k2 in (("hybrid6_1", "h61"), ("hybrid8_1", "h81"), ("hybrid8_2", "h82"))}})
    # next kick-off window pack: window-only ATD 4/6/8/10, per-game props ladders, master slips
    early = None
    up = S[~S.started]
    if len(up) and lad.exists() and pf.exists():
        day0 = up.gameday.min()
        d0 = up[up.gameday == day0]
        hr0 = d0.gametime.str[:2]; first = hr0.min()
        wg0 = (d0[hr0 == first] if (hr0 == first).sum() >= 3 else d0).sort_values("gametime")
        wins = [1] if len(wg0) >= 2 else []
        if wins:
            wg = list(wg0.index)
            try:
                Wd = build_window(season, week, wg, F=F, L=L2, A=A2, PF=PF2)
                from .atd_versions import build as _avb
                _AV = _avb(season, week, wg)
                def _mt(t):
                    h, m = int(t[:2]), t[3:5]; h = (h - 2) % 24
                    return f"{(h - 1) % 12 + 1}:{m} {'am' if h < 12 else 'pm'}"
                ts = sorted(set(wg0.gametime))
                hs = {int(t[:2]) for t in ts}
                wd = str(wg0.weekday.iloc[0])
                label = ("11am" if hs == {13} else wd if len(hs) > 1 and min(hs) <= 13 else "Afternoon" if max(hs) < 19
                         else "Evening" if min(hs) >= 19 else "Afternoon + Evening")
                kick = (_mt(ts[0]) if len(ts) == 1 else f"{_mt(ts[0])} to {_mt(ts[-1])}") + " MST"
                f12 = None; h_et = h_mt = 0
                gi = {x["game"]: i for i, x in enumerate(script_out)}
                early = {"label": label, "kick_et": kick, "games": wg,
                         "backup_qb": Wd["backup_qb"], "held": [list(x) for x in Wd["held"]],
                         "atd": [{"n": t["n"], "p": round(t["p"], 5), "p_indep": round(t["p_indep"], 5), "legs": list(t["legs"].player_id), "exc": t.get("exceptions", [])} for t in Wd["atd"]],
                         "atd_mixed": [{"n": t["n"], "p": round(t["p"], 5), "legs": list(t["legs"].player_id), "mix": t.get("mix", "")} for t in _AV["versions"]["combo"]["tickets"]],
                         "hedges": [{"name": w["name"], "primary": list(w["primary"].player_id), "hedge": list(w["hedge"].player_id),
                                     "pp": round(w["p_primary"], 5), "ph": round(w["p_hedge"], 5), "pe": round(w["p_either"], 5)} for w in _AV["hedges"].get("swaps", [])],
                         "wrte": [{"id": r.player_id, "rz": _f(r.sh_tgt_rz_e3, 2), "ez": _f(r.sh_ez_tgt_e3, 2), "xtd": _f(r.xtd_e3, 2),
                                   "td": _f(r.td_e3, 2), "tds": _f(r.season_tds, 0), "g": _f(r.season_games, 0)} for r in Wd["wrte"].head(16).itertuples()],
                         "per_game": [{"game": o["game"], "gi": gi.get(o["game"]), "notes": o["profile"]["notes"],
                                       "ladder": [{"n": t["n"], "p": round(t["p"], 5), "legs": legs_js(t["legs"])} for t in o["ladder"]],
                                       "h81": None if not o.get("hybrid8_1") else {"p": round(o["hybrid8_1"]["p"], 5), "legs": legs_js(o["hybrid8_1"]["legs"])},
                                       "h82": None if not o.get("hybrid8_2") else {"p": round(o["hybrid8_2"]["p"], 5), "legs": legs_js(o["hybrid8_2"]["legs"])}} for o in Wd["per_game"]],
                         "master": [{"n": m["n"], "p_all": round(m["p_all"], 6), "exp_cash": round(m["exp_cash"], 2), "legs_total": m["legs_total"],
                                     "exp_legs": round(m["exp_legs"], 1), "missing": m["missing"], "p_at_least": {str(k): round(v, 4) for k, v in m["p_at_least"].items()},
                                     "games": [{"game": r["game"], "p": round(r["p"], 5), "legs": legs_js(r["legs"])} for r in m["games"]]} for m in Wd["master"]]}
            except Exception as e:  # noqa: BLE001
                print("  [early window]", e)
    # cross-game SGP ladder (games not yet kicked off)
    xg = {"props": [], "allpos": [], "stacks": []}
    xf = OUT / f"crossgame_{season}_wk{week}.json"
    if xf.exists():
        xg = json.loads(xf.read_text())
        live_ids = {p["id"] for p in players}
        for key in list(xg):
            xg[key] = [t for t in (xg[key] or []) if all(l["id"] in live_ids for l in t.get("legs", []))]
    rec = {}
    gt = OUT / "graded_tickets_20261108.json"
    if gt.exists():
        T = json.loads(gt.read_text())
        legs = {}
        for t in T:
            for l, r in zip(t["legs"], t["res"]):
                legs[(l["name"], l["mk"], l["k"])] = (l.get("p"), r[0] == "hit")
        dec = [(p, h) for p, h in legs.values() if p is not None]
        rec = {"tickets": len(T), "cashed": sum(t["state"] == "CASHED" for t in T),
               "legs_hit": round(100 * np.mean([h for _, h in dec])), "legs_exp": round(100 * np.mean([p for p, _ in dec]))}
    return {"meta": {"season": season, "week": week, "data_asof": data_asof, "record": rec, "weekly": weekly, "overrides": len([x for x in plog if x["type"] == "override"]),
                     "built": datetime.now(timezone.utc).strftime("%a %b %-d, %H:%M UTC"),
                     "n_games": len(games)},
            "games": games, "players": players, "props": props,
            "corr": {"atd": corr_atd, "legs": corr_legs}, "algo": {"atd": algo_atd, "atd_styles": algo_atd_styles, "atd_combos": atd_combos, "props": algo_props, "sgp": algo_sgp_out},
            "personnel": plog, "singles": singles, "rules": rules, "crossgame": xg, "script_sgp": script_out, "early": early}


def write_site(season: int, week: int) -> Path:
    data = build_data(season, week)
    tpl = (ROOT / "attd" / "site_template.html").read_text()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    out = OUT / "site" / "gods_eye.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    # "as shipped" snapshot of every ticket on this build, for grading that never drifts with later rebuilds
    snap_dir = OUT / "shipped"
    snap_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    (snap_dir / f"tickets_{season}_wk{week}_{stamp}.json").write_text(json.dumps(
        {"built": data["meta"]["built"], "algo": data["algo"], "crossgame": data["crossgame"],
         "early": data.get("early"), "script_sgp": data.get("script_sgp"),
         "players": {p["id"]: {"name": p["name"], "team": p["team"], "game": p["game"], "p": p["p"]} for p in data["players"]}}))
    return out
