"""One finished game -> the per-game tables every rate is built from.

Strength state comes from the shift chart: at every second we know who is on the ice, so we know
each side's skater count and whether its goalie is in the net. From a team's point of view:

  ev5  five skaters a side, both goalies in
  pp   more penalty-free manpower than the opponent (an extra attacker for a pulled goalie does not count)
  pk   the mirror of pp
  evo  everything else at even manpower: 4v4, 3v3 overtime, empty-net time

ev5 + evo is what the league calls even strength. The same timeline says who was on the ice for each
MoneyPuck shot (on-ice xG) and what the score was (score-state table). If a game's shift chart is
missing or broken, strength falls back to the play-by-play situation code and the league's own
EV/PP/SH ice time, and on-ice numbers are left empty (toi_source = "pbp").
"""
from datetime import datetime, timedelta

import numpy as np

from nhl.store import STRENGTHS

K = {s: i for i, s in enumerate(STRENGTHS)}
PEN_COUNTED = {"MIN": 1.0, "BEN": 1.0, "MAJ": 1.0}    # penalties that put a team short; fights and misconducts do not


def _known_at(start_utc: str, cfg) -> str:
    t = datetime.fromisoformat(start_utc.replace("Z", "+00:00")) + timedelta(hours=cfg["result_known_after_hours"])
    return t.isoformat(timespec="seconds")


def _merge_short_runs(state: np.ndarray, min_run: int) -> np.ndarray:
    """A pp/pk stretch shorter than min_run seconds is a line change caught mid-shift: give it the state before it."""
    out = state.copy()
    n = len(out)
    i = 0
    while i < n:
        j = i
        while j < n and out[j] == out[i]:
            j += 1
        if out[i] in (K["pp"], K["pk"]) and j - i < min_run and i > 0:
            out[i:j] = out[i - 1]
        i = j
    return out


def _states(own_sk, opp_sk, own_g, opp_g):
    own_adj = own_sk - (~own_g)
    opp_adj = opp_sk - (~opp_g)
    st = np.full(len(own_sk), K["evo"], dtype=np.int8)
    st[(own_sk == 5) & (opp_sk == 5) & own_g & opp_g] = K["ev5"]
    st[own_adj > opp_adj] = K["pp"]
    st[own_adj < opp_adj] = K["pk"]
    return st


def timeline_from_shifts(game: dict, shifts: list, cfg):
    """Per-second on-ice matrix and each side's strength state, or None when the shift chart cannot be trusted."""
    T = game["seconds"]
    ids = [p for p in game["roster"] if any(s[0] == p for s in shifts)] if shifts else []
    if not ids:
        return None
    row = {p: i for i, p in enumerate(ids)}
    on = np.zeros((len(ids), T), dtype=bool)
    for p, a, b in shifts:
        if p in row:
            on[row[p], a:b] = True
    home = np.array([game["roster"][p]["team"] == game["home"] for p in ids])
    goalie = np.array([game["roster"][p]["pos"] == "G" for p in ids])
    sk = {1: on[home & ~goalie].sum(0), 0: on[~home & ~goalie].sum(0)}
    g = {1: on[home & goalie].any(0), 0: on[~home & goalie].any(0)}
    ok = np.mean((sk[1] >= 3) & (sk[1] <= 6) & (sk[0] >= 3) & (sk[0] <= 6))
    if ok < cfg["strength"]["shift_quality_min"]:
        return None
    run = cfg["strength"]["min_state_run_sec"]
    return {"ids": ids, "on": on, "home": home, "goalie": goalie, "goalie_in": g,
            "state": {1: _merge_short_runs(_states(sk[1], sk[0], g[1], g[0]), run),
                      0: _merge_short_runs(_states(sk[0], sk[1], g[0], g[1]), run)}}


def timeline_from_codes(game: dict):
    """Fallback: the situation code on each event (away goalie, away skaters, home skaters, home goalie).

    A code describes the ice just before its event. When it differs from the previous event's and that
    event was a penalty or a goal, the change happened there and the whole gap takes the new code.
    Otherwise something unrecorded changed it in between (a penalty expiring, a goalie pulled), so the gap
    is split down the middle."""
    T = game["seconds"]
    sk = {1: np.full(T, 5), 0: np.full(T, 5)}
    g = {1: np.ones(T, bool), 0: np.ones(T, bool)}

    def paint(a, b, c):
        if b > a:
            g[0][a:b], sk[0][a:b], sk[1][a:b], g[1][a:b] = c[0] == "1", int(c[1]), int(c[2]), c[3] == "1"

    prev, prev_code, caused = 0, None, True
    for e in sorted(game["events"], key=lambda e: e["sec"]):
        c = e.get("code")
        if not c or len(c) != 4:
            continue
        end = min(e["sec"], T)
        if end > prev:
            if prev_code is None or c == prev_code or caused:
                paint(prev, end, c)
            else:
                mid = (prev + end) // 2
                paint(prev, mid, prev_code); paint(mid, end, c)
            caused = False
        caused = caused or e["type"] in ("penalty", "goal") or e["sec"] % 1200 == 0
        prev, prev_code = max(prev, end), c
    return {"ids": [], "on": np.zeros((0, T), bool), "home": np.zeros(0, bool), "goalie": np.zeros(0, bool), "goalie_in": g,
            "state": {1: _states(sk[1], sk[0], g[1], g[0]), 0: _states(sk[0], sk[1], g[0], g[1])}}


def build_game(game: dict, shifts: list, shots, toi_official: dict, cfg) -> dict:
    """All per-game table rows for one finished game.

    game: nhl_api.parse_pbp output. shifts: nhl_api.parse_shifts output. shots: that game's MoneyPuck rows
    (DataFrame, may be empty). toi_official: {player_id: (ev, pp, sh)} seconds from the league."""
    T = game["seconds"]
    tl = timeline_from_shifts(game, shifts, cfg)
    source = "shifts"
    if tl is None:
        tl, source = timeline_from_codes(game), "pbp"
    state, roster = tl["state"], game["roster"]
    home, away = game["home"], game["away"]
    side = {home: 1, away: 0}
    at = lambda sec: min(max(sec - 1, 0), T - 1)       # an event at second t happened in the second that ended at t
    known = _known_at(game["start_utc"], cfg)
    base = {"game_id": game["game_id"], "season": game["season"], "date_et": game["date_et"], "known_at": known}

    # ---- score at every second, from the home side
    lead = np.zeros(T, dtype=int)
    period_goals = {1: [0, 0, 0, 0], 0: [0, 0, 0, 0]}
    for e in game["events"]:
        if e["type"] == "goal" and e["team"] in side:
            s = side[e["team"]]
            lead[min(e["sec"], T):] += 1 if s else -1
            period_goals[s][min(e["period"], 4) - 1] += 1

    tz = lambda: {s: {c: 0 for c in ("gf", "ga", "cf", "ca", "ff", "fa", "sog_f", "sog_a", "hits_f", "hits_a", "blk_f", "blk_a",
                                      "hdf", "hda")} | {"xgf": 0.0, "xga": 0.0, "pen_taken": 0.0, "pen_drawn": 0.0}
                  for s in range(4)}
    team = {1: tz(), 0: tz()}
    pz = lambda: {c: 0 for c in ("g", "a1", "a2", "sog", "icf", "iff", "hits", "blocks")} | {"ixg": 0.0, "pen_taken": 0.0, "pen_drawn": 0.0}
    player: dict = {}
    P = lambda pid, s: player.setdefault((pid, s), pz())
    scopes = ("all", "ev5")
    score = {(s, sc, b): {c: 0 for c in ("cf", "ca", "sog_f", "sog_a", "hits_f", "blk_f")} | {"xgf": 0.0, "xga": 0.0}
             for s in (0, 1) for sc in scopes for b in range(-2, 3)}
    bucket = lambda s, i: int(np.clip(lead[i] if s else -lead[i], -2, 2))
    goalie = {}
    G = lambda pid: goalie.setdefault(pid, {"sa": 0, "ga": 0, "xga": 0.0, "unblocked": 0, "xg_ga": 0})
    summary = {s: {"en_gf": 0, "en_ga": 0, "pim": 0} for s in (0, 1)}

    def tally_score(s, i, key, v=1):
        b = bucket(s, i)
        score[(s, "all", b)][key] += v
        if state[s][i] == K["ev5"]:
            score[(s, "ev5", b)][key] += v

    for e in game["events"]:
        if e["team"] not in side or e["sec"] > T:
            continue
        s, i = side[e["team"]], at(e["sec"])
        o = 1 - s
        ks, ko = int(state[s][i]), int(state[o][i])
        kind = e["type"]
        if kind in ("shot-on-goal", "missed-shot", "blocked-shot", "goal"):
            team[s][ks]["cf"] += 1; team[o][ko]["ca"] += 1
            tally_score(s, i, "cf"); tally_score(o, i, "ca")
            if e.get("shooter") in roster:
                P(e["shooter"], ks)["icf"] += 1
            if kind == "blocked-shot":
                b = e.get("blocker")
                if b in roster and roster[b]["team"] != e["team"]:     # a shot that hit a team-mate is not a block
                    team[o][ko]["blk_f"] += 1; team[s][ks]["blk_a"] += 1
                    P(b, ko)["blocks"] += 1
                    tally_score(o, i, "blk_f")
                continue
            team[s][ks]["ff"] += 1; team[o][ko]["fa"] += 1
            if e.get("shooter") in roster:
                P(e["shooter"], ks)["iff"] += 1
            if kind == "missed-shot":
                continue
            team[s][ks]["sog_f"] += 1; team[o][ko]["sog_a"] += 1
            tally_score(s, i, "sog_f"); tally_score(o, i, "sog_a")
            if e.get("shooter") in roster:
                P(e["shooter"], ks)["sog"] += 1
            if e.get("goalie"):
                G(e["goalie"])["sa"] += 1
            if kind == "goal":
                team[s][ks]["gf"] += 1; team[o][ko]["ga"] += 1
                if e.get("shooter") in roster:
                    P(e["shooter"], ks)["g"] += 1
                for a in ("a1", "a2"):
                    if e.get(a) in roster:
                        P(e[a], ks)[a] += 1
                if e.get("goalie"):
                    G(e["goalie"])["ga"] += 1
                else:
                    summary[s]["en_gf"] += 1; summary[o]["en_ga"] += 1
        elif kind == "hit":
            team[s][ks]["hits_f"] += 1; team[o][ko]["hits_a"] += 1
            tally_score(s, i, "hits_f")
            if e.get("hitter") in roster:
                P(e["hitter"], ks)["hits"] += 1
        elif kind == "penalty":
            summary[s]["pim"] += int(e.get("minutes") or 0)
            n = PEN_COUNTED.get(e.get("pen_type"), 0.0)
            if e.get("desc") == "fighting" or not n:
                continue
            n *= 2 if e.get("minutes") == 4 else 1                     # a double minor is two power plays
            team[s][ks]["pen_taken"] += n; team[o][ko]["pen_drawn"] += n
            if e.get("by") in roster:
                P(e["by"], ks)["pen_taken"] += n
            if e.get("drawn") in roster:
                P(e["drawn"], ko)["pen_drawn"] += n

    # ---- MoneyPuck shots: team xG, individual xG, goalie xG against, on-ice xG
    n_ids = len(tl["ids"])
    on_cols = ("on_xgf", "on_xga", "on_gf", "on_ga", "on_cf", "on_ca")
    onice = {c: np.zeros((n_ids, 4)) for c in on_cols}
    n_shots = 0
    hd = cfg["strength"]["high_danger_xg"]
    if shots is not None and len(shots):
        sh = shots[(shots.sec <= T) & (shots.period <= 4)]
        n_shots = len(sh)
        idx = np.clip(sh.sec.to_numpy() - 1, 0, T - 1)
        xg, is_home = sh.xg.to_numpy(), sh.is_home.to_numpy()
        for i, x, hm, shooter, gid, goal, en in zip(idx, xg, is_home, sh.shooter_id, sh.goalie_id, sh.goal, sh.empty_net):
            s = int(hm); o = 1 - s
            ks, ko = int(state[s][i]), int(state[o][i])
            team[s][ks]["xgf"] += x; team[o][ko]["xga"] += x
            if x >= hd:
                team[s][ks]["hdf"] += 1; team[o][ko]["hda"] += 1
            for sc_s, key in ((s, "xgf"), (o, "xga")):
                tally_score(sc_s, i, key, x)
            if shooter in roster:
                P(int(shooter), ks)["ixg"] += x
            if gid and not en:
                g = G(int(gid)); g["xga"] += x; g["unblocked"] += 1; g["xg_ga"] += int(goal)
        if n_ids:
            M = tl["on"][:, idx]                                        # players x shots
            shot_home = is_home.astype(bool)
            for_mask = tl["home"][:, None] == shot_home[None, :]
            st_p = np.where(tl["home"][:, None], state[1][idx][None, :], state[0][idx][None, :])
            goals = sh.goal.to_numpy()
            for k in range(4):
                mk = M & (st_p == k)
                onice["on_xgf"][:, k] = (mk & for_mask) @ xg
                onice["on_xga"][:, k] = (mk & ~for_mask) @ xg
                onice["on_gf"][:, k] = (mk & for_mask) @ goals
                onice["on_ga"][:, k] = (mk & ~for_mask) @ goals
    if n_ids:                                                           # on-ice shot attempts, from the play-by-play
        att = [(at(e["sec"]), side[e["team"]]) for e in game["events"]
               if e["type"] in ("shot-on-goal", "missed-shot", "blocked-shot", "goal") and e["team"] in side and e["sec"] <= T]
        if att:
            idx2 = np.array([a[0] for a in att]); h2 = np.array([a[1] for a in att], bool)
            M = tl["on"][:, idx2]
            for_mask = tl["home"][:, None] == h2[None, :]
            st_p = np.where(tl["home"][:, None], state[1][idx2][None, :], state[0][idx2][None, :])
            for k in range(4):
                mk = M & (st_p == k)
                onice["on_cf"][:, k] = (mk & for_mask).sum(1)
                onice["on_ca"][:, k] = (mk & ~for_mask).sum(1)

    # ---- rows
    out = {t: [] for t in ("games", "team_game", "team_game_strength", "team_game_score", "player_game_strength",
                           "goalie_game", "players")}
    names = {1: home, 0: away}
    goals = {1: game["home_goals"], 0: game["away_goals"]}
    out["games"].append({**base, "start_utc": game["start_utc"], "home": home, "away": away, "venue": game["venue"],
                         "home_goals": goals[1], "away_goals": goals[0], "decided": game["decided"], "seconds": T,
                         "h1": period_goals[1][0], "h2": period_goals[1][1], "h3": period_goals[1][2], "hot": period_goals[1][3],
                         "a1": period_goals[0][0], "a2": period_goals[0][1], "a3": period_goals[0][2], "aot": period_goals[0][3],
                         "toi_source": source, "xg_shots": n_shots})
    starters = {}
    for s in (0, 1):
        own_goalies = [p for p in roster if roster[p]["team"] == names[s] and roster[p]["pos"] == "G"]
        gtoi = {}
        for p in own_goalies:
            if p in tl["ids"]:
                gtoi[p] = int(tl["on"][tl["ids"].index(p)].sum())
            elif p in goalie:
                gtoi[p] = 0
        played = [p for p in own_goalies if gtoi.get(p, 0) > 0 or p in goalie]
        if tl["ids"]:
            first = [p for p in played if p in tl["ids"] and tl["on"][tl["ids"].index(p), :60].any()]
        else:
            first = []
        if not first:                                                   # no shift chart: the goalie who faced the first shot
            seen = [e.get("goalie") for e in game["events"] if e.get("goalie") in own_goalies]
            first = seen[:1]
        starters[s] = first[0] if first else None
        for p in played:
            g = G(p)
            out["goalie_game"].append({**base, "player_id": p, "team": names[s], "starter": int(p == starters[s]),
                                       "relieved": int(p == starters[s] and len(played) > 1), "toi": gtoi.get(p, 0),
                                       "sa": g["sa"], "ga": g["ga"], "saves": g["sa"] - g["ga"], "xga": round(g["xga"], 4),
                                       "unblocked": g["unblocked"], "xg_ga": g["xg_ga"]})
    for s in (0, 1):
        o = 1 - s
        tot = lambda c: sum(team[s][k][c] for k in range(4))
        out["team_game"].append({**base, "team": names[s], "opp": names[o], "is_home": s, "venue": game["venue"],
                                 "gf": goals[s], "ga": goals[o], "won": int(goals[s] > goals[o]), "decided": game["decided"],
                                 "starter_id": starters[s], "en_sec": int((~tl["goalie_in"][s]).sum()),
                                 "en_gf": summary[s]["en_gf"], "en_ga": summary[s]["en_ga"], "hits": tot("hits_f"),
                                 "blocks": tot("blk_f"), "sog": tot("sog_f"), "cf": tot("cf"), "pen_taken": tot("pen_taken"),
                                 "pen_drawn": tot("pen_drawn"), "pim": summary[s]["pim"]})
        for k, name in enumerate(STRENGTHS):
            v = team[s][k]
            out["team_game_strength"].append({**base, "team": names[s], "strength": name, "is_home": s,
                                              "toi": int((state[s] == k).sum()),
                                              **{c: (round(x, 4) if isinstance(x, float) else x) for c, x in v.items()}})
        for sc in scopes:
            for b in range(-2, 3):
                ld = np.clip(lead if s else -lead, -2, 2) == b
                if sc == "ev5":
                    ld = ld & (state[s] == K["ev5"])
                v = score[(s, sc, b)]
                out["team_game_score"].append({**base, "team": names[s], "scope": sc, "lead": b, "toi": int(ld.sum()),
                                               **{c: (round(x, 4) if isinstance(x, float) else x) for c, x in v.items()}})
    # skaters: every dressed skater gets four rows, so a game with no events still counts as a game played
    toi = {}
    if n_ids:
        for j, p in enumerate(tl["ids"]):
            st = state[1] if tl["home"][j] else state[0]
            toi[p] = [int((tl["on"][j] & (st == k)).sum()) for k in range(4)]
    for p, info in roster.items():
        if info["pos"] == "G" or info["team"] not in side:
            continue
        if n_ids:
            if p not in toi:
                continue                                                # dressed but never took a shift
            t4 = toi[p]
        else:                                                           # league TOI: all even strength goes to ev5
            ev, pp, sh = toi_official.get(p, (0, 0, 0))
            if ev + pp + sh == 0:
                continue
            t4 = [ev, 0, pp, sh]
        j = tl["ids"].index(p) if n_ids else None
        for k, name in enumerate(STRENGTHS):
            v = player.get((p, k), pz())
            oi = {c: (float(onice[c][j, k]) if j is not None else None) for c in on_cols}
            out["player_game_strength"].append({**base, "player_id": p, "strength": name, "team": info["team"], "pos": info["pos"],
                                                "toi": t4[k], **{c: (round(x, 4) if isinstance(x, float) else x) for c, x in v.items()},
                                                **{c: (round(x, 4) if x is not None else None) for c, x in oi.items()}})
    for p, info in roster.items():
        out["players"].append({"player_id": p, "name": info["name"], "pos": info["pos"], "team": info["team"],
                               "last_date": game["date_et"]})
    return out
