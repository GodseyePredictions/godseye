"""One ID map for players, teams and games across sources.

ESPN ids are the canonical ids (the stats tables use them). Other sources (the official injury
report, NBA/pbpstats ids, the odds feed, a pasted bet365 sheet) are matched to them by exact
normalised name only. Anything that does not match exactly and uniquely goes to the review file
and stays unmatched: a guess here would put the wrong player on a ticket.
"""
import csv
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
REVIEW = HERE / "data" / "id_review.csv"
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")

# ESPN abbreviation -> (full name, nickname, NBA tricode used by the injury report and pbpstats)
TEAMS = {
    "ATL": ("Atlanta Hawks", "ATL"), "BOS": ("Boston Celtics", "BOS"), "BKN": ("Brooklyn Nets", "BKN"),
    "CHA": ("Charlotte Hornets", "CHA"), "CHI": ("Chicago Bulls", "CHI"), "CLE": ("Cleveland Cavaliers", "CLE"),
    "DAL": ("Dallas Mavericks", "DAL"), "DEN": ("Denver Nuggets", "DEN"), "DET": ("Detroit Pistons", "DET"),
    "GS": ("Golden State Warriors", "GSW"), "HOU": ("Houston Rockets", "HOU"), "IND": ("Indiana Pacers", "IND"),
    "LAC": ("LA Clippers", "LAC"), "LAL": ("Los Angeles Lakers", "LAL"), "MEM": ("Memphis Grizzlies", "MEM"),
    "MIA": ("Miami Heat", "MIA"), "MIL": ("Milwaukee Bucks", "MIL"), "MIN": ("Minnesota Timberwolves", "MIN"),
    "NO": ("New Orleans Pelicans", "NOP"), "NY": ("New York Knicks", "NYK"), "OKC": ("Oklahoma City Thunder", "OKC"),
    "ORL": ("Orlando Magic", "ORL"), "PHI": ("Philadelphia 76ers", "PHI"), "PHX": ("Phoenix Suns", "PHX"),
    "POR": ("Portland Trail Blazers", "POR"), "SAC": ("Sacramento Kings", "SAC"), "SA": ("San Antonio Spurs", "SAS"),
    "TOR": ("Toronto Raptors", "TOR"), "UTAH": ("Utah Jazz", "UTA"), "WSH": ("Washington Wizards", "WAS"),
}
TEAM_ALIASES = {"los angeles clippers": "LAC", "la lakers": "LAL"}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.'`]", "", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return " ".join(SUFFIX.sub(" ", s).split())


class IdMap:
    def __init__(self, player_games: pd.DataFrame, schedule: pd.DataFrame, review_path: Path = REVIEW):
        """player_games needs player_id, name, team_id (most recent row per player wins for 'current team');
        schedule needs game_id, date_et, home_id, away_id, home, away."""
        self.review_path = review_path
        self.abbr_to_id, self.team_by_name = {}, {}
        for r in schedule.itertuples():
            self.abbr_to_id[r.home] = r.home_id
            self.abbr_to_id[r.away] = r.away_id
        for ab, (full, tri) in TEAMS.items():
            tid = self.abbr_to_id.get(ab)
            if tid is None:
                continue
            for key in (full, ab, tri, full.split()[-1]):
                self.team_by_name[norm(key)] = tid
        for alias, ab in TEAM_ALIASES.items():
            if ab in self.abbr_to_id:
                self.team_by_name[alias] = self.abbr_to_id[ab]
        pg = player_games.dropna(subset=["name"])
        self.names = pg.drop_duplicates("player_id", keep="last").set_index("player_id")["name"].to_dict()
        self.by_name: dict[str, set] = {}
        self.by_team_name: dict[tuple, set] = {}
        for pid, name, tid in pg[["player_id", "name", "team_id"]].drop_duplicates().itertuples(index=False):
            self.by_name.setdefault(norm(name), set()).add(pid)
            self.by_team_name.setdefault((tid, norm(name)), set()).add(pid)
        self.schedule = schedule
        self.unmatched: list[dict] = []

    def team(self, name: str, source: str = "") -> str | None:
        tid = self.team_by_name.get(norm(name))
        if tid is None:
            self._review("team", source, name, "no team with this name")
        return tid

    def player(self, name: str, team_ids=None, source: str = "") -> str | None:
        """Exact normalised-name match. With team_ids, the player must have played for one of them."""
        key = norm(name)
        if team_ids:
            hits = set().union(*(self.by_team_name.get((t, key), set()) for t in team_ids))
            if len(hits) == 1:
                return next(iter(hits))
            if len(hits) > 1:
                self._review("player", source, name, "more than one player with this name on these teams")
                return None
        hits = self.by_name.get(key, set())
        if len(hits) == 1:      # exact, unique across the league (covers a player who has just changed team)
            return next(iter(hits))
        self._review("player", source, name, "no exact match" if not hits else "name is shared by several players")
        return None

    def game(self, home: str, away: str, date_et: str, source: str = "") -> str | None:
        h, a = self.team(home, source), self.team(away, source)
        if h is None or a is None:
            return None
        s = self.schedule
        hit = s[(s.home_id == h) & (s.away_id == a) & (s.date_et == date_et)]
        if len(hit) == 1:
            return hit.game_id.iloc[0]
        self._review("game", source, f"{away} @ {home} {date_et}", "no single game on the schedule")
        return None

    def _review(self, kind, source, key, why):
        self.unmatched.append({"kind": kind, "source": source, "key": key, "why": why,
                               "seen_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})

    def write_review(self) -> int:
        """Append new unmatched names to the review file (one line per distinct name)."""
        old = set()
        if self.review_path.exists():
            with open(self.review_path) as f:
                old = {(r["kind"], r["source"], r["key"]) for r in csv.DictReader(f)}
        new = {}
        for u in self.unmatched:
            k = (u["kind"], u["source"], u["key"])
            if k not in old:
                new[k] = u
        if new:
            self.review_path.parent.mkdir(parents=True, exist_ok=True)
            fresh = not self.review_path.exists()
            with open(self.review_path, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["kind", "source", "key", "why", "seen_at"])
                if fresh:
                    w.writeheader()
                w.writerows(new.values())
        return len(new)
