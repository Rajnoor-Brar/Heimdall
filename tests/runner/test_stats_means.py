"""The means (framework/stats/means.py): the power family with weights and overflow scaling, the order-statistic and
robust means, their error rules and guards, and the two means of whole histograms. Every value here is worked by hand."""

from __future__ import annotations

import math

import numpy as np
import pytest

from runner.errors import HeimdallError
from stats import means

X = [1.0, 2.0, 3.0, 4.0, 10.0]


# ── the power family ──────────────────────────────────────────────────────────────────────────

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
    assert means.power_mean([1e-200, 1e-200], p=-3) == pytest.approx(1e-200)


def test_nan_and_nonpositive_weights_are_left_out_nothing_left_is_nan():
    assert means.power_mean([1.0, math.nan, 3.0], p=1) == pytest.approx(2.0)
    assert means.power_mean([1.0, 3.0], [1, 0], 1) == pytest.approx(1.0)
    assert math.isnan(means.power_mean([math.nan], p=1))
    assert math.isnan(means.power_mean([], p=2))
    assert means.power_mean([0.0, 0.0], p=2) == 0.0
    assert math.isnan(means.REGISTRY["median"]([math.nan]))


def test_the_power_family_by_hand():
    assert means.evaluate("min", X) == 1.0 and means.evaluate("max", X) == 10.0
    assert means.evaluate("linear", X) == pytest.approx(4.0)
    assert means.evaluate("rms", X) == pytest.approx(math.sqrt(130 / 5))
    assert means.evaluate("cubic", X) == pytest.approx((1 + 8 + 27 + 64 + 1000) ** (1 / 3) / 5 ** (1 / 3))
    assert means.evaluate("geometric", X) == pytest.approx(240 ** 0.2)
    assert means.evaluate("harmonic", X) == pytest.approx(5 / (1 + 0.5 + 1 / 3 + 0.25 + 0.1))
    assert means.evaluate("power", X, p=-1) == pytest.approx(means.evaluate("harmonic", X))
    assert means.evaluate("power", X, p=0.5) == pytest.approx((sum(v ** 0.5 for v in X) / 5) ** 2)


def test_the_power_means_are_ordered_by_p():
    chain = [means.evaluate(n, X) for n in ("min", "harmonic", "geometric", "linear", "rms", "cubic", "max")]
    assert chain == sorted(chain) and len(set(chain)) == 7


def test_signs_linear_keeps_them_even_powers_ignore_them_odd_keep_them():
    x = [-3.0, 1.0, 2.0]
    assert means.evaluate("linear", x) == pytest.approx(0.0)
    assert means.evaluate("rms", x) == pytest.approx(math.sqrt(14 / 3))
    assert means.evaluate("cubic", x) == pytest.approx(math.copysign(abs((-27 + 1 + 8) / 3) ** (1 / 3), -18))


def test_geometric_and_harmonic_refuse_a_zero_unless_given_a_floor():
    for name in ("geometric", "harmonic"):
        with pytest.raises(HeimdallError) as caught:
            means.evaluate(name, [0.0, 1.0, 2.0])
        assert "floor" in str(caught.value)
    assert means.evaluate("geometric", [0.0, 1.0, 2.0], floor=0.5) == pytest.approx((0.5 * 1 * 2) ** (1 / 3))
    assert means.evaluate("harmonic", [0.0, 1.0, 2.0], floor=0.5) == pytest.approx(3 / (2 + 1 + 0.5))


def test_a_fractional_power_refuses_a_negative_value():
    with pytest.raises(HeimdallError):
        means.evaluate("power", [-1.0, 2.0], p=0.5)


def test_lehmer_and_the_contraharmonic_mean():
    assert means.evaluate("contraharmonic", X) == pytest.approx(130 / 20)
    assert means.evaluate("lehmer", X, p=2) == pytest.approx(means.evaluate("contraharmonic", X))
    assert means.evaluate("lehmer", X, p=1) == pytest.approx(means.evaluate("linear", X))
    assert means.evaluate("lehmer", X, p=0) == pytest.approx(means.evaluate("harmonic", X))
    with pytest.raises(HeimdallError):
        means.evaluate("lehmer", [-1.0, 3.0], p=2)
    assert means.evaluate("lehmer", [1e200, 1e200], p=2) == pytest.approx(1e200)


def test_logsumexp_runs_from_the_minimum_through_the_mean_to_the_maximum():
    assert means.evaluate("logsumexp", X, beta=1e-9) == pytest.approx(4.0, rel=1e-6)
    assert means.evaluate("logsumexp", X, beta=200.0) == pytest.approx(10.0 - math.log(5) / 200, rel=1e-9)
    assert means.evaluate("logsumexp", X, beta=-200.0) == pytest.approx(1.0 + math.log(5) / 200, rel=1e-9)
    assert math.isfinite(means.evaluate("logsumexp", [1000.0, 1001.0], beta=1.0))             # no overflow
    assert means.evaluate("logsumexp", [3.0], beta=2.0) == pytest.approx(3.0)


# ── the order-statistic and robust means ──────────────────────────────────────────────────────

def test_median_by_hand_and_weighted():
    assert means.evaluate("median", [1.0, 2.0, 3.0, 100.0]) == pytest.approx(2.5)
    assert means.evaluate("median", [5.0, 1.0, 3.0]) == pytest.approx(3.0)
    assert 2.9 < means.evaluate("median", [1.0, 2.0, 3.0], [1, 1, 100]) <= 3.0


def test_trimmed_cuts_alpha_from_each_end_and_fractionally_at_the_boundary():
    spiked = [1, 2, 3, 4, 5, 6, 7, 100]
    assert means.evaluate("trimmed", spiked, alpha=0.25) == pytest.approx((3 + 4 + 5 + 6) / 4)
    ten = list(range(1, 11))                                                    # 1.5 values off each end
    assert means.evaluate("trimmed", ten, alpha=0.15) == pytest.approx((0.5 * 2 + sum(range(3, 9)) + 0.5 * 9) / 7)
    assert means.evaluate("trimmed", ten, alpha=0.0) == pytest.approx(5.5)


def test_trimmed_refuses_what_it_cannot_trim():
    for bad in ({"alpha": 0.5}, {"alpha": -0.1}):
        with pytest.raises(HeimdallError):
            means.evaluate("trimmed", [1.0, 2.0, 3.0, 4.0], **bad)
    with pytest.raises(HeimdallError) as caught:
        means.evaluate("trimmed", [1.0, 2.0, 3.0], alpha=0.25)
    assert "at least 4" in str(caught.value)
    for name in ("trimmed_geometric", "winsorized"):
        with pytest.raises(HeimdallError):
            means.evaluate(name, [1.0, 2.0, 3.0], alpha=0.25)


def test_trimmed_geometric_keeps_the_log_slope_and_drops_the_spike():
    x = [1, 2, 4, 8, 16, 32, 64, 1e9]
    assert means.evaluate("trimmed_geometric", x, alpha=0.25) == pytest.approx((4 * 8 * 16 * 32) ** 0.25)
    with pytest.raises(HeimdallError):
        means.evaluate("trimmed_geometric", [0.0] * 8, alpha=0.25)
    assert means.evaluate("trimmed_geometric", [0.0] * 8, alpha=0.25, floor=1e-3) == pytest.approx(1e-3)


def test_winsorized_clamps_instead_of_dropping():
    assert means.evaluate("winsorized", [1, 2, 3, 4, 5, 6, 7, 100], alpha=0.25) == pytest.approx((3 * 3 + 4 + 5 + 3 * 6) / 8)


def test_midhinge_and_trimean_ignore_the_outer_values():
    base = [1, 2, 3, 4, 5, 6, 7, 8]
    spiked = [1, 2, 3, 4, 5, 6, 7, 5000]
    assert means.evaluate("midhinge", base) == pytest.approx((2.5 + 6.5) / 2)
    assert means.evaluate("trimean", base) == pytest.approx((2.5 + 2 * 4.5 + 6.5) / 4)
    assert means.evaluate("midhinge", spiked) == pytest.approx(means.evaluate("midhinge", base) + 0.0, abs=0.5)
    assert means.evaluate("trimean", spiked) == pytest.approx(means.evaluate("trimean", base), abs=0.5)
    for name in ("midhinge", "trimean"):
        with pytest.raises(HeimdallError):
            means.evaluate(name, [1.0, 2.0, 3.0])


def test_hodges_lehmann_is_the_median_of_the_pair_averages():
    x = [1.0, 2.0, 3.0, 4.0, 100.0]
    walsh = sorted((a + b) / 2 for i, a in enumerate(x) for b in x[i:])
    assert means.evaluate("hodges_lehmann", x) == pytest.approx(float(np.median(walsh)))
    assert means.evaluate("hodges_lehmann", x) < 5
    with pytest.raises(HeimdallError) as caught:
        means.evaluate("hodges_lehmann", x, [1, 1, 1, 1, 5])
    assert "weights" in str(caught.value)
    with pytest.raises(HeimdallError):
        means.evaluate("hodges_lehmann", list(range(1001)))


def test_huber_and_tukey_shrug_off_a_spike_where_linear_does_not():
    x = [10.0, 10.1, 9.9, 10.05, 9.95, 1000.0]
    assert means.evaluate("linear", x) > 150
    for name in ("huber", "tukey"):
        assert 9.9 < means.evaluate(name, x) < 10.2, name
    assert means.evaluate("tukey", x) == pytest.approx(10.0, abs=0.03)           # rejected outright


def test_the_m_estimates_fall_back_when_the_scale_collapses():
    assert means.evaluate("huber", [5.0] * 6) == 5.0
    assert means.evaluate("tukey", [5.0, 5.0, 5.0, 5.0, 5.0, 9.0]) == pytest.approx(5.0)       # MAD 0 -> IQR 0 -> the median
    assert means.evaluate("huber", [1.0, 2.0]) == pytest.approx(1.5)
    assert means.evaluate("huber", [1.0, 2.0, 3.0], [1, 1, 8]) > 2.5                              # weights count


# ── the errors ────────────────────────────────────────────────────────────────────────────────

def test_the_error_of_the_linear_mean_is_the_quadrature_of_the_weighted_errors():
    x, s = [1.0, 2.0, 3.0], [0.3, 0.3, 0.3]
    assert means.REGISTRY["linear"].error(x, s) == pytest.approx(0.3 / math.sqrt(3))
    assert means.REGISTRY["linear"].error([1.0, 3.0], [0.1, 0.2], [1, 3]) == pytest.approx(math.hypot(0.25 * 0.1, 0.75 * 0.2))
    assert means.REGISTRY["linear"].error_kind == "exact"


def test_the_error_of_rms_is_what_propagation_says():
    x, s = np.array([1.0, 2.0, 3.0]), np.array([0.1, 0.2, 0.3])
    m = means.power_mean(x, p=2)
    want = math.sqrt(np.sum((x / (len(x) * m) * s) ** 2))
    assert means.REGISTRY["rms"].error(x, s) == pytest.approx(want)


@pytest.mark.parametrize("name,settings", [("geometric", {}), ("harmonic", {}), ("cubic", {}), ("power", {"p": 1.5}),
                                           ("lehmer", {"p": 2.0}), ("contraharmonic", {}), ("logsumexp", {"beta": 0.7})])
def test_a_smooth_mean_s_error_is_its_gradient_in_quadrature(name, settings):
    """The analytic error equals the finite-difference gradient, and the mean says it is first order."""
    x, s, w = np.array([1.0, 2.0, 3.0, 4.5]), np.array([0.1, 0.05, 0.2, 0.15]), np.array([1.0, 2.0, 1.0, 3.0])
    mean = means.REGISTRY[name]
    grad = np.array([(mean(x + 1e-6 * np.eye(4)[i], w, **settings) - mean(x - 1e-6 * np.eye(4)[i], w, **settings)) / 2e-6 for i in range(4)])
    assert mean.error(x, s, w, **settings) == pytest.approx(float(np.sqrt(np.sum((grad * s) ** 2))), rel=1e-5)
    assert mean.error_kind == "first order"


def test_min_and_max_carry_the_error_of_the_value_they_are():
    assert means.REGISTRY["max"].error([1.0, 5.0, 3.0], [0.1, 0.7, 0.2]) == 0.7
    assert means.REGISTRY["min"].error([1.0, 5.0, 3.0], [0.1, 0.7, 0.2]) == 0.1


def test_a_robust_mean_s_error_is_a_seeded_approximation():
    x, s = np.linspace(9, 11, 25), np.ones(25)
    first = means.REGISTRY["median"].error(x, s)
    assert first == means.REGISTRY["median"].error(x, s)                          # the same twice
    assert 0.15 < first < 0.35                                                    # ~ 1.25 σ/√K = 0.25
    assert means.REGISTRY["median"].error_kind == "approximate"
    for name in ("trimmed", "huber", "tukey", "winsorized", "midhinge", "trimean", "hodges_lehmann", "trimmed_geometric"):
        assert means.REGISTRY[name].error_kind == "approximate", name
    assert 0.1 < means.REGISTRY["huber"].error(x, s) < 0.35


# ── histograms ────────────────────────────────────────────────────────────────────────────────

EDGES = np.linspace(0.0, 10.0, 21)


def blob(centre, width=0.8, area=100.0):
    mid = (EDGES[:-1] + EDGES[1:]) / 2
    f = np.exp(-0.5 * ((mid - centre) / width) ** 2)
    return f / (f * np.diff(EDGES)).sum() * area


def position(f):
    mid, dx = (EDGES[:-1] + EDGES[1:]) / 2, np.diff(EDGES)
    return float((f * dx * mid).sum() / (f * dx).sum())


def test_wasserstein_moves_a_shifted_peak_where_the_bin_wise_mean_smears_it():
    a, b = blob(3.0), blob(7.0)
    bins = means.REGISTRY["linear"]
    smeared = np.array([bins([a[i], b[i]]) for i in range(len(a))])
    moved = means.REGISTRY["wasserstein"](EDGES, [a, b])
    assert (smeared > 0.5 * smeared.max()).sum() > (moved > 0.5 * moved.max()).sum()      # bimodal against one peak
    assert position(moved) == pytest.approx(5.0, abs=0.15)
    assert (moved * np.diff(EDGES)).sum() == pytest.approx(100.0)                          # the linear mean of the yields
    assert (means.REGISTRY["wasserstein"](EDGES, [blob(3.0), blob(7.0, area=300.0)]) * np.diff(EDGES)).sum() == pytest.approx(200.0)
    assert np.argmax(moved) in (9, 10)


def test_wasserstein_weights_and_a_median_across_levels():
    a, b, c = blob(3.0), blob(4.0), blob(8.0)
    assert position(means.REGISTRY["wasserstein"](EDGES, [a, b, c], [1, 1, 8])) > position(means.REGISTRY["wasserstein"](EDGES, [a, b, c]))
    assert position(means.REGISTRY["wasserstein"](EDGES, [a, b, c], loc="median")) < 4.6                 # the outlier member is out-voted


def test_wasserstein_of_identical_histograms_is_that_histogram():
    a = blob(5.0)
    out = means.REGISTRY["wasserstein"](EDGES, [a, a, a])
    assert np.allclose(out, a, rtol=1e-9, atol=1e-9)


def test_wasserstein_keeps_a_gap_a_gap():
    """Two members with mass in the same two places, none between: the barycentre has none between either."""
    f = np.zeros(20)
    f[3:5] = 1.0
    f[14:16] = 1.0
    out = means.REGISTRY["wasserstein"](EDGES, [f, f.copy()])
    assert np.allclose(out, f, atol=1e-9)
    g = np.zeros(20)
    g[5:7] = 1.0
    g[14:16] = 1.0
    both = means.REGISTRY["wasserstein"](EDGES, [f, g])
    assert both[8:13].max() < 1e-9 and both.sum() > 0                          # nothing in the empty middle


def test_scale_aligned_brings_members_of_different_scale_to_the_consensus():
    mid = (EDGES[:-1] + EDGES[1:]) / 2
    a, b = np.exp(-mid / 1.0), np.exp(-mid / 2.0)
    a, b = a / (a * 0.5).sum() * 100, b / (b * 0.5).sum() * 100
    aligned = means.REGISTRY["scale_aligned"](EDGES, [a, b], loc="linear")
    assert (aligned * 0.5).sum() == pytest.approx(100.0)
    consensus = (position(a) + position(b)) / 2
    assert position(aligned) == pytest.approx(consensus, rel=0.05)


@pytest.mark.parametrize("name", ["wasserstein", "scale_aligned"])
def test_an_ensemble_mean_refuses_what_it_cannot_average(name):
    mean = means.REGISTRY[name]
    with pytest.raises(HeimdallError):
        mean(EDGES, [blob(3.0)])                                                  # one histogram
    with pytest.raises(HeimdallError):
        mean(EDGES, [blob(3.0), -blob(4.0)])                                      # a negative density
    with pytest.raises(HeimdallError):
        mean(EDGES, [blob(3.0), np.zeros(20)])                                    # no yield
    with pytest.raises(HeimdallError):
        mean(EDGES[:-1], [blob(3.0), blob(4.0)])                                  # the edges do not fit


def test_scale_aligned_refuses_a_mean_position_at_or_below_zero():
    edges = np.linspace(-5.0, 0.0, 11)
    f = np.ones(10)
    with pytest.raises(HeimdallError):
        means.REGISTRY["scale_aligned"](edges, [f, f * 2])


def test_the_error_of_an_ensemble_mean_is_the_members_relative_error():
    a, b = blob(3.0), blob(4.0)
    sa, sb = 0.1 * a, 0.3 * b
    out = means.REGISTRY["wasserstein"](EDGES, [a, b])
    err = means.REGISTRY["wasserstein"].error(EDGES, [a, b], [sa, sb], result=out)
    populated = (a > 1e-3 * a.max()) & (b > 1e-3 * b.max())
    assert np.allclose(err[populated] / out[populated], 0.2, atol=1e-9)
    assert means.REGISTRY["wasserstein"].error_kind == "approximate"


def test_every_mean_says_what_it_hides_and_how_far_its_error_can_be_trusted():
    for mean in means.REGISTRY.values():
        assert mean.note and mean.guard, mean.name
        assert mean.error_kind in ("exact", "first order", "approximate"), mean.name
        assert mean.kind in ("scalar", "ensemble"), mean.name


def test_an_unknown_mean_lists_the_known():
    with pytest.raises(HeimdallError) as caught:
        means.evaluate("nope", X)
    assert "geometric" in str(caught.value)


# ── the trimmed mean and its error (marginals) ──────────────────────────────────────────────────

def test_the_trimmed_mean_at_no_trim_is_the_mean_and_its_error_s_over_root_n():
    x = [1.0, 2.0, 4.0, 7.0]
    t = means.trimmed_se(x, alpha=0.0)
    assert t.g == 0 and t.n == 4 and t.mean == pytest.approx(3.5)
    assert t.se == pytest.approx(np.std(x, ddof=1) / math.sqrt(4))


def test_the_trimmed_mean_at_its_widest_trim_is_the_median():
    t = means.trimmed_se([5.0, 1.0, 9.0, 3.0, 100.0], alpha=0.4)              # g = ⌊0.4 · 5⌋ = 2: the middle value alone
    assert t.g == 2 and t.mean == 5.0 and math.isnan(t.se)                     # n − 2g = 1 < 2: no error


def test_ten_values_trimmed_by_a_fifth_by_hand():
    """Sorted: 0.2 0.3 0.5 0.7 0.9 1.1 1.4 1.8 2.5 9.0; g = ⌊0.2 · 10⌋ = 2. The mean of the kept six, 0.5 … 1.8: 6.4 / 6. The
    winsorised sample clamps to [0.5, 1.8]: 0.5 ×3, 0.7, 0.9, 1.1, 1.4, 1.8 ×3, mean 1.1, Σ(x − 1.1)² = 1.08 + 0.16 + 0.04 + 0
    + 0.09 + 1.47 = 2.84, s_w = √(2.84 / 9). SE = s_w / ((1 − 2·2/10) √10)."""
    t = means.trimmed_se([0.3, 1.1, 0.7, 2.5, 0.9, 1.4, 0.2, 1.8, 0.5, 9.0, math.nan])     # NaN dropped before n is counted
    assert (t.n, t.g) == (10, 2)
    assert t.mean == pytest.approx(6.4 / 6)
    assert t.se == pytest.approx(math.sqrt(2.84 / 9) / (0.6 * math.sqrt(10)))


def test_two_values_or_fewer_are_not_trimmed_and_a_bad_alpha_is_refused():
    assert [means.trimmed_se([1.0] * n).g for n in (0, 1, 2)] == [0, 0, 0]
    assert math.isnan(means.trimmed_se([]).mean) and math.isnan(means.trimmed_se([2.0]).se)
    pair = means.trimmed_se([1.0, 3.0])
    assert pair.mean == 2.0 and pair.se == pytest.approx(math.sqrt(2) / math.sqrt(2))       # s = √2, over √2
    assert means.trimmed_se([1.0, 2.0, 3.0]).g == 1                              # n ≥ 3: at least one off each end
    for bad in (-0.1, 0.5, 0.7):
        with pytest.raises(HeimdallError, match="trim"):
            means.trimmed_se([1.0, 2.0], alpha=bad)
