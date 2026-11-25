"""Derived tables: team and player rates, goalie GSAx, ice-time projection, schedule spots, arena bias, point-in-time."""
import numpy as np
import pandas as pd
import pytest

from nhl import ids, run_daily, store
from nhl.features import arena_bias, player_rates, schedule, team_rates, toi


# ------------------------------------------------------------------ team rates
def tgs_frame(rows):
    base = {c: 0 for c in team_rates.COUNTS}
    return pd.DataFrame([{**base, "is_home": 1, "date_et": "x", **r} for r in rows])


def test_team_rate_is_60_percent_season_40_percent_last_ten(cfg):
    cfg["rates"]["season_carry_games"] = 0
    rows = []
    for g in range(30):                                   # 20 games at 2.0 xGF/60, then 10 at 3.0
        rows.append({"game_id": g, "team": "AAA", "strength": "ev5", "season": 2026, "known_at": f"2026-11-{g + 1:02d}",
                     "toi": 3000, "xgf": (2.0 if g < 20 else 3.0) * 3000 / 3600, "xga": 2.5 * 3000 / 3600})
    r = team_rates.build(tgs_frame(rows), 2026, cfg)
    r = r[r.strength == "ev5"].iloc[0]
    season = (20 * 2.0 + 10 * 3.0) / 30
    assert r.gp == 30 and r.gp_recent == 10
    assert r.xgf60_season == pytest.approx(season) and r.xgf60_recent == pytest.approx(3.0)
    assert r.xgf60 == pytest.approx(0.6 * season + 0.4 * 3.0)
    assert r.xgf_pct == pytest.approx(r.xgf60 / (r.xgf60 + 2.5))


def test_early_season_leans_on_last_season(cfg):
    cfg["rates"]["season_carry_games"] = 20
    rows = [{"game_id": g, "team": "AAA", "strength": "ev5", "season": 2025, "known_at": f"2025-11-{g + 1:02d}", "toi": 3000,
             "xgf": 2.0 * 3000 / 3600} for g in range(20)]
    rows += [{"game_id": 100 + g, "team": "AAA", "strength": "ev5", "season": 2026, "known_at": f"2026-10-{g + 10:02d}", "toi": 3000,
              "xgf": 4.0 * 3000 / 3600} for g in range(5)]
    r = team_rates.build(tgs_frame(rows), 2026, cfg)
    r = r[r.strength == "ev5"].iloc[0]
    assert r.xgf60_season == pytest.approx((5 * 4.0 + 15 * 2.0) / 20)        # 5 games played, 15 carried
    assert r.xgf60_recent == pytest.approx(4.0)


def test_team_rates_from_the_league(league, cfg):
    r = team_rates.build(league["team_game_strength"], 2026, cfg)
    assert set(r.strength) == set(team_rates.strengths()) and r.team.nunique() == 6
    ev = r[r.strength == "ev5"]
    assert ev.xgf60_idx.mean() == pytest.approx(1.0, abs=0.05)
    allr = r[r.strength == "all"].set_index("team")
    assert (allr.toi_pg == 3600).all()
    pp = r[r.strength == "pp"].set_index("team")
    assert 0 < pp.toi_pg.mean() < 200 and (allr.pen_drawn60 > 0).any()
    assert r.as_of.isna().all() if "as_of" in r else True


# ------------------------------------------------------------------ skaters
def test_skater_rates_have_ev_pp_pk_and_shrink_small_samples(league, cfg):
    pgs = league["player_game_strength"]
    r = player_rates.build(pgs, 2026, cfg)
    assert set(r.strength) == {"ev", "pp", "pk"}
    assert set(r.group) == {"F", "D"}
    ev = r[r.strength == "ev"].set_index("player_id")
    assert ev.gp.max() == pgs[pgs.season == 2026].groupby("player_id").game_id.nunique().max()
    # a player with almost no power-play time is priced near his position's league rate, not at his raw rate
    pp = r[(r.strength == "pp") & (r.group == "F")]
    low = pp[pp.toi_min < 5]
    assert len(low) and (low.sog60 - pp.sog60.median()).abs().max() < (low.sog60_raw.fillna(0) - pp.sog60.median()).abs().max() + 1e-9
    fwd = ev[ev.group == "F"]                                # defencemen never shoot in the made-up league
    assert ((fwd.sog_per_attempt > 0.3) & (fwd.sog_per_attempt < 1)).all()
    assert (ev.finishing > 0.5).all() and (ev.finishing < 1.5).all()


def test_shrinkage_arithmetic(cfg):
    cfg["rates"]["player_weight_recent"] = 0.0
    rows = []
    for pid, sog in ((1, 6), (2, 2)):
        for s in ("ev5", "evo", "pp", "pk"):
            rows.append({"game_id": 1, "player_id": pid, "strength": s, "team": "AAA", "pos": "C", "season": 2026, "date_et": "d",
                         "known_at": "2026-11-01", "toi": 600 if s == "ev5" else 0, **{c: 0.0 for c in player_rates.STATS},
                         "sog": sog if s == "ev5" else 0})
    r = player_rates.build(pd.DataFrame(rows), 2026, cfg).set_index(["player_id", "strength"])
    league = 8 / 1200 * 3600                                # 24 shots per 60
    prior = cfg["rates"]["player_prior_toi_min"]["ev"] * 60
    want = (6 + league * prior / 3600) / (600 + prior) * 3600
    assert r.at[(1, "ev"), "sog60"] == pytest.approx(want)
    assert r.at[(1, "ev"), "sog60_raw"] == pytest.approx(36.0) and league < want < 36.0


def test_on_ice_rates_skip_games_without_a_shift_chart(cfg):
    cfg["rates"]["player_weight_recent"] = 0.0
    cfg["rates"]["player_prior_toi_min"]["ev"] = 0
    rows = []
    for g, on in ((1, 1.0), (2, None)):                      # game 2 was built from the play-by-play: no on-ice numbers
        for s in ("ev5", "evo", "pp", "pk"):
            rows.append({"game_id": g, "player_id": 1, "strength": s, "team": "AAA", "pos": "C", "season": 2026, "date_et": "d",
                         "known_at": f"2026-11-0{g}", "toi": 900 if s == "ev5" else 0, **{c: 0.0 for c in player_rates.STATS},
                         "sog": 3 if s == "ev5" else 0, **{c: (on if s == "ev5" else (0.0 if on else None)) for c in player_rates.ON_ICE}})
    r = player_rates.build(pd.DataFrame(rows), 2026, cfg).set_index("strength").loc["ev"]
    assert r.sog60 == pytest.approx(6 / 1800 * 3600)         # shots use both games
    assert r.on_xgf60 == pytest.approx(1.0 / 900 * 3600)     # on-ice xG uses only the game that has it
    assert r.toi_min == 30 and r.toi_on_ice_min == 15


# ------------------------------------------------------------------ goalies
def test_goalie_gsax_needs_a_minimum_sample(league, cfg):
    gg = league["goalie_game"]
    g = player_rates.goalies(gg, 2026, cfg)
    assert len(g) == 6 and (g.starts >= 15).all() and (g.below_min_sample == 0).all()
    assert g.gsax60.abs().max() < g.gsax60_raw.abs().max()                  # shrunk toward league average
    cfg["rates"]["goalie_min_starts"] = 500
    g = player_rates.goalies(gg, 2026, cfg)
    assert (g.below_min_sample == 1).all() and (g.gsax60 == 0).all()


def test_gsax_is_expected_minus_actual(cfg):
    cfg["rates"]["goalie_min_starts"] = 1
    row = {"game_id": 1, "player_id": 9, "team": "AAA", "season": 2026, "date_et": "d", "known_at": "k", "starter": 1, "relieved": 0,
           "toi": 3600, "sa": 30, "ga": 2, "saves": 28, "xga": 3.2, "unblocked": 40, "xg_ga": 2}
    g = player_rates.goalies(pd.DataFrame([row]), 2026, cfg).iloc[0]
    assert g.gsax == pytest.approx(1.2) and g.gsax60_raw == pytest.approx(1.2)
    assert g.gsax60 == pytest.approx(1.2 / (40 + cfg["rates"]["goalie_prior_shots"]) * 40)
    assert g.sv_pct == pytest.approx(28 / 30)


# ------------------------------------------------------------------ ice time
def test_toi_base_is_recent_shrunk_toward_season(cfg):
    rows = []
    for g in range(20):                                   # 10 games at 600s EV, then 10 at 900s
        for s, t in (("ev5", 600 if g < 10 else 900), ("evo", 0), ("pp", 60), ("pk", 0)):
            rows.append({"game_id": g, "player_id": 1, "strength": s, "team": "AAA", "pos": "C", "season": 2026, "date_et": "d",
                         "known_at": f"2026-11-{g + 1:02d}", "toi": t, **{c: 0.0 for c in player_rates.STATS}})
    b = toi.base(pd.DataFrame(rows), 2026, cfg).iloc[0]
    w = cfg["toi"]["weight_recent"]
    assert b.gp == 20 and b.n_recent == 10
    assert b.ev_base == pytest.approx(w * 900 + (1 - w) * 750) and b.pp_base == 60 and b.pk_base == 0


def test_lines_move_power_play_and_even_strength_time(league, cfg):
    pgs = league["player_game_strength"]
    plain = toi.project(pgs, 2026, cfg).set_index("player_id")
    assert (plain.ev == plain.ev_base).all() and plain.in_lineup.isna().all()
    # NYR is team 1: forwards 100-108 (lines of three), defence 109-112. Tonight the third-liner 106 moves up to the top line.
    slots = [("f1", [100, 101, 106]), ("f2", [103, 104, 105]), ("f3", [102, 107, 108]), ("d1", [109, 110]), ("d2", [111, 112]),
             ("pp1", [106, 100, 101, 103, 109]), ("pp2", [104, 105, 107, 111, 112]), ("ir", [102])]
    lines = pd.DataFrame([{"team": "NYR", "known_at": "2026-11-24T20:00:00+00:00", "source_time": "2026-11-24T18:00:00Z",
                           "player": str(p), "player_id": float(p), "unit": u, "slot": f"s{i}",
                           "category": "pp" if u.startswith("pp") else ("oi" if u == "ir" else "ev"), "injury": None, "gtd": 0}
                          for u, ps in slots for i, p in enumerate(ps)])
    out = toi.project(pgs, 2026, cfg, lines, {"NYR": 300.0}, "2026-11-24T21:00:00+00:00").set_index("player_id")
    assert out.at[106, "pp"] == pytest.approx(cfg["toi"]["pp1_share"] * 300) and out.at[106, "pp_unit"] == "pp1"
    assert out.at[104, "pp"] == pytest.approx(cfg["toi"]["pp2_share"] * 300)
    assert out.at[108, "pp"] == pytest.approx(out.at[108, "pp_base"] * cfg["toi"]["pp_off_unit_factor"], abs=0.06)
    assert out.at[102, "in_lineup"] == 0 and "injured reserve" in out.at[102, "notes"] and out.at[100, "in_lineup"] == 1
    assert out.at[106, "ev_slot"] == "f1" and out.at[109, "ev_slot"] == "d1"
    ranked = plain[(plain.team == "NYR") & (plain.group == "F")].ev_base.sort_values(ascending=False)
    usual = [ranked.iloc[i:i + 3].mean() for i in (0, 3, 6)]
    for p in (106, 100, 102 + 5):
        own = usual[list(ranked.index).index(p) // 3]
        tonight = usual[0] if p in (100, 101, 106) else usual[2]
        assert out.at[p, "ev"] == pytest.approx(plain.at[p, "ev_base"] + cfg["toi"]["line_slot_weight"] * (tonight - own), abs=0.06)
    same = [p for p in (100, 101) if list(ranked.index).index(p) < 3]
    assert all(out.at[p, "ev"] == out.at[p, "ev_base"] for p in same)       # on his usual line: nothing moves
    # an established power-play man keeps half of what he has above the unit's share
    star = toi.project(pgs, 2026, cfg, lines, {"NYR": 1.0}, "2026-11-24T21:00:00+00:00").set_index("player_id")
    t = cfg["toi"]["pp1_share"] * 1.0
    assert star.at[100, "pp"] == pytest.approx(t + cfg["toi"]["pp_surplus_kept"] * (star.at[100, "pp_base"] - t), abs=0.06)
    assert out.at[106, "total"] == pytest.approx(out.at[106, "ev"] + out.at[106, "pp"] + out.at[106, "pk"])
    assert out[out.team == "BOS"].in_lineup.isna().all()                    # no lines for Boston: nothing is assumed
    stale = toi.project(pgs, 2026, cfg, lines, {"NYR": 300.0}, "2026-11-27T21:00:00+00:00").set_index("player_id")
    assert (stale.pp == stale.pp_base).all()                                # three-day-old lines are not used


# ------------------------------------------------------------------ schedule
def test_schedule_spots_rest_travel_and_time_zones(cfg):
    g = lambda i, d, h, a, off: {"game_id": i, "season": 2026, "date_et": d, "start_utc": d + "T23:00:00Z", "home": h, "away": a,
                                 "venue_utc_offset": off, "neutral": 0}
    s = pd.DataFrame([g(1, "2026-11-01", "NJD", "NYR", -5.0), g(2, "2026-11-02", "NYR", "BOS", -5.0), g(3, "2026-11-04", "LAK", "NYR", -8.0),
                      g(4, "2026-11-05", "VAN", "NYR", -8.0)])
    out = schedule.build(s, ids.TEAMS, cfg).set_index(["game_id", "team"])
    assert pd.isna(out.at[(1, "NYR"), "rest_days"]) and 5 < out.at[(1, "NYR"), "travel_km"] < 30      # Manhattan to Newark
    assert out.at[(2, "NYR"), "b2b"] == 1 and out.at[(2, "NYR"), "rest_days"] == 1 and out.at[(2, "BOS"), "b2b"] == 0
    assert pd.isna(out.at[(2, "NYR"), "rest_diff"])                           # Boston's first game: no rest number to compare
    assert 3900 < out.at[(3, "NYR"), "travel_km"] < 4000 and out.at[(3, "NYR"), "tz_shift"] == -3.0
    assert out.at[(3, "NYR"), "three_in_four"] == 1 and out.at[(3, "NYR"), "b2b"] == 0
    assert out.at[(4, "NYR"), "b2b"] == 1 and out.at[(4, "NYR"), "games_last_7"] == 3 and out.at[(4, "NYR"), "tz_shift"] == 0
    assert out.at[(4, "NYR"), "km_last_7"] == pytest.approx(sum(out.at[(i, "NYR"), "travel_km"] for i in (1, 2, 3, 4)), abs=0.3)
    assert out.at[(4, "VAN"), "travel_km"] == 0 and out.at[(4, "VAN"), "opp_b2b"] == 1


# ------------------------------------------------------------------ arena bias
def test_arena_bias_finds_the_loud_rink_shrinks_and_caps(league, cfg):
    b = arena_bias.build(league["team_game"], league["games"], [], cfg)
    hits = b[b.stat == "hits"].set_index("team")
    assert hits.factor.idxmax() == "VAN" and hits.at["VAN", "raw"] > 1.3
    assert 1 < hits.at["VAN", "factor"] < hits.at["VAN", "raw"]                # shrunk toward 1.00
    assert hits.at["VAN", "factor"] <= 1 + cfg["arena_bias"]["cap"]
    others = hits.drop("VAN")
    assert (others.factor - 1).abs().max() < 0.08
    assert (b[b.stat == "sog"].factor - 1).abs().max() < 0.08                  # nobody inflates shots in this league
    cfg["arena_bias"]["prior_games"] = 0
    raw = arena_bias.build(league["team_game"], league["games"], [], cfg)
    assert raw[(raw.stat == "hits") & (raw.team == "VAN")].factor.iloc[0] == 1 + cfg["arena_bias"]["cap"]


def test_arena_bias_ignores_neutral_site_games(league, cfg):
    van_home = league["games"][league["games"].home == "VAN"].game_id
    b = arena_bias.build(league["team_game"], league["games"], van_home, cfg)
    assert "VAN" not in set(b.team)


# ------------------------------------------------------------------ point in time, end to end
def test_before_hides_the_game_being_priced_and_everything_after(db, league):
    g = league["games"].sort_values("known_at").iloc[25]
    seen = store.before(db, "games", g.start_utc.replace("Z", "+00:00"))
    assert g.game_id not in set(seen.game_id) and len(seen) and (seen.known_at < g.start_utc.replace("Z", "+00:00")).all()
    assert len(store.before(db, "player_game_strength", "2000-01-01")) == 0


def test_derive_writes_every_table_and_respects_as_of(db, cfg, league):
    out = run_daily.derive(db, cfg, "2026-12-31T00:00:00+00:00")
    assert set(out) == {"team_rates", "player_rates", "goalie_rates", "schedule_spots", "arena_bias", "ref_rates", "toi_projection"}
    for name in out:
        assert db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] == len(out[name]) > 0
    full = out["team_rates"].set_index(["team", "strength"])
    cut = league["games"][league["games"].season == 2026].sort_values("known_at").iloc[12].known_at
    early = run_daily.derive(db, cfg, cut)["team_rates"].set_index(["team", "strength"])
    assert early.gp.max() < full.gp.max()
    assert db.execute("SELECT DISTINCT as_of FROM team_rates").fetchall() == [(cut,)]
    assert len(out["ref_rates"]) == 4 and np.isfinite(out["ref_rates"].factor).all()
