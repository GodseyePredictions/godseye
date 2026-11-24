"""Checks on the weekly site data before it is allowed to reach the web app.

`check(data, season, week)` returns two lists of plain-English messages:

  errors    the data is malformed or breaks a standing rule; the build is refused
  warnings  the data is usable but someone should look (for example, every game has kicked off)

Nothing here computes a probability. It only confirms that the numbers the algorithm wrote are
well-formed and consistent with each other and with the NFL ticket rules in the repository's CLAUDE.md.
"""
from __future__ import annotations

REQUIRED_KEYS = ("meta", "games", "players", "props", "corr", "algo", "singles", "rules")
YARD_MARKETS = ("pass_yds", "rush_yds", "rec_yds")
LOW_RUNG_FLOOR = {"rush_yds": 20, "rec_yds": 20}   # bet365 rushing and receiving yards ladders start at 20+
MAX_LEGS_UNDER = 1        # at most one leg under WEAK_LEG on any ticket
WEAK_LEG = 0.65
SGP_FLOOR = 0.70          # SGP legs are floor rungs; a leg below this is reported, not refused
TOL = 1e-6


def _prob(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0.0 <= x <= 1.0


def check(data: dict, season: int | None = None, week: int | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["site data is not an object"], warnings
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        return [f"site data is missing: {', '.join(missing)}"], warnings

    meta = data["meta"]
    if season is not None and meta.get("season") != season:
        errors.append(f"data is for season {meta.get('season')}, expected {season}")
    if week is not None and meta.get("week") != week:
        errors.append(f"data is for week {meta.get('week')}, expected {week}")

    games = data["games"]
    game_ids = [g.get("id") for g in games]
    if not games:
        errors.append("no games in the data")
    if len(set(game_ids)) != len(game_ids):
        errors.append("duplicate game ids")
    for g in games:
        if not all(g.get(k) for k in ("id", "away", "home")):
            errors.append(f"game {g.get('id')!r} is missing its id or teams")
    if games and all(g.get("started") for g in games):
        warnings.append("every game in this build has already kicked off, so there are no tickets to show")

    players = {}
    for p in data["players"]:
        pid = p.get("id")
        if pid in players:
            errors.append(f"duplicate player id {pid}")
        players[pid] = p
        if not _prob(p.get("p")):
            errors.append(f"{p.get('name', pid)}: anytime-TD probability {p.get('p')!r} is not between 0 and 1")
        if p.get("game") not in game_ids:
            errors.append(f"{p.get('name', pid)}: game {p.get('game')!r} is not on the slate")

    ladders = {}
    for pid, markets in data["props"].items():
        name = players.get(pid, {}).get("name", pid)
        if pid not in players:
            errors.append(f"prop ladders for unknown player {pid}")
        for mk, lad in markets.items():
            k, p = lad.get("k", []), lad.get("p", [])
            if not k or len(k) != len(p):
                errors.append(f"{name} {mk}: ladder has {len(k)} rungs but {len(p)} probabilities")
                continue
            if any(not _prob(x) for x in p):
                errors.append(f"{name} {mk}: a rung probability is not between 0 and 1")
                continue
            if any(b <= a for a, b in zip(k, k[1:])):
                errors.append(f"{name} {mk}: rungs are not in increasing order")
            if any(b > a + TOL for a, b in zip(p, p[1:])):
                errors.append(f"{name} {mk}: a higher rung is more likely than a lower one")
            if mk in YARD_MARKETS and any(x % 5 for x in k):
                errors.append(f"{name} {mk}: yardage rungs must be multiples of 5")
            if mk in LOW_RUNG_FLOOR and min(k) < LOW_RUNG_FLOOR[mk]:
                errors.append(f"{name} {mk}: ladder starts below {LOW_RUNG_FLOOR[mk]}+, which the book does not offer")
            for kk, pp in zip(k, p):
                ladders[(pid, mk, kk)] = pp

    algo = data["algo"]

    def atd_ticket(t, where):
        ps = []
        for pid in t.get("legs", []):
            if pid not in players:
                errors.append(f"{where}: unknown player {pid}")
            else:
                ps.append(players[pid]["p"])
        joint(t, ps, where)

    def joint(t, leg_ps, where):
        if not _prob(t.get("p")):
            errors.append(f"{where}: ticket probability {t.get('p')!r} is not between 0 and 1")
        elif leg_ps and all(_prob(x) for x in leg_ps) and t["p"] > min(leg_ps) + TOL:
            errors.append(f"{where}: ticket chance {t['p']:.3f} is higher than its weakest leg {min(leg_ps):.3f}")

    for t in algo.get("atd") or []:
        atd_ticket(t, f"{t.get('n')}-leg anytime-TD ticket")
    for t in algo.get("atd_combos") or []:
        atd_ticket(t, f"anytime-TD combo in {t.get('game')}")
    for style in (algo.get("atd_styles") or {}).values():
        for t in style.get("tickets") or []:
            atd_ticket(t, f"{style.get('label', 'style')} {t.get('n')}-leg anytime-TD ticket")

    for t in algo.get("sgp") or []:
        where = f"props SGP for {t.get('game')}"
        legs = t.get("legs", [])
        ps = []
        for l in legs:
            if l.get("id") not in players:
                errors.append(f"{where}: unknown player {l.get('id')}")
            if l.get("mk") == "atd":
                errors.append(f"{where}: carries a touchdown leg; TD legs never go in a props SGP")
            if not _prob(l.get("p")):
                errors.append(f"{where}: a leg has no valid probability")
            else:
                ps.append(l["p"])
        weak = sum(x < WEAK_LEG for x in ps)
        if weak > MAX_LEGS_UNDER:
            errors.append(f"{where}: {weak} legs are under {WEAK_LEG:.0%}; at most {MAX_LEGS_UNDER} is allowed")
        below = sum(x < SGP_FLOOR for x in ps)
        if below:
            warnings.append(f"{where}: {below} leg(s) under the {SGP_FLOOR:.0%} floor")
        joint(t, ps, where)

    for t in algo.get("props") or []:
        where = f"props ticket {t.get('ticket')}"
        ps = []
        for l in t.get("legs", []):
            if l.get("mk") == "atd":
                errors.append(f"{where}: carries a touchdown leg; TD legs never go in a props ticket")
            key = (l.get("id"), l.get("mk"), l.get("k"))
            if key in ladders:
                ps.append(ladders[key])
            else:
                errors.append(f"{where}: leg {l.get('mk')} {l.get('k')}+ for {l.get('id')} is not a rung on that player's ladder")
        joint(t, ps, where)

    return errors, warnings
