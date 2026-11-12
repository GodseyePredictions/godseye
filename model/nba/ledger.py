"""The record of everything the module says and what happened: projections, legs, tickets, prices, results.

Append-only and timestamped (standing rule 9). A ticket marked as placed is locked: its legs, prices and
probabilities can no longer be changed, only graded. The site reads these tables; see docs/nba_schema.md.
"""
import json
import uuid
from datetime import datetime, timezone

from nba.store import upsert

SCHEMA = """
CREATE TABLE IF NOT EXISTS nba_runs (run_id TEXT PRIMARY KEY, run_at TEXT, kind TEXT, slate_date TEXT, n_sims INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS nba_game_cards (run_id TEXT, game_id TEXT, run_at TEXT, matchup TEXT, card_json TEXT, card_text TEXT,
  PRIMARY KEY (run_id, game_id));
CREATE TABLE IF NOT EXISTS nba_projections (
  run_id TEXT, run_at TEXT, game_id TEXT, player_id TEXT, name TEXT, team_id TEXT, status TEXT, role TEXT, role_change TEXT,
  p_play REAL, min_mean REAL, min_p10 REAL, min_p50 REAL, min_p90 REAL, pts REAL, reb REAL, ast REAL, fg3m REAL, stl REAL, blk REAL,
  exp_fg_pct REAL, base_fg_pct REAL, exp_3p_pct REAL, base_3p_pct REAL, gate_pts INTEGER, gate_fg3m INTEGER,
  blowout_exposure REAL, adjustments TEXT, inout_notes TEXT,
  act_min REAL, act_pts REAL, act_reb REAL, act_ast REAL, act_fg3m REAL, act_stl REAL, act_blk REAL, graded_at TEXT,
  PRIMARY KEY (run_id, game_id, player_id));
CREATE TABLE IF NOT EXISTS nba_legs (
  leg_id TEXT, run_id TEXT, run_at TEXT, game_id TEXT, kind TEXT, player_id TEXT, team_id TEXT, label TEXT, market TEXT,
  line REAL, side TEXT, model_prob REAL, p_blowout REAL, p_close REAL, book TEXT, price REAL, price_seen_at TEXT,
  closing_price REAL, gate_ok INTEGER, sgp_eligible INTEGER, why_not TEXT, reason TEXT,
  actual REAL, result TEXT, graded_at TEXT, PRIMARY KEY (run_id, leg_id));
CREATE TABLE IF NOT EXISTS nba_tickets (
  ticket_id TEXT PRIMARY KEY, run_id TEXT, run_at TEXT, game_id TEXT, type TEXT, leg_ids TEXT, slip_json TEXT,
  joint_prob REAL, book_price REAL, price_is_estimate INTEGER, fair_price REAL, ev REAL,
  status TEXT, placed_at TEXT, stake REAL, locked INTEGER DEFAULT 0, result TEXT, graded_at TEXT, miss_causes TEXT);
CREATE TABLE IF NOT EXISTS nba_report_cards (slate_date TEXT PRIMARY KEY, made_at TEXT, card_json TEXT, card_text TEXT);
CREATE TABLE IF NOT EXISTS nba_status_changes (seen_at TEXT, game_id TEXT, player_id TEXT, name TEXT, from_status TEXT,
  to_status TEXT, projections_changed TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init(con):
    con.executescript(SCHEMA)


def new_run(con, kind: str, slate_date: str, n_sims: int, note: str = "") -> tuple[str, str]:
    init(con)
    run_id, at = uuid.uuid4().hex[:12], now()
    upsert(con, "nba_runs", [{"run_id": run_id, "run_at": at, "kind": kind, "slate_date": slate_date, "n_sims": n_sims, "note": note}])
    return run_id, at


def save_game(con, run_id, run_at, game_id, card: dict, text: str, proj_rows: list, legs: list, built: dict, eligibility) -> list:
    upsert(con, "nba_game_cards", [{"run_id": run_id, "game_id": game_id, "run_at": run_at, "matchup": card["matchup"],
                                    "card_json": json.dumps(card), "card_text": text}])
    upsert(con, "nba_projections", [{"run_id": run_id, "run_at": run_at, **r} for r in proj_rows])
    rows = []
    for l in legs:
        ok, why = eligibility(l)
        rows.append({"leg_id": l["id"], "run_id": run_id, "run_at": run_at, "game_id": game_id, "kind": l["kind"],
                     "player_id": l["player_id"], "team_id": l.get("team_id"), "label": l["label"], "market": l["market"],
                     "line": l["line"], "side": l["side"], "model_prob": l["p"], "p_blowout": l["p_blowout"], "p_close": l["p_close"],
                     "book": l["book"], "price": l["price"], "price_seen_at": l["price_seen_at"], "closing_price": None,
                     "gate_ok": int(l["gate_ok"]), "sgp_eligible": int(ok), "why_not": why, "reason": l.get("reason")})
    upsert(con, "nba_legs", rows)
    ids = []
    for t in built["tickets"]:
        tid = uuid.uuid4().hex[:12]
        ids.append(tid)
        upsert(con, "nba_tickets", [{
            "ticket_id": tid, "run_id": run_id, "run_at": run_at, "game_id": game_id, "type": t["type"],
            "leg_ids": json.dumps([l["id"] for l in t["legs"]]),
            "slip_json": json.dumps([{"description": l["label"], "odds": l["price"], "game": card["matchup"]} for l in t["legs"]]),
            "joint_prob": t["joint"], "book_price": t["book_price"], "price_is_estimate": int(bool(t.get("price_is_estimate"))),
            "fair_price": t["fair_price"], "ev": t["ev"], "status": "proposed", "placed_at": None, "stake": None, "locked": 0}])
    return ids


def place(con, ticket_id: str, stake: float | None = None, book_price: float | None = None) -> dict:
    """Mark a ticket as placed: stamp the time, optionally record the real price taken, and lock it."""
    init(con)
    row = con.execute("SELECT locked, status, type FROM nba_tickets WHERE ticket_id=?", [ticket_id]).fetchone()
    if row is None:
        return {"ok": False, "message": f"no ticket {ticket_id}"}
    if str(row[2]).startswith("preview_") and book_price is None:
        return {"ok": False, "message": "this is a model-only preview ticket: give the book's real price to place it "
                                        "(python3 -m nba.run_slate place TICKET_ID STAKE PRICE)"}
    if row[0]:
        return {"ok": False, "message": f"ticket {ticket_id} is already placed and locked"}
    at = now()
    if book_price is not None:
        con.execute("UPDATE nba_tickets SET book_price=?, price_is_estimate=0 WHERE ticket_id=?", [book_price, ticket_id])
    con.execute("UPDATE nba_tickets SET status='placed', placed_at=?, stake=?, locked=1 WHERE ticket_id=?", [at, stake, ticket_id])
    con.commit()
    return {"ok": True, "message": f"ticket {ticket_id} placed and locked at {at}"}


def supersede(con, game_id: str) -> int:
    """When a game is re-run, earlier proposed (not placed) tickets for it are retired. Placed tickets never change."""
    init(con)
    cur = con.execute("UPDATE nba_tickets SET status='superseded' WHERE game_id=? AND status='proposed' AND locked=0", [game_id])
    con.commit()
    return cur.rowcount
