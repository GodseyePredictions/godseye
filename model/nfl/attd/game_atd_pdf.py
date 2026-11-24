"""Single-game ATD slip: ranked board, in-game doubles/trebles priced with the ATD copula, per-player intel."""
from __future__ import annotations

import json
from datetime import datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .atd_slip import CUSHION, am, joint
from .intel import intel, load_defenders, risk_line
from .pick_slip import _kick

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, RED, LINE, BAND, AMBER = (colors.HexColor(c) for c in
                                       ("#161b26", "#5b6473", "#8b1a2b", "#d5d9e0", "#f3f5f8", "#9a5b00"))


def render(season, week, game_id, out_path, subtitle=""):
    F = pd.read_parquet(ROOT / "outputs" / f"projection_features_{season}_wk{week}.parquet")
    sched = pd.read_csv(ROOT / "data" / "schedules.csv").set_index("game_id")
    sg = sched.loc[game_id]
    corr = json.loads((ROOT / "models" / "correlations.json").read_text())
    DF = load_defenders()
    G = F[F.game_id == game_id].sort_values("p_attd", ascending=False).copy()
    G = G[G.p_attd >= 0.10]
    G["single"] = G.singles_only.fillna(False).astype(bool)
    G["play_at"] = (G.p_attd - G.pos_group.map(CUSHION).fillna(0.04)).map(am)

    ss = getSampleStyleSheet()
    T = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=21, textColor=INK, alignment=0, spaceAfter=2)
    SUB = ParagraphStyle("S", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK, spaceBefore=8, spaceAfter=4)
    B = ParagraphStyle("B", parent=ss["Normal"], fontSize=8.6, textColor=INK, leading=11.4, spaceAfter=2)
    RISK = ParagraphStyle("R", parent=B, textColor=AMBER)

    def tbl(rows, widths, head=INK):
        t = Table(rows, colWidths=[w * inch for w in widths], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("BACKGROUND", (0, 0), (-1, 0), head), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
                               ("FONT", (1, 1), (1, -1), "Helvetica-Bold", 8.5),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]), ("GRID", (0, 0), (-1, -1), 0.25, LINE),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
        return t

    title = f"Week {week} ATD · {sg.away_team} @ {sg.home_team}"
    story = [Paragraph(title, T),
             Paragraph(f"{_kick(sg.gametime)} ET · bet365 anytime-TD board · built {datetime.now():%b %-d %H:%M} UTC from the ATTD "
                       f"model (data only, no media picks) · injury report + personnel overrides applied"
                       + (f" · {subtitle}" if subtitle else ""), SUB), Spacer(1, 6)]

    rows = [["#", "Player", "Pos", "Team", "TD chance", "Fair", "Play at", "Use"]]
    for i, r in enumerate(G.itertuples(), 1):
        use = "single only" if r.single else ("parlay-eligible" if r.pos_group in ("RB", "QB") else "single (WR/TE rule)")
        rows.append([i, r.name, r.pos_group, r.team, f"{r.p_attd:.0%}", am(r.p_attd), r.play_at, use])
    story += [Paragraph("Board (every player ≥10%)", H2), tbl(rows, [0.3, 1.7, 0.45, 0.55, 0.8, 0.6, 0.65, 2.2], RED),
              Paragraph("<b>Play at</b> = shortest single price worth taking (fair plus cushion: RB +3 pts, TE/QB +4, WR +6). "
                        "Questionable or returning players are singles only; WR/TE anytime TDs are singles only by standing rule.", SUB)]

    # in-game combos among parlay-eligible legs
    elig = G[~G.single & G.pos_group.isin(["RB", "QB"]) & (G.p_attd >= 0.25)]
    combos = []
    for n in (2, 3):
        for idx in combinations(range(len(elig)), n):
            legs = elig.iloc[list(idx)]
            if legs.team.nunique() < 1:
                continue
            pj = joint(legs, corr); pi = float(np.prod(legs.p_attd))
            combos.append((n, legs, pj, pi))
    combos.sort(key=lambda x: (-x[0], -x[2]))
    if combos:
        rows = [["Legs", "Players", "Hit", "Fair", "If independent", "Correlation"]]
        for n, legs, pj, pi in combos[:10]:
            rows.append([f"{n}-leg", " + ".join(legs.name), f"{pj:.1%}", am(pj), f"{pi:.1%}", f"×{pj / pi:.2f}"])
        story += [Paragraph("In-game anytime-TD combos", H2), tbl(rows, [0.6, 3.1, 0.7, 0.7, 1.0, 1.15], RED),
                  Paragraph("Same-team legs split the same touchdowns (correlation below 1); opposite-team legs ride the "
                            "shootout. Bet only when bet365 pays better than the fair price.", SUB)]
    else:
        story.append(Paragraph("No parlay-eligible pair clears 25%; play the board as singles.", SUB))

    # intel
    story += [PageBreak(), Paragraph("Player intel — every factor", H2)]
    for r in G.head(10).itertuples():
        rr = F.loc[r.Index]
        head = Table([[f"{r.name} · {r.pos_group} {r.team}", f"{r.p_attd:.0%} · fair {am(r.p_attd)} · play at {r.play_at}"]],
                     colWidths=[4.0 * inch, 3.2 * inch])
        head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                                  ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 9.3), ("FONT", (1, 0), (1, 0), "Helvetica", 8.3),
                                  ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        bullets = intel(rr, F, DF, sg, market="atd")
        story.append(KeepTogether([head, Spacer(1, 3)] + [Paragraph("• " + b, B) for b in bullets] +
                                  [Paragraph(risk_line(rr, "atd"), RISK), Spacer(1, 8)]))
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=title, author="God's Eye").build(story)
    return G, combos
