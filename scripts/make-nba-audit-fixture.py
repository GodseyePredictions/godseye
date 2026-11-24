"""Writes fixtures/algo/nba-audit-sample.json: a made-up game's audit export, plus joint chances counted
straight from its simulations. The web tests check the site's joint-probability engine against those counts.

    python3 -I scripts/make-nba-audit-fixture.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model"))
sys.path.insert(0, str(ROOT / "model" / "nba" / "tests"))

from nba import audit_export  # noqa: E402
from nba.player_sim import joint_prob  # noqa: E402
from test_audit_export import leg, made_up_game  # noqa: E402

ps = made_up_game(n=60000, seed=11)
RUNGS = {"pts": {"h1": [17.5, 21.5, 25.5], "h2": [11.5, 15.5, 19.5], "h3": [4.5, 7.5], "a1": [19.5, 23.5, 27.5], "a2": [10.5, 13.5], "a3": [3.5, 6.5]},
         "reb": {"h1": [2.5], "h2": [7.5, 9.5], "a1": [3.5], "a2": [6.5, 8.5]},
         "ast": {"h1": [4.5, 6.5, 8.5], "a1": [4.5, 6.5], "a2": [1.5]},
         "fg3m": {"h1": [1.5, 2.5], "h3": [0.5], "a1": [1.5, 2.5], "a3": [0.5]},
         "pra": {"h1": [30.5], "a1": [32.5]}}
legs = [leg(ps, pid, m, line) for m, by in RUNGS.items() for pid, lines in by.items() for line in lines]
legs.append(leg(ps, "h2", "pts", 21.5, side="under"))
block = audit_export.block(legs, ps)
abbr = {"1": "HOM", "2": "AWY"}
game = {"id": "g1", "home": "HOM", "away": "AWY", "ladder": [{**l, "team": abbr[l["team_id"]]} for l in block["ladder"]], "corr": block["corr"]}

rng = np.random.default_rng(5)
checks = []
while len(checks) < 40:
    k = int(rng.integers(2, 7))
    pick = [legs[i] for i in rng.choice(len(legs), k, replace=False)]
    if len({(l["player_id"], l["market"]) for l in pick}) < k:
        continue
    active = np.logical_and.reduce([l["active"] for l in pick])
    checks.append({"legs": [{"player_id": l["player_id"], "market": l["market"], "line": l["line"], "side": l["side"]} for l in pick],
                   "counted": round(joint_prob([l["hits"] for l in pick], active), 4),
                   "independent": round(float(np.prod([l["p"] for l in pick])), 4)})
out = {"run_at": "2026-11-24T00:00:00+00:00", "note": "Made-up game for tests. Not real players or results.", "games": [game], "checks": checks}
(ROOT / "fixtures" / "algo" / "nba-audit-sample.json").write_text(json.dumps(out, indent=1))
print(len(game["ladder"]), "rungs,", len(game["corr"]), "pairs,", len(checks), "checks")
