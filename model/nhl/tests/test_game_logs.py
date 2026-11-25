"""The per-game builder: strength states from shift charts, counts by strength, on-ice xG, goalies, score state."""
from datetime import date

import numpy as np
import pandas as pd

from nhl.features import game_logs
from nhl.ingest import nhl_api
from nhl.tests.conftest import fixture_json, make_game

K = game_logs.K


def real_game(cfg, with_shifts=True):
    g = nhl_api.parse_pbp(fixture_json("pbp.json"))
    shifts = nhl_api.parse_shifts(fixture_json("shifts.json"), g["seconds"]) if with_shifts else []
    official = {r["player_id"]: (r["ev"], r["pp"], r["sh"]) for r in nhl_api.parse_toi(fixture_json("toi.json"))}
    return g, shifts, official


def test_ice_time_by_strength_matches_the_leagues_own(cfg):
    g, shifts, official = real_game(cfg)
    out = game_logs.build_game(g, shifts, None, official, cfg)
    p = pd.DataFrame(out["player_game_strength"]).pivot_table(index="player_id", columns="strength", values="toi", aggfunc="sum")
    assert len(official) >= 10
    for pid, (ev, pp, sh) in official.items():
        assert (p.at[pid, "ev5"] + p.at[pid, "evo"], p.at[pid, "pp"], p.at[pid, "pk"]) == (ev, pp, sh)


def test_team_totals_match_the_box_score(cfg):
    g, shifts, official = real_game(cfg)
    out = game_logs.build_game(g, shifts, None, official, cfg)
    assert out["games"][0]["toi_source"] == "shifts"
    t = pd.DataFrame(out["team_game_strength"])
    by = t.groupby("team")[["toi", "gf", "sog_f"]].sum()
    assert by.loc["NJD"].tolist() == [3600, 3, 30] and by.loc["CBJ"].tolist() == [3600, 2, 21]
    njd, cbj = t[t.team == "NJD"].set_index("strength"), t[t.team == "CBJ"].set_index("strength")
    assert njd.at["pp", "toi"] == cbj.at["pk", "toi"] and njd.at["pk", "toi"] == cbj.at["pp", "toi"]
    for a, b in (("cf", "ca"), ("hits_f", "hits_a"), ("blk_f", "blk_a"), ("pen_taken", "pen_drawn")):
        assert njd[a].sum() == cbj[b].sum() and cbj[a].sum() == njd[b].sum()
    tg = pd.DataFrame(out["team_game"]).set_index("team")
    assert tg.at["CBJ", "en_sec"] > 0 and tg.at["NJD", "en_sec"] == 0          # Columbus pulled its goalie late
    assert tg.at["NJD", "won"] == 1 and tg.at["CBJ", "pim"] == 6


def test_goalies_starter_and_saves(cfg):
    g, shifts, official = real_game(cfg)
    gg = pd.DataFrame(game_logs.build_game(g, shifts, None, official, cfg)["goalie_game"]).set_index("team")
    assert gg.at["NJD", "starter"] == 1 and gg.at["NJD", "toi"] == 3600 and gg.at["NJD", "saves"] == 19
    assert gg.at["CBJ", "saves"] == 27 and gg.at["CBJ", "toi"] < 3600 and gg.at["CBJ", "relieved"] == 0


def test_without_a_shift_chart_the_leagues_ice_time_is_used(cfg):
    g, _, official = real_game(cfg, with_shifts=False)
    out = game_logs.build_game(g, [], None, official, cfg)
    assert out["games"][0]["toi_source"] == "pbp"
    p = pd.DataFrame(out["player_game_strength"])
    assert set(p.player_id) == set(official)
    assert p.on_xgf.isna().all()                                                # on-ice numbers are left empty, not guessed
    t = pd.DataFrame(out["team_game_strength"]).groupby("team")[["toi", "sog_f"]].sum()
    assert t.loc["NJD"].tolist() == [3600, 30]
    assert pd.DataFrame(out["goalie_game"]).starter.sum() == 2


def test_situation_code_fallback_tracks_the_shift_chart(cfg):
    g, shifts, _ = real_game(cfg)
    a, b = game_logs.timeline_from_shifts(g, shifts, cfg), game_logs.timeline_from_codes(g)
    assert np.mean(a["state"][1] == b["state"][1]) > 0.95        # the saved game is trimmed to shots, hits and penalties
    for k in ("pp", "pk"):
        assert abs(int((a["state"][1] == K[k]).sum()) - int((b["state"][1] == K[k]).sum())) <= 60


def test_an_unexplained_code_change_is_split_down_the_middle():
    ev = lambda sec, code, kind="hit": {"sec": sec, "type": kind, "code": code, "team": "H"}
    g = {"seconds": 1200, "events": [ev(100, "1551", "penalty"), ev(120, "1451"), ev(200, "1451"), ev(260, "1551"), ev(1200, "1551")]}
    st = game_logs.timeline_from_codes(g)["state"][1]
    assert (st[:100] == K["ev5"]).all() and (st[100:230] == K["pp"]).all() and (st[230:] == K["ev5"]).all()


def test_a_broken_shift_chart_is_not_trusted(cfg):
    g, shifts, _ = real_game(cfg)
    assert game_logs.timeline_from_shifts(g, shifts[: len(shifts) // 3], cfg) is None


def test_short_power_play_runs_are_line_change_noise():
    s = np.array([K["ev5"]] * 5 + [K["pp"]] * 2 + [K["ev5"]] * 5 + [K["pk"]] * 6 + [K["ev5"]], dtype=np.int8)
    out = game_logs._merge_short_runs(s, 4)
    assert (out[5:7] == K["ev5"]).all() and (out[12:18] == K["pk"]).all()


def test_made_up_game_with_one_power_play(cfg):
    rng = np.random.default_rng(4)
    game, shifts, shots = make_game(1, date(2026, 11, 1), "NYR", "BOS", rng)
    out = game_logs.build_game(game, shifts, shots, {}, cfg)
    t = pd.DataFrame(out["team_game_strength"]).set_index(["team", "strength"])
    assert t.at[("NYR", "pp"), "toi"] == 120 and t.at[("BOS", "pk"), "toi"] == 120
    assert t.at[("NYR", "ev5"), "toi"] == 3480 and t.at[("BOS", "pp"), "toi"] == 0
    assert t.at[("BOS", "ev5"), "pen_taken"] == 1 and t.at[("NYR", "ev5"), "pen_drawn"] == 1
    assert abs(t.xgf.sum() - shots.xg.sum()) < 1e-6
    assert abs(t.loc["NYR"].xgf.sum() - t.loc["BOS"].xga.sum()) < 1e-6
    p = pd.DataFrame(out["player_game_strength"])
    assert abs(p.ixg.sum() - shots.xg.sum()) < 1e-6
    # five skaters are on the ice for every shot at 5v5, so on-ice xG for is five times the team's
    ev = p[(p.team == "NYR") & (p.strength == "ev5")]
    assert abs(ev.on_xgf.sum() - 5 * t.at[("NYR", "ev5"), "xgf"]) < 1e-6
    # the penalised forward sat out the two minutes
    sat = p[(p.player_id == 302)].toi.sum()
    assert sat == p[(p.player_id == 301)].toi.sum() - 40
    g = pd.DataFrame(out["goalie_game"]).set_index("team")
    assert g.at["BOS", "unblocked"] == int((shots.is_home == 1).sum())
    assert abs(g.at["BOS", "xga"] - shots[shots.is_home == 1].xg.sum()) < 1e-6


def test_score_state_table_covers_the_whole_game(cfg):
    rng = np.random.default_rng(5)
    game, shifts, shots = make_game(2, date(2026, 11, 3), "MTL", "LAK", rng)
    out = game_logs.build_game(game, shifts, shots, {}, cfg)
    s = pd.DataFrame(out["team_game_score"])
    a = s[s.scope == "all"].groupby("team").toi.sum()
    assert a["MTL"] == 3600 and a["LAK"] == 3600
    m, l = s[(s.team == "MTL") & (s.scope == "all")].set_index("lead"), s[(s.team == "LAK") & (s.scope == "all")].set_index("lead")
    for b in range(-2, 3):
        assert m.at[b, "toi"] == l.at[-b, "toi"] and m.at[b, "cf"] == l.at[-b, "ca"]
    assert s[s.scope == "ev5"].toi.sum() <= s[s.scope == "all"].toi.sum()


def test_results_are_known_only_after_the_game(cfg):
    rng = np.random.default_rng(6)
    game, shifts, shots = make_game(3, date(2026, 11, 5), "VAN", "NJD", rng)
    out = game_logs.build_game(game, shifts, shots, {}, cfg)
    assert out["games"][0]["known_at"] == "2026-11-06T03:00:00+00:00"
    assert {r["known_at"] for r in out["player_game_strength"]} == {"2026-11-06T03:00:00+00:00"}
