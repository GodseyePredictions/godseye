"""Hits: hits per 60 x ice time, the opponent's hits absorbed, and the rink's scorer bias. The score's effect
on hitting (leading sides hit less) is applied game by game from the sim."""
from nhl.props.shots import by_strength


def expected(P, ctx, team, opp, home, cfg):
    tr = ctx["team_rates"]
    opp_idx = float(tr[(tr.team == opp) & (tr.strength == "all")].hits_a60_idx.iloc[0])
    arena = ctx["arena"].get((home, "hits"), 1.0)
    notes = [{"what": f"hits taken by {opp} index", "factor": round(opp_idx, 3)}, {"what": f"{home} rink hits bias", "factor": round(arena, 3)}]
    return by_strength(P, "hits") * opp_idx * arena, notes
