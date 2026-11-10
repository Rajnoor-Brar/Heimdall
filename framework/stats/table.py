"""The statistics table: a page's numbers as rows, a set's statistics.csv and its statistics.json written and read back.

Format 2. The columns of `STATISTIC_COLUMNS` come first, in their old order, from Paint's totals; the metrics asked for
(by default the five of `metrics.REGISTRY` that are `default`) follow, those not already among the old columns, computed from
the `measured` bins of the page's stats.json. `statistics.json` beside the csv holds `format = 2`, the columns, and for each
metric on its purpose, direction, thresholds and note. A csv with no sidecar is format 1: the old columns, read as before.

This module imports only the standard library at module level (the runner imports it); numpy is loaded when a metric is
computed. A page is plot's `Page`, used by duck type: its config, document, plain labels, name, rel, cell and object.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

FORMAT = 3
STATISTIC_COLUMNS = ("page", "cell", "object", "curve", "point", "reference", "is_reference", "bins", "area", "area_err",
                     "ref_area", "cmp_area", "abs_area", "yield_weighted_abs_dev", "yield_ratio", "mean_bin_ratio",
                     "mean_abs_ratio_dev", "chi2", "ndf",
                     "chi2_ndf")
#: The columns that hold text, and the counts; every other one is a number ("" in the file: NaN).
TEXT = ("page", "cell", "object", "curve", "point", "run", "reference")
COUNTS = ("bins", "ndf")
SIDECAR = "statistics.json"


def default_metrics() -> tuple[str, ...]:
    """The metrics that are on unless a setting names others."""
    from . import metrics
    return tuple(name for name, m in metrics.REGISTRY.items() if m.default)


def columns_for(names, run: bool = False) -> list[str]:
    """STATISTIC_COLUMNS, then each named metric that is not already one of them, once, in the order given; `run` (a table of
    Runs together: across) puts a `run` column after `point`."""
    out = list(STATISTIC_COLUMNS)
    if run:
        out.insert(out.index("point") + 1, "run")
    for name in names:
        if name not in out:
            out.append(name)
    return out


def statistics_of(page, names=None) -> list[dict] | None:
    """A page's statistics, one row per curve (STATISTIC_COLUMNS, then the extra metrics in `names`: the defaults when
    None), from Paint's <page>.toml.stats.json; None when Paint wrote none (a heat map, a page it could not read). The
    extra metrics are NaN where the page's stats.json has no `measured` bins (written before Paint measured them)."""
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
                     "yield_weighted_abs_dev": number["abs_area"] / number["ref_area"] if number["ref_area"] else float("nan"),
                     "yield_ratio": number["cmp_area"] / number["ref_area"] if number["ref_area"] else float("nan"),
                     "mean_bin_ratio": ratio_sum / ratio_width if ratio_width else float("nan"),
                     "mean_abs_ratio_dev": ratio_area / ratio_width if ratio_width else float("nan"),
                     "ndf": numbers.get("ndf", 0),
                     "chi2_ndf": number["chi2"] / numbers["ndf"] if numbers.get("ndf") else float("nan")})
        if run := getattr(page, "runs", {}).get(rows[-1]["point"]):          # a table of Runs together: whose each is
            rows[-1]["run"] = run
    extra = [n for n in (default_metrics() if names is None else names) if n not in STATISTIC_COLUMNS]
    if extra and rows:
        _add_metrics(rows, made, page, extra)
    return rows


def _add_metrics(rows: list[dict], made: dict, page, names: list[str]) -> None:
    """The extra metric columns of a page's rows, from its measured bins; NaN for a page without them."""
    from runner.errors import HeimdallError
    from . import bins, metrics
    try:
        curves = bins.curves(made, bool(page.document.get("page", {}).get("logx")))
    except HeimdallError:
        curves = None
    for i, row in enumerate(rows):
        for name in names:
            row[name] = metrics.evaluate(name, curves[i], pool=curves) if curves and i < len(curves) else float("nan")


def sidecar_of(names, score: dict | None = None, axes: dict | None = None, merged: dict | None = None, run: bool = False) -> dict:
    """What statistics.json holds for a table with the metrics `names`, scored as `score` (the merged [score] table, a plain
    dict) says: the summary and the report score the rows the way the table was written."""
    from . import metrics
    columns = columns_for(names, run)
    out = {"format": FORMAT, "columns": columns,
           "metrics": {n: {"purpose": m.purpose, "polarity": m.polarity, "phrase": metrics.PHRASE[m.polarity], "scale": m.scale,
                           "thresholds": list(m.thresholds) if m.thresholds else None, "default": m.default, "note": m.note,
                           "why": m.why}
                       for n in columns if (m := metrics.REGISTRY.get(n))}}
    if score:
        out["score"] = score
    if axes:
        out["axes"] = axes                                  # {point: {axis: tag}}: what each point's sweep chose
    if merged:
        out["merged"] = merged                              # {curve: [its points]}: a set's merge, a curve of its own
    return out


def write_statistics(todo: list, target: Path, names=None, score: dict | None = None, axes: dict | None = None,
                     merged: dict | None = None) -> int:
    """results/…/statistics.csv (V160) and its statistics.json: every drawn page's curves; the number of rows."""
    names = list(default_metrics() if names is None else names)
    rows = [row for page in todo for row in (statistics_of(page, names) or [])]
    if not rows:
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    run = any(row.get("run") for row in rows)
    columns = columns_for(names, run)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=columns)
        out.writeheader()
        for row in rows:
            out.writerow({k: ("" if isinstance(v, float) and v != v else v) for k, v in row.items()})
    target.with_name(SIDECAR).write_text(json.dumps(sidecar_of(names, score, axes, merged, run), indent=2) + "\n", encoding="utf-8")
    return len(rows)


def _raw(path: Path) -> dict | None:
    side = Path(path).with_name(SIDECAR)
    return json.loads(side.read_text(encoding="utf-8")) if side.is_file() else None


def upgraded(side: dict) -> dict:
    """A sidecar of format 1, 2 or 3 as format 3 says it, never written back: each metric under its id now, a metric's
    `better` as `polarity` (`none` a `descriptor`). A key format 3 has and the file lacks stays absent."""
    from . import metrics
    out = dict(side)
    out["format"] = FORMAT
    if "columns" in out:
        out["columns"] = [metrics.resolve(c) for c in out["columns"]]
    if "metrics" in out:
        named = {}
        for name, entry in out["metrics"].items():
            entry = dict(entry)
            if "better" in entry:
                better = entry.pop("better")
                entry.setdefault("polarity", "descriptor" if better == "none" else better)
            named[metrics.resolve(name)] = entry
        out["metrics"] = named
    if isinstance(out.get("score"), dict):
        score = dict(out["score"])
        given = score.get("metrics")
        if isinstance(given, dict):
            score["metrics"] = {metrics.resolve(n): w for n, w in given.items()}
        elif isinstance(given, list):
            score["metrics"] = [metrics.resolve(n) for n in given]
        if isinstance(score.get("thresholds"), dict):
            score["thresholds"] = {metrics.resolve(n): v for n, v in score["thresholds"].items()}
        out["score"] = score
    return out


def sidecar(path: Path) -> dict | None:
    """The statistics.json beside a csv, `upgraded` to format 3; None for a csv from before format 2."""
    side = _raw(path)
    return upgraded(side) if side is not None else None


def format_of(path: Path) -> int:
    """1 for a csv with no sidecar, else the format its sidecar was written in."""
    side = _raw(path)
    return int(side.get("format", 1)) if side else 1


def read(path: Path) -> list[dict]:
    """A statistics.csv's rows, typed as statistics_of gives them: text as str, is_reference a bool, bins and
    ndf ints, every other number (the metrics too) a float ("" is NaN). A format 1 csv has only the old columns; a column
    named by a metric's former id is read under its id now."""
    from . import metrics
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
        return [{metrics.resolve(k): value(k, v) for k, v in row.items()} for row in csv.DictReader(handle)]
