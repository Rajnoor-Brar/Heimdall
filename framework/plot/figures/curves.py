"""Merged curves as YODA files (set-merge): read the members, write the merge (plot.py loads this beside derive.py).

`merge_yoda` keeps the 1D estimates every file has (the objects a page draws: not /RAW, not /TMP, not the counters), refuses
binnings that differ naming the first object and edge, and writes one file whose bins are `stats.merge.merged_bins`. Errors are
written symmetric: the mean of the lower and upper totals. `band_yoda` writes the two files whose objects are the envelope drawn
around a merged curve (`stats.merge.band_edges`). Statistical pooling (`how = "combine"`) is rivet-merge's.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from runner.errors import HeimdallError
from stats import merge as numbers

SKIPPED = ("/RAW/", "/TMP/")
COUNTERS = ("/_XSEC", "/_EVTCOUNT")


def _yoda():
    try:
        import yoda
    except ImportError:
        raise HeimdallError("merging curves needs YODA's Python", hint="source gjallarhorn.sh: the stack has it") from None
    return yoda


def _estimate(ao):
    """A binned 1D object as an estimate (a histogram is converted); None for anything else."""
    name = type(ao).__name__
    if name == "BinnedEstimate1D":
        return ao
    if name == "BinnedHisto1D":
        return ao.mkEstimate()
    return None


def read_curves(path) -> dict:
    """{object path: its estimate} of a YODA file's 1D objects: not /RAW or /TMP, not the counters, not a variation's."""
    out = {}
    for name, ao in _yoda().read(str(path)).items():
        if name.startswith(SKIPPED) or name in COUNTERS or name.endswith("]"):
            continue
        if (estimate := _estimate(ao)) is not None:
            out[name] = estimate
    return out


def _shared(sources: list, curves: list[dict]) -> list[str]:
    """The objects every file has, in the first file's order, their bins' edges equal; the first difference refused."""
    shared = [p for p in curves[0] if all(p in c for c in curves[1:])]
    if not shared:
        raise HeimdallError("these curves share no 1D object to merge", hint="the points were not run with the same analyses: "
                            + ", ".join(Path(s).parent.name or str(s) for s in sources[:4]))
    for path in shared:
        edges = [np.asarray(c[path].xEdges(), dtype=float) for c in curves]
        for source, e in zip(sources[1:], edges[1:]):
            if len(e) != len(edges[0]) or not np.allclose(e, edges[0], rtol=1e-9, atol=0.0):
                where = next((i for i, (a, b) in enumerate(zip(edges[0], e)) if not math.isclose(a, b, rel_tol=1e-9)), min(len(e), len(edges[0])))
                raise HeimdallError(f"{path} is binned differently in {source}: {len(e) - 1} bins against {len(edges[0]) - 1}"
                                    f", the first difference at edge {where}",
                                    hint="curves merge bin by bin: run the points with one binning")
    return shared


def _bins(ao) -> tuple[np.ndarray, np.ndarray]:
    """(values, symmetric errors) of an estimate's bins."""
    bins = ao.bins()
    value = np.array([b.val() for b in bins], dtype=float)
    err = np.array([(b.totalErrPos() - b.totalErrNeg()) / 2 for b in bins], dtype=float)
    return value, err


def _set(ao, value: np.ndarray, err: np.ndarray) -> None:
    for b, v, e in zip(ao.bins(), value, err):
        b.setVal(float(v))
        b.setErr((-float(e), float(e)))


def _write(objects: list, target) -> None:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.stem + ".partial" + target.suffix)
    _yoda().write(objects, str(partial))
    partial.replace(target)


def merge_yoda(sources: list, target, how: str = "linear", settings: dict | None = None, weights=None) -> list[str]:
    """`sources` (YODA files) merged into `target` by the mean `how` (a name of `stats.means.REGISTRY`) with its `settings`,
    the members weighted equally unless `weights` say otherwise; the objects merged."""
    if len(sources) < 2:
        raise HeimdallError("merging needs at least two curves")
    curves = [read_curves(s) for s in sources]
    shared = _shared(sources, curves)
    made = []
    for path in shared:
        parts = [_bins(c[path]) for c in curves]
        edges = np.asarray(curves[0][path].xEdges(), dtype=float)
        try:
            value, err = numbers.merged_bins(how, edges, np.array([p[0] for p in parts]), np.array([p[1] for p in parts]), weights, settings)
        except HeimdallError as error:
            raise HeimdallError(f"{path}: {error.args[0] if error.args else error}", hint=getattr(error, "hint", None)) from None
        ao = curves[0][path].clone()
        _set(ao, value, err)
        made.append(ao)
    _write(made, target)
    return shared


def band_yoda(sources: list, low, high, kind: str = "minmax") -> list[str]:
    """The envelope around the merge of `sources`, as two files, `low` and `high`, of the same objects (errors zero)."""
    curves = [read_curves(s) for s in sources]
    shared = _shared(sources, curves)
    lows, highs = [], []
    for path in shared:
        lo, hi = numbers.band_edges(np.array([_bins(c[path])[0] for c in curves]), kind)
        for side, out in ((lo, lows), (hi, highs)):
            ao = curves[0][path].clone()
            _set(ao, side, np.zeros_like(side))
            out.append(ao)
    _write(lows, low)
    _write(highs, high)
    return shared
