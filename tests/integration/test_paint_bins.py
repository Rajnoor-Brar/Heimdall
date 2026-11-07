"""Paint writes the bins it measured (`measured` in <page>.toml.stats.json), and Python's sums of them are Paint's totals.

Every later statistic works on these rows, so they must be exactly what the totals were summed from: each row is
(lo, hi, curve y, curve err, reference y, reference err) over a compared bin, in x order, with NaN as null.
Paint writes its totals to 10 significant digits and the bins to 17, so the sums agree to the totals' precision.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from runner import plot

sys.path.insert(0, str(Path(__file__).parent))
from test_plot_stage import keeps_the_working_files, stage  # noqa: E402,F401

TOTALS = 1e-9               # %.10g: half a unit in the tenth digit is 5e-10 relative


def sums(rows: list, logx: bool) -> dict:
    """What Paint's statistics() adds up, from the rows."""
    out = dict(cmp_area=0.0, ref_area=0.0, abs_area=0.0, chi2=0.0, ndf=0, ratio_area=0.0, ratio_sum=0.0, ratio_width=0.0,
               compared=len(rows))
    for lo, hi, y, err, ref, ref_err in rows:
        w, d = hi - lo, y - ref
        out["ref_area"] += ref * w
        out["cmp_area"] += y * w
        out["abs_area"] += abs(d) * w
        drawn = (math.log10(hi / lo) if lo > 0 else 0.0) if logx else w
        if ref != 0 and drawn > 0:
            r = y / ref
            out["ratio_area"] += abs(r - 1) * drawn
            out["ratio_sum"] += r * drawn
            out["ratio_width"] += drawn
        sigma2 = err * err + ref_err * ref_err
        if sigma2 > 0:
            out["chi2"] += d * d / sigma2
            out["ndf"] += 1
    return out


def close(a, b) -> bool:
    return a == b or abs(a - b) <= TOTALS * max(abs(a), abs(b), 1e-300)


@pytest.mark.slow
def test_python_sums_of_the_measured_bins_are_paints_totals(stage):
    errand, configuration, plans = stage
    said = []
    assert plot.draw(errand, configuration, plans, said.append) == 0, said
    checked = rows_seen = 0
    for page in plot.pages(errand, configuration, plans):
        file = Path(f"{page.config}.stats.json")
        if not file.is_file():                                          # a heat map has no curves
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        logx = bool(page.document["page"]["logx"])
        for i, curve in enumerate(data["curves"]):
            rows = curve["measured"]
            assert all(len(row) == 6 for row in rows), (page.name, i)
            assert all(a is not None and b is not None and a <= b for a, b, *_ in rows), (page.name, i)
            assert [r[0] for r in rows] == sorted(r[0] for r in rows), f"{page.name} curve {i}: x order"
            if curve["reference"]:                                       # the page's first curve is its own reference
                same = lambda a, b: abs(a - b) <= 1e-12 * max(abs(a), abs(b), 1e-300)    # rebinned onto its own edges: y·w/w
                assert all(same(r[2], r[4]) and same(r[3], r[5]) for r in rows), f"{page.name} curve {i}: not its own reference"
            mine = sums([[x if x is not None else math.nan for x in row] for row in rows], logx)
            for key, value in mine.items():
                assert close(value, curve[key]), f"{page.name} curve {i}: {key} {value!r} vs Paint's {curve[key]!r}"
            checked += 1
            rows_seen += len(rows)
    assert checked >= 30 and rows_seen > 300                           # 2 cells × 17 pages, each with its curves
