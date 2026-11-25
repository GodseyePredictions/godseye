"""Blocked shots: blocks per 60 x ice time (penalty-kill minutes carry their own, higher rate), the opponent's
shot attempts, and the rink's scorer bias. The leading-script boost and the opponent's simulated shot volume
are applied game by game from the sim."""
from nhl.props.shots import by_strength


def expected(P, ctx, team, opp, home, cfg):
    tr = ctx["team_rates"]
    opp_idx = float(tr[(tr.team == opp) & (tr.strength == "all")].cf60_idx.iloc[0])
    arena = ctx["arena"].get((home, "blocks"), 1.0)
    notes = [{"what": f"{opp} shot attempts index", "factor": round(opp_idx, 3)}, {"what": f"{home} rink blocks bias", "factor": round(arena, 3)}]
    return by_strength(P, "blocks") * opp_idx * arena, notes
