"""The means (framework/stats/means.py): the power mean family, with weights, overflow scaling and the error rules."""

from __future__ import annotations

import math

import numpy as np
import pytest

from stats import means


def test_linear_is_the_weighted_average_and_rms_the_root_mean_square():
    x = [1.0, 2.0, 3.0, 4.0]
    assert means.REGISTRY["linear"](x) == pytest.approx(2.5)
    assert means.REGISTRY["rms"](x) == pytest.approx(math.sqrt(30 / 4))
    assert means.REGISTRY["linear"](x, [1, 1, 1, 5]) == pytest.approx((1 + 2 + 3 + 20) / 8)


def test_weights_need_not_sum_to_one():
    assert means.power_mean([1.0, 3.0], [10, 30], 1) == pytest.approx(2.5)
    assert means.power_mean([1.0, 3.0], [1, 3], 1) == means.power_mean([1.0, 3.0], [10, 30], 1)


def test_rms_lets_one_bad_value_show_where_linear_averages_it_away():
    x = [0.1] * 9 + [5.0]
    assert means.REGISTRY["rms"](x) > 2.5 * means.REGISTRY["linear"](x)


def test_a_large_value_or_a_high_p_does_not_overflow():
    assert means.power_mean([1e200, 1e200], p=2) == pytest.approx(1e200)
    assert means.power_mean([1e5, 1e5], p=100) == pytest.approx(1e5)


def test_nan_and_nonpositive_weights_are_left_out_nothing_left_is_nan():
    assert means.power_mean([1.0, math.nan, 3.0], p=1) == pytest.approx(2.0)
    assert means.power_mean([1.0, 3.0], [1, 0], 1) == pytest.approx(1.0)
    assert math.isnan(means.power_mean([math.nan], p=1))
    assert math.isnan(means.power_mean([], p=2))
    assert means.power_mean([0.0, 0.0], p=2) == 0.0


def test_the_error_of_the_linear_mean_is_the_quadrature_of_the_weighted_errors():
    x, s = [1.0, 2.0, 3.0], [0.3, 0.3, 0.3]
    assert means.REGISTRY["linear"].error(x, s) == pytest.approx(0.3 / math.sqrt(3))


def test_the_error_of_rms_is_what_propagation_says():
    x, s = np.array([1.0, 2.0, 3.0]), np.array([0.1, 0.2, 0.3])
    m = means.power_mean(x, p=2)
    # M = sqrt(Σ x²/n):  dM/dx_i = x_i / (n M)
    want = math.sqrt(np.sum((x / (len(x) * m) * s) ** 2))
    assert means.REGISTRY["rms"].error(x, s) == pytest.approx(want)


def test_every_mean_says_what_it_hides():
    for mean in means.REGISTRY.values():
        assert mean.note and mean.guard, mean.name
