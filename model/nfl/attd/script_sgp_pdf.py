"""Script-first SGP slip PDF: per game, the read of the script, the 4/6/8/10 props ladder and the two ATD hybrids."""
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

from .crossgame_pdf import am
from .intel import intel, load_defenders, risk_line
from .pick_slip import _kick
from .script_sgp import build_script_sgps, leg_text

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, RED, LINE, BAND, AMBER = (colors.HexColor(c) for c in
                                       ("#161b26", "#5b6473", "#8b1a2b", "#d5d9e0", "#f3f5f8", "#9a5b00"))


def render(season, week, games, out_path, title):
    sched = pd.read_csv(ROOT / "data" / "schedules.csv").set_index("game_id")
    L = pd.read_csv(ROOT / "outputs" / f"prop_ladders_{season}_wk{week}.csv")
    A = pd.read_csv(ROOT / "outputs" / f"atd_{season}_wk{week}.csv")
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text())
    F = pd.read_parquet(ROOT / "outputs" / f"props_features_{season}_wk{week}.parquet")
    DF = load_defenders()
    from .early import backup_qb_teams
    _bq = backup_qb_teams(season, week)

    ss = getSampleStyleSheet()
    T = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=21, textColor=INK, alignment=0, spaceAfter=2)
    SUB = ParagraphStyle("S", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK, spaceBefore=8, spaceAfter=4)
    H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, textColor=RED, spaceBefore=6, spaceAfter=2)
    B = ParagraphStyle("B", parent=ss["Normal"], fontSize=8.5, textColor=INK, leading=11.2, spaceAfter=2)
    RISK = ParagraphStyle("R", parent=B, textColor=AMBER)

    def ticket(head_txt, legs, p):
        rows = [[head_txt, "", f"{p:.1%} · fair {am(p)}"]]
        for i, r in enumerate(legs.itertuples(), 1):
            why = " · ".join(r.fit_why[:2]) if isinstance(r.fit_why, (list, tuple)) else ""
            rows.append([Paragraph(f"<b>{i}. {leg_text(r)}</b>" + (f"<br/><font color='#5b6473' size='7.5'>{why}</font>" if why else ""), B),
                         f"{r.pos_group} {r.team}" + (f" · {int(r.season_hits)}/{int(r.season_n)}" if pd.notna(r.season_n) else ""),
                         f"{r.p:.0%}"])
        t = Table(rows, colWidths=[3.9 * inch, 1.9 * inch, 1.4 * inch])
        t.setStyle(TableStyle([("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (-1, 0), RED), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5), ("FONT", (1, 1), (-1, -1), "Helvetica", 8.3),
                               ("ALIGN", (2, 0), (2, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("BOX", (0, 0), (-1, -1), 0.8, RED), ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return t

    story = [Paragraph(title, T),
             Paragraph(f"Built {datetime.now():%b %-d %H:%M} UTC · the game script is read first (spread, total, pass/run behaviour "
                       f"when leading or trailing, red-zone trend, pace, weather, run-lane and secondary edges); legs are then chosen "
                       f"for what that script favours, not one per position. Longer tickets extend shorter ones. Props tickets carry "
                       f"no TD legs; the two hybrids add the anytime-TD legs. Bet only if bet365 pays better than the fair price.", SUB)]

    built = []
    for g in sorted(games, key=lambda x: sched.loc[x, "gametime"]):
        try:
            o = build_script_sgps(L, A, F, g, corr, hold_pass=tuple(_bq))
        except Exception as e:  # noqa: BLE001
            print("  [script pdf]", g, e); continue
        if not o["ladder"]:
            continue
        built.append((g, o))

    # overview
    rows = [["Game", "Kick", "4-leg", "6-leg", "8-leg", "10-leg", "1 ATD+4", "2 ATD+4"]]
    for g, o in built:
        sg = sched.loc[g]
        lad = {t["n"]: t["p"] for t in o["ladder"]}
        rows.append([f"{sg.away_team} @ {sg.home_team}", _kick(sg.gametime)] +
                    [f"{lad[n]:.1%}" if n in lad else "—" for n in (4, 6, 8, 10)] +
                    [f"{o[k]['p']:.1%}" if o[k] else "—" for k in ("hybrid1", "hybrid2")])
    t = Table(rows, colWidths=[w * inch for w in (1.3, 0.8, 0.8, 0.8, 0.8, 0.8, 0.95, 0.95)], repeatRows=1)
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("BACKGROUND", (0, 0), (-1, 0), INK), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.3),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]), ("GRID", (0, 0), (-1, -1), 0.25, LINE),
                           ("ALIGN", (2, 0), (-1, -1), "RIGHT")]))
    story += [Paragraph("Hit probability by game and ticket", H2), t]

    # per game
    for g, o in built:
        sg = sched.loc[g]
        story += [PageBreak(), Paragraph(f"{sg.away_team} @ {sg.home_team} · {_kick(sg.gametime)}", H2),
                  Paragraph("Game script", H3)] + [Paragraph("• " + n, B) for n in o["profile"]["notes"]]
        for tk in o["ladder"]:
            story += [Spacer(1, 6), ticket(f"{tk['n']}-LEG SCRIPT SGP (props)", tk["legs"], tk["p"])]
        for k, ttl in (("hybrid1", "HYBRID · 1 ANYTIME TD + 4 PROPS"), ("hybrid2", "HYBRID · 2 ANYTIME TDS + 4 PROPS")):
            if o[k]:
                story += [Spacer(1, 6), ticket(ttl, o[k]["legs"], o[k]["p"])]

    # leg intel
    story += [PageBreak(), Paragraph("Leg intel — every factor, per pick", H2)]
    seen = set()
    for g, o in built:
        sg = sched.loc[g]
        legs = pd.concat([o["ladder"][-1]["legs"]] + [o[k]["legs"] for k in ("hybrid1", "hybrid2") if o[k]])
        for r in legs.itertuples():
            key = (r.player_id, r.market, r.k)
            if key in seen:
                continue
            seen.add(key)
            fr = F[(F.player_id == r.player_id) & (F.game_id == g)]
            if fr.empty:
                continue
            fr = fr.iloc[0]
            rung = (f"<b>This line:</b> {leg_text(r)}: model {r.p:.0%} (fair {am(r.p)})" +
                    (f"; cleared in {int(r.season_hits)} of {int(r.season_n)} games this season." if pd.notna(r.season_n) else ".") +
                    (" <b>Script fit:</b> " + "; ".join(r.fit_why) if isinstance(r.fit_why, (list, tuple)) and r.fit_why else ""))
            head = Table([[leg_text(r), f"{sg.away_team} @ {sg.home_team} · {_kick(sg.gametime)}", f"{r.p:.0%} · fair {am(r.p)}"]],
                         colWidths=[2.9 * inch, 2.3 * inch, 2.0 * inch])
            head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                                      ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 9.3), ("FONT", (1, 0), (-1, 0), "Helvetica", 8.3),
                                      ("ALIGN", (2, 0), (2, 0), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            mk = "atd" if r.market == "atd" else r.market
            bullets = intel(fr, F[F.game_id.isin(games)], DF, sg, market=mk, rung_line=rung)
            story.append(KeepTogether([head, Spacer(1, 3)] + [Paragraph("• " + b, B) for b in bullets] +
                                      [Paragraph(risk_line(fr, mk), RISK), Spacer(1, 8)]))
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=title, author="God's Eye").build(story)
    return built
