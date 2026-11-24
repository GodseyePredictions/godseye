"""Names to ids. Teams by abbreviation or full name; players by exact (accent-free) name, never by guess."""
import csv
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def load_teams(path: Path | None = None) -> list[dict]:
    with open(path or HERE / "data" / "teams.csv", newline="") as f:
        return [{**r, "lat": float(r["lat"]), "lon": float(r["lon"])} for r in csv.DictReader(f)]


TEAMS = load_teams()
_BY_NAME = {norm(t["name"]): t["abbrev"] for t in TEAMS} | {norm(t["abbrev"]): t["abbrev"] for t in TEAMS} | \
           {norm(k): v for k, v in {"LA": "LAK", "MON": "MTL", "NAS": "NSH", "NJ": "NJD", "SJ": "SJS", "TB": "TBL", "VEG": "VGK",
                                      "WAS": "WSH"}.items()} | \
           {norm("Utah Hockey Club"): "UTA", norm("Utah HC"): "UTA", norm("Montréal Canadiens"): "MTL", norm("St Louis Blues"): "STL"}


def team(name: str) -> str | None:
    return _BY_NAME.get(norm(name))


def slug(abbrev: str) -> str:
    """Daily Faceoff's URL name for a team: 'st-louis-blues'."""
    name = next(t["name"] for t in TEAMS if t["abbrev"] == abbrev)
    return norm(name).replace(" ", "-")


def load_aliases(path: Path | None = None) -> dict:
    """Spellings a source uses that differ from the NHL's (data/name_aliases.csv: alias, name). Added by hand, one at a time."""
    path = path or HERE / "data" / "name_aliases.csv"
    if not path.exists():
        return {}
    with open(path, newline="") as f:
        return {r["alias"]: r["name"] for r in csv.DictReader(f)}


class PlayerIndex:
    """Exact-name lookup against the players table. A name that matches nobody, or two players on the
    same team, returns None and is listed in `unmatched` for review."""

    def __init__(self, players, aliases: dict | None = None):
        self.by_team, self.by_name, self.unmatched = {}, {}, []
        self.aliases = {norm(a): norm(b) for a, b in (load_aliases() if aliases is None else aliases).items()}
        for p in players:
            n = norm(p["name"])
            self.by_team.setdefault((p["team"], n), []).append(p["player_id"])
            self.by_name.setdefault(n, []).append(p["player_id"])

    def find(self, name: str, team_abbrev: str | None = None):
        n = norm(name)
        n = self.aliases.get(n, n)
        hit = self.by_team.get((team_abbrev, n)) if team_abbrev else None
        if not hit:
            hit = self.by_name.get(n)
        if hit and len(set(hit)) == 1:
            return hit[0]
        self.unmatched.append((name, team_abbrev))
        return None
