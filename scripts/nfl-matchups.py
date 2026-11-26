"""Each player's matchup for one NFL game, from the NFL algorithm's own matchup index (attd/atd_versions.py).

    python3 scripts/nfl-matchups.py 2026_12_GB_LA        writes model/output/nfl_matchups_2026_12_GB_LA.json

Backs: own line against the opposing front, the opponent's run defence, goal-line share, stuffs forced.
Receivers and tight ends: expected dropbacks, yards per target the defence allows to that position, end-zone share,
pressure, red-zone pass rate. Quarterbacks: the average index of their team's three main pass-catchers.
Index of 0.6 or more is a strong matchup, -0.6 or less weak, otherwise neutral (the builder's own cut-offs).
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "model" / "nfl"))
from attd import atd_versions as av  # noqa: E402
from attd.defense_report import team_defense  # noqa: E402

STRONG, WEAK = 0.6, -0.6
gid = sys.argv[1]
season, week = int(gid[:4]), int(gid[5:7])
R = av.build(season, week, [gid])
W = R["W"].copy()
D = team_defense(season, week)
n = len(D)
tag = lambda r: "stingy" if r <= 8 else "soft" if r >= n - 7 else "average"  # noqa: E731

out = {"game_id": gid, "made_by": "scripts/nfl-matchups.py from attd/atd_versions.py", "strong": STRONG, "weak": WEAK, "players": {}, "defences": {}}
for t in W.opp.unique():
    r = D.loc[t]
    out["defences"][t] = {"run": f"{tag(r.r_rb_rush)} against the run ({int(r.r_rb_rush)}th fewest rush yds to backs of {n})",
                          "wr": f"{tag(r.r_wr_yds)} against receivers ({int(r.r_wr_yds)}th of {n})",
                          "te": f"{tag(r.r_te_yds)} against tight ends ({int(r.r_te_yds)}th of {n})"}
pc = W[W.pos_group.isin(["WR", "TE"])].sort_values("p_attd", ascending=False)
for _, r in W.iterrows():
    mx = float(r.mx)
    if r.pos_group == "QB":
        mates = pc[pc.team == r.team].head(3)
        mx = float(mates.mx.mean()) if len(mates) else 0.0
    side = {"RB": "run", "WR": "wr", "TE": "te", "QB": "wr"}.get(r.pos_group, "wr")
    out["players"][r["name"]] = {"team": r.team, "opp": r.opp, "pos": r.pos_group, "index": round(mx, 3),
                                 "tag": "strong" if mx >= STRONG else "weak" if mx <= WEAK else "neutral",
                                 "defence": out["defences"][r.opp][side]}
(ROOT / "model" / "output" / f"nfl_matchups_{gid}.json").write_text(json.dumps(out))
for k, v in sorted(out["players"].items(), key=lambda x: -x[1]["index"])[:14]:
    print(f"{k:22s} {v['team']} {v['pos']} {v['index']:+.2f} {v['tag']:7s} {v['defence']}")
