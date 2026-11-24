"""Props pick slip PDF: cross-game props parlays (4/6/8/10/12), per-game floor SGPs, per-pick intel."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .correlation import ticket_prob
from .intel import MK_LABEL, intel, load_defenders, risk_line
from .pick_slip import _kick
from .tickets import fair, greedy, pick_rungs

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, GREEN, LINE, BAND, AMBER = (colors.HexColor(c) for c in
                                         ("#161b26", "#5b6473", "#1d4e89", "#d5d9e0", "#f3f5f8", "#9a5b00"))


def am(p):
    a = fair(p)
    return f"+{a}" if a > 0 else str(a)


def leg_text(r):
    return f"{r['name']} {int(r.k)}+ {MK_LABEL[r.market]}"


def render(season, week, day, out_path, games=None, subtitle=""):
    L = pd.read_csv(ROOT / "outputs" / f"prop_ladders_{season}_wk{week}.csv")
    F = pd.read_parquet(ROOT / "outputs" / f"props_features_{season}_wk{week}.parquet")
    DF = load_defenders()
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
    sched = pd.read_csv(ROOT / "data" / "schedules.csv")
    S = sched[(sched.season == season) & (sched.week == week) & (sched.gameday == day)].set_index("game_id")
    if games is not None:
        S = S[S.index.isin(games)]
    L = L[L.game_id.isin(S.index)]
    F = F[F.game_id.isin(S.index)]
    fl = pick_rungs(L, "floor")
    combo = greedy(fl, 12, max_per_game=2, max_per_team=1).reset_index(drop=True)
    tickets = [(n, combo.head(n), ticket_prob(combo.head(n), corr), float(combo.head(n).p.prod()))
               for n in (4, 6, 8, 10, 12) if len(combo) >= n]
    sgps = []
    for g in S.sort_values(["gametime"]).index:
        sel = greedy(fl[fl.game_id == g], 6)
        if len(sel) >= 4:
            sgps.append((g, sel, ticket_prob(sel.head(4), corr), ticket_prob(sel, corr) if len(sel) >= 6 else None))

    ss = getSampleStyleSheet()
    T = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=21, textColor=INK, alignment=0,
                       spaceAfter=2)
    SUB = ParagraphStyle("S", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK,
                        spaceBefore=8, spaceAfter=4)
    B = ParagraphStyle("B", parent=ss["Normal"], fontSize=8.4, textColor=INK, leading=11, spaceAfter=2)
    RISK = ParagraphStyle("R", parent=B, textColor=AMBER)

    def tbl(rows, widths, head=INK):
        t = Table(rows, colWidths=[w * inch for w in widths], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 0), (-1, 0), head), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]), ("GRID", (0, 0), (-1, -1), 0.25, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2)]))
        return t

    when = pd.Timestamp(day).strftime("%A, %B %-d %Y")
    story = [Paragraph(f"Week {week} Props Picks — {when}", T),
             Paragraph(f"bet365 milestone props · built {datetime.now():%b %-d %H:%M} UTC · data-only model, every "
                       f"factor in FACTORS.md considered · {len(S)} games · floor legs = 70–88% (target 78%) · "
                       "props parlays never carry TD legs" + (f" · {subtitle}" if subtitle else ""), SUB), Spacer(1, 6),
             Paragraph("Cross-game props parlays", H2)]
    rows = [["Parlay", "Legs", "Hit chance", "Fair odds", "If independent", "Bet only if bet365 pays"]]
    for n, legs, pj, pi in tickets:
        rows.append([f"{n}-Leg props", f"Picks 1–{n}", f"{pj:.1%}", am(pj), f"{pi:.1%}", f"better than {am(pj)}"])
    story += [tbl(rows, [1.0, 0.9, 0.9, 0.9, 1.0, 1.9], GREEN),
              Paragraph("Each parlay builds on the one before it. At most 2 legs per game and 1 per team, so one "
                        "bad game script can't sink the slip. Same-game legs are priced with the measured correlations "
                        "(e.g. a QB's yards and his receiver's yards move together).", SUB),
              Paragraph("The picks", H2)]
    rows = [["#", "Leg", "Game", "Kickoff", "Model", "Fair", "2026 hits", "In parlays"]]
    for i, r in enumerate(combo.itertuples(), 1):
        g = S.loc[r.game_id]
        mem = " ".join(str(n) for n, *_ in tickets if i <= n)
        rows.append([i, Paragraph(f"<b>{leg_text(combo.iloc[i - 1])}</b> <font color='#5b6473'>{r.pos_group} {r.team}</font>",
                                  B), f"{g.away_team} @ {g.home_team}", _kick(g.gametime), f"{r.p:.0%}", am(r.p),
                     f"{int(r.season_hits)}/{int(r.season_n)}", mem])
    story.append(tbl(rows, [0.3, 2.5, 0.85, 0.8, 0.5, 0.55, 0.7, 1.0]))

    story += [PageBreak(), Paragraph("Bet slips", H2)]
    for n, legs, pj, pi in tickets:
        rows = [[f"{n}-LEG PROPS PARLAY", "", f"{pj:.1%} · fair {am(pj)}"]]
        for i, r in enumerate(legs.itertuples(), 1):
            g = S.loc[r.game_id]
            rows.append([f"{i}. {leg_text(legs.iloc[i - 1])}", f"{g.away_team} @ {g.home_team} · {_kick(g.gametime)}",
                         f"{r.p:.0%}"])
        t = Table(rows, colWidths=[3.2 * inch, 2.5 * inch, 1.5 * inch])
        t.setStyle(TableStyle([("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
                               ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5), ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 8.5),
                               ("ALIGN", (2, 0), (2, -1), "RIGHT"), ("BOX", (0, 0), (-1, -1), 0.8, GREEN),
                               ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story.append(KeepTogether([t, Spacer(1, 2), Paragraph(f"Joint {pj:.2%} with correlations vs {pi:.2%} if "
                                                               "independent.", SUB), Spacer(1, 8)]))

    story += [PageBreak(), Paragraph("Same-game parlays by game (floor legs, no TD legs)", H2)]
    rows = [["Game", "Kickoff", "Legs (1–4 core, 5–6 add-ons)", "4-leg", "6-leg"]]
    for g, sel, p4, p6 in sgps:
        sg = S.loc[g]
        legs_txt = "<br/>".join(f"{i}. {leg_text(sel.iloc[i - 1])} ({r.p:.0%})" for i, r in enumerate(sel.itertuples(), 1))
        rows.append([f"{sg.away_team} @ {sg.home_team}", _kick(sg.gametime), Paragraph(legs_txt, B),
                     f"{p4:.1%}\n{am(p4)}", f"{p6:.1%}\n{am(p6)}" if p6 else "–"])
    story += [tbl(rows, [0.8, 0.75, 4.1, 0.75, 0.75]),
              Paragraph("bet365 reprices same-game parlays. Type the SGP price it shows into the God's Eye slip to "
                        "check the edge.", SUB)]

    story += [PageBreak(), Paragraph("Pick intel — every factor, per pick", H2)]
    for i, r in enumerate(combo.itertuples(), 1):
        fr = F[(F.player_id == r.player_id) & (F.game_id == r.game_id)]
        if fr.empty:
            continue
        fr = fr.iloc[0]
        g = S.loc[r.game_id]
        rung = (f"<b>This line:</b> {int(r.k)}+ {MK_LABEL[r.market]}: cleared in {int(r.season_hits)} of "
                f"{int(r.season_n)} games this season; model {r.p:.0%} (fair {am(r.p)}).")
        head = Table([[f"{i}. {leg_text(combo.iloc[i - 1])}", f"{r.team} {'vs' if fr.is_home else '@'} {r.opp} · "
                       f"{_kick(g.gametime)}", f"{r.p:.0%} · fair {am(r.p)}"]],
                     colWidths=[2.9 * inch, 2.3 * inch, 2.0 * inch])
        head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                                  ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 9.3), ("FONT", (1, 0), (-1, 0), "Helvetica", 8.3),
                                  ("ALIGN", (2, 0), (2, 0), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        bullets = intel(fr, F, DF, g, market=r.market, rung_line=rung)
        story.append(KeepTogether([head, Spacer(1, 3)] + [Paragraph("• " + b, B) for b in bullets] +
                                  [Paragraph(risk_line(fr, r.market), RISK), Spacer(1, 8)]))

    story += [Paragraph("Ground rules", H2)] + [Paragraph("• " + t, B) for t in [
        "Probabilities come from one model per market trained on official box scores, with out-of-sample calibration. "
        "2025–26 holdout: floor-band legs priced ~79% hit 76–81%, depending on market (receiving yards ran ~2 pts hot).",
        "Questionable players and anyone back from a 2+ game absence are kept off parlays (singles only). The role gate "
        "requires 2+ games and real volume.",
        "Re-run at inactives (~90 min before kickoff); a scratched leg is replaced by the next qualifying leg.",
        "Long parlays compound small errors: the 4- and 6-leg are the plays; size the rest small."]]
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                      topMargin=0.55 * inch, bottomMargin=0.55 * inch, title=f"Week {week} Props Picks — {when}",
                      author="God's Eye").build(story)
    return combo, tickets, sgps
