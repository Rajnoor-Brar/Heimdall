"""The means: how many numbers become one. The power mean is the family: p = 1 linear, p = 2 root mean square.

`REGISTRY` maps a name to a `Mean`: its function (values, weights → value), the rule that carries the values' errors
into the result's, the guard on what it accepts, and a note on what it hides. Weights are positive and need not sum
to 1; they are normalised here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np


def power_mean(x, w=None, p: float = 1.0) -> float:
    """(Σ w·|x|^p / Σ w)^(1/p) for p > 0, scaled by the largest |x| so a large value or a high p does not overflow.
    NaN values are left out; nothing left, or no weight, is NaN."""
    x = np.asarray(x, dtype=float)
    w = np.ones_like(x) if w is None else np.asarray(w, dtype=float)
    keep = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not keep.any():
        return math.nan
    x, w = np.abs(x[keep]), w[keep] / np.sum(w[keep])
    top = float(np.max(x))
    if top == 0:
        return 0.0
    return top * float(np.sum(w * (x / top) ** p)) ** (1.0 / p)


def power_error(x, sx, w=None, p: float = 1.0) -> float:
    """The error of power_mean from independent errors sx of x: √Σ (w·|x|^(p−1)·σ)² / (M^(p−1)) with w normalised."""
    x, sx = np.asarray(x, dtype=float), np.asarray(sx, dtype=float)
    w = np.ones_like(x) if w is None else np.asarray(w, dtype=float)
    keep = np.isfinite(x) & np.isfinite(sx) & np.isfinite(w) & (w > 0)
    if not keep.any():
        return math.nan
    x, sx, w = np.abs(x[keep]), sx[keep], w[keep] / np.sum(w[keep])
    mean = power_mean(x, w, p)
    if mean == 0:
        return float(np.sqrt(np.sum((w * sx) ** 2))) if p == 1 else 0.0
    return float(np.sqrt(np.sum((w * x ** (p - 1) * sx) ** 2))) / mean ** (p - 1)


@dataclass(frozen=True)
class Mean:
    name: str
    fn: Callable[..., float]
    error: Callable[..., float]
    guard: str = ""
    note: str = ""

    def __call__(self, x, w=None) -> float:
        return self.fn(x, w)


REGISTRY: dict[str, Mean] = {m.name: m for m in (
    Mean("linear", lambda x, w=None: power_mean(x, w, 1.0), lambda x, sx, w=None: power_error(x, sx, w, 1.0),
         guard="any real values (the mean of |x|; losses are non-negative)", note="every page counts by its value: a few bad pages are averaged away"),
    Mean("rms", lambda x, w=None: power_mean(x, w, 2.0), lambda x, sx, w=None: power_error(x, sx, w, 2.0),
         guard="any real values", note="large values count more: one bad page shows (docs/live/stats-rms.md)"),
)}
