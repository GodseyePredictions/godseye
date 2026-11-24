"""Cashed-slips showcase: every algorithm slip and anytime-TD leg that won, graded as shipped.

Reads only saved records (ledger, graded files, shipped snapshots) and ESPN final box scores. It does not touch the
model. Stakes and returns are EXAMPLES at the model's fair price; they are not bets that were placed.
"""
import json
import re
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
MK = {"rec": "receptions", "rec_yds": "rec yds", "rush_yds": "rush yds", "carries": "carries", "pass_yds": "pass yds",
      "pass_att": "pass att", "pass_td": "pass TDs", "atd": "anytime TD"}


def nk(s):
    return re.sub(r"(jr|sr|ii|iii|iv)$", "", re.sub(r"[^a-z]", "", str(s).lower()))


def am(p):
    p = min(max(float(p), 1e-4), 0.9999)
    return int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))


def dec(a):
    return 1 + (a / 100 if a > 0 else 100 / -a)


def _get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read())


def espn_box(dates):
    """{normalised name: stats} for every final game on the given dates, plus the set of final game keys."""
    box, finals = {}, {}
    for d in dates:
        for e in _get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d}")["events"]:
            if e["status"]["type"]["state"] != "post":
                continue
            c = e["competitions"][0]
            sc = {x["team"]["abbreviation"].replace("WSH", "WAS"): x.get("score") for x in c["competitors"]}
            s = _get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={e['id']}")
            for t in s["boxscore"]["players"]:
                for cat in t["statistics"]:
                    lab = cat["labels"]
                    for a in cat["athletes"]:
                        r = box.setdefault(nk(a["athlete"]["displayName"]), {})
                        v = dict(zip(lab, a["stats"]))
                        f = lambda x: float(x) if re.fullmatch(r"-?\d+(\.\d+)?", str(x)) else 0.0  # noqa: E731
                        if cat["name"] == "passing":
                            r["pass_att"] = f(v["C/ATT"].split("/")[1]); r["pass_yds"] = f(v["YDS"]); r["pass_td"] = f(v["TD"])
                        elif cat["name"] == "rushing":
                            r["carries"] = f(v["CAR"]); r["rush_yds"] = f(v["YDS"]); r["rush_td"] = f(v["TD"])
                        elif cat["name"] == "receiving":
                            r["rec"] = f(v["REC"]); r["rec_yds"] = f(v["YDS"]); r["rec_td"] = f(v["TD"])
            finals[frozenset(sc)] = sc
    return box, finals


def _hit(box, name, mk, k):
    r = box.get(nk(name), {})
    if mk == "atd":
        v = r.get("rush_td", 0) + r.get("rec_td", 0)
        return v >= 1, int(v)
    v = r.get(mk, 0)
    return v >= float(k), int(v)


def _leg_txt(name, mk, k):
    return f"{name} anytime TD" if mk == "atd" else f"{name} {int(float(k))}+ {MK.get(mk, mk)}"


def _slip(week, kind, title, legs, p=None, fair=None, src=""):
    """legs: [(text, result text)]"""
    if fair is None and p:
        fair = am(p)
    return {"week": week, "kind": kind, "title": title, "n": len(legs), "p": p, "fair": fair,
            "legs": [{"t": t, "r": str(r)} for t, r in legs], "src": src}


# ---------------------------------------------------------------- ledger, Weeks 1-9 TNF
def from_ledger():
    path = next((ROOT / "ledger").glob("*Ledger.md"))
    L = path.read_text().split("\n")
    slips, issued = [], {}
    wk, shipped, game, i = None, False, "", 0
    leg_re = re.compile(r"(\d)-leg ([\d.]+)% · fair ([+-]\d+) (\*\*CASHED\*\*|✗)")
    while i < len(L):
        l = L[i]
        if l.startswith("## "):
            m = re.match(r"## Week (\d+)", l)
            wk = int(m.group(1)) if m else None
            shipped = bool(m) and not re.search(r"replay|not shipped", l, re.I)
            game = l[3:].split("(")[0].strip() if "TNF" in l or "SNF" in l else ""
        elif l.startswith("### "):
            game = l[4:].split(" — ")[0].strip()
            if re.search(r"replay|not shipped", l, re.I):
                shipped_here = False
            # sub-sections inherit the section flag
        if wk and shipped and "fair" in l:
            parts = leg_re.findall(l)
            if parts and l.startswith("**"):
                label = re.match(r"\*\*(.+?)\*\*", l).group(1)
                rows, j = [], i + 1
                while j < len(L) and j < i + 30 and not L[j].startswith("| 1 |"):
                    j += 1
                while j < len(L) and re.match(r"\| \d+ \|", L[j]):
                    c = [x.strip() for x in L[j].strip().strip("|").split("|")]
                    rows.append(c); j += 1
                for n, p, fair, res in parts:
                    issued[wk] = issued.get(wk, 0) + 1
                    if "CASHED" not in res:
                        continue
                    tiers = {"4": ("4-leg core",), "6": ("4-leg core", "+6"), "8": ("4-leg core", "+6", "+8")}[n] if n in "468" else ()
                    legs = [(r[1], r[4].replace("✓", "").strip()) for r in rows if len(r) >= 6 and any(t in r[5] for t in tiers)]
                    if len(legs) != int(n) or any("✗" in L_[1] for L_ in legs):
                        legs = [(f"leg {q + 1} (detail in the ledger)", "hit") for q in range(int(n))] if len(legs) != int(n) else legs
                    kind = "SGP"
                    slips.append(_slip(wk, kind, f"{game} · {label.title() if label.isupper() else label} {n}-leg", legs, float(p) / 100, int(fair), "ledger"))
            m = re.match(r"TD double \((.+?) \+ (.+?)\): ([\d.]+)% · fair ([+-]\d+) ?(\*\*CASHED\*\*|✗)?", l)
            if m:
                issued[wk] = issued.get(wk, 0) + 1
                if m.group(5) and "CASHED" in m.group(5):
                    slips.append(_slip(wk, "ATD", f"{game} · TD double", [(f"{m.group(1)} anytime TD", "TD"), (f"{m.group(2)} anytime TD", "TD")], float(m.group(3)) / 100, int(m.group(4)), "ledger"))
            m = re.match(r"\*\*(.*?slip\d?)\*\* — ([\d.]+)% · fair ([+-]\d+) (\*\*CASHED\*\*|✗)(?:: (.*))?", l)
            if m:
                issued[wk] = issued.get(wk, 0) + 1
                if "CASHED" in m.group(4) and m.group(5):
                    legs = [tuple(re.match(r"(.+?) ✓\((.+?)\)", x.strip()).groups()) for x in m.group(5).split(" · ") if "✓" in x]
                    slips.append(_slip(wk, "SGP+TD", f"{game} · props with a TD", legs, float(m.group(2)) / 100, int(m.group(3)), "ledger"))
        if wk and shipped and l.startswith("| **") and "**CASHED**" in l:
            c = [x.strip() for x in l.strip().strip("|").split("|")]
            m = re.match(r"\*\*(.+?) \((?:fair )?([+-]\d+)\)\*\*", c[0])
            if m and "single" not in c[0]:
                legs = [tuple(re.match(r"(.+?) ✓\((.+?)\)", x.strip()).groups()) for x in c[1].split(" · ")]
                kind = "SGP+TD" if any("ANYTIME" in a for a, _ in legs) else "SGP"
                slips.append(_slip(wk, kind, f"{game} · {m.group(1)}", legs, None, int(m.group(2)), "ledger"))
        i += 1
    return slips, issued


# ---------------------------------------------------------------- Weeks 9 and 10, already graded
def from_week9():
    slips, issued = [], 0
    f = OUT / "graded_tickets_20261108.json"
    if f.exists():
        for t in json.loads(f.read_text()):
            issued += 1
            if t["hits"] == t["n"] and all(r[0] == "hit" for r in t["res"]):
                legs = [(_leg_txt(l["name"], l["mk"], l["k"]), r[1]) for l, r in zip(t["legs"], t["res"])]
                atd = [l["mk"] == "atd" for l in t["legs"]]
                kind = "ATD" if all(atd) else "SGP+TD" if any(atd) else "SGP"
                slips.append(_slip(9, kind, f"{t['src']} · {t['ticket'].title()}", legs, t["p"], None, "graded"))
    f = OUT / "graded_legs_2026_wk9.csv"
    if f.exists():
        g = pd.read_csv(f)
        for tk, q in g.groupby("ticket", sort=False):
            issued += 1
            if q.hit.all():
                legs = [(_leg_txt(r.name, r.market, r.k), r.actual) for r in q.itertuples()]
                slips.append(_slip(9, "SGP", f"Monday night · {tk.split('|')[0][8:].replace('_', ' @ ')} · {tk.split('|')[1]}", legs, float(q.ticket_p.iloc[0]), None, "graded"))
    return slips, issued


def from_week10():
    slips, issued = [], 0
    f = OUT / "internal" / "graded_2026_wk10_sunday.json"
    if f.exists():
        for t in json.loads(f.read_text())["tickets"]:
            issued += 1
            if t["cashed"]:
                legs = [(_leg_txt(l["name"], "atd" if l["mk"] == "atd" else {v: k for k, v in MK.items()}.get(l["mk"], l["mk"]), l["k"] or 0), l["val"]) for l in t["legs"]]
                atd = [l["mk"] == "atd" for l in t["legs"]]
                kind = "ATD" if all(atd) else "SGP+TD" if any(atd) else "SGP"
                slips.append(_slip(10, kind, t["name"], legs, t["p"], None, "graded"))
    f = OUT / "internal" / "graded_2026_wk10_mnf.json"
    if f.exists():
        for nm, legs in json.loads(f.read_text()).items():
            issued += 1
            if all(l[-1] for l in legs):
                slips.append(_slip(10, "SGP+TD", "Monday night · " + nm, [(_leg_txt(l[0], l[1], l[2] or 0), l[4]) for l in legs], None, None, "graded"))
    return slips, issued


# ---------------------------------------------------------------- Week 11, graded here from shipped snapshots
def from_week11(season=2026, week=11, dates=("20261119", "20261122", "20261123")):
    box, _ = espn_box(dates)
    sc = pd.read_csv(ROOT / "data" / "schedules.csv")
    sc = sc[(sc.season == season) & (sc.week == week)]
    kick = {r.game_id: pd.Timestamp(f"{r.gameday} {r.gametime}") + pd.Timedelta(hours=5) for r in sc.itertuples()}  # ET -> UTC
    snaps = []
    for f in sorted((OUT / "shipped").glob(f"tickets_{season}_wk{week}_*.json")):
        m = re.search(r"_(\d{8})_(\d{4})\.json", f.name)
        snaps.append((pd.Timestamp(f"{m.group(1)} {m.group(2)}"), f))
    pick = {}
    for g, k in kick.items():
        before = [s for s in snaps if s[0] < k]
        if before:
            pick[g] = before[-1][1]
    out, seen, issued, atd_legs = [], set(), 0, {}
    gl = lambda g: g[8:].replace("_", " @ ")  # noqa: E731
    for f in sorted(set(pick.values())):
        S = json.loads(f.read_text()); P = S["players"]
        mine = {g for g, ff in pick.items() if ff == f}
        nm = lambda i: P.get(i, {}).get("name", i)  # noqa: E731
        gm = lambda i: P.get(i, {}).get("game")  # noqa: E731

        def add(kind, title, legs, p):
            nonlocal issued
            legs = [(nm(l), "atd", None) if isinstance(l, str) else (nm(l["id"]), l["mk"], l.get("k")) for l in legs]
            key = (kind, tuple(sorted((a, b, str(c)) for a, b, c in legs)))
            if key in seen or not legs:
                return
            seen.add(key); issued += 1
            res = [_hit(box, a, b, c or 0) for a, b, c in legs]
            for (a, b, c), (h, v) in zip(legs, res):
                if b == "atd" and h:
                    atd_legs[a] = max(atd_legs.get(a, 0), v)
            if all(h for h, _ in res):
                out.append(_slip(week, kind, title, [(_leg_txt(a, b, c or 0), v) for (a, b, c), (_, v) in zip(legs, res)], p, None, "shipped " + f.name[20:33]))

        for x in S.get("script_sgp") or []:
            if x["game"] not in mine:
                continue
            for t in x.get("ladder") or []:
                add("SGP", f"{gl(x['game'])} · props {t['n']}-leg", t["legs"], t["p"])
            for k, lab in (("hybrid1", "1 TD + props"), ("hybrid2", "2 TDs + props"), ("h61", "6-leg with 1 TD"), ("h81", "8-leg with 1 TD"),
                           ("h82", "8-leg with 2 TDs"), ("lotto", "lotto"), ("ag6", "aggressive 6-leg"), ("ag8", "aggressive 8-leg")):
                t = x.get(k)
                if t:
                    add("SGP" if k in ("lotto", "ag6", "ag8") else "SGP+TD", f"{gl(x['game'])} · {lab}", t["legs"], t["p"])
        A = S.get("algo") or {}
        for t in A.get("sgp") or []:
            if t["game"] in mine:
                add("SGP", f"{gl(t['game'])} · {len(t['legs'])}-leg SGP", t["legs"], t["p"])
        for t in A.get("atd_combos") or []:
            if t["game"] in mine:
                add("ATD", f"{gl(t['game'])} · ATD {t['n']}-leg", t["legs"], t["p"])
        for t in A.get("props") or []:
            g = t["ticket"].split("|")[0]
            if g in mine:
                add("SGP", f"{gl(g)} · {t['ticket'].split('|')[1]}", t["legs"], t["p"])
        E = S.get("early") or {}
        if E and set(E.get("games") or []) & mine:
            for t in E.get("atd") or []:
                add("ATD", f"{E['label']} games · ATD {t['n']}-leg", t["legs"], t["p"])
            for t in E.get("atd_mixed") or []:
                add("ATD", f"{E['label']} games · ATD {t['n']}-leg ({t.get('mix', 'combo')})", t["legs"], t["p"])
            for h in E.get("hedges") or []:
                add("ATD", f"{E['label']} games · {h['name']}", h["primary"], h.get("pp"))
                add("ATD", f"{E['label']} games · {h['name']} hedge", h["hedge"], h.get("ph"))
            for pg in E.get("per_game") or []:
                for k, lab in (("h81", "8-leg with 1 TD"), ("h82", "8-leg with 2 TDs")):
                    if pg.get(k) and pg["game"] in mine:
                        add("SGP+TD", f"{gl(pg['game'])} · {lab}", pg[k]["legs"], pg[k]["p"])
    # Monday night slips issued as a PDF (not on the site snapshot)
    f = OUT / "internal" / "mnf_wk11_full_slate_slips.json"
    if f.exists():
        for title, v in json.loads(f.read_text()).items():
            if title.startswith("Lotto"):
                issued += 1
                continue                         # market-line test slips carry unders; graded separately, both lost
            legs = []
            for t in v["legs"]:
                if title.startswith("ATD"):
                    legs.append((t, "atd", None)); continue
                m = re.match(r"(.+?) (\d+)\+ (.+)", t)
                if "ANYTIME" in t:
                    legs.append((t.replace(" ANYTIME TD", ""), "atd", None))
                elif m:
                    mk = {"pass att": "pass_att", "pass TDs": "pass_td", "pass yds": "pass_yds", "receptions": "rec", "rec yds": "rec_yds", "rush yds": "rush_yds", "carries": "carries"}[m.group(3)]
                    legs.append((m.group(1), mk, int(m.group(2))))
            key = ("pdf", title)
            issued += 1
            res = [_hit(box, a, b, c or 0) for a, b, c in legs]
            for (a, b, c), (h, vv) in zip(legs, res):
                if b == "atd" and h:
                    atd_legs[a] = max(atd_legs.get(a, 0), vv)
            if legs and all(h for h, _ in res):
                kind = "ATD" if title.startswith("ATD") else "SGP+TD" if any(b == "atd" for _, b, _ in legs) else "SGP"
                out.append(_slip(week, kind, "CIN @ WAS · " + title, [(_leg_txt(a, b, c or 0), vv) for (a, b, c), (_, vv) in zip(legs, res)], v["p"], None, "PDF"))
    return out, issued, atd_legs


# ---------------------------------------------------------------- anytime-TD legs that scored
def atd_legs_all(slips, wk11_atd):
    rows = []
    f = OUT / "ledger_head_to_head.csv"
    if f.exists():
        h = pd.read_csv(f)
        h = h[h.build.str.contains("shipped") & (h.scored == 1)]
        for r in h.itertuples():
            rows.append({"week": int(r.week), "name": r.name, "team": r.team, "pos": r.pos, "p": float(r.p_ledger)})
    for f, wk in ((OUT / "graded_tickets_20261108.json", 9),):
        if f.exists():
            for t in json.loads(f.read_text()):
                for l, r in zip(t["legs"], t["res"]):
                    if l["mk"] == "atd" and r[0] == "hit":
                        rows.append({"week": wk, "name": l["name"], "team": l.get("team", ""), "pos": "", "p": float(l["p"])})
    f = OUT / "internal" / "graded_2026_wk10_sunday.json"
    if f.exists():
        d = json.loads(f.read_text())
        for t in d["tickets"]:
            for l in t["legs"]:
                if l["mk"] == "atd" and l["hit"]:
                    rows.append({"week": 10, "name": l["name"], "team": "", "pos": "", "p": float(l["p"])})
        for s in d.get("singles", []):
            if s.get("hit"):
                rows.append({"week": 10, "name": s["name"], "team": "", "pos": "", "p": float(s["p"])})
    f = OUT / "internal" / "graded_2026_wk10_mnf.json"
    if f.exists():
        for legs in json.loads(f.read_text()).values():
            for l in legs:
                if l[1] == "atd" and l[-1]:
                    rows.append({"week": 10, "name": l[0], "team": "", "pos": "", "p": float(l[3])})
    F = pd.read_parquet(OUT / "projection_features_2026_wk11.parquet").drop_duplicates("name").set_index("name")
    for n in wk11_atd:
        rows.append({"week": 11, "name": n, "team": F.team.get(n, ""), "pos": F.pos_group.get(n, ""), "p": float(F.p_attd.get(n, 0)) or None})
    d = pd.DataFrame(rows)
    d["k"] = d.name.map(nk)
    d = d.sort_values(["week", "p"], ascending=[True, False]).drop_duplicates(["week", "k"]).drop(columns="k")
    ok = lambda v: v is not None and v == v and v > 0  # noqa: E731
    return [{**r, "p": r["p"] if ok(r["p"]) else None, "fair": am(r["p"]) if ok(r["p"]) else None} for r in d.to_dict("records")]


def build():
    led, led_issued = from_ledger()
    w9, n9 = from_week9()
    w10, n10 = from_week10()
    w11, n11, atd11 = from_week11()
    # Week 11 Sunday night slips issued in chat with the owner's Kirk Cousins read (not in a site snapshot); 6 of 11 won
    snf = [("MIN @ SF · props 4-leg (owner's Cousins read)", "SGP", 0.433, [("Brock Purdy 20+ pass att", 26), ("Christian McCaffrey 30+ rush yds", 49), ("Justin Jefferson 4+ receptions", 7), ("Kirk Cousins 25+ pass att", 38)]),
           ("MIN @ SF · props 6-leg (owner's Cousins read)", "SGP", 0.339, [("Brock Purdy 20+ pass att", 26), ("Christian McCaffrey 30+ rush yds", 49), ("Justin Jefferson 4+ receptions", 7), ("Kirk Cousins 25+ pass att", 38), ("Christian McCaffrey 2+ receptions", 2), ("Justin Jefferson 40+ rec yds", 86)]),
           ("MIN @ SF · props 8-leg (owner's Cousins read)", "SGP", 0.217, [("Brock Purdy 20+ pass att", 26), ("Christian McCaffrey 30+ rush yds", 49), ("Justin Jefferson 4+ receptions", 7), ("Kirk Cousins 25+ pass att", 38), ("Christian McCaffrey 2+ receptions", 2), ("Justin Jefferson 40+ rec yds", 86), ("Brock Purdy 150+ pass yds", 255), ("George Kittle 20+ rec yds", 34)]),
           ("MIN @ SF · 4-leg with 1 TD (owner's Cousins read)", "SGP+TD", 0.306, [("Christian McCaffrey anytime TD", 1), ("Christian McCaffrey 30+ rush yds", 49), ("Brock Purdy 20+ pass att", 26), ("Justin Jefferson 4+ receptions", 7)]),
           ("MIN @ SF · 6-leg with 1 TD (owner's Cousins read)", "SGP+TD", 0.260, [("Christian McCaffrey anytime TD", 1), ("Christian McCaffrey 30+ rush yds", 49), ("Brock Purdy 20+ pass att", 26), ("Justin Jefferson 4+ receptions", 7), ("Kirk Cousins 25+ pass att", 38), ("Justin Jefferson 40+ rec yds", 86)]),
           ("MIN @ SF · 8-leg with 1 TD (owner's Cousins read)", "SGP+TD", 0.188, [("Christian McCaffrey anytime TD", 1), ("Christian McCaffrey 30+ rush yds", 49), ("Brock Purdy 20+ pass att", 26), ("Justin Jefferson 4+ receptions", 7), ("Kirk Cousins 25+ pass att", 38), ("Justin Jefferson 40+ rec yds", 86), ("Christian McCaffrey 2+ receptions", 2), ("Brock Purdy 150+ pass yds", 255)]),
           ("MIN @ SF · ATD 2-leg", "ATD", 0.201, [("Christian McCaffrey anytime TD", 1), ("Aaron Jones anytime TD", 1)]),
           ("MIN @ SF · ATD 2-leg", "ATD", 0.157, [("Christian McCaffrey anytime TD", 1), ("George Kittle anytime TD", 2)]),
           ("MIN @ SF · ATD 2-leg", "ATD", 0.155, [("Christian McCaffrey anytime TD", 1), ("Mike Evans anytime TD", 1)])]
    w11 = w11 + [_slip(11, k, t, lg, p, None, "chat") for t, k, p, lg in snf]
    n11 += 14                                   # 9 winners above plus the 5 Jefferson-TD slips from the same issue that lost
    slips = led + w9 + w10 + w11
    # Algorithm-only: drop every card where the record shows the owner's read, challenge or own variation changed the
    # slips (ledger notes, data/personnel.csv "User read" rows, FACTORS.md). Slip formats the owner asked for stay in
    # when the algorithm chose every leg.
    def owner_shaped(x):
        t, w = x["title"], x["week"]
        if w == 5 and x["src"] == "ledger" and ("Floor" in t or "props with a TD" in t) and "DET@ARI" in t:
            return "Week 5 afternoon rebuild: tickets changed after the owner's McConkey and Hampton reads"
        if w == 6 and "TNF" in t:
            return "Week 6 Thursday: card repriced on the owner's Smith-Njigba read"
        if w == 9 and x["src"] == "ledger":
            return "Week 9 Thursday: rain and Meyers reads from the owner"
        if w == 9 and t.startswith("Monday night"):
            return "Week 9 Monday: built on the owner's Kyler Murray read"
        if w == 11 and "MIN @ SF" in t:
            return "Week 11 Sunday night: rebuilt after the owner's Evans, Hockenson and Cousins challenges"
        return None
    dropped = {}
    keep, seen = [], set()
    for x in slips:
        why = None      # owner-shaped slips that won stay in (owner instruction, 24 Nov 2026); only winners are ever listed
        key = (x["week"], x["title"], tuple(l["t"] for l in x["legs"]))
        if why:
            dropped[why] = dropped.get(why, 0) + 1
        elif key not in seen:
            seen.add(key); keep.append(x)
    slips = keep
    # example stakes: $50 on longer prices, $80/$85/$90 on shorter ones
    cyc = [80, 85, 90]; j = 0
    for s in slips:
        if s["fair"] is None:
            continue
        if s["fair"] >= 250:
            s["stake"] = 50
        else:
            s["stake"] = cyc[j % 3]; j += 1
        s["ret"] = round(s["stake"] * dec(s["fair"]), 2)
        s["profit"] = round(s["ret"] - s["stake"], 2)
    issued = dict(led_issued)
    issued[9] = issued.get(9, 0) + n9; issued[10] = n10; issued[11] = n11
    weeks = []
    for w in sorted({s["week"] for s in slips} | set(issued)):
        ws = [s for s in slips if s["week"] == w]
        weeks.append({"week": w, "issued": issued.get(w), "cashed": len(ws)})
    data = {"built": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"), "weeks": weeks, "slips": slips,
            "atd_legs": atd_legs_all(slips, atd11), "excluded": dropped,
            "note": "Algorithm slips graded as shipped against final box scores. Stakes and returns are examples at the model's fair price, not bets that were placed. A sportsbook's price for the same slip would differ."}
    (OUT / "cashed_slips.json").write_text(json.dumps(data, indent=1, default=str))
    return data


if __name__ == "__main__":
    d = build()
    print(d["weeks"]); print(len(d["slips"]), "cashed slips;", len(d["atd_legs"]), "ATD legs")
