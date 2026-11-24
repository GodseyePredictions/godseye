"""Render the ATD slip as a PDF (reportlab)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .atd_slip import am

INK, MUTED, ACCENT, LINE, BAND = (colors.HexColor(c) for c in ("#1a1f2b", "#5b6473", "#0b6e4f", "#d5d9e0", "#f3f5f8"))


def _styles():
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=s["Title"], fontName="Helvetica-Bold", fontSize=20, textColor=INK,
                                alignment=TA_LEFT, spaceAfter=4),
        "sub": ParagraphStyle("s", parent=s["Normal"], fontSize=9, textColor=MUTED, leading=12),
        "h2": ParagraphStyle("h2", parent=s["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK,
                             spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("b", parent=s["Normal"], fontSize=9, textColor=INK, leading=12),
        "small": ParagraphStyle("sm", parent=s["Normal"], fontSize=7.5, textColor=MUTED, leading=10),
        "cell": ParagraphStyle("c", parent=s["Normal"], fontSize=8, textColor=INK, leading=10),
    }


def _table(rows, widths, header_bg=INK):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), header_bg), ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]), ("GRID", (0, 0), (-1, -1), 0.25, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def render(path, P: pd.DataFrame, tickets, sched: pd.DataFrame, title: str, notes: list[str], n_games=None):
    S = _styles()
    kick = sched.set_index("game_id").gametime.to_dict()
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.55 * inch, rightMargin=0.55 * inch,
                            topMargin=0.55 * inch, bottomMargin=0.55 * inch, title=title, author="ATTD engine")
    st = [Paragraph(title, S["title"]),
          Paragraph(f"Built {datetime.now():%b %d %Y %H:%M} · {n_games or P.game_id.nunique()} games · data-only model (no media picks) · "
                    "probability = P(≥1 rushing/receiving TD | plays) · fair = break-even American price · "
                    "<b>play at</b> = shortest bet365 price worth taking (fair + position cushion).", S["sub"]),
          Spacer(1, 8)]

    # summary strip
    summ = [["Ticket", "Joint prob.", "Fair price", "If independent", "Correlation lift"]]
    for t in tickets:
        summ.append([f"{t['n']}-leg", f"{t['p']:.1%}", am(t["p"]), f"{t['p_indep']:.1%}", f"x{t['lift']:.3f}"])
    st += [Paragraph("Tickets at a glance", S["h2"]), _table(summ, [1.2 * inch] * 5, ACCENT), Spacer(1, 6),
           Paragraph("All tickets nest: the 4-leg is the first four legs of the 6-leg, and so on. ≤1 player per "
                     "team, because teammates compete for the same touchdowns (measured ρ ≈ −0.04 to −0.07). "
                     "Opponents in the same game are mildly positively correlated (ρ ≈ +0.03, shootouts) and legs "
                     "from different games are independent.", S["small"])]

    # each ticket
    for t in tickets:
        rows = [["#", "Player", "Pos", "Team", "Game", "Kick (ET)", "Model", "Fair", "Play at"]]
        for i, r in enumerate(t["legs"].itertuples(), 1):
            rows.append([i, r.name, r.pos_group, r.team, r.matchup, kick.get(r.game_id, ""), f"{r.p_attd:.0%}",
                         am(r.p_attd), r.play_at])
        pair_txt = ("Same-game pairs: " + "; ".join(f"{a} + {b} ({g}, ρ={rho:+.3f})" for a, b, g, rho in t["pairs"])
                    if t["pairs"] else "No same-game pairs: every leg is from a different game (independent).")
        block = [Paragraph(f"{t['n']}-leg ATD — {t['p']:.1%} · fair {am(t['p'])}", S["h2"]),
                 _table(rows, [w * inch for w in [0.3, 1.6, 0.4, 0.45, 0.85, 0.65, 0.55, 0.6, 0.6]], INK),
                 Spacer(1, 3), Paragraph(pair_txt + f" Joint {t['p']:.2%} vs {t['p_indep']:.2%} if independent.",
                                         S["small"])]
        st.append(KeepTogether(block))

    st.append(PageBreak())
    # board
    st.append(Paragraph("Full Sunday board — top 30", S["h2"]))
    rows = [["#", "Player", "Pos", "Team", "Game", "Model", "Fair", "Play at", "Team xTD", "Note"]]
    for i, r in enumerate(P.sort_values("p_attd", ascending=False).head(30).itertuples(), 1):
        note = "singles only" if r.singles_only else ""
        if isinstance(r.injury_status, str):
            note = (note + " · " + r.injury_status).strip(" ·")
        elif r.singles_only:
            note = f"singles only · missed {int(r.games_missed_last4)}/4"
        rows.append([i, r.name, r.pos_group, r.team, r.matchup, f"{r.p_attd:.0%}", am(r.p_attd), r.play_at,
                     f"{r.lam_team_rush + r.lam_team_pass:.2f}", note])
    st.append(_table(rows, [w * inch for w in [0.3, 1.55, 0.4, 0.45, 0.8, 0.5, 0.55, 0.6, 0.65, 1.45]]))

    # by game
    st.append(Paragraph("By game — top 3 each side", S["h2"]))
    rows = [["Game", "Kick", "Implied pts", "Away top 3", "Home top 3"]]
    for g, q in P.groupby("game_id"):
        a, h = g.split("_")[2], g.split("_")[3]
        top = lambda t: ", ".join(f"{r.name} {r.p_attd:.0%}" for r in q[q.team == t].head(3).itertuples())  # noqa
        imp = q.groupby("team").implied_filled.first()
        rows.append([f"{a}@{h}", kick.get(g, ""), f"{imp.get(a, 0):.1f} / {imp.get(h, 0):.1f}",
                     Paragraph(top(a), S["cell"]), Paragraph(top(h), S["cell"])])
    st.append(_table(rows, [w * inch for w in [0.7, 0.5, 0.8, 2.6, 2.6]]))

    st.append(Paragraph("How to read this / caveats", S["h2"]))
    for n in notes:
        st.append(Paragraph("• " + n, S["body"]))
    doc.build(st)
