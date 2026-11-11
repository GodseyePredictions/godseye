from datetime import datetime, timezone

import pandas as pd

from common import http
from nba import espn, injuries, schedule
from nba.config import CONFIG

REPORT = """                                         Injury Report: 11/11/26 12:00 PM

Game Date    Game Time    Matchup   Team                        Player Name             Current Status   Reason

11/11/2026   07:00 (ET)   BOS@TOR   Boston Celtics                                                       NOT YET SUBMITTED

                                    Toronto Raptors             Barnes, Scottie         Out              Injury/Illness - Left Groin Strain

                                                                                                         Injury/Illness - Right Avulsion
                                                                Bittle, Nate            Out
                                                                                                         Fracture

                                                                Jackson-Davis, Trayce   Questionable     Injury/Illness - Illness
                          CLE@NYK   Cleveland Cavaliers         Nance Jr., Larry        Probable         Rest
"""


def test_injury_report_parser():
    rows = injuries.parse_report(REPORT, datetime(2026, 11, 11, 12, 0, tzinfo=injuries.ET))
    by = {r["player_name"]: r for r in rows if r["player_name"]}
    assert set(by) == {"Scottie Barnes", "Nate Bittle", "Trayce Jackson-Davis", "Larry Nance Jr."}
    assert by["Scottie Barnes"]["team"] == "Toronto Raptors" and by["Scottie Barnes"]["status"] == "Out"
    assert by["Nate Bittle"]["reason"] == "Injury/Illness - Right Avulsion Fracture"       # wrapped cell is rejoined
    assert by["Larry Nance Jr."]["team"] == "Cleveland Cavaliers" and by["Larry Nance Jr."]["matchup"] == "CLE@NYK"
    assert rows[0]["status"] == "NOT YET SUBMITTED" and rows[0]["team"] == "Boston Celtics"
    assert rows[0]["report_utc"] == "2026-11-11T17:00:00+00:00" and by["Scottie Barnes"]["game_date"] == "2026-11-11"


def test_report_file_names_follow_the_two_formats():
    assert injuries.report_url(datetime(2025, 1, 15, 17, 0, tzinfo=injuries.ET)).endswith("Injury-Report_2025-01-15_05PM.pdf")
    assert injuries.report_url(datetime(2026, 11, 11, 17, 45, tzinfo=injuries.ET)).endswith("Injury-Report_2026-11-11_05_45PM.pdf")
    t = injuries.report_time_before(datetime(2026, 11, 11, 23, 44, tzinfo=timezone.utc))
    assert (t.hour, t.minute) == (18, 30)
    t = injuries.report_time_before(datetime(2025, 1, 15, 23, 44, tzinfo=timezone.utc))
    assert (t.hour, t.minute) == (18, 0)


def test_schedule_features():
    s = pd.DataFrame([
        {"game_id": "1", "season": 2027, "date_et": "2026-11-01", "tip_utc": "2026-11-02T00:00:00+00:00", "home_id": "b", "away_id": "l", "home": "BOS", "away": "LAL", "neutral": 0},
        {"game_id": "2", "season": 2027, "date_et": "2026-11-02", "tip_utc": "2026-11-03T00:00:00+00:00", "home_id": "n", "away_id": "l", "home": "NY", "away": "LAL", "neutral": 0},
        {"game_id": "3", "season": 2027, "date_et": "2026-11-04", "tip_utc": "2026-11-05T00:00:00+00:00", "home_id": "l", "away_id": "b", "home": "LAL", "away": "BOS", "neutral": 0}])
    f = schedule.team_schedule_features(s).set_index(["game_id", "team_id"])
    assert f.loc[("2", "l"), "b2b"] == 1 and f.loc[("2", "l"), "rest_days"] == 0
    assert 150 < f.loc[("2", "l"), "travel_miles"] < 250                 # Boston to New York
    assert f.loc[("3", "l"), "three_in_four"] == 1 and f.loc[("3", "l"), "tz_change"] == -3
    assert 2300 < f.loc[("3", "l"), "travel_miles"] < 2600 and f.loc[("3", "b"), "b2b"] == 0
    assert f.loc[("1", "b"), "travel_miles"] == 0


def _play(per, clock, kind, ids, text="", **kw):
    return {"period": {"number": per}, "clock": {"displayValue": clock}, "type": {"text": kind}, "text": text,
            "participants": [{"athlete": {"id": i}} for i in ids], **kw}


def test_seconds_by_period_from_substitutions():
    team = {str(i): "A" for i in range(1, 7)}
    plays = [_play(1, "11:30", "Jump Shot", ["1"]), _play(1, "11:00", "Rebound", ["2"]), _play(1, "10:00", "Jump Shot", ["3"]),
             _play(1, "9:00", "Foul", ["4"]), _play(1, "6:00", "Substitution", ["6", "5"]), _play(1, "0:00", "End Period", [])]
    sec = espn.period_seconds(plays, team, {str(i): 720 for i in range(1, 6)} | {"6": 360})
    assert sec["5"][1] == 360 and sec["6"][1] == 360 and sec["1"][1] == 720
    assert sum(v.get(1, 0) for v in sec.values()) == 5 * 720


def test_shot_zones():
    assert espn.zone(25, 2, False, CONFIG) == "rim" and espn.zone(25, 15, False, CONFIG) == "mid"
    assert espn.zone(2, 3, True, CONFIG) == "c3" and espn.zone(25, 26, True, CONFIG) == "ab3"
    assert espn.zone(-214748, 5, False, CONFIG) is None


def test_http_cache_resumes_without_asking_again(tmp_path):
    calls = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"ok": 1}'

    def opener(req, timeout=0):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise TimeoutError("first try fails")
        return Resp()

    body, at = http.get("https://example.test/a?k=SECRET", tmp_path, min_interval=0, opener=opener, redact="SECRET")
    again, at2 = http.get("https://example.test/a?k=SECRET", tmp_path, min_interval=0, opener=opener, redact="SECRET")
    assert body == again == b'{"ok": 1}' and at == at2 and len(calls) == 2          # one retry, then served from disk
    assert "SECRET" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


def test_draftkings_rungs_must_fit_the_over_under_line():
    from nba.sources import choose_ladder
    other = [(2, -125), (3, 250), (4, 600)]                                # a different market mixed in under the same name
    game = [(4, -1500), (5, -800), (6, -300), (7, -120), (8, 150), (10, 400), (12, 900)]
    got, why = choose_ladder(other + game, 6.5)
    assert why == "" and [r for r, _ in got] == [4, 5, 6, 7, 8, 10, 12] and dict(got)[4] == -1500
    assert choose_ladder(other, 6.5)[0] == []                               # the wrong market on its own: nothing survives
    assert choose_ladder(game, None)[0] == [] and "no over/under line" in choose_ladder(game, None)[1]
    shuffled = [(10, -1700), (15, -391), (20, -130), (25, 204), (21, -106), (40, 2700)]
    assert [r for r, _ in choose_ladder(shuffled, 20.5)[0]] == [10, 15, 20, 21, 25, 40]
    odd = [(5, -800), (6, -900), (7, -120), (8, 150)]                       # 5+ priced shorter than 6+: dropped
    assert [r for r, _ in choose_ladder(odd, 6.5)[0]] == [6, 7, 8]
