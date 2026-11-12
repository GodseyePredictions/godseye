"""Daily runner.

  python3 -m nba.run_slate                      # the whole slate, in order: refresh data, availability gate,
                                                #   game script, minutes, player models, simulation, tickets
  python3 -m nba.run_slate game GAME_ID         # re-run one game when news breaks (late-changing data only)
  python3 -m nba.run_slate watch                # re-check availability; re-run only games where a status changed
  python3 -m nba.run_slate place TICKET_ID [STAKE] [PRICE]   # mark a ticket as placed: timestamped and locked
  python3 -m nba.run_slate grade [YYYY-MM-DD]   # nightly grading and report card
Add --no-refresh to skip the data pull (uses what is already in the database).
"""
import json
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from nba import availability, grading, ledger, refresh, sgp, sources
from nba import player_sim as ps
from nba import props
from nba.config import CONFIG
from nba.ids import TEAMS, norm
from nba.pipeline import Pipeline
from nba.store import HERE, PointInTime, connect, load_frames, upsert

OUT = HERE / "output"


def slate_games(con, only: str | None = None) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    if only:
        return pd.read_sql("SELECT * FROM schedule WHERE game_id=?", con, params=[only])
    g = pd.read_sql("SELECT * FROM schedule WHERE tip_utc > ? AND tip_utc < ? ORDER BY tip_utc", con,
                    params=[now.isoformat(), (now + timedelta(hours=20)).isoformat()])
    done = set(pd.read_sql("SELECT game_id FROM games", con).game_id)
    return g[~g.game_id.isin(done)]


def run_gate(con, games: pd.DataFrame, notes: dict) -> pd.DataFrame:
    """Availability for every game on the slate from what is known right now; saved with a timestamp."""
    now = ledger.now()
    pit = PointInTime(now, con)
    out = []
    for g in games.itertuples():
        d = availability.gate(pit, {"game_id": g.game_id, "date_et": g.date_et, "home_id": g.home_id, "away_id": g.away_id,
                                    "home_name": TEAMS[g.home][0], "away_name": TEAMS[g.away][0]}, notes)
        out.append(d)
    gate = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if len(gate):
        rows = gate.dropna(subset=["player_id"]).assign(known_at=now)[
            ["game_id", "player_id", "team_id", "status", "reason", "minutes_restriction", "games_since_return", "games_missed",
             "source_time", "known_at"]].to_dict("records")
        upsert(con, "availability", rows)
    return gate


def previous_gate(con, game_ids, before: str) -> pd.DataFrame:
    q = ",".join("?" * len(game_ids))
    a = pd.read_sql(f"SELECT * FROM availability WHERE game_id IN ({q}) AND known_at < ?", con, params=[*game_ids, before])
    if a.empty:
        return a
    last = a.groupby("game_id").known_at.transform("max")
    return a[a.known_at == last].assign(name="", projected=1)


def officials_tonight(con, games: pd.DataFrame) -> pd.DataFrame:
    """Tonight's crews from the assignments page, matched to games by the two city names."""
    ra = pd.read_sql("SELECT * FROM ref_assignments", con)
    rows = []
    city = {norm(TEAMS[a][0].rsplit(" ", 1)[0] if a not in ("POR",) else "Portland"): a for a in TEAMS}
    city.update({"la lakers": "LAL", "la clippers": "LAC", "los angeles lakers": "LAL", "los angeles clippers": "LAC",
                 "golden state": "GS", "new york": "NY", "new orleans": "NO", "san antonio": "SA", "oklahoma city": "OKC",
                 "portland": "POR", "utah": "UTAH", "washington": "WSH", "brooklyn": "BKN", "phoenix": "PHX"})
    for g in games.itertuples():
        d = ra[ra.date_et == g.date_et]
        for r in d.itertuples():
            a, h = [city.get(norm(x)) for x in r.matchup.split("@")]
            if a == g.away and h == g.home:
                rows.append({"game_id": g.game_id, "name": r.name, "known_at": r.known_at})
    return pd.DataFrame(rows, columns=["game_id", "name", "known_at"])


def offers_for(con, game_id: str, cfg=CONFIG) -> pd.DataFrame:
    """The latest price shown for every rung and line of this game, from the first preferred book that has
    any. Only these can be legs."""
    o = pd.read_sql("SELECT * FROM odds WHERE game_id=? AND known_at < ?", con, params=[game_id, ledger.now()])
    for book in cfg["odds_books"]:
        ob = o[o.book.str.contains(book, case=False)]
        if ob.empty:
            continue
        ob = ob[ob.known_at >= ob.known_at.max()[:15]]            # the latest pull only (same ten minutes)
        return ob.sort_values("known_at").drop_duplicates(["market", "player_name", "side", "line"], keep="last")
    return o.iloc[0:0]


def multi_game_slips(per_game: dict, cfg=CONFIG) -> list:
    """Slips across several games: the best n-leg ticket from each of the strongest games. Games are
    independent of each other, so the slip's chance is the product of each game's counted joint chance."""
    from common.odds_math import decimal_to_american, fair_american
    out = []
    for n in cfg["multi_legs_per_game"]:
        have = sorted(((t["joint"], gid, t) for gid, d in per_game.items() for t in [d.get(n)] if t), key=lambda x: -x[0])
        pick = have[:cfg["multi_games"]]
        if len(pick) < cfg["multi_games"]:
            continue
        joint = float(np.prod([p[0] for p in pick]))
        dec = [p[2]["decimal"] for p in pick]
        price = float(np.prod(dec)) if all(dec) else None
        out.append({"type": f"multi_{n * len(pick)}", "n_legs": n * len(pick), "joint": joint, "fair_price": fair_american(joint),
                    "book_price": decimal_to_american(price) if price else None, "ev": joint * price - 1 if price else None,
                    "price_is_estimate": True,
                    "parts": [{"game_id": gid, "matchup": per_game[gid]["matchup"], "joint": j,
                               "legs": [{k: v for k, v in l.items() if k not in ("hits", "active")} for l in t["legs"]]}
                              for j, gid, t in pick]})
    return out


def projection_rows(game_id, rows: pd.DataFrame, summary: pd.DataFrame, gate: pd.DataFrame) -> list:
    st = gate.dropna(subset=["player_id"]).set_index("player_id").status.to_dict() if len(gate) else {}
    R = rows.set_index("player_id")
    out = []
    for s in summary.itertuples():
        r = R.loc[s.player_id]
        out.append({"game_id": game_id, "player_id": s.player_id, "name": s.name, "team_id": s.team_id, "status": st.get(s.player_id, "unknown"),
                    "role": s.role, "role_change": r.role_change_reason, "p_play": float(s.p_play), "min_mean": float(s.min_mean),
                    "min_p10": float(s.min_p10), "min_p50": float(s.min_p50), "min_p90": float(s.min_p90),
                    **{k: float(getattr(s, k)) for k in ps.STATS},
                    "exp_fg_pct": float(r.exp_fg_pct), "base_fg_pct": float(r.base_fg_pct), "exp_3p_pct": float(r.exp_3p_pct),
                    "base_3p_pct": float(r.base_3p_pct), "gate_pts": int(r.gate_pts), "gate_fg3m": int(r.gate_fg3m),
                    "blowout_exposure": float(s.blowout_exposure),
                    "adjustments": json.dumps(props.explain(r) + [f"baseline sample: {int(r.base_sample_min)} minutes (this season + last, weighted), "
                                                                  f"last {int(r.l5_n or 0)} games for form"]),
                    "inout_notes": r.io_notes})
    return out


def run(con, only: str | None = None, do_refresh: bool = True, cfg=CONFIG, n_sims: int | None = None, quiet=False) -> dict:
    ledger.init(con)
    started = ledger.now()
    info = {}
    if do_refresh:
        info["refresh"] = refresh.gameday(con) if only else refresh.daily(con)
    games = slate_games(con, only)
    if games.empty:
        return {"message": "no games to run", **info}
    ids = refresh.idmap(con)
    try:
        notes = sources.espn_injury_notes(ids) if do_refresh else {}
    except Exception as e:           # the notes only add minutes restrictions; the gate still runs without them
        notes, info["notes_error"] = {}, str(e)
    before = previous_gate(con, list(games.game_id), started)
    gate = run_gate(con, games, notes)
    changed = availability.changes(before, gate) if len(before) else []
    frames = load_frames(con)
    off = officials_tonight(con, games)
    if len(off):
        frames["officials"] = pd.concat([frames["officials"], off], ignore_index=True)
    known = gate.dropna(subset=["player_id"])
    rosters = known[["game_id", "team_id", "player_id", "name", "pos"]]
    live = {"out": {}, "ques": {}, "filed": {}}
    for gid, d in known.groupby("game_id"):
        live["out"][gid] = set(d[d.status.isin(["out", "doubtful"])].player_id)
        live["ques"][gid] = set(d[d.status == "questionable"].player_id)
        live["filed"][gid] = set(d[d.status != "unknown"].team_id)
    pending = games.assign(completed=0)
    pl = Pipeline(frames, pending, rosters, live, cfg)
    models = pl.fit(9999)
    run_id, run_at = ledger.new_run(con, "game" if only else "slate", games.date_et.iloc[0], n_sims or cfg["n_sims"])
    names = {**dict(zip(games.home_id, games.home)), **dict(zip(games.away_id, games.away))}
    restr = known.set_index("player_id").minutes_restriction
    pl.D["minutes_restriction"] = pl.D.player_id.map(restr[~restr.index.duplicated()])
    slate, texts, per_game, book_used = [], [], {}, None
    (HERE / "data" / "sims").mkdir(parents=True, exist_ok=True)
    for g in games.itertuples():
        gg = gate[gate.game_id == g.game_id]
        inputs, sims, players = pl.run_game(g.game_id, models, n_sims)
        if players is None:
            texts.append(f"=== {g.away} @ {g.home} ===\n  not enough rostered players with history to simulate; no bet")
            continue
        sims.save(HERE / "data" / "sims" / f"{g.game_id}_{run_id}.npz")       # the exact games the player simulation used
        card = sgp.script_card(inputs, sims, players, cfg)
        offers = offers_for(con, g.game_id, cfg)
        legs = sgp.build_legs(offers, sims, players, gg, names, cfg)
        preview = False
        if offers.empty and cfg["preview_tickets_without_prices"]:
            # model-only tickets: standard thresholds for confirmed players, no price, not checked against the book
            okp = set(gg[gg.ticket_eligible == 1].player_id)
            cand = players.players[players.players.player_id.isin(okp) & (players.players.e_min >= cfg["preview_min_minutes"])]
            legs = sgp.build_legs(sgp.grid_offers(cand, cfg), sims, players, gg, names, cfg)
            built = sgp.build_tickets(legs, sims, card, cfg, require_price=False)
            built["tickets"] = [t for t in built["tickets"] if t["type"] != "game_script"]
            built["notes"] = [n for n in built["notes"] if not n.startswith("game_script")]
            for t in built["tickets"]:
                t["type"] = "preview_" + t["type"]
            built["notes"].insert(0, "MODEL-ONLY PREVIEW: no book prices are loaded. Thresholds are standard milestones, not rungs read "
                                     "from bet365. Check each rung exists and its price before placing.")
            preview = True
        elif offers.empty:
            built = {"tickets": [], "singles": [], "notes": ["no bet: no book prices are loaded for this game "
                     "(set ODDS_API_KEY or load a bet365 sheet with: python3 -m nba.refresh csv FILE " + g.game_id + ")"]}
        else:
            built = sgp.build_tickets(legs, sims, card, cfg, require_price=True)
        if not preview and not offers.empty:
            from common import tickets as tk
            pool = sgp.floor_rungs([l for l in legs if sgp.sgp_eligible(l, cfg, True)[0]])
            per_game[g.game_id] = {"matchup": card["matchup"],
                                   **{n: tk.best_ticket(pool, n, cfg, True) if len(pool) >= n else None for n in cfg["multi_legs_per_game"]}}
            book_used = offers.book.iloc[0]
        text = sgp.slip_text(card, built, gg)
        summ = ps.summary(players)
        prow = projection_rows(g.game_id, inputs["rows"], summ, gg)
        if only:
            ledger.supersede(con, g.game_id)
        tids = ledger.save_game(con, run_id, run_at, g.game_id, card, text, prow, legs, built, lambda l: sgp.sgp_eligible(l, cfg))
        for t, tid in zip(built["tickets"], tids):
            text += f"\n  ticket id for [{t['type']}]: {tid}"
        texts.append(text)
        slate.append({"card": card, "projections": prow, "preview": preview, "tip_utc": g.tip_utc, "home": g.home, "away": g.away,
                      "home_id": g.home_id, "away_id": g.away_id,
                      "tickets": [{"id": tid, "type": t["type"], "joint": t["joint"], "book_price": t["book_price"],
                                   "fair_price": t["fair_price"], "ev": t["ev"], "price_is_estimate": bool(t.get("price_is_estimate")),
                                   "legs": [{k: v for k, v in l.items() if k not in ("hits", "active")} for l in t["legs"]]}
                                  for t, tid in zip(built["tickets"], tids)],
                      "singles": built.get("singles", []), "notes": built["notes"],
                      "availability": gg[["name", "status", "reason", "minutes_restriction", "games_since_return", "ticket_eligible"]]
                      .to_dict("records")})
    # which projections moved because of a status change
    moved = []
    for c in changed:
        prev = pd.read_sql("SELECT player_id, name, pts, min_mean FROM nba_projections WHERE game_id=? AND run_id != ? "
                           "AND run_at = (SELECT MAX(run_at) FROM nba_projections WHERE game_id=? AND run_id != ?)",
                           con, params=[c["game_id"], run_id, c["game_id"], run_id]).set_index("player_id")
        new = pd.read_sql("SELECT player_id, name, pts, min_mean FROM nba_projections WHERE game_id=? AND run_id=?", con,
                          params=[c["game_id"], run_id]).set_index("player_id")
        diff = [f"{new.name[p]}: minutes {prev.min_mean[p]:.1f} -> {new.min_mean[p]:.1f}, points {prev.pts[p]:.1f} -> {new.pts[p]:.1f}"
                for p in new.index.intersection(prev.index)
                if abs(new.min_mean[p] - prev.min_mean[p]) >= 1.0 or abs(new.pts[p] - prev.pts[p]) >= 0.5]
        gone = [prev.name[p] for p in prev.index.difference(new.index)]
        c["projections_changed"] = diff + [f"{n}: removed (no longer projected)" for n in gone]
        moved.append(c)
        upsert(con, "nba_status_changes", [{"seen_at": run_at, "game_id": c["game_id"], "player_id": c["player_id"], "name": c["name"],
                                            "from_status": c["from"], "to_status": c["to"],
                                            "projections_changed": json.dumps(c["projections_changed"])}])
    OUT.mkdir(exist_ok=True)
    multi = multi_game_slips(per_game, cfg) if not only else []
    for m in multi:
        tid = ledger.uuid.uuid4().hex[:12]
        m["id"] = tid
        upsert(con, "nba_tickets", [{
            "ticket_id": tid, "run_id": run_id, "run_at": run_at, "game_id": "multi:" + games.date_et.iloc[0], "type": m["type"],
            "leg_ids": json.dumps([l["id"] for part in m["parts"] for l in part["legs"]]),
            "slip_json": json.dumps([{"description": l["label"], "odds": l["price"], "game": part["matchup"]}
                                     for part in m["parts"] for l in part["legs"]]),
            "joint_prob": m["joint"], "book_price": m["book_price"], "price_is_estimate": 1, "fair_price": m["fair_price"],
            "ev": m["ev"], "status": "proposed", "placed_at": None, "stake": None, "locked": 0}])
        texts.append(f"=== MULTI-GAME SLIP: {m['n_legs']} props across {len(m['parts'])} games ===\n"
                     f"  joint {m['joint']:.1%} | fair {m['fair_price']:+d} | product of leg prices "
                     + (f"{m['book_price']:+d}" if m["book_price"] else "n/a") + f"  | ticket id {tid}\n"
                     + "\n".join(f"  {part['matchup']} ({part['joint']:.0%}): " + "; ".join(l["label"] for l in part["legs"]) for part in m["parts"]))
    payload = {"run_id": run_id, "run_at": run_at, "n_sims": n_sims or cfg["n_sims"], "games": slate, "status_changes": moved,
               "multi": multi, "book": book_used}
    (OUT / "nba_slate.json").write_text(json.dumps(_clean(payload), indent=1, default=str))
    if not only:
        write_site_file(payload)
    write_track_file(con)
    ids.write_review()
    if not quiet:
        print("\n\n".join(texts))
        for c in moved:
            print(f"\nSTATUS CHANGE {c['name']}: {c['from']} -> {c['to']}" + ("  (his legs are removed)" if c["remove_legs"] else ""))
            for line in c["projections_changed"]:
                print("   ", line)
    return {"run_id": run_id, "games": len(slate), "status_changes": moved, "texts": texts, **info}


def _clean(o):
    """NaN is not valid JSON for a browser: write null instead."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


def write_site_file(payload: dict) -> None:
    """A slim copy of the slate for the website's NBA page (src/components/NbaApp.tsx reads it)."""
    keep_leg = ("label", "market", "line", "side", "p", "p_blowout", "p_close", "price", "reason", "name")
    games = []
    for g in payload["games"]:
        abbr = {g["home_id"]: g["home"], g["away_id"]: g["away"]}
        games.append({
            "id": g["card"]["game_id"], "home": g["home"], "away": g["away"], "tip_utc": g["tip_utc"], "preview": g["preview"],
            "card": g["card"], "notes": g["notes"],
            "tickets": [{"id": t["id"], "type": t["type"], "joint": t["joint"], "book_price": t["book_price"], "fair_price": t["fair_price"],
                         "ev": t["ev"], "price_is_estimate": t["price_is_estimate"],
                         "naive": float(np.prod([l["p"] for l in t["legs"]])),
                         "legs": [{k: l.get(k) for k in keep_leg} for l in t["legs"]]} for t in g["tickets"]],
            "singles": [{k: s.get(k) for k in keep_leg + ("ev", "kelly_stake")} for s in g["singles"][:8]],
            "players": [{k: (round(p[k], 2) if isinstance(p[k], float) else p[k]) for k in
                         ("name", "team_id", "status", "role", "role_change", "p_play", "min_mean", "min_p10", "min_p90", "pts", "reb",
                          "ast", "fg3m", "stl", "blk", "gate_pts", "gate_fg3m", "blowout_exposure", "inout_notes")}
                        | {"adjustments": json.loads(p["adjustments"])[:6], "team": abbr.get(p["team_id"], "")}
                        for p in sorted(g["projections"], key=lambda x: -x["min_mean"]) if p["min_mean"] >= 10],
            "availability": [a for a in g["availability"] if a["status"] != "confirmed_in"]})
    site = {"run_at": payload["run_at"], "n_sims": payload["n_sims"], "games": games, "book": payload.get("book"),
            "multi": [{**m, "parts": [{**p, "legs": [{k: l.get(k) for k in keep_leg} for l in p["legs"]]} for p in m["parts"]]}
                      for m in payload.get("multi", [])]}
    (OUT / "nba_site.json").write_text(json.dumps(_clean(site), default=str, allow_nan=False))


def write_track_file(con) -> dict:
    """Every slip issued, by slate, with its result once graded (output/nba_track.json, read by the website).
    For each date the last full-slate run is the issued one. Model-only preview tickets are not tracked."""
    runs = pd.read_sql("SELECT slate_date, run_id, run_at FROM nba_runs WHERE kind='slate' ORDER BY run_at", con)
    runs = runs.drop_duplicates("slate_date", keep="last")
    sched = pd.read_sql("SELECT game_id, away || ' @ ' || home m FROM schedule", con).set_index("game_id").m.to_dict()
    slates, totals = [], {}
    for r in runs.itertuples():
        T = pd.read_sql("SELECT * FROM nba_tickets WHERE run_id=? AND type NOT LIKE 'preview%'", con, params=[r.run_id])
        if T.empty:
            continue
        L = pd.read_sql("SELECT leg_id, label, model_prob, price, result, actual FROM nba_legs WHERE run_id=?", con,
                        params=[r.run_id]).set_index("leg_id")
        tickets = []
        for t in T.itertuples():
            legs = [{"label": L.label[i], "p": float(L.model_prob[i]), "price": None if pd.isna(L.price[i]) else float(L.price[i]),
                     "result": L.result[i] if isinstance(L.result[i], str) else "pending",
                     "actual": None if pd.isna(L.actual[i]) else float(L.actual[i])} for i in json.loads(t.leg_ids) if i in L.index]
            res = [l["result"] for l in legs]
            result = ("pending" if "pending" in res else "lost" if "lost" in res else
                      "void" if all(x == "void" for x in res) else "won")
            tickets.append({"id": t.ticket_id, "game": sched.get(t.game_id, "Multi-game"), "type": t.type, "result": result,
                            "joint": float(t.joint_prob), "price": None if pd.isna(t.book_price) else float(t.book_price),
                            "placed": t.status == "placed", "hit": sum(x == "won" for x in res), "n": len(legs), "legs": legs})
            if result in ("won", "lost"):
                d = totals.setdefault(t.type, {"tickets": 0, "won": 0, "expected": 0.0, "units": 0.0})
                d["tickets"] += 1; d["won"] += result == "won"; d["expected"] += float(t.joint_prob)
                if tickets[-1]["price"]:
                    px = tickets[-1]["price"]
                    d["units"] += ((px / 100 if px > 0 else 100 / -px) if result == "won" else -1.0)
        graded = [t for t in tickets if t["result"] in ("won", "lost")]
        slates.append({"date": r.slate_date, "issued_at": r.run_at, "tickets": tickets, "graded": len(graded),
                       "won": sum(t["result"] == "won" for t in graded)})
    out = {"made_at": ledger.now(), "slates": slates[::-1], "totals": totals}
    (OUT / "nba_track.json").write_text(json.dumps(_clean(out), default=str, allow_nan=False))
    return out


def watch(con, cfg=CONFIG) -> dict:
    """Pull the late-changing data, and re-run only the games where someone's status changed."""
    refresh.gameday(con)
    games = slate_games(con)
    if games.empty:
        return {"message": "no games to watch"}
    before = previous_gate(con, list(games.game_id), ledger.now())
    gate = run_gate(con, games, {})
    ch = availability.changes(before, gate) if len(before) else []
    out = {"changes": ch, "reruns": []}
    for gid in sorted({c["game_id"] for c in ch}):
        print(f"status changed in game {gid}: re-running")
        out["reruns"].append(run(con, only=gid, do_refresh=False, cfg=cfg)["run_id"])
    if not ch:
        print("no status changes")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    con = connect()
    do_refresh = "--no-refresh" not in sys.argv
    cmd = args[0] if args else "slate"
    if cmd == "slate":
        run(con, do_refresh=do_refresh)
    elif cmd == "game":
        run(con, only=args[1], do_refresh=do_refresh)
    elif cmd == "watch":
        watch(con)
    elif cmd == "place":
        print(ledger.place(con, args[1], float(args[2]) if len(args) > 2 else None, float(args[3]) if len(args) > 3 else None)["message"])
    elif cmd == "grade":
        d = args[1] if len(args) > 1 else (datetime.now(timezone.utc) - timedelta(hours=29)).date().isoformat()
        refresh.daily(con) if do_refresh else None
        print(grading.grade_date(con, d)["text"])
        write_track_file(con)
