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

#: What each purpose asks, as the summary says it: a sentence on the question, and what is not answered by it.
ASKS = {
    "compatibility": "Is the curve statistically compatible with the reference, bin errors counted? Near the good threshold: yes; "
                     "past bad: no. It says nothing of where, and a curve with large errors is compatible with anything.",
    "normalisation": "Does the curve hold the reference's yield? An overall factor, whatever the shape; blind to where the yield goes.",
    "shape": "How far is the curve from the reference, bin by bin, once its normalisation is set aside? Counts the "
             "whole axis, the tails as much as the peak.",
    "similarity": "Are the two distributions alike as shapes: the share of yield per bin, normalisation removed.",
    "trend": "Does the curve drift away from the reference across the axis (a slope or a curvature in the ratio)?",
    "defects": "Is there a bin, or a few, badly off: a spike or a hole the averages hide?",
    "quality": "Is the curve itself sound as a Monte Carlo histogram, with no reference: smooth, filled, enough events?",
}

#: Each metric's name where it is shown (a column, a panel, a section); the name itself where none is given.
TITLES = {
    "chi2_ndf": "χ²/ndf", "chi2_z": "χ² as Z", "poisson": "Poisson deviance", "tail": "tail Z", "norm": "norm |ln yield ratio|",
    "area_ratio": "area / reference", "ratio_mean": "mean ratio", "wmape_yield": "yield-weighted error",
    "shape": "shape |ln ratio|", "ratio_dev": "mean |ratio − 1|", "rel_abs_area": "|Δ| / reference", "wmape_axis": "axis-weighted error",
    "L4": "L4 |ln ratio|", "consensus": "shape vs consensus", "js": "Jensen–Shannon", "ad": "Anderson–Darling", "tilt": "tilt",
    "rho1": "lag-1 autocorrelation", "worst": "worst bins", "cvar": "worst deviances", "roughness": "roughness",
    "n_eff": "effective events", "holes": "holes", "r_int": "ln roughness", "chi2_smooth": "smoothness χ²", "r2_ln": "tail 1 − R²",
    "lambda": "tail decay rate",
}


def title_of(name: str) -> str:
    return TITLES.get(name, name)


#: The formulas of the columns Paint made first, as LaTeX (math mode), i running over the compared bins: a report's
#: "How the numbers are made" sets them; a metric without one is described by its note.
FORMULAS = {
    "chi2_ndf": r"\chi^2/\mathrm{ndf} = \frac{1}{\mathrm{ndf}} \sum_i "
                r"\frac{(y_i - y_{\mathrm{ref},i})^2}{\sigma_i^2 + \sigma_{\mathrm{ref},i}^2}",
    "rel_abs_area": r"\frac{|\Delta|}{\mathrm{reference}} = "
                    r"\frac{\sum_i |y_i - y_{\mathrm{ref},i}|\,\Delta x_i}{\sum_i y_{\mathrm{ref},i}\,\Delta x_i}",
    "area_ratio": r"\frac{\mathrm{area}}{\mathrm{reference}} = \frac{\sum_i y_i\,\Delta x_i}{\sum_i y_{\mathrm{ref},i}\,\Delta x_i}",
    "ratio_mean": r"\mathrm{mean\ ratio} = \frac{\sum_i (y_i / y_{\mathrm{ref},i})\,\Delta x_i}{\sum_i \Delta x_i}",
    "ratio_dev": r"\mathrm{mean}\,|\mathrm{ratio} - 1| = "
                 r"\frac{\sum_i |y_i / y_{\mathrm{ref},i} - 1|\,\Delta x_i}{\sum_i \Delta x_i}",
}


@dataclass(frozen=True)
class Metric:
    name: str
    fn: Callable[..., float]
    purpose: str
    better: str = "lower"                     # "lower"; "higher"; "one": closest to 1, scored by |log10|, as the old ratios; "none": a descriptor
    thresholds: tuple[float, float] | None = None   # (good, bad), in the scored quantity; None: none chosen, so it cannot be normalised by default
    needs_reference: bool = True
    default: bool = False
    note: str = ""
    why: str = ""                             # where the thresholds come from
    pool: bool = False                        # needs the page's other curves (`pool=`): its value depends on who else is on the page

    def __call__(self, curve: Curve, **settings) -> float:
        return self.fn(curve, **settings)

    def scored(self, value: float) -> float:
        """The quantity the thresholds are on: |log10 value| for "one", else the value."""
        if self.better == "one":
            return abs(math.log10(value)) if value > 0 else math.inf
        return value

    def loss(self, value: float, thresholds: tuple[float, float] | None = None) -> float:
        """The hinged penalty: 0 at or inside `good`, 1 at `bad`, linear between and beyond (lower or higher alike)."""
        good, bad = thresholds or self.thresholds or (math.nan, math.nan)
        m = self.scored(value)
        return max(0.0, (m - good) / (bad - good)) if math.isfinite(m) else (math.nan if math.isnan(m) else math.inf)


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


def centres(c: Curve, mode: str = "mid", of: np.ndarray | None = None) -> np.ndarray:
    """Where each bin sits in drawn x: its middle, or (`barycentre`, Lafferty–Wyatt) the centre of gravity of an
    exponential through the bin at the local rate of `of` (the reference by default), which a wide bin of a steep
    spectrum sits left of its middle. The rate is ln(f_i / f_(i+1)) over the distance between the middles; the last
    bin takes its neighbour's; where it cannot be told (a value not positive) the middle stands."""
    a, b = c.edges
    mid = (a + b) / 2
    if mode == "mid":
        return mid
    if mode != "barycentre":
        raise ValueError(f"centres is 'mid' or 'barycentre', not {mode!r}")
    f = c.ref_y if of is None else of
    dx = b - a
    if len(f) < 2:
        return mid
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = np.where((f[:-1] > 0) & (f[1:] > 0), -np.log(f[1:] / f[:-1]) / (mid[1:] - mid[:-1]), 0.0)
    lam = np.nan_to_num(np.append(rate, rate[-1]))
    lam = np.clip(lam, -50.0 / np.maximum(dx, 1e-300), 50.0 / np.maximum(dx, 1e-300))
    small = np.abs(lam * dx) < 1e-3
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        exact = a + 1.0 / lam - dx / np.expm1(lam * dx)
    return np.where(small | ~np.isfinite(exact), mid, exact)


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


# ── the opt-in catalogue ──────────────────────────────────────────────────────────────────────

def _pulls2(c: Curve):
    """Per bin: d = y − ref, s² = σ² + σ_ref², and the bins where a pull exists (s² > 0)."""
    d = c.y - c.ref_y
    s2 = np.nan_to_num(c.err) ** 2 + np.nan_to_num(c.ref_err) ** 2
    return d, s2, (s2 > 0) & np.isfinite(d)


def chi2_z(c: Curve, **_) -> float:
    """χ²/ndf as a number of standard deviations (Wilson–Hilferty): Z = ((χ²/ν)^(1/3) − (1 − 2/9ν)) / √(2/9ν), ν the bins
    counted. One-sided as the plain χ²/ndf is: a fit better than expected comes out negative, which costs nothing.
    Puts a 12-bin page and a 120-bin page on one scale, which χ²/ndf does not (its spread shrinks as 1/√ν)."""
    value = chi2_ndf(c)
    nu = int(np.sum(_pulls2(c)[2]))
    if not nu or math.isnan(value):
        return math.nan
    a = 2.0 / (9.0 * nu)
    return float(((value) ** (1.0 / 3.0) - (1.0 - a)) / math.sqrt(a))


def deviance(c: Curve) -> tuple[np.ndarray, np.ndarray]:
    """(d², usable) per bin: the Poisson deviance of the curve against the reference, anchored to the reference.
    With n = y·Δx the weighted content, s = (ref/σ_ref)²/(ref·Δx) the unweighted counts per unit of weighted content
    (1 where σ_ref is not known), the deviance of s·n counts is 2 s [n_c − n_r + n_r ln(n_r/n_c)], n_c floored at the
    Jeffreys 0.5 counts, that is 0.5/s of weighted content (the note put the floor in weighted units, which is only
    right where s = 1). A reference bin with no content has 2 s n_c. The anchor is the reference's: a spike with an
    error as large as itself cannot excuse itself."""
    use = np.isfinite(c.y) & np.isfinite(c.ref_y) & (c.width > 0)
    dx = np.where(use, c.width, 1.0)
    n_r = np.where(use, np.maximum(c.ref_y, 0.0), 0.0) * dx
    ref_err = np.nan_to_num(c.ref_err)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where((n_r > 0) & (ref_err > 0), (c.ref_y / ref_err) ** 2 / n_r, 1.0)
    s = np.where(np.isfinite(s) & (s > 0), s, 1.0)
    n_c = np.maximum(np.where(use, np.maximum(c.y, 0.0), 0.0) * dx, 0.5 / s)
    with np.errstate(divide="ignore", invalid="ignore"):
        log = np.where(n_r > 0, n_r * np.log(n_r / n_c), 0.0)
    d2 = np.maximum(0.0, 2.0 * s * (n_c - n_r + log))
    return np.where(use, d2, np.nan), use


def poisson(c: Curve, **_) -> float:
    """The mean Poisson deviance per bin against the reference (Baker–Cousins), anchored to the reference: χ²/ndf that
    stays right in low-count tail bins and cannot be fooled by a spike's own error bar (`deviance`)."""
    d2, use = deviance(c)
    return float(np.mean(d2[use])) if use.any() else math.nan


def tail(c: Curve, from_cdf: float = 0.90, **_) -> float:
    """|Z| of the tail's pooled excess: |Σ (y − ref)Δx| / √Σ (σ² + σ_ref²)Δx² over the bins whose left edge is past
    `from_cdf` of the reference yield (at least the last max(2, N/4) bins when fewer than two are). Pooling K wide
    noisy bins gains √K, so a systematic tail excess shows that no one bin does; blind to an excess that changes
    sign inside the tail."""
    use = np.isfinite(c.y) & np.isfinite(c.ref_y)
    if use.sum() < 2:
        return math.nan
    y, r, e, re, dx = c.y[use], c.ref_y[use], np.nan_to_num(c.err[use]), np.nan_to_num(c.ref_err[use]), c.width[use]
    area = np.cumsum(np.maximum(r, 0) * dx)
    if area[-1] <= 0:
        return math.nan
    left = np.concatenate(([0.0], area[:-1])) / area[-1]
    mask = left >= from_cdf
    if mask.sum() < 2:
        mask = np.zeros(len(dx), dtype=bool)
        mask[-max(2, len(dx) // 4):] = True
    sigma = math.sqrt(float(np.sum((e[mask] ** 2 + re[mask] ** 2) * dx[mask] ** 2)))
    return abs(float(np.sum((y[mask] - r[mask]) * dx[mask]))) / sigma if sigma > 0 else math.nan


def wmape_yield(c: Curve, **_) -> float:
    """Σ |y − ref|Δx / Σ ref Δx: the mean relative error weighted by the reference's yield (the old `rel_abs_area`)."""
    return rel_abs_area(c)


def wmape_axis(c: Curve, **_) -> float:
    """Σ Δx |y/ref − 1| / Σ Δx over the page as drawn: every unit of the axis counts alike, noise and all. Right when
    every bin is precise; a noisy wide tail bin makes a true curve look wrong (`shape` shrinks it), and a hole costs
    at most 1 (`shape` and `L4` take the log)."""
    use, drawn = _ratio_terms(c)
    width = float(np.sum(drawn[use]))
    return float(np.sum(np.abs(c.y[use] / c.ref_y[use] - 1) * drawn[use])) / width if width else math.nan


def L4(c: Curve, eps: float = EPS, **_) -> float:
    """(mean |ℓ|⁴)^¼: the fourth-power mean of the log ratio, which counts a 10× blow-up or dropout some 3500× a 10 %
    fluctuation. Not weighted by precision: a noisy wide bin that fluctuates counts in full."""
    ell, _, use = log_ratio(c, eps)
    return float(np.mean(np.abs(ell[use]) ** 4) ** 0.25) if use.any() else math.nan


def rho1(c: Curve, **_) -> float:
    """The lag-1 autocorrelation of the signed Poisson-deviance pulls: ~0 for scatter that changes sign bin to bin,
    toward 1 for a curve that sits above the reference for a stretch and below for the next. A systematic, whatever
    the χ². NaN under 8 bins (it is unreliable there); blind to an isolated spike, which has no neighbour like it."""
    d2, use = deviance(c)
    if use.sum() < 8:
        return math.nan
    d = (np.sign(c.y - c.ref_y) * np.sqrt(d2))[use]
    d = d - d.mean()
    den = float(np.sum(d * d))
    return float(np.sum(d[:-1] * d[1:]) / den) if den > 0 else math.nan


def cvar(c: Curve, k: int | None = None, **_) -> float:
    """The mean of the k largest Poisson deviances, k = max(3, ⌈0.1 N⌉) unless given: `worst` on the reference's
    anchor, so a spike with an error as large as itself counts in full. Two curves with the same worst bins tie."""
    d2, use = deviance(c)
    if not use.any():
        return math.nan
    d2 = np.sort(d2[use])[::-1]
    return float(np.mean(d2[:min(len(d2), k if k else max(3, math.ceil(0.10 * len(d2))))]))


def _second_difference(values: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(jump, w_left, w_right): each interior value less the interpolation of its neighbours at their x (a straight
    line, so a constant and a straight tilt have no jump)."""
    span = x[2:] - x[:-2]
    with np.errstate(divide="ignore", invalid="ignore"):
        wl, wr = (x[2:] - x[1:-1]) / span, (x[1:-1] - x[:-2]) / span
    return values[1:-1] - (wl * values[:-2] + wr * values[2:]), wl, wr


def roughness(c: Curve, eps: float = EPS, centres_mode: str = "mid", **_) -> float:
    """The RMS second difference of the log ratio over bin centres: each bin against the line through its neighbours.
    Fires on a spike or a hole and not on a normalisation or tilt (a constant and a line have no second difference);
    blind to those, and to a defect two bins wide that its neighbours share."""
    ell, _, use = log_ratio(c, eps)
    x = centres(c, centres_mode)
    ok = use & np.isfinite(x)
    if ok.sum() < 3:
        return math.nan
    jump, _, _ = _second_difference(ell[ok], x[ok])
    return float(math.sqrt(np.mean(jump**2)))


def _intrinsic(c: Curve, eps: float):
    """(η, σ_η, ok): ln y floored at ε of the mean density, and its error."""
    use = np.isfinite(c.y)
    total = float(np.sum(np.maximum(c.y[use], 0) * c.width[use]))
    span = float(np.sum(c.width[use]))
    floor = eps * max(total / span if span > 0 else 0.0, 1e-300)
    star = np.maximum(np.where(use, c.y, 0.0), floor)
    sigma = np.where(np.nan_to_num(c.err) > 0, np.nan_to_num(c.err) / star, 1.0)
    return np.log(star), sigma, use & (total > 0)


def r_int(c: Curve, eps: float = EPS, **_) -> float:
    """The RMS second difference of ln y, no reference: a smooth exponential or power law has none, a spike or a hole
    has a lot. Counts statistical scatter too, so a noisy tail reads rough (`chi2_smooth` forgives scatter)."""
    eta, _, ok = _intrinsic(c, eps)
    a, b = c.edges
    x = ((a + b) / 2)[ok]
    if ok.sum() < 3 or not np.isfinite(x).all():
        return math.nan
    jump, _, _ = _second_difference(eta[ok], x)
    return float(math.sqrt(np.mean(jump**2)))


def chi2_smooth(c: Curve, eps: float = EPS, **_) -> float:
    """r_int's jumps in units of what scatter explains, per bin: jump² / (V_n + σ̃²), V_n the neighbours' interpolated
    variance and σ̃² the mean of their error² standing in for the bin's own, which a spike would inflate to excuse
    itself. About 1 for a smooth curve with honest errors; the note's denominator (2 V_n) gives 1.5 for it."""
    eta, sigma, ok = _intrinsic(c, eps)
    a, b = c.edges
    x = ((a + b) / 2)[ok]
    if ok.sum() < 3 or not np.isfinite(x).all():
        return math.nan
    jump, wl, wr = _second_difference(eta[ok], x)
    sg = sigma[ok]
    own = (sg[:-2] ** 2 + sg[2:] ** 2) / 2
    var = (wl * sg[:-2]) ** 2 + (wr * sg[2:]) ** 2 + own
    return float(np.mean(jump**2 / np.maximum(var, 1e-300)))


def n_eff(c: Curve, **_) -> float:
    """Kish's effective count: (Σ y Δx)² / Σ (σ Δx)². How many equal-weight events the histogram is worth; one huge
    weight in one bin takes it to ~1. Needs no reference. Not meaningful where the errors are not weighted-count errors."""
    use = np.isfinite(c.y) & np.isfinite(c.err)
    den = float(np.sum((c.err[use] * c.width[use]) ** 2))
    return float(np.sum(np.maximum(c.y[use], 0) * c.width[use]) ** 2 / den) if den > 0 else math.nan


def holes(c: Curve, **_) -> float:
    """The share of the axis (as drawn) in interior bins with y ≤ 0, that is, with a positive bin after them: an
    unphysical dropout or negative weight. A tail that runs out to zeros is not interior."""
    use = np.isfinite(c.y)
    if not use.any():
        return math.nan
    y, w = c.y[use], c.drawn[use]
    positive = np.flatnonzero(y > 0)
    if not len(positive) or w.sum() <= 0:
        return math.nan
    hole = (y <= 0) & (np.arange(len(y)) < positive[-1])
    return float(np.sum(w[hole]) / np.sum(w))


def tail_fit(c: Curve, eps: float = EPS, tau0: float = TAU0, last: float = 0.25, **_) -> tuple[float, float]:
    """(λ, R²) of ln y = α − λx over the last `last` of the bins (at least 4), weights 1/(σ_η² + τ0²): the decay rate
    of the tail and how straight the tail is in log space. No reference."""
    eta, sigma, ok = _intrinsic(c, eps)
    a, b = c.edges
    x = ((a + b) / 2)
    idx = np.flatnonzero(ok & np.isfinite(x))
    idx = idx[-max(4, math.ceil(last * len(idx))):]
    if len(idx) < 4:
        return math.nan, math.nan
    xs, ys, w = x[idx], eta[idx], 1.0 / (sigma[idx] ** 2 + tau0**2)
    xbar, ybar = np.sum(w * xs) / np.sum(w), np.sum(w * ys) / np.sum(w)
    sxx = float(np.sum(w * (xs - xbar) ** 2))
    if sxx <= 0:
        return math.nan, math.nan
    slope = float(np.sum(w * (xs - xbar) * (ys - ybar))) / sxx
    resid = float(np.sum(w * (ys - (ybar + slope * (xs - xbar))) ** 2))
    total = float(np.sum(w * (ys - ybar) ** 2))
    return -slope, (1.0 - resid / total) if total > 0 else 1.0


def tail_rate(c: Curve, **settings) -> float:
    """λ of `tail_fit`: how fast the tail falls, per unit of drawn x. A descriptor: it has no better or worse."""
    return tail_fit(c, **settings)[0]


def r2_ln(c: Curve, **settings) -> float:
    """1 − R² of `tail_fit`: how far the tail is from a straight line in log y (0 is exactly exponential)."""
    return 1.0 - tail_fit(c, **settings)[1]


def consensus(c: Curve, pool: list | None = None, base: str = "shape", **settings) -> float:
    """`base` (shape by default) of the curve against the median of the pool, not the reference: the curve that
    disagrees with the others, for a page without a trusted reference. The pool's median density and median error per
    bin (bins matched by edges) stand in for the reference; needs three curves with the bin. Pool-dependent: add a
    curve and the others' values move."""
    if not pool or len(pool) < 3:
        return math.nan
    rows = {}
    for other in pool:
        for lo, hi, y, e in zip(other.lo, other.hi, other.y, other.err):
            if np.isfinite(y):
                rows.setdefault((float(lo), float(hi)), []).append((y, e))
    keep = [i for i in range(c.n) if len(rows.get((float(c.lo[i]), float(c.hi[i])), ())) >= 3]
    if len(keep) < 1:
        return math.nan
    med = [(np.median([y for y, _ in rows[(float(c.lo[i]), float(c.hi[i]))]]),
            np.median([e if np.isfinite(e) else 0.0 for _, e in rows[(float(c.lo[i]), float(c.hi[i]))]])) for i in keep]
    k = np.array(keep)
    against = Curve(c.lo[k], c.hi[k], c.y[k], c.err[k], np.array([m for m, _ in med]), np.array([e for _, e in med]), c.logx)
    return REGISTRY[base](against, **settings)


def js(c: Curve, **_) -> float:
    """The Jensen–Shannon divergence of the two shapes, each normalised to unit yield, in bits (0 to 1): blind to
    normalisation by construction, ignores the errors, and dominated by the bulk where the probability is."""
    use = np.isfinite(c.y) & np.isfinite(c.ref_y)
    p, q = np.maximum(c.y[use], 0) * c.width[use], np.maximum(c.ref_y[use], 0) * c.width[use]
    if p.sum() <= 0 or q.sum() <= 0:
        return math.nan
    p, q = p / p.sum(), q / q.sum()
    m = (p + q) / 2
    with np.errstate(divide="ignore", invalid="ignore"):
        kl = lambda a: float(np.sum(np.where(a > 0, a * np.log(a / m), 0.0)))
    return max(0.0, (kl(p) + kl(q)) / (2 * math.log(2)))


def ad(c: Curve, **_) -> float:
    """The Anderson–Darling distance between the two cumulative shapes: Σ (F_c − F_r)² / (F_r (1 − F_r)) · q over the
    interior edges. The weight 1/(1 − F_r) grows as the reference's tail runs out, so a tail discrepancy counts as much as
    the peak's; blind to normalisation and to a self-cancelling wiggle."""
    use = np.isfinite(c.y) & np.isfinite(c.ref_y)
    p, q = np.maximum(c.y[use], 0) * c.width[use], np.maximum(c.ref_y[use], 0) * c.width[use]
    if p.sum() <= 0 or q.sum() <= 0 or len(p) < 3:
        return math.nan
    p, q = p / p.sum(), q / q.sum()
    fc, fr = np.cumsum(p)[:-1], np.cumsum(q)[:-1]
    inside = (fr > 0) & (fr < 1)
    return float(np.sum((fc[inside] - fr[inside]) ** 2 / (fr[inside] * (1 - fr[inside])) * q[:-1][inside]))


REGISTRY: dict[str, Metric] = {m.name: m for m in (
    # 1. Statistical compatibility
    Metric("chi2_ndf", chi2_ndf, "compatibility", thresholds=(1.0, 3.0), default=True,
           why="1 is the expectation for a true curve; 3 is a fit no one calls compatible",
           note="reduced χ² as Paint counts it; blind to a bin whose own error is as large as its excess"),
    Metric("chi2_z", chi2_z, "compatibility", thresholds=(2.5, 6.0),
           why="Z of χ²/ndf (Wilson–Hilferty): 6 is χ²/ndf = 3 on 40 bins; 2.5 is the 99th percentile of a true curve",
           note="χ²/ndf in standard deviations, so pages with 12 and 120 bins share a scale; the same blind spot as χ²/ndf"),
    Metric("poisson", poisson, "compatibility", thresholds=(3.5, 9.0),
           why="a true curve as noisy as its reference averages 2 (its value is 1 + (σ/σ_ref)²), p97 3.0",
           note="mean Poisson deviance anchored to the reference; right in low-count tails and not fooled by a spike's own "
                "error bar; reads high when the curve is noisier than the reference"),
    Metric("tail", tail, "compatibility", thresholds=(2.5, 6.0),
           why="|Z| of a true tail is half-normal: p97 is 2.2; 6 is a tail off by several sigma",
           note="|Z| of the pooled excess over the last 10 % of the reference's yield; blind to an excess that changes sign inside the tail"),
    # 2. Normalisation
    Metric("norm", norm, "normalisation", thresholds=(0.02, 0.15), default=True,
           why="2 % is inside a good normalisation, 15 % is a curve off by a luminosity",
           note="|ln| of the yield ratio; blind to where the yield goes"),
    Metric("area_ratio", area_ratio, "normalisation", better="one", thresholds=(0.009, 0.065),
           why="the same as norm in log10: 2 % and 15 %",
           note="the old column: yield over reference yield, scored by |log10|. Moves with ratio_mean (collinear)"),
    Metric("ratio_mean", ratio_mean, "normalisation", better="one", thresholds=(0.009, 0.065),
           why="the same as area_ratio",
           note="the old column: the ratio pad's mean ratio, scored by |log10|"),
    Metric("wmape_yield", wmape_yield, "normalisation", thresholds=(0.03, 0.20),
           why="a true curve reads 0.016 at p97; 20 % is a yield-weighted error nobody accepts",
           note="Σ|y−ref|Δx / Σ ref Δx: the yield-weighted mean relative error (= rel_abs_area); blind to where in x the error is"),
    # 3. Shape accuracy, bin by bin
    Metric("shape", shape, "shape", thresholds=(0.02, 0.15), default=True,
           why="2 % is the noise floor of a precise page, 15 % a shape no one accepts",
           note="mean |ln ratio| over the axis, a noisy bin counted less; shares a uniform shift with norm"),
    Metric("ratio_dev", ratio_dev, "shape", thresholds=(0.04, 0.25),
           why="a true curve reads 0.023 at p97; 25 % as wmape_axis's bad",
           note="the old column: the ratio pad's mean |ratio − 1|. Moves with rel_abs_area (collinear)"),
    Metric("rel_abs_area", rel_abs_area, "shape", thresholds=(0.03, 0.20),
           why="as wmape_yield, which it equals",
           note="the old column: Σ|y−ref|Δx / Σ ref Δx. Moves with ratio_dev (collinear)"),
    Metric("wmape_axis", wmape_axis, "shape", thresholds=(0.04, 0.25),
           why="a true curve reads 0.023 at p97; 25 % is a ratio pad off by a quarter on average",
           note="mean |ratio − 1| over the axis, noise and all; a noisy wide bin makes a true curve read wrong"),
    Metric("L4", L4, "shape", thresholds=(0.07, 0.40),
           why="a true curve reads 0.05 at p97; 0.4 is a bin off by a factor 1.5 in a fifth of the bins or a 10× in one",
           note="(mean |ln ratio|⁴)^¼: counts an outlier of either direction far more than a fluctuation; not weighted by precision"),
    Metric("consensus", consensus, "shape", thresholds=(0.03, 0.20), needs_reference=False, pool=True,
           why="shape against the median of at least three curves: a true curve among true curves reads 0.02 to 0.03",
           note="shape against the median curve of the page, not the reference; pool-dependent: add a curve and the others' values move"),
    # 4. Shape similarity, as distributions
    Metric("js", js, "similarity", thresholds=(0.0005, 0.02),
           why="a true curve reads 8e-5 at p97; a tilt of e^0.6 across the page reads 0.004; a bin ×20, 0.15",
           note="Jensen–Shannon divergence of the shapes in bits; blind to normalisation and the errors, dominated by the bulk"),
    Metric("ad", ad, "similarity", thresholds=(0.0005, 0.02),
           why="a true curve reads 2e-5 at p97; the same tilt reads 0.011; a bin ×20, 0.067",
           note="Anderson–Darling distance of the cumulative shapes; weights a gap by 1/(F(1−F)), so one in the tail counts more than in the bulk; blind to normalisation"),
    # 5. Trend
    Metric("tilt", tilt, "trend", thresholds=(0.03, 0.25), default=True,
           why="3 % across the page is inside the noise of a precise page, 25 % a trend nobody accepts",
           note="the ratio's total change across the page (weighted slope × span); blind to a kink"),
    Metric("rho1", rho1, "trend", thresholds=(0.35, 0.8),
           why="the lag-1 autocorrelation of 40 true pulls has σ = 0.16 (p97 0.26, max 0.38); a tilt of e^0.6 reads 0.9",
           note="lag-1 autocorrelation of the signed pulls, mean removed: a curve above the reference for a stretch and below for the next; "
                "blind to a uniform offset and to an isolated spike; NaN under 8 bins"),
    # 6. Local defects
    Metric("worst", worst, "defects", thresholds=(7.0, 25.0), default=True,
           why="the mean of the top 4 of 40 true squared pulls has median 4.1, p97 6.6, max 9.2 (the notes' good = 2 would charge a "
               "true curve 0.3); 25 is one bin at 10 sigma",
           note="the mean of the k largest squared pulls; a spike with an error as big as itself hides in it"),
    Metric("cvar", cvar, "defects", thresholds=(14.0, 45.0),
           why="twice worst's: the reference-anchored deviance of two equally noisy curves is twice a pull²; true curves read 8 (p97 13)",
           note="the mean of the k largest Poisson deviances (k settable); a spike counts in full whatever its own error; ties on the same worst bins"),
    Metric("roughness", roughness, "defects", thresholds=(0.06, 0.40),
           why="a true curve reads 0.042 at p97; a bin ×20 reads 0.6, a hole 0.9",
           note="RMS second difference of the log ratio; fires on a spike or a hole, not on a shift or a tilt; counts scatter too"),
    # 7. Monte Carlo quality, without a reference
    Metric("n_eff", n_eff, "quality", better="higher", thresholds=(1000.0, 100.0), needs_reference=False,
           why="a yield known to 3 % is worth 1000 equal-weight events, to 10 % 100",
           note="Kish's effective count; one huge weight in one bin takes it to about 1; says nothing where errors are not weight errors"),
    Metric("holes", holes, "quality", thresholds=(0.0, 0.10), needs_reference=False,
           why="no hole is the only good; a tenth of the axis is a histogram with gaps",
           note="share of the axis in interior bins with y ≤ 0; a tail running out to zeros is not interior"),
    Metric("r_int", r_int, "quality", thresholds=(0.05, 0.40), needs_reference=False,
           why="a true curve of this precision reads 0.029 at p97; a spike or a hole reads 0.6 to 0.8",
           note="RMS second difference of ln y; counts scatter, so a sparse tail reads rough (chi2_smooth forgives scatter)"),
    Metric("chi2_smooth", chi2_smooth, "quality", thresholds=(2.5, 8.0), needs_reference=False,
           why="about 1 for a smooth curve with honest errors (p97 1.7); a spike reads hundreds",
           note="the jumps of ln y in units of what scatter explains, anchored to the neighbours' errors"),
    Metric("r2_ln", r2_ln, "quality", thresholds=(0.05, 0.30), needs_reference=False,
           why="1 − R² of the log-linear tail fit: p97 0.023 for a true exponential tail",
           note="how far the last quarter of the curve is from a straight line in ln y; blind to a wrong slope: see tail_rate"),
    Metric("lambda", tail_rate, "quality", better="none", needs_reference=False,
           note="the fitted decay rate of the last quarter of the curve; a descriptor, it has no better or worse (give thresholds to score it)"),
)}


def describe(name: str, thresholds: tuple[float, float] | None = None) -> str:
    """A metric as a footnote says it: its title and note, then what its thresholds are (`thresholds`: the setting's, else the
    registry's) and why."""
    m = REGISTRY[name]
    text = f"{title_of(name)}: {m.note}."
    used = thresholds or m.thresholds
    if used:
        good, bad = used
        text += f" Scored from {good:g} (cost 0) to {bad:g} (cost 1)" + (f": {m.why}." if m.why and not thresholds else ".")
    else:
        text += " A descriptor: it is not scored."
    return text


def evaluate(name: str, curve: Curve, **settings) -> float:
    """metric `name` of `curve` (`pool=` the page's curves for a pooled one); an unknown name is an error that lists the known ones."""
    from runner.errors import HeimdallError
    if name not in REGISTRY:
        raise HeimdallError(f"no metric '{name}'", hint="metrics: " + ", ".join(REGISTRY))
    return REGISTRY[name](curve, **settings)
