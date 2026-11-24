"""Cross-game SGP ladder PDF + flat export for the platform."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .intel import MK_LABEL, intel, load_defenders, risk_line
from .pick_slip import _kick
from .tickets import fair

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, GREEN, LINE, BAND, AMBER = (colors.HexColor(c) for c in
                                         ("#161b26", "#5b6473", "#0b6e4f", "#d5d9e0", "#f3f5f8", "#9a5b00"))


def am(p):
    a = fair(p)
    return f"+{a}" if a > 0 else str(a)


def leg_text(r):
    return f"{r['name']} ANYTIME TD" if r.market == "atd" else f"{r['name']} {int(r.k)}+ {MK_LABEL[r.market]}"


def stack_note(cs):
    return ("legs lift each other" if cs >= 0.3 else "mild help" if cs >= 0.08 else "independent legs")


def render(season, week, day, out_path, out, S, games, excluded_note=""):
    sched = pd.read_csv(ROOT / "data" / "schedules.csv").set_index("game_id")
    F = pd.read_parquet(ROOT / "outputs" / f"props_features_{season}_wk{week}.parquet")
    FA = pd.read_parquet(ROOT / "outputs" / f"projection_features_{season}_wk{week}.parquet")
    DF = load_defenders()
    ss = getSampleStyleSheet()
    T = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=21, textColor=INK, alignment=0, spaceAfter=2)
    SUB = ParagraphStyle("S", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK, spaceBefore=8, spaceAfter=4)
    B = ParagraphStyle("B", parent=ss["Normal"], fontSize=8.4, textColor=INK, leading=11, spaceAfter=2)
    RISK = ParagraphStyle("R", parent=B, textColor=AMBER)

    def tbl(rows, widths, head=INK):
        t = Table(rows, colWidths=[w * inch for w in widths], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("BACKGROUND", (0, 0), (-1, 0), head), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.3),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]), ("GRID", (0, 0), (-1, -1), 0.25, LINE),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return t

    when = pd.Timestamp(day).strftime("%A, %B %-d %Y")
    story = [Paragraph(f"Week {week} Cross-Game SGPs — {when}", T),
             Paragraph(f"Built {datetime.now():%b %-d %H:%M} UTC · every factor in FACTORS.md · floor-band bet365 legs · "
                       f"each game contributes a 2-leg stack whose legs help each other; stacks multiply across games. {excluded_note}", SUB)]
    for key, title, note in [("props", "Props ladder (no TD legs)", "Two props per game, one game added at a time."),
                             ("allpos", "All-position ladder (prop stack + anytime TD)", "Three legs per game: the prop stack plus that game's best eligible anytime TD.")]:
        rows = [["Ticket", "Games", "Hit chance", "Fair odds", "If independent", "Bet only if bet365 pays"]]
        for t in out[key]:
            rows.append([f"{t['n']}-leg", str(len(t["games"])), f"{t['p']:.1%}", am(t["p"]), f"{t['p_indep']:.1%}", f"better than {am(t['p'])}"])
        story += [Paragraph(title, H2), Paragraph(note, SUB), tbl(rows, [0.9, 0.7, 1.0, 0.9, 1.1, 2.0], GREEN)]
        if out[key]:
            big = out[key][-1]
            rows = [["#", "Leg", "Game", "Kickoff", "Model", "2026 hits"]]
            for i, r in enumerate(big["legs"].itertuples(), 1):
                g = sched.loc[r.game_id]
                hits = "" if r.market == "atd" else f"{int(r.season_hits)}/{int(r.season_n)}"
                rows.append([i, leg_text(big["legs"].iloc[i - 1]), f"{g.away_team} @ {g.home_team}", _kick(g.gametime), f"{r.p:.0%}", hits])
            story += [Paragraph(f"Legs of the {big['n']}-leg (each shorter ticket is its first games)", SUB), tbl(rows, [0.3, 2.7, 1.0, 0.9, 0.6, 0.8])]
    # stacks by game
    story.append(Paragraph("Best stack in every game", H2))
    rows = [["Game", "Kickoff", "Stack", "Joint", "Fair", "Correlation"]]
    for r in S[S["size"] == 2].sort_values("p", ascending=False).itertuples():
        g = sched.loc[r.game_id]
        rows.append([f"{g.away_team} @ {g.home_team}", _kick(g.gametime),
                     Paragraph(" + ".join(leg_text(x) for _, x in r.legs.iterrows()), B), f"{r.p:.0%}", am(r.p), stack_note(r.corr_sum)])
    story.append(tbl(rows, [0.9, 0.8, 3.3, 0.55, 0.6, 1.0]))
    # intel for ladder legs
    story.append(Paragraph("Leg intel — every factor, per pick", H2))
    seen = set()
    for key in ("props", "allpos"):
        if not out[key]:
            continue
        for _, r in out[key][-1]["legs"].iterrows():
            k = (r.player_id, r.market, r.get("k"))
            if k in seen:
                continue
            seen.add(k)
            src = FA if r.market == "atd" else F
            fr = src[(src.player_id == r.player_id) & (src.game_id == r.game_id)]
            if fr.empty:
                continue
            fr = fr.iloc[0]
            g = sched.loc[r.game_id]
            rung = None if r.market == "atd" else (f"<b>This line:</b> {int(r.k)}+ {MK_LABEL[r.market]}: cleared in "
                                                   f"{int(r.season_hits)} of {int(r.season_n)} games this season; model {r.p:.0%}.")
            head = Table([[leg_text(r), f"{g.away_team} @ {g.home_team} · {_kick(g.gametime)}", f"{r.p:.0%} · fair {am(r.p)}"]],
                         colWidths=[2.9 * inch, 2.3 * inch, 2.0 * inch])
            head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                                      ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 9.3), ("FONT", (1, 0), (-1, 0), "Helvetica", 8.3),
                                      ("ALIGN", (2, 0), (2, 0), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            bullets = intel(fr, src[src.game_id.isin(games)], DF, g, market=r.market, rung_line=rung)
            story.append(KeepTogether([head, Spacer(1, 3)] + [Paragraph("• " + b, B) for b in bullets] +
                                      [Paragraph(risk_line(fr, r.market), RISK), Spacer(1, 8)]))
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=f"Week {week} Cross-Game SGPs", author="God's Eye").build(story)


def export_json(out, S):
    def legs(L):
        return [{"id": r.player_id, "mk": r.market, "k": None if r.market == "atd" else int(r.k), "p": round(float(r.p), 4)}
                for r in L.itertuples()]
    return {"props": [{"n": t["n"], "games": t["games"], "p": round(t["p"], 5), "p_indep": round(t["p_indep"], 5), "legs": legs(t["legs"])} for t in out["props"]],
            "allpos": [{"n": t["n"], "games": t["games"], "p": round(t["p"], 5), "p_indep": round(t["p_indep"], 5), "legs": legs(t["legs"])} for t in out["allpos"]],
            "stacks": [{"game": r.game_id, "p": round(float(r.p), 4), "corr": round(float(r.corr_sum), 3), "legs": legs(r.legs)}
                       for r in S[S["size"] == 2].sort_values("p", ascending=False).itertuples()]}
