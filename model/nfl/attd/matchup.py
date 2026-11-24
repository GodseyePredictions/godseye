"""EXPERIMENTAL matchup reads (Nov 19 2026, user test; not part of the default build).

For a candidate prop leg, look at how the same role slot has done against this defence this season:
QB = most attempts, RB1/RB2 by carries, WR1/WR2/WR3 and TE1 by targets in that game. The read is the share of
opponents in that slot who cleared the line. Passing-side positional splits carry little week to week (tested
2023-26: ~80% of the gap between soft and stingy defences is gone the next game), so the read steers leg selection
and never changes a probability."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DATA_DIR

COL = {"rec": "receptions", "rec_yds": "receiving_yards", "rush_yds": "rushing_yards", "carries": "carries",
       "pass_att": "attempts", "pass_yds": "passing_yards", "pass_td": "passing_tds"}


def _slots(g: pd.DataFrame) -> pd.DataFrame:
    """Label each player-game with a role slot within his team that week."""
    g = g.copy(); g["slot"] = None
    key = ["team", "week"]
    q = g[g.position == "QB"]; q = q.assign(r=q.groupby(key).attempts.rank(ascending=False, method="first"))
    g.loc[q[q.r == 1].index, "slot"] = "QB"
    r = g[g.position == "RB"]; r = r.assign(r=r.groupby(key).carries.rank(ascending=False, method="first"))
    g.loc[r[r.r == 1].index, "slot"] = "RB1"; g.loc[r[r.r == 2].index, "slot"] = "RB2"
    for pos, n in (("WR", 3), ("TE", 1)):
        w = g[g.position == pos]; w = w.assign(r=w.groupby(key).targets.rank(ascending=False, method="first"))
        for i in range(1, n + 1):
            g.loc[w[w.r == i].index, "slot"] = f"{pos}{i}"
    return g


def reads(season: int, week: int, game_id: str, L: pd.DataFrame, PF: pd.DataFrame) -> pd.DataFrame:
    sw = pd.read_parquet(DATA_DIR / f"stats_week_{season}.parquet")
    sw = sw[(sw.season_type == "REG") & (sw.week < week)].copy()
    for c in ("attempts", "carries", "targets"):
        sw[c] = sw[c].fillna(0)
    sw = _slots(sw)
    # tonight's slot for each projected player: rank on recent usage within his team
    f = PF[PF.game_id == game_id].drop_duplicates("player_id").copy()
    f["slot"] = None
    for t, q in f.groupby("team"):
        qb = q[q.pos_group == "QB"].sort_values("pass_att_p3", ascending=False)
        if len(qb): f.loc[qb.index[0], "slot"] = "QB"
        rb = q[q.pos_group == "RB"].sort_values("carries_p3", ascending=False)
        for i, ix in enumerate(rb.index[:2], 1): f.loc[ix, "slot"] = f"RB{i}"
        wr = q[q.pos_group == "WR"].sort_values("tgt_p3", ascending=False)
        for i, ix in enumerate(wr.index[:3], 1): f.loc[ix, "slot"] = f"WR{i}"
        te = q[q.pos_group == "TE"].sort_values("tgt_p3", ascending=False)
        if len(te): f.loc[te.index[0], "slot"] = "TE1"
    slot = f.set_index("player_id").slot
    out = []
    q = L[(L.game_id == game_id) & (L.market != "atd")]
    for r in q.itertuples():
        s = slot.get(r.player_id)
        if s is None or r.market not in COL:
            continue
        log = sw[(sw.opponent_team == r.opp) & (sw.slot == s)]
        if len(log) < 5:
            continue
        v = log[COL[r.market]].fillna(0)
        out.append({"player_id": r.player_id, "market": r.market, "k": r.k, "slot": s, "read_n": len(v),
                    "read_hits": int((v >= r.k).sum()), "read": float((v >= r.k).mean())})
    return pd.DataFrame(out)


def apply(props: pd.DataFrame, R: pd.DataFrame, drop_gap=0.25, drop=True, mode="steer") -> pd.DataFrame:
    """Attach the read to candidate legs: shift script fit by (read - model), drop a leg whose read trails the model by
    drop_gap or more. Probabilities are untouched."""
    if R is None or R.empty:
        return props
    p = props.merge(R, on=["player_id", "market", "k"], how="left")
    gap = (p["read"] - p.p).fillna(0)
    if mode == "consensus":
        # Agreed legs only (Nov 21 2026): the model must price the leg AND at least 60% of that role must have cleared
        # the line against this defence. The read can veto but never promote, except rushing legs, where run defence
        # is the one split with real carry-over (soft run defences keep ~40% of their gap) and so moves the ranking.
        rushm = p.market.isin(["carries", "rush_yds"])
        p["fit"] = (p.fit + np.where(rushm, (1.5 * gap).clip(-0.6, 0.6), 0.0)).clip(-1, 1)
        p["fit_why"] = [list(w) + ([f"{int(h)} of {int(n)} {s}s cleared this line vs this defence"] if pd.notna(n) else [])
                        for w, h, n, s in zip(p.fit_why, p.read_hits, p.read_n, p.slot)]
        p = p[p["read"].isna() | (p["read"] >= 0.60)]
        return p.drop(columns=["slot", "read_n", "read_hits", "read"])
    p["fit"] = (p.fit + (1.5 * gap).clip(-0.6, 0.6)).clip(-1, 1)
    p["fit_why"] = [list(w) + ([f"{int(h)} of {int(n)} {s}s cleared this line vs this defence"] if pd.notna(n) else [])
                    for w, h, n, s in zip(p.fit_why, p.read_hits, p.read_n, p.slot)]
    # drop: the read trails the model by drop_gap, or fewer than 60% of that role cleared it and the model is 15+ points higher
    if drop:
        p = p[~((gap <= -drop_gap) | ((p["read"] < 0.60) & (gap <= -0.15)))]
    return p.drop(columns=["slot", "read_n", "read_hits", "read"])


def read_modes() -> dict:
    """Games with the matchup overlay switched on (data/matchup_read_games.txt, lines `game_id[,mode]`)."""
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "data" / "matchup_read_games.txt"
    out = {}
    if f.exists():
        for ln in f.read_text().split():
            a = ln.split(","); out[a[0]] = a[1] if len(a) > 1 else "steer"
    return out


def build_game(season, week, L, A, PF, game_id, corr, hold_pass=(), modes=None):
    """One game's script slips in the mode configured for it. In consensus mode a ticket size falls back to the
    algorithm's own slip when too few legs are agreed. Returns (slips, mode_used)."""
    from .script_sgp import build_script_sgps
    modes = read_modes() if modes is None else modes
    mode = modes.get(game_id)
    base = build_script_sgps(L, A, PF, game_id, corr, hold_pass=hold_pass)
    if not mode:
        return base, None
    R = reads(season, week, game_id, L, PF)
    o = build_script_sgps(L, A, PF, game_id, corr, hold_pass=hold_pass, reads=R, read_mode=mode)
    have = {t["n"] for t in o["ladder"]}
    o["ladder"] = sorted(o["ladder"] + [t for t in base["ladder"] if t["n"] not in have], key=lambda t: t["n"])
    for k in ("hybrid1", "hybrid2", "hybrid6_1", "hybrid6_2", "hybrid8_1", "hybrid8_2"):
        if not o.get(k):
            o[k] = base.get(k)
    o["fallback_sizes"] = sorted(t["n"] for t in base["ladder"] if t["n"] not in have)
    return o, mode
