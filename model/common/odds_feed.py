"""Odds in: The Odds API, or a pasted bet365 sheet. Both produce the same rows.

A row is one price the book actually offers: market, player (or team), side, line, price, time seen.
A milestone rung such as "20+" is stored as over 19.5, so ladders and over/under lines share one
shape. Nothing here invents a rung: if the book did not list it, there is no row.

The Odds API part follows its published v4 format. It has not been run against the live service
from this project yet (no key was available when it was written), so treat it as untested until
`python3 -m nba.refresh gameday` has been run once with ODDS_API_KEY set.
"""
import csv
import io
import json
import re
from datetime import datetime, timezone

from common.http import get
from common.odds_math import parse_price

API = "https://api.the-odds-api.com/v4/sports/basketball_nba"
PLAYER_MARKETS = {"pts": "player_points", "reb": "player_rebounds", "ast": "player_assists", "fg3m": "player_threes",
                  "stl": "player_steals", "blk": "player_blocks", "pra": "player_points_rebounds_assists",
                  "pr": "player_points_rebounds", "pa": "player_points_assists", "dd": "player_double_double",
                  "td": "player_triple_double"}
GAME_MARKETS = {"ml": "h2h", "spread": "spreads", "total": "totals", "alt_spread": "alternate_spreads",
                "alt_total": "alternate_totals"}
API_TO_OURS = {v: k for k, v in PLAYER_MARKETS.items()} | {v + "_alternate": k for k, v in PLAYER_MARKETS.items()} | \
              {"h2h": "ml", "spreads": "spread", "totals": "total", "alternate_spreads": "spread", "alternate_totals": "total"}
ALIASES = {"points": "pts", "pts": "pts", "rebounds": "reb", "reb": "reb", "assists": "ast", "ast": "ast",
           "threes": "fg3m", "3 pointers made": "fg3m", "3-pointers made": "fg3m", "threes made": "fg3m", "3pm": "fg3m",
           "fg3m": "fg3m", "steals": "stl", "stl": "stl", "blocks": "blk", "blk": "blk",
           "points rebounds assists": "pra", "points + rebounds + assists": "pra", "pra": "pra", "pts+reb+ast": "pra",
           "points + rebounds": "pr", "points rebounds": "pr", "pr": "pr", "pts+reb": "pr",
           "points + assists": "pa", "points assists": "pa", "pa": "pa", "pts+ast": "pa",
           "double double": "dd", "double-double": "dd", "dd": "dd", "triple double": "td", "triple-double": "td", "td": "td",
           "moneyline": "ml", "money line": "ml", "ml": "ml", "to win": "ml", "spread": "spread", "alternative spread": "spread",
           "alt spread": "spread", "handicap": "spread", "total": "total", "game total": "total",
           "alternative total": "total", "alt total": "total"}
PLAYER_KEYS = set(PLAYER_MARKETS)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ The Odds API
def api_events(key: str, raw_root, max_age=300) -> list[dict]:
    body, _ = get(f"{API}/events?apiKey={key}", raw_root, max_age=max_age, redact=key)
    return json.loads(body)


def api_event_odds(key: str, event_id: str, raw_root, markets: list[str], regions: str, book: str | None,
                   snapshot_tag: str) -> tuple[dict, str]:
    url = f"{API}/events/{event_id}/odds?apiKey={key}&regions={regions}&markets={','.join(markets)}&oddsFormat=american"
    if book:
        url += f"&bookmakers={book}"
    body, at = get(url, raw_root, tag=snapshot_tag, redact=key)   # tag = one cached copy per snapshot time
    return json.loads(body), at


def all_api_markets() -> list[str]:
    props = list(PLAYER_MARKETS.values())
    alts = [m + "_alternate" for m in props if m not in ("player_double_double", "player_triple_double")]
    return list(GAME_MARKETS.values()) + props + alts


def rows_from_api(event: dict, known_at: str, book: str | None = None) -> list[dict]:
    """Flatten one event's odds. Game id and player ids are filled in later by the ID map."""
    rows = []
    for bk in event.get("bookmakers", []):
        if book and book not in bk["key"]:
            continue
        for mk in bk.get("markets", []):
            ours = API_TO_OURS.get(mk["key"])
            if not ours:
                continue
            for o in mk.get("outcomes", []):
                name, desc, point = o.get("name", ""), o.get("description"), o.get("point")
                if ours in PLAYER_KEYS:
                    side = "yes" if name.lower() == "yes" else name.lower()
                    if side == "no" or side not in ("over", "under", "yes"):
                        continue
                    player, line = desc, (0.5 if ours in ("dd", "td") else point)
                elif ours == "total":
                    player, side, line = "", name.lower(), point
                else:
                    player, side, line = name, "team", (point if ours == "spread" else 0.0)
                if line is None:
                    continue
                rows.append({"known_at": known_at, "source": "the-odds-api", "book": bk["key"], "game_id": None,
                             "market": ours, "player_id": None, "player_name": player, "side": side,
                             "line": float(line), "price": float(o["price"]), "is_close": 0,
                             "_home": event.get("home_team"), "_away": event.get("away_team"),
                             "_commence": event.get("commence_time")})
    return rows


# ------------------------------------------------------------------ pasted bet365 sheet
RUNG = re.compile(r"^(\d+)\s*\+$")
LINE = re.compile(r"^(o|over|u|under)?\s*([+-]?\d+(?:\.\d+)?)$", re.I)


def read_csv(text: str, known_at: str | None = None, book: str = "bet365") -> tuple[list[dict], list[str]]:
    """Validate a pasted sheet. Needed columns: player, market, a rung or line, price.
    Optional: side (over/under), game. Returns (good rows, rejection messages)."""
    known_at = known_at or now_utc()
    good, bad = [], []
    rd = csv.DictReader(io.StringIO(text.strip()))
    cols = {c.strip().lower(): c for c in (rd.fieldnames or [])}
    line_col = next((cols[c] for c in ("rung or line", "rung", "line", "rung_or_line") if c in cols), None)
    missing = [c for c in ("player", "market", "price") if c not in cols] + ([] if line_col else ["rung or line"])
    if missing:
        return [], [f"sheet rejected: missing column(s) {', '.join(missing)}"]
    seen = set()
    for n, r in enumerate(rd, start=2):
        player = (r[cols["player"]] or "").strip()
        mk_raw = (r[cols["market"]] or "").strip()
        market = ALIASES.get(re.sub(r"\s+", " ", mk_raw.lower()))
        raw_line = (r[line_col] or "").strip()
        side = (r.get(cols.get("side", ""), "") or "").strip().lower()
        if not market:
            bad.append(f"row {n}: market '{mk_raw}' is not one this module handles"); continue
        try:
            price = parse_price(r[cols["price"]])
        except (ValueError, ZeroDivisionError, TypeError):
            bad.append(f"row {n}: price '{r[cols['price']]}' is not a valid price"); continue
        if market in PLAYER_KEYS and not player:
            bad.append(f"row {n}: player is blank"); continue
        if market in ("dd", "td"):
            line, side = 0.5, "yes"
        elif market == "ml":
            if not player:
                bad.append(f"row {n}: moneyline needs the team in the player column"); continue
            line, side = 0.0, "team"
        else:
            m = RUNG.match(raw_line)
            if m:
                if market in ("spread", "total"):
                    bad.append(f"row {n}: '{raw_line}' is a milestone rung; {market} needs a line such as 220.5"); continue
                line, side = int(m.group(1)) - 0.5, "over"
            else:
                m = LINE.match(raw_line)
                if not m:
                    bad.append(f"row {n}: '{raw_line}' is neither a rung (20+) nor a line (24.5)"); continue
                line = float(m.group(2))
                if market == "spread":
                    if not player:
                        bad.append(f"row {n}: spread needs the team in the player column"); continue
                    side = "team"
                else:
                    word = (m.group(1) or side or "").lower()
                    side = {"o": "over", "over": "over", "u": "under", "under": "under"}.get(word)
                    if not side:
                        bad.append(f"row {n}: line {raw_line} needs over or under"); continue
                    if line < 0 or (line * 2) % 1:
                        bad.append(f"row {n}: line {raw_line} is not a whole or half number"); continue
        key = (player.lower(), market, side, line)
        if key in seen:
            bad.append(f"row {n}: duplicate of an earlier row ({player} {market} {raw_line})"); continue
        seen.add(key)
        good.append({"known_at": known_at, "source": "csv", "book": book, "game_id": None, "market": market,
                     "player_id": None, "player_name": player, "side": side, "line": float(line), "price": price,
                     "is_close": 0, "_game": (r.get(cols.get("game", ""), "") or "").strip()})
    return good, bad


def resolve(rows: list[dict], idmap, game_id: str | None = None, team_ids=None) -> tuple[list[dict], list[str]]:
    """Attach game and player ids. Rows whose player cannot be matched exactly are dropped and reported."""
    out, bad = [], []
    for r in rows:
        r = dict(r)
        gid, teams = game_id, team_ids
        if gid is None and r.get("_home"):
            day = (datetime.fromisoformat(r["_commence"].replace("Z", "+00:00")).timestamp() - 5 * 3600)
            gid = idmap.game(r["_home"], r["_away"], datetime.fromtimestamp(day, timezone.utc).date().isoformat(), r["source"])
            teams = [idmap.team(r["_home"], r["source"]), idmap.team(r["_away"], r["source"])]
        if gid is None:
            bad.append(f"{r['player_name'] or r['market']}: game not found on the schedule"); continue
        r["game_id"] = gid
        if r["market"] in PLAYER_KEYS:
            r["player_id"] = idmap.player(r["player_name"], teams, r["source"])
            if r["player_id"] is None:
                bad.append(f"{r['player_name']}: no exact player match, sent to the review file"); continue
        elif r["side"] == "team":
            r["player_id"] = idmap.team(r["player_name"], r["source"])
            if r["player_id"] is None or (teams and r["player_id"] not in teams):
                bad.append(f"{r['player_name']}: not a team in this game"); continue
        out.append({k: v for k, v in r.items() if not k.startswith("_")})
    return out, bad


def mark_closing(con, game_id: str, tip_utc: str) -> int:
    """Flag the last price seen before tip-off for every market of a game as its closing price."""
    con.execute("UPDATE odds SET is_close=0 WHERE game_id=?", [game_id])
    cur = con.execute("""
        UPDATE odds SET is_close=1 WHERE game_id=? AND known_at < ? AND known_at = (
          SELECT MAX(o2.known_at) FROM odds o2 WHERE o2.game_id=odds.game_id AND o2.source=odds.source
            AND o2.book=odds.book AND o2.market=odds.market AND o2.player_name=odds.player_name
            AND o2.side=odds.side AND o2.line=odds.line AND o2.known_at < ?)""", [game_id, tip_utc, tip_utc])
    con.commit()
    return cur.rowcount
