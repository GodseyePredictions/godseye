"""Honest scorecard for the NFL model against the betting market.

Usage: python3 backtest.py [path/to/games.csv]
Writes output/backtest.json and output/predictions.json.
"""
import itertools, json, math, sys
import numpy as np
import pandas as pd
from nfl_model import Params, load_games, run, win_prob

TUNE_END = 2014      # parameters are chosen on seasons up to here
TEST_START = 2015    # and scored only on seasons from here on
BREAK_EVEN = 110 / 210  # win rate needed to profit at -110


def implied(ml):
    return np.where(ml < 0, -ml / (-ml + 100), 100 / (ml + 100))


def tune(games):
    """Pick parameters by margin error on the tuning seasons only."""
    best, best_mae = None, 1e9
    for k, hfa, carry in itertools.product([0.04, 0.06, 0.08, 0.10], [1.5, 2.0, 2.5], [0.5, 0.62, 0.75]):
        p = Params(k=k, home_field=hfa, carryover=carry)
        d = run(games, p)
        d = d[(d.season >= 2003) & (d.season <= TUNE_END) & d.result.notna()]
        mae = (d.result - d.model_margin).abs().mean()
        if mae < best_mae:
            best, best_mae = p, mae
    return best


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/games.csv"
    games = load_games(path)
    p = tune(games)
    d = run(games, p)
    played = d[d.result.notna() & d.spread_line.notna()]
    test = played[played.season >= TEST_START].copy()

    # 1. Who predicts the final margin better?
    mae_model = (test.result - test.model_margin).abs().mean()
    mae_market = (test.result - test.spread_line).abs().mean()

    # 2. Win probability quality (log loss, lower is better), on games with moneylines
    ml = test[test.home_moneyline.notna() & test.away_moneyline.notna() & (test.result != 0)].copy()
    ph, pa = implied(ml.home_moneyline), implied(ml.away_moneyline)
    ml["p_market"] = ph / (ph + pa)  # remove the bookmaker's margin
    ml["p_model"] = ml.model_margin.apply(win_prob).clip(0.02, 0.98)
    y = (ml.result > 0).astype(int)
    ll = lambda q: float(-(y * np.log(q) + (1 - y) * np.log(1 - q)).mean())

    # 3. Would betting the model against the closing spread have paid?
    test["edge"] = test.model_margin - test.spread_line  # + means model likes home
    ats = []
    for thr in [0, 1, 2, 3, 4]:
        b = test[(test.edge.abs() >= thr) & (test.result != test.spread_line)]
        won = (np.sign(b.edge) == np.sign(b.result - b.spread_line)).sum()
        n = len(b)
        rate = won / n if n else float("nan")
        se = math.sqrt(0.25 / n) if n else float("nan")
        ats.append({"min_edge_points": thr, "bets": int(n), "win_rate": round(rate, 4),
                    "roi_at_minus_110": round(rate * (100 / 110) - (1 - rate), 4),
                    "z_vs_break_even": round((rate - BREAK_EVEN) / se, 2)})

    # 4. Does the model add anything once you already know the market line?
    train = played[(played.season >= 2003) & (played.season < TEST_START)]
    X = np.c_[train.spread_line, train.model_margin - train.spread_line]
    coef, *_ = np.linalg.lstsq(X, train.result, rcond=None)
    blend = coef[0] * test.spread_line + coef[1] * (test.model_margin - test.spread_line)
    mae_blend = (test.result - blend).abs().mean()

    out = {
        "parameters": p.__dict__,
        "test_seasons": f"{TEST_START}-{int(test.season.max())}",
        "games_scored": int(len(test)),
        "margin_error_points": {"model": round(mae_model, 3), "market_closing_spread": round(mae_market, 3),
                                "market_plus_model_blend": round(mae_blend, 3)},
        "blend_weight_on_model_disagreement": round(float(coef[1]), 3),
        "win_prob_log_loss": {"model": round(ll(ml.p_model), 4), "market": round(ll(ml.p_market), 4),
                              "games": int(len(ml))},
        "straight_up_accuracy": {"model": round(float((np.sign(test.model_margin) == np.sign(test.result)).mean()), 4),
                                 "market": round(float((np.sign(test.spread_line) == np.sign(test.result)).mean()), 4)},
        "against_the_spread": ats,
        "break_even_win_rate": round(BREAK_EVEN, 4),
    }
    json.dump(out, open("output/backtest.json", "w"), indent=2)
    print(json.dumps(out, indent=2))

    # Predictions for the next unplayed week
    up = d[d.result.isna()]
    if len(up):
        first = up.iloc[0]
        wk = up[(up.season == first.season) & (up.week == first.week)]
        preds = [{"game_id": r.game_id, "gameday": r.gameday, "away": r.away_team, "home": r.home_team,
                  "model_home_margin": round(r.model_margin, 1),
                  "model_home_win_prob": round(win_prob(r.model_margin), 3),
                  "market_home_spread": None if pd.isna(r.spread_line) else r.spread_line}
                 for r in wk.itertuples()]
        json.dump({"season": int(first.season), "week": int(first.week), "games": preds},
                  open("output/predictions.json", "w"), indent=2)
        print(f"\nWrote {len(preds)} predictions for {int(first.season)} week {int(first.week)}")


if __name__ == "__main__":
    main()
