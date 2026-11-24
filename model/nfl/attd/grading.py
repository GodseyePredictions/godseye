"""Grade a saved weekly card 'as shipped' against official nflverse stat lines (standing rule 5)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import data as D

ROOT = Path(__file__).resolve().parent.parent


def grade_card(season: int, week: int, refresh=True) -> str:
    if refresh:
        D.download([season], force_current=season)
    card = json.loads((ROOT / "outputs" / f"card_{season}_wk{week}.json").read_text())
    L = pd.DataFrame(card["legs"])
    st = D.load_official_stats([season])
    pbp = D.load_pbp([season])
    td = pbp[(pbp.touchdown == 1) & (pbp.td_team == pbp.posteam) & pbp.play_type.isin(["run", "pass"])
             & (pbp.two_point_attempt != 1)].groupby(["game_id", "td_player_id"]).size()
    done = set(pbp.game_id.unique())
    L = L[L.game_id.isin(done)]
    if L.empty:
        return "No graded games yet for this card."

    def result(r):
        if r.market == "atd":
            return int(td.get((r.game_id, r.player_id), 0) > 0), "TD" if td.get((r.game_id, r.player_id), 0) else "no TD"
        row = st[(st.game_id == r.game_id) & (st.player_id == r.player_id)]
        x = float(row[r.market].iloc[0]) if len(row) else 0.0   # no box line = did not record a stat (miss)
        return int(x >= r.k), f"{x:.0f}"
    res = L.apply(result, axis=1, result_type="expand")
    L["hit"], L["actual"] = res[0], res[1]

    out = [f"# Report card — {season} Week {week} (graded as shipped)", ""]
    legs = L.drop_duplicates(["game_id", "player_id", "market", "k"])
    props = legs[legs.market != "atd"]
    atd = legs[legs.market == "atd"]
    out.append(f"**Prop legs:** {props.hit.sum()}/{len(props)} = {props.hit.mean():.0%} actual vs "
               f"{props.p.mean():.0%} expected")
    out.append(f"**ATD legs:** {atd.hit.sum()}/{len(atd)} = {atd.hit.mean():.0%} actual vs {atd.p.mean():.0%} expected")
    out += ["", "| Ticket | Price | Legs | Result |", "|---|---|---|---|"]
    for t, g in L[L.ticket_p.notna()].groupby("ticket", sort=False):
        ok = g.hit.all()
        out.append(f"| {t} | {g.ticket_p.iloc[0]:.1%} | " + " · ".join(
            f"{r['name']} {'ATD' if r.market == 'atd' else str(int(r.k)) + '+ ' + r.market} "
            f"{'✓' if r.hit else '✗'}({r.actual})" for _, r in g.iterrows()) + f" | {'**CASHED**' if ok else '✗'} |")
    # calibration of shipped legs by band
    props = props.assign(band=pd.cut(props.p, [0, .55, .68, .70, .88, 1.0]))
    out += ["", "| Band | Legs | Expected | Actual |", "|---|---|---|---|"]
    for b, g in props.groupby("band", observed=True):
        out.append(f"| {b} | {len(g)} | {g.p.mean():.0%} | {g.hit.mean():.0%} |")
    txt = "\n".join(out)
    (ROOT / "outputs" / f"report_card_{season}_wk{week}.md").write_text(txt)
    L.to_csv(ROOT / "outputs" / f"graded_legs_{season}_wk{week}.csv", index=False)
    return txt
