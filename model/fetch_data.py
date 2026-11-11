"""Download the public nflverse files the models read.

Usage: python3 fetch_data.py [first_season] [last_season]
Play-by-play files and the player list are large and are not committed; games.csv is.
"""
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
PBP = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{s}.csv.gz"
GAMES = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PLAYERS = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r:
        dest.write_bytes(r.read())
    print(f"{dest.name}: {dest.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 2021
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    fetch(GAMES, DATA / "games.csv")
    fetch(PLAYERS, DATA / "players.csv")
    for s in range(first, last + 1):
        fetch(PBP.format(s=s), DATA / "pbp" / f"play_by_play_{s}.csv.gz")
        # injury reports, snap counts and (from 2022) play charting, used by matchups.py
        for kind, start in (("injuries", 2015), ("snap_counts", 2015), ("ftn_charting", 2022)):
            if s >= start:
                fetch(f"https://github.com/nflverse/nflverse-data/releases/download/{kind}/{kind}_{s}.csv", DATA / kind / f"{kind}_{s}.csv")
