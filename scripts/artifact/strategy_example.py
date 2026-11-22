"""Write tonight's bankroll strategy data file for the NBA site."""
import json
import sys

out = sys.argv[1]


def rows(a):
    return [dict(zip(("slip", "type", "stake", "chance", "price", "profit"), r)) for r in a]


strat = {
    "date": "2026-11-21",
    "built": "Saturday 21 November 2026, slips from the 5:47 pm ET run",
    "intro": "How to spread a bankroll across tonight's algorithm slips: single-game parlays first, one cross-game parlay "
             "for payout, and a small lotto slip.",
    "bankrolls": [
        {"size": 200, "staked": 170, "reserve": 30, "win_chance": 0.56, "lose_all": 0.09, "typical": 21, "rows": rows([
            ("MEM @ MIN 4-leg A", "SGP", 40, 0.46, 219, 70), ("LAC @ DAL 4-leg A", "SGP", 35, 0.42, 207, 58),
            ("NO @ SA 4-leg A", "SGP", 30, 0.53, 124, 30), ("POR @ NY 6-leg", "SGP, higher payout", 40, 0.32, 439, 140),
            ("Cross-game 6-leg", "Cross-game parlay", 20, 0.36, 341, 61), ("Lotto slip, 20 legs", "Lotto", 5, 0.015, 16459, 415)])},
        {"size": 100, "staked": 80, "reserve": 20, "win_chance": 0.58, "lose_all": 0.09, "typical": 16, "rows": rows([
            ("MEM @ MIN 4-leg A", "SGP", 20, 0.46, 219, 35), ("LAC @ DAL 4-leg A", "SGP", 17, 0.42, 207, 28),
            ("NO @ SA 4-leg A", "SGP", 15, 0.53, 124, 15), ("POR @ NY 6-leg", "SGP, higher payout", 15, 0.32, 439, 53),
            ("Cross-game 6-leg", "Cross-game parlay", 10, 0.36, 341, 31), ("Lotto slip, 20 legs", "Lotto", 3, 0.015, 16459, 249)])},
    ],
    "cross_game": {"name": "Cross-game 6-leg", "chance": 0.36, "price": 341, "min_price": 190, "legs": [
        {"game": "LAC @ DAL", "label": "Zaccharie Risacher 6+ Points", "p": 0.79, "price": -220},
        {"game": "LAC @ DAL", "label": "Keaton Wagler 6+ Points", "p": 0.84, "price": -407},
        {"game": "MEM @ MIN", "label": "Cam Spencer 3+ Assists", "p": 0.97, "price": -840},
        {"game": "MEM @ MIN", "label": "LaMelo Ball 3+ Threes Made", "p": 0.79, "price": -291},
        {"game": "NO @ SA", "label": "Herbert Jones 1+ Threes Made", "p": 0.81, "price": -295},
        {"game": "NO @ SA", "label": "De'Aaron Fox 10+ Points", "p": 0.87, "price": -479}]},
    "notes": [
        "The single-game slips are on the Game SGPs tab with every leg. The lotto slip is each of tonight's five games' "
        "4-leg A slip on one ticket.",
        "About 85% of the stake is on single-game slips, 12% on the cross-game parlay and 3% on the lotto slip. One slip "
        "per game, so one bad game costs one stake.",
        "The cross-game parlay and the lotto slip use legs from the same games as the core slips, so they win on the same "
        "nights. They add payout, not safety.",
        "Chances come from 600,000 simulations using the model's own probabilities. Profit figures assume the book's real "
        "price pays about 20% less than listed on a same-game slip and about 10% less on the cross-game parlay. Those are "
        "estimates.",
        "Place slips as issued, with no added legs. Never more than a quarter of the bankroll on one slip. Do not raise "
        "stakes to chase a loss. Nothing here is a guarantee: most bettors lose over time.",
    ],
}
json.dump(strat, open(out, "w"), indent=1)
print("wrote", out)
