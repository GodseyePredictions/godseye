"""Points: the joint draw of goals and assists in the same simulated game. Never goals + assists
projected separately and added."""


def joint(goal_counts, assist_counts):
    return goal_counts + assist_counts
