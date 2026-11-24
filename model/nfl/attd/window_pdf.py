"""PDFs for a kick-off window pack: window-only ATD tickets (4/6/8/10) and the master props slips."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .atd_slip import CUSHION, am
from .intel import intel, load_defenders, risk_line
from .script_sgp import leg_text

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, RED, LINE, BAND, AMBER = (colors.HexColor(c) for c in
                                       ("#161b26", "#5b6473", "#8b1a2b", "#d5d9e0", "#f3f5f8", "#9a5b00"))
ss = getSampleStyleSheet()
T = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, textColor=INK, alignment=0, spaceAfter=2)
SUB = ParagraphStyle("S", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK, spaceBefore=8, spaceAfter=4)
B = ParagraphStyle("B", parent=ss["Normal"], fontSize=8.6, textColor=INK, leading=11.4, spaceAfter=2)
RISK = ParagraphStyle("R", parent=B, textColor=AMBER)
HD = ParagraphStyle("HD", parent=B, fontName="Helvetica-Bold", textColor=colors.white)


def _tbl(rows, widths, head=RED, span=None):
    rows = [[Paragraph(str(c), HD) for c in rows[0]]] + [[Paragraph(str(c), B) if not hasattr(c, "wrap") else c for c in r] for r in rows[1:]]
    t = Table(rows, colWidths=[w * inch for w in widths], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), head), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BAND]),
          ("GRID", (0, 0), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    t.setStyle(TableStyle(st))
    return t


def _gl(g):
    a = g.split("_")
    return f"{a[2]} @ {a[3]}"


def render_atd(season, week, W, out_path, label, kick_et, note=""):
    F = pd.read_parquet(ROOT / "outputs" / f"projection_features_{season}_wk{week}.parquet")
    sched = pd.read_csv(ROOT / "data" / "schedules.csv").set_index("game_id")
    DF = load_defenders()
    story = [Paragraph(f"God's Eye · Week {week} · {label} ATDs", T),
             Paragraph(f"{len(W['games'])} games kicking at {kick_et}: {' · '.join(_gl(g) for g in W['games'])}. Built {datetime.now():%b %-d %H:%M} UTC "
                       f"from the ATTD model (data only, no media picks); official report, ESPN sweep and personnel overrides applied."
                       + (f" {note}" if note else ""), SUB), Spacer(1, 6)]
    for t in W["atd"]:
        rows = [[f"{t['n']}-LEG ATD", "Pos · Team", "Game", "TD chance", "Play at"]]
        for i, r in enumerate(t["legs"].itertuples(), 1):
            rows.append([f"<b>{i}. {r.name}</b>", f"{r.pos_group} {r.team}", _gl(r.game_id), f"{r.p_attd:.0%}",
                         am(r.p_attd - CUSHION.get(r.pos_group, 0.04))])
        rows.append([f"<b>Ticket: {t['p']:.1%} · fair {am(t['p'])}</b>", "", "", f"indep. {t['p_indep']:.1%}", f"×{t['p'] / t['p_indep']:.2f}"])
        blk = [_tbl(rows, [2.6, 1.0, 1.3, 1.2, 1.1])]
        if t.get("exceptions"):
            blk.append(Paragraph(f"Rule exception: {', '.join(t['exceptions'])} (normally singles: returning or inheriting the job). Used only because "
                                 f"the clean pool ran out at {t['n'] - len(t['exceptions'])} legs.", RISK))
        story += [KeepTogether(blk + [Spacer(1, 7)])]
    story.append(Paragraph("One player per team (teammates split touchdowns). Each ticket extends the one before it. Bet a ticket only if bet365 pays "
                           "better than its fair price. Opposite-team legs in the same game are priced with the measured shootout correlation.", SUB))
    if W["held"]:
        story += [Paragraph("Held off the parlays (singles only)", H2)] + [Paragraph(f"• <b>{n}</b> ({tm}): {why}", B) for n, tm, why in W["held"]]
    if len(W.get("wrte", [])):
        rows = [["Player", "Game", "TD chance", "Fair", "Play at", "RZ tgt share", "EZ tgt share", "xTD / TD per game", "Season"]]
        for r in W["wrte"].head(16).itertuples():
            rows.append([f"<b>{r.name}</b> {r.pos_group} {r.team}", _gl(r.game_id), f"{r.p_attd:.0%}", am(r.p_attd),
                         f"<b>{am(r.p_attd - CUSHION.get(r.pos_group, 0.06))}</b>", f"{r.sh_tgt_rz_e3:.0%}", f"{r.sh_ez_tgt_e3:.0%}",
                         f"{r.xtd_e3:.2f} / {r.td_e3:.2f}", f"{int(r.season_tds or 0)} TD in {int(r.season_games or 0)}"])
        story += [PageBreak(), Paragraph(f"{label} receivers and tight ends: singles", H2),
                  Paragraph("Clean pass-catchers at 25% or better: not on the injury report, not returning, not on a replacement-quarterback "
                            "offence. Take one only at the play-at price or longer (fair plus a cushion: WR +6 points, TE +4).", SUB), Spacer(1, 4),
                  _tbl(rows, [1.75, 0.85, 0.6, 0.55, 0.6, 0.65, 0.65, 0.9, 0.75])]
    if W.get("atd_mixed"):
        story += [Paragraph(f"{label} mixed ATD tickets: backs and pass-catchers", H2),
                  Paragraph("Outside the standing rule. Receiver and tight end anytime TDs are singles because they went 1 of 8 on tickets in the "
                            "ledger and ran about 7 points hot. These cap running backs at half the legs, one player per team.", RISK)]
        for t in W["atd_mixed"]:
            story.append(Paragraph(f"<b>{t['n']}-leg mixed · {t['p']:.2%} · fair {am(t['p'])}:</b> "
                                   + " · ".join(f"{r.name} ({r.pos_group} {r.team}, {r.p_attd:.0%})" for r in t["legs"].itertuples()), B))
    bd = W["board"]
    rows = [["#", "Player", "Pos", "Team", "Game", "TD chance", "Fair", "Play at", "Use"]]
    tick = set(W["atd"][-1]["legs"].player_id) if W["atd"] else set()
    heldn = {h[0] for h in W["held"]}
    for i, r in enumerate(bd[bd.p_attd >= 0.18].itertuples(), 1):
        use = "ticket leg" if r.player_id in tick else "single (held)" if r.name in heldn else \
            "single (flagged)" if bool(r.singles_only) else "single (WR/TE rule)" if r.pos_group in ("WR", "TE") else "eligible"
        rows.append([i, f"<b>{r.name}</b>", r.pos_group, r.team, _gl(r.game_id), f"{r.p_attd:.0%}", am(r.p_attd),
                     am(r.p_attd - CUSHION.get(r.pos_group, 0.04)), use])
    story += [PageBreak(), Paragraph(f"{label} board (every player at 18% or better)", H2),
              _tbl(rows, [0.3, 1.75, 0.4, 0.5, 0.95, 0.75, 0.6, 0.65, 1.3])]
    story += [PageBreak(), Paragraph("Ticket-leg intel: every factor", H2)]
    if W["atd"]:
        for r in W["atd"][-1]["legs"].itertuples():
            rr = F[(F.player_id == r.player_id) & (F.game_id == r.game_id)].iloc[0]
            blk = [Paragraph(f"<b>{r.name} · {r.pos_group} {r.team} · {_gl(r.game_id)} · {r.p_attd:.0%} · fair {am(r.p_attd)}</b>", B)]
            blk += [Paragraph(x, B) for x in intel(rr, F, DF, sched.loc[r.game_id], market="atd")]
            blk += [Paragraph(risk_line(rr, "atd"), RISK), Spacer(1, 6)]
            story.append(KeepTogether(blk[:3])); story += blk[3:]
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=f"{label} ATDs").build(story)


def render_master(season, week, W, out_path, label, kick_et):
    story = [Paragraph(f"God's Eye · Week {week} · Master Slip · {label} Football Player Props", T),
             Paragraph(f"Every {label} game's top props on one slip ({kick_et} kickoffs). Built {datetime.now():%b %-d %H:%M} UTC. Each game is read "
                       f"on its own script first; legs are that game's best props in order, so the 6 extends the 4 and the 8 extends the 6. "
                       f"No TD legs. Each game block is its own same-game parlay; games are independent of each other.", SUB), Spacer(1, 6)]
    rows = [["Master slip", "Legs", "All games together", "Fair", "Game tickets expected", "Half or more cash"]]
    for m in W["master"]:
        k = len(m["games"]); half = -(-k // 2)
        rows.append([f"<b>Top {m['n']} per game</b>", m["legs_total"], f"{m['p_all']:.2%}", am(m["p_all"]),
                     f"{m['exp_cash']:.1f} of {k}", f"{m['p_at_least'][half]:.0%} ({half}+)"])
    story += [_tbl(rows, [1.6, 0.6, 1.5, 0.9, 1.5, 1.2]),
              Paragraph("The all-games price is the product of the game tickets. It is a long shot by construction: the straight play is each game's "
                        "ticket on its own, and the master is the sweep on top.", SUB)]
    for m in W["master"]:
        story += [PageBreak(), Paragraph(f"Master slip: top {m['n']} props per game · {m['legs_total']} legs · {m['p_all']:.2%} · fair {am(m['p_all'])}", H2)]
        if m.get("missing"):
            story.append(Paragraph(f"No {m['n']}-leg for {', '.join(_gl(g) for g in m['missing'])}: too few legs clear the rules there "
                                   f"(replacement quarterback), so that game sits out this slip.", RISK))
        for r in m["games"]:
            rows = [[f"{_gl(r['game'])} · {r['p']:.1%} · fair {am(r['p'])}", "Pos · Team", "Season", "Model"]]
            for i, x in enumerate(r["legs"].itertuples(), 1):
                why = " · ".join(x.fit_why[:2]) if isinstance(x.fit_why, (list, tuple)) else ""
                rows.append([f"<b>{i}. {leg_text(x)}</b>" + (f"<br/><font color='#5b6473' size='7.3'>{why}</font>" if why else ""),
                             f"{x.pos_group} {x.team}", f"{int(x.season_hits)}/{int(x.season_n)}" if pd.notna(x.season_n) else "", f"{x.p:.0%}"])
            story.append(KeepTogether([_tbl(rows, [4.1, 1.1, 0.9, 1.1]), Spacer(1, 6)]))
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=f"Master Slip {label}").build(story)


def render_full(season, week, W, out_path, label, kick_et, status=""):
    """One document for the whole window: cover + summary, ATDs, per-game script picks with intel, master slips."""
    import tempfile
    from pypdf import PdfReader, PdfWriter
    from .script_sgp_pdf import render as render_games
    tmp = Path(tempfile.mkdtemp())
    story = [Spacer(1, 40), Paragraph(f"God's Eye Predictions", T),
             Paragraph(f"Week {week} · {label} Morning Slips", ParagraphStyle("T2", parent=T, fontSize=26, textColor=RED, leading=30)),
             Paragraph(f"{len(W['games'])} games kicking at {kick_et} · built {datetime.now():%a %b %-d %H:%M} UTC · model only, no media picks"
                       + (f" · {status}" if status else ""), SUB), Spacer(1, 14),
             Paragraph("What is inside", H2)]
    for i, x in enumerate([f"{label} ATDs: 4 / 6 / 8 / 10-leg running-back and quarterback tickets, receivers and tight ends as singles, mixed tickets, full board, ticket-leg intel",
                           f"{label} Algo Picks per game: each game's script read, 4 / 6 / 8 / 10-leg props tickets, anytime-TD hybrids, intel for every leg",
                           f"Master Slip · {label} Football Player Props: every game's top 4, top 6 and top 8 on one slip"], 1):
        story.append(Paragraph(f"{i}. {x}", B))
    story += [Paragraph("ATD tickets at a glance", H2)]
    rows = [["Ticket", "Legs", "Hit", "Fair"]]
    for t in W["atd"]:
        rows.append([f"<b>{t['n']}-leg ATD</b>", " · ".join(t["legs"].name), f"{t['p']:.2%}", am(t["p"])])
    for t in W.get("atd_mixed", []):
        rows.append([f"{t['n']}-leg mixed", " · ".join(t["legs"].name), f"{t['p']:.2%}", am(t["p"])])
    story.append(_tbl(rows, [1.1, 4.6, 0.7, 0.9]))
    story += [Paragraph("Game tickets at a glance", H2)]
    sizes = [4, 6, 8]
    rows = [["Game"] + [f"{n}-leg" for n in sizes] + ["Top four legs"]]
    for o in W["per_game"]:
        lad = {x["n"]: x for x in o["ladder"]}
        rows.append([f"<b>{_gl(o['game'])}</b>"] + [f"{lad[n]['p']:.1%} · {am(lad[n]['p'])}" if n in lad else "none" for n in sizes]
                    + [" · ".join(leg_text(r) for r in lad[4]["legs"].itertuples()) if 4 in lad else ""])
    story.append(_tbl(rows, [0.95, 0.95, 0.95, 0.95, 3.5]))
    story += [Paragraph("Master slips at a glance", H2)]
    rows = [["Master slip", "Legs", "All games together", "Fair", "Game tickets expected"]]
    for m in W["master"]:
        rows.append([f"<b>Top {m['n']} per game</b>", m["legs_total"], f"{m['p_all']:.2%}", am(m["p_all"]), f"{m['exp_cash']:.1f} of {len(m['games'])}"])
    story.append(_tbl(rows, [1.8, 0.8, 1.7, 1.2, 1.8]))
    if W["backup_qb"] or W["held"]:
        story += [Paragraph("Flags on this window", H2)]
        gs = {t for g in W["games"] for t in g.split("_")[2:]}
        for t, why in W["backup_qb"].items():
            if t in gs:
                story.append(Paragraph(f"• <b>{t}</b>: replacement quarterback ({why}). Off ATD parlays; passing and receiving legs off the game tickets.", B))
        for n, tm, why in W["held"]:
            if "backup-QB" not in why:
                story.append(Paragraph(f"• <b>{n}</b> ({tm}): {why}. Single only.", B))
    story.append(Paragraph("Bet a ticket only when bet365 pays better than its fair price. Probabilities are the model's; long tickets are long shots "
                           "and priced that way.", SUB))
    SimpleDocTemplate(str(tmp / "0.pdf"), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch).build(story)
    render_atd(season, week, W, tmp / "1.pdf", label, kick_et)
    render_games(season, week, W["games"], str(tmp / "2.pdf"), f"God's Eye · Week {week} · {label} Algo Picks per game")
    render_master(season, week, W, tmp / "3.pdf", label, kick_et)
    w = PdfWriter()
    for i in range(4):
        for pg in PdfReader(str(tmp / f"{i}.pdf")).pages:
            w.add_page(pg)
    w.add_metadata({"/Title": f"God's Eye Week {week} {label} Morning Slips"})
    with open(out_path, "wb") as f:
        w.write(f)
    return len(w.pages)


def render_core(season, week, W, out_path, label, status=""):
    """Short slip sheet: window ATDs, master slips (4/6/8 per game), and per-game 8-leg hybrids (1 ATD + 7, 2 ATDs + 6)."""
    story = [Paragraph(f"God's Eye · Week {week} · {label} Slips", T),
             Paragraph(f"{len(W['games'])} games: {' · '.join(_gl(g) for g in W['games'])}. Built {datetime.now():%a %b %-d %H:%M} UTC · model only"
                       + (f" · {status}" if status else "") + ". Bet a ticket only if bet365 pays better than its fair price.", SUB), Spacer(1, 6),
             Paragraph(f"1. {label} ATDs", H2)]
    for t in W["atd"]:
        rows = [[f"{t['n']}-LEG ATD · {t['p']:.2%} · fair {am(t['p'])}", "Pos · Team", "Game", "TD chance"]]
        for i, r in enumerate(t["legs"].itertuples(), 1):
            rows.append([f"<b>{i}. {r.name}</b>", f"{r.pos_group} {r.team}", _gl(r.game_id), f"{r.p_attd:.0%}"])
        blk = [_tbl(rows, [3.4, 1.2, 1.4, 1.2])]
        if t.get("exceptions"):
            blk.append(Paragraph(f"Rule exception: {', '.join(t['exceptions'])} (normally singles: returning or inheriting the job).", RISK))
        story.append(KeepTogether(blk + [Spacer(1, 6)]))
    if len(W.get("wrte", [])):
        rows = [["Receiver / tight end singles", "Game", "TD chance", "Fair", "Play at"]]
        for r in W["wrte"].head(10).itertuples():
            rows.append([f"<b>{r.name}</b> {r.pos_group} {r.team}", _gl(r.game_id), f"{r.p_attd:.0%}", am(r.p_attd),
                         f"<b>{am(r.p_attd - CUSHION.get(r.pos_group, 0.06))}</b>"])
        story.append(KeepTogether([_tbl(rows, [3.0, 1.2, 1.0, 1.0, 1.0]),
                                   Paragraph("Pass-catchers are singles by standing rule. Take one only at the play-at price or longer.", SUB)]))
    story += [PageBreak(), Paragraph(f"2. {label} Master Slip · Football Player Props", H2)]
    rows = [["Master slip", "Legs", "All games together", "Fair", "Game tickets expected"]]
    for m in W["master"]:
        rows.append([f"<b>{m['n']} legs per game</b>", m["legs_total"], f"{m['p_all']:.2%}", am(m["p_all"]), f"{m['exp_cash']:.1f} of {len(m['games'])}"])
    story += [_tbl(rows, [1.8, 0.8, 1.7, 1.2, 1.8]), Spacer(1, 6)]
    for m in W["master"]:
        story.append(Paragraph(f"<b>Master {m['n']}-leg per game · {m['legs_total']} legs · {m['p_all']:.2%} · fair {am(m['p_all'])}</b>", B))
        if m.get("missing"):
            story.append(Paragraph(f"No {m['n']}-leg for {', '.join(_gl(g) for g in m['missing'])} (replacement quarterback thins the pool).", RISK))
        rows = [["Game", "Hit · fair", "Legs"]]
        for r in m["games"]:
            rows.append([f"<b>{_gl(r['game'])}</b>", f"{r['p']:.1%} · {am(r['p'])}",
                         "<br/>".join(f"{i}. {leg_text(x)} ({x.p:.0%})" for i, x in enumerate(r["legs"].itertuples(), 1))])
        story += [_tbl(rows, [1.0, 1.1, 5.1]), Spacer(1, 8)]
    story += [PageBreak(), Paragraph(f"3. {label} SGPs per game · 8 legs with anytime TDs", H2),
              Paragraph("Slip A is 1 anytime TD + 7 props. Slip B is 2 anytime TDs + 6 props. Eight legs in total each, priced with same-game correlation.", SUB)]
    for o in W["per_game"]:
        blk = [Paragraph(f"<b>{_gl(o['game'])}</b>", H2)]
        for key, nm in (("hybrid8_1", "Slip A"), ("hybrid8_2", "Slip B")):
            h = o.get(key)
            if not h:
                blk.append(Paragraph(f"{nm}: no eligible anytime-TD leg in this game.", RISK)); continue
            na = int((h["legs"].market == "atd").sum()); n = len(h["legs"])
            rows = [[f"{nm} · {na} ATD + {n - na} props · {h['p']:.1%} · fair {am(h['p'])}", "Pos · Team", "Model"]]
            for i, x in enumerate(h["legs"].itertuples(), 1):
                rows.append([f"<b>{i}. {leg_text(x)}</b>", f"{x.pos_group} {x.team}", f"{x.p:.0%}"])
            blk.append(_tbl(rows, [4.6, 1.4, 1.2]))
            if n < 8:
                blk.append(Paragraph(f"Only {n} legs clear the rules in this game (replacement quarterback thins the pool).", RISK))
            blk.append(Spacer(1, 5))
        story.append(KeepTogether(blk))
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=f"{label} Slips").build(story)


def render_game_hybrids(season, week, game_id, out_path, title, status=""):
    """One game: 6-leg and 8-leg same-game slips that include anytime TDs (1 ATD and 2 ATD versions), board, intel."""
    import json
    from .early import backup_qb_teams
    from .script_sgp import build_script_sgps
    O = ROOT / "outputs"
    F = pd.read_parquet(O / f"projection_features_{season}_wk{week}.parquet"); L = pd.read_csv(O / f"prop_ladders_{season}_wk{week}.csv")
    A = pd.read_csv(O / f"atd_{season}_wk{week}.csv"); PF = pd.read_parquet(O / f"props_features_{season}_wk{week}.parquet")
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text()); bq = backup_qb_teams(season, week)
    sched = pd.read_csv(ROOT / "data" / "schedules.csv").set_index("game_id"); DF = load_defenders()
    o = build_script_sgps(L, A[~A.singles_only.fillna(False).astype(bool)], PF, game_id, corr, hold_pass=tuple(bq))
    story = [Paragraph(title, T),
             Paragraph(f"Built {datetime.now():%a %b %-d %H:%M} UTC · model only, no media picks" + (f" · {status}" if status else "")
                       + ". Bet a slip only if bet365 pays better than its fair price.", SUB), Spacer(1, 6), Paragraph("Game script", H2)]
    story += [Paragraph(f"• {n}", B) for n in o["profile"]["notes"]]
    seen = {}
    for key, nm in (("hybrid6_1", "6-leg · 1 anytime TD + 5 props"), ("hybrid6_2", "6-leg · 2 anytime TDs + 4 props"),
                    ("hybrid8_1", "8-leg · 1 anytime TD + 7 props"), ("hybrid8_2", "8-leg · 2 anytime TDs + 6 props")):
        h = o.get(key)
        if not h:
            continue
        rows = [[f"{nm} · {h['p']:.1%} · fair {am(h['p'])}", "Pos · Team", "Season", "Model"]]
        for i, x in enumerate(h["legs"].itertuples(), 1):
            why = " · ".join(x.fit_why[:2]) if isinstance(x.fit_why, (list, tuple)) else ""
            rows.append([f"<b>{i}. {leg_text(x)}</b>" + (f"<br/><font color='#5b6473' size='7.3'>{why}</font>" if why else ""),
                         f"{x.pos_group} {x.team}", f"{int(x.season_hits)}/{int(x.season_n)}" if pd.notna(x.season_n) else "", f"{x.p:.0%}"])
            seen[(x.player_id, x.market, x.k if pd.notna(x.k) else None)] = x
        story.append(KeepTogether([Spacer(1, 6), _tbl(rows, [4.1, 1.1, 0.9, 1.1])]))
    G = F[(F.game_id == game_id) & (F.p_attd >= 0.10)].sort_values("p_attd", ascending=False)
    rows = [["Anytime-TD board", "Pos · Team", "TD chance", "Fair", "Play at", "Note"]]
    for r in G.itertuples():
        note = "backup-QB haircut applied" if getattr(r, "backup_qb_team", False) and r.pos_group != "QB" else ""
        if bool(r.singles_only): note = (note + "; " if note else "") + "single only"
        rows.append([f"<b>{r.name}</b>", f"{r.pos_group} {r.team}", f"{r.p_attd:.0%}", am(r.p_attd), am(r.p_attd - CUSHION.get(r.pos_group, 0.04)), note])
    story += [PageBreak(), Paragraph("Board", H2), _tbl(rows, [2.0, 1.0, 0.8, 0.7, 0.7, 2.0]), Paragraph("Leg intel: every factor", H2)]
    for (pid, mk, k), x in seen.items():
        src = F if mk == "atd" else PF
        fr = src[(src.player_id == pid) & (src.game_id == game_id)]
        if fr.empty:
            continue
        rung = None if mk == "atd" else f"<b>This line:</b> cleared in {int(x.season_hits)} of {int(x.season_n)} games this season; model {x.p:.0%}."
        blk = [Paragraph(f"<b>{leg_text(x)} · {x.p:.0%} · fair {am(x.p)}</b>", B)]
        blk += [Paragraph(z, B) for z in intel(fr.iloc[0], src[src.game_id == game_id] if mk != "atd" else F, DF, sched.loc[game_id], market=mk, rung_line=rung)]
        blk += [Paragraph(risk_line(fr.iloc[0], mk), RISK), Spacer(1, 5)]
        story.append(KeepTogether(blk[:2])); story += blk[2:]
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=title).build(story)
    return o


def build_game_pack(season, week, game_id, use_reads=False):
    """Single-game pack: props ladder (4/6/8), lotto ticket, anytime-TD combos (2/3/4) and ATD + props slips."""
    import json
    from itertools import combinations
    from .atd_slip import joint
    from .early import atd_parlay_pool, backup_qb_teams
    from .script_sgp import build_lotto, build_script_sgps
    O = ROOT / "outputs"
    F = pd.read_parquet(O / f"projection_features_{season}_wk{week}.parquet"); L = pd.read_csv(O / f"prop_ladders_{season}_wk{week}.csv")
    A = pd.read_csv(O / f"atd_{season}_wk{week}.csv"); PF = pd.read_parquet(O / f"props_features_{season}_wk{week}.parquet")
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text()); corr_atd = json.loads((ROOT / "models" / "correlations.json").read_text())
    from .early import apply_overrides
    F, L, A = apply_overrides(F), apply_overrides(L), apply_overrides(A)
    bq = backup_qb_teams(season, week)
    R = None
    if use_reads:
        from .matchup import reads as _reads
        R = _reads(season, week, game_id, L, PF)
    o = build_script_sgps(L, A[~A.singles_only.fillna(False).astype(bool)], PF, game_id, corr, hold_pass=tuple(bq), reads=R)
    lotto = build_lotto(L, game_id, corr, n=10, hold_pass=tuple(bq), reads=R)
    W = F[F.game_id == game_id]
    ok, held = atd_parlay_pool(W, {})          # flags and workload rules; backup-QB teams handled below
    ok = ok[~(ok.team.isin(bq) & (ok.pos_group != "RB"))]
    ok = ok.assign(play=ok.p_attd - ok.pos_group.map(CUSHION).fillna(0.05))
    cand = ok.sort_values("play", ascending=False).head(8)
    combos = {}
    for n in (2, 3, 4):
        res = []
        for idx in combinations(range(len(cand)), n):
            legs = cand.iloc[list(idx)]
            res.append({"legs": legs, "p": joint(legs, corr_atd), "p_indep": float(legs.p_attd.prod()), "play": float(legs.play.prod())})
        res.sort(key=lambda t: -t["p"])
        combos[n] = res[:3]
    return {"game": game_id, "script": o, "lotto": lotto, "combos": combos, "board": W[W.p_attd >= 0.10].sort_values("p_attd", ascending=False),
            "held": held, "bq": {k: v for k, v in bq.items() if k in set(W.team)}, "F": F, "PF": PF, "reads": R}


def render_game_pack(season, week, game_id, out_path, title, status="", use_reads=False, recommend=None, aggressive=False):
    K = build_game_pack(season, week, game_id, use_reads=use_reads); o = K["script"]; F, PF = K["F"], K["PF"]
    sched = pd.read_csv(ROOT / "data" / "schedules.csv").set_index("game_id"); DF = load_defenders()
    seen = {}

    def ticket(nm, h):
        rows = [[f"{nm} · {h['p']:.1%} · fair {am(h['p'])}", "Pos · Team", "Season", "Model"]]
        for i, x in enumerate(h["legs"].itertuples(), 1):
            why = " · ".join(x.fit_why[:2]) if isinstance(x.fit_why, (list, tuple)) else ""
            rows.append([f"<b>{i}. {leg_text(x)}</b>" + (f"<br/><font color='#5b6473' size='7.3'>{why}</font>" if why else ""),
                         f"{x.pos_group} {x.team}", f"{int(x.season_hits)}/{int(x.season_n)}" if pd.notna(x.season_n) else "", f"{x.p:.0%}"])
            seen[(x.player_id, x.market, x.k if pd.notna(x.k) else None)] = x
        return KeepTogether([_tbl(rows, [4.1, 1.1, 0.9, 1.1]), Spacer(1, 7)])

    story = [Paragraph(title, T),
             Paragraph(f"Built {datetime.now():%a %b %-d %H:%M} UTC · model only, no media picks" + (f" · {status}" if status else "")
                       + ". Bet a slip only if bet365 pays better than its fair price.", SUB), Spacer(1, 6), Paragraph("Game script", H2)]
    story += [Paragraph(f"• {n}", B) for n in o["profile"]["notes"]]
    if recommend:
        story += [Paragraph("Recommended plays", H2)] + [Paragraph(f"• {x}", B) for x in recommend]
    story += [Paragraph("1. SGP · props only", H2)]
    for t in o["ladder"]:
        if t["n"] <= 8:
            story.append(ticket(f"{t['n']}-LEG PROPS SGP", t))
    if K["lotto"]:
        story += [Paragraph("Lotto ticket · the most likely legs in the game", H2),
                  Paragraph("Each leg is the safest line the model has for that player. Every leg is a strong favourite on its own; the ticket is long because there are many of them.", SUB), Spacer(1, 3),
                  ticket(f"{len(K['lotto']['legs'])}-LEG LOTTO", K["lotto"])]
    story += [PageBreak(), Paragraph("2. Anytime-TD slip · choose 2, 3 or 4", H2)]
    for n in (2, 3, 4):
        rows = [[f"{n} scorers", "Hit", "Fair", "If independent"]]
        for c in K["combos"][n]:
            rows.append([" + ".join(f"<b>{r.name}</b> ({r.pos_group} {r.team}, {r.p_attd:.0%})" for r in c["legs"].itertuples()),
                         f"{c['p']:.1%}", am(c["p"]), f"{c['p_indep']:.1%}"])
        story += [_tbl(rows, [4.6, 0.8, 0.8, 1.0]), Spacer(1, 6)]
    story.append(Paragraph("Top line of each table is the pick; the next two are alternates. Teammates split the same touchdowns, opponents ride the same shootout, and the prices account for both.", SUB))
    rows = [["Anytime-TD board", "Pos · Team", "TD chance", "Fair", "Play at", "Note"]]
    for r in K["board"].itertuples():
        note = "backup-QB haircut applied" if getattr(r, "backup_qb_team", False) and r.pos_group != "QB" else ""
        if bool(r.singles_only): note = (note + "; " if note else "") + "single only"
        rows.append([f"<b>{r.name}</b>", f"{r.pos_group} {r.team}", f"{r.p_attd:.0%}", am(r.p_attd), am(r.p_attd - CUSHION.get(r.pos_group, 0.04)), note])
    story += [Spacer(1, 4), _tbl(rows, [2.0, 1.0, 0.8, 0.7, 0.7, 2.0])]
    story += [PageBreak(), Paragraph("3. SGP · anytime TD + props", H2)]
    for key, nm in (("hybrid6_1", "6-LEG · 1 ANYTIME TD + 5 PROPS"), ("hybrid6_2", "6-LEG · 2 ANYTIME TDS + 4 PROPS"),
                    ("hybrid8_1", "8-LEG · 1 ANYTIME TD + 7 PROPS"), ("hybrid8_2", "8-LEG · 2 ANYTIME TDS + 6 PROPS")):
        if o.get(key):
            story.append(ticket(nm, o[key]))
    if aggressive:
        import json as _json
        from .script_sgp import build_aggressive
        L_ = pd.read_csv(ROOT / "outputs" / f"prop_ladders_{season}_wk{week}.csv")
        corr_ = _json.loads((ROOT / "models" / "leg_correlations.json").read_text())
        from .early import apply_overrides as _ao
        ag = build_aggressive(_ao(L_), PF, game_id, corr_, hold_pass=tuple(K["bq"]), reads=K.get("reads"))
        K["aggressive"] = ag
        story += [PageBreak(), Paragraph("4. Aggressive SGP · higher milestones", H2),
                  Paragraph("Each leg is one step up the player's ladder, priced 50-72% on its own. Bigger payout, lower hit rate.", SUB), Spacer(1, 3)]
        for t in ag["tickets"]:
            story.append(ticket(f"AGGRESSIVE SGP · {t['n']}-LEG", t))
    story += [PageBreak(), Paragraph("Leg intel: every factor", H2)]
    for (pid, mk, k), x in seen.items():
        src = F if mk == "atd" else PF
        fr = src[(src.player_id == pid) & (src.game_id == game_id)]
        if fr.empty:
            continue
        rung = None if mk == "atd" else f"<b>This line:</b> cleared in {int(x.season_hits)} of {int(x.season_n)} games this season; model {x.p:.0%}."
        blk = [Paragraph(f"<b>{leg_text(x)} · {x.p:.0%} · fair {am(x.p)}</b>", B)]
        blk += [Paragraph(z, B) for z in intel(fr.iloc[0], src[src.game_id == game_id] if mk != "atd" else F, DF, sched.loc[game_id], market=mk, rung_line=rung)]
        blk += [Paragraph(risk_line(fr.iloc[0], mk), RISK), Spacer(1, 5)]
        story.append(KeepTogether(blk[:2])); story += blk[2:]
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=title).build(story)
    return K


def render_aggressive(season, week, game_id, out_path, title, status="", use_reads=True):
    """Aggressive SGP: 6 and 8-leg slips built from higher milestone lines (each leg priced 50-72%)."""
    import json
    from .early import backup_qb_teams
    from .script_sgp import build_aggressive
    O = ROOT / "outputs"
    L = pd.read_csv(O / f"prop_ladders_{season}_wk{week}.csv"); PF = pd.read_parquet(O / f"props_features_{season}_wk{week}.parquet")
    corr = json.loads((ROOT / "models" / "leg_correlations.json").read_text()); bq = backup_qb_teams(season, week)
    R = None
    if use_reads:
        from .matchup import reads as _reads
        R = _reads(season, week, game_id, L, PF)
    from .early import apply_overrides
    L = apply_overrides(L)
    o = build_aggressive(L, PF, game_id, corr, hold_pass=tuple(bq), reads=R)
    sched = pd.read_csv(ROOT / "data" / "schedules.csv").set_index("game_id"); DF = load_defenders()
    story = [Paragraph(title, T),
             Paragraph(f"Built {datetime.now():%a %b %-d %H:%M} UTC · model only, no media picks" + (f" · {status}" if status else "")
                       + ". Each leg is one step up the player's milestone ladder: priced 50-72% on its own, where the standard slips use 70-88%. "
                         "Bigger payout, lower hit rate. Bet a slip only if bet365 pays better than its fair price.", SUB), Spacer(1, 6)]
    for t in o["tickets"]:
        rows = [[f"AGGRESSIVE SGP · {t['n']}-LEG · {t['p']:.1%} · fair {am(t['p'])}", "Pos · Team", "Season", "Model", "Leg fair"]]
        for i, x in enumerate(t["legs"].itertuples(), 1):
            why = x.fit_why[-1] if isinstance(x.fit_why, (list, tuple)) and len(x.fit_why) else ""
            rows.append([f"<b>{i}. {leg_text(x)}</b>" + (f"<br/><font color='#5b6473' size='7.3'>{why}</font>" if why else ""),
                         f"{x.pos_group} {x.team}", f"{int(x.season_hits)}/{int(x.season_n)}", f"{x.p:.0%}", am(x.p)])
        story.append(KeepTogether([_tbl(rows, [3.7, 1.0, 0.8, 0.8, 0.9]), Spacer(1, 8)]))
    story.append(Paragraph("The 8-leg extends the 6-leg. Same construction rules as the standard slips: at most two legs per player, at most half the "
                           "ticket on one team's passing game, four games on record for every leg.", SUB))
    story += [PageBreak(), Paragraph("Leg intel: every factor", H2)]
    if o["tickets"]:
        for x in o["tickets"][-1]["legs"].itertuples():
            fr = PF[(PF.player_id == x.player_id) & (PF.game_id == game_id)]
            if fr.empty:
                continue
            rung = f"<b>This line:</b> cleared in {int(x.season_hits)} of {int(x.season_n)} games this season; model {x.p:.0%}."
            blk = [Paragraph(f"<b>{leg_text(x)} · {x.p:.0%} · fair {am(x.p)}</b>", B)]
            blk += [Paragraph(z, B) for z in intel(fr.iloc[0], PF[PF.game_id == game_id], DF, sched.loc[game_id], market=x.market, rung_line=rung)]
            blk += [Paragraph(risk_line(fr.iloc[0], x.market), RISK), Spacer(1, 5)]
            story.append(KeepTogether(blk[:2])); story += blk[2:]
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                      bottomMargin=0.55 * inch, title=title).build(story)
    return o
