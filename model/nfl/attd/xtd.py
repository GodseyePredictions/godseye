"""Play-level expected touchdown (xTD) models.

Actual TDs are extremely noisy. A carry at the 1 is worth ~0.45 TDs, a carry at midfield ~0.01.
A target 25 yards downfield from the opponent's 22 (i.e. an end-zone target) is worth far more than a
checkdown. We fit P(TD | opportunity context) for rushes and targets separately and sum per player-game.
That opportunity-weighted xTD is the single most predictive input of future TD scoring.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

RUSH_FEATS = ["yardline_100", "down", "ydstogo", "goal_to_go", "is_qb"]
TGT_FEATS = ["yardline_100", "down", "ydstogo", "goal_to_go", "air_yards", "ez_target"]

_PARAMS = dict(objective="binary", n_estimators=300, learning_rate=0.05, num_leaves=15,
               min_child_samples=200, subsample=0.8, subsample_freq=1, verbose=-1,
               monotone_constraints_method="advanced")


def prep_plays(pbp: pd.DataFrame, qb_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = pbp[(pbp.two_point_attempt != 1) & (pbp.qb_kneel != 1) & (pbp.qb_spike != 1)]
    p = p[p.play_type.isin(["run", "pass"])].copy()
    p["off_td"] = ((p.touchdown == 1) & (p.td_team == p.posteam)).astype(int)

    rushes = p[(p.rush == 1) & p.rusher_player_id.notna()].copy()
    rushes["player_id"] = rushes.rusher_player_id
    rushes["is_qb"] = rushes.player_id.isin(qb_ids).astype(int)
    rushes["y"] = ((rushes.off_td == 1) & (rushes.td_player_id == rushes.player_id)).astype(int)

    tg = p[(p["pass"] == 1) & (p.sack != 1) & p.receiver_player_id.notna()].copy()
    tg["player_id"] = tg.receiver_player_id
    tg["air_yards"] = tg.air_yards.fillna(0)
    tg["ez_target"] = (tg.air_yards >= tg.yardline_100).astype(int)
    tg["y"] = ((tg.off_td == 1) & (tg.td_player_id == tg.player_id)).astype(int)
    return rushes, tg


class XTDModel:
    def fit(self, rushes, targets):
        self.rush = lgb.LGBMClassifier(**_PARAMS, monotone_constraints=[-1, 0, 0, 0, 0])
        self.rush.fit(rushes[RUSH_FEATS].fillna(0), rushes.y)
        self.tgt = lgb.LGBMClassifier(**_PARAMS, monotone_constraints=[0, 0, 0, 0, 0, 1])
        self.tgt.fit(targets[TGT_FEATS].fillna(0), targets.y)
        return self

    def score(self, rushes, targets):
        rushes = rushes.assign(xtd=self.rush.predict_proba(rushes[RUSH_FEATS].fillna(0))[:, 1])
        targets = targets.assign(xtd=self.tgt.predict_proba(targets[TGT_FEATS].fillna(0))[:, 1])
        return rushes, targets
