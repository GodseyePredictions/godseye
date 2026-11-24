# ATTD backtest (out-of-sample: 2025,2026)

## Model comparison
| model                            |    n |   log_loss |   brier |    auc |   mean_pred |   actual_rate |
|:---------------------------------|-----:|-----------:|--------:|-------:|------------:|--------------:|
| baseline: position avg           | 9900 |     0.4444 |  0.1371 | 0.5787 |      0.1635 |        0.1664 |
| baseline: player rolling TD rate | 9900 |     0.4405 |  0.1261 | 0.7283 |      0.167  |        0.1664 |
| structural (team x share)        | 9900 |     0.3986 |  0.1214 | 0.7543 |      0.1658 |        0.1664 |
| FINAL (structural + GBM)         | 9900 |     0.3869 |  0.1204 | 0.7642 |      0.1637 |        0.1664 |

## Calibration (final model)
| bin         |    n |   pred |   actual |
|:------------|-----:|-------:|---------:|
| (0.0, 0.05] | 2117 |  0.034 |    0.034 |
| (0.05, 0.1] | 2511 |  0.073 |    0.075 |
| (0.1, 0.15] | 1343 |  0.123 |    0.132 |
| (0.15, 0.2] |  960 |  0.174 |    0.196 |
| (0.2, 0.25] |  734 |  0.223 |    0.241 |
| (0.25, 0.3] |  564 |  0.274 |    0.287 |
| (0.3, 0.35] |  465 |  0.324 |    0.344 |
| (0.35, 0.4] |  335 |  0.373 |    0.349 |
| (0.4, 0.5]  |  503 |  0.446 |    0.419 |
| (0.5, 0.6]  |  224 |  0.541 |    0.46  |
| (0.6, 1.0]  |  144 |  0.656 |    0.632 |

## By position
| model   |    n |   log_loss |   brier |    auc |   mean_pred |   actual_rate |
|:--------|-----:|-----------:|--------:|-------:|------------:|--------------:|
| QB      | 1002 |     0.3181 |  0.0925 | 0.7376 |      0.1159 |        0.1148 |
| RB      | 2436 |     0.4537 |  0.1478 | 0.7777 |      0.2289 |        0.2323 |
| TE      | 2528 |     0.3316 |  0.0987 | 0.7585 |      0.1151 |        0.1262 |
| WR      | 3934 |     0.3987 |  0.1244 | 0.7368 |      0.1666 |        0.1645 |

## Top features (gain)
|                     |   gain |
|:--------------------|-------:|
| lam_struct          |  58182 |
| yds_e3              |  35098 |
| p_struct            |  19491 |
| offense_pct_lag1    |   8156 |
| pos_group_share_sum |   3493 |
| offense_pct_e3      |   3194 |
| short_tgt_e3        |   3066 |
| draft_number        |   3018 |
| sh_xtd_lag1         |   2972 |
| share_raw           |   2772 |
| split_is_indoor     |   2756 |
| lam_team_pass       |   2728 |
| td_e3               |   2428 |
| split_is_turf       |   2424 |
| targets_e3          |   2341 |
| split_wx_bad        |   2213 |
| age                 |   2129 |
| mx_pos_td_allowed   |   2068 |
| lam_team_rush       |   2041 |
| sh_ez_tgt_e3        |   1955 |
| carries_e3          |   1924 |
| rush_share          |   1914 |
| vacated             |   1790 |
| sh_carries_lag1     |   1787 |
| split_slot          |   1758 |

Team TD residual same-game correlation: 0.175

## Factor report card (out-of-sample log-loss change; positive = factor helps)
Base model log loss 0.3871 -> full model 0.3869

| factor_group         |   n_features |   gain_when_added_to_base |   loss_when_removed_from_full |
|:---------------------|-------------:|--------------------------:|------------------------------:|
| stadium_weather      |            8 |                   9e-05   |                       0.00012 |
| game_time            |            4 |                  -0.00015 |                      -0.00028 |
| travel_rest          |            7 |                  -0.00029 |                      -0.00041 |
| player_splits        |           10 |                  -0.00012 |                       0.00042 |
| def_injuries         |            5 |                  -0.00015 |                      -0       |
| own_ol_injuries      |            1 |                  -0.00018 |                      -0.00066 |
| def_scheme_dc        |           17 |                  -0.00043 |                       0.00018 |
| off_playcalling_oc   |           25 |                  -0.00027 |                      -0.00021 |
| player_route_profile |            7 |                  -1e-05   |                      -0.00014 |

## Leg correlations (Gaussian copula rho)
|            |    rho |
|:-----------|-------:|
| OPP        |  0.03  |
| TM:default | -0.04  |
| TM:QB-QB   | -0.025 |
| TM:QB-RB   |  0.004 |
| TM:QB-TE   | -0.052 |
| TM:QB-WR   | -0.033 |
| TM:RB-RB   | -0.075 |
| TM:RB-TE   | -0.04  |
| TM:RB-WR   | -0.049 |
| TM:TE-TE   |  0     |
| TM:TE-WR   | -0.048 |
| TM:WR-WR   | -0.048 |