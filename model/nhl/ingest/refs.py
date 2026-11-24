"""Referee crews: tonight's assignments from Scouting the Refs, and each referee's penalty-rate history
from the officials the NHL lists on every finished game.

The crew factor multiplies a game's projected power-play time: the two referees' penalties called per
game against the league's, each shrunk toward 1.00 by sample size, averaged, and capped.
"""
import html as html_lib
import re
from datetime import datetime, timezone

import pandas as pd

from common.http import get
from nhl import ids

SITE = "https://scoutingtherefs.com"
_POST = re.compile(r'href="(https://scoutingtherefs\.com/\d{4}/\d{2}/\d+/[^"]*nhl-referees-and-lines[^"]*-(\d{1,2})-(\d{1,2})-(\d{2})/?)"')
_GAME = re.compile(r"<h1[^>]*>\s*(?:<strong>)?\s*([^<]+?)\s+at\s+([^<]+?)\s*<br", re.I)
_NAME = re.compile(r"<strong>\s*([^<#]+?)\s*#\s*\d+\s*</strong>")


def find_post(index_html: str, date_et: str) -> str | None:
    """The 'Tonight's NHL Referees and Linespersons' post for one date, from the site's front page."""
    y, m, d = date_et.split("-")
    for url, mm, dd, yy in _POST.findall(index_html):
        if (int(mm), int(dd), yy) == (int(m), int(d), y[2:]):
            return url
    return None


def parse_post(post_html: str, date_et: str, known_at: str | None = None) -> list[dict]:
    known_at = known_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    heads = list(_GAME.finditer(post_html))
    for i, h in enumerate(heads):
        away, home = ids.team(html_lib.unescape(h.group(1))), ids.team(html_lib.unescape(h.group(2)))
        if not home or not away:
            continue
        block = post_html[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(post_html)]
        cut = re.search(r"LINES(?:PERSONS|MEN)", block)
        parts = (("referee", block[:cut.start()] if cut else block), ("linesperson", block[cut.start():] if cut else ""))
        seen = set()
        for role, text in parts:
            for name in _NAME.findall(text):
                if name in seen:                      # each official is named again above his season stats
                    continue
                seen.add(name)
                rows.append({"date_et": date_et, "away": away, "home": home, "name": html_lib.unescape(name).strip(),
                             "role": role, "known_at": known_at})
    return rows


def assignments(date_et: str, root, cfg) -> list[dict]:
    kw = dict(min_interval=cfg["sources"]["min_interval"]["scoutingtherefs.com"], retries=cfg["sources"]["retries"],
              max_age=cfg["sources"]["gameday_max_age_sec"])
    index, _ = get(SITE + "/", root, **kw)
    url = find_post(index.decode("utf8", "replace"), date_et)
    if not url:
        return []
    body, at = get(url, root, **kw)
    return parse_post(body.decode("utf8", "replace"), date_et, at)


# ------------------------------------------------------------------ penalty-rate history
def ref_rates(officials: pd.DataFrame, team_game: pd.DataFrame, cfg) -> pd.DataFrame:
    """Per referee: games worked, penalties called per game (both teams), and the shrunk ratio to the league.
    Pass only rows known before the game being priced."""
    pens = team_game.groupby("game_id").pen_taken.sum().rename("pens")
    if pens.empty:
        return pd.DataFrame(columns=["name", "games", "pens_pg", "league_pg", "factor"])
    league = float(pens.mean())
    o = officials[officials.role == "referee"].merge(pens, on="game_id")
    g = o.groupby("name").pens.agg(games="count", pens_pg="mean").reset_index()
    k = cfg["refs"]["prior_games"]
    g["league_pg"] = league
    g["factor"] = 1 + (g.pens_pg / league - 1) * g.games / (g.games + k)
    return g


def crew_factor(names: list[str], rates: pd.DataFrame, cfg) -> dict:
    """The power-play multiplier for a crew, with what it is made of. Unknown referees count as league average."""
    by = {ids.norm(r.name): r for r in rates.itertuples()}
    parts = []
    for n in names:
        r = by.get(ids.norm(n))
        parts.append({"name": n, "games": int(r.games) if r is not None else 0, "factor": float(r.factor) if r is not None else 1.0})
    cap = cfg["refs"]["factor_cap"]
    raw = sum(p["factor"] for p in parts) / len(parts) if parts else 1.0
    return {"factor": min(1 + cap, max(1 - cap, raw)), "referees": parts}
