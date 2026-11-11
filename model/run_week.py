"""Run the whole weekly pipeline in the right order, so no step is skipped.

Usage: python3 run_week.py [season]
Re-run it whenever news breaks: after each injury report posts, and again when inactives are announced.
"""
import subprocess
import sys

season = sys.argv[1] if len(sys.argv) > 1 else "2026"
STEPS = [
    ["fetch_data.py", season, season],   # latest play-by-play, injury reports, snap counts, charting, roster status
    ["features.py"],                     # team, quarterback and player tables
    ["matchups.py"],                     # unit matchups and starters ruled out
    ["fetch_odds.py"],                   # current game lines
    ["apply_overrides.py"],              # user reads and late news
    ["freshness.py"],                    # roster audit: who the snapshot has wrong
    ["game_markets.py"],                 # ratings, forecasts, tickets, hybrids (holds anyone with an open alert)
]
for step in STEPS:
    print(f"\n=== {step[0]} ===", flush=True)
    subprocess.run([sys.executable, *step], check=True)
print("\nDone. Check output/freshness.json for open alerts before using any pick.")
