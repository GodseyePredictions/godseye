"""Full-slate ATD slip for a set of games (e.g. one Sunday), priced with the ATD copula."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .correlation import build_sigma, joint_prob

ROOT = Path(__file__).resolve().parent.parent
# Price cushion before a leg is worth playing.  WRs that make tickets ran ~7 pts hot in the 2026 ledger
# (selection effect), so they need a bigger gap between our number and the book's.
CUSHION = {"WR": 0.06, "RB": 0.03, "TE": 0.04, "QB": 0.04}


def am(p):
    p = float(np.clip(p, 1e-4, 1 - 1e-4))
    a = int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))
    return f"+{a}" if a > 0 else str(a)


def joint(legs, corr):
    pj = 1.0
    for _, g in legs.groupby("game_id"):
        pj *= joint_prob(g.p_attd.values, build_sigma(g, corr), n_sims=400_000)
    return pj


def build_slip(proj: pd.DataFrame, games: list[str], title: str) -> str:
    corr = json.loads((ROOT / "models" / "correlations.json").read_text())
    P = proj[proj.game_id.isin(games)].copy()
    P["min_p_needed"] = P.p_attd - P.pos_group.map(CUSHION).fillna(0.04)
    P["play_at"] = P.min_p_needed.map(am)
    P["matchup"] = P.game_id.str.split("_").str[2] + "@" + P.game_id.str.split("_").str[3]
    ok = P[~P.singles_only.fillna(False).astype(bool)].sort_values("p_attd", ascending=False)

    L = [f"# {title}", "",
         "*All data, no picks from media. Probabilities = P(player scores ≥1 rushing/receiving TD | he plays). "
         "Fair = break-even price. **Play at** = the shortest bet365 price worth taking (fair + position cushion).*",
         "", "## Board — top 20", "",
         "| # | Player | Pos | Game | Model | Fair | Play at | Team TDs (rush+pass) | Note |",
         "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(P.sort_values("p_attd", ascending=False).head(20).itertuples(), 1):
        note = "singles only" if r.singles_only else ""
        if isinstance(r.injury_status, str):
            note = (note + f" · {r.injury_status}").strip(" ·")
        L.append(f"| {i} | {r.name} | {r.pos_group} | {r.matchup} ({r.team}) | **{r.p_attd:.0%}** | {am(r.p_attd)} | "
                 f"{r.play_at} | {r.lam_team_rush + r.lam_team_pass:.2f} | {note} |")

    # tickets: ≤1 player per team (avoids teammates splitting the same TDs)
    one_per_team = ok.drop_duplicates("team")
    core = one_per_team.head(6)
    L += ["", "## Tickets (≤1 player per team; correlation-priced)", ""]
    for n, label in [(2, "Chalk double"), (3, "Chalk triple"), (4, "4-leg"), (6, "6-leg ladder")]:
        legs = core.head(n)
        pj, pi = joint(legs, corr), float(np.prod(legs.p_attd))
        L.append(f"**{label}** — {pj:.1%} · fair {am(pj)}  ·  " +
                 " + ".join(f"{r.name} ({r.p_attd:.0%})" for r in legs.itertuples()))
    # a second, non-overlapping ticket so the slip isn't one story
    alt = one_per_team.iloc[6:9]
    if len(alt) == 3:
        pj = joint(alt, corr)
        L.append(f"**Second triple (no overlap with the chalk)** — {pj:.1%} · fair {am(pj)}  ·  " +
                 " + ".join(f"{r.name} ({r.p_attd:.0%})" for r in alt.itertuples()))

    # best same-game doubles (opponents: slight positive correlation; teammates: negative)
    rows = []
    for g, q in ok.groupby("game_id"):
        a = q[q.team == q.team.iloc[0]].head(1)
        b = q[q.team != q.team.iloc[0]].head(1)
        if len(a) and len(b):
            legs = pd.concat([a, b])
            rows.append((joint(legs, corr), legs))
    rows.sort(key=lambda x: -x[0])
    L += ["", "## Best same-game doubles (one from each side)", ""]
    for pj, legs in rows[:5]:
        L.append(f"- {legs.matchup.iloc[0]}: " + " + ".join(f"{r.name} ({r.p_attd:.0%})" for r in legs.itertuples())
                 + f" — {pj:.1%} · fair {am(pj)}")

    so = P[P.singles_only.fillna(False).astype(bool) & (P.p_attd >= 0.25)].sort_values("p_attd", ascending=False)
    if len(so):
        L += ["", "## Singles only (Questionable or first game back from a 2+ game absence)", ""]
        L += [f"- {r.name} ({r.team} {r.pos_group}) {r.p_attd:.0%} · fair {am(r.p_attd)} · play at {r.play_at}"
              + (f" · {r.injury_status}" if isinstance(r.injury_status, str) else
                 f" · missed {int(r.games_missed_last4)} of last 4") for r in so.head(10).itertuples()]
    L += ["", "## By game — top 3 each side", ""]
    for g, q in P.groupby("game_id"):
        parts = []
        for t, qq in q.groupby("team"):
            parts.append(f"**{t}** " + ", ".join(f"{r.name} {r.p_attd:.0%}" for r in qq.head(3).itertuples()))
        imp = q.groupby("team").implied_filled.first()
        L.append(f"- {q.matchup.iloc[0]} (implied {' / '.join(f'{t} {v:.1f}' for t, v in imp.items())}): "
                 + " · ".join(parts))
    return "\n".join(L)


# ============================================================================================
STYLES = {
    "chalk": dict(label="Chalk", desc="Highest probabilities, one player per team. RB-heavy, shortest payout, fewest misses."),
    "balanced": dict(label="Balanced", desc="No position is more than half the legs and every ticket carries at least one WR. "
                                             "A few points less likely than chalk, paid like a real parlay."),
    "air": dict(label="Air (singles only)", desc="Receivers only. Shown for reference: WR/TE anytime TDs are singles under the Week 9 rule (1 of 8 hit; ledger pattern), not ticket legs."),
}


def _pick_style(ok: pd.DataFrame, n: int, style: str) -> pd.DataFrame:
    """Greedy fill from the probability-sorted eligible pool, ≤1 per team, with position caps that apply at every
    length as the ticket grows, so the 4-leg is balanced on its own and the 6-leg extends it (tickets nest)."""
    import math

    def caps(i):   # caps when choosing leg number i (1-based)
        if style == "chalk":
            return {}
        if style == "balanced":
            return {"RB": math.ceil(i / 2), "WR": math.ceil(i / 2), "TE": max(1, i // 4), "QB": max(1, i // 6)}
        return {"RB": 0, "WR": i, "TE": max(1, i // 3), "QB": max(1, i // 4)}

    chosen, teams, cnt = [], set(), {}
    while len(chosen) < n:
        c = caps(len(chosen) + 1)
        pick = next((r for r in ok.itertuples() if r.Index not in chosen and r.team not in teams
                     and cnt.get(r.pos_group, 0) < c.get(r.pos_group, n)), None)
        if pick is None:
            break
        chosen.append(pick.Index); teams.add(pick.team); cnt[pick.pos_group] = cnt.get(pick.pos_group, 0) + 1
    return ok.loc[chosen]


def ticket_sets(proj: pd.DataFrame, games: list[str], sizes=(4, 6, 8, 10, 12), style="chalk"):
    """Best ATD tickets per size: highest-probability eligible legs, ≤1 per team (teammates split TDs),
    so the only same-game pairs are opponents (measured ρ>0).  Joint priced with the ATD copula."""
    corr = json.loads((ROOT / "models" / "correlations.json").read_text())
    P = proj[proj.game_id.isin(games)].copy()
    P["matchup"] = P.game_id.str.split("_").str[2] + "@" + P.game_id.str.split("_").str[3]
    P["min_p_needed"] = P.p_attd - P.pos_group.map(CUSHION).fillna(0.04)
    P["play_at"] = P.min_p_needed.map(am)
    ok = P[~P.singles_only.fillna(False).astype(bool)]
    if style != "air": ok = ok[ok.pos_group.isin(["RB", "QB"])]     # Fix 5: WR/TE TDs are singles only
    ok = ok.sort_values("p_attd", ascending=False)
    out = []
    for n in sizes:
        legs = _pick_style(ok, n, style)
        pj, pi = joint(legs, corr), float(np.prod(legs.p_attd))
        pairs = []
        for g, q in legs.groupby("game_id"):
            if len(q) == 2:
                rho = build_sigma(q, corr)[0, 1]
                pairs.append((q.iloc[0]["name"], q.iloc[1]["name"], q.matchup.iloc[0], float(rho)))
        out.append({"n": n, "legs": legs, "p": pj, "p_indep": pi, "lift": pj / pi, "pairs": pairs, "style": style})
    return P, out, corr
