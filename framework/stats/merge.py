"""Merging curves (set-merge): the numbers of a merge, bin by bin. No file is read here (framework/plot/figures/curves.py does).

`merged_bins` takes K members' values and errors in each of B bins (K × B arrays) and a mean of `stats.means.REGISTRY`: a
scalar mean is applied to each bin's K values, an ensemble mean (`wasserstein`, `scale_aligned`) to the members' densities as
histograms on shared edges; each returns the value and the error by the mean's own rule. `band_edges` gives the envelope
drawn around a merged curve: the members' lowest and highest value in each bin, or the mean less and plus one standard
deviation. Statistical pooling (`how = "combine"`) is rivet-merge's, not this module's.
"""

from __future__ import annotations

import numpy as np

from runner.errors import HeimdallError

from . import means

BANDS = ("minmax", "std")


def merged_bins(how: str, edges, values: np.ndarray, errs: np.ndarray, weights=None, settings: dict | None = None):
    """(value, error) of each bin after the mean `how`: `values` and `errs` are K × B arrays, one row a member."""
    mean = means.REGISTRY.get(how)
    if mean is None:
        raise HeimdallError(f"no mean '{how}'", hint="means: " + ", ".join(means.REGISTRY))
    settings = dict(settings or {})
    unknown = sorted(set(settings) - set(mean.settings))
    if unknown:
        raise HeimdallError(f"the {how} mean takes no setting '{unknown[0]}'", hint=("its settings: " + ", ".join(mean.settings)) if mean.settings else f"{how} has none")
    if mean.kind == "ensemble":
        value = np.asarray(mean(edges, values, weights, **settings), dtype=float)
        return value, np.asarray(mean.error(edges, values, errs, weights, result=value, **settings), dtype=float)
    value = np.empty(values.shape[1])
    err = np.empty(values.shape[1])
    for b in range(values.shape[1]):
        try:
            value[b] = mean(values[:, b], weights, **settings)
            err[b] = mean.error(values[:, b], errs[:, b], weights, **settings)
        except HeimdallError as error:
            raise HeimdallError(f"{error.args[0] if error.args else error} (bin {b + 1})", hint=getattr(error, "hint", None)) from None
    return value, err


def band_edges(values: np.ndarray, kind: str = "minmax") -> tuple[np.ndarray, np.ndarray]:
    """(low, high) of each bin of the K × B `values`: the members' lowest and highest (`kind` "minmax"), or the mean less and
    plus one sample standard deviation ("std": 3 members at least, for two have no spread worth drawing)."""
    if kind not in BANDS:
        raise HeimdallError(f"a band is one of {', '.join(BANDS)}", hint=f"got {kind!r}")
    if kind == "std":
        if len(values) < 3:
            raise HeimdallError(f"band = \"std\" needs at least 3 curves, and this merges {len(values)}", hint='band = "minmax" draws the envelope of two')
        centre, spread = np.nanmean(values, axis=0), np.nanstd(values, axis=0, ddof=1)
        return centre - spread, centre + spread
    return np.nanmin(values, axis=0), np.nanmax(values, axis=0)
