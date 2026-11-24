"""One-stop SGP slip PDF: per-game algorithm SGPs + cross-game ladders + play notes + leg intel."""
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

from .crossgame import build_ladders
from .crossgame_pdf import am, leg_text
from .intel import MK_LABEL, intel, load_defenders, risk_line
from .pick_slip import _kick
from .tickets import algo_sgp

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, GREEN, LINE, BAND, AMBER = (colors.HexColor(c) for c in
                                         ("#161b26", "#5b6473", "#0b6e4f", "#d5d9e0", "#f3f5f8", "#9a5b00"))


def render(season, week, day, games, out_path, title, notes, excluded_note=""):
    sched = pd.read_csv(ROOT / "data" / "schedules.csv").set_index("game_id")
    L = pd.read_csv(ROOT / "outputs" / f"prop_ladders_{season}_wk{week}.csv")
    L = L[L.game_id.isin(games)]
    A = pd.read_csv(ROOT / "outputs" / f"atd_{season}_wk{week}.csv")
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
    F = pd.read_parquet(ROOT / "outputs" / f"props_features_{season}_wk{week}.parquet")
    DF = load_defenders()
    out, S = build_ladders(season, week, games, A)

    ss = getSampleStyleSheet()
    T = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=21, textColor=INK, alignment=0, spaceAfter=2)
    SUB = ParagraphStyle("S", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK, spaceBefore=8, spaceAfter=4)
    B = ParagraphStyle("B", parent=ss["Normal"], fontSize=8.5, textColor=INK, leading=11.2, spaceAfter=2)
    RISK = ParagraphStyle("R", parent=B, textColor=AMBER)

    def tbl(rows, widths, head=INK):
        t = Table(rows, colWidths=[w * inch for w in widths], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("BACKGROUND", (0, 0), (-1, 0), head), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.3),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]), ("GRID", (0, 0), (-1, -1), 0.25, LINE),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return t

    story = [Paragraph(title, T),
             Paragraph(f"Built {datetime.now():%b %-d %H:%M} UTC · every factor in FACTORS.md · floor-band bet365 milestone legs "
                       f"(70–88%) · [x/y] = games this season clearing that exact line · bet a ticket only if bet365 pays better "
                       f"than the fair price. {excluded_note}", SUB)]

    # per-game SGPs
    sgps = []
    for g in sorted(games, key=lambda x: sched.loc[x, "gametime"]):
        C, alts, pj, pi = algo_sgp(L, g, corr)
        if not C.empty:
            sgps.append((g, C, alts, pj, pi))
    sgps.sort(key=lambda x: -x[3])
    rows = [["Game", "Kick", "Legs (slot: leg [season])", "Hit", "Fair"]]
    for g, C, alts, pj, pi in sgps:
        sg = sched.loc[g]
        legs_txt = "<br/>".join(f"<b>{r.slot}:</b> {leg_text(C.iloc[i])} [{int(r.season_hits)}/{int(r.season_n)}] {r.p:.0%}"
                                for i, r in enumerate(C.itertuples()))
        rows.append([f"{sg.away_team} @ {sg.home_team}", _kick(sg.gametime), Paragraph(legs_txt, B), f"{pj:.1%}", am(pj)])
    story += [Paragraph("Algorithm SGP per game (best leg per slot, ranked)", H2),
              tbl(rows, [0.85, 0.75, 4.3, 0.6, 0.6], GREEN),
              Paragraph("Slots: QB pass yards or passing TDs · RB rush yards · WR, TE and RB receiving (receptions or yards). "
                        "A slot with nothing in band is filled by the next-best leg (marked 'fill'). Questionable and returning "
                        "players are excluded. No TD legs.", SUB)]

    # cross-game ladders
    for key, ttl, note in [("props", "Cross-game props ladder (no TD legs)", "Two props per game, one game added at a time."),
                           ("allpos", "Cross-game all-position ladder (stack + anytime TD)", "Three legs per game: the prop stack plus the game's best eligible anytime TD.")]:
        if not out[key]:
            continue
        rows = [["Ticket", "Hit", "Fair", "Legs"]]
        for t in out[key]:
            rows.append([f"{t['n']}-leg", f"{t['p']:.1%}", am(t["p"]),
                         Paragraph(" · ".join(leg_text(t["legs"].iloc[i]) for i in range(len(t["legs"]))), B)])
        story += [Paragraph(ttl, H2), Paragraph(note, SUB), tbl(rows, [0.7, 0.6, 0.65, 5.15], GREEN)]

    story += [Paragraph("How to play it", H2)] + [Paragraph("• " + n, B) for n in notes]

    # bet slips per game SGP
    story += [PageBreak(), Paragraph("Bet slips", H2)]
    for g, C, alts, pj, pi in sgps:
        sg = sched.loc[g]
        rows = [[f"{sg.away_team} @ {sg.home_team} · {_kick(sg.gametime)} · {len(C)}-LEG SGP", "", f"{pj:.1%} · fair {am(pj)}"]]
        for i, r in enumerate(C.itertuples(), 1):
            rows.append([f"{i}. {leg_text(C.iloc[i - 1])}", f"{r.slot} · {r.pos_group} {r.team}", f"{r.p:.0%}"])
        t = Table(rows, colWidths=[3.3 * inch, 2.4 * inch, 1.5 * inch])
        t.setStyle(TableStyle([("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (-1, 0), GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
                               ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 8.5), ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                               ("BOX", (0, 0), (-1, -1), 0.8, GREEN), ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        alt_txt = "; ".join(f"{slot}: " + " / ".join(f"{a['name']} {int(a['k'])}+ {MK_LABEL[a['market']]} ({a['p']:.0%})" for a in al)
                            for slot, al in alts.items() if al)
        story.append(KeepTogether([t, Spacer(1, 2), Paragraph(("Alternatives — " + alt_txt) if alt_txt else "", SUB), Spacer(1, 8)]))

    # leg intel
    story += [PageBreak(), Paragraph("Leg intel — every factor, per pick", H2)]
    seen = set()
    for g, C, alts, pj, pi in sgps:
        sg = sched.loc[g]
        for i, r in enumerate(C.itertuples()):
            k = (r.player_id, r.market, r.k)
            if k in seen:
                continue
            seen.add(k)
            fr = F[(F.player_id == r.player_id) & (F.game_id == g)]
            if fr.empty:
                continue
            fr = fr.iloc[0]
            rung = (f"<b>This line:</b> {int(r.k)}+ {MK_LABEL[r.market]}: cleared in {int(r.season_hits)} of "
                    f"{int(r.season_n)} games this season; model {r.p:.0%} (fair {am(r.p)}).")
            head = Table([[leg_text(C.iloc[i]), f"{sg.away_team} @ {sg.home_team} · {_kick(sg.gametime)}", f"{r.p:.0%} · fair {am(r.p)}"]],
                         colWidths=[2.9 * inch, 2.3 * inch, 2.0 * inch])
            head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                                      ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 9.3), ("FONT", (1, 0), (-1, 0), "Helvetica", 8.3),
                                      ("ALIGN", (2, 0), (2, 0), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            bullets = intel(fr, F[F.game_id.isin(games)], DF, sg, market=r.market, rung_line=rung)
            story.append(KeepTogether([head, Spacer(1, 3)] + [Paragraph("• " + b, B) for b in bullets] +
                                      [Paragraph(risk_line(fr, r.market), RISK), Spacer(1, 8)]))
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=title, author="God's Eye").build(story)
    return sgps, out
