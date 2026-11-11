"""The official NBA injury report: find the right PDF for a moment in time, download it, parse it.

Reports are published as PDFs named by Eastern time: hourly up to 2025-26, every 15 minutes from
2026-27. The report time is the timestamp: a row is "known" from the moment its report was posted.
"""
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from common.http import FetchError, get
from nba.config import CONFIG
from nba.ids import TEAMS, norm
from nba.store import RAW

ET = ZoneInfo("America/New_York")
BASE = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{d}_{t}.pdf"
STATUSES = "Out|Questionable|Doubtful|Probable|Available"
WORDS = r"[A-Z][A-Za-z.'\-]*(?: [A-Za-z.'\-]+)*"
PLAYER = re.compile(rf"({WORDS},\s?{WORDS})\s{{2,}}({STATUSES})\b\s*(.*)$")
MATCHUP = re.compile(r"\b([A-Z]{2,3})@([A-Z]{2,3})\b")
GDATE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
TEAM_NAMES = sorted((full for full, _ in TEAMS.values()), key=len, reverse=True) + ["Los Angeles Clippers"]
FIFTEEN_MIN_FROM = "2025-12-22"   # the NBA moved from hourly to 15-minute reports on this date


def report_url(when_et: datetime) -> str:
    d = when_et.strftime("%Y-%m-%d")
    if d >= FIFTEEN_MIN_FROM:
        return BASE.format(d=d, t=when_et.strftime("%I_%M%p"))
    return BASE.format(d=d, t=when_et.strftime("%I%p"))


def report_time_before(moment_utc: datetime) -> datetime:
    """The latest publication slot at or before `moment_utc`, as an Eastern time."""
    t = moment_utc.astimezone(ET)
    step = 15 if t.strftime("%Y-%m-%d") >= FIFTEEN_MIN_FROM else 60
    return t.replace(minute=(t.minute // step) * step, second=0, microsecond=0)


def fetch_report(when_et: datetime, max_age=None) -> tuple[bytes, datetime] | None:
    try:
        body, _ = get(report_url(when_et), RAW, min_interval=CONFIG["min_interval"]["ak-static.cms.nba.com"],
                      retries=2, max_age=max_age)
    except FetchError:
        return None
    return body, when_et


def fetch_latest_before(moment_utc: datetime, look_back: int = 8) -> tuple[bytes, datetime] | None:
    """Walk back slot by slot until a report exists (some slots are never published)."""
    t = report_time_before(moment_utc)
    step = timedelta(minutes=15 if t.strftime("%Y-%m-%d") >= FIFTEEN_MIN_FROM else 60)
    for _ in range(look_back):
        got = fetch_report(t)
        if got:
            return got
        t -= step
    return None


def pdf_text(body: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(body); f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, check=True).stdout


def parse_report(text: str, report_et: datetime) -> list[dict]:
    """One row per listed player, plus one row per team that has not filed (player_name '')."""
    rows, team, matchup, gdate = [], None, None, None
    orphan_before, last_row = None, None
    report_utc = report_et.astimezone(timezone.utc).isoformat(timespec="seconds")
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("Injury Report:", "Game Date", "Page ")):
            continue
        m = GDATE.search(line)
        if m:
            gdate = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        m = MATCHUP.search(line)
        if m:
            matchup = m.group(0)
        for name in TEAM_NAMES:
            if name in line:
                team = "LA Clippers" if name == "Los Angeles Clippers" else name
                break
        base = {"report_utc": report_utc, "game_date": gdate, "matchup": matchup, "team": team, "player_id": None}
        if "NOT YET SUBMITTED" in line and team:
            rows.append({**base, "player_name": "", "status": "NOT YET SUBMITTED", "reason": None})
            continue
        m = PLAYER.search(line)
        if m and team:
            last, first = [x.strip() for x in m.group(1).split(",", 1)]
            reason = m.group(3).strip() or orphan_before      # a wrapped reason sits on the lines around the name
            last_row = {**base, "player_name": f"{first} {last}", "status": m.group(2), "reason": reason,
                        "_wrapped": not m.group(3).strip()}
            rows.append(last_row)
            orphan_before = None
        elif line.startswith(" " * 40) and not MATCHUP.search(line):
            text = line.strip()
            if last_row is not None and last_row.get("_wrapped") and last_row.get("_tail") is None:
                last_row["reason"] = f"{last_row['reason'] or ''} {text}".strip()
                last_row["_tail"] = True
            else:
                orphan_before = text
    for r in rows:
        r.pop("_wrapped", None); r.pop("_tail", None)
    return rows


def resolve_ids(rows: list[dict], idmap) -> list[dict]:
    for r in rows:
        if r["player_name"]:
            tid = idmap.team(r["team"], "injury_report")
            r["player_id"] = idmap.player(r["player_name"], [tid] if tid else None, "injury_report")
    return rows
