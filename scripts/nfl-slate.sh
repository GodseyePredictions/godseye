#!/usr/bin/env bash
# A day's NFL slips, every leg priced from the live feed, in the four steps (CLAUDE.md, "How every slip is made").
#
#   bash scripts/nfl-slate.sh 2026_12_CHI_DET 2026_12_PHI_DAL 2026_12_KC_BUF
#
# 1. prices: each game's listed rungs from The Odds API (npm run nfl:listings)
# 2. touchdowns: the algorithm's TD versions across the day's games (scripts/nfl-atd-versions.py)
# 3. matchups: strong / neutral / weak for every player (scripts/nfl-matchups.py)
# 4. slips: each game's tiers (scripts/nfl-today.ts), joined into model/output/nfl_today.json for the site
set -euo pipefail
cd "$(dirname "$0")/.."
[ "${SKIP_LISTINGS:-}" = 1 ] || for g in "$@"; do npm run -s nfl:listings -- "$g" "model/output/nfl_listed_rungs_$g.json"; done
python3 scripts/nfl-atd-versions.py "$@"
for g in "$@"; do
  python3 scripts/nfl-matchups.py "$g" > /dev/null
  node scripts/nfl-today.ts "$g"
done
python3 - "$@" <<'PY'
import json, sys
games = [json.load(open(f"model/output/nfl_today_{g}.json")) for g in sys.argv[1:]]
out = {"made_at": max(g["made_at"] for g in games), "built_from": games[0]["built_from"], "rules": games[0]["rules"],
       "listings": games[0]["listings"], "games": [{k: v for k, v in g.items() if k not in ("cross", "rules")} for g in games], "cross": games[0]["cross"]}
json.dump(out, open("model/output/nfl_today.json", "w"))
print(f"model/output/nfl_today.json: {len(games)} games")
PY
