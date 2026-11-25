"""Daily Faceoff: tonight's starting goalies, line combinations, power-play units and injured reserve.

Both pages carry their data as JSON inside the page (the __NEXT_DATA__ block), which is what is read here.
A goalie counts as confirmed only when Daily Faceoff labels him "Confirmed"; "Likely" and "Unconfirmed"
are stored as they are so the goalie gate can refuse them.
"""
import json
import re
from datetime import datetime, timezone

from common.http import get
from nhl import ids

SITE = "https://www.dailyfaceoff.com"
_NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class PageChanged(Exception):
    """The page no longer carries the data block this parser reads."""


def _page_props(html: str) -> dict:
    m = _NEXT.search(html)
    if not m:
        raise PageChanged("no __NEXT_DATA__ block")
    return json.loads(m.group(1))["props"]["pageProps"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_goalies(html: str, cfg, known_at: str | None = None) -> list[dict]:
    props = _page_props(html)
    known_at = known_at or _now()
    confirmed = set(cfg["sources"]["goalie_confirmed_labels"])
    rows = []
    for g in props.get("data") or []:
        for side, other in (("home", "away"), ("away", "home")):
            team = ids.team(g.get(f"{side}TeamAbbreviation") or "") or ids.team(g.get(f"{side}TeamName") or "")
            opp = ids.team(g.get(f"{other}TeamAbbreviation") or "") or ids.team(g.get(f"{other}TeamName") or "")
            if not team:
                continue
            status = g.get(f"{side}NewsStrengthName") or "Unconfirmed"
            rows.append({"date_et": props.get("date") or (g.get("date") or "")[:10], "team": team, "opp": opp,
                         "is_home": int(side == "home"), "goalie": g.get(f"{side}GoalieName"), "player_id": None,
                         "status": status, "confirmed": int(status in confirmed and bool(g.get(f"{side}GoalieName"))),
                         "source_time": g.get(f"{side}NewsCreatedAt"), "known_at": known_at})
    return rows


def parse_lines(html: str, known_at: str | None = None) -> list[dict]:
    """One row per listed slot: forwards f1-f4, defence d1-d3, goalies g, pp1/pp2, pk1/pk2, injured reserve ir."""
    comb = _page_props(html).get("combinations") or {}
    team = ids.team(comb.get("teamAbbreviation") or "") or ids.team(comb.get("teamName") or "")
    if not team or not comb.get("players"):
        raise PageChanged("no line combinations on the page")
    known_at = known_at or _now()
    return [{"team": team, "known_at": known_at, "source_time": comb.get("updatedAt"), "player": p.get("name"), "player_id": None,
             "unit": p.get("groupIdentifier"), "slot": p.get("positionIdentifier"), "category": p.get("categoryIdentifier"),
             "injury": p.get("injuryStatus"), "gtd": int(bool(p.get("gameTimeDecision")))} for p in comb["players"]]


def _get(url, root, cfg, tag=""):
    body, at = get(url, root, min_interval=cfg["sources"]["min_interval"]["www.dailyfaceoff.com"],
                   retries=cfg["sources"]["retries"], max_age=cfg["sources"]["gameday_max_age_sec"], tag=tag)
    return body.decode("utf8", "replace"), at


def goalies(date_et: str, root, cfg) -> list[dict]:
    html, at = _get(f"{SITE}/starting-goalies/{date_et}", root, cfg)
    return parse_goalies(html, cfg, at)


def lines(team: str, root, cfg) -> list[dict]:
    html, at = _get(f"{SITE}/teams/{ids.slug(team)}/line-combinations", root, cfg)
    return parse_lines(html, at)


def attach_ids(rows: list[dict], index: ids.PlayerIndex, name_key: str) -> list[dict]:
    for r in rows:
        if r.get(name_key):
            r["player_id"] = index.find(r[name_key], r["team"])
    return rows
