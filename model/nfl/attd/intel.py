"""Per-pick intel, shared by the ATD slip, the props slip and the God's Eye site.

Covers every factor in FACTORS.md that applies to the player: team scoring, role, form, the named defenders he faces
(WR vs CB/S, RB's O-line vs DL/LB, TE vs LB/S, QB vs pass rush), unit-vs-unit efficiency, OC vs DC tendencies,
venue / surface / weather / slot / time zones / rest / home-away, and a risk line.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TEAM = {"ARI": "Arizona", "ATL": "Atlanta", "BAL": "Baltimore", "BUF": "Buffalo", "CAR": "Carolina", "CHI": "Chicago",
        "CIN": "Cincinnati", "CLE": "Cleveland", "DAL": "Dallas", "DEN": "Denver", "DET": "Detroit", "GB": "Green Bay",
        "HOU": "Houston", "IND": "Indianapolis", "JAX": "Jacksonville", "KC": "Kansas City", "LA": "the Rams",
        "LAC": "the Chargers", "LV": "Las Vegas", "MIA": "Miami", "MIN": "Minnesota", "NE": "New England",
        "NO": "New Orleans", "NYG": "the Giants", "NYJ": "the Jets", "PHI": "Philadelphia", "PIT": "Pittsburgh",
        "SEA": "Seattle", "SF": "San Francisco", "TB": "Tampa Bay", "TEN": "Tennessee", "WAS": "Washington"}
MK_LABEL = {"carries": "carries", "rush_yds": "rush yds", "rec": "receptions", "rec_yds": "rec yds",
            "pass_att": "pass att", "pass_yds": "pass yds", "pass_td": "pass TDs"}


def _ord(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _rank(F, col, val, high_is_more=True, by="opp"):
    s = F.drop_duplicates(by)[col].dropna()
    if pd.isna(val) or s.empty:
        return None, len(s)
    return int(((s > val) if high_is_more else (s < val)).sum()) + 1, len(s)


def load_defenders():
    f = ROOT / "outputs" / "defenders_upcoming.csv"
    return pd.read_csv(f) if f.exists() else pd.DataFrame()


def _names(DF, game, team, unit, n):
    q = DF[(DF.game_id == game) & (DF.team == team) & (DF.unit == unit)].sort_values("defense_pct_e", ascending=False)
    out = []
    for r in q.head(n).itertuples():
        if unit in ("CB", "S"):
            stat = f"{r.pd_e:.1f} PBU, {r.int_e:.2f} INT/g"
        else:
            stat = f"{r.sack_e:.2f} sacks, {r.tfl_e:.1f} TFL/g"
        out.append(f"{r.player} ({r.defense_pct_e:.0%} snaps; {stat})")
    return out


def matchup_line(r, F, DF) -> str:
    g, opp, pos = r.game_id, r.opp, r.pos_group
    tn, on = TEAM.get(r.team, r.team), TEAM.get(opp, opp)
    def rk(col, val, hi=True):
        k, n = _rank(F, col, val, hi)
        return f" ({_ord(k)} most of {n})" if k else ""
    if pos == "WR":
        names = _names(DF, g, opp, "CB", 3) + _names(DF, g, opp, "S", 2)
        s = (f"<b>vs {opp} secondary:</b> {', '.join(names) if names else 'no projected list'}. {on} allows "
             f"{r.ypt_allowed_WR_dc:.1f} yds/target to WRs{rk('ypt_allowed_WR_dc', r.ypt_allowed_WR_dc)}, "
             f"{r.cr_allowed_WR_dc:.0%} catch rate, {r.explosive_allowed_dc:.0%} of passes going 20+.")
        if r.get("def_CB_avail", 1) < 0.85:
            s += f" Corner room is thin: {r.def_CB_avail:.0%} of normal CB snaps available."
    elif pos == "TE":
        names = _names(DF, g, opp, "LB", 2) + _names(DF, g, opp, "S", 2)
        s = (f"<b>vs {opp} linebackers & safeties:</b> {', '.join(names) if names else 'no projected list'}. {on} "
             f"allows {r.ypt_allowed_TE_dc:.1f} yds/target to TEs{rk('ypt_allowed_TE_dc', r.ypt_allowed_TE_dc)} at a "
             f"{r.cr_allowed_TE_dc:.0%} catch rate.")
    elif pos == "RB":
        names = _names(DF, g, opp, "DL", 3) + _names(DF, g, opp, "LB", 2)
        s = (f"<b>{r.team} O-line vs {opp} front:</b> {tn}'s RBs average {r.ol_rb_ypc_oc:.1f} yds/carry and get stuffed "
             f"{r.ol_stuff_rate_oc:.0%} of the time; {on} allows {r.dl_rb_ypc_allowed_dc:.1f}"
             f"{rk('dl_rb_ypc_allowed_dc', r.dl_rb_ypc_allowed_dc)} and stuffs {r.dl_stuff_forced_dc:.0%}. Front: "
             f"{', '.join(names) if names else 'no projected list'}. In the passing game {on} allows "
             f"{r.ypt_allowed_RB_dc:.1f} yds/target to RBs.")
        if r.get("own_ol_out", 0) >= 0.5:
            s += f" {r.team} is missing O-line snap share ({r.own_ol_out:.1f} starters' worth out)."
    else:  # QB
        names = _names(DF, g, opp, "DL", 3)
        s = (f"<b>Pass rush:</b> {', '.join(names) if names else 'no projected list'}. {on} sacks on "
             f"{r.dl_sack_rate_dc:.1%} of dropbacks; {tn} allows sacks on {r.ol_sack_rate_oc:.1%}.")
    if r.def_starters_out >= 1:
        s += f" {opp} has {int(r.def_starters_out)} defensive starter(s) ruled Out/Doubtful."
    return s


def scheme_line(r) -> str:
    oc = (f"{r.team} OC: pass rate {r.proe_oc:+.1f}% vs expected (red zone {r.rz_pass_oc:.0%} pass), "
          f"targets WR {r.tgt_WR_oc:.0%} / TE {r.tgt_TE_oc:.0%} / RB {r.tgt_RB_oc:.0%}, deep shots {r.deep_rate_oc:.0%}, "
          f"screens {r.screen_rate_oc:.0%}")
    dc = (f"{r.opp} DC: blitzes {r.blitz_rate_dc:.0%}, light box (≤6) on {r.light_box_dc:.0%} of runs, "
          f"deep passes faced {r.deep_rate_allowed_dc:.0%}, red-zone TD rate allowed {r.rz_td_rate_allowed_dc:.0%}")
    return f"<b>Play-calling:</b> {oc}. {dc}."


def env_line(r, sched_row) -> str:
    bits = [("home" if r.is_home else "road"), f"{sched_row.stadium}", "turf" if r.is_turf else "grass"]
    if r.wx_cat == "indoor":
        bits.append("indoors (weather neutral)")
    elif pd.isna(r.temp):
        bits.append("no NWS forecast (international), weather neutral")
    else:
        bits.append(f"{r.wx_cat}, {r.temp:.0f}°F, wind {r.wind:.0f} mph")
    slot = {"early": "early 1pm window", "late": "late afternoon window", "night": "prime-time night game",
            "intl_morning": "international morning kickoff", "other_day": "non-Sunday"}.get(r.slot, r.slot)
    bits.append(slot)
    if not r.is_home and abs(r.tz_shift) >= 1:
        bits.append(f"{r.travel_miles:,.0f}-mile trip, {r.tz_shift:+.0f}h time zones (kickoff {r.body_clock_hour:.0f}:00 "
                    "on his body clock)")
    elif r.slot == "intl_morning":
        bits.append(f"{r.travel_miles:,.0f}-mile trip")
    if r.rest_days >= 10:
        bits.append(f"{int(r.rest_days)} days' rest (off bye)")
    elif r.rest_days <= 5:
        bits.append(f"short week ({int(r.rest_days)} days)")
    sp = getattr(r, "split_home_away", np.nan)
    tail = ""
    if not pd.isna(sp) and abs(sp - 1) >= 0.08:
        tail = (f" His {'home' if r.is_home else 'road'} scoring runs {sp:.2f}× his norm (shrunk)."
                if True else "")
    return "<b>Game:</b> " + ", ".join(bits) + "." + tail


def role_line(r, market=None) -> str:
    tn = TEAM.get(r.team, r.team)
    if market in (None, "atd"):
        if r.pos_group in ("RB", "QB"):
            return (f"<b>Goal-line role:</b> {r.sh_rush_i10_e3:.0%} of {tn}'s inside-10 carries, {r.sh_rush_rz_e3:.0%} of "
                    f"red-zone carries, {r.sh_tgt_rz_e3:.0%} of red-zone targets ({r.carries_e3:.1f} carries, "
                    f"{r.targets_e3:.1f} targets/g). Share of team rushing TDs: {r.rush_share:.0%}.")
        return (f"<b>Red-zone role:</b> {r.sh_tgt_rz_e3:.0%} of {tn}'s red-zone targets, {r.sh_ez_tgt_e3:.0%} of end-zone "
                f"targets ({r.targets_e3:.1f} targets/g, {r.offense_pct_e3:.0%} snaps). Share of team receiving TDs: "
                f"{r.rec_share:.0%}.")
    vol = {"carries": f"{r.carries_p3:.1f} carries/g recently ({r.sh_carries_e3:.0%} of team carries)",
           "rush_yds": f"{r.rush_yds_p3:.0f} rush yds/g recently on {r.carries_p3:.1f} carries",
           "rec": f"{r.rec_p3:.1f} catches on {r.tgt_p3:.1f} targets/g ({r.sh_targets_e3:.0%} target share)",
           "rec_yds": f"{r.rec_yds_p3:.0f} rec yds/g on {r.tgt_p3:.1f} targets ({r.sh_air_yds_e3:.0%} of team air yards)",
           "pass_att": f"{r.pass_att_p3:.1f} attempts/g recently (season {r.pass_att_std:.1f})",
           "pass_yds": f"{r.pass_yds_p3:.0f} pass yds/g recently (season {r.pass_yds_std:.0f})",
           "pass_td": f"{r.pass_td_p3:.1f} TD passes/g recently (season {r.pass_td_std:.1f}); team red-zone pass rate "
                      f"{r.rz_pass_oc:.0%}"}[market]
    return f"<b>Volume:</b> {vol}; {r.offense_pct_e3:.0%} of snaps."


def scoring_line(r, F) -> str:
    k, n = _rank(F, "implied_filled", r.implied_filled, True, by="team")
    lam = r.lam_team_rush + r.lam_team_pass
    sp = r.spread
    script = (f"favoured by {sp:.1f}" if sp >= 1 else (f"an underdog by {-sp:.1f}" if sp <= -1 else "a pick'em"))
    return (f"<b>Team outlook:</b> {TEAM.get(r.team, r.team)} implied for {r.implied_filled:.1f} pts "
            f"({_ord(k)} of {n} teams), {script}; model expects {lam:.1f} offensive TDs ({r.lam_team_rush:.1f} rush / "
            f"{r.lam_team_pass:.1f} pass).")


def tempo_line(r) -> str:
    ep, et = r.get("exp_plays", np.nan), r.get("exp_top_sec", np.nan)
    if ep is None or pd.isna(ep):
        return ""
    tn = TEAM.get(r.team, r.team)
    snaps = r.get("exp_snaps", np.nan); tof = r.get("exp_time_on_field", np.nan)
    bits = [f"{tn} project to ~{ep:.0f} offensive plays and {int(et // 60)}:{int(et % 60):02d} of possession "
            f"(their pace {r.get('sec_per_play_tp', np.nan):.1f} s/play; opponent allows {r.get('plays_allowed_tpd', np.nan):.0f} plays/g)"]
    if not pd.isna(snaps):
        bits.append(f"at {r.offense_pct_e3:.0%} of snaps that is ~{snaps:.0f} snaps, ~{int(tof // 60)}:{int(tof % 60):02d} on the field")
    op, dp_ = r.get("off_pen_rate_tp", np.nan), r.get("def_pen_rate_tpd", np.nan)
    if not pd.isna(op) and not pd.isna(dp_):
        bits.append(f"penalties: {tn} flagged on {op:.1%} of plays, this defence {dp_:.1%} (league 6.4% / 5.2%)")
    st, fg = r.get("stall3_rate_tp", np.nan), r.get("fg_after3_pd_tp", np.nan)
    if not pd.isna(st):
        bits.append(f"{st:.0%} of failed 3rd downs end the drive ({r.get('punt_after3_pd_tp', np.nan):.0%} of drives punt, {fg:.0%} FG)")
    return "<b>Tempo & discipline:</b> " + "; ".join(bits) + "."


def risk_line(r, market=None) -> str:
    risk = []
    if r.offense_pct_e3 < 0.65:
        risk.append(f"snap share only {r.offense_pct_e3:.0%}")
    if r.pos_group == "RB" and r.rush_share < 0.6 and market in (None, "atd", "carries", "rush_yds"):
        risk.append(f"committee backfield ({r.rush_share:.0%} of rushing TDs)")
    if r.spread <= -3 and market in (None, "atd", "carries", "rush_yds"):
        risk.append("trailing game script cuts carries")
    if r.spread >= 7 and market in ("pass_att", "pass_yds", "rec", "rec_yds"):
        risk.append("big favourite: may run the clock late, which caps passing volume")
    if r.pos_group == "WR" and market in (None, "atd"):
        risk.append("WRs on tickets ran ~7 pts hot in the ledger, so take him only at the play-at price")
    if r.slot == "intl_morning":
        risk.append("international early kickoff")
    if r.wx_cat in ("rain", "snow") or (not pd.isna(r.wind) and r.wind >= 15):
        risk.append("weather can cut passing")
    if r.get("def_CB_avail", 1) < 0.85 and r.pos_group == "WR":
        pass
    return ("<b>Risk:</b> " + "; ".join(risk) + ".") if risk else "<b>Risk:</b> no structural red flags; normal variance."


def intel(r, F, DF, sched_row, market=None, rung_line=None) -> list[str]:
    out = [scoring_line(r, F), role_line(r, market)]
    if rung_line:
        out.append(rung_line)
    elif market in (None, "atd"):
        _i = lambda v: 0 if pd.isna(v) else int(v)  # noqa: E731
        form = (f"<b>Form:</b> {_i(r.season_tds)} TDs this season, scoring in {_i(r.season_td_games)} of "
                f"{_i(r.season_games)} games; expected TDs {r.xtd_e3:.2f}/g vs actual {r.td_e3:.2f}/g")
        if r.td_e3 > 1.3 * r.xtd_e3:
            form += ": running hot, so the model prices the opportunity, not the streak."
        elif r.td_e3 < 0.75 * r.xtd_e3:
            form += ": scoring below his usage, and the model expects that to come back up."
        else:
            form += ": in line with usage."
        out.append(form)
    out += [matchup_line(r, F, DF), scheme_line(r), env_line(r, sched_row)]
    tl = tempo_line(r)
    if tl:
        out.append(tl)
    return out
