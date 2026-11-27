"""One date's slate: gates, game sim, props, correlation, tickets, for every game that has not started.

Output: nhl/output/nhl_slate.json (what the site shows) and nhl/output/nhl_ledger.json (every ticket with
the time it was made, locked once its game starts, graded by grade.py). Picks come only from this engine.
"""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from nhl import context, explain, gates as gates_mod, props, store, tickets
from nhl.ingest import refs
from nhl.sim import game_sim

OUT = Path(__file__).parent / "output"
SLATE, LEDGER, SITE = OUT / "nhl_slate.json", OUT / "nhl_ledger.json", OUT / "nhl_site.json"
CASHED = OUT / "nhl_cashed.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def latest(con, table: str, key: str, as_of: str, where: str = "1=1", params=()) -> pd.DataFrame:
    return store.read(con, f"SELECT t.* FROM {table} t JOIN (SELECT {key} k, MAX(known_at) m FROM {table} WHERE known_at <= ? AND {where} "
                           f"GROUP BY {key}) x ON t.{key} = x.k AND t.known_at = x.m WHERE {where}", [as_of, *params, *params])


def run_game(game: dict, ctx: dict, tables, con, cfg, as_of: str, n: int | None = None, recent: dict | None = None) -> dict:
    home, away = game["home"], game["away"]
    goalie_rows = latest(con, "goalie_starts", "team", as_of, "date_et = ?", [game["date_et"]]).to_dict("records")
    lines = ctx["lines"] if ctx.get("lines") is not None else pd.DataFrame()
    line_rows = lines[lines.team.isin([home, away])].to_dict("records") if len(lines) else []
    clean = lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else v
    line_rows = [{k: clean(v) for k, v in r.items()} for r in line_rows]
    line_rows = [{**r, "player_id": None if r["player_id"] is None else int(r["player_id"])} for r in line_rows]
    G = gates_mod.game_gates(game, goalie_rows, line_rows, cfg)
    if cfg["gates"].get("preview"):                               # said, not enforced: the final run enforces them
        G["notes"] = [n.split(":")[0] + ": legs that depend on it are re-run once it is confirmed" for n in G["notes"]]
    flags = gates_mod.lineup_flags(line_rows)
    rosters, absent = {}, {}
    for t in (home, away):
        rosters[t] = context.roster(ctx, t, cfg)
        absent[t] = context.absent_share(ctx, t, set(rosters[t].player_id), cfg) if G["lines"][t]["ok"] else {}
    gk = {}
    for t in (home, away):
        g = G["goalies"][t]
        pid = None if g["player_id"] is None or pd.isna(g["player_id"]) else int(g["player_id"])
        gk[t] = context.goalie_input(ctx, pid, g["goalie"]) if g["goalie"] else None
        if gk[t]:
            gk[t]["player_id"] = pid
    ra = store.read(con, "SELECT name FROM ref_assignments WHERE date_et=? AND home=? AND role='referee'", [game["date_et"], home])
    crew = refs.crew_factor(list(ra.name), ctx["ref_rates"], cfg) if len(ra) else {"factor": 1.0, "referees": []}
    gctx = {**ctx, "goalies": gk, "crew_factor": crew["factor"], "spots": context.spots_for(tables, game["game_id"]), "absent": absent}
    lam = game_sim.team_lambdas(home, away, gctx, cfg)
    S = game_sim.simulate(lam, home, away, ctx["K"], cfg, n=n, seed=cfg["sim"]["seed"] + int(game["game_id"]) % 100000)
    summ = game_sim.summary(S, cfg)
    odds_rows = latest(con, "odds", "game_id", as_of, "game_id = ?", [game["game_id"]]).to_dict("records")
    lines_priced = game_sim.price_markets(S, odds_rows, cfg)
    if cfg["gates"].get("require_book_rung") and not odds_rows:
        G["notes"].insert(0, "no listed prices for this game: the odds feed did not return it, so no slip is issued")
    PS = props.simulate(S, rosters, gctx, cfg, game_id=game["game_id"], goalies={t: gk[t] or {} for t in (home, away)})
    ex = explain.Explainer(PS, S, lam, gctx, recent or {}, lines_priced, summ, S.n)
    T = tickets.build(PS, S, G, flags, odds_rows, summ, lines_priced, cfg, explain=ex)
    gates_ok = G["goalies_ok"] and all(v["ok"] for v in G["lines"].values())
    probs = game_sim.market_probs(S)
    fair = lambda k: {"prob": round(probs[k], 4), "fair_price": tickets.fair_american(probs[k])}
    proj = []
    for j, r in enumerate(PS.players.itertuples()):
        proj.append({"player_id": int(r.player_id), "player": r.name, "team": r.team, "pos": r.group, "toi_min": round(r.total / 60, 1),
                     "line": r.ev_slot, "pp": r.pp_unit, "notes": r.notes,
                     **{m: round(float(PS.data[m][:, j].mean()), 2) for m in ("sog", "pts", "goals", "ast", "hits", "blk")},
                     "atg": round(float((PS.data["goals"][:, j] >= 1).mean()), 4)})
    paper = not all(t["rungs_verified"] for t in T["tickets"]) if T["tickets"] else True
    label = f"{away} @ {home}"
    for t in T["tickets"]:
        t["id"] = f"{game['date_et']}-{away}-{home}-{t['kind']}"
        t["game"], t["game_id"], t["made_at"], t["start_utc"] = label, game["game_id"], as_of, game["start_utc"]
        for l in t["legs"]:
            l["game"], l["game_id"] = label, game["game_id"]
    for l in T["legs"]:
        l["game"], l["game_id"] = label, game["game_id"]
        if l["market"] in cfg["tickets"]["multi"]["lotto_markets"] and cfg["tickets"]["multi"]["lotto_leg_prob"][0] <= l["p"] <= cfg["tickets"]["multi"]["lotto_leg_prob"][1]:
            l["why"] = ex(l)
    if T.get("multi_part"):
        for l in T["multi_part"]["legs"]:
            l["game"], l["game_id"] = label, game["game_id"]
    return {"game_id": game["game_id"], "label": label, "home": home, "away": away, "date_et": game["date_et"],
            "start_utc": game["start_utc"], "venue": game.get("venue"), "gates": G, "referees": crew,
            "expected": {t: {"goals": round(lam[t]["lam"], 3), "sog": round(lam[t]["sog_mean"], 1), "pp_min": round(lam[t]["pp_sec"] / 60, 2),
                             "steps": lam[t]["steps"]} for t in (home, away)},
            "sim": summ,
            "fair": {"moneyline": {home: fair(("ml", home, 0.0)), away: fair(("ml", away, 0.0))},
                     "puck_line": {f"{home} -1.5": fair(("spread", home, -1.5)), f"{away} +1.5": fair(("spread", away, 1.5)),
                                   f"{away} -1.5": fair(("spread", away, -1.5)), f"{home} +1.5": fair(("spread", home, 1.5))},
                     "totals": {f"over {l}": fair(("total", "over", l)) for l in (5.5, 6.5)},
                     "regulation": {home: fair(("ml3", home, 0.0)), "draw": fair(("ml3", "draw", 0.0)), away: fair(("ml3", away, 0.0))}},
            "game_lines": lines_priced,
            "goalies": {t: {k: v for k, v in PS.goalies[t].items() if k not in ("saves", "pulled")} for t in (home, away)},
            "tickets": T["tickets"], "pool": T["pool"], "removed": T["removed"][:60], "removed_count": len(T["removed"]),
            "notes": G["notes"] + T.get("notes", []), "projections": sorted(proj, key=lambda x: -x["toi_min"]),
            "paper": paper, "sims": S.n, "gates_ok": bool(gates_ok), "preview": bool(cfg["gates"].get("preview")),
            "_legs": T["legs"], "_multi_part": T.get("multi_part")}


def _site_leg(l: dict) -> dict:
    return {k: l.get(k) for k in ("label", "market", "team", "prob", "price", "book", "matchup", "rung_verified", "why", "game")}


def site_export(slate: dict, cfg) -> dict:
    """What the website shows: tonight's games, their slips and projections. No results, no ledger."""
    games = []
    for g in slate["games"]:
        games.append({
            "id": str(g["game_id"]), "label": g["label"], "home": g["home"], "away": g["away"], "start_utc": g["start_utc"],
            "venue": g["venue"], "paper": g["paper"], "early": bool(g.get("early")), "made_after_start": g.get("made_after_start", False), "notes": g["notes"],
            "goalies": {t: {"name": v["goalie"], "status": v["status"], "ok": v["ok"]} for t, v in g["gates"]["goalies"].items()},
            "lines_ok": {t: v["ok"] for t, v in g["gates"]["lines"].items()},
            "referees": [r["name"] for r in g["referees"]["referees"]],
            "sim": g["sim"], "expected": g["expected"], "fair": g["fair"],
            "game_lines": [{k: l[k] for k in ("book", "market", "side", "line", "price", "model_prob", "implied_prob", "edge", "tier")}
                           for l in g["game_lines"]],
            "saves": {t: {"name": v.get("name"), "expected": v.get("expected_saves"), "pull_prob": v.get("pull_prob")}
                      for t, v in g["goalies"].items()},
            "tickets": [{"id": t["id"], "kind": t["kind"], "title": t["title"], "chance": t["chance"], "miss": t["miss"],
                         "book_price": t.get("book_price"), "lift": t["lift"], "priced": t["priced"], "rungs_verified": t["rungs_verified"],
                         "edge": t.get("edge"), "book": t.get("book"), "kelly_stake": t.get("kelly_stake"),
                         "legs": [_site_leg(l) for l in t["legs"]]}
                        for t in g["tickets"]],
            "removed_count": g["removed_count"],
            "projections": [{k: p[k] for k in ("player", "team", "pos", "toi_min", "line", "pp", "sog", "pts", "goals", "ast", "hits", "blk", "atg")}
                            for p in g["projections"][:40]]})
    multi = [{"id": t["id"], "kind": t["kind"], "title": t["title"], "chance": t["chance"], "miss": t["miss"], "book_price": t.get("book_price"),
              "games": t["games"], "how_chosen": t.get("how_chosen"), "rungs_verified": t["rungs_verified"], "priced": t["priced"],
              "start_utc": t["start_utc"], "includes_early": t.get("includes_early", []),
              "legs": [_site_leg(l) for l in t["legs"]]} for t in slate.get("multi", [])]
    cashed = json.loads(CASHED.read_text()) if CASHED.exists() else {"slips": []}
    return {"date": slate["date"], "made_at": slate["made_at"], "status": slate["status"], "preview": slate.get("preview", False),
            "early": slate.get("early", False), "mixed": slate.get("mixed", False),
            "sims": cfg["sim"]["n_sims"], "floor": cfg["tickets"]["floor_prob"], "games": games, "multi": multi,
            "cashed": cashed["slips"], "skipped": slate["skipped"]}


def run(con, cfg, date_et: str, as_of: str | None = None, include_started: bool = False) -> dict:
    """Every game of the date that has not started (or all of them with include_started, for a late paper run)."""
    as_of = as_of or now_iso()
    tables = context.Tables.load(con, cfg)
    sched = tables.schedule[tables.schedule.date_et == date_et].sort_values("start_utc").to_dict("records")
    lines = store.read(con, "SELECT l.* FROM lines l JOIN (SELECT team, MAX(known_at) k FROM lines WHERE known_at <= ? GROUP BY team) m "
                            "ON l.team = m.team AND l.known_at = m.k", [as_of])
    season = int(sched[0]["season"]) if sched else cfg["seasons"]["current"]
    ctx = context.build(tables, as_of, season, cfg, lines)
    recent = explain.recent_form(tables, as_of)
    preview = bool(cfg["gates"].get("preview"))
    early = preview and bool(cfg["gates"].get("issue_early"))
    fallback = bool(cfg["gates"].get("early_fallback")) and not preview
    games, skipped = [], []
    prev = json.loads(SLATE.read_text()) if SLATE.exists() else {}
    kept = {g["game_id"]: g for g in prev.get("games", [])} if prev.get("date") == date_et else {}
    for g in sched:
        started = g["start_utc"].replace("Z", "+00:00") <= as_of
        if started and not include_started:
            if g["game_id"] in kept:                              # under way: its slips were locked at puck drop and stay on the board
                games.append(kept[g["game_id"]])
            else:
                skipped.append(f"{g['away']} @ {g['home']}: already started")
            continue
        try:
            out = run_game(g, ctx, tables, con, cfg, as_of, recent=recent)
            out["early"] = early
            if fallback and not out["gates_ok"]:                  # not confirmed yet: re-issued as early, on today's personnel
                ecfg = copy.deepcopy(cfg)
                ecfg["gates"]["preview"] = True
                out = run_game(g, ctx, tables, con, ecfg, as_of, recent=recent)
                out["early"] = True
            out["made_after_start"] = bool(started)
            games.append(out)
        except Exception as e:                                    # one game's failure must not lose the slate
            skipped.append(f"{g['away']} @ {g['home']}: not run ({type(e).__name__}: {e})")
    live = [g for g in games if "_legs" in g and not g.get("made_after_start")]
    ready = [{"game_id": g["game_id"], "label": g["label"], "legs": g["_legs"], "multi_part": g["_multi_part"],
              "gates_ok": g["gates_ok"] or preview} for g in live]
    multis = tickets.multi_game(ready, cfg)
    lot = tickets.lotto(ready, cfg)
    if lot is None and fallback:                                  # too few confirmed games for a longshot: early games may join, labelled
        lot = tickets.lotto([{**r, "gates_ok": True} for r in ready], cfg)
        if lot:
            lot["includes_early"] = sorted({l["game"] for l in lot["legs"]} & {g["label"] for g in live if g.get("early")})
    multis += [lot] if lot else []
    starts = {g["game_id"]: g["start_utc"] for g in games}
    for t in multis:
        t["id"] = f"{date_et}-{t['kind']}"
        t["made_at"], t["start_utc"] = as_of, min(starts[i] for i in t["game_ids"])
    kept_multi = prev.get("multi", []) if prev.get("date") == date_et else []
    locked = {t["kind"]: t for t in kept_multi if t["start_utc"].replace("Z", "+00:00") <= as_of}   # its first game is under way
    multis = [locked.get(t["kind"], t) for t in multis] + [t for k, t in locked.items() if k not in {m["kind"] for m in multis}]
    for g in games:
        g.pop("_legs", None); g.pop("_multi_part", None)
    mixed = any(g.get("early") for g in games) and not early
    slate = {"date": date_et, "made_at": as_of, "games": games, "multi": multis, "skipped": skipped, "preview": preview and not early,
             "early": early, "mixed": mixed,
             "status": ("gated where goalies and lines are confirmed; the rest are early slips on the latest personnel, re-run before puck drop"
                        if mixed else"early card: issued before goalies and lines were confirmed; each game is re-issued once they are" if early else
                        "preview: goalies and lines are not all confirmed yet, so these slips are not final and are not being graded"
                        if preview else "test slate: no NHL market has been validated against closing lines yet")}
    OUT.mkdir(exist_ok=True)
    SLATE.write_text(json.dumps(slate, indent=1, default=str))
    SITE.write_text(json.dumps(site_export(slate, cfg), indent=1, default=str))
    if preview and not early:
        return slate                                              # a preview is shown, never logged or graded
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"tickets": []}
    by_id = {t["id"]: t for t in ledger["tickets"]}
    entries = [({k: v for k, v in t.items() if k != "pairs"}, g["paper"], g["made_after_start"], bool(g.get("early"))) for g in games for t in g["tickets"]]
    entries += [(t, not t["rungs_verified"], False, early) for t in multis]
    reissued = {g["game_id"] for g in games if g["start_utc"].replace("Z", "+00:00") > as_of}
    fresh = {t["id"] for t, *_ in entries}
    for tid in [i for i, t in by_id.items() if t.get("game_id") in reissued and i not in fresh and not t.get("graded")]:
        del by_id[tid]                                            # a slip this run no longer issues for an open game is withdrawn
    for t, paper, late, is_early in entries:
        old = by_id.get(t["id"])
        if old and (old.get("graded") or old["start_utc"].replace("Z", "+00:00") <= as_of):
            continue                                              # locked at puck drop
        if t["start_utc"].replace("Z", "+00:00") <= as_of and not late:
            continue
        by_id[t["id"]] = {**t, "paper": paper, "made_after_start": late, "graded": False, "early": is_early}
    ledger["tickets"] = sorted(by_id.values(), key=lambda t: (t["start_utc"], t["id"]))
    LEDGER.write_text(json.dumps(ledger, indent=1, default=str))
    return slate
