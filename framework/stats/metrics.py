"""The metrics: a number for one curve against its page's reference, from Paint's measured bins.

`REGISTRY` maps an id to a `Metric`: its function, the category it answers (CATEGORIES), its polarity (which way is
better, POLARITIES), its scale, the (good, bad) thresholds that normalise it (a value at or under `good` costs nothing; at `bad`, 1), whether it needs a
reference, whether it is on by default, and a note saying what it measures and what it is blind to. A function takes a
`bins.Curve` and returns a float, NaN when the curve has too little to say. `ALIASES` maps an id a metric had before to
the one it has, and `resolve` reads either.

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
TAU = 0.10        # the model tolerance that sets how much a noisy bin counts in `log_dev_shrunk`
TAU0 = 0.01       # keeps one very precise bin from owning the `tilt` regression

#: What a metric answers: its category, in the order the summary and the report show them.
CATEGORIES = {
    "compatibility": "Statistical compatibility",
    "normalisation": "Normalisation",
    "accuracy": "Shape accuracy, bin by bin",
    "similarity": "Shape similarity, as distributions",
    "trend": "Trend",
    "defects": "Local defects",
    "integrity": "Integrity",
    "quality": "Monte Carlo quality, without a reference",
}

#: The question each category asks, as the summary says it: a sentence on the question, and what is not answered by it.
QUESTIONS = {
    "compatibility": "Is the curve statistically compatible with the reference, bin errors counted? Near the good threshold: yes; "
                     "past bad: no. It says nothing of where, and a curve with large errors is compatible with anything.",
    "normalisation": "Does the curve hold the reference's yield? An overall factor, whatever the shape; blind to where the yield goes.",
    "accuracy": "How far is the curve from the reference, bin by bin, once its normalisation is set aside? Counts the "
                "whole axis, the tails as much as the peak.",
    "similarity": "Are the two distributions alike as shapes: the share of yield per bin, normalisation removed.",
    "trend": "Does the curve drift away from the reference across the axis (a slope or a curvature in the ratio)?",
    "defects": "Is there a bin, or a few, badly off: a spike or a hole the averages hide?",
    "integrity": "Is the curve fit to be ranked at all: no bin a thousand times its reference, a positive yield on a "
                 "cross-section page? A page that fails it is a gate's veto, not a cost.",
    "quality": "Is the curve itself sound as a Monte Carlo histogram, with no reference: smooth, filled, enough events?",
}

#: Each metric's name where it is shown (a column, a panel, a section); the id itself where none is given.
TITLES = {
    "chi2_ndf": "χ²/ndf", "chi2_sigma": "χ² significance (σ)", "poisson_dev": "Poisson deviance per bin",
    "tail_excess_sigma": "tail excess (σ)", "log_yield_ratio": "yield ratio, |ln|", "yield_ratio": "yield ratio",
    "mean_bin_ratio": "mean bin ratio", "log_dev_shrunk": "mean |ln ratio|, precision-shrunk", "log_dev_l4": "L4 |ln ratio|",
    "mean_abs_ratio_dev": "mean |ratio − 1|", "yield_weighted_abs_dev": "yield-weighted |Δ|",
    "consensus_dev": "deviation from the page's median curve", "js_divergence": "Jensen–Shannon divergence (bits)",
    "ad_distance": "Anderson–Darling distance", "tilt": "tilt, Δ ln ratio across the page",
    "pull_autocorr": "pull autocorrelation, lag 1", "peak_pull2": "largest pulls², mean of the top k",
    "peak_deviance": "largest deviances, mean of the top k", "log_ratio_roughness": "roughness of ln ratio",
    "n_eff": "effective events", "hole_fraction": "hole fraction", "log_roughness": "roughness of ln y",
    "smoothness_chi2": "smoothness χ²", "tail_nonlinearity": "tail non-linearity, 1 − R²", "tail_slope": "tail decay rate",
    "peak_bin_ratio": "largest bin ratio (decades)", "yield_sign": "page yield ≤ 0", "negative_share": "negative-weight share",
}

#: Each metric's id before the catalogue was renamed → its id now. Two retired twins read as the metric they equal.
ALIASES = {
    "chi2_z": "chi2_sigma", "poisson": "poisson_dev", "tail": "tail_excess_sigma", "norm": "log_yield_ratio",
    "area_ratio": "yield_ratio", "ratio_mean": "mean_bin_ratio", "wmape_yield": "yield_weighted_abs_dev",
    "shape": "log_dev_shrunk", "L4": "log_dev_l4", "ratio_dev": "mean_abs_ratio_dev", "rel_abs_area": "yield_weighted_abs_dev",
    "wmape_axis": "mean_abs_ratio_dev", "consensus": "consensus_dev", "js": "js_divergence", "ad": "ad_distance",
    "rho1": "pull_autocorr", "worst": "peak_pull2", "cvar": "peak_deviance", "roughness": "log_ratio_roughness",
    "holes": "hole_fraction", "r_int": "log_roughness", "chi2_smooth": "smoothness_chi2", "r2_ln": "tail_nonlinearity",
    "lambda": "tail_slope",
}

#: Which way a metric is better, and how each is said: a glyph, its form for a terminal that is not UTF-8, a phrase.
POLARITIES = ("lower", "higher", "one", "descriptor")
GLYPH = {"lower": "↓", "higher": "↑", "one": "→1", "descriptor": "○"}
ASCII = {"lower": "[v]", "higher": "[^]", "one": "[=1]", "descriptor": "[o]"}
PHRASE = {"lower": "lower is better", "higher": "higher is better", "one": "closest to 1 is better",
          "descriptor": "a descriptor, not scored"}
SCALES = ("linear", "log")


def resolve(name: str) -> str:
    """A metric's id, from its id or the id it had before."""
    return ALIASES.get(name, name)


def title_of(name: str) -> str:
    return TITLES.get(name, name)


#: The formulas of the columns Paint made first, as LaTeX (math mode), i running over the compared bins: a report's
#: "How the numbers are made" sets them; a metric without one is described by its note.
FORMULAS = {
    "chi2_ndf": r"\chi^2/\mathrm{ndf} = \frac{1}{\mathrm{ndf}} \sum_i "
                r"\frac{(y_i - y_{\mathrm{ref},i})^2}{\sigma_i^2 + \sigma_{\mathrm{ref},i}^2}",
    "yield_weighted_abs_dev": r"\frac{|\Delta|}{\mathrm{reference}} = "
                    r"\frac{\sum_i |y_i - y_{\mathrm{ref},i}|\,\Delta x_i}{\sum_i y_{\mathrm{ref},i}\,\Delta x_i}",
    "yield_ratio": r"\frac{\mathrm{area}}{\mathrm{reference}} = \frac{\sum_i y_i\,\Delta x_i}{\sum_i y_{\mathrm{ref},i}\,\Delta x_i}",
    "mean_bin_ratio": r"\mathrm{mean\ ratio} = \frac{\sum_i (y_i / y_{\mathrm{ref},i})\,\Delta x_i}{\sum_i \Delta x_i}",
    "mean_abs_ratio_dev": r"\mathrm{mean}\,|\mathrm{ratio} - 1| = "
                 r"\frac{\sum_i |y_i / y_{\mathrm{ref},i} - 1|\,\Delta x_i}{\sum_i \Delta x_i}",
}


@dataclass(frozen=True)
class Metric:
    name: str
    fn: Callable[..., float]
    category: str
    polarity: str = "lower"                   # one of POLARITIES; "one": closest to 1, scored by |log10|; "descriptor": not scored
    scale: str = "linear"                     # "log": the metric spans decades, as n_eff
    thresholds: tuple[float, float] | None = None   # (good, bad), in the scored quantity; None: none chosen, so it cannot be normalised by default
    needs_reference: bool = True
    default: bool = False
    note: str = ""
    why: str = ""                             # where the thresholds come from
    pool: bool = False                        # needs the page's other curves (`pool=`): its value depends on who else is on the page
    shown: bool = False                       # computed in every table, not scored unless named
    gate: float | None = None                 # a page fails at this value or more (or +inf); NaN never fails

    def __call__(self, curve: Curve, **settings) -> float:
        return self.fn(curve, **settings)

    def _descriptor(self) -> None:
        if self.polarity == "descriptor":
            from runner.errors import HeimdallError
            raise HeimdallError(f"'{self.name}' is a descriptor: it has no cost", hint="name a metric that is scored, or a gate")

    def _scaled(self, value: float) -> float:
        """T: log10 for a metric on a log scale (NaN at or below zero), else the value."""
        if self.scale == "log":
            return math.log10(value) if value > 0 else math.nan
        return value

    def oriented(self, value: float) -> float:
        """q, the oriented excess: T(m) for "lower", −T(m) for "higher", |log10 m| for "one" (+inf at m ≤ 0); NaN stays NaN."""
        self._descriptor()
        if value != value:
            return math.nan
        if self.polarity == "one":
            return abs(math.log10(value)) if value > 0 else math.inf
        t = self._scaled(value)
        return -t if self.polarity == "higher" else t

    def _edge(self, threshold: float) -> float:
        """A threshold oriented as a value is; a "one" metric's thresholds are given on |log10| already."""
        return threshold if self.polarity == "one" else self.oriented(threshold)

    def excess(self, value: float, thresholds: tuple[float, float] | None = None) -> float:
        """z, the hinged tolerance excess: 0 at or inside good, 1 at bad, in proportion beyond; +inf for q = +inf, 0 for q = −inf
        (infinitely good), NaN stays NaN."""
        good, bad = thresholds or self.thresholds or (math.nan, math.nan)
        q = self.oriented(value)
        if q != q:
            return math.nan
        if math.isinf(q):
            return math.inf if q > 0 else 0.0
        g, b = self._edge(good), self._edge(bad)
        return max(0.0, (q - g) / (b - g))

    def cost(self, value: float, thresholds: tuple[float, float] | None = None) -> float:
        """c = log2(1 + z): 0 within good, 1 at bad, 2 at z = 3; grows ever slower beyond bad."""
        z = self.excess(value, thresholds)
        return z if z != z or math.isinf(z) else math.log2(1.0 + z)


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


# ── the five the defaults began with ───────────────────────────────────────────────────────────

def chi2_ndf(c: Curve, **_) -> float:
    """χ²/ndf as Paint counts it: Σ (y − ref)² / (σ² + σ_ref²) over the bins with a nonzero error, per such bin."""
    d = c.y - c.ref_y
    s2 = np.nan_to_num(c.err) ** 2 + np.nan_to_num(c.ref_err) ** 2
    use = (s2 > 0) & np.isfinite(d)
    return float(np.sum(d[use] ** 2 / s2[use]) / use.sum()) if use.any() else math.nan


def log_yield_ratio(c: Curve, eps: float = EPS, **_) -> float:
    """|ln(Σ y·Δx / Σ ref·Δx)|: the yield off by a factor, either way alike (a curve 20 % high and one 1/1.2 low
    are equally wrong). Blind to where the yield goes. A curve with no yield counts as ε of the reference."""
    use = np.isfinite(c.y) & np.isfinite(c.ref_y)
    ref_area = float(np.sum(c.ref_y[use] * c.width[use]))
    if not use.any() or ref_area <= 0:
        return math.nan
    cmp_area = max(float(np.sum(c.y[use] * c.width[use])), eps * ref_area)
    return abs(math.log(cmp_area / ref_area))


def log_dev_shrunk(c: Curve, eps: float = EPS, tau: float = TAU, **_) -> float:
    """Σ Δx·s·|ℓ| / Σ Δx, s = τ²/(τ² + σ_ℓ²): the log ratio's mean size over the axis, a noisy bin counted less
    (it cannot be told from a fluctuation) and a wide bin more. Blind to a uniform shift that `log_yield_ratio` carries too."""
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


def peak_pull2(c: Curve, k_floor: int = 3, k_frac: float = 0.10, **_) -> float:
    """The mean of the k largest squared pulls (y − ref)/σ, k = max(3, ⌈0.1 N⌉): a glitch that χ²/ndf spreads over
    all the bins, undiluted. A spike whose own error is as large as itself hides in its σ: `poisson_dev` and `peak_deviance`
    anchor the error to the reference instead (the catalogue)."""
    d = c.y - c.ref_y
    s2 = np.nan_to_num(c.err) ** 2 + np.nan_to_num(c.ref_err) ** 2
    use = (s2 > 0) & np.isfinite(d)
    if not use.any():
        return math.nan
    z2 = np.sort(d[use] ** 2 / s2[use])[::-1]
    k = min(len(z2), max(k_floor, math.ceil(k_frac * len(z2))))
    return float(np.mean(z2[:k]))


# ── the table's fixed ratio columns, from the same bins ───────────────────────────────────────

def _ratio_terms(c: Curve):
    ref = c.ref_y
    drawn = c.drawn
    use = np.isfinite(c.y) & np.isfinite(ref) & (ref != 0) & (drawn > 0)
    return use, drawn


def yield_weighted_abs_dev(c: Curve, **_) -> float:
    """Σ |y − ref|·Δx / Σ ref·Δx: the yield-weighted error, shape and normalisation together."""
    ref_area = float(np.sum(c.ref_y * c.width))
    return float(np.sum(np.abs(c.y - c.ref_y) * c.width)) / ref_area if ref_area else math.nan


def yield_ratio(c: Curve, **_) -> float:
    """Σ y·Δx / Σ ref·Δx: the curve's yield over the reference's."""
    ref_area = float(np.sum(c.ref_y * c.width))
    return float(np.sum(c.y * c.width)) / ref_area if ref_area else math.nan


def mean_bin_ratio(c: Curve, **_) -> float:
    """The mean of y/ref over the page as drawn (the ratio pad's width: log10 x on a log-x page)."""
    use, drawn = _ratio_terms(c)
    width = float(np.sum(drawn[use]))
    return float(np.sum(c.y[use] / c.ref_y[use] * drawn[use])) / width if width else math.nan


def mean_abs_ratio_dev(c: Curve, **_) -> float:
    """The mean of |y/ref − 1| over the page as drawn: every unit of the axis alike, noise and all."""
    use, drawn = _ratio_terms(c)
    width = float(np.sum(drawn[use]))
    return float(np.sum(np.abs(c.y[use] / c.ref_y[use] - 1) * drawn[use])) / width if width else math.nan


# ── the opt-in catalogue ──────────────────────────────────────────────────────────────────────

def _pulls2(c: Curve):
    """Per bin: d = y − ref, s² = σ² + σ_ref², and the bins where a pull exists (s² > 0)."""
    d = c.y - c.ref_y
    s2 = np.nan_to_num(c.err) ** 2 + np.nan_to_num(c.ref_err) ** 2
    return d, s2, (s2 > 0) & np.isfinite(d)


def chi2_sigma(c: Curve, **_) -> float:
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


def poisson_dev(c: Curve, **_) -> float:
    """The mean Poisson deviance per bin against the reference (Baker–Cousins), anchored to the reference: χ²/ndf that
    stays right in low-count tail bins and cannot be fooled by a spike's own error bar (`deviance`)."""
    d2, use = deviance(c)
    return float(np.mean(d2[use])) if use.any() else math.nan


def tail_excess_sigma(c: Curve, from_cdf: float = 0.90, **_) -> float:
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


def log_dev_l4(c: Curve, eps: float = EPS, **_) -> float:
    """(mean |ℓ|⁴)^¼: the fourth-power mean of the log ratio, which counts a 10× blow-up or dropout some 3500× a 10 %
    fluctuation. Not weighted by precision: a noisy wide bin that fluctuates counts in full."""
    ell, _, use = log_ratio(c, eps)
    return float(np.mean(np.abs(ell[use]) ** 4) ** 0.25) if use.any() else math.nan


def pull_autocorr(c: Curve, **_) -> float:
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


def peak_deviance(c: Curve, k: int | None = None, **_) -> float:
    """The mean of the k largest Poisson deviances, k = max(3, ⌈0.1 N⌉) unless given: `peak_pull2` on the reference's
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


def log_ratio_roughness(c: Curve, eps: float = EPS, centres_mode: str = "mid", **_) -> float:
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


def log_roughness(c: Curve, eps: float = EPS, **_) -> float:
    """The RMS second difference of ln y, no reference: a smooth exponential or power law has none, a spike or a hole
    has a lot. Counts statistical scatter too, so a noisy tail reads rough (`smoothness_chi2` forgives scatter)."""
    eta, _, ok = _intrinsic(c, eps)
    a, b = c.edges
    x = ((a + b) / 2)[ok]
    if ok.sum() < 3 or not np.isfinite(x).all():
        return math.nan
    jump, _, _ = _second_difference(eta[ok], x)
    return float(math.sqrt(np.mean(jump**2)))


def smoothness_chi2(c: Curve, eps: float = EPS, **_) -> float:
    """log_roughness's jumps in units of what scatter explains, per bin: jump² / (V_n + σ̃²), V_n the neighbours' interpolated
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


def negative_share(c: Curve, **_) -> float:
    """Σ max(−y, 0)·Δx / Σ |y|·Δx: how much of the curve is negative bins (negative weights), no reference."""
    use = np.isfinite(c.y)
    total = float(np.sum(np.abs(c.y[use]) * c.width[use]))
    return float(np.sum(np.maximum(-c.y[use], 0) * c.width[use])) / total if total > 0 else math.nan


def n_eff(c: Curve, **_) -> float:
    """Kish's effective count: (Σ y Δx)² / Σ (σ Δx)². How many equal-weight events the histogram is worth; one huge
    weight in one bin takes it to ~1. Needs no reference. Not meaningful where the errors are not weighted-count errors."""
    use = np.isfinite(c.y) & np.isfinite(c.err)
    den = float(np.sum((c.err[use] * c.width[use]) ** 2))
    return float(np.sum(np.maximum(c.y[use], 0) * c.width[use]) ** 2 / den) if den > 0 else math.nan


def hole_fraction(c: Curve, **_) -> float:
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


def tail_slope(c: Curve, **settings) -> float:
    """λ of `tail_fit`: how fast the tail falls, per unit of drawn x. A descriptor: it has no better or worse."""
    return tail_fit(c, **settings)[0]


def tail_nonlinearity(c: Curve, **settings) -> float:
    """1 − R² of `tail_fit`: how far the tail is from a straight line in log y (0 is exactly exponential)."""
    return 1.0 - tail_fit(c, **settings)[1]


def consensus_dev(c: Curve, pool: list | None = None, base: str = "log_dev_shrunk", **settings) -> float:
    """`base` (`log_dev_shrunk` by default) of the curve against the median of the pool, not the reference: the curve that
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


def js_divergence(c: Curve, **_) -> float:
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


def ad_distance(c: Curve, **_) -> float:
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


# ── the integrity gates ──────────────────────────────────────────────────────────────────────

def peak_bin_ratio(c: Curve, **_) -> float:
    """log10 of the largest |y|/ref over the compared bins with a positive reference: 3 is a bin 1000× its reference.
    NaN when no such bin has a yield."""
    use = np.isfinite(c.y) & np.isfinite(c.ref_y) & (c.ref_y > 0)
    ratio = np.abs(c.y[use]) / c.ref_y[use]
    top = float(ratio.max()) if ratio.size else 0.0
    return math.log10(top) if top > 0 else math.nan


def yield_sign(c: Curve, **_) -> float:
    """1 when the page's summed yield Σ y·Δx is not positive, else 0: a cross-section is positive. NaN on a normalised
    page, where the yield is not a cross-section."""
    use = np.isfinite(c.y)
    if c.normalised or not use.any():
        return math.nan
    return 1.0 if float(np.sum(c.y[use] * c.width[use])) <= 0 else 0.0


REGISTRY: dict[str, Metric] = {m.name: m for m in (
    # 1. Statistical compatibility
    Metric("chi2_ndf", chi2_ndf, "compatibility", thresholds=(1.0, 3.0), default=True,
           why="1 is the expectation for a true curve; 3 is a fit no one calls compatible",
           note="Σ (y − ref)² / (σ² + σ_ref²) per bin with an error; 1 is a true curve. Blind to a bin whose error is as big as its excess"),
    Metric("chi2_sigma", chi2_sigma, "compatibility", thresholds=(2.5, 6.0),
           why="Z of χ²/ndf (Wilson–Hilferty): 6 is χ²/ndf = 3 on 40 bins; 2.5 is the 99th percentile of a true curve",
           note="χ²/ndf as standard deviations (Wilson–Hilferty), so pages of 5 and 50 bins share one scale"),
    Metric("poisson_dev", poisson_dev, "compatibility", thresholds=(3.5, 9.0),
           why="a true curve as noisy as its reference averages 2 (its value is 1 + (σ/σ_ref)²), p97 3.0",
           note="Baker–Cousins deviance anchored to the reference's counts: a spike cannot hide in its own error bar"),
    Metric("tail_excess_sigma", tail_excess_sigma, "compatibility", thresholds=(2.5, 6.0),
           why="|Z| of a true tail is half-normal: p97 is 2.2; 6 is a tail off by several sigma",
           note="|Z| of the summed excess beyond 90 % of the reference's yield"),
    # 2. Normalisation
    Metric("log_yield_ratio", log_yield_ratio, "normalisation", thresholds=(0.02, 0.15), default=True,
           why="2 % is inside a good normalisation, 15 % is a curve off by a luminosity",
           note="|ln(Σ y Δx / Σ ref Δx)|: off by a factor, either way alike; blind to where the yield goes"),
    Metric("yield_ratio", yield_ratio, "normalisation", polarity="one", thresholds=(0.009, 0.065),
           why="the same as log_yield_ratio in log10: 2 % and 15 %",
           note="the curve's yield over the reference's on the compared bins"),
    Metric("mean_bin_ratio", mean_bin_ratio, "normalisation", polarity="one", thresholds=(0.009, 0.065),
           why="the same as yield_ratio",
           note="the ratio pad's mean height over the axis as drawn"),
    # 3. Shape accuracy, bin by bin
    Metric("log_dev_shrunk", log_dev_shrunk, "accuracy", thresholds=(0.02, 0.15), default=True,
           why="2 % is the noise floor of a precise page, 15 % a shape no one accepts",
           note="the log ratio's mean size over the axis, a bin less precise than 10 % counted less"),
    Metric("log_dev_l4", log_dev_l4, "accuracy", thresholds=(0.07, 0.40),
           why="a true curve reads 0.05 at p97; 0.4 is a bin off by a factor 1.5 in a fifth of the bins or a 10× in one",
           note="(mean |ln ratio|⁴)^¼: one bin off by 10× costs as much as thousands of 10 % ones"),
    Metric("mean_abs_ratio_dev", mean_abs_ratio_dev, "accuracy", thresholds=(0.04, 0.25),
           why="a true curve reads 0.023 at p97; 25 % is a ratio pad off by a quarter on average",
           note="the ratio pad's mean distance from 1 over the axis, every bin alike"),
    Metric("yield_weighted_abs_dev", yield_weighted_abs_dev, "accuracy", thresholds=(0.03, 0.20),
           why="a true curve reads 0.016 at p97; 20 % is a yield-weighted error nobody accepts",
           note="Σ |y − ref| Δx / Σ ref Δx: shape and normalisation together, where the yield is"),
    Metric("consensus_dev", consensus_dev, "accuracy", thresholds=(0.03, 0.20), needs_reference=False, pool=True,
           why="log_dev_shrunk against the median of at least three curves: a true curve among true curves reads 0.02 to 0.03",
           note="log_dev_shrunk against the median of ≥ 3 curves, not the reference; pool-dependent"),
    # 4. Shape similarity, as distributions
    Metric("js_divergence", js_divergence, "similarity", thresholds=(0.0005, 0.02),
           why="a true curve reads 8e-5 at p97; a tilt of e^0.6 across the page reads 0.004; a bin ×20, 0.15",
           note="the two shapes as distributions; blind to normalisation and errors"),
    Metric("ad_distance", ad_distance, "similarity", thresholds=(0.0005, 0.02),
           why="a true curve reads 2e-5 at p97; the same tilt reads 0.011; a bin ×20, 0.067",
           note="the cumulative shapes, a gap in the tail weighted up"),
    # 5. Trend
    Metric("tilt", tilt, "trend", thresholds=(0.03, 0.25), default=True,
           why="3 % across the page is inside the noise of a precise page, 25 % a trend nobody accepts",
           note="the log ratio's fitted change from the first edge to the last"),
    Metric("pull_autocorr", pull_autocorr, "trend", thresholds=(0.35, 0.8),
           why="the lag-1 autocorrelation of 40 true pulls has σ = 0.16 (p97 0.26, max 0.38); a tilt of e^0.6 reads 0.9",
           note="near 0 for scatter; near 1 when the curve sits on one side of the reference for stretches"),
    # 6. Local defects
    Metric("peak_pull2", peak_pull2, "defects", thresholds=(7.0, 25.0), default=True,
           why="the mean of the top 4 of 40 true squared pulls has median 4.1, p97 6.6, max 9.2 (the notes' good = 2 would charge a "
               "true curve 0.3); 25 is one bin at 10 sigma",
           note="the mean of the k = max(3, ⌈N/10⌉) largest squared pulls: a glitch χ² spreads thin"),
    Metric("peak_deviance", peak_deviance, "defects", thresholds=(14.0, 45.0),
           why="twice peak_pull2's: the reference-anchored deviance of two equally noisy curves is twice a pull²; true curves read 8 (p97 13)",
           note="peak_pull2 on the Poisson deviance: a spike counts in full, whatever its error"),
    Metric("log_ratio_roughness", log_ratio_roughness, "defects", thresholds=(0.06, 0.40),
           why="a true curve reads 0.042 at p97; a bin ×20 reads 0.6, a hole 0.9",
           note="the RMS second difference of the log ratio: a spike or a hole, never a shift or a tilt"),
    # 7. Monte Carlo quality, without a reference
    Metric("n_eff", n_eff, "quality", polarity="higher", scale="log", thresholds=(1000.0, 100.0), needs_reference=False,
           why="a yield known to 3 % is worth 1000 equal-weight events, to 10 % 100",
           note="Kish's (Σ y Δx)² / Σ (σ Δx)²: how many equal-weight events the histogram is worth"),
    Metric("hole_fraction", hole_fraction, "quality", thresholds=(0.0, 0.10), needs_reference=False,
           why="no hole is the only good; a tenth of the axis is a histogram with gaps",
           note="the axis share of interior bins with y ≤ 0"),
    Metric("log_roughness", log_roughness, "quality", thresholds=(0.05, 0.40), needs_reference=False,
           why="a true curve of this precision reads 0.029 at p97; a spike or a hole reads 0.6 to 0.8",
           note="the RMS second difference of ln y, no reference"),
    Metric("smoothness_chi2", smoothness_chi2, "quality", thresholds=(2.5, 8.0), needs_reference=False,
           why="about 1 for a smooth curve with honest errors (p97 1.7); a spike reads hundreds",
           note="log_roughness's jumps in units of what scatter explains"),
    Metric("tail_nonlinearity", tail_nonlinearity, "quality", thresholds=(0.05, 0.30), needs_reference=False,
           why="1 − R² of the log-linear tail fit: p97 0.023 for a true exponential tail",
           note="how far the last quarter is from a straight line in ln y"),
    Metric("tail_slope", tail_slope, "quality", polarity="descriptor", needs_reference=False,
           note="the fitted decay rate of the last quarter; a descriptor"),
    Metric("negative_share", negative_share, "quality", thresholds=(0.0, 0.25), needs_reference=False,
           why="ordinary Sherpa curves reach 0.36 at most, p99 0.18: a quarter negative is past bad, and not a gate",
           note="the share of the curve's |yield| in negative bins"),
    # 8. integrity: the gates, a page that fails one vetoes its point
    Metric("peak_bin_ratio", peak_bin_ratio, "integrity", thresholds=(1.0, 3.0), gate=3.0,
           why="ordinary curves reach 2.01 at most; a pathological one 10.7 at the median: 3 is a bin 1000× its reference",
           note="log10 of the largest |y|/ref of a bin with a positive reference"),
    Metric("yield_sign", yield_sign, "integrity", gate=1.0, needs_reference=False,
           note="1 when the page's summed yield is not positive (a cross-section page), else 0"),
)}


def describe(name: str, thresholds: tuple[float, float] | None = None) -> str:
    """A metric as a footnote says it: its title and note, then what its thresholds are (`thresholds`: the setting's, else the
    registry's) and why."""
    name = resolve(name)
    m = REGISTRY[name]
    text = f"{title_of(name)}: {m.note}."
    used = thresholds or m.thresholds
    if used:
        good, bad = used
        text += (f" Scored from {good:g} (cost 0) to {bad:g} (cost 1), compressed beyond: log₂(1 + excess)"
                 + (f": {m.why}." if m.why and not thresholds else "."))
    elif m.gate is not None:
        text += f" A gate only: a page fails it at {m.gate:g} or more, and it is not scored."
    else:
        text += " A descriptor: it is not scored."
    return text


def evaluate(name: str, curve: Curve, **settings) -> float:
    """metric `name` of `curve` (`pool=` the page's curves for a pooled one); an unknown name is an error that lists the known ones."""
    from runner.errors import HeimdallError
    name = resolve(name)
    if name not in REGISTRY:
        raise HeimdallError(f"no metric '{name}'", hint="metrics: " + ", ".join(REGISTRY))
    return REGISTRY[name](curve, **settings)
