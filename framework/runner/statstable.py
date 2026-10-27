"""The statistics table (V160, V164; I-108 P1): a page's numbers as rows, a set's statistics.csv written and
read back, and its bar graphs and summary (rank 4).

plot.py measures (Paint writes each page's <page>.toml.stats.json) and calls these; the report reads a source's
statistics.csv with `read` and lays out its summary's sections itself. A page is plot's `Page`: its config,
document, curves' plain labels, name, cell, object and set.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from . import plugins
from .paths import heimdall_root, results_root

STATISTIC_COLUMNS = ("page", "cell", "object", "curve", "point", "reference", "is_reference", "bins", "area", "area_err",
                     "ref_area", "cmp_area", "abs_area", "rel_abs_area", "area_ratio", "ratio_mean", "ratio_dev", "chi2", "ndf",
                     "chi2_ndf")
#: The columns that hold text, and the counts; every other one is a number ("" in the file: NaN).
TEXT = ("page", "cell", "object", "curve", "point", "reference")
COUNTS = ("bins", "ndf")


def bars():
    """framework/plot/figures/bars.py, loaded (V162): the bar graphs and the summary."""
    return plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "bars.py", "bars")


def statistics_of(page) -> list[dict] | None:
    """A page's statistics, one row per curve (STATISTIC_COLUMNS), from Paint's <page>.toml.stats.json; None
    when Paint wrote none (a heat map, a page it could not read)."""
    path = page.config.with_name(page.config.name + ".stats.json")
    if not path.is_file():
        return None
    made = json.loads(path.read_text(encoding="utf-8"))
    curves = page.document.get("curve", [])
    data = page.document.get("data")
    reference = data["label"] if data and made.get("reference") == "data" else curves[0]["label"] if curves else ""
    rows = []
    for curve, numbers in zip(curves, made.get("curves", [])):
        number = {k: (float("nan") if numbers.get(k) is None else numbers[k])
                  for k in ("area", "area_err", "ref_area", "cmp_area", "abs_area", "ratio_area", "ratio_sum", "ratio_width",
                            "chi2")}
        ratio_area, ratio_sum, ratio_width = (number.pop(k) for k in ("ratio_area", "ratio_sum", "ratio_width"))   # V175
        label = page.plain[len(rows)] if len(page.plain) > len(rows) else curve["label"]
        rows.append({"page": page.rel or page.name, "cell": page.cell, "object": page.object, "curve": label,
                     "point": curve["object"].split("/", 1)[0], "reference": reference,
                     "is_reference": bool(numbers.get("reference")), "bins": numbers.get("bins", 0), **number,
                     "rel_abs_area": number["abs_area"] / number["ref_area"] if number["ref_area"] else float("nan"),
                     "area_ratio": number["cmp_area"] / number["ref_area"] if number["ref_area"] else float("nan"),
                     "ratio_mean": ratio_sum / ratio_width if ratio_width else float("nan"),
                     "ratio_dev": ratio_area / ratio_width if ratio_width else float("nan"),
                     "ndf": numbers.get("ndf", 0),
                     "chi2_ndf": number["chi2"] / numbers["ndf"] if numbers.get("ndf") else float("nan")})
    return rows


def write_statistics(todo: list, target: Path) -> int:
    """results/…/plots/statistics.csv (V160): every drawn page's curves; the number of rows."""
    import csv
    rows = [row for page in todo for row in (statistics_of(page) or [])]
    if not rows:
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=STATISTIC_COLUMNS)
        out.writeheader()
        for row in rows:
            out.writerow({k: ("" if isinstance(v, float) and v != v else v) for k, v in row.items()})
    return len(rows)


def read(path: Path) -> list[dict]:
    """A statistics.csv's rows, typed as statistics_of gives them: text as str, is_reference a bool, bins and
    ndf ints, every other number a float ("" is NaN)."""
    import csv

    def value(key: str, text: str):
        if key in TEXT:
            return text
        if key == "is_reference":
            return text == "True"
        if key in COUNTS:
            return int(float(text)) if text else 0
        try:
            return float(text) if text != "" else math.nan
        except ValueError:
            return math.nan

    with open(path, encoding="utf-8", newline="") as handle:
        return [{k: value(k, v) for k, v in row.items()} for row in csv.DictReader(handle)]


def heading_of(numbers: Path) -> str:
    """A set's statistics' heading (V196): its run folder under results/ (else that folder's last two parts) and
    the set, "eic/zeus_validation/01_pythia_qed_lepton · qed_lepton_by_pdf"."""
    run = numbers.parent.parent
    try:
        where = run.resolve().relative_to(results_root().resolve()).as_posix()
    except ValueError:
        where = "/".join(run.parts[-2:])
    return f"{where} · {numbers.name}"


def write_set(pages: list, numbers: Path, formats: list[str], module=None) -> tuple[int, int]:
    """A set's numbers, statistics/<set>/ (V160, V164): statistics.csv, then each page's bar graph and the summary
    (bars.draw), when any page has numbers. (rows written, images made). `module`: bars, loaded once by the caller."""
    count = write_statistics(pages, numbers / "statistics.csv")
    if not count:
        return 0, 0
    module = module or bars()
    images = module.draw([(p.rel, statistics_of(p) or []) for p in pages], numbers / "bars", formats,
                         summary=numbers / "summary", heading=heading_of(numbers))
    return count, images
