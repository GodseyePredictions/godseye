"""Script-first SGP builder.

1. game_script(): read the game (spread, totals, pass/run tendencies when leading or trailing, red-zone recency, pace,
   weather, run-lane and secondary edges) into a profile with plain-English notes.
2. leg_fit(): score every candidate leg against that profile (−1..+1) with the reasons.
3. build_script_sgps(): nested 4/6/8/10-leg props tickets chosen for joint probability with script fit as the
   tiebreaker (≤2 legs per player, ≤3 per market), plus two hybrids: 1 ATD + 4 props, 2 ATDs + 4 props.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .correlation import ticket_prob
from .intel import MK_LABEL, TEAM
from .tickets import pick_rungs

ROOT = Path(__file__).resolve().parent.parent
SIZES = (4, 6, 8, 10)
PASS_MK = ("rec", "rec_yds", "pass_att", "pass_yds", "pass_td")
FIT_WEIGHT = 0.55            # logit(p) + FIT_WEIGHT * fit ranks candidates
VOL_MARKETS = {"carries", "rush_yds", "pass_att"}


def _team_profile(r) -> dict:
    """r = one props-features row for any player on the team (team-level fields are identical)."""
    sp = float(r.spread)
    return {
        "team": r.team, "opp": r.opp, "spread": sp, "implied": float(r.implied_filled), "total": float(r.total_line),
        "fav": sp >= 3, "dog": sp <= -3, "big_fav": sp >= 7, "big_dog": sp <= -7,
        "proe": float(r.get("proe_oc", 0) or 0), "trail_pass": float(r.get("trail_pass_oc", np.nan)),
        "lead_run": float(r.get("lead_run_oc", np.nan)), "rz_pass3": float(r.get("rz_pass_oc3", np.nan)),
        "rz_pass": float(r.get("rz_pass_oc", np.nan)), "plays": float(r.get("plays_ewm", np.nan)),
        "run_lane": float(r.get("mx_run_lane", 4.2) or 4.2), "stuff": float(r.get("mx_stuff", 0.35) or 0.35),
        "ypt_wr": float(r.get("ypt_allowed_WR_dc", np.nan)), "ypt_te": float(r.get("ypt_allowed_TE_dc", np.nan)),
        "ypt_rb": float(r.get("ypt_allowed_RB_dc", np.nan)), "blitz": float(r.get("blitz_rate_dc", np.nan)),
        "light_box": float(r.get("light_box_dc", np.nan)), "pass_pro": float(r.get("mx_pass_pro", 0.14) or 0.14),
        "wx": str(r.get("wx_cat", "")), "wind": float(r.get("wind", 0) or 0), "indoor": int(r.get("is_indoor", 0) or 0),
        "def_out": float(r.get("def_starters_out", 0) or 0),
        # tempo & discipline
        "off_pen": float(r.get("off_pen_rate_tp", np.nan)), "opp_def_pen": float(r.get("def_pen_rate_tpd", np.nan)),
        "stall3": float(r.get("stall3_rate_tp", np.nan)), "stall3_forced": float(r.get("stall3_forced_tpd", np.nan)),
        "punt_after3": float(r.get("punt_after3_pd_tp", np.nan)), "fg_after3": float(r.get("fg_after3_pd_tp", np.nan)),
        "third_conv": float(r.get("third_conv_tp", np.nan)), "plays_tp": float(r.get("plays_tp", np.nan)),
        "plays_allowed": float(r.get("plays_allowed_tpd", np.nan)), "exp_plays": float(r.get("exp_plays", np.nan)),
        "top": float(r.get("top_sec_tp", np.nan)), "exp_top": float(r.get("exp_top_sec", np.nan)),
        "spp": float(r.get("sec_per_play_tp", np.nan)),
    }


LG = {"off_pen": 0.064, "def_pen": 0.052, "stall3": 0.73, "third_conv": 0.39, "plays": 61.0, "top": 1800.0, "spp": 29.7}


def _mmss(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}" if not np.isnan(sec) else "—"


def game_script(F: pd.DataFrame, game_id: str) -> dict:
    g = F[F.game_id == game_id]
    teams = {t: _team_profile(g[g.team == t].iloc[0]) for t in g.team.unique()}
    notes = []
    tot = next(iter(teams.values()))["total"]
    windy = any(t["wind"] >= 15 for t in teams.values()) and not any(t["indoor"] for t in teams.values())
    wet = any(t["wx"] in ("rain", "snow") for t in teams.values())
    tier = "shootout" if tot >= 48 else "low" if tot <= 41 else "mid"
    notes.append(f"Total {tot:.1f} ({tier}){' · wind' if windy else ''}{' · ' + 'rain/snow' if wet else ''}.")
    for t, p in teams.items():
        tn = TEAM.get(t, t)
        if p["big_fav"]:
            side = f"{tn} are {p['spread']:.0f}-point favourites"
        elif p["fav"]:
            side = f"{tn} are favoured by {p['spread']:.0f}"
        elif p["big_dog"]:
            side = f"{tn} are {-p['spread']:.0f}-point underdogs"
        elif p["dog"]:
            side = f"{tn} are {-p['spread']:.0f}-point underdogs"
        else:
            side = f"{tn} in a pick'em"
        tend = ("pass-leaning" if p["proe"] > 2 else "run-leaning" if p["proe"] < -2 else "balanced")
        extra = []
        if p["fav"] and not np.isnan(p["lead_run"]) and p["lead_run"] >= 0.55:
            extra.append(f"run {p['lead_run']:.0%} when up 10+")
        if p["dog"] and not np.isnan(p["trail_pass"]) and p["trail_pass"] >= 0.65:
            extra.append(f"throw {p['trail_pass']:.0%} when down 10+")
        if not np.isnan(p["rz_pass3"]) and not np.isnan(p["rz_pass"]) and abs(p["rz_pass3"] - p["rz_pass"]) >= 0.08:
            extra.append(f"red zone trending {'pass' if p['rz_pass3'] > p['rz_pass'] else 'run'} ({p['rz_pass3']:.0%} last 3 vs {p['rz_pass']:.0%} season)")
        if p["run_lane"] >= 4.6:
            extra.append("soft run lane (O-line vs front)")
        elif p["run_lane"] <= 3.9:
            extra.append("tough run lane")
        if not np.isnan(p["ypt_wr"]) and p["ypt_wr"] >= 8.6:
            extra.append("soft secondary vs WRs")
        if not np.isnan(p["ypt_te"]) and p["ypt_te"] >= 7.6:
            extra.append("soft vs TEs")
        if p["def_out"] >= 2:
            extra.append(f"opponent missing {int(p['def_out'])} defensive starters")
        # discipline & drive stalls
        if not np.isnan(p["off_pen"]) and p["off_pen"] >= LG["off_pen"] * 1.2:
            extra.append(f"penalty-prone offence ({p['off_pen']:.1%} of plays flagged, league {LG['off_pen']:.1%})")
        elif not np.isnan(p["off_pen"]) and p["off_pen"] <= LG["off_pen"] * 0.75:
            extra.append(f"disciplined offence ({p['off_pen']:.1%} flagged)")
        if not np.isnan(p["opp_def_pen"]) and p["opp_def_pen"] >= LG["def_pen"] * 1.2:
            extra.append(f"faces a flag-happy defence ({p['opp_def_pen']:.1%} of plays), free first downs")
        if not np.isnan(p["stall3"]) and p["stall3"] >= 0.80:
            extra.append(f"drives die on 3rd down ({p['stall3']:.0%} of failed 3rd downs end in a punt or FG; "
                         f"{p['punt_after3']:.0%} of drives punt, {p['fg_after3']:.0%} settle for FGs)")
        elif not np.isnan(p["stall3"]) and p["stall3"] <= 0.62:
            extra.append(f"extends drives (only {p['stall3']:.0%} of failed 3rd downs end the drive; 3rd-down {p['third_conv']:.0%})")
        if not np.isnan(p["fg_after3"]) and p["fg_after3"] >= 0.22:
            extra.append("settles for field goals (hurts TD legs)")
        notes.append(f"{side}, {tend} offence ({p['proe']:+.1f}% PROE), implied {p['implied']:.1f}" + (f"; {', '.join(extra)}" if extra else "") + ".")
    tp = [(TEAM.get(t, t), p) for t, p in teams.items() if not np.isnan(p.get("exp_plays", np.nan))]
    if tp:
        parts = [f"{tn} {p['exp_plays']:.0f} plays / {_mmss(p['exp_top'])} possession" for tn, p in tp]
        fast = [tn for tn, p in tp if not np.isnan(p["spp"]) and p["spp"] <= LG["spp"] - 2]
        slow = [tn for tn, p in tp if not np.isnan(p["spp"]) and p["spp"] >= LG["spp"] + 2]
        tail = (f"; up-tempo: {', '.join(fast)}" if fast else "") + (f"; slow, clock-eating: {', '.join(slow)}" if slow else "")
        notes.append("Expected volume: " + " · ".join(parts) + tail + ". More plays and possession = more time on field for every prop.")
    return {"game_id": game_id, "teams": teams, "total": tot, "tier": tier, "windy": windy, "wet": wet, "notes": notes}


def leg_fit(leg, prof: dict) -> tuple[float, list[str]]:
    """Script fit for one leg (−1..+1) with reasons. leg has team, pos_group, market."""
    p = prof["teams"][leg.team]
    fit, why = 0.0, []
    mk, pos = leg.market, leg.pos_group
    rush = mk in ("carries", "rush_yds")
    recv = mk in ("rec", "rec_yds")
    # Low implied team total (Nov 21 2026 backtest): floor legs on teams implied under 17.5 hit about a point under
    # their price while every other bucket ran 2-5 points over (2026 walk-forward, n=205 vs 2,578); model-free
    # 2021-26 the same legs hit 68-71% against 73-76% elsewhere. A ranking nudge, not a cap: a hard underdog cap
    # failed the backtest (receiving legs on 10+ point underdogs hit 73.7% vs 73.9% for everyone else, n=691).
    if p.get("implied", 99) < 17.5:
        fit -= 0.15; why.append("low implied team total")
    passing = mk in ("pass_att", "pass_yds", "pass_td")
    # game state
    if p["fav"]:
        if rush:
            fit += 0.35 if p["big_fav"] else 0.2; why.append("favourite's backs get the late-game carries")
            if not np.isnan(p["lead_run"]) and p["lead_run"] >= 0.55:
                fit += 0.15; why.append(f"this offence runs {p['lead_run']:.0%} when ahead")
        if passing and mk in ("pass_att", "pass_yds"):
            fit -= 0.35 if p["big_fav"] else 0.15; why.append("big favourites throw less late")
        if recv and pos == "WR" and mk == "rec_yds":
            fit -= 0.15 if p["big_fav"] else 0.0
    if p["dog"]:
        if passing or (recv and pos in ("WR", "TE")):
            fit += 0.3 if p["big_dog"] else 0.15; why.append("underdogs throw to catch up")
            if not np.isnan(p["trail_pass"]) and p["trail_pass"] >= 0.65:
                fit += 0.1; why.append(f"this offence throws {p['trail_pass']:.0%} when behind")
        if rush:
            fit -= 0.35 if p["big_dog"] else 0.15; why.append("trailing script cuts carries")
        if recv and pos == "RB":
            fit += 0.15; why.append("trailing backs catch checkdowns")
    # tendencies
    if p["proe"] > 2 and (passing or recv):
        fit += 0.1; why.append("pass-leaning play-caller")
    if p["proe"] < -2 and rush:
        fit += 0.1; why.append("run-leaning play-caller")
    if mk == "pass_td":
        if not np.isnan(p["rz_pass3"]) and p["rz_pass3"] >= 0.6:
            fit += 0.2; why.append(f"red-zone passing {p['rz_pass3']:.0%} over the last 3 games")
        elif not np.isnan(p["rz_pass3"]) and p["rz_pass3"] <= 0.45:
            fit -= 0.2; why.append("red zone is run-first lately")
    # matchups
    if rush:
        if p["run_lane"] >= 4.6:
            fit += 0.2; why.append("soft run lane")
        elif p["run_lane"] <= 3.9:
            fit -= 0.2; why.append("tough front")
        if mk == "rush_yds" and not np.isnan(p["light_box"]) and p["light_box"] >= 0.5:
            fit += 0.1; why.append("light boxes")
    if recv and pos == "WR" and not np.isnan(p["ypt_wr"]):
        if p["ypt_wr"] >= 8.6: fit += 0.2; why.append("soft secondary vs WRs")
        elif p["ypt_wr"] <= 7.0: fit -= 0.15; why.append("stingy secondary vs WRs")
    if recv and pos == "TE" and not np.isnan(p["ypt_te"]):
        if p["ypt_te"] >= 7.6: fit += 0.2; why.append("soft vs TEs")
        elif p["ypt_te"] <= 6.2: fit -= 0.15; why.append("stingy vs TEs")
    if passing and p["pass_pro"] >= 0.17:
        fit -= 0.1; why.append("pressure risk (sacks)")
    # tempo & discipline: volume markets ride plays and possession; TD markets hate stalled drives and FGs
    vol = mk in ("carries", "rush_yds", "rec", "rec_yds", "pass_att", "pass_yds")
    ep = p.get("exp_plays", np.nan)
    if vol and not np.isnan(ep):
        if ep >= LG["plays"] + 4:
            fit += 0.15; why.append(f"high-volume script (~{ep:.0f} plays expected)")
        elif ep <= LG["plays"] - 4:
            fit -= 0.15; why.append(f"low-volume script (~{ep:.0f} plays expected)")
    st = p.get("stall3", np.nan)
    if vol and not np.isnan(st):
        if st >= 0.80:
            fit -= 0.1; why.append("drives stall on 3rd down (fewer snaps per drive)")
        elif st <= 0.62:
            fit += 0.1; why.append("sustains drives (converts or goes for it)")
    if mk in ("pass_td", "atd") and not np.isnan(p.get("fg_after3", np.nan)) and p["fg_after3"] >= 0.22:
        fit -= 0.15; why.append("settles for field goals")
    if not np.isnan(p.get("opp_def_pen", np.nan)) and p["opp_def_pen"] >= LG["def_pen"] * 1.2 and (vol or mk == "pass_td"):
        fit += 0.05; why.append("opponent's flags extend drives")
    if not np.isnan(p.get("off_pen", np.nan)) and p["off_pen"] >= LG["off_pen"] * 1.2 and mk in ("pass_td", "atd"):
        fit -= 0.05; why.append("own penalties push them out of scoring range")
    # environment
    if (prof["windy"] or prof["wet"]) and (mk in ("pass_yds", "rec_yds", "pass_td")):
        fit -= 0.25; why.append("weather hits passing yardage")
    if (prof["windy"] or prof["wet"]) and rush:
        fit += 0.1
    if prof["tier"] == "shootout" and (passing or recv):
        fit += 0.1; why.append("high total")
    if prof["tier"] == "low" and mk in ("pass_yds", "rec_yds"):
        fit -= 0.1; why.append("low total")
    return float(np.clip(fit, -1, 1)), why


def _joint(df, corr):
    d = df.copy(); d["p"] = d.p.astype(float)
    return ticket_prob(d, corr, n_sims=40_000)


def _greedy(pool: pd.DataFrame, corr, n, seed=None, per_player=2, per_market=3, atd_cap=0, cap_pass=True, fit_w=None):
    cur = seed.copy() if seed is not None else pool.iloc[0:0].copy()
    while len(cur) < n:
        best = None
        # the one-script cap is tried first; if nothing else is left (one offence held out, the other all passing),
        # it is relaxed so the game still gets a ticket
        for capped in ((True, False) if cap_pass else (False,)):
            for i, r in pool.iterrows():
                if i in cur.index: continue
                if (cur.player_id == r.player_id).sum() >= per_player: continue
                if ((cur.player_id == r.player_id) & (cur.market == r.market)).any(): continue
                if r.market == "atd" and (cur.market == "atd").sum() >= atd_cap: continue
                if r.market != "atd" and (cur.market == r.market).sum() >= per_market: continue
                # one-script cap (Week 10 MNF): legs tied to one team's passing game are at most half the ticket
                if capped and r.market in PASS_MK:
                    same = ((cur.team == r.team) & cur.market.isin(PASS_MK)).sum()
                    if same >= -(-(len(cur) + 1) // 2): continue
                trial = pd.concat([cur, pool.loc[[i]]])
                pj = _joint(trial, corr)
                score = np.log(pj / (1 - pj + 1e-9)) + (FIT_WEIGHT * 0.5 if fit_w is None else fit_w) * r.fit
                if best is None or score > best[0]:
                    best = (score, i, pj)
            if best is not None: break
        if best is None: break
        cur = pd.concat([cur, pool.loc[[best[1]]]])
    return cur


def build_script_sgps(L: pd.DataFrame, A: pd.DataFrame, F: pd.DataFrame, game_id: str, corr: dict, hold_pass=(), reads=None, read_mode="steer") -> dict:
    """hold_pass: teams whose passing game is run by a replacement QB this week. Their passing and receiving legs
    (and anytime-TD legs) stay off the tickets; rushing legs remain. Interim rule after the Week 9 Monday grade."""
    prof = game_script(F, game_id)
    if hold_pass:
        L = L[~(L.team.isin(hold_pass) & L.market.isin(["rec", "rec_yds", "pass_att", "pass_yds", "pass_td"]))]
        # anytime-TD legs: pass-catchers and QBs on a replacement-QB offence are out (priced 29% / hit 17% out of sample);
        # a lead back stays available at his haircut price, because in a one-game slip the alternative is a weaker leg
        if len(A): A = A[~(A.team.isin(hold_pass) & (A.pos_group != "RB"))]
        held = [prof["teams"][t]["name"] if "name" in prof["teams"].get(t, {}) else t for t in prof["teams"] if t in hold_pass]
        if held:
            prof["notes"] = list(prof["notes"]) + [f"Replacement quarterback for {' and '.join(held)}: their passing and receiving legs are held off the tickets; rushing legs stay, and their backs' touchdown prices carry the backup-QB haircut."]
    props = pd.concat([pick_rungs(L[L.game_id == game_id], "floor"), pick_rungs(L[L.game_id == game_id], "mid")]) \
        .drop_duplicates(["player_id", "market", "k"])
    props = props[props.p >= 0.62].copy()
    # a leg needs at least four games on record this season (Week 10 MNF: a 2-of-3 depth receiver and a third back's
    # 1+ reception both missed)
    props = props[props.season_n.fillna(0) >= 4]
    fits = [leg_fit(r, prof) for r in props.itertuples()]
    props["fit"] = [f for f, _ in fits]; props["fit_why"] = [w for _, w in fits]
    if reads is not None:   # experimental matchup-read overlay (attd/matchup.py); off by default
        from .matchup import apply as _apply_reads
        props = _apply_reads(props, reads, mode=read_mode)
    props["score"] = np.log(props.p / (1 - props.p)) + FIT_WEIGHT * props.fit
    props = props.sort_values("score", ascending=False).reset_index(drop=True)
    # legs the script actively argues against are dropped when there is enough else to choose from
    against = props.fit <= -0.3
    if (~against).sum() >= 14:
        props = props[~against].reset_index(drop=True)
    cols = ["game_id", "team", "player_id", "name", "pos_group", "market", "k", "p", "season_hits", "season_n", "fit", "fit_why", "score"]
    pool = props[cols]
    out = {"profile": prof, "ladder": [], "hybrid1": None, "hybrid2": None, "hybrid8_1": None, "hybrid8_2": None, "hybrid6_1": None, "hybrid6_2": None, "pool": pool}
    ladder = _greedy(pool, corr, max(SIZES))
    for n in SIZES:
        legs = ladder.head(n)
        if len(legs) < n: break
        out["ladder"].append({"n": n, "legs": legs, "p": _joint(legs, corr), "p_indep": float(legs.p.prod())})
    # hybrids: ATD legs (eligible, scored with fit on the TD side of the script)
    atd = A[(A.game_id == game_id) & ~A.singles_only.fillna(False).astype(bool) & (A.p >= 0.30)].copy()
    if len(atd):
        fits = []
        for r in atd.itertuples():
            tp = prof["teams"][r.team]; f = 0.0; why = []
            if r.pos_group == "RB":
                if tp["fav"]: f += 0.25; why.append("favourite's goal-line back")
                if tp["run_lane"] >= 4.6: f += 0.1
                if not np.isnan(tp["rz_pass3"]) and tp["rz_pass3"] >= 0.62: f -= 0.25; why.append("red zone trending pass")
            else:
                if not np.isnan(tp["rz_pass3"]) and tp["rz_pass3"] >= 0.6: f += 0.2; why.append("red zone trending pass")
                if tp["dog"]: f += 0.1
            fits.append((float(np.clip(f, -1, 1)), why))
        atd["fit"] = [f for f, _ in fits]; atd["fit_why"] = [w for _, w in fits]
        # rank on the play-at probability (model minus the position cushion: RB 3 pts, QB/TE 4, WR 6), so a pass-catcher
        # is only the anytime-TD leg when he beats the backs by more than his cushion (Week 10: WR/TE hybrid legs 1 of 8)
        pe = (atd.p - atd.pos_group.map({"RB": 0.03, "QB": 0.04, "TE": 0.04, "WR": 0.06}).fillna(0.05)).clip(0.02, 0.98)
        atd["score"] = np.log(pe / (1 - pe)) + FIT_WEIGHT * atd.fit
        atd = atd.sort_values("score", ascending=False)
        atd["k"] = np.nan; atd["season_hits"] = np.nan; atd["season_n"] = np.nan
        apool = atd[cols]
        # single-TD slips: among the top three candidates, keep the scorer whose finished 6-leg slip is most likely
        # after his position cushion (so a back is not forced in when a pass-catcher makes the better ticket, or the reverse)
        CUSH = {"RB": 0.03, "QB": 0.04, "TE": 0.04, "WR": 0.06}
        best1 = None
        for i in range(min(3, len(apool))):
            c = apool.iloc[[i]]
            t6 = _greedy(pd.concat([c, pool]), corr, 6, seed=c, atd_cap=1)
            pc = float(c.p.iloc[0]); adj = _joint(t6, corr) * max(pc - CUSH.get(c.pos_group.iloc[0], 0.05), 0.01) / pc
            if best1 is None or adj > best1[0]: best1 = (adj, c)
        a1 = best1[1]
        h1 = _greedy(pd.concat([a1, pool]), corr, 5, seed=a1, atd_cap=1)
        out["hybrid1"] = {"legs": h1, "p": _joint(h1, corr), "p_indep": float(h1.p.prod())}
        # 2 ATDs: best pair by joint (prefer different teams; shootout correlation) then 4 props
        best = None
        for i in range(min(5, len(apool))):
            for j in range(i + 1, min(6, len(apool))):
                pair = apool.iloc[[i, j]]
                pj = _joint(pair, corr) * (1.0 + 0.2 * (pair.fit.mean()))
                if best is None or pj > best[0]: best = (pj, pair)
        if best is not None:
            h2 = _greedy(pd.concat([best[1], pool]), corr, 6, seed=best[1], atd_cap=2)
            out["hybrid2"] = {"legs": h2, "p": _joint(h2, corr), "p_indep": float(h2.p.prod())}
        # 8-leg hybrids: 1 ATD + 7 props, and 2 ATDs + 6 props (8 legs in total, anytime-TD legs included)
        h61 = _greedy(pd.concat([a1, pool]), corr, 6, seed=a1, atd_cap=1)
        out["hybrid6_1"] = {"legs": h61, "p": _joint(h61, corr), "p_indep": float(h61.p.prod())}
        out["hybrid6_2"] = out["hybrid2"]
        h81 = _greedy(pd.concat([a1, pool]), corr, 8, seed=a1, atd_cap=1)
        out["hybrid8_1"] = {"legs": h81, "p": _joint(h81, corr), "p_indep": float(h81.p.prod())}
        if best is not None:
            h82 = _greedy(pd.concat([best[1], pool]), corr, 8, seed=best[1], atd_cap=2)
            out["hybrid8_2"] = {"legs": h82, "p": _joint(h82, corr), "p_indep": float(h82.p.prod())}
    return out


def build_lotto(L: pd.DataFrame, game_id: str, corr: dict, n=10, hold_pass=(), reads=None) -> dict | None:
    """Lotto ticket: the n most likely props in the game, safest rung per player and market (75-97%), at most two legs
    per player and half the ticket on one team's passing game. Long by design; every leg is a favourite on its own."""
    q = L[(L.game_id == game_id) & (L.market != "atd") & L.role_ok & ~L.singles_only & (L.season_n.fillna(0) >= 4)
          & L.p.between(0.75, 0.97) & (L.season_rate.fillna(0) >= 0.70)].copy()
    if hold_pass:
        q = q[~(q.team.isin(hold_pass) & q.market.isin(PASS_MK))]
    if q.empty:
        return None
    # per player and market: the hardest line still at 82%+; if none, his safest line
    q["safe"] = q.p >= 0.82
    q = pd.concat([q[q.safe].sort_values("k", ascending=False), q[~q.safe].sort_values("p", ascending=False)]) \
        .drop_duplicates(["player_id", "market"])
    q["fit"] = 0.0; q["fit_why"] = [[] for _ in range(len(q))]
    if reads is not None:
        from .matchup import apply as _apply_reads
        q = _apply_reads(q, reads)
    q["score"] = q.p
    q = q.sort_values("p", ascending=False).reset_index(drop=True)
    cols = ["game_id", "team", "player_id", "name", "pos_group", "market", "k", "p", "season_hits", "season_n", "fit", "fit_why", "score"]
    legs = _greedy(q[cols], corr, n, per_market=4)
    if len(legs) < 6:
        return None
    return {"legs": legs, "p": _joint(legs, corr), "p_indep": float(legs.p.prod())}


def build_aggressive(L: pd.DataFrame, F: pd.DataFrame, game_id: str, corr: dict, hold_pass=(), reads=None, sizes=(6, 8)) -> dict:
    """Aggressive SGP: one step up the milestone ladder. Each leg is the player's line priced 50-72% (the line
    nearest 62% per player and market), ranked with script fit, same caps as the standard slips."""
    prof = game_script(F, game_id)
    q = L[L.game_id == game_id]
    if hold_pass:
        q = q[~(q.team.isin(hold_pass) & q.market.isin(PASS_MK))]
    q = q[(q.market != "atd") & q.role_ok & ~q.singles_only & (q.season_n.fillna(0) >= 4) & q.p.between(0.50, 0.72)]
    VOL = q.market.isin(["carries", "rush_yds", "pass_att"])
    if "fresh_role" in q.columns:
        q = q[~(VOL & (q.fresh_role.fillna(0) == 1))]
    q = q[q.season_rate.fillna(0) >= 0.40]                      # he has actually cleared it in 40%+ of games
    q = q.assign(_d=(q.p - 0.62).abs()).sort_values("_d").drop_duplicates(["player_id", "market"]).copy()   # the line nearest 62%
    fits = [leg_fit(r, prof) for r in q.itertuples()]
    q["fit"] = [f for f, _ in fits]; q["fit_why"] = [w for _, w in fits]
    if reads is not None:
        from .matchup import apply as _apply_reads
        q = _apply_reads(q, reads, drop=False)     # aggressive lines: the read ranks, it does not veto
    q["score"] = np.log(q.p / (1 - q.p)) + FIT_WEIGHT * q.fit
    q = q.sort_values("score", ascending=False).reset_index(drop=True)
    cols = ["game_id", "team", "player_id", "name", "pos_group", "market", "k", "p", "season_hits", "season_n", "fit", "fit_why", "score"]
    lad = _greedy(q[cols], corr, max(sizes), fit_w=1.2 if reads is not None else None)
    out = []
    for n in sizes:
        legs = lad.head(n)
        if len(legs) == n:
            out.append({"n": n, "legs": legs, "p": _joint(legs, corr), "p_indep": float(legs.p.prod())})
    return {"profile": prof, "tickets": out, "pool": q[cols]}


def leg_text(r):
    nm = r.name if hasattr(r, "Index") else r["name"]
    return f"{nm} ANYTIME TD" if r.market == "atd" else f"{nm} {int(r.k)}+ {MK_LABEL[r.market]}"
