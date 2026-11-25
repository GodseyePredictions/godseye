"""Why the algorithm rates a leg: every line is a number the engine produced, written out.

For a skater prop: the projection and the ice time behind it, his own per-60 rates, what the opponent and
the rink did to it, how often he has reached the rung lately, and the share of simulated games it hit.
For saves: the opponent's projected shots, pull risk, and the goalie's recent starts. For a game line: each
side's expected goals with the adjustments that moved them, and the listed price against the model.
"""
import numpy as np

UNIT = {"sog": "shots on goal", "hits": "hits", "blk": "blocked shots", "pts": "points", "ast": "assists", "goals": "goals"}
RATE = {"sog": "sog", "hits": "hits", "blk": "blocks"}


class Explainer:
    def __init__(self, PS, S, lam: dict, ctx: dict, recent: dict, lines_priced: list, summary: dict, n_sims: int):
        self.PS, self.S, self.lam, self.ctx, self.recent = PS, S, lam, ctx, recent
        self.priced = {(g["market"], g["side"], float(g["line"])): g for g in lines_priced}
        self.summary, self.n = summary, n_sims
        self.rows = {int(r.player_id): r for r in PS.players.itertuples()}
        self.steps = {m: {e["player_id"]: e for e in v} for m, v in PS.expected.items()}

    def _recent(self, pid: int, market: str, rung: int) -> str | None:
        vals = self.recent.get(pid, {}).get(market)
        if not vals:
            return None
        k = sum(v >= rung for v in vals)
        return f"Reached {rung}+ in {k} of his last {len(vals)} games (most recent first: {', '.join(str(int(v)) for v in vals)})"

    def __call__(self, leg: dict) -> list[str]:
        if leg.get("kind") == "game":
            return self.game_line(leg)
        if leg["market"] == "saves":
            return self.saves(leg)
        return self.skater(leg)

    def skater(self, leg: dict) -> list[str]:
        r, m, S = self.rows[leg["player_id"]], leg["market"], self.S
        opp = S.away if r.team == S.home else S.home
        slot = f"line {r.ev_slot[1]}" if isinstance(r.ev_slot, str) and r.ev_slot.startswith("f") else \
            (f"pair {r.ev_slot[1]}" if isinstance(r.ev_slot, str) else "lines not posted")
        unit = f", {r.pp_unit.upper()}" if isinstance(r.pp_unit, str) else ""
        out = [f"Projected {leg['mean']:.2f} {UNIT[m]} in {r.total / 60:.1f} minutes: {r.ev / 60:.1f} even strength, "
               f"{r.pp / 60:.1f} power play{unit}, {r.pk / 60:.1f} penalty kill ({slot})"]
        if m in RATE:
            k = RATE[m]
            out.append(f"His rates per 60 minutes: {getattr(r, f'{k}60_ev'):.1f} at even strength, {getattr(r, f'{k}60_pp'):.1f} on the power "
                       f"play, {getattr(r, f'{k}60_pk'):.1f} shorthanded ({int(r.gp)} games this season, shrunk toward his position's rate)")
            st = self.steps.get(m, {}).get(leg["player_id"])
            if st:
                out.append("Adjustments: " + "; ".join(f"{s['what']} x{s['factor']:.2f}" for s in st["steps"]))
        else:
            lam = self.lam[r.team]
            out.append(f"{r.team} expected goals {lam['lam']:.2f} before empty net and overtime ({lam['goals']['pp']:.2f} of it on the power play), "
                       f"against {self._goalie(opp)}")
            out.append(f"His share: {r.ixg60_ev:.2f} expected goals and {r.a160_ev + r.a260_ev:.2f} assists per 60 at even strength, "
                       f"{r.ixg60_pp:.2f} and {r.a160_pp + r.a260_pp:.2f} on the power play; on the ice for {r.on_xgf60_ev:.1f} team expected goals per 60")
            if m == "goals":
                out.append(f"Finishing {r.finishing:.2f} goals per expected goal (shrunk hard toward 1.00)")
        if isinstance(r.notes, str) and r.notes:
            out.append(f"Tonight's deployment: {r.notes}")
        rec = self._recent(leg["player_id"], m, leg["rung"])
        if rec:
            out.append(rec)
        if m == "sog":
            f, lead = self.S.f_sog[r.team], self._lead(r.team)
            tail = ""
            if (lead < 0).any():
                d = 100 * (f[lead < 0].mean() / max(f.mean(), 1e-9) - 1)
                tail = f"; when it trails after two periods it shoots {d:+.0f}% against its average" if abs(d) >= 1 else ""
            out.append(f"Script: {r.team} project for {S.sog[r.team].mean():.1f} shots on goal against {opp}{tail}")
        if m in ("hits", "blk"):
            f = (S.f_hits if m == "hits" else S.f_blk)[r.team]
            lead = self._lead(r.team)
            if (lead > 0).any() and (lead < 0).any():
                out.append(f"Script: when {r.team} lead after two periods the score moves its {UNIT[m]} {100 * (f[lead > 0].mean() - 1):+.0f}%, "
                           f"when it trails {100 * (f[lead < 0].mean() - 1):+.0f}% ({r.team} lead after two in {100 * (lead > 0).mean():.0f}% of games)")
        out.append(f"Hit in {100 * leg['p']:.1f}% of {self.n:,} simulated games" + ("" if leg.get("rung_verified") else "; the rung is not checked at the book"))
        return out

    def _lead(self, team):
        return self.S.lead_p2 if team == self.S.home else -self.S.lead_p2

    def _goalie(self, team: str) -> str:
        g = (self.ctx.get("goalies") or {}).get(team)
        if not g:
            return f"{team}'s goalie (not named yet)"
        note = "too few starts to rate, priced as league average" if g.get("below_min_sample") else f"GSAx {g['gsax60']:+.2f} per 60"
        return f"{g.get('name')} ({note})"

    def saves(self, leg: dict) -> list[str]:
        S = self.S
        team = leg["team"]
        opp = S.away if team == S.home else S.home
        g = self.PS.goalies[team]
        out = [f"Projected {g['expected_saves']:.1f} saves: {opp} project for {S.sog[opp].mean():.1f} shots on goal and "
               f"{self.lam[opp]['lam']:.2f} goals before empty net and overtime",
               f"{opp} shot volume: {self.lam[opp]['sog']['ev']:.1f} at even strength, {self.lam[opp]['sog']['pp']:.1f} on "
               f"{self.lam[opp]['pp_sec'] / 60:.1f} projected power-play minutes",
               f"Pull risk: he is replaced in {100 * g['pull_prob']:.1f}% of simulated games (down three or more after two periods) and keeps only the saves made by then"]
        rec = self._recent(leg["player_id"], "saves", leg["rung"])
        if rec:
            out.append(rec.replace("games", "starts"))
        out.append(f"Saves legs need 85%: in backtest the model ran two to four points over on this market")
        out.append(f"Hit in {100 * leg['p']:.1f}% of {self.n:,} simulated games" + ("" if leg.get("rung_verified") else "; the rung is not checked at the book"))
        return out

    def game_line(self, leg: dict) -> list[str]:
        S, sm = self.S, self.summary
        h, a = S.home, S.away
        out = [f"Simulated score: {a} {sm['away_goals']:.2f}, {h} {sm['home_goals']:.2f} (total {sm['total']:.2f}); "
               f"{h} win {100 * sm['home_win']:.0f}%, overtime {100 * sm['overtime']:.0f}%"]
        for t in (a, h):
            lam = self.lam[t]
            moves = [f"{s['what']} x{s['factor']:.3f}" for s in lam["steps"] if "factor" in s and abs(s["factor"] - 1) >= 0.004]
            out.append(f"{t}: {lam['goals']['ev']:.2f} expected goals at 5v5, {lam['goals']['pp']:.2f} on {lam['pp_sec'] / 60:.1f} power-play minutes"
                       + (f"; {'; '.join(moves)}" if moves else ""))
        m = S.margin() if leg["side"] == h else -S.margin()
        if leg["market"] == "spread":
            out.append(f"{leg['side']} win by two or more in {100 * (m >= 2).mean():.0f}% of games, by exactly one in {100 * (m == 1).mean():.0f}%, "
                       f"lose in {100 * (m < 0).mean():.0f}%; empty-net goals ({sm['empty_net_goals']:.2f} a game) are in the margin")
        if leg["market"] == "total":
            tot = S.total()
            out.append(f"Total goals: {100 * (tot <= 4).mean():.0f}% four or fewer, {100 * ((tot == 5) | (tot == 6)).mean():.0f}% five or six, "
                       f"{100 * (tot >= 7).mean():.0f}% seven or more. In backtest the model's totals were no better than the base rate")
        g = self.priced.get((leg["market"], leg["side"], float(leg["line"])))
        if g:
            out.append(f"{g['book']} price {g['price']:+.0f}: {100 * g['implied_prob']:.1f}% with the vig removed, against the model's "
                       f"{100 * g['model_prob']:.1f}% (edge {100 * g['edge']:+.1f} points). The model has not been tested against closing lines")
        out.append(f"Hit in {100 * leg['p']:.1f}% of {self.n:,} simulated games" + ("" if leg.get("rung_verified") else "; the line is not checked at the book"))
        return out


def recent_form(tables, as_of: str, n: int = 10) -> dict:
    """{player_id: {market: [last n game counts, most recent first]}} from games known before as_of."""
    ev = tables.collapsed()
    ev = ev[ev.known_at < as_of]
    last_date = ev.known_at.max()
    g = ev.groupby(["player_id", "game_id", "known_at"], as_index=False)[["sog", "g", "a1", "a2", "hits", "blocks"]].sum()
    g = g.sort_values("known_at", ascending=False).groupby("player_id").head(n)
    out = {}
    for pid, d in g.groupby("player_id", sort=False):
        out[int(pid)] = {"sog": d.sog.tolist(), "goals": d.g.tolist(), "ast": (d.a1 + d.a2).tolist(), "pts": (d.g + d.a1 + d.a2).tolist(),
                         "hits": d.hits.tolist(), "blk": d.blocks.tolist()}
    gg = tables.before("goalie_game", as_of)
    gg = gg[gg.starter == 1].sort_values("known_at", ascending=False).groupby("player_id").head(n)
    for pid, d in gg.groupby("player_id", sort=False):
        out.setdefault(int(pid), {})["saves"] = d.saves.tolist()
    return out
