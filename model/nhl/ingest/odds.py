"""Odds in for the NHL: The Odds API (sport key icehockey_nhl) and the hand-entered bet365 ladder sheet.

Rows have the same shape as the shared odds feed (common/odds_feed.py) and reuse its HTTP client and
price parser. A milestone rung such as "3+" shots is stored as over 2.5, so ladders and over/under
lines share one shape. Nothing here invents a rung: if the book did not list it, there is no row.

Market keys follow The Odds API's published v4 list. This module has not been run against the live
service from this project (no ODDS_API_KEY was available when it was written), so treat the API half as
untested until a keyed game-day run has been checked. The Odds API lists no player-hits market for the
NHL: hits ladders can only come from the bet365 sheet.
"""
import csv
import io
import json
import re
from datetime import datetime, timezone

from common.http import get
from common.odds_math import parse_price
from nhl import ids

API = "https://api.the-odds-api.com/v4/sports/icehockey_nhl"
PLAYER_MARKETS = {"sog": "player_shots_on_goal", "pts": "player_points", "ast": "player_assists", "goals": "player_goals",
                  "atg": "player_goal_scorer_anytime", "blk": "player_blocked_shots", "saves": "player_total_saves"}
GAME_MARKETS = {"ml": "h2h", "ml3": "h2h_3_way", "spread": "spreads", "total": "totals", "alt_spread": "alternate_spreads",
                "alt_total": "alternate_totals"}
NO_ALTERNATE = {"player_goal_scorer_anytime"}
API_TO_OURS = {v: k for k, v in PLAYER_MARKETS.items()} | {v + "_alternate": k for k, v in PLAYER_MARKETS.items()} | \
              {"h2h": "ml", "h2h_3_way": "ml3", "spreads": "spread", "totals": "total", "alternate_spreads": "spread",
               "alternate_totals": "total"}
ALIASES = {"shots on goal": "sog", "shots": "sog", "sog": "sog", "points": "pts", "pts": "pts", "assists": "ast", "ast": "ast",
           "goals": "goals", "anytime goal scorer": "atg", "anytime goalscorer": "atg", "anytime scorer": "atg", "atg": "atg",
           "hits": "hits", "blocked shots": "blk", "blocks": "blk", "blk": "blk", "saves": "saves", "goalie saves": "saves",
           "moneyline": "ml", "money line": "ml", "ml": "ml", "to win": "ml", "60 minute line": "ml3", "3-way": "ml3", "ml3": "ml3",
           "puck line": "spread", "spread": "spread", "alt puck line": "spread", "alternative puck line": "spread",
           "total": "total", "match total": "total", "game total": "total", "alt total": "total", "alternative total": "total"}
PLAYER_KEYS = set(PLAYER_MARKETS) | {"hits"}
RUNG = re.compile(r"^(\d+)\s*\+$")
LINE = re.compile(r"^(o|over|u|under)?\s*([+-]?\d+(?:\.\d+)?)$", re.I)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def all_api_markets() -> list[str]:
    props = list(PLAYER_MARKETS.values())
    return list(GAME_MARKETS.values()) + props + [m + "_alternate" for m in props if m not in NO_ALTERNATE]


def api_events(key: str, root, cfg, max_age=300) -> list[dict]:
    body, _ = get(f"{API}/events?apiKey={key}", root, max_age=max_age, redact=key,
                  min_interval=cfg["sources"]["min_interval"]["api.the-odds-api.com"])
    return json.loads(body)


def api_event_odds(key: str, event_id: str, root, cfg, snapshot_tag: str) -> tuple[dict, str]:
    url = (f"{API}/events/{event_id}/odds?apiKey={key}&regions={cfg['sources']['odds_regions']}"
           f"&markets={','.join(all_api_markets())}&oddsFormat=american&bookmakers={','.join(cfg['sources']['odds_books'])}")
    body, at = get(url, root, tag=snapshot_tag, redact=key, min_interval=cfg["sources"]["min_interval"]["api.the-odds-api.com"])
    return json.loads(body), at


def rows_from_api(event: dict, known_at: str) -> list[dict]:
    """Flatten one event's odds. Game and player ids are attached by `resolve`."""
    rows = []
    home, away = ids.team(event.get("home_team", "")), ids.team(event.get("away_team", ""))
    for bk in event.get("bookmakers", []):
        for mk in bk.get("markets", []):
            ours = API_TO_OURS.get(mk["key"])
            if not ours:
                continue
            for o in mk.get("outcomes", []):
                name, desc, point = o.get("name", ""), o.get("description"), o.get("point")
                if ours == "atg":
                    player, side, line = desc or name, "yes", 0.5
                elif ours in PLAYER_KEYS:
                    side = name.lower()
                    if side not in ("over", "under"):
                        continue
                    player, line = desc, point
                elif ours == "total":
                    player, side, line = "", name.lower(), point
                else:
                    player, side = ("Draw", "draw") if name.lower() == "draw" else (ids.team(name) or name, "team")
                    line = point if ours == "spread" else 0.0
                if line is None:
                    continue
                rows.append({"known_at": known_at, "source": "the-odds-api", "book": bk["key"], "game_id": None, "market": ours,
                             "player_id": None, "player_name": player, "side": side, "line": float(line),
                             "price": float(o["price"]), "is_close": 0, "_home": home, "_away": away,
                             "_commence": event.get("commence_time")})
    return rows


def read_csv(text: str, known_at: str | None = None, book: str = "bet365") -> tuple[list[dict], list[str]]:
    """Validate a bet365 ladder sheet. Columns: game (AWAY@HOME), player, market, rung or line, price; optional side.
    Returns (good rows, rejection messages). A bad row is rejected and reported, never repaired."""
    known_at = known_at or now_utc()
    good, bad, seen = [], [], set()
    rd = csv.DictReader(io.StringIO(text.strip()))
    cols = {c.strip().lower(): c for c in (rd.fieldnames or [])}
    line_col = next((cols[c] for c in ("rung or line", "rung", "line", "rung_or_line") if c in cols), None)
    missing = [c for c in ("game", "player", "market", "price") if c not in cols] + ([] if line_col else ["rung or line"])
    if missing:
        return [], [f"sheet rejected: missing column(s) {', '.join(missing)}"]
    for n, r in enumerate(rd, start=2):
        player = (r[cols["player"]] or "").strip()
        mk_raw = (r[cols["market"]] or "").strip()
        market = ALIASES.get(re.sub(r"\s+", " ", mk_raw.lower()))
        raw_line = (r[line_col] or "").strip()
        side = (r.get(cols.get("side", ""), "") or "").strip().lower()
        teams = [ids.team(t) for t in re.split(r"\s*(?:@| at | vs\.? )\s*", (r[cols["game"]] or "").strip())]
        if len(teams) != 2 or not all(teams):
            bad.append(f"row {n}: game '{r[cols['game']]}' is not AWAY@HOME with two NHL teams"); continue
        if not market:
            bad.append(f"row {n}: market '{mk_raw}' is not one the NHL engine handles"); continue
        try:
            price = parse_price(r[cols["price"]])
        except (ValueError, ZeroDivisionError, TypeError):
            bad.append(f"row {n}: price '{r[cols['price']]}' is not a valid price"); continue
        if market in PLAYER_KEYS and not player:
            bad.append(f"row {n}: player is blank"); continue
        if market == "atg":
            line, side = 0.5, "yes"
        elif market in ("ml", "ml3"):
            if player.lower() == "draw" and market == "ml3":
                line, side = 0.0, "draw"
            elif ids.team(player) in teams:
                player, line, side = ids.team(player), 0.0, "team"
            else:
                bad.append(f"row {n}: moneyline needs one of the game's teams in the player column"); continue
        else:
            m = RUNG.match(raw_line)
            if m:
                if market in ("spread", "total"):
                    bad.append(f"row {n}: '{raw_line}' is a milestone rung; {market} needs a line such as 5.5"); continue
                line, side = int(m.group(1)) - 0.5, "over"
            else:
                m = LINE.match(raw_line)
                if not m:
                    bad.append(f"row {n}: '{raw_line}' is neither a rung (3+) nor a line (2.5)"); continue
                line = float(m.group(2))
                if market == "spread":
                    if ids.team(player) not in teams:
                        bad.append(f"row {n}: puck line needs one of the game's teams in the player column"); continue
                    player, side = ids.team(player), "team"
                else:
                    side = {"o": "over", "over": "over", "u": "under", "under": "under"}.get((m.group(1) or side or "").lower())
                    if not side:
                        bad.append(f"row {n}: line {raw_line} needs over or under"); continue
                    if line < 0 or (line * 2) % 1:
                        bad.append(f"row {n}: line {raw_line} is not a whole or half number"); continue
        key = (tuple(teams), player.lower(), market, side, line)
        if key in seen:
            bad.append(f"row {n}: duplicate of an earlier row ({player} {market} {raw_line})"); continue
        seen.add(key)
        good.append({"known_at": known_at, "source": "csv", "book": book, "game_id": None, "market": market, "player_id": None,
                     "player_name": player, "side": side, "line": float(line), "price": price, "is_close": 0,
                     "_away": teams[0], "_home": teams[1], "_commence": None})
    return good, bad


def resolve(rows: list[dict], schedule: list[dict], index: ids.PlayerIndex, date_et: str | None = None) -> tuple[list[dict], list[str]]:
    """Attach game and player ids. A row whose game is not on the schedule, or whose player has no exact
    match on either team, is dropped and reported."""
    games = {}
    for g in schedule:
        games.setdefault((g["away"], g["home"]), []).append(g)
    out, bad = [], []
    for r in rows:
        r = dict(r)
        day = date_et
        if r.get("_commence"):
            t = datetime.fromisoformat(r["_commence"].replace("Z", "+00:00")).timestamp() - 5 * 3600
            day = datetime.fromtimestamp(t, timezone.utc).date().isoformat()
        cands = [g for g in games.get((r["_away"], r["_home"]), []) if not day or g["date_et"] == day]
        if len(cands) != 1:
            bad.append(f"{r['player_name'] or r['market']}: {r['_away']}@{r['_home']} is not on the schedule for {day}"); continue
        r["game_id"] = cands[0]["game_id"]
        if r["market"] in PLAYER_KEYS:
            r["player_id"] = index.find(r["player_name"], r["_home"]) or index.find(r["player_name"], r["_away"])
            if r["player_id"] is None:
                bad.append(f"{r['player_name']}: no exact player match"); continue
        out.append({k: v for k, v in r.items() if not k.startswith("_")})
    return out, bad
