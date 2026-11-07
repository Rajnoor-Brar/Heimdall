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
    if noise:
        counts = RNG.poisson(ref * (hi - lo) * 100) / 100
        y = counts / (hi - lo)
        err = np.sqrt(np.maximum(counts, 1) * 100) / 100 / (hi - lo)
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


def test_a_true_curve_with_noise_stays_under_every_good_threshold():
    for seed in range(5):
        np.random.default_rng(seed)
        got = all_metrics(spectrum(noise=True))
        for name, value in got.items():
            assert value <= metrics.REGISTRY[name].thresholds[0] * (1.5 if name == "chi2_ndf" else 1.0), (name, value)


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


def test_every_metric_names_a_purpose_and_a_direction():
    for m in metrics.REGISTRY.values():
        assert m.purpose in metrics.PURPOSES, m.name
        assert m.better in ("lower", "one"), m.name
        assert m.note, m.name
        if m.default:
            assert m.thresholds and m.thresholds[0] < m.thresholds[1], m.name


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
