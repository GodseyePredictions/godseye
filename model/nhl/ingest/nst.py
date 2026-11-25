"""Natural Stat Trick: on-ice rates, line-mate data and home/away and score-state splits.

Natural Stat Trick's Cloudflare refuses automated requests (HTTP 403, "you have been blocked"),
and this project does not pretend to be a browser. So `fetch` reports the refusal as NstBlocked and
nothing is substituted silently. Two things stand in, and both are labelled as such:

  * the engine's own tables cover the same ground from the NHL's play-by-play and shift charts and
    MoneyPuck's xG: on-ice xG and shot attempts per player (player_game_strength), home/away
    (team_game_strength.is_home) and score state (team_game_score);
  * a CSV exported by hand from Natural Stat Trick and dropped in nhl/data/manual/nst/ is read by
    `read_export` and stored in the `nst` table, where the Phase 1 spot-check picks it up.

File names say what the export is: <kind>_<situation>.csv, e.g. team_5v5.csv, skater_onice_5v5.csv,
lines_5v5.csv. The first text column (Team, Player or the line) names the row.
"""
import csv
import io
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from common.http import FetchError, get

SITE = "https://www.naturalstattrick.com"


class NstBlocked(Exception):
    pass


def team_table_url(season: int, situation: str = "5v5") -> str:
    s = f"{season}{season + 1}"
    return f"{SITE}/teamtable.php?fromseason={s}&thruseason={s}&stype=2&sit={situation}&score=all&rate=n&team=all&loc=B&gpf=410&fd=&td="


def fetch(url: str, root, cfg) -> bytes:
    try:
        body, _ = get(url, root, min_interval=cfg["sources"]["min_interval"]["www.naturalstattrick.com"], retries=0)
        return body
    except FetchError as e:
        if isinstance(e.__cause__, urllib.error.HTTPError) and e.__cause__.code == 403:
            raise NstBlocked("Natural Stat Trick refused the request (403). Export the table by hand into "
                             "nhl/data/manual/nst/ instead.") from e
        raise


def _num(v: str):
    v = (v or "").strip().rstrip("%")
    try:
        return float(v)
    except ValueError:
        return v or None


def read_export(path: Path, known_at: str | None = None) -> list[dict]:
    """Rows for the `nst` table from one hand-exported CSV."""
    path = Path(path)
    kind, _, situation = path.stem.rpartition("_")
    if not kind:
        raise ValueError(f"{path.name}: name the file <kind>_<situation>.csv, e.g. team_5v5.csv")
    known_at = known_at or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    rd = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    key = next((c for c in (rd.fieldnames or []) if c.strip().lower() in ("team", "player", "line")), None)
    if not key:
        raise ValueError(f"{path.name}: no Team, Player or Line column")
    return [{"kind": kind, "situation": situation, "entity": r[key].strip(), "known_at": known_at,
             "data": json.dumps({c.strip(): _num(v) for c, v in r.items() if c and c != key and c.strip()})}
            for r in rd if (r.get(key) or "").strip()]
