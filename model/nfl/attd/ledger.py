"""Parse the season ledger (shipped ATD prices + results) for head-to-head grading."""
from __future__ import annotations

import re

import pandas as pd

SECTIONS = {  # ledger "## " heading prefix -> (week, build label)
    "Week 1 — Sunday Sept 13": (1, "v1.3 shipped"),
    "Week 3 — Sunday Sept 27": (3, "v1.7 shipped"),
    "Week 3 — v1.8 replay": (3, "v1.8 replay"),
    "Week 4 — Sunday Oct 4": (4, "v1.8/1.9 shipped"),
    "Week 5 — Sunday Oct 11": (5, "v1.9b shipped"),
    "Week 6 — Sunday Oct 18": (6, "v1.9e shipped"),
    "Week 6 — v1.9f build": (6, "v1.9f pre-kick"),
    "Week 8 — Sunday Nov 1": (8, "v1.9f shipped"),
    "Week 8 — v1.9g replay": (8, "v1.9g replay"),
    "Week 9 TNF": (9, "v1.9g shipped"),
}
ROW = re.compile(r"^\|\s*([^|]+?)\s*\(([A-Z]{2,3})\s+(QB|RB|WR|TE|FB)\)\s*\|\s*(\d+)%\s*\|.*?(✓ TD|✗ no TD)")


def parse(path) -> pd.DataFrame:
    rows, sec, game = [], None, None
    for line in open(path, encoding="utf-8"):
        if line.startswith("## "):
            sec = next((v for k, v in SECTIONS.items() if line[3:].startswith(k)), None)
            game = "JAX@BAL" if sec and sec[0] == 9 else None
        elif line.startswith("### "):
            m = re.match(r"### ([A-Z]{2,3})@([A-Z]{2,3})", line)
            game = f"{m.group(1)}@{m.group(2)}" if m else game
        elif sec and game:
            m = ROW.match(line)
            if m:
                rows.append({"week": sec[0], "build": sec[1], "game": game, "name": m.group(1).strip(),
                             "team": m.group(2), "pos": m.group(3), "p_ledger": int(m.group(4)) / 100,
                             "scored": int(m.group(5).startswith("✓"))})
    d = pd.DataFrame(rows).drop_duplicates(["build", "name", "team"])
    return d


def norm(s: pd.Series) -> pd.Series:
    return (s.str.lower().str.replace(r"\b(jr|sr|ii|iii|iv)\b\.?", "", regex=True)
            .str.replace(r"[^a-z]", "", regex=True))


PROP_ROW = re.compile(r"^\|\s*\d+\s*\|\s*(.+?)\s+(\d+)\+\s+(receptions|rush yds|rec yds|carries|pass yds|pass att)\s*\|"
                      r"\s*(\d+)%\s*\|[^|]*\|\s*(✓|✗)")
MARKET_OF = {"receptions": "rec", "rush yds": "rush_yds", "rec yds": "rec_yds", "carries": "carries",
             "pass yds": "pass_yds", "pass att": "pass_att"}


def parse_props(path) -> pd.DataFrame:
    """Every props-SGP leg in the ledger: (build, week, game, name, market, k, p_ledger, hit)."""
    rows, sec, game, block = [], None, None, None
    for line in open(path, encoding="utf-8"):
        if line.startswith("## "):
            sec = next((v for k, v in SECTIONS.items() if line[3:].startswith(k)), None)
            if sec is None and line[3:].startswith("Week 4 — aggressive"):
                sec = (4, "W4 aggressive")
            elif sec is None and line[3:].startswith("Week 5 — aggressive"):
                sec = (5, "W5 aggressive")
            elif sec is None and line[3:].startswith("Week 6 — aggressive"):
                sec = (6, "W6 aggressive")
            elif sec is None and line[3:].startswith("Week 8 — aggressive"):
                sec = (8, "W8 aggressive")
            game = "JAX@BAL" if sec and sec[0] == 9 else None
        elif line.startswith("### "):
            m = re.match(r"### ([A-Z]{2,3})@([A-Z]{2,3})", line)
            game = f"{m.group(1)}@{m.group(2)}" if m else game
        elif line.startswith("**") and "SGP" in line:
            block = line.split("**")[1]
        elif sec and game:
            m = PROP_ROW.match(line)
            if m:
                rows.append({"week": sec[0], "build": sec[1] if "AGGRESSIVE" not in (block or "") or "aggressive" in sec[1]
                             else sec[1] + " (aggr)", "game": game, "name": m.group(1).strip(),
                             "market": MARKET_OF[m.group(3)], "k": int(m.group(2)),
                             "p_ledger": int(m.group(4)) / 100, "hit": int(m.group(5) == "✓")})
    return pd.DataFrame(rows).drop_duplicates(["build", "game", "name", "market", "k"])
