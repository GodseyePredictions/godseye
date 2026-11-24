from __future__ import annotations

from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .atd_slip import am
from .window_pdf import B, H2, RISK, SUB, T, _gl, _tbl


def render(K, out_path, title, status=""):
    V, H = K["versions"], K["hedges"]
    story = [Paragraph(title, T),
             Paragraph(f"Built {datetime.now():%a %b %-d %H:%M} UTC · model only, no media picks" + (f" · {status}" if status else "") + ". "
                       f"Games: {' · '.join(_gl(g) for g in K['games'])}. One player per team on every ticket. Probabilities are the model's; "
                       "the matchup column only decides the order legs are taken in. Bet a ticket only if bet365 pays better than its fair price.", SUB),
             Spacer(1, 6), Paragraph("All versions at a glance", H2)]
    rows = [["Version", "4-leg", "6-leg", "4-leg players"]]
    for k, v in V.items():
        t = {x["n"]: x for x in v["tickets"]}
        f = lambda n: f"{t[n]['p']:.2%} · {am(t[n]['p'])}" if n in t else "none"  # noqa: E731
        rows.append([f"<b>{v['name']}</b>", f(4), f(6), " · ".join(t[4]["legs"].name) if 4 in t else ""])
    story.append(_tbl(rows, [2.2, 1.1, 1.2, 2.8]))
    for k, v in V.items():
        blk = [Paragraph(v["name"], H2), Paragraph(v["note"], SUB), Spacer(1, 3)]
        for t in v["tickets"]:
            rows = [[f"{t['n']}-LEG · {t['p']:.2%} · fair {am(t['p'])}", "Pos · Team", "Game", "TD chance", "Matchup"]]
            for i, r in enumerate(t["legs"].itertuples(), 1):
                rows.append([f"<b>{i}. {r.name}</b>", f"{r.pos_group} {r.team}", _gl(r.game_id), f"{r.p_attd:.0%}", r.mx_tag])
            blk += [_tbl(rows, [2.7, 1.0, 1.2, 1.0, 1.3]), Spacer(1, 5)]
        story.append(KeepTogether(blk))
    story += [PageBreak(), Paragraph("Hedge slips: three options", H2),
              Paragraph("Each option is a primary slip and a hedge slip. In the hedge, the two least likely legs are swapped for the next-best scorer on the same team, so it wins when that team's touchdown goes to the other man.", SUB), Spacer(1, 4)]
    for i, w in enumerate(H.get("swaps", []), 1):
        rows = [[f"Option {i} · {w['name']}", "Primary slip", "Hedge slip"]]
        hn = list(w["hedge"].name); pn = list(w["primary"].name)
        for j in range(max(len(pn), len(hn))):
            a_ = w["primary"].iloc[j] if j < len(pn) else None; b_ = w["hedge"].iloc[j] if j < len(hn) else None
            rows.append([f"Leg {j + 1}", f"{a_['name']} ({a_.pos_group} {a_.team}) {a_.p_attd:.0%}" if a_ is not None else "",
                         (f"<b>{b_['name']}</b>" if b_ is not None and b_['name'] not in pn else (b_['name'] if b_ is not None else "")) + (f" ({b_.pos_group} {b_.team}) {b_.p_attd:.0%}" if b_ is not None else "")])
        rows.append(["<b>Hit</b>", f"<b>{w['p_primary']:.1%} · fair {am(w['p_primary'])}</b>", f"<b>{w['p_hedge']:.1%} · fair {am(w['p_hedge'])}</b>"])
        story.append(KeepTogether([_tbl(rows, [1.9, 2.6, 2.6]),
                                   Paragraph("Swapped: " + "; ".join(f"{a} ({pa:.0%}) for {b} ({pb:.0%})" for a, pa, b, pb in [(c[2], c[3], c[0], c[1]) for c in w["changes"]]) +
                                             f". At least one of the two slips cashes {w['p_either']:.1%} of the time.", SUB), Spacer(1, 8)]))
    story += [Paragraph("Other hedges", H2)]
    a = H.get("air_cover")
    if a:
        rows = [["Ground leg", "TD chance", "Air cover, same team", "TD chance"]]
        for r, c in zip(a["ground"].itertuples(), a["cover"].itertuples()):
            rows.append([f"<b>{r.name}</b> ({r.pos_group} {r.team})", f"{r.p_attd:.0%}", f"<b>{c.name}</b> ({c.pos_group} {c.team})", f"{c.p_attd:.0%}"])
        story += [Paragraph("1. Air cover for the ground ticket", B),
                  Paragraph("A second 4-leg made of the best pass-catcher on each of the same four teams. It wins in the script where those teams score through the air.", SUB), Spacer(1, 3),
                  _tbl(rows, [2.4, 0.9, 2.6, 0.9]),
                  Paragraph(f"Ground ticket {a['p_ground']:.1%} · air cover {a['p_cover']:.1%} · at least one of the two cashes {a['p_either']:.1%}. "
                            "The cover adds about three points of coverage for a second stake, so it is a long-shot add-on, not insurance.", SUB), Spacer(1, 8)]
    rr = H.get("round_robin")
    if rr:
        d = rr["dist"]
        story += [Paragraph("2. Round robin on the ground 4-leg", B),
                  Paragraph(f"How many of the four score: all four {d[4]:.1%}, exactly three {d[3]:.1%}, exactly two {d[2]:.1%}, one {d[1]:.1%}, none {d[0]:.1%}. "
                            f"Three or more score {rr['p_ge3']:.1%} of the time; two or more {rr['p_ge2']:.1%}.", SUB), Spacer(1, 3)]
        rows = [["Trebles (by 3s): one miss still pays one ticket", "Hit", "Fair"]]
        for x in rr["by3"]: rows.append([" + ".join(x["legs"].name), f"{x['p']:.1%}", am(x["p"])])
        story.append(_tbl(rows, [4.8, 0.9, 1.1]))
        rows = [["Doubles (by 2s): two misses still pay one ticket", "Hit", "Fair"]]
        for x in rr["by2"]: rows.append([" + ".join(x["legs"].name), f"{x['p']:.1%}", am(x["p"])])
        story += [Spacer(1, 4), _tbl(rows, [4.8, 0.9, 1.1]), Spacer(1, 8)]
    if H.get("pairs"):
        rows = [["Team", "Lead back", "Top pass-catcher", "Either scores", "Both score"]]
        for p in H["pairs"]:
            rows.append([f"<b>{p['team']}</b>", f"{p['back']['name']} {p['back'].p_attd:.0%}", f"{p['catcher']['name']} {p['catcher'].p_attd:.0%}", f"{p['p_either']:.0%}", f"{p['p_both']:.0%}"])
        story += [KeepTogether([Paragraph("3. Either-scorer pairs (two singles on one offence)", B),
                  Paragraph("Backing the lead back and the top pass-catcher on the same team as two singles. One of them scores this often. It only pays if both prices together beat the combined chance.", SUB),
                  Spacer(1, 3), _tbl(rows, [0.7, 2.1, 2.3, 1.0, 0.9]), Spacer(1, 8)])]
    if H.get("shootout"):
        rows = [["Game", "Opposite-team double", "Hit", "Fair"]]
        for s in H["shootout"]: rows.append([f"<b>{_gl(s['game'])}</b>", " + ".join(f"{r.name} ({r.team})" for r in s["legs"].itertuples()), f"{s['p']:.1%}", am(s["p"])])
        story += [KeepTogether([Paragraph("4. Shootout doubles (one scorer from each side of a game)", B), Spacer(1, 3), _tbl(rows, [1.1, 4.0, 0.8, 0.9])])]
    bd = K["board"]; heldn = {h[0] for h in K["held"]}
    rows = [["Scorer board (25%+)", "Pos · Team", "Game", "TD chance", "Fair", "Play at", "Matchup", "Note"]]
    for r in bd.itertuples():
        note = "held: single only" if r.name in heldn else "flagged: single only" if bool(r.singles_only) else ""
        rows.append([f"<b>{r.name}</b>", f"{r.pos_group} {r.team}", _gl(r.game_id), f"{r.p_attd:.0%}", am(r.p_attd), am(r.play), r.mx_tag, note])
    story += [PageBreak(), Paragraph("Scorer board with matchup", H2),
              Paragraph("Matchup for backs: own line's yards per carry, the opposing front's yards per carry allowed and stuff rate, opponent run-defence rank, goal-line carry share. "
                        "For pass-catchers: expected dropbacks, opposing sack rate, yards per target allowed to the position, end-zone target share, red-zone pass rate.", SUB), Spacer(1, 3),
              _tbl(rows, [1.7, 0.8, 0.95, 0.7, 0.55, 0.6, 0.7, 1.3])]
    SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.55 * inch, rightMargin=0.55 * inch, topMargin=0.5 * inch, bottomMargin=0.5 * inch, title=title).build(story)
