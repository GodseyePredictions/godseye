"""PDF for the full-slate comparison (algorithm vs matchup reads vs agreed slips, ATDs, all-team defence table)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .atd_slip import CUSHION, am
from .defense_report import summary
from .script_sgp import leg_text
from .window_pdf import B, H2, RISK, SUB, T, _gl, _tbl
from reportlab.lib.styles import ParagraphStyle

SM = ParagraphStyle("SMx", parent=B, fontSize=7.8, leading=9.8)


def _key(df):
    return set(zip(df.player_id, df.market, df.k.fillna(-1)))


def render(season, week, K, out_path, title, status=""):
    sched = pd.read_csv(K["D"].index.name and "/dev/null" or "/dev/null") if False else None
    sc = pd.read_csv(__import__("pathlib").Path(__file__).resolve().parent.parent / "data" / "schedules.csv").set_index("game_id")
    def kick(g):
        h, m = str(sc.loc[g, "gametime"]).split(":"); h = (int(h) - 2) % 24
        return f"{sc.loc[g, 'weekday'][:3]} {(h - 1) % 12 + 1}:{m} {'am' if h < 12 else 'pm'} MST"
    story = [Paragraph(title, T),
             Paragraph(f"Built {datetime.now():%a %b %-d %H:%M} UTC · model only, no media picks" + (f" · {status}" if status else "") + ". "
                       "Every game is built three ways: the algorithm alone, the algorithm steered by matchup reads, and the agreed slip, "
                       "where a leg must be priced by the model and cleared by at least 60% of that role against this defence. "
                       "Probabilities are always the model's. Bet a slip only if bet365 pays better than its fair price.", SUB), Spacer(1, 6),
             Paragraph("Final SGPs at a glance", H2)]
    rows = [["Game", "Kick", "4-leg", "6-leg", "8-leg", "Built from"]]
    for o in K["per_game"]:
        c = o["cmp"]
        cell = lambda n: f"{c[n]['final']['p']:.1%} · {am(c[n]['final']['p'])}" if c[n]["final"] else "none"  # noqa: E731
        rows.append([f"<b>{_gl(o['game'])}</b>", kick(o["game"]), cell(4), cell(6), cell(8), c[4]["final_is"] + (" · same legs as the algorithm" if c[4]["same_as_model"] else "")])
    story.append(_tbl(rows, [1.0, 1.25, 1.1, 1.1, 1.1, 1.75]))
    story += [Paragraph("Final anytime-TD tickets at a glance", H2)]
    rows = [["Ticket", "Legs", "Hit", "Fair"]]
    for t in K["atd_final"]:
        rows.append([f"<b>{t['n']}-leg</b>", " · ".join(t["legs"].name), f"{t['p']:.2%}", am(t["p"])])
    story.append(_tbl(rows, [0.8, 4.9, 0.7, 0.9]))
    # ---------------- ATDs
    story += [PageBreak(), Paragraph("Anytime TDs: algorithm against the run-defence matchup", H2),
              Paragraph("Touchdowns allowed by position showed no carry-over in the backtest, so receivers and tight ends are not adjusted. "
                        "Run defence did carry over (soft run defences allowed 0.79 rushing TDs to backs the next game against 0.64 for stingy ones), "
                        "so a back facing a bottom-ten run defence moves up the ticket order and a back facing a top-eight one moves down. "
                        "Tickets are backs and quarterbacks, one per team.", SUB), Spacer(1, 4)]
    mm = {t["n"]: t for t in K["atd_model"]}
    for t in K["atd_final"]:
        a = mm.get(t["n"])
        rows = [[f"FINAL {t['n']}-LEG ATD · {t['p']:.2%} · fair {am(t['p'])}", "Pos · Team", "Game", "TD chance", "Matchup"]]
        for i, r in enumerate(t["legs"].itertuples(), 1):
            rows.append([f"<b>{i}. {r.name}</b>", f"{r.pos_group} {r.team}", _gl(r.game_id), f"{r.p_attd:.0%}", r.matchup or "neutral"])
        blk = [_tbl(rows, [2.6, 0.9, 1.1, 0.9, 1.7])]
        if a is not None:
            diff_in = [x for x in t["legs"].name if x not in set(a["legs"].name)]; diff_out = [x for x in a["legs"].name if x not in set(t["legs"].name)]
            blk.append(Paragraph(f"Algorithm-only {t['n']}-leg: {a['p']:.2%}, fair {am(a['p'])}. " +
                                 ("Same legs." if not diff_in else f"The matchup swapped in {', '.join(diff_in)} for {', '.join(diff_out)}."), SUB))
        story.append(KeepTogether(blk + [Spacer(1, 7)]))
    bd = K["board"]
    rows = [["Scorer board (25%+)", "Pos · Team", "Game", "TD chance", "Fair", "Play at", "Run-defence matchup", "Use"]]
    heldn = {h[0]: h[2] for h in K["held"]}
    for r in bd.itertuples():
        use = "single (held)" if r.name in heldn else "single (flagged)" if bool(r.singles_only) else "single (WR/TE rule)" if r.pos_group in ("WR", "TE") else "ticket-eligible"
        rows.append([f"<b>{r.name}</b>", f"{r.pos_group} {r.team}", _gl(r.game_id), f"{r.p_attd:.0%}", am(r.p_attd), am(r.play), r.matchup or "", use])
    story += [Paragraph("Scorer board", H2), _tbl(rows, [1.7, 0.75, 0.9, 0.7, 0.55, 0.6, 1.2, 1.0])]
    # ---------------- per game
    D = K["D"]
    for o in K["per_game"]:
        g = o["game"]; a, h = g.split("_")[2], g.split("_")[3]; c = o["cmp"]
        story += [PageBreak(), Paragraph(f"{_gl(g)} · {kick(g)}", H2)]
        story += [Paragraph(f"• {x}", SM) for x in o["model"]["profile"]["notes"]]
        for tm, opp in ((h, a), (a, h)):
            story.append(Paragraph(f"<b>{tm} defence</b> (what {opp} faces)", B))
            story += [Paragraph(x, SM) for x in summary(D, tm)]
        rows = [["", "Algorithm", "Matchup-steered", "FINAL (agreed)"]]
        for n in (4, 6, 8):
            f = lambda t: f"{t['p']:.1%} · {am(t['p'])}" if t else "none"  # noqa: E731
            rows.append([f"<b>{n}-leg</b>", f(c[n]["model"]), f(c[n]["reads"]), f(c[n]["final"]) + ("" if c[n]["final_is"] == "agreed" else " (algorithm)")])
        story += [Spacer(1, 4), _tbl(rows, [0.8, 2.1, 2.1, 2.3])]
        top = c[8]["final"] or c[6]["final"] or c[4]["final"]
        if top is not None:
            rows = [[f"FINAL SGP · legs in order (4-leg = first four, 6-leg = first six)", "Pos · Team", "Season", "Model"]]
            for i, x in enumerate(top["legs"].itertuples(), 1):
                why = x.fit_why[-1] if isinstance(x.fit_why, (list, tuple)) and len(x.fit_why) else ""
                rows.append([f"<b>{i}. {leg_text(x)}</b>" + (f"<br/><font color='#5b6473' size='7.2'>{why}</font>" if why else ""),
                             f"{x.pos_group} {x.team}", f"{int(x.season_hits)}/{int(x.season_n)}" if pd.notna(x.season_n) else "", f"{x.p:.0%}"])
            story += [Spacer(1, 4), _tbl(rows, [4.1, 1.1, 0.9, 1.1])]
            ml = c[len(top["legs"])]["model"] if len(top["legs"]) in c else None
            if ml is not None:
                km, kf = _key(ml["legs"]), _key(top["legs"])
                out_ = [leg_text(x) for x in ml["legs"].itertuples() if (x.player_id, x.market, -1 if pd.isna(x.k) else x.k) not in kf]
                in_ = [leg_text(x) for x in top["legs"].itertuples() if (x.player_id, x.market, -1 if pd.isna(x.k) else x.k) not in km]
                story.append(Paragraph("Same legs as the algorithm's own slip." if not out_ and not in_ else
                                       f"Against the algorithm's slip the matchup removed: {', '.join(out_) or 'nothing'}. Added: {', '.join(in_) or 'nothing'}.", SUB))
        h6 = o["final"].get("hybrid6_1") or o["model"].get("hybrid6_1")
        if h6:
            story.append(Paragraph(f"<b>6-leg with one anytime TD, {h6['p']:.1%}, fair {am(h6['p'])}:</b> " + " · ".join(leg_text(x) for x in h6["legs"].itertuples()), B))
    # ---------------- appendix
    story += [PageBreak(), Paragraph("Every defence by position, season to date (rank 1 = best defence)", H2)]
    cols = [("rb_rush", "Rush yds/g"), ("rb_ypc", "Yds/carry"), ("rb_rushtd", "Rush TD/g"), ("wr_yds", "WR yds/g"), ("wr_rec", "WR rec/g"),
            ("te_yds", "TE yds/g"), ("rb_recyds", "RB rec yds/g"), ("pass_yds", "Pass yds/g"), ("sack_rate", "Sack rate")]
    rows = [["Team"] + [c[1] for c in cols]]
    for tm, r in D.sort_values("r_rb_rush").iterrows():
        rows.append([f"<b>{tm}</b>"] + [(f"{r[k]:.1%}" if k == "sack_rate" else f"{r[k]:.2f}" if k in ("rb_ypc", "rb_rushtd") else f"{r[k]:.0f}" if k != "wr_rec" else f"{r[k]:.1f}") + f" ({int(r['r_' + k])})" for k, _ in cols])
    story.append(_tbl(rows, [0.55] + [0.74] * 9))
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.55 * inch, rightMargin=0.55 * inch, topMargin=0.5 * inch,
                      bottomMargin=0.5 * inch, title=title).build(story)
