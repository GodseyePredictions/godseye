"""Decision slip: the model's ATD picks for bet365 4/6/8/10/12-leg parlays + per-pick intel (PDF)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .atd_slip import CUSHION, am, joint

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, GREEN, LINE, BAND, AMBER = (colors.HexColor(c) for c in
                                         ("#161b26", "#5b6473", "#0b6e4f", "#d5d9e0", "#f3f5f8", "#9a5b00"))
SIZES = (4, 6, 8, 10, 12)
TEAM_NAMES = {"DET": "Detroit", "KC": "Kansas City", "SF": "San Francisco", "DAL": "Dallas", "LA": "the Rams",
              "CHI": "Chicago", "IND": "Indianapolis", "ATL": "Atlanta", "NE": "New England", "CAR": "Carolina",
              "SEA": "Seattle", "CIN": "Cincinnati"}


def _ord(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _kick(t):
    h, m = map(int, str(t).split(":"))
    return f"{(h - 1) % 12 + 1}:{m:02d} {'am' if h < 12 else 'pm'} ET"


def select_picks(F: pd.DataFrame, n=12) -> pd.DataFrame:
    ok = F[~F.singles_only.fillna(False).astype(bool)].sort_values("p_attd", ascending=False)
    return ok.drop_duplicates("team").head(n).reset_index(drop=True)   # ≤1 per team: teammates split TDs


def reasons(r, F: pd.DataFrame, sched_row) -> tuple[list[str], str]:
    """Data-only reasoning bullets + one risk line for a pick."""
    teams = F.drop_duplicates("team")
    imp_rank = int((teams.implied_filled > r.implied_filled).sum()) + 1
    n_teams = len(teams)
    lam = r.lam_team_rush + r.lam_team_pass
    tn = TEAM_NAMES.get(r.team, r.team)
    out = [f"<b>Team scoring:</b> {tn} implied for {r.implied_filled:.1f} points ({_ord(imp_rank)} of {n_teams} "
           f"teams on the slate), so the model expects {lam:.1f} offensive TDs ({r.lam_team_rush:.1f} rushing, "
           f"{r.lam_team_pass:.1f} receiving)."]
    if r.pos_group == "RB":
        out.append(f"<b>Goal-line role:</b> takes {r.sh_rush_i10_e3:.0%} of {tn}'s inside-10 carries and "
                   f"{r.sh_rush_rz_e3:.0%} of red-zone carries ({r.rush_i10_e3:.1f} inside-10 carries/game recently), "
                   f"plus {r.sh_tgt_rz_e3:.0%} of red-zone targets. Model share of team rushing TDs: {r.rush_share:.0%}.")
    else:
        out.append(f"<b>Red-zone role:</b> gets {r.sh_tgt_rz_e3:.0%} of {tn}'s red-zone targets and "
                   f"{r.sh_ez_tgt_e3:.0%} of end-zone targets ({r.ez_tgt_e3:.1f} end-zone targets/game recently, "
                   f"{r.targets_e3:.1f} targets/game). Model share of team receiving TDs: {r.rec_share:.0%}.")
    form = (f"<b>Production:</b> {int(r.season_tds)} TDs this season, scoring in {int(r.season_td_games)} of "
            f"{int(r.season_games)} games. Recent expected TDs {r.xtd_e3:.2f}/game vs actual {r.td_e3:.2f}/game")
    if r.td_e3 > 1.3 * r.xtd_e3:
        form += ": he's running above his opportunity, so the model prices the opportunity, not the streak."
    elif r.td_e3 < 0.75 * r.xtd_e3:
        form += ": he's scoring less than his usage says he should, and the model expects that to come back up."
    else:
        form += ": scoring is in line with usage, a stable profile."
    out.append(form)
    pos = r.pos_group if r.pos_group in ("RB", "WR", "TE", "QB") else "RB"
    col = f"td_allowed_{pos}_dc"
    defs = F.drop_duplicates("opp")[["opp", col]].dropna()
    d_rank = int((defs[col] > r[col]).sum()) + 1
    m = (f"<b>Matchup:</b> {r.opp} allows {r[col]:.2f} {pos} TDs per game recently ({_ord(d_rank)} most of "
         f"{len(defs)} defenses playing) and turns {r.rz_td_rate_allowed_dc:.0%} of opponents' red-zone trips into TDs.")
    if r.def_starters_out >= 1:
        m += f" {r.opp} has {int(r.def_starters_out)} defensive starter(s) ruled Out/Doubtful."
    out.append(m)
    sp = r.spread
    script = (f"favoured by {sp:.1f}, a positive script that means late carries and goal-line snaps" if sp >= 3 else
              (f"an underdog by {-sp:.1f}, so script risk if they trail" if sp <= -3 else f"a near pick'em ({sp:+.1f})"))
    env = []
    if r.wx_cat == "indoor":
        env.append("indoors, no weather effect")
    elif pd.isna(r.temp):
        env.append(f"international game at {sched_row.stadium}, no NWS forecast (weather treated as neutral)")
    else:
        env.append(f"{r.wx_cat}, {r.temp:.0f}°F, wind {r.wind:.0f} mph at kickoff (NWS)")
    env.append("turf" if r.is_turf else "grass")
    if r.rest_days >= 10:
        env.append(f"{int(r.rest_days)} days' rest (off a bye)")
    if abs(r.tz_shift) >= 2 and not r.is_home:
        env.append(f"{r.travel_miles:,.0f}-mile trip, {r.tz_shift:+.0f}h time zones")
    elif r.slot == "intl_morning":
        env.append(f"{r.travel_miles:,.0f}-mile trip for both teams")
    out.append(f"<b>Game:</b> {'home' if r.is_home else 'road'}, {script}; " + ", ".join(env) + ".")

    risk = []
    if r.offense_pct_e3 < 0.70:
        risk.append(f"snap share {r.offense_pct_e3:.0%}, so he's not an every-down player")
    if r.pos_group == "RB" and r.rush_share < 0.6:
        risk.append(f"a committee backfield (model gives him only {r.rush_share:.0%} of rushing TDs)")
    if sp <= -3:
        risk.append("trailing game script")
    if r.pos_group == "WR":
        risk.append("WRs on tickets ran ~7 pts hot in the 2026 ledger, so only take him at the 'play at' price or longer")
    if r[col] < 0.8:
        risk.append(f"{r.opp} has been stingy against {pos}s")
    if r.slot == "intl_morning":
        risk.append("international early kickoff: body-clock and travel unknowns for both sides")
    if abs(r.tz_shift) >= 3 and not r.is_home and r.slot != "intl_morning":
        risk.append("cross-country trip with an early body-clock kickoff")
    return out, ("; ".join(risk) if risk else "no structural red flags. The main risk is just football variance.")


def render(season, week, day, out_path, games=None, subtitle=""):
    F = pd.read_parquet(ROOT / "outputs" / f"projection_features_{season}_wk{week}.parquet")
    sched = pd.read_csv(ROOT / "data" / "schedules.csv")
    S = sched[(sched.season == season) & (sched.week == week) & (sched.gameday == day)].set_index("game_id")
    if games is not None:
        S = S[S.index.isin(games)]
    F = F[F.game_id.isin(S.index)].copy()
    corr = json.loads((ROOT / "models" / "correlations.json").read_text())
    from .atd_slip import STYLES, _pick_style
    F["play_at"] = (F.p_attd - F.pos_group.map(CUSHION).fillna(0.04)).map(am)
    F["matchup"] = [f"{r.team} vs {r.opp}" if r.is_home else f"{r.team} @ {r.opp}" for r in F.itertuples()]
    F["kick"] = [_kick(S.loc[g, "gametime"]) for g in F.game_id]
    ok = F[~F.singles_only.fillna(False).astype(bool)].sort_values("p_attd", ascending=False)
    STYLE_SIZES = {"chalk": SIZES, "balanced": SIZES, "air": (4, 6, 8)}
    styled = {}
    for st in STYLES:
        picks_s = _pick_style(ok, max(STYLE_SIZES[st]), st).reset_index(drop=True)
        tk = []
        for n in STYLE_SIZES[st]:
            legs = picks_s.head(n)
            if len(legs) < n:
                break
            tk.append((n, legs, joint(legs, corr), float(np.prod(legs.p_attd))))
        styled[st] = (picks_s, tk)
    picks, tickets = styled["chalk"]
    all_picks = pd.concat([styled[st][0] for st in STYLES]).drop_duplicates("player_id")
    all_picks = all_picks.sort_values("p_attd", ascending=False).reset_index(drop=True)

    ss = getSampleStyleSheet()
    T = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=21, textColor=INK,
                       alignment=0, spaceAfter=2)
    SUB = ParagraphStyle("S", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK,
                        spaceBefore=8, spaceAfter=4)
    B = ParagraphStyle("B", parent=ss["Normal"], fontSize=8.6, textColor=INK, leading=11.4, spaceAfter=2)
    RISK = ParagraphStyle("R", parent=B, textColor=AMBER)
    CELL = ParagraphStyle("C", parent=ss["Normal"], fontSize=8, leading=10, textColor=INK)

    def tbl(rows, widths, head=INK, bold_first_col=False):
        t = Table(rows, colWidths=[w * inch for w in widths], repeatRows=1)
        st = [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("BACKGROUND", (0, 0), (-1, 0), head), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]), ("GRID", (0, 0), (-1, -1), 0.25, LINE),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3.5),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
        if bold_first_col:
            st.append(("FONT", (1, 1), (1, -1), "Helvetica-Bold", 8.5))
        t.setStyle(TableStyle(st))
        return t

    when = pd.Timestamp(day).strftime("%A, %B %-d %Y")
    story = [Paragraph(f"Week {week} ATD Picks — {when}", T),
             Paragraph(f"bet365 anytime-TD parlays · built {datetime.now():%b %-d %H:%M} UTC from the ATTD model "
                       f"(data only, no media picks) · {len(S)} games · injury report + personnel overrides applied"
                       + (f" · {subtitle}" if subtitle else ""), SUB), Spacer(1, 6)]

    # three ticket styles
    rows = [["Style", "4-leg", "6-leg", "8-leg", "10-leg", "12-leg"]]
    for st, meta in STYLES.items():
        tk = dict((n, (pj, pi)) for n, _, pj, pi in styled[st][1])
        rows.append([meta["label"]] + [f"{tk[n][0]:.1%}\n{am(tk[n][0])}" if n in tk else "—" for n in SIZES])
    story += [Paragraph("Three ways to build it", H2), tbl(rows, [1.1, 1.24, 1.24, 1.24, 1.24, 1.24], GREEN)]
    for st, meta in STYLES.items():
        story.append(Paragraph(f"<b>{meta['label']}:</b> {meta['desc']}", SUB))
    story.append(Paragraph(
        "Chance to hit over fair odds. Each parlay builds on the one before it. One player per team on every ticket, "
        "because teammates split the same touchdowns; opponents in the same game carry the shootout correlation. "
        "Air stops at 8 legs: beyond that it is a lottery ticket at any price.", SUB))

    for st, meta in STYLES.items():
        picks_s, tk = styled[st]
        sizes_s = [n for n, *_ in tk]
        story.append(Paragraph(f"{meta['label']} picks", H2))
        rows = [["#", "Player", "Pos", "Game", "Kickoff", "TD chance", "Fair", "Play at", "In parlays"]]
        for i, r in enumerate(picks_s.head(max(sizes_s)).itertuples(), 1):
            mem = " ".join(str(n) for n in sizes_s if i <= n)
            rows.append([i, r.name, r.pos_group, r.matchup, r.kick, f"{r.p_attd:.0%}", am(r.p_attd), r.play_at, mem])
        story.append(tbl(rows, [0.3, 1.55, 0.4, 1.0, 0.85, 0.7, 0.55, 0.6, 1.25], INK, bold_first_col=True))
    story.append(Paragraph("<b>Play at</b> = the shortest single-leg price worth taking (fair plus a cushion: "
                           "RB +3 pts, TE/QB +4, WR +6; WRs on tickets ran ~7 pts hot in the 2026 ledger).", SUB))

    # each parlay as a slip
    story.append(PageBreak())
    story.append(Paragraph("Bet slips", H2))
    slips = [(st, n, legs, pj, pi) for st in STYLES for n, legs, pj, pi in styled[st][1] if n <= 6 or st == "chalk"]
    for st, n, legs, pj, pi in slips:
        rows = [[f"{STYLES[st]['label'].upper()} · {n}-LEG ATD PARLAY", "", f"{pj:.1%} · fair {am(pj)}"]]
        for i, r in enumerate(legs.itertuples(), 1):
            rows.append([f"{i}. {r.name} — Anytime TD", f"{r.matchup} · {r.kick}", f"{r.p_attd:.0%}"])
        pairs = [f"{q.iloc[0]['name']} + {q.iloc[1]['name']}" for _, q in legs.groupby("game_id") if len(q) == 2]
        t = Table(rows, colWidths=[3.1 * inch, 2.6 * inch, 1.5 * inch])
        t.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5), ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 8.5),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"), ("BOX", (0, 0), (-1, -1), 0.8, GREEN),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2)]))
        note = (f"Same-game pairs (correlation priced in): {', '.join(pairs)}. " if pairs else
                "Every leg is from a different game (independent). ")
        note += f"Joint {pj:.2%} vs {pi:.2%} if the legs were independent."
        story.append(KeepTogether([t, Spacer(1, 2), Paragraph(note, SUB), Spacer(1, 9)]))

    # intel
    story.append(PageBreak())
    story.append(Paragraph("Pick intel — why each player is on the slip", H2))
    for i, r in enumerate(all_picks.itertuples(), 1):
        rr = all_picks.iloc[i - 1]
        from .intel import intel as _intel, load_defenders, risk_line
        bullets = _intel(rr, F, load_defenders(), S.loc[rr.game_id], market="atd")
        risk = risk_line(rr, "atd").replace("<b>Risk:</b> ", "")
        head = Table([[f"{i}. {r.name}  ({r.team} {r.pos_group})", f"{r.matchup} · {r.kick}",
                       f"{r.p_attd:.0%} · fair {am(r.p_attd)} · play at {r.play_at}"]],
                     colWidths=[2.45 * inch, 2.15 * inch, 2.6 * inch])
        head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                                  ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 9.5),
                                  ("FONT", (1, 0), (-1, 0), "Helvetica", 8.5), ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                                  ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        if rr.pos_group == "RB":
            stat = [["Snap %", "Carries/g", "Inside-10 car/g", "Inside-10 share", "RZ target share", "xTD/g", "Season"],
                    [f"{rr.offense_pct_e3:.0%}", f"{rr.carries_e3:.1f}", f"{rr.rush_i10_e3:.1f}",
                     f"{rr.sh_rush_i10_e3:.0%}", f"{rr.sh_tgt_rz_e3:.0%}", f"{rr.xtd_e3:.2f}",
                     f"{int(rr.season_tds)} TD in {int(rr.season_games)} g"]]
        else:
            stat = [["Snap %", "Targets/g", "RZ targets/g", "RZ target share", "End-zone share", "xTD/g", "Season"],
                    [f"{rr.offense_pct_e3:.0%}", f"{rr.targets_e3:.1f}", f"{rr.tgt_rz_e3:.1f}",
                     f"{rr.sh_tgt_rz_e3:.0%}", f"{rr.sh_ez_tgt_e3:.0%}", f"{rr.xtd_e3:.2f}",
                     f"{int(rr.season_tds)} TD in {int(rr.season_games)} g"]]
        st = Table(stat, colWidths=[1.03 * inch] * 7)
        st.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica", 7), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                                ("FONT", (0, 1), (-1, 1), "Helvetica-Bold", 9), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("BACKGROUND", (0, 0), (-1, -1), BAND), ("TOPPADDING", (0, 0), (-1, -1), 2),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        block = [head, st, Spacer(1, 3)] + [Paragraph("• " + b, B) for b in bullets] + \
                [Paragraph("<b>Risk:</b> " + risk, RISK), Spacer(1, 9)]
        story.append(KeepTogether(block))

    story.append(Paragraph("Ground rules", H2))
    for t in ["Probabilities = chance of ≥1 rushing/receiving TD, given he plays. Out-of-sample 2025–26 the model "
              "scores log loss 0.387 / AUC 0.76; on the 223 ATD legs shipped in the 2026 ledger it priced slightly "
              "better than the old engine.",
              "Kept off every parlay (singles only): Questionable players and anyone who missed 2+ of his team's "
              "last 4 games, e.g. Amon-Ra St. Brown (Q), George Pickens (Q), Josh Jacobs (2 of last 4 missed).",
              "Re-run at inactives (~90 min before kickoff). A scratched pick gets replaced by the next player on the board.",
              "Long parlays are lottery tickets even when every leg is fair: size at quarter-Kelly or less. The 4- "
              "and 6-leg are the model's real plays."]:
        story.append(Paragraph("• " + t, B))

    doc = SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.55 * inch, bottomMargin=0.55 * inch,
                            title=f"Week {week} ATD Picks — {when}", author="ATTD model")
    doc.build(story)
    return styled, all_picks
