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
# Weather changes the tactics (owner, 27 November): outdoors in rain or snow, or in wind of WIND_FROM mph or more, teams run
# more and throw short, so a back's matchup moves up a step and a pass-catcher's or quarterback's moves down a step.
WIND_FROM = 15
gid = sys.argv[1]
season, week = int(gid[:4]), int(gid[5:7])
R = av.build(season, week, [gid])
W = R["W"].copy()
D = team_defense(season, week)
n = len(D)
tag = lambda r: "stingy" if r <= 8 else "soft" if r >= n - 7 else "average"  # noqa: E731

g0 = W.iloc[0]
outdoor = str(g0.get("roof_type", "")) in ("outdoors", "open")
bad = outdoor and (str(g0.get("wx_cat", "")) in ("rain", "snow") or float(g0.get("wind", 0) or 0) >= WIND_FROM)
weather = {"roof": str(g0.get("roof_type", "")), "surface": "turf" if int(g0.get("is_turf", 0) or 0) else "grass", "sky": str(g0.get("wx_cat", "")),
           "temp": float(g0.get("temp", 0) or 0), "wind": float(g0.get("wind", 0) or 0), "bad": bool(bad)}
weather["note"] = (f"{weather['sky']}, {weather['temp']:.0f}°F, wind {weather['wind']:.0f} mph: backs up a step, passing game down a step" if bad
                   else f"{weather['sky']}, {weather['temp']:.0f}°F, wind {weather['wind']:.0f} mph: no weather step")
out = {"game_id": gid, "weather": weather, "made_by": "scripts/nfl-matchups.py from attd/atd_versions.py", "strong": STRONG, "weak": WEAK, "players": {}, "defences": {}}
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
                                 "defence": out["defences"][r.opp][side],
                                 "weather_step": (1 if r.pos_group == "RB" else -1) if bad else 0}
(ROOT / "model" / "output" / f"nfl_matchups_{gid}.json").write_text(json.dumps(out))
print(weather["note"])
for k, v in sorted(out["players"].items(), key=lambda x: -x[1]["index"])[:14]:
    print(f"{k:22s} {v['team']} {v['pos']} {v['index']:+.2f} {v['tag']:7s} {v['defence']}")
