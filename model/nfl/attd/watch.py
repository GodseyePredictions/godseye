"""News watch: re-pull injuries/rosters/schedules + NWS forecasts, diff against the last snapshot, flag shipped legs.

`python run.py refresh --season S --week W` is the on-demand entry point. The diff is appended to
data/news_log.jsonl and summarised in outputs/watch_<S>_wk<W>.md so the next site build can show "what changed".
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from .context import fetch_forecasts
from .data import DATA_DIR, download

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
SNAP = DATA_DIR / "watch_snapshots"


def _inj_state(season, week):
    i = pd.read_parquet(DATA_DIR / f"inj_{season}.parquet")
    i = i[i.week == week]
    return {f"{r.team}|{r.full_name}": [str(r.report_status), str(r.practice_status), str(r.report_primary_injury)]
            for r in i.itertuples()}


def _roster_state(season, week):
    r = pd.read_parquet(DATA_DIR / f"roster_{season}.parquet")
    r = r[(r.week == week) & r.position.isin(["QB", "RB", "WR", "TE"])]
    return {str(x.gsis_id): [x.team, str(x.status), x.full_name] for x in r.itertuples() if pd.notna(x.gsis_id)}


def _sched_state(season, week):
    s = pd.read_csv(DATA_DIR / "schedules.csv")
    s = s[(s.season == season) & (s.week == week)]
    return {g.game_id: [g.spread_line, g.total_line, str(g.gameday), str(g.gametime)] for g in s.itertuples()}


def _wx_state(season, week):
    f = DATA_DIR / f"forecast_{season}_wk{week}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def snapshot(season, week):
    return {"inj": _inj_state(season, week), "roster": _roster_state(season, week),
            "sched": _sched_state(season, week), "wx": _wx_state(season, week),
            "at": datetime.utcnow().isoformat(timespec="minutes") + "Z"}


def diff(old, new):
    ev = []
    for k, v in new["inj"].items():
        o = old["inj"].get(k)
        if o is None:
            if v[0] != "nan" or "Not" in v[1]:
                ev.append({"kind": "injury", "key": k, "msg": f"{k.split('|')[1]} ({k.split('|')[0]}) added to report: "
                           f"{v[0] if v[0] != 'nan' else 'no designation'}, {v[1].lower()}, {v[2]}"})
        elif o[:2] != v[:2]:
            ev.append({"kind": "injury", "key": k, "msg": f"{k.split('|')[1]} ({k.split('|')[0]}): {o[0]} → {v[0]}; "
                       f"practice {o[1].lower()} → {v[1].lower()}"})
    for k, v in new["roster"].items():
        o = old["roster"].get(k)
        if o and (o[0] != v[0] or o[1] != v[1]):
            ev.append({"kind": "roster", "key": k, "msg": f"{v[2]}: {o[0]} {o[1]} → {v[0]} {v[1]}"})
    for g, v in new["sched"].items():
        o = old["sched"].get(g)
        if o and (o[0] != v[0] or o[1] != v[1]):
            ev.append({"kind": "market", "key": g, "msg": f"{g}: spread {o[0]} → {v[0]}, total {o[1]} → {v[1]}"})
        if o and o[2:] != v[2:]:
            ev.append({"kind": "schedule", "key": g, "msg": f"{g}: kickoff {o[2]} {o[3]} → {v[2]} {v[3]}"})
    for g, v in new["wx"].items():
        o = old["wx"].get(g)
        if o is None:
            continue
        chg = []
        if abs((v.get("temp") or 0) - (o.get("temp") or 0)) >= 5:
            chg.append(f"temp {o.get('temp'):.0f}→{v.get('temp'):.0f}°F")
        if abs((v.get("wind") or 0) - (o.get("wind") or 0)) >= 5:
            chg.append(f"wind {o.get('wind'):.0f}→{v.get('wind'):.0f} mph")
        if (v.get("pop") or 0) - (o.get("pop") or 0) >= 30 or (o.get("pop") or 0) - (v.get("pop") or 0) >= 30:
            chg.append(f"precip {o.get('pop')}%→{v.get('pop')}%")
        if chg:
            ev.append({"kind": "weather", "key": g, "msg": f"{g}: " + ", ".join(chg) + f" ({v.get('short')})"})
    return ev


def affected_shipped(events):
    """Shipped legs (from the current site build) whose player or game is named by an event."""
    try:
        from .live import load_shipped
        tickets, board = load_shipped()
    except Exception:  # noqa: BLE001
        return []
    names = {e["key"].split("|")[-1] for e in events if e["kind"] == "injury"}
    games = {e["key"] for e in events if e["kind"] in ("weather", "market", "schedule")}
    hits = []
    for t in tickets:
        for l in t["legs"]:
            if l["name"] in names or l["game_id"] in games:
                hits.append(f"{t['group']} {t['name']}: {l['name']} ({l['mk']}{'' if l['k'] is None else ' ' + str(l['k']) + '+'})")
    return sorted(set(hits))


def refresh(season, week, pull=True):
    SNAP.mkdir(parents=True, exist_ok=True)
    prev_f = SNAP / f"{season}_wk{week}.json"
    had_prev = prev_f.exists()
    old = json.loads(prev_f.read_text()) if had_prev else None
    if pull:
        download(range(season, season + 1), force_current=season)
        sched = pd.read_csv(DATA_DIR / "schedules.csv")
        fetch_forecasts(sched, season, week)
    new = snapshot(season, week)
    events = diff(old, new) if had_prev else []
    prev_f.write_text(json.dumps(new))
    hits = affected_shipped(events)
    stamp = new["at"]
    with (DATA_DIR / "news_log.jsonl").open("a") as fh:
        for e in events:
            fh.write(json.dumps({"at": stamp, "season": season, "week": week, **e}) + "\n")
    md = [f"# Watch · {season} Week {week} · {stamp}", ""]
    if not had_prev:
        md.append("Baseline snapshot taken.")
    elif not events:
        md.append("No changes since the last snapshot.")
    for kind, ttl in (("injury", "Injury report"), ("roster", "Roster moves"), ("market", "Line moves"),
                      ("schedule", "Schedule"), ("weather", "Weather")):
        rows = [e for e in events if e["kind"] == kind]
        if rows:
            md += [f"## {ttl}"] + [f"- {e['msg']}" for e in rows] + [""]
    if hits:
        md += ["## Shipped legs touched"] + [f"- {h}" for h in hits] + [""]
    (OUT / f"watch_{season}_wk{week}.md").write_text("\n".join(md))
    print("\n".join(md))
    return events, hits
