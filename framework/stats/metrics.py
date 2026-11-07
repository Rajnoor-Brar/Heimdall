"""The metrics: a number for one curve against its page's reference, from Paint's measured bins.

`REGISTRY` maps a name to a `Metric`: its function, the purpose it answers (PURPOSES), which way is better, the
(good, bad) thresholds that normalise it (a value at or under `good` costs nothing; at `bad`, 1), whether it needs a
reference, whether it is on by default, and a note saying what it measures and what it is blind to. A function takes a
`bins.Curve` and returns a float, NaN when the curve has too little to say.

Notation, for the curve y ± σ on the reference's bins (ref, σ_ref), bin width Δx (drawn: log10 x on a log-x page):
    ℓ = ln(max(y, ε·ref) / ref)                         the log ratio, floored so a hole is finite (ε = 0.01)
    σ_ℓ = √((σ / max(y, ε·ref))² + (σ_ref / ref)²)      its error
The formulas were re-derived from first principles and each has a test on a built spectrum (tests/runner/test_stats_metrics.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .bins import Curve

EPS = 0.01        # the floor of the log ratio, as a fraction of the reference
TAU = 0.10        # the model tolerance that sets how much a noisy bin counts in `shape`
TAU0 = 0.01       # keeps one very precise bin from owning the `tilt` regression

#: What a metric answers, in the order the summary and the report show them.
PURPOSES = {
    "compatibility": "Statistical compatibility",
    "normalisation": "Normalisation",
    "shape": "Shape accuracy, bin by bin",
    "similarity": "Shape similarity, as distributions",
    "trend": "Trend",
    "defects": "Local defects",
    "quality": "Monte Carlo quality, without a reference",
}


@dataclass(frozen=True)
class Metric:
    name: str
    fn: Callable[..., float]
    purpose: str
    better: str = "lower"                     # "lower", or "one": closest to 1 (scored by |log10|, as the old ratios)
    thresholds: tuple[float, float] | None = None   # (good, bad); None: none chosen, so it cannot be normalised by default
    needs_reference: bool = True
    default: bool = False
    note: str = ""

    def __call__(self, curve: Curve, **settings) -> float:
        return self.fn(curve, **settings)


# ── the log ratio ─────────────────────────────────────────────────────────────────────────────

def _usable(c: Curve) -> np.ndarray:
    """The bins a ratio can be made on: finite, a positive reference."""
    return np.isfinite(c.y) & np.isfinite(c.ref_y) & (c.ref_y > 0)


def log_ratio(c: Curve, eps: float = EPS) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(ℓ, σ_ℓ, usable) per bin; ℓ and σ_ℓ are NaN where the bin is not usable."""
    use = _usable(c)
    ref = np.where(use, c.ref_y, 1.0)
    y = np.where(use, c.y, 0.0)
    err = np.nan_to_num(c.err, nan=0.0)
    ref_err = np.nan_to_num(c.ref_err, nan=0.0)
    ell = np.log(np.maximum(y, eps * ref) / ref)
    sigma = np.sqrt((err / np.maximum(y, eps * ref)) ** 2 + (ref_err / ref) ** 2)
    return np.where(use, ell, np.nan), np.where(use, sigma, np.nan), use


def centres(c: Curve, mode: str = "mid") -> np.ndarray:
    """Where each bin sits in drawn x: its middle, or (`barycentre`, Lafferty–Wyatt) the centre of gravity of an
    exponential falling at the reference's local rate, which a wide bin of a steep spectrum sits left of its middle."""
    a, b = c.edges
    mid = (a + b) / 2
    if mode == "mid":
        return mid
    if mode != "barycentre":
        raise ValueError(f"centres is 'mid' or 'barycentre', not {mode!r}")
    dx = b - a
    ref = c.ref_y
    nxt = np.append(ref[1:], ref[-1])
    with np.errstate(divide="ignore", invalid="ignore"):
        lam = np.where((ref > 0) & (nxt > 0), -np.log(nxt / ref) / dx, 0.0)
    lam = np.maximum(0.0, np.nan_to_num(lam))
    small = lam * dx < 1e-3
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        exact = a + 1.0 / lam - dx / np.expm1(lam * dx)
    return np.where(small, mid, exact)


# ── the five that are on by default ───────────────────────────────────────────────────────────

def chi2_ndf(c: Curve, **_) -> float:
    """χ²/ndf as Paint counts it: Σ (y − ref)² / (σ² + σ_ref²) over the bins with a nonzero error, per such bin."""
    d = c.y - c.ref_y
    s2 = np.nan_to_num(c.err) ** 2 + np.nan_to_num(c.ref_err) ** 2
    use = (s2 > 0) & np.isfinite(d)
    return float(np.sum(d[use] ** 2 / s2[use]) / use.sum()) if use.any() else math.nan


def norm(c: Curve, eps: float = EPS, **_) -> float:
    """|ln(Σ y·Δx / Σ ref·Δx)|: the yield off by a factor, either way alike (a curve 20 % high and one 1/1.2 low
    are equally wrong). Blind to where the yield goes. A curve with no yield counts as ε of the reference."""
    use = np.isfinite(c.y) & np.isfinite(c.ref_y)
    ref_area = float(np.sum(c.ref_y[use] * c.width[use]))
    if not use.any() or ref_area <= 0:
        return math.nan
    cmp_area = max(float(np.sum(c.y[use] * c.width[use])), eps * ref_area)
    return abs(math.log(cmp_area / ref_area))


def shape(c: Curve, eps: float = EPS, tau: float = TAU, **_) -> float:
    """Σ Δx·s·|ℓ| / Σ Δx, s = τ²/(τ² + σ_ℓ²): the log ratio's mean size over the axis, a noisy bin counted less
    (it cannot be told from a fluctuation) and a wide bin more. Blind to a uniform shift that `norm` carries too."""
    ell, sigma, use = log_ratio(c, eps)
    dx = c.drawn
    use = use & (dx > 0)
    if not use.any():
        return math.nan
    s = tau**2 / (tau**2 + sigma[use] ** 2)
    return float(np.sum(dx[use] * s * np.abs(ell[use])) / np.sum(dx[use]))


def tilt(c: Curve, eps: float = EPS, tau0: float = TAU0, centres_mode: str = "mid", **_) -> float:
    """|slope of ℓ against x| × the axis span: the log ratio's total change across the page, weights
    1/(σ_ℓ² + τ0²). A candidate that decays too fast or too slowly. Blind to a kink; NaN under three usable bins."""
    ell, sigma, use = log_ratio(c, eps)
    x = centres(c, centres_mode)
    use = use & np.isfinite(x)
    if use.sum() < 3:
        return math.nan
    w = 1.0 / (sigma[use] ** 2 + tau0**2)
    xs, ys = x[use], ell[use]
    xbar, ybar = np.sum(w * xs) / np.sum(w), np.sum(w * ys) / np.sum(w)
    var = float(np.sum(w * (xs - xbar) ** 2))
    if var <= 0:
        return math.nan
    return abs(float(np.sum(w * (xs - xbar) * (ys - ybar))) / var) * c.span


def worst(c: Curve, k_floor: int = 3, k_frac: float = 0.10, **_) -> float:
    """The mean of the k largest squared pulls (y − ref)/σ, k = max(3, ⌈0.1 N⌉): a glitch that χ²/ndf spreads over
    all the bins, undiluted. A spike whose own error is as large as itself hides in its σ: `poisson` and `cvar`
    anchor the error to the reference instead (the catalogue)."""
    d = c.y - c.ref_y
    s2 = np.nan_to_num(c.err) ** 2 + np.nan_to_num(c.ref_err) ** 2
    use = (s2 > 0) & np.isfinite(d)
    if not use.any():
        return math.nan
    z2 = np.sort(d[use] ** 2 / s2[use])[::-1]
    k = min(len(z2), max(k_floor, math.ceil(k_frac * len(z2))))
    return float(np.mean(z2[:k]))


# ── today's statistics (the old table's columns), from the same bins ──────────────────────────

def _ratio_terms(c: Curve):
    ref = c.ref_y
    drawn = c.drawn
    use = np.isfinite(c.y) & np.isfinite(ref) & (ref != 0) & (drawn > 0)
    return use, drawn


def rel_abs_area(c: Curve, **_) -> float:
    """Σ |y − ref|·Δx / Σ ref·Δx (the old `rel_abs_area`; the yield-weighted ratio error)."""
    ref_area = float(np.sum(c.ref_y * c.width))
    return float(np.sum(np.abs(c.y - c.ref_y) * c.width)) / ref_area if ref_area else math.nan


def area_ratio(c: Curve, **_) -> float:
    """Σ y·Δx / Σ ref·Δx (the old `area_ratio`)."""
    ref_area = float(np.sum(c.ref_y * c.width))
    return float(np.sum(c.y * c.width)) / ref_area if ref_area else math.nan


def ratio_mean(c: Curve, **_) -> float:
    """The mean of y/ref over the page as drawn (the ratio pad's width: log10 x on a log-x page); the old `ratio_mean`."""
    use, drawn = _ratio_terms(c)
    width = float(np.sum(drawn[use]))
    return float(np.sum(c.y[use] / c.ref_y[use] * drawn[use])) / width if width else math.nan


def ratio_dev(c: Curve, **_) -> float:
    """The mean of |y/ref − 1| over the page as drawn; the old `ratio_dev`."""
    use, drawn = _ratio_terms(c)
    width = float(np.sum(drawn[use]))
    return float(np.sum(np.abs(c.y[use] / c.ref_y[use] - 1) * drawn[use])) / width if width else math.nan


REGISTRY: dict[str, Metric] = {m.name: m for m in (
    Metric("chi2_ndf", chi2_ndf, "compatibility", thresholds=(1.0, 3.0), default=True,
           note="reduced χ² as Paint counts it; blind to a bin whose own error is as large as its excess"),
    Metric("norm", norm, "normalisation", thresholds=(0.02, 0.15), default=True,
           note="|ln| of the yield ratio; blind to where the yield goes"),
    Metric("shape", shape, "shape", thresholds=(0.02, 0.15), default=True,
           note="mean |ln ratio| over the axis, a noisy bin counted less; shares a uniform shift with norm"),
    Metric("tilt", tilt, "trend", thresholds=(0.03, 0.25), default=True,
           note="the ratio's total change across the page (weighted slope × span); blind to a kink"),
    Metric("worst", worst, "defects", thresholds=(2.0, 9.0), default=True,
           note="the mean of the k largest squared pulls; a spike with an error as big as itself hides in it"),
    Metric("rel_abs_area", rel_abs_area, "shape",
           note="the old column: Σ|y−ref|Δx / Σ ref Δx. Moves with ratio_dev (collinear)"),
    Metric("area_ratio", area_ratio, "normalisation", better="one",
           note="the old column: yield over reference yield. Moves with ratio_mean (collinear)"),
    Metric("ratio_mean", ratio_mean, "normalisation", better="one",
           note="the old column: the ratio pad's mean ratio"),
    Metric("ratio_dev", ratio_dev, "shape",
           note="the old column: the ratio pad's mean |ratio − 1|"),
)}


def evaluate(name: str, curve: Curve, **settings) -> float:
    """metric `name` of `curve`; an unknown name is an error that lists the known ones."""
    from runner.errors import HeimdallError
    if name not in REGISTRY:
        raise HeimdallError(f"no metric '{name}'", hint="metrics: " + ", ".join(REGISTRY))
    return REGISTRY[name](curve, **settings)
