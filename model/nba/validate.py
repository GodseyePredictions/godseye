"""Turn the backtest output into the validation report (docs/nba_backtest.md and output/backtest_report.json).

Usage (from model/):  python3 -m nba.validate          (after python3 -m nba.backtest)
Every figure comes with its sample size; anything on fewer than `small_sample` cases is marked.
"""
import json

import numpy as np
import pandas as pd

from nba import game_sim as gs
from nba import props
from nba.config import CONFIG
from nba.pipeline import Pipeline
from nba.store import HERE, connect, load_frames

OUT = HERE / "output"
DOCS = HERE.parent.parent / "docs"
SMALL = CONFIG["small_sample"]


def flag(n):
    return " (too small to trust)" if n < SMALL else ""


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.itertuples(index=False):
        lines.append("| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(lines)


def calib(d: pd.DataFrame, p="p", y="hit", edges=(0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0001)) -> pd.DataFrame:
    b = pd.cut(d[p], edges, right=False)
    g = d.groupby(b, observed=True).agg(legs=(y, "size"), forecast=(p, "mean"), actual=(y, "mean")).reset_index()
    g["bucket"] = [f"{int(i.left * 100)}-{min(100, int(i.right * 100))}%" for i in g[p]]
    g["gap"] = g.actual - g.forecast
    g["note"] = [flag(n).strip() for n in g.legs]
    return g[["bucket", "legs", "forecast", "actual", "gap", "note"]]


def minutes_section(M: pd.DataFrame) -> tuple[str, dict]:
    rows = []
    for season, ds in list(M.groupby("season")) + [("both", M)]:
        for name, d in (("all games", ds), ("normal (no rotation player out, no blowout)", ds[(ds.starter_out == 0) & (ds.blowout == 0)]),
                        ("a rotation player out", ds[ds.starter_out == 1]), ("blowouts", ds[ds.blowout == 1])):
            rows.append({"season": season, "games": name, "player-games": len(d), "MAE model": float((d.min_mean - d.act).abs().mean()),
                         "MAE baseline": float((d.base_min - d.act).abs().mean()), "beat 10th pct": float((d.act > d.p10).mean()),
                         "beat 50th pct": float((d.act > d.p50).mean()), "beat 90th pct": float((d.act > d.p90).mean())})
    t = pd.DataFrame(rows)
    return table(t), {"minutes": rows}


def game_section(G: pd.DataFrame) -> tuple[str, dict]:
    out, js = [], {}
    rows = []
    for season, d in list(G.groupby("season")) + [("both", G)]:
        rows.append({"season": season, "games": len(d), "margin MAE (ours)": float((d.margin - d.model_margin).abs().mean()),
                     "margin MAE (ratings only)": float((d.margin - d.rating_margin).abs().mean()),
                     "margin MAE (always 0)": float(d.margin.abs().mean()), "total MAE (ours)": float((d.total - d.model_total).abs().mean()),
                     "total MAE (season average)": float((d.total - d.total.mean()).abs().mean()),
                     "winner picked": float(((d.model_margin > 0) == (d.margin > 0)).mean()),
                     "margin inside 10-90% band": float(((d.margin > d.m_p10) & (d.margin < d.m_p90)).mean()),
                     "total inside 10-90% band": float(((d.total > d.t_p10) & (d.total < d.t_p90)).mean())})
    out.append(table(pd.DataFrame(rows)))
    js["game"] = rows
    w = G.assign(hit=(G.margin > 0).astype(int))
    out.append("\n**Home win probability calibration**\n\n" + table(calib(w, "p_home", "hit").rename(columns={"legs": "games"})))
    b = G.assign(hit=G.blowout)
    out.append("\n**Blowout probability calibration** (blowout = lead of 15+ entering the fourth, or 20+ at any point in the second half)\n\n" +
               table(calib(b, "p_blowout", "hit", (0, .3, .4, .5, .6, .7, 1.0001)).rename(columns={"legs": "games"})))
    fl = G[G.p_blowout >= CONFIG["blowout_flag_prob"]]
    hi = G[G.p_blowout >= 0.6]
    out.append(f"\nPredicted blowouts: games given 60%+ blowout probability were blowouts {hi.blowout.mean():.1%} of the time "
               f"({len(hi)} games{flag(len(hi))}). All games: predicted {G.p_blowout.mean():.1%}, actual {G.blowout.mean():.1%}. "
               f"Close games: predicted {G.p_close.mean():.1%}, actual {G.close.mean():.1%}. Overtime: predicted {G.p_ot.mean():.1%}, actual {G.ot.mean():.1%}. "
               f"The blowout warning (probability at or above {CONFIG['blowout_flag_prob']:.0%}) fired in {len(fl) / len(G):.0%} of games.")
    js["blowout"] = {"pred": float(G.p_blowout.mean()), "actual": float(G.blowout.mean()), "flag_share": float(len(fl) / len(G)),
                     "p60_actual": float(hi.blowout.mean()) if len(hi) else None, "p60_n": int(len(hi))}
    return "\n".join(out), js


def legs_section(L: pd.DataFrame, D: pd.DataFrame, T: pd.DataFrame, Cr: pd.DataFrame) -> tuple[str, dict]:
    P = L[L.player_id.notna()]
    GL = L[L.player_id.isna()]
    out, js = [], {}
    for season, d in list(P.groupby("season")) + [("both", P)]:
        out.append(f"\n**Player legs, season {season}** ({len(d):,} legs on the calibration grid)\n\n" + table(calib(d)))
    hi = P[P.p >= CONFIG["sgp_leg_floor"]]
    rows = []
    for m, d in hi.groupby("market"):
        rows.append({"market": m, "legs at 70%+": len(d), "forecast": float(d.p.mean()), "actual": float(d.hit.mean()),
                     "gap": float(d.hit.mean() - d.p.mean()), "note": flag(len(d)).strip()})
    out.append("\n**Legs the model calls 70% or better, by market**\n\n" + table(pd.DataFrame(rows)))
    js["legs70"] = rows
    b7 = P[(P.p >= 0.7) & (P.p < 0.8)]
    js["bucket_70_80"] = {"n": int(len(b7)), "forecast": float(b7.p.mean()), "actual": float(b7.hit.mean())}
    rows = []
    for m, d in P.groupby("market"):
        d7 = d[(d.p >= .7) & (d.p < .8)]
        rows.append({"market": m, "all legs": len(d), "mean abs gap by bucket": float(calib(d).query("legs >= 200").gap.abs().mean()),
                     "70-80% bucket legs": len(d7), "70-80% forecast": float(d7.p.mean()), "70-80% actual": float(d7.hit.mean())})
    out.append("\n**Calibration by market**\n\n" + table(pd.DataFrame(rows)))
    js["by_market"] = rows
    combo = P[P.market.isin(["pra", "pr", "pa"])]
    out.append("\n**Combo markets only (PRA, P+R, P+A), counted from joint results**\n\n" + table(calib(combo)))
    dd = D.rename(columns={"p_dd": "p", "dd": "hit"})
    out.append(f"\n**Double-doubles** ({len(dd):,} player-games with 20+ projected minutes)\n\n" + table(calib(dd)))
    td = D.rename(columns={"p_td": "p", "td": "hit"})
    out.append(f"\n**Triple-doubles**: forecast {td.p.mean():.2%}, actual {td.hit.mean():.2%} over {len(td):,} player-games; "
               f"players given 10%+: forecast {td[td.p >= .1].p.mean():.1%}, actual {td[td.p >= .1].hit.mean():.1%} "
               f"({len(td[td.p >= .1])} cases{flag(len(td[td.p >= .1]))}).")
    js["dd"] = calib(dd).to_dict("records")
    out.append("\n**Game legs (moneyline, spreads, totals on a fixed grid)**\n\n" + table(calib(GL)))
    rows = []
    for m, d in GL.groupby("market"):
        rows.append({"market": m, "legs": len(d), "mean abs gap by bucket": float(calib(d).query("legs >= 200").gap.abs().mean())})
    out.append("\n" + table(pd.DataFrame(rows)))
    # tickets
    rows = []
    for (ty, season), d in list(T.groupby(["type", "season"])) + [((ty, "both"), d) for ty, d in T.groupby("type")]:
        rows.append({"ticket": ty, "season": season, "tickets": len(d), "modelled joint probability": float(d.joint.mean()),
                     "actual hit rate": float(d.hit.mean()), "gap": float(d.hit.mean() - d.joint.mean()),
                     "if legs were multiplied": float((d.avg_leg_p ** d.n_legs).mean()), "note": flag(len(d)).strip()})
    out.append("\n**Tickets: hit rate against modelled joint probability** (no prices: these are built for highest joint probability, not value)\n\n" +
               table(pd.DataFrame(rows).sort_values(["ticket", "season"], key=lambda s: s.astype(str))))
    js["tickets"] = rows
    rows = []
    for name, d in (("blowout-flagged games", hi[hi.flagged == 1]), ("other games", hi[hi.flagged == 0]),
                    ("early season (first 20 games)", hi[hi.game_no <= 20]), ("mid-season (21-55)", hi[(hi.game_no > 20) & (hi.game_no <= 55)]),
                    ("after the All-Star break (56-72)", hi[(hi.game_no > 55) & (hi.game_no <= 72)]), ("final weeks (73+)", hi[hi.game_no > 72]),
                    ("starters", hi[hi.role == "starter"]), ("bench", hi[hi.role != "starter"]),
                    ("team has a rotation player out", hi[hi.starter_out == 1])):
        rows.append({"70%+ legs in": name, "legs": len(d), "forecast": float(d.p.mean()), "actual": float(d.hit.mean()),
                     "gap": float(d.hit.mean() - d.p.mean()), "note": flag(len(d)).strip()})
    out.append("\n**70%+ legs by situation**\n\n" + table(pd.DataFrame(rows)))
    js["situations"] = rows
    bl = hi[(hi.flagged == 1) & hi.p_blowout.notna()]
    out.append(f"\nBlowout rule: in flagged games, 70%+ legs that also clear 70% inside blowout simulations hit "
               f"{bl[bl.p_blowout >= .7].hit.mean():.1%} ({len(bl[bl.p_blowout >= .7]):,} legs); those that do not hit "
               f"{bl[bl.p_blowout < .7].hit.mean():.1%} ({len(bl[bl.p_blowout < .7]):,} legs{flag(len(bl[bl.p_blowout < .7]))}).")
    g = hi[hi.market.isin(["pts", "fg3m", "pra", "pr", "pa"])]
    rows = [{"70%+ scoring legs": n, "legs": len(d), "forecast": float(d.p.mean()), "actual": float(d.hit.mean()), "gap": float(d.hit.mean() - d.p.mean())}
            for n, d in (("pass the shooting gate", g[g.gate_ok == 1]), ("fail the shooting gate", g[g.gate_ok == 0]))]
    out.append("\n**Shooting gate**\n\n" + table(pd.DataFrame(rows)))
    js["gate"] = rows
    rows = [{"pair": p, "cases": len(d), "simulated correlation": float(d.sim_corr.mean()), "historical correlation": float(d.zz.clip(-9, 9).mean())}
            for p, d in Cr.groupby("pair")]
    out.append("\n**Simulated against historical correlation** (historical = average product of standardised surprises)\n\n" + table(pd.DataFrame(rows)))
    js["corr"] = rows
    return "\n".join(out), js


def ablation(pl: Pipeline, seasons=(2025, 2026)) -> tuple[str, dict]:
    """Out-of-sample accuracy of the rate models with each factor group switched off. Lower deviance is better."""
    D = pl.D
    rows = []
    groups = list(CONFIG["factor_groups_on"])
    everything = {g: True for g in groups}
    for s in seasons:
        tr, te = D[(D.season < s) & (D.pending == 0)], D[(D.season == s) & (D.pending == 0)]
        full = props.deviance(props.fit(tr, pl.cfg, everything), te)
        none = props.deviance(props.fit(tr, pl.cfg, {g: False for g in groups}), te)
        for g in groups:
            off = props.deviance(props.fit(tr, pl.cfg, {**everything, g: False}), te)
            for stat in full:
                rows.append({"season": s, "group": g, "stat": stat, "full": full[stat], "without": off[stat], "baseline_only": none[stat]})
    A = pd.DataFrame(rows)
    A["gain"] = (A.without - A.full) / A.full          # positive = the group helps
    piv = A.groupby(["group", "stat"]).gain.mean().unstack("stat")
    piv = piv[[c for c in props.FEATS if c in piv.columns]]
    both = A.groupby(["group", "season"]).gain.mean().unstack("season")
    verdict = {}
    lines = ["| factor group | " + " | ".join(piv.columns) + " | mean | helps in both seasons | verdict |", "|---|" + "---|" * (len(piv.columns) + 3)]
    for g in groups:
        vals = piv.loc[g]
        used = vals[vals.abs() > 1e-9]
        mean = float(used.mean()) if len(used) else 0.0
        ok = bool((both.loc[g] > 0).all())
        verdict[g] = "keep" if (mean > 0.0002 and ok) else "switch off"
        lines.append(f"| {props.LABEL[g]} | " + " | ".join("n/a" if abs(v) < 1e-9 else f"{v:+.2%}" for v in vals) + f" | {mean:+.2%} | {'yes' if ok else 'no'} | {verdict[g]} |")
    # team model inputs
    G = pl.G
    trows = []
    for name, drop in (("referee crew", ("ref_pts", "ref_pf")), ("style clash", ("s_3pa", "s_orb", "s_tov", "s_fta")),
                       ("rest, back-to-back, travel", ("d_b2b", "d_3in4", "d_trip", "d_rest", "d_tz", "s_b2b")),
                       ("who is missing tonight", ("d_missing", "s_missing"))):
        for s in seasons:
            tr, te = G[(G.season < s) & (G.pending == 0)], G[(G.season == s) & (G.pending == 0)]
            f, o = gs.fit_team_model(tr).predict(te), gs.fit_team_model(tr, drop).predict(te)
            trows.append({"input": name, "season": s, "margin MAE with": float((te.margin - f.model_margin).abs().mean()),
                          "margin MAE without": float((te.margin - o.model_margin).abs().mean()),
                          "total MAE with": float((te.total - f.model_total).abs().mean()),
                          "total MAE without": float((te.total - o.model_total).abs().mean())})
    text = ("Each cell is how much worse the out-of-sample fit gets when the group is removed (positive = the group helps). "
            "Fitted on earlier seasons, scored on 2024-25 and 2025-26.\n\n" + "\n".join(lines) +
            "\n\n**Game-level inputs** (margin and total error with and without each)\n\n" + table(pd.DataFrame(trows)))
    return text, {"ablation": A.groupby(["group", "stat"]).gain.mean().reset_index().to_dict("records"), "verdict": verdict, "team_inputs": trows}


def main():
    G, M, L, D, T, Cr = [pd.read_csv(OUT / f"backtest_{n}.csv.gz") for n in ("games", "minutes", "legs", "dd", "tickets", "corr")]
    con = connect()
    pl = Pipeline(load_frames(con))
    report, js = [], {"games": int(len(G)), "seasons": sorted(int(s) for s in G.season.unique())}
    for title, fn, args in (("Minutes and role model", minutes_section, (M,)), ("Game script engine", game_section, (G,)),
                            ("Player simulation, legs and tickets", legs_section, (L, D, T, Cr)), ("Factor ablation", ablation, (pl,))):
        text, part = fn(*args)
        report.append(f"## {title}\n\n{text}")
        js.update(part)
    (OUT / "backtest_report.json").write_text(json.dumps(js, indent=1, default=float))
    (OUT / "backtest_sections.md").write_text("\n\n".join(report))
    print("\n\n".join(report))


if __name__ == "__main__":
    main()
