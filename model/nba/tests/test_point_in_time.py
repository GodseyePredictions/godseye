"""No feature for a game may carry anything from that game or later."""
import numpy as np
import pandas as pd

from nba import game_sim as gs
from nba import prep
from nba.store import PointInTime
from nba.tests.conftest import make_league

RESULT_COLS = {"min", "pts", "reb", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
               "rim_a", "rim_m", "mid_a", "mid_m", "c3_a", "c3_m", "ab3_a", "ab3_m", "q4_fga", "q4_pts", "sec_q4", "starter", "dnp",
               "played", "margin", "q4_entry", "poss", "reg_min", "periods", "known", "team_pts", "opp_pts", "max_lead_2h",
               "max_deficit_2h", "close_last5", "total", "max_lead", "max_deficit"}


def corrupt_from(frames, tip):
    """Rewrite every result from `tip` onward: the target game itself and everything after it."""
    f = {k: v.copy() for k, v in frames.items()}
    g = f["games"]
    late = g.tip_utc >= tip
    for c in ("home_pts", "away_pts", "hq1", "hq2", "hq3", "hq4", "aq1", "aq2", "aq3", "aq4", "max_lead_2h_home", "max_lead_2h_away"):
        g.loc[late, c] = g.loc[late, c] * 3 + 7
    ids = set(g[late].game_id)
    pg = f["player_games"]
    m = pg.game_id.isin(ids)
    num = [c for c in pg.columns if pd.api.types.is_numeric_dtype(pg[c]) and c not in ("starter", "dnp")]
    pg.loc[m, num] = pg.loc[m, num] * 3 + 5
    pg.loc[m, "starter"] = 1 - pg.loc[m, "starter"]
    return f


def test_features_for_a_past_game_ignore_that_game_and_later():
    frames = make_league(seed=3)
    g = frames["games"].sort_values("tip_utc")
    target = g.iloc[len(g) * 2 // 3]
    clean = prep.master(frames)
    dirty = prep.master(corrupt_from(frames, target.tip_utc))
    for key in ("players", "teams"):
        a = clean[key][clean[key].game_id == target.game_id].sort_values(["team_id"] + (["player_id"] if key == "players" else []))
        b = dirty[key][dirty[key].game_id == target.game_id].sort_values(["team_id"] + (["player_id"] if key == "players" else []))
        # a row's own result columns (the box score of the target game, for and against) are outcomes, not features
        cols = [c for c in a.columns if c not in RESULT_COLS and not (c.startswith("o_") and c[2:] in RESULT_COLS)
                and pd.api.types.is_numeric_dtype(a[c])]
        assert len(a) and len(cols) > 50
        diff = [c for c in cols if not np.allclose(a[c].to_numpy(float), b[c].to_numpy(float), equal_nan=True)]
        assert diff == [], f"{key}: these pre-game fields changed when the future changed: {diff}"


def test_game_script_inputs_ignore_the_future():
    frames = make_league(seed=4)
    g = frames["games"].sort_values("tip_utc")
    target = g.iloc[len(g) * 2 // 3]
    out = []
    for f in (frames, corrupt_from(frames, target.tip_utc)):
        M = prep.master(f)
        G = gs.game_table(M["players"], M["teams"], M["league"], f["officials"])
        out.append(G[G.game_id == target.game_id].iloc[0])
    for c in gs.MARGIN_X + gs.TOTAL_X + ["r_ppp_h", "r_ppp_a", "r_pace"]:
        assert np.isclose(out[0][c], out[1][c], equal_nan=True), c


def test_first_game_of_a_player_has_no_history():
    M = prep.master(make_league(seed=5))
    P = M["players"]
    first = P.sort_values("tip").groupby("player_id").head(1)
    assert (first.s_n == 0).all() and (first.prev_n == 0).all() and first.l5_n.isna().all()


def test_point_in_time_view_hides_rows_known_at_or_after_the_moment():
    df = pd.DataFrame({"game_id": ["a", "b", "c"], "known_at": ["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00",
                                                                "2026-01-03T00:00:00+00:00"]})
    v = PointInTime("2026-01-02T00:00:00+00:00", frames={"games": df}).table("games")
    assert list(v.game_id) == ["a"]


def test_injury_report_posted_after_the_cutoff_is_not_used():
    frames = make_league(seed=6)
    g = frames["games"].sort_values("tip_utc").iloc[40]
    pid = frames["player_games"][frames["player_games"].game_id == g.game_id].player_id.iloc[0]
    from nba.ids import TEAMS
    late = pd.Timestamp(g.tip_utc) + pd.Timedelta(minutes=5)
    frames["injury_reports"] = pd.DataFrame([{"report_utc": late.isoformat(), "game_date": g.date_et, "matchup": "X@Y",
                                              "team": TEAMS[g.home][0], "player_name": "x", "status": "Out", "reason": None, "player_id": pid}])
    M = prep.master(frames)
    assert g.game_id not in M["out"]
