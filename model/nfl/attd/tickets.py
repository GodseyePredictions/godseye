"""Ticket construction following the standing rules from the 2026 ledger.

  * Props SGPs never contain TD legs; ATDs are their own ticket.  Every pack: floor 4/6/8, aggressive 4/6/8,
    ATD ticket per game, all-position slips, cross-game combos 4/6/8/10/12, full-slate ATD slip.
  * bet365 milestone ladders only (yards from 20 in 10s, carries 10/15/20/25, pass yds by 25 from 150,
    attempts by 5, receptions from 1+).
  * Questionable / return-from-absence players are singles only.  Role gate (2+ games; RB 8 touches/g,
    WR/TE 4 targets/g, QB 20 att/g).  Distinct players per props SGP, market cap 2, one RB volume leg per team.
  * Floor band 70-88% (target 78%), aggressive 55-68% (target 62%).
  * Joint prices from the measured leg-correlation copula (same game) x independence (across games).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .correlation import ticket_prob
from .props import MARKETS, YARDAGE

BANDS = {"floor": (0.70, 0.88, 0.78), "aggressive": (0.55, 0.68, 0.62), "mid": (0.62, 0.74, 0.68)}
RB_VOLUME = {"carries", "rush_yds"}


def fair(p):
    p = float(np.clip(p, 1e-4, 1 - 1e-4))
    return int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))


def fmt_am(a):
    return f"+{a}" if a > 0 else str(a)


def leg_text(r):
    if r.market == "atd":
        return f"{r['name']} ANYTIME TD"
    return f"{r['name']} {int(r.k)}+ {MARKETS[r.market]['label']}"


def pick_rungs(legs: pd.DataFrame, band: str, sanity=True) -> pd.DataFrame:
    """One rung per (player, market): the in-band rung closest to the band target."""
    lo, hi, tgt = BANDS[band]
    L = legs[(legs.market != "atd") & legs.p.between(lo, hi) & legs.role_ok & ~legs.singles_only].copy()
    VOL = L.market.isin(["carries", "rush_yds", "pass_att"])   # backtest: gates only help volume markets
    # replacement lead back (starter ruled out): his rushing lines are judged on this week's role, so they skip the
    # fresh-role gate and the season hit-rate gate (Nov 21 2026; Montgomery, Week 11)
    LR = (L.lead_repl.fillna(False).astype(bool) & L.market.isin(["carries", "rush_yds"])) if "lead_repl" in L.columns \
        else pd.Series(False, index=L.index)
    if "fresh_role" in L.columns:   # Fix 3 (Week 9): fresh roles are singles only on volume legs
        keep = ~(VOL & (L.fresh_role.fillna(0) == 1)) | LR
        L, VOL, LR = L[keep], VOL[keep], LR[keep]
    if sanity:  # v1.9d sanity gate: the player must actually clear this rung often this season
        need = np.where(L.market.isin(YARDAGE), 0.65, 0.60) - (0.0 if band == "floor" else 0.15)
        keep = (L.season_n < 3) | (L.season_rate >= need) | LR
        L, LR = L[keep], LR[keep]
    if sanity and band == "floor" and "season_min" in L.columns:
        # Fix 4 (Week 9): a floor leg must survive the player's worst game OR his average in losses
        has = (L.season_n >= 3) & L.market.isin(["carries", "rush_yds", "pass_att"])
        ok = (L.season_min >= L.k) | (L.loss_mean >= L.k)
        L = L[~has | ok.fillna(False) | LR.reindex(L.index).fillna(False)]
    L["dist"] = (L.p - tgt).abs()
    return L.sort_values("dist").drop_duplicates(["player_id", "market"])


def greedy(pool: pd.DataFrame, n_max=8, distinct_players=True, market_cap=2, max_per_game=None,
           max_per_team=None):
    chosen, players, mk_count, rbvol_team, game_n, team_n = [], set(), {}, set(), {}, {}
    for _, r in pool.sort_values("p", ascending=False).iterrows():
        if distinct_players and r.player_id in players:
            continue
        if mk_count.get(r.market, 0) >= market_cap:
            continue
        if r.market in RB_VOLUME and r.pos_group == "RB" and r.team in rbvol_team:
            continue
        if max_per_game and game_n.get(r.game_id, 0) >= max_per_game:
            continue
        if max_per_team and team_n.get(r.team, 0) >= max_per_team:
            continue
        chosen.append(r)
        players.add(r.player_id)
        mk_count[r.market] = mk_count.get(r.market, 0) + 1
        if r.market in RB_VOLUME and r.pos_group == "RB":
            rbvol_team.add(r.team)
        game_n[r.game_id] = game_n.get(r.game_id, 0) + 1
        team_n[r.team] = team_n.get(r.team, 0) + 1
        if len(chosen) >= n_max:
            break
    return pd.DataFrame(chosen)


def tiered(legs: pd.DataFrame, corr, sizes=(4, 6, 8)):
    out = {}
    for n in sizes:
        if len(legs) >= n:
            pj = ticket_prob(legs.head(n), corr)
            out[n] = {"p": pj, "fair": fair(pj)}
    return out


def build_card(legs: pd.DataFrame, atd: pd.DataFrame, corr: dict) -> dict:
    """legs: long frame of all prop rungs (+ singles/role info). atd: ATD projections with market='atd'."""
    card = {"games": [], "combos": {}, "atd_slate": {}}
    pools = {b: pick_rungs(legs, b) for b in ("floor", "aggressive")}
    for g in sorted(legs.game_id.unique()):
        game = {"game_id": g}
        for b in ("floor", "aggressive"):
            sel = greedy(pools[b][pools[b].game_id == g], 8)
            game[b] = {"legs": sel, "tiers": tiered(sel, corr) if len(sel) else {}}
        a = atd[(atd.game_id == g)].sort_values("p", ascending=False)
        a_ok = a[~a.singles_only & a.role_ok]
        top = a_ok.head(6)
        game["atd"] = {"legs": a.head(8), "double": ticket_prob(top.head(2), corr) if len(top) >= 2 else None,
                       "triple": ticket_prob(top.head(3), corr) if len(top) >= 3 else None,
                       "singles_only": a[a.singles_only & (a.p >= 0.25)]}
        # all-position slip: best floor leg at QB, RB, WR, TE (distinct players) + top ATD
        fl = pools["floor"][pools["floor"].game_id == g].sort_values("p", ascending=False)
        rows, used = [], set()
        for pos in ("QB", "RB", "WR", "TE"):
            c = fl[(fl.pos_group == pos) & ~fl.player_id.isin(used)]
            if len(c):
                rows.append(c.iloc[0]); used.add(c.iloc[0].player_id)
        if len(top):
            rows.append(top.iloc[0])
        slip5 = pd.DataFrame(rows)
        extra = fl[~fl.player_id.isin(used)].head(2)
        slip8 = pd.concat([slip5, extra, top.iloc[1:2]], ignore_index=True) if len(top) > 1 else slip5
        game["slip5"] = {"legs": slip5, "p": ticket_prob(slip5, corr) if len(slip5) else None}
        game["slip8"] = {"legs": slip8, "p": ticket_prob(slip8, corr) if len(slip8) > len(slip5) else None}
        game["singles"] = legs[(legs.game_id == g) & legs.singles_only & (legs.market != "atd")
                               & legs.p.between(0.70, 0.88)].sort_values("p", ascending=False) \
            .drop_duplicates(["player_id"]).head(6)
        card["games"].append(game)

    # cross-game combos: floor legs, max 2 per game, max 1 per team (diversify by team)
    cg = greedy(pools["floor"], 12, max_per_game=2, max_per_team=1)
    card["combos"] = {"legs": cg, "tiers": tiered(cg, corr, (4, 6, 8, 10, 12))}
    # full-slate ATD slip (eligible only), max 1 per team
    a_ok = atd[~atd.singles_only & atd.role_ok].sort_values("p", ascending=False)
    a_ok = a_ok.drop_duplicates("team")
    card["atd_slate"] = {"board": atd.sort_values("p", ascending=False).head(16),
                         "legs": a_ok.head(6), "tiers": tiered(a_ok.head(6), corr, (2, 3, 4, 6))}
    return card


# --------------------------------------------------------------------------------------------
def card_markdown(card, header: dict, ctx: pd.DataFrame) -> str:
    L = [f"# ATTD + Props card — {header['season']} Week {header['week']}",
         f"*Built {header['built']} · data through the last completed game · bet365 milestones · "
         "play only when the book is longer than fair · quarter-Kelly.*", ""]
    for game in card["games"]:
        g = game["game_id"]
        c = ctx[ctx.game_id == g]
        if len(c):
            h = c[c.is_home == 1].iloc[0] if (c.is_home == 1).any() else c.iloc[0]
            a = c[c.is_home == 0].iloc[0] if (c.is_home == 0).any() else c.iloc[0]
            L.append(f"## {a.team} @ {h.team}")
            if h.wx_cat == "indoor":
                wx = "indoor"
            elif pd.isna(h.temp):
                wx = "weather n/a (no NWS forecast: international or beyond 7 days)"
            else:
                wx = f"{h.wx_cat}, {h.temp:.0f}°F, wind {h.wind:.0f} mph"
            roof = h.roof_type if h.roof_type not in ("nan", "None") else "roof n/a"
            L.append(f"*{h.slot} · {roof} · {'turf' if h.is_turf else 'grass'} · {wx} · implied "
                     f"{a.team} {a.implied_filled:.1f} / {h.team} {h.implied_filled:.1f} · {a.team} travel "
                     f"{a.travel_miles:.0f} mi, {a.tz_shift:+.0f}h, rest {a.rest_days:.0f}d · opp DEF out "
                     f"(snap-wt): {a.team} faces {a.def_out_total:.1f}, {h.team} faces {h.def_out_total:.1f}*")
        else:
            L.append(f"## {g}")
        for b, title in (("floor", "FLOOR SGP"), ("aggressive", "AGGRESSIVE SGP")):
            t = game[b]
            if not len(t["legs"]):
                L.append(f"\n**{title}** — no legs qualify"); continue
            tiers = " · ".join(f"{n}-leg {v['p']:.1%} fair {fmt_am(v['fair'])}" for n, v in t["tiers"].items())
            L += [f"\n**{title}** — {tiers}", "", "| # | Leg | Model | Fair | 2026 pre-game | Tier |",
                  "|---|---|---|---|---|---|"]
            for i, (_, r) in enumerate(t["legs"].iterrows(), 1):
                tier = "4-leg core" if i <= 4 else ("+6" if i <= 6 else "+8")
                L.append(f"| {i} | {leg_text(r)} | {r.p:.0%} | {fmt_am(fair(r.p))} | "
                         f"{int(r.season_hits)}/{int(r.season_n)} | {tier} |")
        at = game["atd"]
        L += ["", "**Anytime TD (separate ticket)**", "", "| Player | Model | Fair | Note | Decomposition |",
              "|---|---|---|---|---|"]
        for _, r in at["legs"].iterrows():
            note = "singles only" if r.singles_only else ("role gate" if not r.role_ok else "")
            L.append(f"| {r['name']} ({r.team} {r.pos_group}) | {r.p:.0%} | {fmt_am(fair(r.p))} | {note} | "
                     f"rush {r.lam_team_rush:.2f}×{r.rush_share:.0%} + pass {r.lam_team_pass:.2f}×{r.rec_share:.0%} |")
        if at["double"]:
            L.append(f"\nTD double: {at['double']:.1%} · fair {fmt_am(fair(at['double']))}" +
                     (f" · triple: {at['triple']:.1%} · fair {fmt_am(fair(at['triple']))}" if at["triple"] else ""))
        for key, lab in (("slip5", "All-position slip"), ("slip8", "All-position 8-leg")):
            s = game[key]
            if s["p"]:
                L.append(f"\n**{lab}** — {s['p']:.1%} · fair {fmt_am(fair(s['p']))}: " +
                         " · ".join(leg_text(r) for _, r in s["legs"].iterrows()))
        if len(game["singles"]):
            L.append("\n*Singles only (Questionable / return from absence):* " + " · ".join(
                f"{leg_text(r)} {r.p:.0%} ({fmt_am(fair(r.p))})" for _, r in game["singles"].iterrows()))
        L.append("")
    cg = card["combos"]
    L += ["## Cross-game combos (floor legs, ≤2 per game, ≤1 per team)", ""]
    for n, v in cg["tiers"].items():
        L.append(f"**{n}-leg** — {v['p']:.1%} · fair {fmt_am(fair(v['p']))}: " +
                 " · ".join(leg_text(r) for _, r in cg["legs"].head(n).iterrows()))
    a = card["atd_slate"]
    L += ["", "## Full-slate ATD board (top 16)", "", "| # | Player | Team | Model | Fair | Note |",
          "|---|---|---|---|---|---|"]
    for i, (_, r) in enumerate(a["board"].iterrows(), 1):
        L.append(f"| {i} | {r['name']} ({r.pos_group}) | {r.team} | {r.p:.0%} | {fmt_am(fair(r.p))} | "
                 f"{'singles only' if r.singles_only else ''} |")
    L.append("")
    for n, v in a["tiers"].items():
        L.append(f"**ATD {n}-leg** (≤1 per team) — {v['p']:.1%} · fair {fmt_am(fair(v['p']))}: " +
                 " · ".join(f"{r['name']}" for _, r in a["legs"].head(n).iterrows()))
    return "\n".join(L)


def card_legs_json(card) -> list[dict]:
    """Flat list of every shipped leg/ticket for grading later ('as shipped')."""
    out = []
    def add(ticket, legs, p):
        for _, r in legs.iterrows():
            out.append({"ticket": ticket, "ticket_p": p, "game_id": r.game_id, "player_id": r.player_id,
                        "name": r["name"], "team": r.team, "market": r.market,
                        "k": None if r.market == "atd" else float(r.k), "p": float(r.p)})
    for game in card["games"]:
        g = game["game_id"]
        for b in ("floor", "aggressive"):
            for n, v in game[b]["tiers"].items():
                add(f"{g}|{b}{n}", game[b]["legs"].head(n), v["p"])
        add(f"{g}|atd_board", game["atd"]["legs"], None)
        for key in ("slip5", "slip8"):
            if game[key]["p"]:
                add(f"{g}|{key}", game[key]["legs"], game[key]["p"])
    for n, v in card["combos"]["tiers"].items():
        add(f"combo{n}", card["combos"]["legs"].head(n), v["p"])
    for n, v in card["atd_slate"]["tiers"].items():
        add(f"atd_slate{n}", card["atd_slate"]["legs"].head(n), v["p"])
    add("atd_board16", card["atd_slate"]["board"], None)
    return out


# ============================================================================================
# Algorithm SGP per game: best leg per position slot
# ============================================================================================
SGP_SLOTS = [("QB", ("pass_yds", "pass_td"), ("QB",)),
             ("RB rush", ("rush_yds",), ("RB",)),
             ("WR", ("rec", "rec_yds"), ("WR",)),
             ("TE", ("rec", "rec_yds"), ("TE",)),
             ("RB receiving", ("rec", "rec_yds"), ("RB",))]
SGP_MARKETS = {m for _, ms, _ in SGP_SLOTS for m in ms}


def algo_sgp(legs: pd.DataFrame, game_id: str, corr: dict, n_alt=2):
    """For one game: the best floor-band leg per slot (QB pass yds|pass TDs, RB rush yds, WR/TE/RB receptions|rec yds),
    distinct players, ≤2 legs per market.  A slot with nothing qualifying is skipped and refilled with the next-best leg
    from the allowed markets.  Returns (chosen legs with slot labels, alternatives per slot, joint p, independent p)."""
    pool = pick_rungs(legs[(legs.game_id == game_id) & legs.market.isin(SGP_MARKETS)], "floor")
    pool = pool.sort_values("p", ascending=False)
    used, mk_n, chosen, alts, skipped = set(), {}, [], {}, []
    for slot, mks, poss in SGP_SLOTS:
        c = pool[pool.market.isin(mks) & pool.pos_group.isin(poss) & ~pool.player_id.isin(used)]
        c = c[[mk_n.get(m, 0) < 2 for m in c.market]]
        if c.empty:
            skipped.append(slot)
            continue
        pick = c.iloc[0]
        chosen.append(pick.to_dict() | {"slot": slot})
        used.add(pick.player_id)
        mk_n[pick.market] = mk_n.get(pick.market, 0) + 1
        alts[slot] = c.iloc[1:1 + n_alt].to_dict("records")
    for slot in skipped:  # refill: next-best leg from any allowed market
        c = pool[~pool.player_id.isin(used)]
        c = c[[mk_n.get(m, 0) < 2 for m in c.market]]
        if c.empty:
            break
        pick = c.iloc[0]
        chosen.append(pick.to_dict() | {"slot": f"{pick.pos_group} (fill for {slot})"})
        used.add(pick.player_id)
        mk_n[pick.market] = mk_n.get(pick.market, 0) + 1
    C = pd.DataFrame(chosen)
    if C.empty:
        return C, alts, None, None
    return C, alts, ticket_prob(C, corr), float(C.p.prod())
