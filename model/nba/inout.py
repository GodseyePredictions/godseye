"""Teammate in/out: where a missing rotation player's minutes, shots, rebounds and assists go.

For every pair of teammates the model keeps, game by game, how player A's minutes and per-minute
rates differ in games B missed. The split is shrunk toward "no difference" by sample size. With
fewer than `wowy_min_games` games without B, a positional rule is used instead and labelled so.

The baseline already contains whatever absences happened in the games it was built from, so
tonight's adjustment for each teammate is: effect x (out tonight - share of baseline games he missed).
That one formula covers a player going out, several out at once, and a star coming back.

The split is by game (who dressed), from box scores, because that can be rebuilt for any past date.
Possession-level on/off (pbpstats) is finer but cannot be re-pulled point-in-time fast enough to backtest.
"""
import numpy as np
import pandas as pd

from nba.config import CONFIG

STATS = ["fga", "fg3a", "fta", "reb", "ast", "pts"]
NEAR = {("G", "G"): 1.0, ("F", "F"): 1.0, ("C", "C"): 1.0, ("G", "F"): 0.5, ("F", "G"): 0.5,
        ("F", "C"): 0.6, ("C", "F"): 0.6, ("G", "C"): 0.15, ("C", "G"): 0.15}


def baseline_minutes(P: pd.DataFrame, cfg=CONFIG) -> pd.Series:
    """Blend of season, last-10 and last-5 minutes per game, leaning on recent games when the role has moved."""
    s = P.s_min / P.s_n.replace(0, np.nan)
    l5 = P.l5_min / P.l5_n.replace(0, np.nan)
    l10 = P.l10_min / P.l10_n.replace(0, np.nan)
    prev = P.prev_min / P.prev_n.replace(0, np.nan)
    k = cfg["min_prior_games"]
    s = (P.s_min + k * prev.fillna(l10).fillna(0)) / (P.s_n + k).where(prev.notna() | l10.notna(), P.s_n.replace(0, np.nan))
    s = s.fillna(l10).fillna(prev)
    l5, l10 = l5.fillna(s), l10.fillna(s)
    moved = (l5 - s).abs() >= cfg["role_change_minutes"]
    w, wr = cfg["min_weights"], cfg["min_weights_role_change"]
    normal = w["season"] * s + w["last10"] * l10 + w["last5"] * l5
    changed = wr["season"] * s + wr["last10"] * l10 + wr["last5"] * l5
    return normal.where(~moved, changed)


def status_quo_out(P: pd.DataFrame, reported_out: dict, reported_teams: dict, long_gap_days: float = 10.0) -> pd.Series:
    """Is each player expected to miss this game, from what was known before tip?
    Listed Out or Doubtful on the report = out. Team filed and player not listed = in.
    No report for the team = status quo: a player who has not played for `long_gap_days` stays out."""
    listed = np.array([pid in reported_out.get(g, ()) for g, pid in zip(P.game_id, P.player_id)])
    filed = np.array([t in reported_teams.get(g, ()) for g, t in zip(P.game_id, P.team_id)])
    stale = (P.days_since_played.fillna(999) > long_gap_days).to_numpy() & (P.s_n.to_numpy() > 0)   # a summer break is not an absence
    return pd.Series(np.where(listed, 1, np.where(filed, 0, stale.astype(int))), index=P.index)


def adjustments(P: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Per player per game: log-multipliers for minutes and per-minute rates, plus the reasons.
    Needs columns base_min, exp_out (0/1 expected out tonight) on top of the feature frame."""
    k0, min_n, rot = cfg["wowy_prior_games"], cfg["wowy_min_games"], cfg["rotation_min"]
    out_rows = []
    P = P.sort_values("tip")
    for (team, season), d in P.groupby(["team_id", "season"], sort=False):
        ids = d.player_id.unique()
        ix = {p: i for i, p in enumerate(ids)}
        n = len(ids)
        K = len(STATS)
        with_n = np.zeros((n, n)); wo_n = np.zeros((n, n))
        with_min = np.zeros((n, n)); wo_min = np.zeros((n, n))
        with_x = np.zeros((n, n, K)); wo_x = np.zeros((n, n, K))
        seen = np.zeros(n, bool)                      # has appeared for this team this season
        recent = [[] for _ in range(n)]               # last five "who was absent" vectors for each player
        for gid, g in d.groupby("game_id", sort=False):
            i_all = np.array([ix[p] for p in g.player_id])
            base = g.base_min.fillna(0).to_numpy()
            exp_out = g.exp_out.to_numpy().astype(bool)
            grp = g.grp.to_numpy()
            names, pend, was_played, pids = g["name"].to_numpy(), g.pending.to_numpy(), g.played.to_numpy(), g.player_id.to_numpy()
            # ---- tonight's adjustment, from pair tables that hold earlier games only
            rot_mask = (base >= rot) & (g.last_team.to_numpy() == team)
            jj = np.where(rot_mask)[0]
            for a in range(len(g)):
                i = i_all[a]
                if pend[a] == 0 and was_played[a] != 1:
                    continue
                if exp_out[a] or base[a] <= 0:
                    continue
                adj = np.zeros(K + 1); notes = []; n_out = 0
                tot_i = with_n[i].max() if n else 0
                for b in jj:
                    if b == a:
                        continue
                    j = i_all[b]
                    nw, no = with_n[i, j], wo_n[i, j]
                    hist = recent[i]
                    share5 = np.mean([h[j] for h in hist]) if hist else 0.0
                    share_s = no / (nw + no) if nw + no > 0 else 0.0
                    share = 0.5 * share5 + 0.5 * share_s
                    x = float(exp_out[b]) - share
                    n_out += int(exp_out[b])
                    if abs(x) < 0.05:
                        continue
                    if no >= min_n and nw >= min_n:
                        w = no / (no + k0) * nw / (nw + k0 / 2)
                        e = np.zeros(K + 1)
                        e[0] = w * np.log(max(wo_min[i, j] / no, 1.0) / max(with_min[i, j] / nw, 1.0))
                        r_wo = wo_x[i, j] / max(wo_min[i, j], 1.0); r_w = with_x[i, j] / max(with_min[i, j], 1.0)
                        ok = (r_wo > 0) & (r_w > 0)
                        e[1:][ok] = w * np.log(r_wo[ok] / r_w[ok])
                        how = f"with/without, {int(no)} games without"
                    else:                               # positional rule
                        wt = np.array([NEAR.get((grp[c], grp[b]), 0.3) * base[c] if (c != b and not exp_out[c]) else 0.0
                                       for c in range(len(g))])
                        sh = wt[a] / wt.sum() if wt.sum() > 0 else 0.0
                        e = np.zeros(K + 1)
                        e[0] = np.log1p(sh * base[b] / max(base[a], 1.0) * 0.9)
                        e[1:] = 0.10 * NEAR.get((grp[a], grp[b]), 0.3) * min(1.0, base[b] / 30.0)
                        how = f"positional rule, only {int(no)} games without"
                    e = np.clip(e, -0.5, 0.5)
                    adj += x * e
                    if abs(x * e[0]) >= 0.02 or np.abs(x * e[1:]).max() >= 0.03:
                        notes.append(f"{names[b]} {'out' if x > 0 else 'back'}: minutes {x * e[0]:+.0%}, "
                                     f"shots/min {x * e[1]:+.0%} ({how})")
                adj = np.clip(adj, -0.6, 0.6)
                out_rows.append((gid, pids[a], n_out, *adj, "; ".join(notes[:4])))
            # ---- then file this game (only if it has been played)
            if pend[0] == 1:
                continue
            played = np.zeros(n, bool); mins = np.zeros(n); X = np.zeros((n, K))
            pl = g.played.to_numpy() == 1
            played[i_all[pl]] = True
            mins[i_all[pl]] = g["min"].to_numpy()[pl]
            X[i_all[pl]] = g[STATS].to_numpy(float)[pl]
            seen |= played
            absent = seen & ~played
            pi = np.where(played)[0]
            with_n[np.ix_(pi, pi)] += 1; with_min[np.ix_(pi, pi)] += mins[pi][:, None]
            with_x[np.ix_(pi, pi)] += X[pi][:, None, :]
            ai = np.where(absent)[0]
            if len(ai):
                wo_n[np.ix_(pi, ai)] += 1; wo_min[np.ix_(pi, ai)] += mins[pi][:, None]
                wo_x[np.ix_(pi, ai)] += X[pi][:, None, :]
            av = absent.astype(float)
            for i in pi:
                recent[i].append(av)
                if len(recent[i]) > 5:
                    recent[i].pop(0)
    cols = ["game_id", "player_id", "n_rot_out", "io_min"] + ["io_" + s for s in STATS] + ["io_notes"]
    return pd.DataFrame(out_rows, columns=cols)
