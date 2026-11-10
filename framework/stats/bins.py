"""A page's measured bins as arrays (rank: stats). Paint's `measured` rows, one `Curve` per curve of the page."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from runner.errors import HeimdallError


@dataclass(frozen=True)
class Curve:
    """The bins one curve was compared on, against the page's reference: (lo, hi, y, err, ref_y, ref_err) per bin,
    the curve rebinned onto the reference's edges, in x order. `logx`: the page's x axis is logarithmic, so a
    bin's drawn width and centre are in log10 x (as Paint's ratio sums are). `reference`: this is the page's
    first curve, being its own reference. `normalised`: the page is drawn normalised, so a yield is not a cross-section."""

    lo: np.ndarray
    hi: np.ndarray
    y: np.ndarray
    err: np.ndarray
    ref_y: np.ndarray
    ref_err: np.ndarray
    logx: bool = False
    reference: bool = False
    normalised: bool = False

    @property
    def n(self) -> int:
        return len(self.lo)

    @property
    def width(self) -> np.ndarray:
        """hi − lo: what areas are summed with (Paint's `w`), on a log axis too."""
        return self.hi - self.lo

    @property
    def drawn(self) -> np.ndarray:
        """A bin's width as the page draws it: hi − lo, or log10(hi/lo) on a log-x page (0 where lo ≤ 0)."""
        if not self.logx:
            return self.width
        with np.errstate(divide="ignore", invalid="ignore"):
            out = np.log10(self.hi / self.lo)
        return np.where((self.lo > 0) & np.isfinite(out), out, 0.0)

    @property
    def edges(self) -> tuple[np.ndarray, np.ndarray]:
        """The bin edges in drawn x (log10 on a log-x page; a non-positive edge there is NaN)."""
        if not self.logx:
            return self.lo, self.hi
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.log10(np.where(self.lo > 0, self.lo, np.nan)), np.log10(np.where(self.hi > 0, self.hi, np.nan))

    @property
    def span(self) -> float:
        """The axis span in drawn x, first edge to last."""
        a, b = self.edges
        return float(b[-1] - a[0]) if self.n else float("nan")


def curves(made: dict, logx: bool = False, normalised: bool = False) -> list[Curve]:
    """The curves of one page's stats.json (already parsed). A curve with no `measured` (a file written before
    Paint did) is refused: the numbers cannot be made from totals."""
    out = []
    for i, curve in enumerate(made.get("curves", [])):
        if "measured" not in curve:
            raise HeimdallError("this page's statistics have no measured bins (written by an older Paint)",
                           hint="draw the page again (heimdall plot), which writes them")
        rows = np.array([[np.nan if v is None else v for v in row] for row in curve["measured"]], dtype=float).reshape(-1, 6)
        out.append(Curve(*(rows[:, k] for k in range(6)), logx=logx, reference=bool(curve.get("reference")),
                         normalised=normalised))
    return out


def read(path: Path, logx: bool = False) -> list[Curve]:
    """The curves of the stats.json at `path` (<page>.toml.stats.json)."""
    try:
        made = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HeimdallError(f"cannot read a page's statistics: {error}", where=str(path)) from None
    return curves(made, logx)
