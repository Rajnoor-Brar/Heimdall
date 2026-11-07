"""The metrics (framework/stats/metrics.py) on built spectra: each defect raises its own metric most, and a true curve
with Poisson noise stays under every `good` threshold. The old table's columns equal statstable's on a hand-made page."""

from __future__ import annotations

import math

import numpy as np
import pytest

from runner import statstable
from runner.errors import HeimdallError
from stats import bins, metrics

N = 40
RNG = np.random.default_rng(20261107)


def spectrum(*, scale=1.0, tilt=0.0, bump=None, hole=None, noise=False, logx=False) -> bins.Curve:
    """A falling exponential reference, 40 bins over [0, 8] (log x: [1, 1000]), and a curve made from it."""
    edges = np.geomspace(1.0, 1000.0, N + 1) if logx else np.linspace(0.0, 8.0, N + 1)
    lo, hi = edges[:-1], edges[1:]
    x = (lo + hi) / 2
    u = (x - x.min()) / (x.max() - x.min())
    ref = 1000.0 * np.exp(-3.0 * u) * (hi - lo)
    ref = ref / (hi - lo)                                               # a density, as the curves are
    ref_err = 0.02 * ref
    y = ref * scale * np.exp(tilt * (u - 0.5))
    if bump is not None:
        y[bump[0]] *= bump[1]
    if hole is not None:
        y[hole] = 0.0
    err = 0.02 * np.maximum(y, 0.01 * ref)
    if noise:                                                           # two independent samples of one truth
        sample = lambda: RNG.poisson(ref * (hi - lo) * 100)
        raw_r, raw = sample(), sample()
        ref, ref_err = raw_r / 100 / (hi - lo), np.sqrt(np.maximum(raw_r, 1)) / 100 / (hi - lo)
        y, err = raw / 100 / (hi - lo), np.sqrt(np.maximum(raw, 1)) / 100 / (hi - lo)
    return bins.Curve(lo, hi, y, err, ref, ref_err, logx=logx)


def all_metrics(curve: bins.Curve) -> dict[str, float]:
    return {name: metrics.REGISTRY[name](curve) for name in metrics.REGISTRY if metrics.REGISTRY[name].default}


def good(name: str) -> float:
    return metrics.REGISTRY[name].thresholds[0]


def test_the_curve_is_its_own_reference_costs_nothing():
    c = spectrum()
    c = bins.Curve(c.lo, c.hi, c.ref_y, c.ref_err, c.ref_y, c.ref_err)
    for name, value in all_metrics(c).items():
        assert value == pytest.approx(0, abs=1e-9), name


def test_twenty_percent_high_is_a_normalisation_defect():
    got = all_metrics(spectrum(scale=1.2))
    assert got["norm"] == pytest.approx(math.log(1.2), rel=0.05)
    assert got["norm"] > metrics.REGISTRY["norm"].thresholds[1]            # worse than `bad`
    assert got["tilt"] < good("tilt")                                       # not a tilt: the ratio is flat
    # and it is exactly as bad the other way round
    assert all_metrics(spectrum(scale=1 / 1.2))["norm"] == pytest.approx(got["norm"], rel=0.05)


def test_a_tilt_is_found_by_tilt_and_not_by_norm():
    got = all_metrics(spectrum(tilt=0.6))
    assert got["tilt"] == pytest.approx(0.6, rel=0.05)                      # the ratio changes by e^0.6 across the page
    assert got["tilt"] > metrics.REGISTRY["tilt"].thresholds[1]
    assert got["norm"] < metrics.REGISTRY["norm"].thresholds[1]             # the yield is nearly right


def test_one_bin_times_twenty_is_a_defect_for_worst():
    got = all_metrics(spectrum(bump=(N // 3, 20.0)))
    assert got["worst"] > metrics.REGISTRY["worst"].thresholds[1]
    assert got["worst"] > 20 * all_metrics(spectrum(scale=1.01))["worst"]
    assert got["tilt"] < metrics.REGISTRY["tilt"].thresholds[1]             # one bin does not make a trend


def test_one_bin_zero_is_finite_and_found():
    got = all_metrics(spectrum(hole=N // 2))
    assert all(math.isfinite(v) for v in got.values())
    assert got["worst"] > good("worst")
    assert got["shape"] > good("shape") or got["worst"] > metrics.REGISTRY["worst"].thresholds[1]


def true_curves(n=60, seed=1000):
    global RNG
    out = []
    for i in range(n):
        RNG = np.random.default_rng(seed + i)
        out.append(spectrum(noise=True))
    return out


QUALITY = ("n_eff", "holes", "r_int", "chi2_smooth", "r2_ln")          # no reference needed


def scored(m):
    return m.thresholds is not None and not m.pool and (m.needs_reference or m.name in QUALITY)


def test_a_true_curve_with_noise_costs_almost_nothing_under_every_metric():
    """A candidate that is the reference's truth, as noisy as the reference (60 draws of 40 bins): the median cost is
    under 5 % of the way from good to bad and the 90th percentile under half. The thresholds were set on this."""
    curves = true_curves()
    for m in metrics.REGISTRY.values():
        if not scored(m):
            continue
        losses = np.array([m.loss(m(c)) for c in curves])
        assert np.nanmedian(losses) <= 0.05, (m.name, np.nanmedian(losses))
        assert np.nanpercentile(losses, 90) <= 0.5, (m.name, np.nanpercentile(losses, 90))


def test_log_x_changes_the_drawn_width_not_the_yield():
    lin, log = spectrum(scale=1.2), spectrum(scale=1.2, logx=True)
    assert log.drawn.sum() == pytest.approx(3.0)                            # log10(1000) decades
    assert lin.drawn.sum() == pytest.approx(8.0)
    assert metrics.norm(lin) == pytest.approx(metrics.norm(log), rel=0.05)


def test_a_curve_with_no_reference_bins_has_nothing_to_say():
    c = spectrum()
    empty = bins.Curve(c.lo, c.hi, c.y, c.err, np.zeros(N), np.zeros(N))
    assert math.isnan(metrics.shape(empty)) and math.isnan(metrics.tilt(empty)) and math.isnan(metrics.norm(empty))


def test_tilt_needs_three_usable_bins():
    c = spectrum(tilt=0.5)
    two = bins.Curve(c.lo[:2], c.hi[:2], c.y[:2], c.err[:2], c.ref_y[:2], c.ref_err[:2])
    assert math.isnan(metrics.tilt(two))


def test_the_barycentre_of_a_steep_wide_bin_sits_left_of_its_middle():
    edges = np.array([0.0, 1.0, 4.0])
    ref = np.array([100.0, 100.0 * math.exp(-4.0)])                         # λ = ln(ref0/ref1)/Δx per the next bin
    c = bins.Curve(edges[:-1], edges[1:], ref, 0.1 * ref, ref, 0.1 * ref)
    assert metrics.centres(c, "barycentre")[0] < metrics.centres(c, "mid")[0]
    with pytest.raises(ValueError):
        metrics.centres(c, "median")


def test_an_unknown_metric_lists_the_known():
    with pytest.raises(HeimdallError) as caught:
        metrics.evaluate("nope", spectrum())
    assert "chi2_ndf" in str(caught.value)


def test_the_old_columns_are_statstables_on_the_same_bins(tmp_path):
    """rel_abs_area, area_ratio, ratio_mean, ratio_dev and chi2_ndf, from the bins, are what Paint's totals make."""
    for logx in (False, True):
        c = spectrum(scale=1.1, tilt=0.3, bump=(7, 2.0), logx=logx)
        rows = list(zip(c.lo, c.hi, c.y, c.err, c.ref_y, c.ref_err))
        w = c.width
        totals = dict(ref_area=float(np.sum(c.ref_y * w)), cmp_area=float(np.sum(c.y * w)),
                      abs_area=float(np.sum(np.abs(c.y - c.ref_y) * w)))
        ratio = c.y / c.ref_y
        totals.update(ratio_area=float(np.sum(np.abs(ratio - 1) * c.drawn)), ratio_sum=float(np.sum(ratio * c.drawn)),
                      ratio_width=float(np.sum(c.drawn)))
        s2 = c.err**2 + c.ref_err**2
        want = {
            "rel_abs_area": totals["abs_area"] / totals["ref_area"],
            "area_ratio": totals["cmp_area"] / totals["ref_area"],
            "ratio_mean": totals["ratio_sum"] / totals["ratio_width"],
            "ratio_dev": totals["ratio_area"] / totals["ratio_width"],
            "chi2_ndf": float(np.sum((c.y - c.ref_y) ** 2 / s2) / len(rows)),
        }
        for name, value in want.items():
            assert metrics.REGISTRY[name](c) == pytest.approx(value, rel=1e-12), (name, logx)


# ── the opt-in catalogue ──────────────────────────────────────────────────────────────────────

def loss(name: str, curve: bins.Curve, **settings) -> float:
    m = metrics.REGISTRY[name]
    return m.loss(m(curve, **settings))


def flat(n=N, ref=10.0, ref_err=1.0, y=None, err=None, width=1.0, logx=False) -> bins.Curve:
    """n equal bins with the same reference value, the curve y (default: the reference)."""
    lo = np.arange(n, dtype=float) * width + (1.0 if logx else 0.0)
    ref_a = np.full(n, ref)
    y_a = ref_a.copy() if y is None else np.asarray(y, dtype=float)
    return bins.Curve(lo, lo + width, y_a, np.full(n, ref_err) if err is None else np.asarray(err, dtype=float),
                      ref_a, np.full(n, ref_err), logx=logx)


def test_the_poisson_deviance_of_one_bin_by_hand():
    """n_c = 12 against n_r = 10, one count per unit (σ_ref = √(ref/Δx), so s = 1): 2 [2 + 10 ln(10/12)]."""
    c = flat(n=1, ref=10.0, ref_err=math.sqrt(10.0), y=[12.0], err=[1.0])
    d2, use = metrics.deviance(c)
    assert use[0] and d2[0] == pytest.approx(2 * (2 + 10 * math.log(10 / 12)))
    assert metrics.poisson(c) == pytest.approx(d2[0])


def test_the_deviance_floor_is_half_an_unweighted_count():
    """A hole in a reference bin worth s = 100 counts per unit of content: n_c is floored at 0.5/s, so the bin costs
    2 s [0.005 − 10 + 10 ln(10/0.005)], a number and not infinity."""
    c = flat(n=1, ref=10.0, ref_err=1.0, y=[0.0], err=[0.0])          # (ref/σ)² / (ref·Δx) = 100/10 = 10
    s = (10.0 / 1.0) ** 2 / 10.0
    n_c = 0.5 / s
    want = 2 * s * (n_c - 10 + 10 * math.log(10 / n_c))
    assert metrics.deviance(c)[0][0] == pytest.approx(want)
    assert math.isfinite(want)


def test_a_reference_bin_with_no_content_costs_twice_the_curve_floor():
    c = flat(n=1, ref=0.0, ref_err=0.0, y=[3.0], err=[0.1])
    assert metrics.deviance(c)[0][0] == pytest.approx(2 * 3.0)       # s = 1, n_r = 0: 2 n_c


def test_chi2_z_is_wilson_hilferty():
    """40 bins each with a squared pull of 2: χ²/ndf = 2 and Z = (2^⅓ − (1 − 2/360)) / √(2/360)."""
    sigma = math.sqrt(1.0 + 1.0)                                     # σ² + σ_ref² with both errors 1
    c = flat(n=40, ref=10.0, ref_err=1.0, y=np.full(40, 10.0 + math.sqrt(2) * sigma), err=np.full(40, 1.0))
    assert metrics.chi2_ndf(c) == pytest.approx(2.0)
    a = 2 / 360
    assert metrics.chi2_z(c) == pytest.approx((2 ** (1 / 3) - (1 - a)) / math.sqrt(a))
    assert metrics.chi2_z(c) == pytest.approx(3.57, abs=0.01)


def test_chi2_z_is_one_sided():
    c = spectrum()                                                    # the curve a few percent off, errors 2 %: χ² under 1
    c = bins.Curve(c.lo, c.hi, c.ref_y * 1.001, c.err, c.ref_y, c.ref_err)
    assert metrics.chi2_z(c) < 0 and metrics.REGISTRY["chi2_z"].loss(metrics.chi2_z(c)) == 0


def test_a_yield_off_by_twenty_percent_costs_the_yield_and_ratio_metrics_and_not_the_shape_ones():
    c = spectrum(scale=1.2)
    for name in ("wmape_yield", "rel_abs_area", "area_ratio", "ratio_mean", "wmape_axis", "ratio_dev", "poisson", "chi2_z"):
        assert loss(name, c) > 0.7, name
    for name in ("js", "ad", "roughness", "rho1", "r_int"):
        assert loss(name, c) == pytest.approx(0, abs=1e-6), name        # a shift is invisible to them by design
    assert metrics.js(c) == pytest.approx(0, abs=1e-12) and metrics.ad(c) == pytest.approx(0, abs=1e-12)


def test_a_tilt_costs_the_trend_and_the_shape_distances_and_not_roughness():
    c = spectrum(tilt=0.6)
    assert loss("rho1", c) > 1.0                                      # one sign, then the other, across the page
    assert loss("js", c) > 0.1 and loss("ad", c) > 0.4
    assert loss("roughness", c) == pytest.approx(0, abs=1e-6)         # a straight tilt has no second difference
    assert metrics.rho1(spectrum(scale=1.2)) < 0.35                   # a uniform shift has no trend once its mean is gone


def test_one_bin_times_twenty_costs_the_defect_metrics_and_the_intrinsic_ones():
    c = spectrum(bump=(N // 3, 20.0))
    for name in ("cvar", "roughness", "r_int", "chi2_smooth", "js", "ad", "L4", "poisson"):
        assert loss(name, c) >= 1.0, name
    assert loss("rho1", c) < 0.1                                      # an isolated spike has no neighbour like it
    assert loss("tail", c) == pytest.approx(0, abs=1e-6)              # and it is not in the tail


def test_one_bin_zero_costs_the_hole_metrics():
    c = spectrum(hole=N // 2)
    assert metrics.holes(c) == pytest.approx(1 / N)
    for name in ("cvar", "roughness", "r_int", "chi2_smooth", "L4"):
        assert loss(name, c) >= 1.0, name
    assert loss("holes", c) == pytest.approx((1 / N) / 0.10)


def test_a_tail_excess_is_found_by_tail_and_pooled():
    c = spectrum()
    y = c.y.copy()
    y[-8:] *= 1.15
    c = bins.Curve(c.lo, c.hi, y, c.err, c.ref_y, c.ref_err)
    assert metrics.tail(c) > metrics.REGISTRY["tail"].thresholds[1]
    clean = spectrum()
    one = clean.y.copy()
    one[-1] *= 1.04                                                    # one bin 4 % high is within its errors
    assert metrics.tail(bins.Curve(c.lo, c.hi, one, c.err, c.ref_y, c.ref_err)) < metrics.REGISTRY["tail"].thresholds[0]


def test_the_tail_is_the_last_bins_when_the_reference_has_too_few_past_ninety_percent():
    c = flat(n=12, y=[10.0] * 6 + [12.0] * 6)                          # a flat reference: 90 % is bin 11, one bin
    # the last max(2, 12 // 4) = 3 bins are the tail, so only they count: 3 bins of +2 with σ² = 2
    assert metrics.tail(c) == pytest.approx(3 * 2.0 / math.sqrt(3 * 2.0))


def test_L4_counts_an_outlier_far_more_than_a_fluctuation():
    quiet = flat(n=20, y=[10.0 * 1.05] * 20)
    spike = flat(n=20, y=[10.0] * 19 + [100.0])
    assert metrics.L4(quiet) == pytest.approx(math.log(1.05))
    assert metrics.L4(spike) > 10 * metrics.L4(quiet)


def test_wmape_axis_counts_every_unit_of_the_axis_alike():
    narrow = np.array([1.0] * 30 + [10.0] * 3)                        # 30 narrow bins, then 3 wide
    lo = np.concatenate(([0.0], np.cumsum(narrow)[:-1]))
    ref = np.full(33, 10.0)
    y = ref.copy()
    y[-3:] *= 1.25
    c = bins.Curve(lo, lo + narrow, y, np.full(33, 0.1), ref, np.full(33, 0.1))
    assert metrics.wmape_axis(c) == pytest.approx(0.25 * 30 / 60)       # 30 of 60 units are 25 % off
    assert metrics.wmape_yield(c) == pytest.approx(metrics.rel_abs_area(c))


def test_rho1_separates_scatter_from_a_systematic_with_the_same_chi2():
    sign = np.tile([1.0, -1.0], 20)
    scatter = flat(n=40, y=10 + sign * 1.0)
    block = flat(n=40, y=10 + np.repeat([1.0, -1.0], 20) * 1.0)
    assert metrics.chi2_ndf(scatter) == pytest.approx(metrics.chi2_ndf(block))
    assert metrics.rho1(scatter) < -0.9 and metrics.rho1(block) > 0.9
    assert math.isnan(metrics.rho1(flat(n=7, y=[11.0] * 7)))


def test_cvar_k_is_settable_and_a_spike_counts_in_full_whatever_its_own_error():
    c = flat(n=40, y=[10.0] * 39 + [200.0], err=[1.0] * 39 + [200.0])  # an MC spike whose error is as large as itself
    assert metrics.worst(c) < 1.0                                       # excused by its own error bar
    assert metrics.cvar(c, k=1) > 1000
    assert metrics.cvar(c, k=1) > metrics.cvar(c, k=3) > metrics.cvar(c)


def test_roughness_ignores_a_shift_and_a_line_and_not_a_kink():
    x = np.arange(20, dtype=float)
    ref = np.full(20, 10.0)
    lin = bins.Curve(x, x + 1, ref * np.exp(0.5 + 0.1 * (x + 0.5)), ref * 0.01, ref, ref * 0.01)
    assert metrics.roughness(lin) == pytest.approx(0, abs=1e-12)
    kink = bins.Curve(x, x + 1, ref * np.exp(0.2 * np.abs(x - 9.5)), ref * 0.01, ref, ref * 0.01)
    assert metrics.roughness(kink) > 0.0


def test_the_barycentre_of_a_wide_bin_moves_the_trend_the_right_way():
    """An exact exponential tilt, y/ref = e^(βx) per unit x on coarse bins: with the bin contents integrated, the
    ratio of contents is e^(β·barycentre-ish) and the barycentre reading is closer to β than the middle's."""
    lam, beta, edges = 1.0, 0.1, np.array([0.0, 1.0, 2.0, 4.0, 8.0, 14.0])
    lo, hi = edges[:-1], edges[1:]
    integral = lambda k: (np.exp(-k * lo) - np.exp(-k * hi)) / k            # ∫ e^(−k x) dx over each bin
    ref = integral(lam) / (hi - lo)
    y = integral(lam - beta) / (hi - lo)                                    # density e^(−(λ−β) x): ratio e^(βx)
    c = bins.Curve(lo, hi, y, y * 0.001, ref, ref * 0.001)
    want = beta * (hi[-1] - lo[0])
    mid, bary = metrics.tilt(c, centres_mode="mid"), metrics.tilt(c, centres_mode="barycentre")
    assert abs(bary - want) < abs(mid - want)
    assert bary == pytest.approx(want, rel=0.05)


def test_n_eff_flags_one_huge_weight():
    c = spectrum()
    assert metrics.n_eff(c) > metrics.REGISTRY["n_eff"].thresholds[0]
    y, err = c.y.copy(), c.err.copy()
    y[10] *= 1000
    err[10] = y[10]
    spiky = bins.Curve(c.lo, c.hi, y, err, c.ref_y, c.ref_err)
    assert metrics.n_eff(spiky) < 3 and loss("n_eff", spiky) >= 1.0
    assert metrics.REGISTRY["n_eff"].loss(1e6) == 0


def test_the_hole_fraction_leaves_a_tail_of_zeros_alone():
    c = spectrum()
    y = c.y.copy()
    y[-5:] = 0.0
    assert metrics.holes(bins.Curve(c.lo, c.hi, y, c.err, c.ref_y, c.ref_err)) == 0.0


def test_the_tail_fit_finds_the_rate_and_how_straight_it_is():
    c = spectrum()
    assert metrics.tail_rate(c) == pytest.approx(3.0 / 7.8, rel=1e-9)    # ref = 1000 e^(−3u), u over the middles 0.1 to 7.9
    assert metrics.r2_ln(c) == pytest.approx(0, abs=1e-9)
    y = c.y.copy()
    y[-10:] *= np.exp(-0.8 * np.arange(10) ** 2 / 20)                    # a tail that bends
    bent = bins.Curve(c.lo, c.hi, y, c.err, c.ref_y, c.ref_err)
    assert metrics.r2_ln(bent) > metrics.r2_ln(c) + 0.01
    assert metrics.REGISTRY["lambda"].better == "none" and metrics.REGISTRY["lambda"].thresholds is None


def test_js_and_ad_are_blind_to_normalisation_and_js_is_bounded():
    a, b = spectrum(scale=1.0), spectrum(scale=7.0)
    assert metrics.js(b) == pytest.approx(0, abs=1e-12) and metrics.ad(b) == pytest.approx(0, abs=1e-12)
    far = flat(n=10, y=[10.0] * 5 + [0.0] * 5, err=[0.1] * 10)
    far = bins.Curve(far.lo, far.hi, np.array([10.0] * 5 + [0.0] * 5), far.err, np.array([0.0] * 5 + [10.0] * 5), far.ref_err)
    assert metrics.js(far) == pytest.approx(1.0)                         # disjoint shapes: the bound, in bits


def test_ad_counts_a_gap_in_the_tail_more_than_cramer_von_mises_does():
    """AD is the Cramér–von Mises sum with the weight 1/(F(1−F)): the same cumulative gap, made deep in the tail,
    counts several times more relative to the plain sum than one made in the bulk. JS, by mass, finds the bulk's."""
    ref = np.exp(-0.5 * np.arange(30))
    lo = np.arange(30, dtype=float)

    def cvm(c):
        p, q = c.y * c.width, c.ref_y * c.width
        fc, fr = np.cumsum(p / p.sum())[:-1], np.cumsum(q / q.sum())[:-1]
        return float(np.sum((fc - fr) ** 2 * (q / q.sum())[:-1]))

    def with_error(at):
        y = ref.copy()
        y[at] *= 2.0
        return bins.Curve(lo, lo + 1, y, y * 0.01, ref, ref * 0.01)

    bulk, deep = with_error(0), with_error(20)
    assert metrics.ad(deep) / cvm(deep) > 5 * metrics.ad(bulk) / cvm(bulk)
    assert metrics.js(bulk) > metrics.js(deep)


def test_consensus_is_the_shape_against_the_pool_s_median():
    base = spectrum()
    pool = [bins.Curve(base.lo, base.hi, base.ref_y * f, base.err, base.ref_y, base.ref_err) for f in (1.0, 1.0, 1.0, 1.0, 1.3)]
    odd = metrics.REGISTRY["consensus"](pool[-1], pool=pool)
    fine = metrics.REGISTRY["consensus"](pool[0], pool=pool)
    assert fine == pytest.approx(0, abs=1e-12) and odd == pytest.approx(math.log(1.3), rel=0.1)
    assert math.isnan(metrics.REGISTRY["consensus"](pool[0], pool=pool[:2])) and math.isnan(metrics.REGISTRY["consensus"](pool[0]))
    assert metrics.REGISTRY["consensus"].pool and not metrics.REGISTRY["consensus"].needs_reference


def test_the_loss_is_hinged_and_works_for_every_direction():
    m = metrics.REGISTRY
    assert m["norm"].loss(0.02) == 0 and m["norm"].loss(0.085) == pytest.approx(0.5) and m["norm"].loss(0.15) == pytest.approx(1)
    assert m["n_eff"].loss(1000) == 0 and m["n_eff"].loss(550) == pytest.approx(0.5) and m["n_eff"].loss(100) == pytest.approx(1)
    assert m["area_ratio"].loss(1.0) == 0 and m["area_ratio"].loss(1.2) == pytest.approx(m["area_ratio"].loss(1 / 1.2), rel=0.03)
    assert m["norm"].loss(0.3) > 1                                       # linear beyond bad, not capped
    assert math.isnan(m["norm"].loss(math.nan))
    assert m["norm"].loss(0.1, thresholds=(0.0, 0.2)) == pytest.approx(0.5)   # a setting overrides the registry's
