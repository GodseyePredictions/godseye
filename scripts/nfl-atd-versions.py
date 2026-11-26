"""The NFL algorithm's touchdown versions (attd/atd_versions.py) for a set of games, as JSON for the slip builder.

    python3 scripts/nfl-atd-versions.py 2026_12_CHI_DET 2026_12_PHI_DAL 2026_12_KC_BUF

Writes model/output/nfl_atd_versions.json: the games, players held out of touchdown parlays and why, each version's
tickets, and the touchdown board.
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "model" / "nfl"))
from attd import atd_versions as av  # noqa: E402

games = sys.argv[1:]
season, week = int(games[0][:4]), int(games[0][5:7])
R = av.build(season, week, games)
leg = lambda r: {"name": r["name"], "team": r["team"], "pos": r["pos_group"], "game": r["game_id"], "p": float(r["p_attd"]), "id": r["player_id"], "mx": r.get("mx_tag", "")}  # noqa: E731
out = {
    "games": games,
    "held": [list(h) for h in R["held"]],
    "versions": {k: {"name": v["name"], "note": v["note"], "tickets": [{"n": t["n"], "p": float(t["p"]), "p_indep": float(t.get("p_indep", t["p"])), "mix": t.get("mix", ""),
                                                                       "legs": [leg(r) for _, r in t["legs"].iterrows()]} for t in v["tickets"]]} for k, v in R["versions"].items()},
    "board": [{"name": r["name"], "team": r["team"], "pos": r["pos_group"], "game": r["game_id"], "p": float(r["p_attd"]), "singles": bool(r.get("singles_only", False)), "id": r["player_id"]}
              for _, r in R["board"].sort_values("p_attd", ascending=False).iterrows()],
}
(ROOT / "model" / "output" / "nfl_atd_versions.json").write_text(json.dumps(out))
print(f"{len(games)} games, {len(out['board'])} on the board, held: {[h[0] for h in out['held']]}")
for t in out["versions"]["combo"]["tickets"]:
    print(f"  {t['n']}-leg {t['mix']}: {t['p']:.3f}  " + ", ".join(x["name"] for x in t["legs"]))
