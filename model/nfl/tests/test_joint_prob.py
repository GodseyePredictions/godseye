"""Sanity checks on the parlay maths: the chance that every leg of a ticket hits."""
import numpy as np
import pytest

from attd.correlation import joint_prob


def sigma(n, rho):
    return np.full((n, n), rho) + np.eye(n) * (1 - rho)


def test_single_leg_is_its_own_chance():
    assert joint_prob(np.array([0.63]), np.eye(1)) == pytest.approx(0.63)


@pytest.mark.parametrize("n", [2, 3, 5])
def test_unrelated_legs_multiply(n):
    p = np.array([0.80, 0.72, 0.65, 0.90, 0.55])[:n]
    assert joint_prob(p, np.eye(n)) == pytest.approx(float(np.prod(p)), abs=0.004)


@pytest.mark.parametrize("n", [2, 4])
def test_legs_that_move_together_cash_more_often(n):
    p = np.full(n, 0.7)
    apart, together = joint_prob(p, sigma(n, 0.0)), joint_prob(p, sigma(n, 0.4))
    assert together > apart


def test_legs_that_fight_each_other_cash_less_often():
    p = np.array([0.7, 0.7])
    assert joint_prob(p, sigma(2, -0.3)) < joint_prob(p, sigma(2, 0.0))


@pytest.mark.parametrize("rho", [-0.2, 0.0, 0.3, 0.6])
def test_ticket_never_beats_its_weakest_leg(rho):
    for p in (np.array([0.9, 0.5]), np.array([0.85, 0.8, 0.45, 0.7])):
        n = len(p)
        if rho < 0 and n > 2:
            continue   # an all-negative table of that size is not a valid correlation matrix
        j = joint_prob(p, sigma(n, rho))
        assert 0.0 <= j <= p.min() + 1e-9


def test_same_inputs_give_the_same_answer():
    p, S = np.array([0.8, 0.7, 0.6]), sigma(3, 0.25)
    assert joint_prob(p, S) == joint_prob(p, S)
