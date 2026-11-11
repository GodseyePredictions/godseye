"""Legs, tickets and cards for one game, built from the simulations.

Candidate legs are only ever rungs and lines the book offers tonight (rows from the odds table).
The backtest has no book prices, so it passes a fixed calibration grid instead and says so.
"""
import numpy as np
import pandas as pd

from common import tickets as tk
from common.odds_math import decimal_to_american, fair_american
from nba import game_sim as gs
from nba import player_sim as ps
from nba import props
from nba.config import CONFIG

WORDS = {"pts": "Points", "reb": "Rebounds", "ast": "Assists", "fg3m": "Threes Made", "stl": "Steals", "blk": "Blocks",
         "pra": "Points, Rebounds & Assists", "pr": "Points & Rebounds", "pa": "Points & Assists",
         "dd": "To Record a Double Double", "td": "To Record a Triple Double"}
PROP_MARKETS = ["pts", "reb", "ast", "fg3m", "stl", "blk", "pra", "pr", "pa"]
STAT_ITEMS = {"pts": {"fg2a", "fg3a", "fta", "fg2m", "fg3m"}, "reb": {"reb"}, "ast": {"ast"}, "fg3m": {"fg3a", "fg3m"},
              "stl": {"stl"}, "blk": {"blk"}}


def grid_offers(players: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Backtest only: a fixed grid of thresholds for every player. These are NOT book lines."""
    rows = []
    for p in players.itertuples():
        for m, ks in cfg["calibration_grid"].items():
            rows += [{"market": m, "player_id": p.player_id, "player_name": p.name, "side": "over", "line": k - 0.5,
                      "price": None, "book": "grid", "known_at": None} for k in ks]
    return pd.DataFrame(rows)


def label(o, both_sides: bool, team_names: dict) -> str:
    if o.market in ("dd", "td"):
        return f"{o.player_name} {WORDS[o.market]}"
    if o.market == "ml":
        return f"{team_names.get(o.player_id, o.player_name)} Money Line"
    if o.market == "spread":
        return f"{team_names.get(o.player_id, o.player_name)} {o.line:+g} Spread"
    if o.market == "total":
        return f"{o.side.title()} {o.line:g} Total Points"
    if both_sides or o.side == "under":
        return f"{o.player_name} {o.side.title()} {o.line:g} {WORDS[o.market]}"
    return f"{o.player_name} {int(o.line + 0.5)}+ {WORDS[o.market]}"


def reason_for(row, market: str) -> str:
    """One line for the slip, taken from the itemised adjustments (or the role note)."""
    stats = set().union(*(STAT_ITEMS.get(s, set()) for s in (ps.COMBOS.get(market) or (market,))))
    names = {"fg2a": "two-point attempts", "fg3a": "three-point attempts", "fta": "free throws", "reb": "rebounds",
             "ast": "assists", "stl": "steals", "blk": "blocks", "fg2m": "two-point accuracy", "fg3m": "three-point accuracy"}
    items = sorted((i for i in row["items"] if i[0] in stats), key=lambda x: -abs(x[2]))
    if row.get("role_change_reason"):
        lead = f"role: {row['role_change_reason']}"
    else:
        lead = ""
    if items:
        s, g, v = items[0]
        txt = f"{names[s]} {np.expm1(v):+.0%} from {props.LABEL[g]}"
        return f"{lead}; {txt}" if lead else txt
    return lead or "at baseline: no adjustment above 1%"


def build_legs(offers: pd.DataFrame, sims, players, gate: pd.DataFrame | None, team_names: dict, cfg=CONFIG) -> list[dict]:
    """Every offered rung with its model probability from the simulations and its eligibility checks."""
    legs = []
    if offers is None or offers.empty:
        return legs
    P = players.players.set_index("player_id") if players is not None else None
    ok_ids = None if gate is None else set(gate[gate.ticket_eligible == 1].player_id)
    flagged = (sims.blowout(cfg) != 0).mean() >= cfg["blowout_flag_prob"]
    pairs = set(zip(offers.market, offers.player_id, offers.line, offers.side))
    rank = {}
    for (m, pid), d in offers[offers.side == "over"].groupby(["market", "player_id"]):
        for i, l in enumerate(sorted(d.line.unique())):
            rank[(m, pid, l)] = i + 1
    for o in offers.itertuples():
        if o.market in ("ml", "spread", "total"):
            side = ("home" if o.player_id == sims.home_id else "away") if o.market != "total" else o.side
            hits = gs.leg_hits(sims, o.market, float(o.line), side)
            both = False
            act = None
            leg = {"kind": "game", "player_id": None, "team_id": o.player_id if o.market != "total" else None, "starter": False,
                   "gate_ok": True, "eligible_player": True, "rung_rank": 1}
        else:
            if P is None or o.player_id not in P.index:
                continue
            r = P.loc[o.player_id]
            hits = players.hits(o.player_id, o.market, float(o.line), o.side)
            act = players.active(o.player_id)
            both = (o.market, o.player_id, o.line, "under" if o.side == "over" else "over") in pairs
            g_ok = True
            if o.side == "over" and o.market in ("pts", "pra", "pr", "pa"):
                g_ok = bool(r.gate_pts)
            if o.side == "over" and o.market == "fg3m":
                g_ok = bool(r.gate_fg3m)
            leg = {"kind": "dd" if o.market in ("dd", "td") else "prop", "player_id": o.player_id, "team_id": r.team_id,
                   "starter": r.role == "starter", "gate_ok": g_ok, "eligible_player": ok_ids is None or o.player_id in ok_ids,
                   "rung_rank": rank.get((o.market, o.player_id, o.line), 1), "reason": reason_for(r, o.market),
                   "name": r["name"]}
        sp = ps.split_prob(players, hits, act) if players is not None else {"all": float(hits.mean()), "blowout": None, "close": None}
        gap = cfg["script_dependence_gap"]
        script = None
        if sp["blowout"] is not None and sp["close"] is not None:
            script = "needs close game" if sp["close"] - sp["blowout"] > gap else ("needs blowout" if sp["blowout"] - sp["close"] > gap else None)
        leg.update({"market": o.market, "line": float(o.line), "side": o.side, "p": sp["all"], "p_blowout": sp["blowout"],
                    "p_close": sp["close"], "price": None if pd.isna(o.price) else float(o.price), "book": o.book,
                    "price_seen_at": o.known_at, "hits": hits, "active": act, "script": script, "flagged_game": bool(flagged),
                    "label": label(o, both, team_names)})
        leg["id"] = f"{sims.game_id}|{o.market}|{o.player_id}|{o.side}|{o.line:g}"
        legs.append(leg)
    return legs


def sgp_eligible(leg: dict, cfg=CONFIG, require_price=True) -> tuple[bool, str]:
    """The standing rules for a same-game parlay leg, with the reason when a leg fails."""
    if leg["kind"] != "prop" or leg["market"] not in PROP_MARKETS:
        return False, "not a props-ticket market"
    if require_price and leg["price"] is None:
        return False, "no book price"
    if not leg["eligible_player"]:
        return False, "player not confirmed in"
    if leg["p"] < cfg["sgp_leg_floor"]:
        return False, f"model probability {leg['p']:.0%} is under the floor"
    if not leg["gate_ok"]:
        return False, "fails the shooting gate"
    if leg["flagged_game"]:
        if leg["p_blowout"] is not None and leg["p_blowout"] < cfg["sgp_leg_floor"]:
            return False, "under the floor inside blowout simulations"
        if leg["starter"] and leg["side"] == "over" and leg["rung_rank"] > cfg["upper_rung_rank"]:
            return False, "starter's upper rung in a blowout-flagged game"
    return True, ""


def floor_rungs(legs: list) -> list:
    """For each player and market keep the highest rung that still qualifies (the floor rung)."""
    best = {}
    for l in legs:
        k = (l["player_id"], l["market"], l["side"])
        cur = best.get(k)
        if cur is None or (l["line"] > cur["line"] if l["side"] == "over" else l["line"] < cur["line"]):
            best[k] = l
    return list(best.values())


def script_card(card: dict, sims, players, cfg=CONFIG) -> dict:
    g, pred = card["game"], card["pred"]
    b, close, m = sims.blowout(cfg), sims.close(cfg), sims.margin
    H, A = g.home_abbr, g.away_abbr
    cls = np.select([b == 1, b == -1, close, m > 0], [0, 1, 2, 3], 4)
    names = [f"{H} control from the second half and lead big; starters rest in the fourth",
             f"{A} control from the second half and lead big; starters rest in the fourth",
             "Close game decided in the last five minutes; starters play heavy fourth-quarter minutes",
             f"{H} win comfortably without a blowout; normal rotations",
             f"{A} win comfortably without a blowout; normal rotations"]
    effects = ["bench scorers and deep reserves gain minutes; starters on both sides lose fourth-quarter volume; "
               "ball handlers lose late assists; rebounders lose the least",
               "bench scorers and deep reserves gain minutes; starters on both sides lose fourth-quarter volume; "
               "ball handlers lose late assists; rebounders lose the least",
               "starters and primary ball handlers gain (late possessions, free throws); bench scorers lose minutes",
               "everyone near baseline; winning side's starters may sit the last minutes",
               "everyone near baseline; winning side's starters may sit the last minutes"]
    scripts = []
    S = ps.summary(players) if players is not None else None
    for i in np.argsort(-np.bincount(cls, minlength=5))[:3]:
        sel = cls == i
        if sel.mean() < 0.02:
            continue
        who = ""
        if S is not None and sel.sum() >= 30:
            d = players.data["min"][sel].mean(0) - players.data["min"].mean(0)
            nm = players.players.name.to_numpy()
            up, dn = np.argsort(-d)[:2], np.argsort(d)[:2]
            who = ("gain: " + ", ".join(f"{nm[j]} {d[j]:+.1f} min" for j in up if d[j] > 0.5) +
                   " | lose: " + ", ".join(f"{nm[j]} {d[j]:+.1f} min" for j in dn if d[j] < -0.5))
        scripts.append({"script": names[i], "probability": float(sel.mean()), "who": effects[i], "players": who})
    pb = float((b != 0).mean())
    out = {"game_id": g.game_id, "matchup": f"{A} @ {H}", "date": g.date_et,
           "pace": {"ours": round(float(pred.model_poss), 1)},
           "margin_home": {"ours": round(float(pred.model_margin), 1), "market": None if pd.isna(pred.market_margin) else float(pred.market_margin),
                           "blend": round(float(pred.blend_margin), 1), "simulated": round(float(m.mean()), 1)},
           "total": {"ours": round(float(pred.model_total), 1), "market": None if pd.isna(pred.market_total) else float(pred.market_total),
                     "blend": round(float(pred.blend_total), 1), "simulated": round(float(sims.total.mean()), 1)},
           "market_weight": float(pred.market_weight),
           "win_prob_home": float((m > 0).mean()), "blowout_prob": pb,
           "blowout_prob_home": float((b == 1).mean()), "blowout_prob_away": float((b == -1).mean()),
           "close_prob": float(close.mean()), "scripts": scripts, "blowout_warning": pb >= cfg["blowout_flag_prob"]}
    if S is not None:
        st = S[S.role == "starter"]
        out["starter_q4_minutes"] = {r["name"]: round(float(r.q4_min), 1) for _, r in st.iterrows()}
        out["blowout_exposure"] = {r["name"]: round(float(r.blowout_exposure), 2) for _, r in S[S.e_min >= 15].iterrows()}
    return out


def build_tickets(legs: list, sims, card: dict, cfg=CONFIG, require_price=True, sgp_prices: dict | None = None) -> dict:
    """All tickets for one game. `sgp_prices` may hold the book's real same-game price per ticket type."""
    sgp_prices = sgp_prices or {}
    pool = floor_rungs([l for l in legs if sgp_eligible(l, cfg, require_price)[0]])
    out = {"tickets": [], "notes": []}

    def finish(kind, t):
        if t is None:
            out["notes"].append(f"{kind}: no bet (no combination clears the rules)")
            return None
        real = sgp_prices.get(kind)
        if real:
            t.update(tk.score(t["legs"], real))
        t["type"] = kind
        t["fair_price"] = fair_american(t["joint"])
        t["book_price"] = decimal_to_american(t["decimal"]) if t["decimal"] else None
        out["tickets"].append(t)
        return t

    four = None
    for size in cfg["sgp_sizes"]:
        t = finish(f"props_{size}", tk.best_ticket(pool, size, cfg, require_price) if len(pool) >= size else None)
        if size == 4:
            four = t
    # game-script variant: the 4-leg ticket plus one game leg that fits the likely scripts and adds value
    if four is not None:
        top = card["scripts"][0]["script"] if card.get("scripts") else ""
        best = None
        for gl in [l for l in legs if l["kind"] == "game" and l["p"] >= cfg["sgp_leg_floor"] and (l["price"] is not None or not require_price)]:
            s = tk.score(four["legs"] + [gl])
            if s["joint"] < cfg["ticket_min_joint"].get(5, 0):
                continue
            gain = (s["ev"] - four["ev"]) if (s["ev"] is not None and four["ev"] is not None) else None
            if require_price and (gain is None or gain <= 0):
                continue
            key = s["ev"] if s["ev"] is not None else s["joint"]
            if best is None or key > best[0]:
                best = (key, {"legs": four["legs"] + [gl], **s})
        if best:
            finish("game_script", best[1])
        else:
            out["notes"].append("game_script: no game leg qualifies")
    dd = [l for l in legs if l["kind"] == "dd" and l["eligible_player"] and l["p"] >= cfg["sgp_leg_floor"]
          and (l["price"] is not None or not require_price)]
    pub = cfg["dd_publish_min_prob"]
    dd = [l for l in dd if l["p"] >= (pub if l["market"] == "dd" else cfg["td_publish_min_prob"])]
    if dd:
        dd = sorted(dd, key=lambda l: -l["p"])[:cfg["dd_ticket_max_legs"]]
        s = tk.score(dd)
        finish("double_double", {"legs": dd, **s})
    else:
        out["notes"].append("double_double: no bet (no published double-double or triple-double leg clears 70%)")
    out["singles"] = tk.singles([l for l in legs if l["eligible_player"] and l["p"] < cfg["sgp_leg_floor"]], cfg) if require_price else []
    return out


def slip_text(card: dict, built: dict, gate: pd.DataFrame | None) -> str:
    """The printed card: game script first, then tickets in the book's wording, then risk notes."""
    L = [f"=== {card['matchup']}  {card['date']} ===", "GAME SCRIPT"]
    mm, tt = card["margin_home"], card["total"]
    mk = lambda v: "n/a" if v is None else f"{v:+.1f}"
    L.append(f"  Margin (home): ours {mm['ours']:+.1f} | market {mk(mm['market'])} | blend {mm['blend']:+.1f}")
    L.append(f"  Total: ours {tt['ours']:.1f} | market {'n/a' if tt['market'] is None else tt['market']} | blend {tt['blend']:.1f}"
             f"   Pace: {card['pace']['ours']} possessions")
    L.append(f"  Home win {card['win_prob_home']:.0%} | blowout {card['blowout_prob']:.0%} | close game {card['close_prob']:.0%}")
    if mm["market"] is None:
        L.append("  No market line was available: the blend is our number alone.")
    for s in card["scripts"]:
        L.append(f"  {s['probability']:.0%}  {s['script']}")
        L.append(f"        {s['who']}" + (f"  [{s['players']}]" if s["players"] else ""))
    if card["blowout_warning"]:
        L.append("  ** BLOWOUT WARNING: starters' upper rungs are excluded and every leg must clear 70% inside blowout simulations **")
    L.append("TICKETS")
    for t in built["tickets"]:
        price = f"{t['book_price']:+d}" if t["book_price"] is not None else "no price"
        est = " (product of leg prices, not the book's same-game price)" if t.get("price_is_estimate") and t["book_price"] is not None else ""
        ev = f"{t['ev']:+.1%}" if t["ev"] is not None else "n/a"
        L.append(f"  [{t['type']}] joint {t['joint']:.1%} | book {price}{est} | fair {t['fair_price']:+d} | EV {ev}")
        for l in t["legs"]:
            p = f"{l['price']:+.0f}" if l["price"] is not None else "-"
            L.append(f"     {l['label']:<48} model {l['p']:.0%}  book {p}  {l.get('reason', '')}")
    for n in built["notes"]:
        L.append(f"  {n}")
    if built.get("singles"):
        L.append("SINGLES (edge rungs, straight bets only)")
        for s in built["singles"][:10]:
            L.append(f"     {s['label']:<48} model {s['p']:.0%}  book {s['price']:+.0f}  EV {s['ev']:+.1%}  stake {s['kelly_stake']:.2%} of bankroll")
    L.append("RISK NOTES")
    L.append(f"  Blowout probability {card['blowout_prob']:.0%}.")
    if gate is not None and len(gate):
        q = gate[gate.status.isin(["questionable", "doubtful", "unknown"]) & gate.player_id.notna()]
        used = {l.get("team_id") for t in built["tickets"] for l in t["legs"]}
        for r in q.itertuples():
            if r.team_id in used or not built["tickets"]:
                L.append(f"  {r.name} is {r.status}: a change re-runs this game and can change the tickets.")
    return "\n".join(L)
