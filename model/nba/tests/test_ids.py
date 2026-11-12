import pandas as pd

from nba.ids import IdMap, norm


def slate(tmp_path):
    names = [("101", "Nikola Jokić", "7"), ("102", "Jaren Jackson Jr.", "29"), ("103", "Shai Gilgeous-Alexander", "25"),
             ("104", "De'Aaron Fox", "24"), ("105", "Jalen Williams", "25"), ("106", "Jaylin Williams", "25"),
             ("107", "Marcus Morris Sr.", "20"), ("108", "Jalen Brunson", "18"), ("109", "Tim Hardaway Jr.", "7"),
             ("110", "Bogdan Bogdanović", "12"), ("111", "Jalen Johnson", "1"), ("112", "Jalen Johnson", "24")]
    pg = pd.DataFrame(names, columns=["player_id", "name", "team_id"])
    sched = pd.DataFrame([{"game_id": "g1", "date_et": "2026-11-11", "home_id": "7", "away_id": "25", "home": "DEN", "away": "OKC"},
                          {"game_id": "g2", "date_et": "2026-11-11", "home_id": "18", "away_id": "24", "home": "NY", "away": "SA"},
                          {"game_id": "g3", "date_et": "2026-11-11", "home_id": "29", "away_id": "20", "home": "MEM", "away": "PHI"},
                          {"game_id": "g4", "date_et": "2026-11-11", "home_id": "12", "away_id": "1", "home": "LAC", "away": "ATL"}])
    return IdMap(pg, sched, tmp_path / "review.csv")


def test_full_slate_matches_across_sources(tmp_path):
    m = slate(tmp_path)
    odds_names = {"Nikola Jokic": "101", "Jaren Jackson": "102", "Shai Gilgeous Alexander": "103", "DeAaron Fox": "104",
                  "Jalen Williams": "105", "Jaylin Williams": "106", "Marcus Morris": "107", "JALEN BRUNSON": "108",
                  "Tim Hardaway Jr": "109", "Bogdan Bogdanovic": "110"}
    for name, pid in odds_names.items():
        assert m.player(name, source="odds") == pid, name
    assert m.game("Denver Nuggets", "Oklahoma City Thunder", "2026-11-11") == "g1"
    assert m.game("New York Knicks", "San Antonio Spurs", "2026-11-11") == "g2"
    assert m.game("LA Clippers", "Atlanta Hawks", "2026-11-11") == "g4"
    assert m.game("Los Angeles Clippers", "Atlanta Hawks", "2026-11-11") == "g4"
    assert m.team("NYK") == "18" and m.team("Knicks") == "18"
    assert m.unmatched == []


def test_never_guesses(tmp_path):
    m = slate(tmp_path)
    assert m.player("J. Brunson") is None                 # initials are not an exact match
    assert m.player("Jalen Brunsen") is None              # a misspelling is not an exact match
    assert m.player("Jalen Johnson") is None              # two players share the name: no team, no match
    assert m.player("Jalen Johnson", ["1"]) == "111"      # the team settles it
    assert m.player("Jalen Johnson", ["24"]) == "112"
    assert m.game("Denver Nuggets", "Miami Heat", "2026-11-11") is None
    n = m.write_review()
    rows = pd.read_csv(tmp_path / "review.csv")
    assert n == len(rows) >= 4 and set(rows.kind) >= {"player"}
    assert m.write_review() == 0                          # the same names are not written twice


def test_norm():
    assert norm("Nikola Jokić") == "nikola jokic" and norm("Jaren Jackson Jr.") == "jaren jackson"
    assert norm("De'Aaron Fox") == "deaaron fox" and norm("Shai Gilgeous-Alexander") == "shai gilgeous alexander"
