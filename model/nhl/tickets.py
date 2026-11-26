"""Ticket builder: milestone rungs, the ticket rules, one set of slips per game, then the multi-game slips.

Per game (owner, 24 November 2026): a 4-leg, a 6-leg and an 8-leg slip. Shots, points, assists, goals, hits,
blocks, saves, moneyline, puck line and total all go into one pool and the best legs are combined on one
slip. Every leg is a floor rung (70%+; saves 85%+). Also an anytime goal scorer slip and a game-line closer
when the sim's edge over the listed price clears the bar.

Across games: a 2-game slip and a 3-game slip from the games the model reads best, and one lotto ticket at
+5000 or longer built from longshot rungs. Games are independent, so a multi-game chance is each game's
counted chance multiplied across games; inside a game it is always counted from the simulated games.

Rules applied in the search: one leg per player, at most two points legs from one line, market caps so a
slip is not one market repeated, one side and one total at most, no saves leg with that goalie's own team to
win, the blowout guard, and at most one leg under 65%.
"""
from itertools import combinations

import numpy as np

from common.odds_math import expected_value, fair_american, kelly_stake
from common.tickets import allowed, joint, score
from nhl import correlation, gates as gates_mod
from nhl.sim import game_sim

LABEL = {"sog": "shots on goal", "pts": "points", "ast": "assists", "hits": "hits", "blk": "blocked shots", "saves": "saves", "goals": "goals"}
PROP_MARKETS = ("sog", "pts", "ast", "hits", "blk")
LATE_TOI = {"sog", "pts", "ast", "goals"}
SIDES = {"ml", "spread"}


def ladders(odds_rows: list, cfg) -> dict:
    """{(market, player_id): [(rung, price)]} from the book's rows, over side only (a milestone is one-sided)."""
    order = {b: i for i, b in enumerate(cfg["sources"].get("odds_books", []))}
    best = {}
    for r in odds_rows:
        pid = r.get("player_id")
        if pid is not None and pid == pid and r["side"] in ("over", "yes"):            # pid == pid: not NaN from the store
            market = "goals" if r["market"] == "atg" else r["market"]       # anytime scorer is "1+ goals"
            k = (market, int(r["player_id"]), int(r["line"] + 0.5))
            rank = order.get(r.get("book"), len(order))
            if k not in best or rank < best[k][0]:
                best[k] = (rank, r["price"], r.get("book"))
    out = {}
    for (market, pid, rung), (_, price, book) in best.items():
        out.setdefault((market, pid), []).append((rung, price, book))
    return out


def game_line_legs(S, gates: dict, odds_rows: list, cfg) -> tuple[list, list]:
    """Moneyline, puck line and total legs: the book's own lines with their prices, and the standard alternates."""
    c = cfg["tickets"]
    h, a = S.home, S.away
    order = {b: i for i, b in enumerate(cfg["sources"].get("odds_books", []))}
    listed = {}
    for r in odds_rows:
        if r["market"] in ("ml", "spread", "total"):
            side = r["player_name"] if r["side"] == "team" else r["side"]
            k = (r["market"], side, float(r["line"]))
            if k not in listed or order.get(r["book"], 99) < order.get(listed[k][1], 99):
                listed[k] = (r["price"], r["book"])
    want = [("ml", t, 0.0) for t in (h, a)]
    want += [("spread", t, float(l)) for t in (h, a) for l in c["paper_game_lines"]["spread"]]
    want += [("total", s, float(l)) for s in ("over", "under") for l in c["paper_game_lines"]["total"]]
    legs, removed = [], []
    for market, side, line in dict.fromkeys(list(listed) + want):
        hits = game_sim.hits_for(S, market, side, line)
        price, book = listed.get((market, side, line), (None, None))
        label = {"ml": f"{side} moneyline", "spread": f"{side} {line:+g} puck line", "total": f"{side.title()} {line:g} goals"}[market]
        leg = {"kind": "game", "market": market, "team": side if market != "total" else None, "player_id": None, "player": None,
               "side": side, "line": line, "rung": None, "price": price, "book": book, "p": float(hits.mean()), "hits": hits, "active": None,
               "rung_verified": price is not None, "label": label, "line_slot": None, "top_line": False, "script": None}
        ok, why = gates_mod.leg_passes(leg, gates, {}, cfg)
        (legs if ok else removed).append(leg if ok else {"label": label, "p": round(leg["p"], 4), "reason": why})
    return legs, removed


def matchup_grade(factor: float, cfg) -> str:
    m = cfg["tickets"]["matchup"]
    return "strong" if factor >= m["strong"] else ("weak" if factor <= m["weak"] else "neutral")


def matchup_factors(PS, S, cfg) -> dict:
    """How far tonight's matchup moves each projection from the player's own baseline (his rates on his ice time):
    the opponent's allowance, the rink and the score script for shots, hits and blocks; his team's expected goals
    against the league's for goals, assists and points; the opponent's projected shots against the league's for saves."""
    out = {}
    for m in ("sog", "hits", "blk"):
        for e in PS.expected.get(m, []):
            f = 1.0
            for st in e["steps"]:
                f *= st.get("factor", 1.0)
            out[(m, e["player_id"])] = f
    lg_goals = float(np.mean([S.lam[t]["lam"] for t in (S.home, S.away)]))
    lg_goals = cfg["tickets"]["matchup"].get("league_goals", lg_goals)
    for r in PS.players.itertuples():
        f = S.lam[r.team]["lam"] / lg_goals
        for m in ("pts", "ast", "goals"):
            out[(m, int(r.player_id))] = f
    lg_sog = cfg["tickets"]["matchup"].get("league_sog", 28.5)
    for team in (S.home, S.away):
        opp = S.away if team == S.home else S.home
        out[("saves", team)] = float(S.sog[opp].mean()) / lg_sog
    return out


def build_legs(PS, S, gates: dict, flags: dict, odds_rows: list, summary: dict, cfg) -> tuple[list, list]:
    """Every candidate leg that passes the gates, and the ones removed with the reason."""
    c = cfg["tickets"]
    book = ladders(odds_rows, cfg)
    legs, removed = [], []
    P = PS.players
    fav = summary["favourite"]
    dog = S.away if fav == S.home else S.home

    def add(market, team, pid, name, counts, extra):
        rungs = book.get((market, pid))
        verified = rungs is not None
        if not verified:
            rungs = [(1, None, None)] if market == "goals" else [(r, None, None) for r in c["paper_ladders"].get(market, [])]
        grade = matchup_grade(extra.get("matchup_factor", 1.0), cfg)
        for rung, price, bk in sorted(rungs):
            hits = counts >= rung
            leg = {"kind": "prop", "market": market, "team": team, "player_id": pid, "player": name, "rung": rung, "price": price,
                   "book": bk, "p": float(hits.mean()), "hits": hits, "active": None, "rung_verified": verified, "mean": float(counts.mean()),
                   "label": f"{name} {rung}+ {LABEL[market]}", "matchup": grade, **extra}
            ok, why = gates_mod.leg_passes(leg, gates, flags, cfg)
            if ok and summary["blowout_flag"]:
                if market == "saves" and team == dog and c["saves_cap_blowout"]:
                    ok, why = False, "blowout guard: saves on the goalie facing the favourite"
                elif market in LATE_TOI and team == fav and extra.get("top_line"):
                    ok, why = False, "blowout guard: late ice time on the favourite's top line"
            (legs if ok else removed).append(leg if ok else {"label": leg["label"], "p": round(leg["p"], 4), "reason": why})

    mf = matchup_factors(PS, S, cfg)
    for j, r in enumerate(P.itertuples()):
        for m in PROP_MARKETS + ("goals",):
            add(m, r.team, int(r.player_id), r.name, PS.data[m][:, j],
                {"line_slot": r.ev_slot, "top_line": bool(r.top_line), "script": f"shots:{r.team}" if m == "sog" else None,
                 "matchup_factor": mf.get((m, int(r.player_id)), 1.0)})
    for team, g in PS.goalies.items():
        if g.get("player_id") is None:
            continue
        opp = S.away if team == S.home else S.home
        add("saves", team, int(g["player_id"]), g["name"], g["saves"],
            {"line_slot": None, "top_line": False, "script": f"shots:{opp}", "matchup_factor": mf.get(("saves", team), 1.0)})
    gl, gr = game_line_legs(S, gates, odds_rows, cfg)
    return legs + gl, removed + gr


def leg_floor(leg: dict, cfg) -> float:
    c = cfg["tickets"]
    return c.get("floor_prob_by_market", {}).get(leg["market"], c["floor_prob"])


def floor_rungs(legs: list, cfg) -> list:
    """For each player and market the highest rung that still clears the floor (the floor rung), and for game
    lines the listed line when it clears the floor, else the tightest alternate that does."""
    best, strong = {}, {}
    sr = cfg["tickets"]["matchup"]["strong_rung_prob"]
    for l in legs:
        if l.get("kind") != "game" and l.get("matchup") == "weak":
            continue                                                    # a weak matchup stays off the slip
        if l.get("kind") != "game" and l.get("matchup") == "strong" and l["market"] != "goals" and l["p"] >= min(sr, leg_floor(l, cfg)):
            k = (l["market"], l["player_id"])
            if k not in strong or l["rung"] > strong[k]["rung"]:
                strong[k] = l                                           # a strong mismatch may take a higher listed rung
        if l["p"] < leg_floor(l, cfg):
            continue
        if l.get("kind") == "game":
            k = (l["market"], l["side"])
            cur = best.get(k)
            better = cur is None or (l["rung_verified"] and not cur["rung_verified"]) or \
                (l["rung_verified"] == cur["rung_verified"] and l["p"] < cur["p"])        # the tightest line that still clears
            if better:
                best[k] = l
        else:
            k = (l["market"], l["player_id"])
            if k not in best or l["rung"] > best[k]["rung"]:
                best[k] = l
    for k, l in strong.items():
        if k in best and l["rung"] > best[k]["rung"]:                  # only above a floor rung, never in place of one
            best[k] = {**l, "rung_reason": "strong matchup: one rung above the floor"}
    return list(best.values())


def nhl_allowed(combo, cfg) -> bool:
    c = cfg["tickets"]
    if sum(l["p"] < c["sub65_prob"] for l in combo) > c["max_sub65_legs"]:
        return False
    per_line, sides, totals, saves_teams, side_teams = {}, 0, 0, set(), set()
    for l in combo:
        if l["market"] in ("pts", "ast") and l.get("line_slot"):
            k = (l["team"], l["line_slot"])
            per_line[k] = per_line.get(k, 0) + 1
        if l["market"] in SIDES:
            sides += 1; side_teams.add(l["team"])
        elif l["market"] == "total":
            totals += 1
        elif l["market"] == "saves":
            saves_teams.add(l["team"])
    if sides > 1 or totals > 1 or sides + totals > c.get("max_game_line_legs", 2):
        return False
    if saves_teams & side_teams:                                        # a goalie's saves over and his own team to win pull apart
        return False
    return not per_line or max(per_line.values()) <= c["max_legs_same_line_points"]


def best_sgp(pool: list, size: int, cfg, floor_joint: float | None = None) -> dict | None:
    """Highest expected value when every leg has a price; otherwise the highest joint chance."""
    c = cfg["tickets"]
    priced = all(l.get("price") is not None for l in pool) and bool(pool)
    rank = (lambda l: -(l["p"] * (1 + l["price"] / 100 if l["price"] > 0 else 1 + 100 / -l["price"]))) if priced else (lambda l: -l["p"])
    cap = c.get("max_legs_per_market", {})
    ranked, seen = [], {}
    for l in sorted(pool, key=rank):                                    # the pool is filled market by market, so every market gets a look
        if seen.get(l["market"], 0) < cap.get(l["market"], 4) + 2:
            ranked.append(l); seen[l["market"]] = seen.get(l["market"], 0) + 1
    pool = ranked[:c.get("sgp_candidate_pool_by_size", {}).get(size, c["sgp_candidate_pool"])]
    floor_joint = c["ticket_min_joint"].get(size, 0.0) if floor_joint is None else floor_joint
    rule = {**c, "max_legs_per_market": {**cap, **c.get("max_legs_per_market_by_size", {}).get(size, {})}, "max_legs_per_market_by_size": {}}
    stack = np.array([l["hits"] for l in pool]) if pool else np.zeros((0, 0), bool)
    best, key = None, None
    for idx in combinations(range(len(pool)), size):
        combo = [pool[i] for i in idx]
        if not allowed(combo, rule, False, size) or not nhl_allowed(combo, cfg):
            continue
        j = float(stack[list(idx)].all(0).mean())
        if j < floor_joint:
            continue
        k = score(combo)["ev"] if priced else j
        if key is None or k > key:
            best, key = {"legs": combo, "joint": j}, k
    return best


def leg_out(l: dict) -> dict:
    return {"label": l["label"], "kind": l.get("kind", "prop"), "market": l["market"], "team": l.get("team"), "player": l.get("player"),
            "player_id": l.get("player_id"), "rung": l.get("rung"), "side": l.get("side"), "line": l.get("line"), "prob": round(l["p"], 4),
            "price": l.get("price"), "book": l.get("book"), "matchup": l.get("matchup"), "rung_reason": l.get("rung_reason"),
            "fair_price": fair_american(l["p"]), "rung_verified": bool(l.get("rung_verified", True)),
            "why": l.get("why", []), "game": l.get("game"), "game_id": l.get("game_id")}


def legs_price(prices: list) -> int | None:
    """The slip's price from the book's own leg prices, multiplied (the book's same-game price will differ)."""
    if not prices or any(p is None for p in prices):
        return None
    d = 1.0
    for p in prices:
        d *= 1 + p / 100 if p > 0 else 1 + 100 / -p
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))


def _ticket(kind, title, legs, cfg, extra=None) -> dict:
    j = joint(legs)
    prices = [l.get("price") for l in legs]
    return {"kind": kind, "title": title, "legs": [leg_out(l) for l in legs], "chance": round(j, 4), "miss": round(1 - j, 4),
            "fair_price": fair_american(j), "lift": round(correlation.lift(legs), 3) if len(legs) > 1 else 1.0,
            "pairs": correlation.pair_table(legs) if 1 < len(legs) <= 6 else [],
            "markets": sorted({l["market"] for l in legs}), "book_price": legs_price(prices),
            "priced": all(p is not None for p in prices), "rungs_verified": all(l.get("rung_verified", True) for l in legs), **(extra or {})}


def build(PS, S, gates: dict, flags: dict, odds_rows: list, summary: dict, game_lines: list, cfg, explain=None) -> dict:
    """All of one game's slips, what was removed and why, and the legs the multi-game slips draw on.
    `explain(leg)` returns the reasons for a leg; it is called only for legs that make a slip or the pool."""
    c = cfg["tickets"]
    legs, removed = build_legs(PS, S, gates, flags, odds_rows, summary, cfg)
    pool = floor_rungs(legs, cfg)
    if explain:
        for l in pool:
            l["why"] = explain(l)
    out = {"tickets": [], "removed": removed, "pool": [leg_out(l) for l in sorted(pool, key=lambda l: -l["p"])], "legs": legs}
    for size in c["sizes"]:
        t = best_sgp(pool, size, cfg)
        if t:
            out["tickets"].append(_ticket(f"sgp{size}", f"{size}-leg slip", t["legs"], cfg))
        else:
            out.setdefault("notes", []).append(f"no {size}-leg slip: {len(pool)} floor rungs passed the gates, "
                                               f"or no combination reached the {c['ticket_min_joint'].get(size, 0):.0%} joint floor")
    trio = best_sgp(pool, c["multi"]["legs_per_game"], cfg, floor_joint=0.0)
    out["multi_part"] = trio
    # ordered by the model's chance alone, weak matchups left out (odds never pick a scorer)
    goals = [l for l in legs if l["market"] == "goals" and l["rung"] == 1 and l.get("matchup") != "weak"]
    scorers = sorted([l for l in goals if l["p"] >= c["atg_min_prob"]], key=lambda l: -l["p"]) or sorted(goals, key=lambda l: -l["p"])
    if scorers:
        pick = [{**l, "label": f"{l['player']} anytime goal scorer", "why": explain(l) if explain else []} for l in scorers[:c["atg_legs"]]]
        out["tickets"].append(_ticket("atg", "Anytime goal scorer", pick, cfg))
    # Odds never make a pick (owner, 25 November 2026): the closer is the listed side or total the model itself rates most
    # likely, if that clears the bar. The book's line only confirms the line exists and says what it pays.
    listed = [l for l in legs if l.get("kind") == "game" and l.get("rung_verified") and l["market"] in c["closer_markets"]
              and (l["market"] == "ml" or abs(l["line"]) in c["closer_spreads"])]
    closers = sorted([l for l in listed if l["p"] >= c["closer_min_prob"]], key=lambda l: -l["p"])
    if closers and gates["goalies_ok"]:
        leg = {**closers[0], "why": explain(closers[0]) if explain else []}
        out["tickets"].append(_ticket("closer", "Game-line closer", [leg], cfg, {"book": leg.get("book")}))
    elif closers:
        out.setdefault("notes", []).append("game-line closer withheld: starting goalie not confirmed")
    return out


# ------------------------------------------------------------------ across games
def _multi_ticket(kind: str, title: str, parts: list, extra=None) -> dict:
    """parts: [(game dict, legs)]. Chance = each game's counted chance, multiplied across the (independent) games."""
    chance, legs = 1.0, []
    for game, ls in parts:
        chance *= joint(ls)
        legs += [{**leg_out(l), "game": game["label"], "game_id": game["game_id"]} for l in ls]
    return {"kind": kind, "title": title, "legs": legs, "chance": round(chance, 5), "miss": round(1 - chance, 5),
            "fair_price": fair_american(chance), "book_price": legs_price([l["price"] for l in legs]), "games": [g["label"] for g, _ in parts], "game_ids": [g["game_id"] for g, _ in parts],
            "markets": sorted({l["market"] for l in legs}), "priced": all(l["price"] is not None for l in legs),
            "rungs_verified": all(l["rung_verified"] for l in legs), "lift": 1.0, **(extra or {})}


def multi_game(games: list, cfg) -> list:
    """The 2-game and 3-game slips: the games whose best three-leg combination the model rates highest.
    games: [{"game_id", "label", "multi_part", "gates_ok"}]. A game that failed a gate is not used."""
    c = cfg["tickets"]["multi"]
    ranked = sorted([g for g in games if g.get("multi_part") and g.get("gates_ok")], key=lambda g: -g["multi_part"]["joint"])
    out = []
    for n in c["games"]:
        if len(ranked) >= n:
            parts = [(g, g["multi_part"]["legs"]) for g in ranked[:n]]
            out.append(_multi_ticket(f"multi{n}", f"{n}-game slip", parts,
                                     {"how_chosen": f"the {n} games whose best {c['legs_per_game']}-leg combination has the highest counted chance"}))
    return out


def _decimal(price) -> float:
    return 1 + price / 100 if price > 0 else 1 + 100 / -price


def lotto(games: list, cfg) -> dict | None:
    """One longshot ticket at +5000 or longer on the book's own leg prices multiplied, from the strongest longshot rungs
    on the board: each leg is a listed rung, the player's most likely one in the longshot band, never a weak matchup.
    The price keeps the ticket in its range; it never chooses a leg (the model's chance orders them)."""
    c = cfg["tickets"]["multi"]
    lo, hi = c["lotto_leg_prob"]
    cands = []
    for g in games:
        if not g.get("gates_ok"):
            continue
        best = {}
        for l in g["legs"]:
            if l["market"] not in c["lotto_markets"] or not (lo <= l["p"] <= hi) or l.get("matchup") == "weak":
                continue
            if cfg["gates"].get("require_book_rung") and l.get("price") is None:
                continue
            k = l["player_id"] if l.get("player_id") is not None else ("side", l["market"])
            if k not in best or l["p"] > best[k]["p"]:
                best[k] = l                                             # one leg per player: his most likely longshot rung
        cands += [(g, l) for l in best.values()]
    cands.sort(key=lambda x: -x[1]["p"])
    priced = cfg["gates"].get("require_book_rung")
    picked, per_game = [], {}

    def chance(sel):
        by = {}
        for g, l in sel:
            by.setdefault(g["game_id"], []).append(l)
        return float(np.prod([joint(ls) for ls in by.values()]))

    def price(sel):                                                     # the range check: book prices when we have them
        return float(np.prod([_decimal(l["price"]) for _, l in sel])) if priced else 1 / max(chance(sel), 1e-9)

    for g, l in cands:
        if per_game.get(g["game_id"], 0) >= c["lotto_max_legs_per_game"] or len(picked) >= c["lotto_legs"][1]:
            continue
        same = [x for gg, x in picked if gg["game_id"] == g["game_id"]]
        if same and not nhl_allowed(same + [l], cfg | {"tickets": {**cfg["tickets"], "max_sub65_legs": 99}}):
            continue
        trial = picked + [(g, l)]
        if price(trial) > c["lotto_max_decimal"]:
            continue
        picked = trial
        per_game[g["game_id"]] = per_game.get(g["game_id"], 0) + 1
        if price(picked) >= c["lotto_min_decimal"] and len(picked) >= c["lotto_legs"][0] and len(per_game) >= c["lotto_min_games"]:
            break
    if not picked or price(picked) < c["lotto_min_decimal"] or len(per_game) < c["lotto_min_games"]:
        return None
    by = {}
    for g, l in picked:
        by.setdefault(g["game_id"], (g, []))[1].append(l)
    basis = "the book's leg prices multiplied" if priced else "the model's fair price"
    return _multi_ticket("lotto", "Lotto ticket", list(by.values()),
                         {"how_chosen": f"each player's most likely listed longshot rung ({lo:.0%} to {hi:.0%}), strongest first, at most "
                                        f"{c['lotto_max_legs_per_game']} a game, until {basis} passes +{round((c['lotto_min_decimal'] - 1) * 100)}"})
