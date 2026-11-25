"""Walk-forward backtest: every game priced with only what was known before its date.

For each date the context is rebuilt from rows known before the day's first puck drop, then each game is
simulated and its props drawn exactly as the live slate does it. Two things are taken as known that a live
run gets from Daily Faceoff: who started in goal and who dressed. Game-day lines and PP units have no
history, so the backtest runs without them (ice time is the rolling projection only).

Reported per market: hit rate, calibration (predicted against actual in 5% buckets), mean projection
against the mean result. ROI and closing line value need the prices that were on offer, and this project
holds no historical NHL prices, so they are reported as not available and no market is marked live.

    python3 -m nhl.backtest [N_SIMS] [FIRST_SEASON]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from nhl import context, props, store
from nhl.config import CONFIG
from nhl.sim import game_sim

OUT = Path(__file__).parent / "output" / "backtest_report.json"
BUCKETS = 20
PROP_STATS = {"sog": "sog", "pts": None, "ast": None, "goals": "g", "hits": "hits", "blk": "blocks"}


class Calib:
    """Predicted probability against outcome, in 5% buckets."""

    def __init__(self):
        self.n, self.hit, self.psum = np.zeros(BUCKETS), np.zeros(BUCKETS), np.zeros(BUCKETS)
        self.sq, self.base = 0.0, 0.0

    def add(self, p, y):
        p, y = np.asarray(p, float).ravel(), np.asarray(y, float).ravel()
        b = np.minimum((p * BUCKETS).astype(int), BUCKETS - 1)
        np.add.at(self.n, b, 1); np.add.at(self.hit, b, y); np.add.at(self.psum, b, p)
        self.sq += float(((p - y) ** 2).sum())

    def report(self) -> dict:
        n = self.n.sum()
        if not n:
            return {"n": 0}
        rate = self.hit.sum() / n
        rows = [{"bucket": f"{5 * i}-{5 * i + 5}%", "n": int(self.n[i]), "predicted": round(self.psum[i] / self.n[i], 4),
                 "actual": round(self.hit[i] / self.n[i], 4)} for i in range(BUCKETS) if self.n[i] >= 30]
        ece = float(sum(abs(self.psum[i] - self.hit[i]) for i in range(BUCKETS)) / n)
        return {"n": int(n), "hit_rate": round(float(rate), 4), "mean_predicted": round(float(self.psum.sum() / n), 4),
                "brier": round(self.sq / n, 5), "brier_base_rate": round(float(rate * (1 - rate)), 5),
                "calibration_gap": round(ece, 4), "buckets": rows}


def run(con, cfg, n_sims: int | None = None, first_season: int | None = None, log=print) -> dict:
    n_sims = n_sims or cfg["sim"]["n_sims_backtest"]
    tables = context.Tables.load(con, cfg)
    games = tables.frames["games"].sort_values("start_utc")
    seasons = sorted(games.season.unique())
    first_season = first_season or seasons[0]
    tg = tables.frames["team_game"].set_index(["game_id", "team"])
    offs = tables.frames["officials"]
    ev = tables.collapsed()
    act = ev.groupby(["game_id", "player_id"])[["sog", "g", "a1", "a2", "hits", "blocks"]].sum()
    dressed = ev.drop_duplicates(["game_id", "player_id"]).groupby(["game_id", "team"]).player_id.apply(set)
    saves = tables.frames["goalie_game"].set_index(["game_id", "player_id"]).saves
    ladders = {**cfg["tickets"]["paper_ladders"], "goals": [1]}
    cal = {m: {r: Calib() for r in rungs} for m, rungs in ladders.items()}
    floor = {m: Calib() for m in ladders}                      # only legs the ticket builder could use: 70%+
    game_cal = {k: Calib() for k in ("moneyline_home", "over_5.5", "over_6.5", "favourite_-1.5", "regulation_draw")}
    bias = {m: [0.0, 0.0, 0] for m in list(PROP_STATS) + ["saves", "home_goals", "away_goals", "total", "home_sog", "away_sog"]}
    done, skipped, t0 = 0, 0, time.time()
    from nhl.ingest import refs
    for (season, day), G in games[games.season >= first_season].groupby(["season", "date_et"], sort=True):
        as_of = G.start_utc.min().replace("Z", "+00:00")
        try:
            ctx = context.build(tables, as_of, int(season), cfg)
        except Exception:
            skipped += len(G)
            continue
        have = set(ctx["team_rates"].team)
        gp = ctx["team_rates"].drop_duplicates("team").set_index("team").gp
        for g in G.itertuples():
            h, a = g.home, g.away
            if h not in have or a not in have or (season == seasons[0] and min(gp[h], gp[a]) < 10):
                skipped += 1
                continue
            try:
                gk = {t: context.goalie_input(ctx, None if pd.isna(tg.at[(g.game_id, t), "starter_id"]) else int(tg.at[(g.game_id, t), "starter_id"]))
                      for t in (h, a)}
                rosters = {t: context.roster(ctx, t, cfg, dressed=dressed.get((g.game_id, t), set())) for t in (h, a)}
                if min(len(rosters[h]), len(rosters[a])) < 12:
                    skipped += 1
                    continue
                crew = refs.crew_factor(list(offs[(offs.game_id == g.game_id) & (offs.role == "referee")].name), ctx["ref_rates"], cfg)
                gctx = {**ctx, "goalies": gk, "crew_factor": crew["factor"], "spots": context.spots_for(tables, g.game_id), "absent": {}}
                lam = game_sim.team_lambdas(h, a, gctx, cfg)
                S = game_sim.simulate(lam, h, a, ctx["K"], cfg, n=n_sims, seed=int(g.game_id) % 1_000_003)
                PS = props.simulate(S, rosters, gctx, cfg, game_id=g.game_id,
                                    goalies={t: {"player_id": gk[t].get("player_id")} for t in (h, a)})
            except Exception as e:
                skipped += 1
                if skipped < 5:
                    log(f"  {g.game_id}: {type(e).__name__}: {e}")
                continue
            margin, total = g.home_goals - g.away_goals, g.home_goals + g.away_goals
            pm = game_sim.market_probs(S)
            game_cal["moneyline_home"].add(pm[("ml", h, 0.0)], margin > 0)
            game_cal["over_5.5"].add(pm[("total", "over", 5.5)], total > 5.5)
            game_cal["over_6.5"].add(pm[("total", "over", 6.5)], total > 6.5)
            fav_home = pm[("ml", h, 0.0)] >= 0.5
            game_cal["favourite_-1.5"].add(pm[("spread", h if fav_home else a, -1.5)], (margin if fav_home else -margin) > 1.5)
            game_cal["regulation_draw"].add(pm[("ml3", "draw", 0.0)], g.decided != "REG")
            for k, pred, actual in (("home_goals", S.final[h].mean(), g.home_goals), ("away_goals", S.final[a].mean(), g.away_goals),
                                    ("total", S.total().mean(), total), ("home_sog", S.sog[h].mean(), tg.at[(g.game_id, h), "sog"]),
                                    ("away_sog", S.sog[a].mean(), tg.at[(g.game_id, a), "sog"])):
                bias[k][0] += float(pred); bias[k][1] += float(actual); bias[k][2] += 1
            pid = PS.players.player_id.to_numpy()
            A = act.reindex(pd.MultiIndex.from_arrays([np.full(len(pid), g.game_id), pid])).fillna(0).to_numpy()
            actual = {"sog": A[:, 0], "goals": A[:, 1], "ast": A[:, 2] + A[:, 3], "pts": A[:, 1] + A[:, 2] + A[:, 3], "hits": A[:, 4], "blk": A[:, 5]}
            for m in PROP_STATS:
                X = PS.data[m]
                bias[m][0] += float(X.mean(0).sum()); bias[m][1] += float(actual[m].sum()); bias[m][2] += len(pid)
                for r in ladders[m]:
                    p, y = (X >= r).mean(0), actual[m] >= r
                    cal[m][r].add(p, y)
                    ok = p >= cfg["tickets"]["floor_prob"]
                    if ok.any():
                        floor[m].add(p[ok], y[ok])
            for t in (h, a):
                gid = gk[t].get("player_id")
                if gid is None or (g.game_id, gid) not in saves.index:
                    continue
                sv, x = saves.at[(g.game_id, gid)], PS.goalies[t]["saves"]
                bias["saves"][0] += float(x.mean()); bias["saves"][1] += float(sv); bias["saves"][2] += 1
                for r in ladders["saves"]:
                    p = float((x >= r).mean())
                    cal["saves"][r].add(p, sv >= r)
                    if p >= cfg["tickets"]["floor_prob"]:
                        floor["saves"].add(p, sv >= r)
            done += 1
        if done and done % 400 < len(G):
            log(f"  {day}: {done} games in {time.time() - t0:.0f}s")
    rep = {"made_at": pd.Timestamp.utcnow().isoformat(timespec="seconds"), "sims_per_game": n_sims, "games": done, "skipped": skipped,
           "seasons": [int(s) for s in seasons if s >= first_season],
           "assumed_known": "starting goalies and dressed skaters (live: Daily Faceoff); no game-day lines or PP units",
           "game_lines": {k: v.report() for k, v in game_cal.items()},
           "props": {m: {f"{r}+": c.report() for r, c in d.items()} for m, d in cal.items()},
           "floor_legs": {m: c.report() for m, c in floor.items()},
           "projection_vs_actual": {k: {"projected": round(v[0] / v[2], 4), "actual": round(v[1] / v[2], 4), "n": v[2]} for k, v in bias.items() if v[2]},
           "roi": "not available: no historical NHL prices are held",
           "closing_line_value": "not available: no historical NHL closing lines are held",
           "markets_live": [], "markets_live_rule": "a market goes live only after it beats the closing line in backtest; none can be shown to yet"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1))
    return rep


if __name__ == "__main__":
    a = sys.argv[1:]
    r = run(store.connect(), CONFIG, int(a[0]) if a else None, int(a[1]) if len(a) > 1 else None)
    print(json.dumps({k: r[k] for k in ("games", "skipped", "projection_vs_actual")}, indent=1))
    for k, v in r["game_lines"].items():
        print(k, {x: v[x] for x in ("n", "hit_rate", "mean_predicted", "brier", "brier_base_rate", "calibration_gap")})
    for m, v in r["floor_legs"].items():
        print("floor", m, {x: v.get(x) for x in ("n", "hit_rate", "mean_predicted")})
