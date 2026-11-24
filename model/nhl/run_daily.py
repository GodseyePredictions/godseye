"""The NHL daily runner. Phase 1 stages: ingest and derived tables. Later phases add gates, the game
sim, props, correlation, tickets and grading after these.

Run from model/:

    python3 -m nhl.run_daily nightly            # schedule, finished games, MoneyPuck xG, rosters, then every derived table
    python3 -m nhl.run_daily gameday [DATE]     # goalies, lines and PP units, referees, odds and ladders; refreshes the TOI projection
    python3 -m nhl.run_daily watch [DATE]       # from 90 minutes before the first puck drop, re-run gameday every 30 minutes until goalies are confirmed
    python3 -m nhl.run_daily derive [AS_OF]     # rebuild the derived tables as of a UTC time (default: now)
    python3 -m nhl.run_daily status
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pandas as pd

from common.http import FetchError
from nhl import ids, store
from nhl.config import CONFIG
from nhl.features import arena_bias, game_logs, player_rates, schedule as schedule_spots, team_rates, toi
from nhl.ingest import dailyfaceoff, moneypuck, nhl_api, nst, odds, refs

GAME_TABLES = ("games", "team_game", "team_game_strength", "team_game_score", "player_game_strength", "goalie_game")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_et() -> str:
    return (now_utc() - timedelta(hours=5)).date().isoformat()


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ nightly ingest
def ingest_schedule(con, cfg, seasons) -> pd.DataFrame:
    for s in seasons:
        rows = nhl_api.season_schedule(s, store.RAW, cfg, current=(s == cfg["seasons"]["current"]))
        store.write(con, "schedule", rows)
        log(f"schedule {s}: {len(rows)} games")
    return store.read(con, "SELECT * FROM schedule")


def ingest_shots(con, cfg, seasons) -> dict:
    """MoneyPuck shots per season into the shots table; returns {game_id: DataFrame}."""
    by_game = {}
    for s in seasons:
        try:
            d = moneypuck.shots(s, store.RAW, cfg, current=(s == cfg["seasons"]["current"]))
        except FetchError as e:
            log(f"MoneyPuck shots {s}: not available ({e}); games are built without xG and rebuilt when it arrives")
            continue
        con.execute("DELETE FROM shots WHERE season=?", [s])
        d.to_sql("shots", con, if_exists="append", index=False)
        con.commit()
        by_game.update({int(g): x for g, x in d.groupby("game_id")})
        log(f"MoneyPuck shots {s}: {len(d)} shots in {d.game_id.nunique()} games")
    return by_game


def save_players(con, players: dict):
    con.executemany("""INSERT INTO players (player_id, name, pos, team, last_date) VALUES (?,?,?,?,?)
                       ON CONFLICT(player_id) DO UPDATE SET name=excluded.name, pos=excluded.pos, team=excluded.team,
                       last_date=excluded.last_date WHERE excluded.last_date >= players.last_date""",
                    [[p["player_id"], p["name"], p["pos"], p["team"], p["last_date"]] for p in players.values()])
    con.commit()


def ingest_games(con, cfg, sched: pd.DataFrame, shots_by_game: dict, workers: int = 6, force: bool = False) -> int:
    """Fetch and build every finished game that is new, was built before its xG arrived, is recent enough to be
    corrected, or (this season) was built without a shift chart that may have been posted since."""
    have = store.read(con, "SELECT game_id, xg_shots, toi_source FROM games").set_index("game_id")
    recent = (now_utc().date() - timedelta(days=2)).isoformat()
    todo = []
    for r in sched[sched.state.isin(list(nhl_api.FINAL_STATES))].to_dict("records"):
        g = r["game_id"]
        if force or g not in have.index or r["date_et"] >= recent or (have.at[g, "xg_shots"] == 0 and g in shots_by_game) \
                or (have.at[g, "toi_source"] == "pbp" and r["season"] == cfg["seasons"]["current"]):
            todo.append(r)
    if not todo:
        return 0
    log(f"games to build: {len(todo)}")

    def pull(r):
        try:
            return r, nhl_api.fetch_game(r["game_id"], r["date_et"], store.RAW, cfg)
        except FetchError as e:
            return r, e

    def pull_toi(d):
        try:
            return nhl_api.toi_by_strength(d, store.RAW, cfg)
        except FetchError as e:
            log(f"league TOI {d}: {e}")
            return []

    with ThreadPoolExecutor(workers) as ex:
        for rows in ex.map(pull_toi, sorted({r["date_et"] for r in todo})):
            store.write(con, "toi_official", rows)
        official = store.read(con, "SELECT game_id, player_id, ev, pp, sh FROM toi_official")
        official = {g: {int(p): (e, pp, sh) for p, e, pp, sh in zip(x.player_id, x.ev, x.pp, x.sh)} for g, x in official.groupby("game_id")}
        players, built, t0 = {}, 0, time.time()
        for r, raw in ex.map(pull, todo):
            if isinstance(raw, Exception):
                log(f"game {r['game_id']}: {raw}")
                continue
            game = nhl_api.parse_pbp(raw["pbp"])
            if game["state"] not in nhl_api.FINAL_STATES:
                continue
            shifts = nhl_api.parse_shifts(raw["shifts"], game["seconds"])
            out = game_logs.build_game(game, shifts, shots_by_game.get(game["game_id"]), official.get(game["game_id"], {}), cfg)
            for t in GAME_TABLES:
                con.execute(f"DELETE FROM {t} WHERE game_id=?", [game["game_id"]])
                store.write(con, t, out[t])
            offs, scr = nhl_api.parse_rail(raw["rail"], game)
            known = out["games"][0]["known_at"]
            store.write(con, "officials", [{**o, "date_et": game["date_et"], "known_at": known} for o in offs])
            store.write(con, "scratches", [{**s, "date_et": game["date_et"], "known_at": known} for s in scr])
            for p in out["players"]:
                if p["player_id"] not in players or p["last_date"] >= players[p["player_id"]]["last_date"]:
                    players[p["player_id"]] = p
            built += 1
            if built % 500 == 0:
                log(f"  built {built} games in {time.time() - t0:.0f}s")
        save_players(con, players)
    return built


def ingest_rosters(con, cfg, sched: pd.DataFrame):
    season = cfg["seasons"]["current"]
    day = today_et()
    for team in sorted(set(sched[sched.season == season].home)):
        try:
            rows = nhl_api.roster(team, store.RAW, cfg)
        except FetchError as e:
            log(f"roster {team}: {e}")
            continue
        save_players(con, {r["player_id"]: {**r, "last_date": day} for r in rows})


def ingest_nst(con, cfg):
    folder = store.MANUAL / "nst"
    files = sorted(folder.glob("*.csv")) if folder.exists() else []
    for f in files:
        try:
            log(f"NST export {f.name}: {store.write(con, 'nst', nst.read_export(f))} rows")
        except ValueError as e:
            log(f"NST export rejected: {e}")
    if not files:
        log("NST: no hand exports in data/manual/nst/ (the site refuses automated requests; see ingest/nst.py)")


# ------------------------------------------------------------------ derived tables
def derive(con, cfg, as_of: str | None = None) -> dict:
    """Rebuild every derived table from rows known before `as_of` and save them as the current snapshot."""
    as_of = as_of or now_utc().isoformat(timespec="seconds")
    sched = store.read(con, "SELECT * FROM schedule")
    if not con.execute("SELECT 1 FROM games LIMIT 1").fetchone():
        log("derive: no finished games in the store yet; run `nightly` first")
        return {}
    day = (datetime.fromisoformat(as_of.replace("Z", "+00:00")) - timedelta(hours=5)).date().isoformat()
    past = sched[sched.date_et <= day]
    season = int(past.season.max()) if len(past) else cfg["seasons"]["current"]
    tgs = store.before(con, "team_game_strength", as_of)
    tg = store.before(con, "team_game", as_of)
    games = store.before(con, "games", as_of)
    pgs = store.before(con, "player_game_strength", as_of, "season >= ?", [season - 1])
    gg = store.before(con, "goalie_game", as_of)
    offs = store.before(con, "officials", as_of)
    out = {"team_rates": team_rates.build(tgs, season, cfg),
           "player_rates": player_rates.build(pgs, season, cfg),
           "goalie_rates": player_rates.goalies(gg, season, cfg),
           "schedule_spots": schedule_spots.build(sched, ids.TEAMS, cfg),
           "arena_bias": arena_bias.build(tg, games, sched[sched.neutral == 1].game_id, cfg),
           "ref_rates": refs.ref_rates(offs, tg, cfg)}
    lines = store.read(con, "SELECT l.* FROM lines l JOIN (SELECT team, MAX(known_at) k FROM lines WHERE known_at <= ? GROUP BY team) m "
                            "ON l.team = m.team AND l.known_at = m.k", [as_of])
    tr = out["team_rates"]
    pp_sec = dict(zip(tr[tr.strength == "pp"].team, tr[tr.strength == "pp"].toi_pg))
    out["toi_projection"] = toi.project(pgs, season, cfg, lines, pp_sec, as_of)
    for name, df in out.items():
        df.assign(as_of=as_of).to_sql(name, con, if_exists="replace", index=False)
    con.commit()
    log(f"derived as of {as_of} (season {season}): " + ", ".join(f"{k} {len(v)}" for k, v in out.items()))
    return out


def nightly(con, cfg, force: bool = False):
    seasons = cfg["seasons"]["history"] + [cfg["seasons"]["current"]]
    sched = ingest_schedule(con, cfg, seasons)
    shots = ingest_shots(con, cfg, seasons)
    log(f"built {ingest_games(con, cfg, sched, shots, force=force)} games")
    ingest_rosters(con, cfg, sched)
    ingest_nst(con, cfg)
    derive(con, cfg)


# ------------------------------------------------------------------ game day
def gameday(con, cfg, date_et: str | None = None) -> dict:
    """Goalies, lines and PP units, referees, odds and ladders for one date. Returns what is confirmed."""
    date_et = date_et or today_et()
    rows = nhl_api.season_schedule(cfg["seasons"]["current"], store.RAW, cfg, current=True)
    store.write(con, "schedule", rows)
    games = [r for r in rows if r["date_et"] == date_et]
    index = ids.PlayerIndex(store.read(con, "SELECT * FROM players").to_dict("records"))
    report = {"date": date_et, "games": len(games), "notes": []}
    if not games:
        log(f"{date_et}: no games")
        return report
    try:
        g = dailyfaceoff.attach_ids(dailyfaceoff.goalies(date_et, store.RAW, cfg), index, "goalie")
        store.write(con, "goalie_starts", g)
        report["goalies"] = {r["team"]: (r["goalie"], r["status"]) for r in g}
    except (FetchError, dailyfaceoff.PageChanged) as e:
        report["notes"].append(f"starting goalies not read: {e}")
    lined = 0
    for team in sorted({t for r in games for t in (r["home"], r["away"])}):
        try:
            L = dailyfaceoff.attach_ids(dailyfaceoff.lines(team, store.RAW, cfg), index, "player")
            store.write(con, "lines", L)
            lined += 1
        except (FetchError, dailyfaceoff.PageChanged) as e:
            report["notes"].append(f"lines for {team} not read: {e}")
    report["teams_with_lines"] = lined
    try:
        a = refs.assignments(date_et, store.RAW, cfg)
        store.write(con, "ref_assignments", a)
        report["games_with_referees"] = len({r["home"] for r in a})
    except FetchError as e:
        report["notes"].append(f"referee assignments not read: {e}")
    prices, rejected = [], []
    key = os.environ.get(cfg["sources"]["odds_api_key_env"])
    if key:
        try:
            tag = now_utc().strftime("%Y%m%dT%H%M")
            for ev in odds.api_events(key, store.RAW, cfg):
                doc, at = odds.api_event_odds(key, ev["id"], store.RAW, cfg, tag)
                prices += odds.rows_from_api(doc, at)
        except FetchError as e:
            report["notes"].append(f"The Odds API not read: {e}")
    else:
        report["notes"].append(f"no {cfg['sources']['odds_api_key_env']} in the environment: no API odds")
    folder = store.MANUAL / "bet365"
    for f in sorted(folder.glob(f"{date_et}*.csv")) if folder.exists() else []:
        good, bad = odds.read_csv(f.read_text(encoding="utf-8-sig"))
        prices += good
        rejected += [f"{f.name}: {b}" for b in bad]
    good, bad = odds.resolve(prices, rows, index, None)
    store.write(con, "odds", good)
    report["odds_rows"], report["odds_rejected"] = len(good), rejected + bad
    if index.unmatched:
        report["unmatched_names"] = sorted({f"{n} ({t})" for n, t in index.unmatched})
    derive(con, cfg)
    for k, v in report.items():
        log(f"{k}: {v}")
    return report


def watch(con, cfg, date_et: str | None = None, sleep=time.sleep):
    date_et = date_et or today_et()
    sched = nhl_api.season_schedule(cfg["seasons"]["current"], store.RAW, cfg, current=True)
    starts = sorted(datetime.fromisoformat(r["start_utc"].replace("Z", "+00:00")) for r in sched if r["date_et"] == date_et)
    if not starts:
        log(f"{date_et}: no games")
        return
    lead = timedelta(minutes=cfg["sources"]["refresh_lead_min"])
    while now_utc() < starts[-1]:
        if now_utc() < starts[0] - lead:
            sleep(min(900, (starts[0] - lead - now_utc()).total_seconds() + 1))
            continue
        rep = gameday(con, cfg, date_et)
        if rep.get("goalies") and all(s in cfg["sources"]["goalie_confirmed_labels"] for _, s in rep["goalies"].values()):
            log("every starting goalie is confirmed")
            return
        sleep(cfg["sources"]["gameday_max_age_sec"] + 300)


def status(con):
    for t in ("schedule", "games", "player_game_strength", "goalie_game", "shots", "toi_official", "officials", "players",
              "goalie_starts", "lines", "ref_assignments", "odds", "nst"):
        log(f"{t:22s} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>9,}")
    log(store.read(con, "SELECT season, COUNT(*) games, SUM(toi_source='shifts') from_shifts, SUM(xg_shots>0) with_xg, "
                        "MAX(date_et) latest FROM games GROUP BY season").to_string(index=False))


def main(argv):
    cmd = argv[0] if argv else "nightly"
    con = store.connect()
    if cmd == "nightly":
        nightly(con, CONFIG, force="--force" in argv)
    elif cmd == "gameday":
        gameday(con, CONFIG, argv[1] if len(argv) > 1 else None)
    elif cmd == "watch":
        watch(con, CONFIG, argv[1] if len(argv) > 1 else None)
    elif cmd == "derive":
        derive(con, CONFIG, argv[1] if len(argv) > 1 else None)
    elif cmd == "status":
        status(con)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
