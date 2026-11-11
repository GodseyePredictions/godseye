"""Every threshold, weight and cap for the NBA module. Nothing else in the module hard-codes one.

Change a value here and every stage picks it up. Tests may pass their own copy of CONFIG.
"""
import os

CONFIG = {
    # ---- sources and politeness -------------------------------------------------------------
    "min_interval": {"site.api.espn.com": 0.15, "api.pbpstats.com": 1.5, "www.basketball-reference.com": 3.5,
                     "official.nba.com": 1.0, "ak-static.cms.nba.com": 0.5, "api.the-odds-api.com": 1.0},
    "retries": 4,
    "odds_api_key_env": "ODDS_API_KEY",
    "odds_regions": "us,uk,eu,au",
    "odds_book": "bet365",
    "injury_report_lead_min": 30,        # use the last official report at least this long before tip
    "officials_posted_utc_hour": 14,     # referee assignments are posted about 9am ET on game day

    # ---- parsing ----------------------------------------------------------------------------
    "rim_max_ft": 4.5,                   # shots this close to the basket count as rim attempts
    "corner3_max_y": 9.0,                # threes no further than this from the baseline are corner threes
    "close_margin": 5,                   # "close game": within this many points in the last 5 minutes

    # ---- availability gate ------------------------------------------------------------------
    "status_map": {"out": "out", "doubtful": "doubtful", "questionable": "questionable",
                   "probable": "questionable", "available": "confirmed_in"},
    "unlisted_status": "confirmed_in",   # on the roster, team has filed its report, player not listed
    "unsubmitted_status": "unknown",     # team has not filed yet
    "ticket_statuses": ["confirmed_in"],
    "projected_statuses": ["confirmed_in", "questionable"],
    "return_ramp_games": 5,              # games after an absence during which the ramp applies
    "absence_min_games": 3,              # missed games that count as an injury absence
    "restriction_pattern": r"(\d{2})\s*(?:-|to)?\s*(?:\d{2})?\s*minute",

    # ---- schedule ---------------------------------------------------------------------------
    "b2b_days": 1, "three_in_four_days": 4,

    # ---- minutes model ----------------------------------------------------------------------
    "min_weights": {"season": 0.35, "last10": 0.30, "last5": 0.35},
    "min_weights_role_change": {"season": 0.10, "last10": 0.30, "last5": 0.60},
    "role_change_minutes": 6.0,          # last-5 minutes this far from season minutes = role change
    "role_starter_share": 0.5,           # started at least this share of recent games = starter
    "role_sixth_min": 22.0, "role_rotation_min": 12.0,
    "reconcile_floor": 0.10,             # share of the 240-minute reconciliation every player takes regardless of sample
    "min_prior_games": 8,                # shrinkage strength (in games) for a player's minutes
    "team_effect_prior_games": 25,       # shrinkage for a team's (coach's) blowout habits
    "ramp_minutes_factor": [0.80, 0.86, 0.91, 0.95, 0.98],   # starting point; refitted from history
    "load_mgmt_age_games": 600,          # career-games proxy is unavailable; see minutes.py
    "margin_buckets": [-99, -20, -12, -5, 5, 12, 20, 99],     # final margin, from the player's side
    "q4_entry_buckets": [-99, -20, -15, -8, 8, 15, 20, 99],   # margin entering the fourth
    "minutes_sd_floor": 2.5,
    "wowy_prior_games": 12,              # shrinkage (in games) for with/without splits
    "wowy_min_games": 4,                 # fewer games than this without the teammate = positional rule
    "rotation_min": 15.0,                # a "rotation player" for in/out purposes averages this many minutes

    # ---- game script ------------------------------------------------------------------------
    "rating_half_life_games": 25,
    "rating_ridge": 6.0,
    "season_carry": 0.6,
    "market_weight_early": 0.85, "market_weight_late": 0.65, "market_weight_switch_games": 20,
    "n_sims": 10000, "n_sims_backtest": 2000,
    "blowout_q4_lead": 15, "blowout_2h_lead": 20,
    "blowout_flag_prob": 0.55,           # warning threshold. 47% of real games meet the blowout definition, so 0.30 flagged every game;
                                         # 0.55 flags about one game in five
    "blowout_2h_checkpoint_lead": 18,    # simulated leads are only seen every six minutes; 18 there stands for "20 at any point"
    "home_court_prior": 2.3,
    "sim_poss_sd": 1.5,                  # game-to-game spread of possessions around the projection
    "sim_eff_sd": 0.0,                   # extra game-to-game spread of a team's shooting (log scale); shot-by-shot noise already covers it
    "sim_segment_poss_sd": 0.5,
    "rubber_band": 0.08,                 # share of the current margin pulled back in each six-minute segment
    "ot_total_allowance": 1.1,           # points the average game gains from overtime; taken off the regulation target
    "ot_pull_prob": 0.22,                # chance a one- or two-point game is tied up and goes to overtime
    "credited_rebound_share": 0.87,      # share of missed shots that end as a rebound credited to a player
    "ft_miss_rebound_share": 0.45,       # share of missed free throws that can be rebounded
    "close_mid_q4_margin": 10,            # stand-in for "within 5 in the last 5 minutes": margin with 6:00 left
    "style_prior_games": 12,             # shrinkage (in games) of a team's style toward last season / the league
    "ref_prior_games": 40,
    "missing_window_games": 15,

    # ---- player stat models -----------------------------------------------------------------
    "last_season_weight": 0.45,          # weight of a last-season minute relative to a this-season minute
    "rate_prior_minutes": {"pts": 250, "reb": 250, "ast": 300, "fg3m": 500, "stl": 700, "blk": 700,
                           "fga": 250, "fg3a": 350, "fta": 350},
    "form_games": 5,
    "form_cap_volume": 0.30,             # the most last-5 volume may move a rate (log scale)
    "form_cap_shooting": 0.05,           # the most last-5 shooting percentages may move a make rate
    "form_pseudo": {"fg2a": 12, "fg3a": 8, "fta": 6, "reb": 10, "ast": 8, "stl": 3, "blk": 3},
    "eff_prior_attempts": {"p2": 150, "p3": 250, "ft": 100, "rim": 100, "mid": 150},
    "opp_pos_prior_games": 15,
    "q4_usage_prior_fga": 60,
    "q4_usage_weight": 0.25,             # how much of a player's close-fourth-quarter usage shift is applied
    "share_noise_sd": {"usage": 0.0, "fg2a": 0.0, "fg3a": 0.08, "fta": 0.15, "oreb": 0.35, "dreb": 0.20,
                       "ast": 0.12, "stl": 0.30, "blk": 0.40, "make": 0.0},
    "role_shift_usage": 0.20,            # last-5 usage this far from season usage = flagged
    "max_total_adjustment": 0.25,        # stacked factors cannot move a rate more than this
    "home_away_cap": 0.03,
    "factor_groups_on": {"form": True, "opp_shot_profile": True, "opp_position": True, "rim_protection": True,
                         "situational": False,   # switched off: did not improve out-of-sample accuracy (docs/nba_backtest.md)
                         "teammate_inout": True, "referee": True},
    "shooting_gate_fg_margin": 0.0,      # expected FG% must be at least baseline + this
    "shooting_gate_3p_margin": 0.0,
    "shooting_gate_3pa_margin": 0.0,

    # ---- simulation and markets -------------------------------------------------------------
    "dd_publish_min_prob": 0.25, "td_publish_min_prob": 0.05,
    "calibration_grid": {"pts": [10, 15, 20, 25, 30, 35], "reb": [4, 6, 8, 10, 12], "ast": [2, 4, 6, 8, 10],
                         "fg3m": [1, 2, 3, 4, 5], "stl": [1, 2, 3], "blk": [1, 2, 3],
                         "pra": [15, 20, 25, 30, 35, 40, 45], "pr": [10, 15, 20, 25, 30, 35],
                         "pa": [10, 15, 20, 25, 30, 35]},

    # ---- tickets ----------------------------------------------------------------------------
    "sgp_leg_floor": 0.70,
    "sgp_sizes": [4, 6],
    "ticket_min_joint": {4: 0.30, 6: 0.18, 5: 0.25},
    "max_legs_per_player": 2,
    "max_legs_same_script": 4,
    "upper_rung_rank": 2,                # in blowout-flagged games starters may use only their lowest rungs
    "single_min_ev": 0.02,
    "kelly_fraction": 0.25, "kelly_cap": 0.03,
    "sgp_candidate_pool": 14,
    # With no book prices loaded, publish model-only tickets on standard milestone thresholds, clearly labelled
    # "rung and price not checked at the book". They cannot be marked as placed. Set False to print "no bet" instead.
    "preview_tickets_without_prices": True,
    "preview_min_minutes": 18.0,
    "script_dependence_gap": 0.10,       # a leg "depends on a script" when its chance differs this much between scripts
    "combo_component_ev_gain": 0.02,     # a combo may sit with its own component only if EV improves by this much
    "dd_ticket_max_legs": 3,

    # ---- grading ----------------------------------------------------------------------------
    "calibration_tolerance": 0.06,       # alert when a market's hit rate strays this far from its forecast
    "calibration_min_legs": 100,
    "small_sample": 200,                 # results on fewer legs than this are marked "too small to trust"
    "minutes_miss": 6.0,                 # minutes this far under projection tags a miss as a minutes miss
}


def odds_api_key() -> str | None:
    return os.environ.get(CONFIG["odds_api_key_env"]) or None
