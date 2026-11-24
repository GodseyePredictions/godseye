# ATTD backtest (out-of-sample: 2025,2026)

## Model comparison
| model                            |     n |   log_loss |   brier |    auc |   mean_pred |   actual_rate |
|:---------------------------------|------:|-----------:|--------:|-------:|------------:|--------------:|
| baseline: position avg           | 10908 |     0.4441 |  0.137  | 0.5799 |      0.1634 |        0.1663 |
| baseline: player rolling TD rate | 10908 |     0.4445 |  0.1262 | 0.7249 |      0.1665 |        0.1663 |
| structural (team x share)        | 10908 |     0.4007 |  0.1216 | 0.7505 |      0.166  |        0.1663 |
| FINAL (structural + GBM)         | 10908 |     0.388  |  0.1205 | 0.7601 |      0.1674 |        0.1663 |

## Calibration (final model)
| bin         |    n |   pred |   actual |
|:------------|-----:|-------:|---------:|
| (0.0, 0.05] | 2134 |  0.034 |    0.033 |
| (0.05, 0.1] | 2752 |  0.073 |    0.076 |
| (0.1, 0.15] | 1556 |  0.123 |    0.128 |
| (0.15, 0.2] | 1081 |  0.174 |    0.183 |
| (0.2, 0.25] |  815 |  0.224 |    0.237 |
| (0.25, 0.3] |  685 |  0.274 |    0.286 |
| (0.3, 0.35] |  528 |  0.324 |    0.288 |
| (0.35, 0.4] |  415 |  0.374 |    0.378 |
| (0.4, 0.5]  |  522 |  0.445 |    0.383 |
| (0.5, 0.6]  |  273 |  0.543 |    0.527 |
| (0.6, 1.0]  |  147 |  0.652 |    0.66  |

## By position
| model   |    n |   log_loss |   brier |    auc |   mean_pred |   actual_rate |
|:--------|-----:|-----------:|--------:|-------:|------------:|--------------:|
| QB      | 1108 |     0.32   |  0.0925 | 0.7198 |      0.1155 |        0.1128 |
| RB      | 2676 |     0.4488 |  0.1459 | 0.7826 |      0.2351 |        0.2317 |
| TE      | 2793 |     0.3314 |  0.0985 | 0.7518 |      0.1182 |        0.1246 |
| WR      | 4331 |     0.4043 |  0.1261 | 0.7294 |      0.1706 |        0.1665 |

## Top features (gain)
|                     |   gain |
|:--------------------|-------:|
| lam_struct          |  56179 |
| yds_e3              |  33165 |
| p_struct            |  22542 |
| offense_pct_lag1    |   6596 |
| pos_group_share_sum |   2776 |
| xtd_e10             |   2712 |
| sh_xtd_lag1         |   2648 |
| draft_number        |   2536 |
| short_tgt_e3        |   2498 |
| mx_tgt_x_ypt        |   2457 |
| split_is_indoor     |   2306 |
| mx_cr_allowed       |   2256 |
| lam_team_pass       |   2203 |
| snap_trend          |   2084 |
| targets_e3          |   1904 |
| split_is_turf       |   1891 |
| mx_ypt_allowed      |   1849 |
| team_td_sd          |   1781 |
| age                 |   1781 |
| td_e3               |   1765 |
| split_wx_bad        |   1758 |
| exp_snaps           |   1656 |
| mx_rush_x_lane      |   1630 |
| lam_team_rush       |   1626 |
| sh_carries_lag1     |   1588 |

Team TD residual same-game correlation: 0.175

## Factor report card (out-of-sample log-loss change; positive = factor helps)
Base model log loss 0.3873 -> full model 0.3880

| factor_group         |   n_features |   gain_when_added_to_base |   loss_when_removed_from_full |
|:---------------------|-------------:|--------------------------:|------------------------------:|
| stadium_weather      |            8 |                   7e-05   |                       7e-05   |
| game_time            |            4 |                  -0.0002  |                       5e-05   |
| travel_rest          |            7 |                  -0.00012 |                      -0.00029 |
| player_splits        |           10 |                  -0.00064 |                       0.00061 |
| def_injuries         |            5 |                  -0.00027 |                       5e-05   |
| own_ol_injuries      |            1 |                  -0.00017 |                       0.00016 |
| def_scheme_dc        |           17 |                  -0.00081 |                       0.00021 |
| off_playcalling_oc   |           25 |                  -0.00046 |                       0.00025 |
| unit_matchups        |           23 |                  -0.00097 |                       3e-05   |
| defender_personnel   |           15 |                  -0.0006  |                       0.00015 |
| tempo_penalty        |           25 |                  -0.00111 |                       9e-05   |
| team_scenario        |            6 |                  -0.0007  |                      -0.00024 |
| rz_recency           |            9 |                  -0.00012 |                       0.0002  |
| role_freshness       |            4 |                  -0.00039 |                       7e-05   |
| player_route_profile |            7 |                  -6e-05   |                       0.00055 |

## Leg correlations (Gaussian copula rho)
|            |    rho |
|:-----------|-------:|
| OPP        |  0.02  |
| TM:default | -0.04  |
| TM:QB-QB   | -0.018 |
| TM:QB-RB   | -0.007 |
| TM:QB-TE   | -0.071 |
| TM:QB-WR   | -0.018 |
| TM:RB-RB   | -0.095 |
| TM:RB-TE   | -0.032 |
| TM:RB-WR   | -0.049 |
| TM:TE-TE   | -0.008 |
| TM:TE-WR   | -0.049 |
| TM:WR-WR   | -0.04  |