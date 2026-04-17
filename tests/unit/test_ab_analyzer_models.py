from __future__ import annotations

from services.ab_testing.analyzer import _bayesian_normal_probability, _bayesian_rate_probability


def test_bayesian_rate_probability_bounds() -> None:
    probability = _bayesian_rate_probability(
        control_successes=20,
        control_trials=100,
        treatment_successes=35,
        treatment_trials=100,
    )
    assert 0.0 <= probability <= 1.0
    assert probability > 0.5


def test_bayesian_normal_probability_bounds() -> None:
    probability = _bayesian_normal_probability(
        control_vals=[1.2, 1.1, 1.3, 1.0],
        treatment_vals=[1.5, 1.6, 1.4, 1.7],
    )
    assert 0.0 <= probability <= 1.0
    assert probability > 0.5
