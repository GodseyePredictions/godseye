"""Kick-off window pack (e.g. the Sunday early window): ATD 4/6/8/10 tickets from that window's games only,
each game's script-first props ladder, and master slips (every game's top-N props on one sheet)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .atd_slip import _pick_style, joint
from .script_sgp import build_script_sgps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
ATD_SIZES = (4, 6, 8, 10)
MASTER_SIZES = (4, 6, 8)


def backup_qb_teams(season: int, week: int) -> dict:
    """Teams whose passing game is run by a replacement this week: a backup_qb entry on the personnel log, or a QB
    ruled Out / overridden OUT who has thrown >= 25% of the team's passes this season. Interim rule after the Week 9
    MNF grade (Vikings 0-for-5 on the ATD board behind a backup): their skill players are ATD singles only."""
    out = {}
    lf = OUT / f"personnel_log_{season}_wk{week}.json"
    if lf.exists():
        for x in json.loads(lf.read_text()):
            if x.get("type") == "backup_qb":
                out[x["team"]] = f"{x['name']} starts"
    try:
        from .data import DATA_DIR
        sw = pd.read_parquet(DATA_DIR / f"stats_week_{season}.parquet")
        sw = sw[(sw.season_type == "REG") & (sw.attempts > 0)]
        cur = sw.sort_values("week").groupby("player_id").team.last()
        att = sw.groupby("player_id").attempts.sum()
        tot = att.groupby(cur).sum()
        nm = sw.groupby("player_id").player_display_name.last()
        inj = pd.read_parquet(DATA_DIR / f"inj_{season}.parquet")
        outs = set(inj[(inj.week == week) & inj.report_status.isin(["Out", "Doubtful"]) & (inj.position == "QB")].gsis_id)
        pf = DATA_DIR / "personnel.csv"
        if pf.exists():
            P = pd.read_csv(pf); P = P[P.status.str.upper().isin(["OUT", "INACTIVE", "IR"])]
            sc = pd.read_csv(ROOT / "data" / "schedules.csv")
            end = pd.to_datetime(sc[(sc.season == season) & (sc.week == week)].gameday).max()
            asof = pd.to_datetime(P.as_of, errors="coerce")
            P = P[(P.status.str.upper() == "IR") | ((asof > end - pd.Timedelta(days=7)) & (asof <= end))]
            low = set(P.name.str.lower())
            outs |= {pid for pid, n in nm.items() if str(n).lower() in low}
        for pid in outs:
            if pid in att.index and att[pid] / max(tot.get(cur[pid], 1), 1) >= 0.25:
                out.setdefault(cur[pid], f"{nm[pid]} out")
        # starter-share rule (the definition the haircut was measured on): no quarterback on the active roster who is
        # available this week has thrown >= 25% of the team's passes this season. Catches starters lost to injured
        # reserve, who never appear on the weekly report (Baltimore, Week 10: Jackson and Huntley both on IR).
        if week >= 4:
            ro = pd.read_parquet(DATA_DIR / f"roster_{season}.parquet")
            ro = ro[(ro.week == ro.week.max()) & (ro.status == "ACT") & (ro.position == "QB")]
            ro = ro[~ro.gsis_id.isin(outs)]
            share = (att / att.index.map(cur).map(tot)).fillna(0)
            # expected starter = the available quarterback with the most attempts over the team's last two games
            lastw = sw.groupby("team").week.apply(lambda x: sorted(x.unique())[-2:])
            rec = sw[[w in lastw.get(t, []) for w, t in zip(sw.week, sw.team)]].groupby("player_id").attempts.sum()
            best = ro.assign(rec=ro.gsis_id.map(rec).fillna(0), sh=ro.gsis_id.map(share).fillna(0)) \
                .sort_values(["rec", "sh"], ascending=False).drop_duplicates("team")
            for r in best.itertuples():
                if r.sh < 0.25 and tot.get(r.team, 0) > 0:
                    out.setdefault(r.team, f"no established starter ({r.full_name} is the most recent passer at {r.sh:.0%} of season attempts)")
    except Exception as e:  # noqa: BLE001
        print("  [backup qb teams]", e)
    return out


def lead_replacements(season: int, week: int) -> dict:
    """Teams whose lead back (most carries over the team's last three games, 30+) is ruled out this week, mapped to the
    replacement: the available back with the most carries in that span. Backtest 2021-26 (n=167): replacements went
    from 6.5 carries / 27.7 yards to 12.2 / 51.2 in that game; 80% cleared 20 yards, 67% cleared 30, 65% had 10+
    carries, and their own floor rushing lines hit 92% (n=37) against 73% for other backs."""
    out = {}
    try:
        from .data import DATA_DIR
        sw = pd.read_parquet(DATA_DIR / f"stats_week_{season}.parquet")
        sw = sw[(sw.season_type == "REG") & (sw.week < week) & (sw.position == "RB")]
        inj = pd.read_parquet(DATA_DIR / f"inj_{season}.parquet")
        outs = set(inj[(inj.week == week) & inj.report_status.isin(["Out", "Doubtful"])].gsis_id)
        ro = pd.read_parquet(DATA_DIR / f"roster_{season}.parquet"); ro = ro[ro.week == ro.week.max()]
        act = set(ro[ro.status == "ACT"].gsis_id)
        pf = DATA_DIR / "personnel.csv"
        if pf.exists():
            P = pd.read_csv(pf); P = P[P.status.str.upper().isin(["OUT", "INACTIVE", "IR"])]
            sc = pd.read_csv(ROOT / "data" / "schedules.csv")
            end = pd.to_datetime(sc[(sc.season == season) & (sc.week == week)].gameday).max()
            asof = pd.to_datetime(P.as_of, errors="coerce")
            P = P[(P.status.str.upper() == "IR") | ((asof > end - pd.Timedelta(days=7)) & (asof <= end))]
            low = set(zip(P.team, P.name.str.lower()))
            nm = ro.set_index("gsis_id").full_name.str.lower(); tm = ro.set_index("gsis_id").team
            outs |= {g for g in nm.index if (tm.get(g), nm.get(g)) in low}
        for team, g in sw.groupby("team"):
            last3 = sorted(g.week.unique())[-3:]
            c = g[g.week.isin(last3)].groupby("player_id").carries.sum().sort_values(ascending=False)
            if c.empty or c.iloc[0] < 30:
                continue
            lead = c.index[0]
            if lead in outs or lead not in act:
                rest = [pid for pid in c.index[1:] if pid not in outs and pid in act]
                # a back returning from absence has no carries in the span: fall back to season carries
                season_c = g.groupby("player_id").carries.sum().sort_values(ascending=False)
                cand = [pid for pid in season_c.index if pid != lead and pid not in outs and pid in act]
                if cand:
                    out[team] = {"replacement": cand[0], "lead": lead}
    except Exception as e:  # noqa: BLE001
        print("  [lead replacements]", e)
    return out


def apply_role_flags(L: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    """Mark the replacement lead back on the ladders (`lead_repl`) so his rushing lines skip the season hit-rate gate
    and the fresh-role gate (both describe his old role, not this week's)."""
    L = L.copy(); L["lead_repl"] = False
    lr = lead_replacements(season, week)
    ids = {v["replacement"] for v in lr.values()}
    if ids:
        L.loc[L.player_id.isin(ids), "lead_repl"] = True
        for t, v in lr.items():
            n = L[L.player_id == v["replacement"]].name
            print(f"  [lead back] {t}: lead back out -> {n.iloc[0] if len(n) else v['replacement']} is the replacement (rushing lines exempt from the hit-rate gate)")
    return L


def apply_overrides(df: pd.DataFrame) -> pd.DataFrame:
    """User overrides (data/ticket_overrides.txt, one player name per line): lift the returning / fresh-role flags so
    the player competes for ticket legs on the normal probability thresholds. Logged on the slip as an exception."""
    f = ROOT / "data" / "ticket_overrides.txt"
    if not f.exists() or df is None or not len(df) or "name" not in df.columns:
        return df
    names = {x.strip().lower() for x in f.read_text().splitlines() if x.strip()}
    m = df.name.str.lower().isin(names)
    if not m.any():
        return df
    df = df.copy()
    for c, v in (("singles_only", False), ("returning", False), ("fresh_role", 0)):
        if c in df.columns:
            df.loc[m, c] = v
    return df


def override_names() -> list:
    f = ROOT / "data" / "ticket_overrides.txt"
    return [x.strip() for x in f.read_text().splitlines() if x.strip()] if f.exists() else []


def atd_parlay_pool(W: pd.DataFrame, bq: dict):
    """ATD parlay-eligible pool and the list of players held out with the reason (they stay on the board as singles)."""
    held = []
    ok = W[~W.singles_only.fillna(False).astype(bool)]
    if "atd_ticket_ok" in ok.columns:
        ok = ok[ok.atd_ticket_ok.fillna(True).astype(bool)]
    m = ok.team.isin(bq)
    held += [(r["name"], r.team, f"backup-QB offence ({bq[r.team]})") for _, r in ok[m & (ok.p_attd >= 0.2)].iterrows()]
    ok = ok[~m]
    m = (ok.pos_group == "RB") & (ok.carries_e3.fillna(0) < 7)
    held += [(r["name"], r.team, f"unproven workload ({r.carries_e3:.1f} carries a game recently)") for _, r in ok[m & (ok.p_attd >= 0.2)].iterrows()]
    ok = ok[~m]
    # displaced back: a teammate RB is in his first two games back and out-carried him last game
    if {"returning", "sh_carries_lag1"} <= set(W.columns):
        ret = W[(W.pos_group == "RB") & W.returning.fillna(False).astype(bool)]
        top = ret.sort_values("sh_carries_lag1", ascending=False).drop_duplicates("team").set_index("team")
        m = (ok.pos_group == "RB") & ok.team.isin(top.index) & \
            (ok.sh_carries_lag1.fillna(0) < ok.team.map(top.sh_carries_lag1).fillna(0))
        held += [(r["name"], r.team, f"displaced: {top.loc[r.team, 'name']} is back and out-carried him last game")
                 for _, r in ok[m & (ok.p_attd >= 0.2)].iterrows()]
        ok = ok[~m]
    return ok.sort_values("p_attd", ascending=False), held


def window_games(season: int, week: int, day: str, time: str) -> list[str]:
    s = pd.read_csv(ROOT / "data" / "schedules.csv")
    g = s[(s.season == season) & (s.week == week) & (s.gameday == day) & (s.gametime == time) & s.home_score.isna()]
    return g.game_id.tolist()


def build_window(season: int, week: int, games: list[str], F=None, L=None, A=None, PF=None) -> dict:
    F = pd.read_parquet(OUT / f"projection_features_{season}_wk{week}.parquet") if F is None else F
    L = pd.read_csv(OUT / f"prop_ladders_{season}_wk{week}.csv") if L is None else L
    A = pd.read_csv(OUT / f"atd_{season}_wk{week}.csv") if A is None else A
    PF = pd.read_parquet(OUT / f"props_features_{season}_wk{week}.parquet") if PF is None else PF
    corr_atd = json.loads((ROOT / "models" / "correlations.json").read_text())
    corr_legs = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
    bq = backup_qb_teams(season, week)
    # ---- ATD tickets: this window only, RB/QB (WR/TE are singles), no flagged players, no backup-QB offences
    W = F[F.game_id.isin(games)].copy()
    ok, held = atd_parlay_pool(W, bq)
    ok = ok[ok.pos_group.isin(["RB", "QB"]) & (ok.p_attd >= 0.20)]     # no filler legs: a ticket size is skipped if the pool runs dry
    # run-defence matchup in the ticket order (Nov 21 2026): soft run defences allowed 0.79 rushing TDs to backs the
    # next game vs 0.64 for stingy ones (2023-26, 1,420 team-games). A back facing a bottom-ten run defence moves up,
    # one facing a top-eight run defence moves down. Order only; probabilities unchanged.
    try:
        from .defense_report import team_defense
        Dd = team_defense(season, week); rk = ok.opp.map(Dd.r_rb_rush); nD = len(Dd)
        adj = np.where((ok.pos_group == "RB") & (rk >= nD - 9), 0.20, np.where((ok.pos_group == "RB") & (rk <= 8), -0.20, 0.0))
        ok = ok.assign(_s=np.log(ok.p_attd / (1 - ok.p_attd)) + adj).sort_values("_s", ascending=False).drop(columns="_s")
    except Exception as e:  # noqa: BLE001
        print("  [run-defence order]", e)
    picks = _pick_style(ok, max(ATD_SIZES), "chalk")
    # pool-dry fallback: a returning lead back (led his team in carries in his first game back, not on the injury
    # report) may fill the last legs, flagged as a rule exception on the ticket
    exc = set()
    if len(picks) < max(ATD_SIZES) and "sh_carries_lag1" in W.columns:
        fb = W[(W.pos_group == "RB") & W.returning.fillna(False).astype(bool) & W.injury_status.isna()
               & (W.sh_carries_lag1.fillna(0) >= 0.5) & (W.p_attd >= 0.20) & ~W.team.isin(bq)
               & ~W.team.isin(picks.team)].sort_values("p_attd", ascending=False).drop_duplicates("team")
        fb = fb.head(max(ATD_SIZES) - len(picks))
        exc = set(fb.player_id)
        picks = pd.concat([picks, fb])
        if len(picks) < max(ATD_SIZES):   # second tier: a back inheriting the job this week (unproven workload), 30%+
            fb2 = W[(W.pos_group == "RB") & ~W.singles_only.fillna(False).astype(bool) & (W.carries_e3.fillna(0) < 7)
                    & (W.p_attd >= 0.30) & ~W.team.isin(bq) & ~W.team.isin(picks.team)] \
                .sort_values("p_attd", ascending=False).drop_duplicates("team").head(max(ATD_SIZES) - len(picks))
            exc |= set(fb2.player_id)
            picks = pd.concat([picks, fb2])
        # (third tier removed Nov 16 2026: backs on replacement-QB offences went 0 for 3 as fill legs in Week 10 and
        #  hit 29% against a 45% price out of sample; they are never ticket legs)
    atd = []
    for n in ATD_SIZES:
        legs = picks.head(n)
        if len(legs) < n:
            break
        atd.append({"n": n, "legs": legs, "p": joint(legs, corr_atd), "p_indep": float(legs.p_attd.prod()),
                    "exceptions": [r["name"] for _, r in legs[legs.player_id.isin(exc)].iterrows()]})
    # receivers and tight ends: singles board (clean = not flagged, not a backup-QB offence) and a mixed-position
    # ticket ladder. Mixed tickets sit outside the WR/TE singles rule and are labelled that way.
    ok_all, _ = atd_parlay_pool(W, bq)
    wrte = ok_all[ok_all.pos_group.isin(["WR", "TE"]) & (ok_all.p_attd >= 0.25)].copy()
    mpool = pd.concat([ok, wrte]).sort_values("p_attd", ascending=False)
    mp = _pick_style(mpool, max(ATD_SIZES), "balanced")
    mixed = []
    for n in ATD_SIZES:
        legs = mp.head(n)
        if len(legs) < n:
            break
        mixed.append({"n": n, "legs": legs, "p": joint(legs, corr_atd), "p_indep": float(legs.p_attd.prod())})
    board = W[W.p_attd >= 0.10].sort_values("p_attd", ascending=False)
    # ---- per game script ladders; ATD hybrids skip backup-QB offences too
    # hybrid ATD legs obey the same hold-outs as the ATD tickets (flags, backup-QB offences, unproven / displaced backs)
    A2 = A[A.player_id.isin(ok_all.player_id)] if len(A) else A
    per_game = []
    for g in games:
        try:
            from .matchup import build_game as _bg
            o, _ = _bg(season, week, L, A2, PF, g, corr_legs, hold_pass=tuple(bq))
        except Exception as e:  # noqa: BLE001
            print("  [window sgp]", g, e); continue
        per_game.append({"game": g, **o})
    # ---- master slips: every game's top-N props on one sheet. Games are independent of each other.
    master = []
    for n in MASTER_SIZES:
        rows = []
        for o in per_game:
            t = next((x for x in o["ladder"] if x["n"] == n), None)
            if t is not None:
                rows.append({"game": o["game"], "p": t["p"], "legs": t["legs"]})
        if not rows:
            continue
        ps = np.array([r["p"] for r in rows])
        # distribution of how many game tickets cash (Poisson-binomial)
        dist = np.array([1.0])
        for p in ps:
            dist = np.convolve(dist, [1 - p, p])
        missing = [o["game"] for o in per_game if not any(x["n"] == n for x in o["ladder"])]
        master.append({"n": n, "games": rows, "missing": missing, "p_all": float(ps.prod()), "exp_cash": float(ps.sum()),
                       "legs_total": int(sum(len(r["legs"]) for r in rows)),
                       "exp_legs": float(sum(r["legs"].p.sum() for r in rows)),
                       "p_at_least": {k: float(dist[k:].sum()) for k in range(1, len(ps) + 1)}})
    return {"games": games, "held": held, "atd": atd, "wrte": wrte, "atd_mixed": mixed, "board": board, "per_game": per_game, "master": master, "backup_qb": bq}
