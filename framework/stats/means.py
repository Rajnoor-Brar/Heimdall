"""The means: how many numbers become one, and (for set-merge) how many histograms become one.

`REGISTRY` maps a name to a `Mean`. A scalar mean takes values `x` and weights `w` (positive, any sum: they are
normalised here) and returns one number; its `error` takes the values' errors `sx` too and returns the result's. An
ensemble mean (`kind = "ensemble"`) takes K histograms on shared bin edges and returns one density per bin.

`error_kind` says how far an error can be trusted: "exact" (linear: independent errors in quadrature), "first order" (the
gradient of a smooth mean, the same propagation), "approximate" (a robust mean has no formula: the spread of 200 draws of
the inputs within their errors, seeded, so the number is repeatable).

A mean that cannot work on its input says so with a `HeimdallError` and a hint (a trimmed mean with nothing to trim, a
harmonic mean of a zero with no floor), not with a number. NaN values and non-positive weights are left out first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from runner.errors import HeimdallError

EPS = 1e-15
DRAWS = 200            # inputs drawn within their errors for an approximate error
SEED = 20261107


# ── inputs ────────────────────────────────────────────────────────────────────────────────────

def _clean(x, w=None, sx=None):
    """(x, w̃, sx) as float arrays of the finite values with a positive weight, w̃ summing to 1; None when nothing is left."""
    x = np.atleast_1d(np.asarray(x, dtype=float))
    w = np.ones_like(x) if w is None else np.atleast_1d(np.asarray(w, dtype=float))
    sx = None if sx is None else np.atleast_1d(np.asarray(sx, dtype=float))
    keep = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not keep.any():
        return None
    w = w[keep] / np.sum(w[keep])
    return x[keep], w, (None if sx is None else np.nan_to_num(sx[keep]))


def _floor(x: np.ndarray, floor: float | None, name: str) -> np.ndarray:
    if floor is not None:
        return np.maximum(x, floor)
    if np.any(x <= 0):
        raise HeimdallError(f"the {name} mean needs every value above zero", hint="give a floor (the smallest value that counts), or use a mean that takes zeros")
    return x


def wquantile(x, w, q: float) -> float:
    """The weighted quantile q: the points sit at (cumulative weight − half its own) and are interpolated, which for equal
    weights is the usual median at q = 0.5 and Hazen's quartile at 0.25 and 0.75."""
    order = np.argsort(x, kind="stable")
    xs, ws = np.asarray(x)[order], np.asarray(w)[order]
    return float(np.interp(q, np.cumsum(ws) - ws / 2, xs))


def _trim_weights(x, w, alpha: float, name: str):
    """(x sorted, the weights left after cutting weight mass alpha from each end, boundary values fractionally)."""
    if not 0 <= alpha < 0.5:
        raise HeimdallError(f"{name}: alpha must be from 0 up to (not including) 0.5", hint=f"got {alpha}")
    if alpha > 0 and math.floor(alpha * len(x) + 1e-9) < 1:
        raise HeimdallError(f"{name} with alpha {alpha} trims nothing from {len(x)} values", hint=f"it needs at least {math.ceil(1 / alpha)} values; use a smaller alpha, or the median or linear mean")
    order = np.argsort(x, kind="stable")
    xs, ws = x[order], w[order]
    hi = np.cumsum(ws)
    lo = hi - ws
    kept = np.clip(np.minimum(hi, 1 - alpha) - np.maximum(lo, alpha), 0.0, None)
    return xs, kept


# ── the power means ───────────────────────────────────────────────────────────────────────────

def power_mean(x, w=None, p: float = 1.0, floor: float | None = None) -> float:
    """(Σ w·x^p / Σ w)^(1/p), weighted. p = 1 is the plain mean and may take signed values; an even integer p is
    sign-free; a cubic or any odd integer p keeps the sign; other p > 0 needs x ≥ 0. p ≤ 0 needs x > 0 (or a `floor`);
    p = 0 is the geometric mean (in log space); ±∞ is the largest and smallest. Scaled by the largest value (or the
    smallest, for p < 0) so a big value or a high p does not overflow. NaN values are left out; none left is NaN."""
    c = _clean(x, w)
    if c is None:
        return math.nan
    x, w, _ = c
    if p == math.inf:
        return float(np.max(x))
    if p == -math.inf:
        return float(np.min(x))
    if p == 0 or p < 0:
        x = _floor(x, floor, "geometric" if p == 0 else "harmonic" if p == -1 else "negative-power")
        if p == 0:
            return float(math.exp(np.sum(w * np.log(x))))
        low = float(np.min(x))
        return low * float(np.sum(w * (x / low) ** p)) ** (1.0 / p)
    odd = float(p).is_integer() and int(p) % 2 == 1
    if not odd and not float(p).is_integer() and np.any(x < 0):
        raise HeimdallError(f"the power mean with p = {p} needs values of zero or more", hint="use an integer p, or take |x| first")
    top = float(np.max(np.abs(x)))
    if top == 0:
        return 0.0
    terms = (np.abs(x) / top) ** p * (np.sign(x) if odd or p == 1 else 1.0)
    total = float(np.sum(w * terms))
    return top * math.copysign(abs(total) ** (1.0 / p), total) if p != 1 else top * total


def power_error(x, sx, w=None, p: float = 1.0, floor: float | None = None) -> float:
    """The first-order error of `power_mean` from independent errors sx: √Σ (∂M/∂x_i · σ_i)², the gradient being
    w_i·x_i^(p−1)/M^(p−1) (geometric: w_i·M/x_i; the largest and smallest: the error of the one value that is it)."""
    c = _clean(x, w, sx)
    if c is None:
        return math.nan
    x, w, sx = c
    if p in (math.inf, -math.inf):
        return float(sx[int(np.argmax(x) if p > 0 else np.argmin(x))])
    mean = power_mean(x, w, p, floor)
    if p <= 0:
        x = _floor(x, floor, "geometric" if p == 0 else "harmonic")
    if p == 0:
        grad = w * mean / x
    elif p == 1:
        grad = w
    elif mean == 0:
        return 0.0
    else:
        grad = w * np.abs(x) ** (p - 1) / abs(mean) ** (p - 1)
        if p > 0 and float(p).is_integer() and int(p) % 2 == 0:
            grad = grad * np.sign(x)
    return float(np.sqrt(np.sum((grad * sx) ** 2)))


def lehmer(x, w=None, p: float = 2.0) -> float:
    """Σ w·x^p / Σ w·x^(p−1) (p = 2 is the contraharmonic mean; p = 1 the linear; p = 0 the harmonic): the mean
    weighted by its own values, so no root. Non-negative values with a positive sum."""
    c = _clean(x, w)
    if c is None:
        return math.nan
    x, w, _ = c
    if np.any(x < 0):
        raise HeimdallError("the Lehmer mean needs values of zero or more", hint="a signed value can cancel its sum; use the linear mean")
    top = float(np.max(x))
    if top == 0:
        return 0.0
    r = x / top
    with np.errstate(divide="ignore", invalid="ignore"):
        num, den = np.sum(w * r**p), np.sum(w * r ** (p - 1))
    if not np.isfinite(den) or den <= 0:
        raise HeimdallError(f"the Lehmer mean with p = {p} divides by zero on these values", hint="a zero value with p ≤ 1 has no weight; drop it or raise p")
    return top * float(num / den)


def lehmer_error(x, sx, w=None, p: float = 2.0) -> float:
    c = _clean(x, w, sx)
    if c is None:
        return math.nan
    x, w, sx = c
    value = lehmer(x, w, p)
    den = float(np.sum(w * x ** (p - 1)))
    grad = w * (p * x ** (p - 1) - (p - 1) * value * x ** (p - 2)) / den
    return float(np.sqrt(np.sum((grad * sx) ** 2)))


def logsumexp(x, w=None, beta: float = 1.0) -> float:
    """(1/β) ln Σ w·e^(βx): the soft maximum (β → ∞ the largest, β → 0 the linear mean, β < 0 the soft minimum).
    Shifted by the extreme value, so it does not overflow."""
    c = _clean(x, w)
    if c is None:
        return math.nan
    x, w, _ = c
    if beta == 0:
        return float(np.sum(w * x))
    m = float(np.max(x) if beta > 0 else np.min(x))
    return m + math.log(float(np.sum(w * np.exp(beta * (x - m))))) / beta


def logsumexp_error(x, sx, w=None, beta: float = 1.0) -> float:
    c = _clean(x, w, sx)
    if c is None:
        return math.nan
    x, w, sx = c
    if beta == 0:
        return float(np.sqrt(np.sum((w * sx) ** 2)))
    soft = w * np.exp(beta * (x - (np.max(x) if beta > 0 else np.min(x))))
    return float(np.sqrt(np.sum((soft / np.sum(soft) * sx) ** 2)))


# ── the order-statistic means ─────────────────────────────────────────────────────────────────

def median(x, w=None) -> float:
    c = _clean(x, w)
    return math.nan if c is None else wquantile(c[0], c[1], 0.5)


def trimmed(x, w=None, alpha: float = 0.25) -> float:
    """The mean after cutting weight alpha from each end of the sorted values (a boundary value fractionally): the
    interquartile mean at 0.25. Needs alpha·K ≥ 1 or it trims nothing."""
    c = _clean(x, w)
    if c is None:
        return math.nan
    xs, kept = _trim_weights(c[0], c[1], alpha, "the trimmed mean")
    return float(np.sum(kept * xs) / np.sum(kept))


def trimmed_geometric(x, w=None, alpha: float = 0.25, floor: float | None = None) -> float:
    """The geometric mean of what a trimmed mean keeps: rejects spikes and keeps the average log slope. A zero among
    the kept values needs a `floor`."""
    c = _clean(x, w)
    if c is None:
        return math.nan
    xs, kept = _trim_weights(c[0], c[1], alpha, "the trimmed geometric mean")
    xs = _floor(xs[kept > 0], floor, "trimmed geometric")
    kept = kept[kept > 0]
    return float(math.exp(np.sum(kept * np.log(xs)) / np.sum(kept)))


def winsorized(x, w=None, alpha: float = 0.25) -> float:
    """The mean with the lowest and highest weight alpha clamped to the nearest value kept, instead of dropped."""
    c = _clean(x, w)
    if c is None:
        return math.nan
    x, w, _ = c
    _trim_weights(x, w, alpha, "the winsorized mean")
    order = np.argsort(x, kind="stable")
    xs, ws = x[order], w[order]
    cum = np.cumsum(ws)
    lo = xs[min(int(np.searchsorted(cum, alpha + 1e-12, side="right")), len(xs) - 1)]
    hi = xs[min(int(np.searchsorted(cum, 1 - alpha - 1e-12, side="left")), len(xs) - 1)]
    return float(np.sum(ws * np.clip(xs, lo, hi)))


def _quartiles(x, w, name: str):
    c = _clean(x, w)
    if c is None:
        return None
    if len(c[0]) < 4:
        raise HeimdallError(f"the {name} needs at least 4 values", hint=f"got {len(c[0])}; use the median or the linear mean")
    return tuple(wquantile(c[0], c[1], q) for q in (0.25, 0.5, 0.75))


def midhinge(x, w=None) -> float:
    q = _quartiles(x, w, "midhinge")
    return math.nan if q is None else (q[0] + q[2]) / 2


def trimean(x, w=None) -> float:
    q = _quartiles(x, w, "trimean")
    return math.nan if q is None else (q[0] + 2 * q[1] + q[2]) / 4


def hodges_lehmann(x, w=None) -> float:
    """The median of all pair averages (x_i + x_j)/2, i ≤ j: 95 % Gaussian efficiency and 29 % breakdown, for small K.
    It has no weights: unequal weights are refused, not ignored."""
    c = _clean(x, w)
    if c is None:
        return math.nan
    x, w, _ = c
    if not np.allclose(w, w[0]):
        raise HeimdallError("the Hodges–Lehmann mean has no weights", hint="use the median, a trimmed mean or Huber, which take them")
    if len(x) > 1000:
        raise HeimdallError(f"the Hodges–Lehmann mean compares every pair: {len(x)} values is too many", hint="use at most 1000, or the median")
    i, j = np.triu_indices(len(x))
    return float(np.median((x[i] + x[j]) / 2))


def _m_estimate(x, w, kind: str) -> float:
    """Huber (c = 1.345) or Tukey bisquare (c = 4.685) location by IRLS from the median, scale 1.4826·MAD (0.7413·IQR where
    the MAD is zero; the median itself where both are), 30 iterations or a step under 1e-6 of the scale."""
    mu = wquantile(x, w, 0.5)
    s = 1.4826 * wquantile(np.abs(x - mu), w, 0.5)
    if s < EPS:
        s = 0.7413 * (wquantile(x, w, 0.75) - wquantile(x, w, 0.25))
    if s < EPS:
        return mu
    c = 1.345 if kind == "huber" else 4.685
    for _ in range(30):
        u = np.abs(x - mu) / s
        if kind == "huber":
            r = np.where(u <= c, 1.0, c / np.maximum(u, EPS))
        else:
            r = np.where(u <= c, (1 - (u / c) ** 2) ** 2, 0.0)
        total = float(np.sum(w * r))
        if total <= EPS:
            return mu
        new = float(np.sum(w * r * x) / total)
        done = abs(new - mu) <= 1e-6 * s
        mu = new
        if done:
            break
    return mu


def huber(x, w=None) -> float:
    """Huber's M-estimate: the mean in the core, the median-like pull in the tails (95 % Gaussian efficiency)."""
    c = _clean(x, w)
    return math.nan if c is None else _m_estimate(c[0], c[1], "huber")


def tukey(x, w=None) -> float:
    """Tukey's bisquare M-estimate: a value beyond 4.685 scales is rejected outright. May not converge from a bad start."""
    c = _clean(x, w)
    return math.nan if c is None else _m_estimate(c[0], c[1], "tukey")


# ── errors ────────────────────────────────────────────────────────────────────────────────────

def drawn_error(fn: Callable, x, sx, w=None, **settings) -> float:
    """The spread of `fn` over 200 draws of x within sx (seeded, so the same answer twice): the error of a mean with no
    formula. An approximation, and a rough one under 10 values."""
    c = _clean(x, w, sx)
    if c is None:
        return math.nan
    x, wn, sx = c
    rng = np.random.default_rng(SEED)
    values = [fn(x + sx * rng.standard_normal(len(x)), wn, **settings) for _ in range(DRAWS)]
    return float(np.std(values, ddof=1))


# ── ensembles of histograms ───────────────────────────────────────────────────────────────────

def _ensemble(edges, f, w):
    edges = np.asarray(edges, dtype=float)
    f = np.atleast_2d(np.asarray(f, dtype=float))
    if f.shape[1] != len(edges) - 1:
        raise HeimdallError("the histograms do not share the bin edges", hint=f"{f.shape[1]} bins against {len(edges) - 1} edges + 1")
    if len(f) < 2:
        raise HeimdallError("an ensemble mean needs at least 2 histograms")
    if np.any(f < 0) or not np.all(np.isfinite(f)):
        raise HeimdallError("an ensemble mean needs every density finite and zero or more", hint="a negative bin has no place in a distribution")
    w = np.ones(len(f)) if w is None else np.asarray(w, dtype=float)
    return edges, f, w / np.sum(w), np.diff(edges)


def _sides(c, edges, levels):
    """(left, right) quantiles of a member at the CDF `levels`. Strictly inside a segment of the CDF they are the same
    point; where a level sits on a plateau (a gap with no mass) the left is the gap's start and the right its end, so
    that the barycentre keeps a gap a gap."""
    n = len(c)
    j = np.minimum(np.searchsorted(c, levels, side="left"), n - 1)
    k = np.searchsorted(c, levels, side="right") - 1
    exact = c[j] == levels
    prev = np.maximum(j - 1, 0)
    span = np.where(c[j] > c[prev], c[j] - c[prev], 1.0)
    inside = edges[prev] + (levels - c[prev]) / span * (edges[j] - edges[prev])
    return np.where(exact, edges[j], inside), np.where(exact, edges[np.maximum(k, 0)], inside)


def wasserstein(edges, f, w=None, loc: str = "linear", grid: int = 1000) -> np.ndarray:
    """The W₂ (quantile) barycentre of K densities on shared edges: each member's quantile function at `grid` + 1 even
    levels and at every CDF value the members have at an edge, `loc` (a scalar mean) taken across members at each level,
    and the barycentre's CDF read back at the edges. For the linear mean this is exact (the mean of piecewise-linear
    quantile functions is piecewise linear, with its breakpoints among those levels); for the others the grid approximates.
    Shapes move (a peak that shifts stays one peak) where the bin-wise mean smears; the yield is the linear mean of the
    members' yields, since the shape alone is a distribution."""
    edges, f, w, dx = _ensemble(edges, f, w)
    mass = f * dx
    area = mass.sum(axis=1)
    if np.any(area <= 0):
        raise HeimdallError("the Wasserstein mean needs every histogram to have some yield")
    cdf = np.concatenate([np.zeros((len(f), 1)), np.cumsum(mass / area[:, None], axis=1)], axis=1)
    cdf[:, -1] = 1.0
    levels = np.unique(np.clip(np.concatenate([np.linspace(0.0, 1.0, grid + 1), cdf.ravel()]), 0.0, 1.0))
    sides = [_sides(c, edges, levels) for c in cdf]
    if loc == "linear":
        around = [w @ np.array([s[i] for s in sides]) for i in (0, 1)]
    else:
        mean = MEANS_BY_NAME[loc]
        around = [np.array([mean(np.array([s[i][m] for s in sides]), w) for m in range(len(levels))]) for i in (0, 1)]
    xs = np.maximum.accumulate(np.column_stack(around).ravel())
    us = np.repeat(levels, 2)
    fbar = np.interp(edges, xs, us)
    p = np.clip(np.diff(np.clip(fbar, 0.0, 1.0)), 0.0, None)
    if p.sum() <= 0:
        raise HeimdallError("the Wasserstein barycentre has no mass on these edges")
    return float(w @ area) * p / p.sum() / dx


def scale_aligned(edges, f, w=None, loc: str = "huber") -> np.ndarray:
    """Each histogram's axis is rescaled so its mean position equals the consensus (`loc` of the members' mean positions), its
    mass is rebinned onto the original bins by overlap, the bins are averaged bin by bin with `loc`, and the result is
    renormalised to the linear mean of the members' yields. For members that differ in scale (a width that varies) more than
    in shape. Needs positive mean positions."""
    edges, f, w, dx = _ensemble(edges, f, w)
    mass = f * dx
    area = mass.sum(axis=1)
    if np.any(area <= 0):
        raise HeimdallError("the scale-aligned mean needs every histogram to have some yield")
    centres = (edges[:-1] + edges[1:]) / 2
    pos = (mass * centres).sum(axis=1) / area
    if np.any(pos <= 0):
        raise HeimdallError("the scale-aligned mean needs every histogram's mean position above zero", hint="shift the axis, or use the bin-wise mean")
    consensus = MEANS_BY_NAME[loc](pos, w)
    aligned = np.empty_like(mass)
    for k in range(len(f)):
        moved = edges * (consensus / pos[k])
        overlap = np.clip(np.minimum(edges[1:, None], moved[None, 1:]) - np.maximum(edges[:-1, None], moved[None, :-1]), 0.0, None)
        aligned[k] = overlap @ (mass[k] / area[k] / np.maximum(np.diff(moved), EPS))
    bins = np.array([MEANS_BY_NAME[loc](aligned[:, b], w) for b in range(aligned.shape[1])])
    if bins.sum() <= 0:
        raise HeimdallError("the scale-aligned mean has no mass on these edges")
    return float(w @ area) * bins / bins.sum() / dx


def members_error(edges, f, sf, w=None, result=None, **_) -> np.ndarray:
    """The error of an ensemble mean: the result times the weighted mean relative error of the members in that bin. No exact
    error exists for a transport mean; this one says how well the members were measured."""
    edges, f, w, dx = _ensemble(edges, f, w)
    sf = np.asarray(sf, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.where(f > 0, np.nan_to_num(sf) / f, 0.0)
    return np.asarray(result) * (w @ rel)


# ── the registry ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Mean:
    name: str
    fn: Callable
    error: Callable
    guard: str = ""
    note: str = ""
    kind: str = "scalar"                      # "scalar", or "ensemble": histograms on shared edges, one density out
    error_kind: str = "exact"                 # "exact", "first order", "approximate"
    settings: tuple = field(default_factory=tuple)   # the keywords it takes, with defaults in its function

    def __call__(self, *args, **settings):
        return self.fn(*args, **settings)


def _scalar(name, fn, error, guard, note, error_kind="approximate", settings=(), **fixed) -> Mean:
    """A scalar Mean with `fixed` settings bound; the rest are passed through."""
    call = (lambda x, w=None, **s: fn(x, w, **{**fixed, **s})) if fixed else fn
    err = error if error is not None else (lambda x, sx, w=None, **s: drawn_error(fn, x, sx, w, **{**fixed, **s}))
    if error is not None and fixed:
        err = lambda x, sx, w=None, **s: error(x, sx, w, **{**fixed, **s})
    return Mean(name, call, err, guard, note, "scalar", error_kind, settings)


REGISTRY: dict[str, Mean] = {m.name: m for m in (
    _scalar("linear", power_mean, power_error, "any real values",
            "every page counts by its value: a few bad pages are averaged away", "exact", p=1.0),
    _scalar("rms", power_mean, power_error, "any real values",
            "large values count more: one bad page shows (docs/live/stats-rms.md)", "first order", p=2.0),
    _scalar("cubic", power_mean, power_error, "any real values",
            "cubes the values: dominated by the worst one or two; keeps the sign", "first order", p=3.0),
    _scalar("geometric", power_mean, power_error, "values above zero, or a `floor`",
            "the mean of the logs: a ratio and its inverse cancel; one zero sets the result to the floor", "first order", ("floor",), p=0.0),
    _scalar("harmonic", power_mean, power_error, "values above zero, or a `floor`",
            "dominated by the smallest value: the mean of the best, not the worst", "first order", ("floor",), p=-1.0),
    _scalar("min", power_mean, power_error, "any real values",
            "the best value alone: ignores every other", "first order", p=-math.inf),
    _scalar("max", power_mean, power_error, "any real values",
            "the worst value alone (the minimax norm): ignores every other", "first order", p=math.inf),
    _scalar("power", power_mean, power_error, "p > 0 needs values ≥ 0 unless p is an integer; p ≤ 0 needs values > 0 or a `floor`",
            "the family: p = 1 linear, 2 rms, 3 cubic, 0 geometric, -1 harmonic; a higher p lets the worst values count more", "first order", ("p", "floor")),
    _scalar("lehmer", lehmer, lehmer_error, "values ≥ 0 with a positive sum",
            "weighted by its own values: a large value counts more, without a root; a zero is ignored (p ≥ 1)", "first order", ("p",)),
    _scalar("contraharmonic", lehmer, lehmer_error, "values ≥ 0 with a positive sum",
            "the mean plus variance over mean: pulled up by a spread; unstable if the sum nears zero", "first order", p=2.0),
    _scalar("logsumexp", logsumexp, logsumexp_error, "any real values",
            "the soft maximum: beta sets how much the worst counts (large: the maximum, 0: the linear mean)", "first order", ("beta",)),
    _scalar("median", median, None, "any real values",
            "the middle value: half the values can be wrong; blind to how wrong the rest are, and steps rather than slides"),
    _scalar("trimmed", trimmed, None, "alpha < 0.5 and alpha·K ≥ 1 (4 values at the default 0.25)",
            "the mean after cutting the highest and lowest alpha: robust to a few bad values, a little biased by a skewed set", settings=("alpha",)),
    _scalar("trimmed_geometric", trimmed_geometric, None, "alpha < 0.5, alpha·K ≥ 1, values above zero or a `floor`",
            "the geometric mean of what is kept: rejects spikes and keeps the average log slope; fails if all that is kept is zero", settings=("alpha", "floor")),
    _scalar("winsorized", winsorized, None, "alpha < 0.5 and alpha·K ≥ 1",
            "the extremes clamped to the nearest kept value instead of dropped: robust, and still counts that they were there", settings=("alpha",)),
    _scalar("midhinge", midhinge, None, "at least 4 values",
            "the average of the quartiles: robust to the outer half; ignores the middle's shape"),
    _scalar("trimean", trimean, None, "at least 4 values",
            "Tukey: the quartiles and the median, 1:2:1; robust and smoother than the median"),
    _scalar("hodges_lehmann", hodges_lehmann, None, "equal weights; at most 1000 values",
            "the median of the pair averages: 95 % efficient and 29 % breakdown, for small sets; has no weights"),
    _scalar("huber", huber, None, "any real values; scale from the MAD, else the IQR, else the median",
            "the mean in the core, the median in the tails; stops at a spike; its scale is a guess under 5 values"),
    _scalar("tukey", tukey, None, "any real values; scale from the MAD, else the IQR, else the median",
            "rejects a value beyond 4.7 scales outright; can lose to the median if started badly; its scale is a guess under 5 values"),
    Mean("wasserstein", wasserstein, members_error,
         "at least 2 histograms on shared edges, densities ≥ 0, each with some yield",
         "moves a shifted peak instead of smearing it; the yield is the linear mean of the members'; no exact error exists",
         "ensemble", "approximate", ("loc", "grid")),
    Mean("scale_aligned", scale_aligned, members_error,
         "at least 2 histograms on shared edges, densities ≥ 0, mean positions above zero",
         "for members that differ in scale more than in shape; rebins by overlap; no exact error exists",
         "ensemble", "approximate", ("loc",)),
)}

MEANS_BY_NAME = {name: m for name, m in REGISTRY.items() if m.kind == "scalar"}


def evaluate(name: str, x, w=None, **settings) -> float:
    """scalar mean `name` of x; an unknown name is an error that lists the known ones."""
    if name not in MEANS_BY_NAME:
        raise HeimdallError(f"no mean '{name}'", hint="means: " + ", ".join(MEANS_BY_NAME))
    return MEANS_BY_NAME[name](x, w, **settings)
