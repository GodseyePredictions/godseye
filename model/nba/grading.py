"""Nightly grading: every projection, leg and ticket against the official box score, with a report card.

Each missed leg gets one cause tag, checked in this order:
  injury in game   the player left early (played under half his projected 10th-percentile minutes and under 12)
  blowout          the game met the blowout definition and the player lost minutes
  minutes miss     he played `minutes_miss` or more below his projected minutes for another reason
  shooting variance  minutes were there and so were the attempts (points and threes legs), the shots did not fall
  model error      none of the above: the projection itself was wrong
"""
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from common.odds_math import closing_line_value, to_decimal
from nba import ledger
from nba.config import CONFIG
from nba.player_sim import COMBOS


def _actual(pg_row, market):
    if market in COMBOS:
        return float(sum(pg_row[s] for s in COMBOS[market]))
    if market in ("dd", "td"):
        return float(sum(int(pg_row[s] >= 10) for s in ("pts", "reb", "ast", "stl", "blk")) >= (2 if market == "dd" else 3))
    return float(pg_row[market])


def cause(leg, proj, box, game, cfg=CONFIG) -> str:
    if proj is None or box is None:
        return "model error"
    q4_entry = sum(game[f"hq{q}"] - game[f"aq{q}"] for q in (1, 2, 3))
    blow = abs(q4_entry) >= cfg["blowout_q4_lead"] or max(game["max_lead_2h_home"], game["max_lead_2h_away"]) >= cfg["blowout_2h_lead"]
    short = proj["min_mean"] - box["min"]
    if box["min"] < 12 and box["min"] < 0.5 * proj["min_p10"]:
        return "injury in game"
    if blow and short >= cfg["minutes_miss"] / 2:
        return "blowout"
    if short >= cfg["minutes_miss"]:
        return "minutes miss"
    if leg["market"] in ("pts", "fg3m", "pra", "pr", "pa") and leg["side"] == "over":
        exp_fga = box["min"] * (proj.get("fga_per_min") or 0)
        if exp_fga and box["fga"] >= 0.85 * exp_fga:
            return "shooting variance"
        if not exp_fga and box["fga"] > 0 and box["fgm"] / box["fga"] < (proj.get("exp_fg_pct") or 0.45) - 0.08:
            return "shooting variance"
    return "model error"


def grade_date(con, date_et: str, cfg=CONFIG) -> dict:
    """Grade everything logged for games on `date_et` that have finished. Safe to run more than once."""
    ledger.init(con)
    games = pd.read_sql("SELECT * FROM games WHERE date_et=?", con, params=[date_et])
    if games.empty:
        return {"date": date_et, "message": "no finished games in the database for this date"}
    gids = tuple(games.game_id)
    q = ",".join("?" * len(gids))
    pg = pd.read_sql(f"SELECT * FROM player_games WHERE game_id IN ({q})", con, params=gids).set_index(["game_id", "player_id"])
    gi = games.set_index("game_id")
    at = ledger.now()
    # closing prices: the last price seen before tip for the same market, side and line
    close = pd.read_sql(f"SELECT game_id, market, player_name, player_id, side, line, price FROM odds WHERE is_close=1 AND game_id IN ({q})",
                        con, params=gids)
    ckey = {(r.game_id, r.market, r.player_id, r.side, r.line): r.price for r in close.itertuples()}
    proj = pd.read_sql(f"SELECT * FROM nba_projections WHERE game_id IN ({q})", con, params=gids)
    for r in proj.itertuples():
        k = (r.game_id, r.player_id)
        if k in pg.index and pg.loc[k, "min"] > 0:
            b = pg.loc[k]
            con.execute("UPDATE nba_projections SET act_min=?, act_pts=?, act_reb=?, act_ast=?, act_fg3m=?, act_stl=?, act_blk=?, graded_at=? "
                        "WHERE run_id=? AND game_id=? AND player_id=?",
                        [float(b["min"]), float(b.pts), float(b.reb), float(b.ast), float(b.fg3m), float(b.stl), float(b.blk),
                         at, r.run_id, r.game_id, r.player_id])
    pmap = {(r.run_id, r.game_id, r.player_id): r._asdict() for r in proj.itertuples()}
    legs = pd.read_sql(f"SELECT * FROM nba_legs WHERE game_id IN ({q})", con, params=gids)
    res, causes = {}, {}
    for l in legs.itertuples():
        g = gi.loc[l.game_id]
        if l.kind == "game":
            margin = g.home_pts - g.away_pts
            val = margin if l.team_id == g.home_id else -margin
            if l.market == "ml":
                actual, hit = val, val > 0
            elif l.market == "spread":
                actual, hit = val, (val + l.line > 0)
                if val + l.line == 0:
                    hit = None
            else:
                actual = g.home_pts + g.away_pts
                hit = None if actual == l.line else ((actual > l.line) if l.side == "over" else (actual < l.line))
            result = "push" if hit is None else ("won" if hit else "lost")
        else:
            k = (l.game_id, l.player_id)
            if k not in pg.index or pg.loc[k, "min"] <= 0:
                actual, result = None, "void"
            else:
                actual = _actual(pg.loc[k], l.market)
                hit = actual > l.line if l.side in ("over", "yes") else actual < l.line
                result = "won" if hit else "lost"
                if not hit:
                    p = pmap.get((l.run_id, l.game_id, l.player_id))
                    causes[(l.run_id, l.leg_id)] = cause({"market": l.market, "side": l.side}, p, pg.loc[k], g, cfg)
        cp = ckey.get((l.game_id, l.market, l.player_id if l.kind != "game" or l.market == "total" else l.team_id, l.side, l.line))
        res[(l.run_id, l.leg_id)] = result
        con.execute("UPDATE nba_legs SET actual=?, result=?, graded_at=?, closing_price=COALESCE(?, closing_price) WHERE run_id=? AND leg_id=?",
                    [None if actual is None else float(actual), result, at, None if cp is None else float(cp), l.run_id, l.leg_id])
    tickets = pd.read_sql(f"SELECT * FROM nba_tickets WHERE game_id IN ({q}) AND status IN ('proposed','placed')", con, params=gids)
    for t in tickets.itertuples():
        rs = [res.get((t.run_id, i), "void") for i in json.loads(t.leg_ids)]
        live = [r for r in rs if r not in ("void", "push")]
        result = "void" if not live else ("lost" if "lost" in rs else "won")
        cs = sorted({causes[(t.run_id, i)] for i in json.loads(t.leg_ids) if (t.run_id, i) in causes})
        con.execute("UPDATE nba_tickets SET result=?, graded_at=?, miss_causes=? WHERE ticket_id=?", [result, at, json.dumps(cs), t.ticket_id])
    con.commit()
    return report_card(con, date_et, cfg)


def running(con, cfg=CONFIG) -> dict:
    """Results to date from the ledger: calibration by market and by ticket type, and drift alerts.
    Uses the latest run per leg so a re-run game is not counted twice."""
    L = pd.read_sql("SELECT * FROM nba_legs WHERE result IN ('won','lost')", con)
    out = {"markets": [], "tickets": [], "alerts": []}
    if len(L):
        L = L.sort_values("run_at").drop_duplicates(["game_id", "leg_id"], keep="last")
        L["hit"] = (L.result == "won").astype(int)
        for m, d in L[L.model_prob >= cfg["sgp_leg_floor"]].groupby("market"):
            row = {"market": m, "legs": int(len(d)), "forecast": round(float(d.model_prob.mean()), 3), "hit_rate": round(float(d.hit.mean()), 3),
                   "too_small_to_trust": bool(len(d) < cfg["small_sample"])}
            out["markets"].append(row)
            if len(d) >= cfg["calibration_min_legs"] and abs(row["hit_rate"] - row["forecast"]) > cfg["calibration_tolerance"]:
                out["alerts"].append(f"{m}: legs forecast at {row['forecast']:.0%} are hitting {row['hit_rate']:.0%} over {len(d)} legs")
        priced = L[L.price.notna() & L.closing_price.notna()]
        if len(priced):
            clv = [closing_line_value(a, b) for a, b in zip(priced.price, priced.closing_price)]
            out["closing_line_value"] = {"legs": len(priced), "mean": round(float(np.mean(clv)), 4), "beat_close_share": round(float(np.mean(np.array(clv) > 0)), 3)}
    T = pd.read_sql("SELECT * FROM nba_tickets WHERE result IN ('won','lost')", con)
    for (ty, st), d in T.groupby(["type", "status"]):
        row = {"type": ty, "status": st, "tickets": int(len(d)), "forecast": round(float(d.joint_prob.mean()), 3),
               "hit_rate": round(float((d.result == "won").mean()), 3), "too_small_to_trust": bool(len(d) < cfg["small_sample"])}
        pr = d[d.book_price.notna() & (d.price_is_estimate == 0)]
        if len(pr):
            ret = [(to_decimal(p) - 1) if r == "won" else -1 for p, r in zip(pr.book_price, pr.result)]
            row["roi_real_prices"] = round(float(np.mean(ret)), 3)
            row["priced_tickets"] = int(len(pr))
        out["tickets"].append(row)
    return out


def report_card(con, date_et: str, cfg=CONFIG) -> dict:
    L = pd.read_sql("SELECT l.*, g.date_et FROM nba_legs l JOIN games g USING (game_id) WHERE g.date_et=? AND l.result IS NOT NULL", con, params=[date_et])
    T = pd.read_sql("SELECT t.* FROM nba_tickets t JOIN games g USING (game_id) WHERE g.date_et=? AND t.result IS NOT NULL", con, params=[date_et])
    P = pd.read_sql("SELECT p.* FROM nba_projections p JOIN games g USING (game_id) WHERE g.date_et=? AND p.act_min IS NOT NULL", con, params=[date_et])
    if len(L):
        L = L.sort_values("run_at").drop_duplicates(["game_id", "leg_id"], keep="last")
    el = L[(L.sgp_eligible == 1) & L.result.isin(["won", "lost"])] if len(L) else L
    card = {"date": date_et, "made_at": ledger.now(),
            "projections_graded": int(len(P)),
            "minutes_mae": round(float((P.min_mean - P.act_min).abs().mean()), 2) if len(P) else None,
            "points_mae": round(float((P.pts - P.act_pts).abs().mean()), 2) if len(P) else None,
            "eligible_legs": {"n": int(len(el)), "hit": int((el.result == "won").sum()) if len(el) else 0,
                              "forecast_hit_rate": round(float(el.model_prob.mean()), 3) if len(el) else None},
            "tickets": [{"type": t.type, "status": t.status, "result": t.result, "joint_prob": round(t.joint_prob, 3),
                         "miss_causes": json.loads(t.miss_causes or "[]"), "legs": [x["description"] for x in json.loads(t.slip_json)]}
                        for t in T.itertuples()],
            "running": running(con, cfg)}
    lines = [f"REPORT CARD {date_et}",
             f"Projections graded: {card['projections_graded']}  minutes MAE {card['minutes_mae']}  points MAE {card['points_mae']}",
             f"Eligible legs: {card['eligible_legs']['hit']}/{card['eligible_legs']['n']} hit (forecast {card['eligible_legs']['forecast_hit_rate']})"]
    for t in card["tickets"]:
        lines.append(f"  [{t['type']}/{t['status']}] {t['result'].upper()}  joint {t['joint_prob']:.0%}" +
                     (f"  causes: {', '.join(t['miss_causes'])}" if t["miss_causes"] else ""))
    for a in card["running"]["alerts"]:
        lines.append(f"  ALERT calibration drift: {a}")
    text = "\n".join(lines)
    ledger.upsert(con, "nba_report_cards", [{"slate_date": date_et, "made_at": card["made_at"], "card_json": json.dumps(card), "card_text": text}])
    card["text"] = text
    return card


if __name__ == "__main__":
    import sys
    from nba.store import connect
    d = sys.argv[1] if len(sys.argv) > 1 else (datetime.now(timezone.utc) - timedelta(hours=29)).date().isoformat()
    print(grade_date(connect(), d)["text"])
