"""`heimdall rank`: a Run's leaderboard, marginals and baselines, read from its statistics.csv with no page drawn.

The numbers are stats/ranking.py's; this module finds the tables, lays settings over what each was ranked with, and prints.
A Run's folder holds statistics/<set>/statistics.csv (and statistics.json: the `[ranking]` it was ranked with and each point's
values); `<A>/<E>` names every Run under it, and `--across` the errand's own folder (its Runs together).
"""

from __future__ import annotations

import json
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import plotdoc, statstable
from .errors import HeimdallError
from .paths import results_root


@dataclass
class Table:
    run: str                       # <A>/<E>/<R>, or <A>/<E> for an errand's own (across)
    serial: str
    set: str
    csv: Path


def parse_filter(text: str) -> object:
    """`--baseline`: `quantity=value[,quantity=value…]` a filter, anything else a point's name."""
    if "=" not in text:
        return text.strip()
    out = {}
    for part in text.split(","):
        key, _, value = part.partition("=")
        if not key.strip() or not value.strip():
            raise HeimdallError(f"--baseline: '{part}' is not quantity=value", hint="--baseline generator=py8,pdf=NNPDF23lo, or a point's name")
        out[key.strip()] = value.strip()
    return out


def _serial(folder: Path) -> str:
    try:
        source = tomllib.loads((folder / plotdoc.FILE).read_text(encoding="utf-8")).get("source", {})
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    return str(source.get("serial", "")) if source.get("serial") is not None else ""


def tables_of(target: str, set_: str | None, across: bool) -> list[Table]:
    """The statistics tables the target names: a Run's folder, `<A>/<E>`'s Runs (a folder of folders), or with `across` the
    errand's own; `set_` one set, else every set found."""
    name = target.strip("/")
    base = Path(name) if name.startswith("/") else results_root() / name
    if not base.is_dir():
        raise HeimdallError(f"no results folder '{name}'", hint="a Run <A>/<E>/<R>, or <A>/<E> for each of its Runs")
    runs = sorted(p for p in base.iterdir() if (p / "statistics").is_dir())
    folders = [base] if across or not runs else runs         # an errand's own statistics are `--across`'s; its Runs are the rest
    found = []
    for folder in folders:
        shown = str(folder.relative_to(results_root())) if folder.is_relative_to(results_root()) else str(folder)
        for csv in sorted((folder / "statistics").glob("*/statistics.csv")):
            if set_ is None or csv.parent.name == set_:
                found.append(Table(shown, _serial(folder), csv.parent.name, csv))
    if not found:
        raise HeimdallError(f"no statistics in {name}" + (f" for set {set_}" if set_ else ""),
                            hint="heimdall plot <run> --stats-only measures them")
    return found


def settings_for(table: Table, by: str | None, baseline: str | None):
    """The settings a table was ranked with, `--by` and `--baseline` over them, and its points' values."""
    from stats import ranking
    side = statstable.sidecar(table.csv) or {}
    over = {}
    if by:
        over["by"] = [b.strip() for b in by.split(",") if b.strip()]
    if baseline:
        over["baseline"] = parse_filter(baseline)
    values = dict(side.get("values") or {}) or statstable.point_values(table.csv.parent)   # a table from before the sidecar held them
    return ranking.settings_of(side.get("ranking"), over), values


def ranked(table: Table, by: str | None = None, baseline: str | None = None, rows: list | None = None):
    """(rows, settings, values, the ranking) of one table; `rows` replace its own (a Run's rows over the pages Runs share)."""
    from stats import ranking
    st, values = settings_for(table, by, baseline)
    rows = [r for r in (rows if rows is not None else statstable.read(table.csv)) if not str(r.get("object", "")).startswith("/overlay/")]
    return rows, st, values, ranking.score(rows, st)


def _num(v: float, digits: int = 3) -> str:
    return "–" if v != v else "∞" if math.isinf(v) else f"{v:.{digits}g}"


def _grid(headers: list[str], rows: list[list[str]], left: int = 1) -> list[str]:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    line = lambda cells: "  ".join(c.ljust(w) if i < left else c.rjust(w) for i, (c, w) in enumerate(zip(cells, widths))).rstrip()  # noqa: E731
    return [line(headers), line(["-" * w for w in widths]), *(line(r) for r in rows)]


def leaderboard_of(result, st) -> list[dict]:
    from stats import metrics
    out = []
    for cell in dict.fromkeys(p.cell for p in result.points):
        for rank, p in enumerate(result.ranked(cell), 1):
            out.append({"cell": cell, "rank": rank, "point": p.point, "loss": p.loss, "worst_page": p.worst_page,
                        "worst": p.worst_loss, "vetoed": p.vetoed, "dominated": p.dominated, "pages": p.n_pages,
                        "categories": {metrics.CATEGORIES[k]: v for k, v in p.categories.items()},
                        "shares": {metrics.CATEGORIES[k]: v for k, v in p.shares.items()}})
    return out


def report_of(table: Table, by: str | None, baseline: str | None) -> dict:
    """One table's leaderboard, marginals (when its points' values are known) and baseline (when set), as plain data."""
    from stats import ranking
    rows, st, values, result = ranked(table, by, baseline)
    out = {"run": table.run, "serial": table.serial, "set": table.set, "metrics": list(st.metrics),
           "leaderboard": leaderboard_of(result, st), "notes": list(result.notes)}
    if values:
        out["marginals"] = [{"quantity": m.quantity, "confounded": m.confounded,
                             "values": [{"value": v, "loss": s, "points": n, "categories": by_p} for v, s, n, by_p in m.rows]}
                            for m in ranking.marginals(result, values, st)]
        if st.baseline:
            b = ranking.baseline(result, values)
            out["baseline"] = {"filter": b.filter, "unmatched": [{"cell": c, "point": p, "why": w} for c, p, w in b.unmatched],
                               "rows": [{"cell": r.cell, "point": r.point, "partner": r.partner, "loss": r.loss, "base": r.base,
                                         "delta": r.delta, "baseline": r.is_baseline, "objects": r.objects} for r in b.rows]}
    elif by or st.baseline:
        out["warning"] = "this table's points have no values (its statistics.json and plot.toml name none): no marginals or baseline"
    return out


def runs_of(tables: list[Table], by: str | None, baseline: str | None) -> list[dict]:
    """An errand's Runs, a row each: the Run's loss over the pages its Runs share (the objects every Run has), with its serial:
    the `[ranking].over_pages` mean of its points' losses, its best point and its worst page."""
    from stats import means
    by_set: dict = {}
    for t in tables:
        by_set.setdefault(t.set, []).append(t)
    out = []
    for set_, group in by_set.items():
        rows_of = {t.run: [r for r in statstable.read(t.csv) if not r.get("is_reference")] for t in group}
        shared = set.intersection(*({str(r["object"]).rsplit("/", 1)[-1] for r in rows} for rows in rows_of.values())) if rows_of else set()
        for t in group:
            keep = [r for r in statstable.read(t.csv) if str(r["object"]).rsplit("/", 1)[-1] in shared]
            _, st, _, result = ranked(t, by, baseline, keep)
            good = [p for p in result.points if p.loss == p.loss]
            best = min(good, key=lambda p: p.loss, default=None)
            worst = max(good, key=lambda p: p.worst_loss, default=None)
            out.append({"run": t.run, "serial": t.serial, "set": set_, "points": len(good), "pages": len(shared),
                        "loss": means.evaluate(st.over_pages, [p.loss for p in good]) if good else math.nan,
                        "best": best.point if best else "", "best_loss": best.loss if best else math.nan,
                        "worst_page": worst.worst_page if worst else ""})
    return out


def lines_of(report: dict) -> list[str]:
    head = f"{report['run']}" + (f" (run {report['serial']})" if report["serial"] else "") + f" · {report['set']}"
    out = [head, f"metrics: {', '.join(report['metrics'])}", ""]
    board = report["leaderboard"]
    categories = list(dict.fromkeys(k for s in board for k in s["categories"]))
    cells = len({s["cell"] for s in board}) > 1
    headers = ["", "point", "loss", "worst page", "worst", "veto", *categories]
    body = [[f"{s['rank']}." + (f" {s['cell']}" if cells else ""), s["point"], _num(s["loss"]), s["worst_page"].rsplit("/", 1)[-1] or "–",
             _num(s["worst"]), "veto" if s["vetoed"] else "", *(_num(s["categories"].get(p, math.nan)) for p in categories)] for s in board]
    out += ["Leaderboard (lower loss is better):", *_grid(headers, body, 2), ""]
    for m in report.get("marginals", []):
        rows = [[v["value"], _num(v["loss"]), str(v["points"])] for v in m["values"]]
        out += [f"By {m['quantity']}:", *_grid([m["quantity"], "loss", "points"], rows)]
        out += [f"  confounded: {c}" for c in m["confounded"]] + [""]
    if "baseline" in report:
        b = report["baseline"]
        given = ", ".join(f"{k} = {v}" for k, v in b["filter"].items())
        rows = [[r["point"] + (" (baseline)" if r["baseline"] else ""), r["partner"], _num(r["loss"]), _num(r["base"]), f"{r['delta']:+.3g}"]
                for r in b["rows"]]
        out += [f"Baseline {given} (negative: better):", *_grid(["point", "against", "loss", "baseline", "Δloss"], rows, 2)]
        out += [f"  unmatched: {u['point']} ({u['why']})" for u in b["unmatched"]] + [""]
    if report.get("warning"):
        out += [report["warning"], ""]
    return out + [f"note: {n}" for n in report["notes"]]


def run(args) -> int:
    """`heimdall rank <A>/<E>[/<R>] [--set S] [--across] [--by QUANTITIES] [--baseline q=value] [--json]`."""
    tables = tables_of(args.target, args.set_name, args.across)
    by_run = {t.run for t in tables}
    if len(by_run) > 1 and not args.across:                  # an errand's Runs: a row a Run
        runs = runs_of(tables, args.by, args.baseline)
        if args.json:
            print(json.dumps({"runs": runs}, indent=2, allow_nan=False, default=lambda v: None if v != v else str(v)))
            return 0
        for set_ in dict.fromkeys(r["set"] for r in runs):
            mine = [r for r in runs if r["set"] == set_]
            print(f"{args.target} · {set_}: each Run's loss over the {mine[0]['pages']} page(s) its Runs share (lower is better)")
            rows = [[r["serial"] or "–", r["run"], str(r["points"]), _num(r["loss"]), r["best"], _num(r["best_loss"]),
                     r["worst_page"].rsplit("/", 1)[-1] or "–"] for r in mine]
            print("\n".join(_grid(["run", "folder", "points", "loss", "best point", "best", "worst page"], rows, 2)), "\n", sep="")
        return 0
    reports = [report_of(t, args.by, args.baseline) for t in tables]
    if args.json:
        print(json.dumps({"tables": reports}, indent=2, allow_nan=False, default=lambda v: None if v != v else str(v)))
        return 0
    print("\n".join(line for r in reports for line in lines_of(r)))
    return 0
