"""Smaller pulls: referee assignments, ESPN injury notes, ESPN market lines, pbpstats snapshots."""
import html
import json
import re
from datetime import datetime, timezone

from common.http import FetchError, get
from nba.config import CONFIG
from nba.store import RAW, upsert

GAP = CONFIG["min_interval"]


def referee_assignments(max_age=900) -> list[dict]:
    """Tonight's crews from official.nba.com. The page shows today only, so it is captured every day."""
    body, at = get("https://official.nba.com/referee-assignments/", RAW, min_interval=GAP["official.nba.com"],
                   max_age=max_age, tag=datetime.now(timezone.utc).strftime("%Y%m%d"))
    t = body.decode("utf8", "ignore")
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (20\d\d)", t)
    if not m:
        return []
    day = datetime.strptime(" ".join(m.groups()), "%B %d %Y").date().isoformat()
    nba = t.split("G League")[0] if "G League" in t else t
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", nba, flags=re.S):
        cells = [html.unescape(re.sub("<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
        if len(cells) >= 4 and "@" in cells[0]:
            for role, name in zip(("crew_chief", "referee", "umpire"), cells[1:4]):
                name = re.sub(r"\s*\(#\d+\)", "", name).strip()
                if name:
                    rows.append({"date_et": day, "matchup": cells[0], "name": name, "role": role, "known_at": at})
    return rows


def espn_injury_notes(idmap, max_age=600) -> dict:
    """player_id -> latest ESPN note (free text). Used only to spot stated minutes restrictions."""
    body, _ = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries", RAW,
                  min_interval=GAP["site.api.espn.com"], max_age=max_age, tag=datetime.now(timezone.utc).strftime("%Y%m%d%H"))
    out = {}
    for t in json.loads(body).get("injuries", []):
        tid = idmap.team(t.get("displayName", ""), "espn_injuries")
        for i in t.get("injuries", []):
            pid = idmap.player(i["athlete"]["displayName"], [tid] if tid else None, "espn_injuries")
            if pid:
                out[pid] = " ".join(x for x in (i.get("shortComment"), i.get("longComment")) if x)
    return out


def espn_market_line(summary: dict, game_id: str, known_at: str) -> dict | None:
    """Spread, total and moneyline that ESPN shows before a game (DraftKings). ESPN drops these
    once a game is old, so they only exist for games captured on the day."""
    pc = summary.get("pickcenter") or []
    if not pc:
        return None
    p = pc[0]
    if p.get("spread") is None and p.get("overUnder") is None:
        return None
    return {"game_id": game_id, "known_at": known_at, "provider": "espn:" + (p.get("provider") or {}).get("name", "?"),
            "spread_home": p.get("spread"), "total": p.get("overUnder"),
            "ml_home": (p.get("homeTeamOdds") or {}).get("moneyLine"), "ml_away": (p.get("awayTeamOdds") or {}).get("moneyLine")}


def pbpstats_snapshot(con, season: str, to_date: str) -> int:
    """Possession-level team and player totals up to `to_date`, kept as dated snapshots.
    Stored for later use; the models do not read these yet (see docs/nba_data_health.md)."""
    con.execute("CREATE TABLE IF NOT EXISTS pbp_snapshots (snapshot_date TEXT, kind TEXT, entity_id TEXT, name TEXT, "
                "team TEXT, data TEXT, known_at TEXT, PRIMARY KEY (snapshot_date, kind, entity_id))")
    n = 0
    for kind in ("Team", "Opponent", "Player", "Lineup"):
        url = (f"https://api.pbpstats.com/get-totals/nba?Season={season}&SeasonType=Regular%20Season&Type={kind}"
               f"&ToDate={to_date}")
        try:
            body, at = get(url, RAW, min_interval=GAP["api.pbpstats.com"], timeout=90)
        except FetchError as e:
            print(f"  pbpstats {kind}: {e}")
            continue
        rows = [{"snapshot_date": to_date, "kind": kind, "entity_id": str(r.get("EntityId")), "name": r.get("Name"),
                 "team": r.get("TeamAbbreviation"), "data": json.dumps(r), "known_at": at}
                for r in json.loads(body).get("multi_row_table_data", [])]
        n += upsert(con, "pbp_snapshots", rows)
    return n


OU_TYPES = {"pts": "Total Points", "reb": "Total Rebounds", "ast": "Total Assists", "fg3m": "Total 3-Point Field Goals"}


def _implied(american: float) -> float:
    return 100 / (american + 100) if american > 0 else -american / (-american + 100)


def _ladder_median(ladder: list) -> float:
    """The count at which a ladder's price crosses a coin flip (the book's own idea of the player's median)."""
    pts = sorted((r, _implied(px)) for r, px in ladder)
    for (r0, p0), (r1, p1) in zip(pts, pts[1:]):
        if p0 >= 0.5 > p1:
            return r0 + (p0 - 0.5) / max(p0 - p1, 1e-9) * (r1 - r0) - 0.5
    return pts[0][0] - 1.0 if pts[0][1] < 0.5 else pts[-1][0] + 0.5


def choose_ladder(rungs: list, ou_line: float | None, need_line: bool = True) -> tuple[list, str]:
    """`rungs` is one player's rows for one market, as (rung, price). The feed sometimes mixes a second,
    different market into the same name, so no rung is trusted on its own. Each one must fit the player's
    full-game over/under line: clearly likely when well under the line, clearly unlikely when well over it,
    and getting longer as the rung rises. Rungs that do not fit are dropped. With no line, nothing is used."""
    if ou_line is None:
        return [], "no over/under line to confirm the ladder"
    ok = {}
    for r, px in rungs:
        p, gap = _implied(px), (r - 0.5) - ou_line                 # gap < 0: rung is under the line
        if gap <= -3 and p < 0.72: continue
        if gap <= -1 and p < 0.52: continue
        if gap >= 1 and p > 0.56: continue
        if gap >= 3 and p > 0.38: continue
        if r not in ok or abs(p - (0.5 - 0.1 * gap)) < abs(_implied(ok[r]) - (0.5 - 0.1 * gap)):
            ok[r] = px
    below = sorted((r for r in ok if r - 0.5 <= ou_line), reverse=True)
    above = sorted(r for r in ok if r - 0.5 > ou_line)
    keep, last = [], 0.0
    for r in below:                                               # walking down from the line: chance must not fall
        p = _implied(ok[r])
        if p >= last - 1e-9:
            keep.append(r); last = p
    last = 1.0
    for r in above:                                               # walking up from the line: chance must not rise
        p = _implied(ok[r])
        if p <= last + 1e-9:
            keep.append(r); last = p
    out = [(r, ok[r]) for r in sorted(keep)]
    return out, ("" if out else "no rung fits the over/under line")


def espn_draftkings_props(game_id: str, names: dict, cfg=CONFIG, max_age=240) -> tuple[list[dict], list[str]]:
    """DraftKings milestone ladders (points, rebounds, assists, threes) for one game, from ESPN's odds API.

    Each row is a rung DraftKings lists ("15+" is stored as over 14.5) with its price. Players come with
    ESPN ids, which are this module's own ids, so no name matching is involved. ESPN's over/under rows do
    not say which price is the over, so they are used only for their line, to confirm which ladder is the
    full-game one. Returns (rows, problems)."""
    base = (f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{game_id}/competitions/{game_id}"
            f"/odds/100/propBets?lang=en&region=us&limit=1000")
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")[:-1]          # a fresh copy every ten minutes
    raw, ou, page, pages, at = {}, {}, 1, 1, None
    ou_names = {v: k for k, v in OU_TYPES.items()}
    while page <= pages:
        body, at = get(f"{base}&page={page}", RAW, min_interval=GAP["sports.core.api.espn.com"], max_age=max_age, tag=tag)
        d = json.loads(body)
        pages = d.get("pageCount", 1)
        for it in d.get("items", []):
            tname = (it.get("type") or {}).get("name")
            a = re.search(r"/athletes/(\d+)", (it.get("athlete") or {}).get("$ref", ""))
            total = ((it.get("odds") or {}).get("total") or {}).get("value", "")
            if not a:
                continue
            pid = a.group(1)
            if tname in ou_names:
                try:
                    ou[(pid, ou_names[tname])] = float(total)
                except (TypeError, ValueError):
                    pass
                continue
            market = cfg["espn_dk_markets"].get(tname)
            m = re.match(r"^(\d+)\+$", str(total))
            price = ((it.get("odds") or {}).get("american") or {}).get("value")
            if not (market and m and price):
                continue
            try:
                px = float(str(price).replace("+", "").replace("EVEN", "100"))
            except ValueError:
                continue
            if abs(px) < 100:
                continue
            raw.setdefault((pid, market), []).append((int(m.group(1)), px))
        page += 1
    rows, problems = [], []
    for (pid, market), rungs in raw.items():
        ladder, why = choose_ladder(rungs, ou.get((pid, market)))
        if why:
            problems.append(f"{names.get(pid, pid)} {market}: {why}; not used")
        for r, px in ladder:
            rows.append({"known_at": at, "source": "espn-core", "book": "draftkings", "game_id": game_id, "market": market,
                         "player_id": pid, "player_name": names.get(pid, pid), "side": "over", "line": r - 0.5,
                         "price": px, "is_close": 0})
    return rows, problems
