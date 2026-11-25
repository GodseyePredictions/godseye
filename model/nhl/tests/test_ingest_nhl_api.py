"""NHL API parsers, on trimmed copies of real responses for NJD 3, CBJ 2 on 23 November 2026."""
from nhl.ingest import nhl_api
from nhl.tests.conftest import fixture_json


def test_schedule_week_rows():
    rows = nhl_api.parse_schedule_week(fixture_json("schedule_week.json"))
    assert len(rows) == 2
    g = rows[0]
    assert (g["game_id"], g["season"], g["home"], g["away"], g["date_et"]) == (2026020378, 2026, "NJD", "CBJ", "2026-11-23")
    assert g["venue_utc_offset"] == -5.0 and g["neutral"] == 0 and g["state"] == "OFF"


def test_schedule_skips_other_game_types():
    assert nhl_api.parse_schedule_week(fixture_json("schedule_week.json"), game_types=(3,)) == []


def test_pbp_score_length_and_shot_counts():
    g = nhl_api.parse_pbp(fixture_json("pbp.json"))
    assert (g["home"], g["away"], g["home_goals"], g["away_goals"], g["decided"], g["seconds"]) == ("NJD", "CBJ", 3, 2, "REG", 3600)
    on_net = [e for e in g["events"] if e["type"] in ("shot-on-goal", "goal")]
    assert sum(e["team"] == "NJD" for e in on_net) == 30 and sum(e["team"] == "CBJ" for e in on_net) == 21
    assert sum(e["type"] == "goal" for e in g["events"]) == 5


def test_pbp_blocked_shot_belongs_to_the_shooter():
    g = nhl_api.parse_pbp(fixture_json("pbp.json"))
    blocks = [e for e in g["events"] if e["type"] == "blocked-shot" and e.get("blocker")]
    assert len(blocks) == 31 and all(g["roster"][e["shooter"]]["team"] == e["team"] for e in blocks)
    # the feed also lists shots that hit a team-mate; only an opponent's block is credited (29 = 15 + 14 in the box score)
    assert sum(g["roster"][e["blocker"]]["team"] != e["team"] for e in blocks) == 29


def test_pbp_drops_shootout_attempts():
    doc = fixture_json("pbp.json")
    doc["plays"].append({"periodDescriptor": {"number": 5, "periodType": "SO"}, "timeInPeriod": "00:00", "typeDescKey": "goal",
                         "details": {"eventOwnerTeamId": 1, "scoringPlayerId": 8478414}})
    g = nhl_api.parse_pbp(doc)
    assert g["decided"] == "SO" and g["seconds"] == 3600 and sum(e["type"] == "goal" for e in g["events"]) == 5


def test_shifts_are_game_seconds_and_skip_goal_rows():
    doc = fixture_json("shifts.json")
    rows = nhl_api.parse_shifts(doc, 3600)
    assert len(rows) == sum(r["typeCode"] == 517 for r in doc["data"])
    assert all(0 <= a < b <= 3600 for _, a, b in rows)
    assert max(b for _, _, b in rows) == 3600


def test_rail_officials_and_scratches():
    g = nhl_api.parse_pbp(fixture_json("pbp.json"))
    offs, scr = nhl_api.parse_rail(fixture_json("rail.json"), g)
    assert sorted(o["name"] for o in offs if o["role"] == "referee") == ["Francis Charron", "Pierre Lambert"]
    assert sum(o["role"] == "linesperson" for o in offs) == 2
    assert {s["team"] for s in scr} == {"NJD", "CBJ"} and len(scr) == 5
    assert nhl_api.parse_rail({}, g) == ([], [])


def test_rail_accepts_the_older_name_shape():
    g = nhl_api.parse_pbp(fixture_json("pbp.json"))
    offs, _ = nhl_api.parse_rail({"gameInfo": {"referees": [{"default": "Old Shape"}]}}, g)
    assert offs == [{"game_id": 2026020378, "name": "Old Shape", "role": "referee"}]


def test_league_toi_and_roster():
    toi = nhl_api.parse_toi(fixture_json("toi.json"))
    assert toi and all(r["ev"] + r["pp"] + r["sh"] == r["total"] for r in toi)
    r = nhl_api.parse_roster(fixture_json("roster.json"), "NJD")
    assert len(r) == 8 and {x["pos"] for x in r} >= {"G", "D"} and all(x["team"] == "NJD" for x in r)


def test_recent_games_are_re_read_and_old_ones_are_not(cfg):
    from datetime import date
    assert nhl_api.game_max_age("2026-11-23", cfg, today=date(2026, 11, 24)) == cfg["sources"]["recent_game_max_age_sec"]
    assert nhl_api.game_max_age("2026-11-01", cfg, today=date(2026, 11, 24)) is None
