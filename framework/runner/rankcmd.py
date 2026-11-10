"""`heimdall rank`: a Run's leaderboard, marginals and baselines, read from its statistics.csv with no page drawn.

The numbers are stats/ranking.py's; this module finds the tables, lays settings over what each was ranked with, and prints.
A Run's folder holds statistics/<set>/statistics.csv (and statistics.json: the `[ranking]` it was ranked with and each point's
values); `<A>/<E>` names every Run under it, and `--across` the errand's own folder (its Runs together).
"""

from __future__ import annotations

import dataclasses
import json
import math
import sys
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


def flags_of(args) -> dict:
    """The command's flags that reach the engine, as `[ranking]` keys: `--by`, `--baseline`, `--trim`, `--head-to-head`,
    `--detail` (each the source "--<flag>" in the record)."""
    flags: dict = {}
    if getattr(args, "by", None):
        flags["by"] = [b.strip() for b in args.by.split(",") if b.strip()]
    if getattr(args, "baseline", None):
        flags["baseline"] = parse_filter(args.baseline)
    if getattr(args, "trim", None) is not None:
        flags["trim"] = args.trim
    if getattr(args, "head_to_head", None):
        flags["head_to_head"] = args.head_to_head
    if getattr(args, "detail", False):
        flags["detail"] = True
    return flags


def settings_for(table: Table, flags: dict | None = None):
    """The settings a table was ranked with, the command's `flags` over them, and its points' values."""
    from stats import ranking
    side = statstable.sidecar(table.csv) or {}
    values = dict(side.get("values") or {}) or statstable.point_values(table.csv.parent)   # a table from before the sidecar held them
    return ranking.settings_of(side.get("ranking"), flags, side.get("ranking_sources")), values


def ranked(table: Table, flags: dict | None = None, rows: list | None = None):
    """(rows, settings, values, the ranking) of one table; `rows` replace its own (a Run's rows over the pages Runs share)."""
    from stats import ranking
    st, values = settings_for(table, flags)
    side = statstable.sidecar(table.csv) or {}
    rows = [r for r in (rows if rows is not None else statstable.read(table.csv)) if not str(r.get("object", "")).startswith("/overlay/")]
    return rows, st, values, ranking.rank(rows, st, side.get("page_weights"), values)


def _times(v: float) -> str:
    """A log ratio as the ratio itself."""
    return "–" if v != v or math.isinf(v) else f"×{math.exp(v):.2f}"


def _num(v: float, digits: int = 3) -> str:
    return "–" if v != v else "∞" if math.isinf(v) else f"{v:.{digits}g}"


def _grid(headers: list[str], rows: list[list[str]], left: int = 1) -> list[str]:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    line = lambda cells: "  ".join(c.ljust(w) if i < left else c.rjust(w) for i, (c, w) in enumerate(zip(cells, widths))).rstrip()  # noqa: E731
    return [line(headers), line(["-" * w for w in widths]), *(line(r) for r in rows)]


def glyphs() -> dict:
    """A polarity's mark as this terminal can print it: the Unicode glyphs when stdout is UTF-8, else the ASCII forms."""
    from stats import metrics
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower().replace("-", "").replace("_", "")
    return metrics.GLYPH if encoding == "utf8" else metrics.ASCII


def leaderboard_of(result) -> list[dict]:
    """The ranking's points in its order: `rank` is None for a vetoed point and one with no loss."""
    from stats import metrics
    return [{"cell": p.cell, "rank": p.rank, "point": p.point, "loss": p.loss, "worst_page": p.worst_page,
             "worst": p.worst_loss, "vetoed": p.vetoed, "failed_pages": p.failed_pages, "gate_reason": p.gate_reason,
             "dominated": p.dominated, "pages": p.n_pages,
             "values": {k: v if math.isfinite(v) else None for k, v in p.values.items()},     # NaN: no page had a number
             "categories": {metrics.CATEGORIES[k]: v for k, v in p.categories.items()},
             "shares": {metrics.CATEGORIES[k]: v for k, v in p.shares.items()}} for p in result.points]


def report_of(table: Table, flags: dict | None = None) -> dict:
    """One table's leaderboard, marginals (when its points' values are known), baseline (when set) and head to head (when
    asked), each with its "Made by" from the record, and the record itself, as plain data."""
    from stats import ranking
    rows, st, values, result = ranked(table, flags)
    method = result.method
    out = {"run": table.run, "serial": table.serial, "set": table.set, "metrics": list(st.metrics), "flat": result.flat,
           "leaderboard": leaderboard_of(result), "notes": list(result.notes), "method": method.as_dict(),
           "made_by": {"leaderboard": method.made_by("leaderboard"), "values": method.made_by("values", list(st.metrics))},
           "detail": st.detail}
    if values:
        out["marginals"] = [{"quantity": m.quantity, "headline": m.headline, "strata": list(m.strata), "confounded": m.confounded,
                             "values": [dataclasses.asdict(r) for r in m.rows],
                             "made_by": method.made_by("marginal", quantity=m.quantity)} for m in result.marginals]
        if result.baseline is not None:
            b = result.baseline
            out["baseline"] = {"filter": b.filter, "unmatched": [{"cell": c, "point": p, "why": w} for c, p, w in b.unmatched],
                               "rows": [{"cell": r.cell, "point": r.point, "partner": r.partner, "loss": r.loss, "base": r.base,
                                         "delta": r.delta, "baseline": r.is_baseline, "objects": r.objects} for r in b.rows],
                               "made_by": method.made_by("baseline")}
    pages = ranking.matched_pages(rows, st.head_to_head)
    if pages:
        out["head_to_head"] = {"pages": [ranking.head_to_head(rows, page, st) for page in pages],
                               "made_by": method.made_by("head_to_head")}
    elif st.head_to_head:
        out["warning"] = f"--head-to-head: no page '{st.head_to_head}' in this table"
    if not values and (st.by or st.baseline):
        out["warning"] = "this table's points have no values (its statistics.json and plot.toml name none): no marginals or baseline"
    return out


def runs_of(tables: list[Table], flags: dict | None = None) -> list[dict]:
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
            _, st, _, result = ranked(t, flags, keep)
            good = [p for p in result.points if p.loss == p.loss]
            best = min(good, key=lambda p: p.loss, default=None)
            worst = max(good, key=lambda p: p.worst_loss, default=None)
            out.append({"run": t.run, "serial": t.serial, "set": set_, "points": len(good), "pages": len(shared),
                        "loss": means.evaluate(st.over_pages, [p.loss for p in good]) if good else math.nan,
                        "best": best.point if best else "", "best_loss": best.loss if best else math.nan,
                        "worst_page": worst.worst_page if worst else ""})
    return out


def _made(lines: list[str]) -> list[str]:
    """A table's "Made by", under it."""
    return [f"  made by: {line}" for line in lines]


def method_lines(report: dict) -> list[str]:
    """`--method`: a table's whole record, stage by stage, and no table."""
    from stats import ranking
    head = f"{report['run']}" + (f" (run {report['serial']})" if report["serial"] else "") + f" · {report['set']}"
    out = [head]
    for stage in ranking.Method.STAGES:
        choices = report["method"][stage]
        if choices:
            out.append(f"{ranking.Method.TITLES[stage]}:")
            out += [f"  {c['name']}: {ranking._said(c['value'])} ({c['source']})." + (f" {c['note']}" if c["note"] else "")
                    for c in choices]
    return out + [""]


def lines_of(report: dict) -> list[str]:
    from stats import metrics
    g = glyphs()
    down = g["lower"]
    head = f"{report['run']}" + (f" (run {report['serial']})" if report["serial"] else "") + f" · {report['set']}"
    out = [head, f"metrics: {', '.join(report['metrics'])}", ""]
    board = report["leaderboard"]
    categories = list(dict.fromkeys(k for s in board for k in s["categories"]))
    cells = len({s["cell"] for s in board}) > 1
    headers = ["", "point", f"point loss {down}", "worst page", f"page loss {down}", *(f"{c} {down}" for c in categories)]
    body = [[(f"{s['rank']}." if s["rank"] else "–") + (f" {s['cell']}" if cells else ""), s["point"], _num(s["loss"]), s["worst_page"].rsplit("/", 1)[-1] or "–",
             _num(s["worst"]), *(_num(s["categories"].get(p, math.nan)) for p in categories)] for s in board]
    out += ["Leaderboard:", *_grid(headers, body, 2)]
    out += [f"  vetoed: {s['point']}: {s['gate_reason']}" for s in board if s["vetoed"]]
    out += _made(report["made_by"]["leaderboard"]) + [""]
    if report.get("detail"):
        names = [n for n in report["metrics"] if n in metrics.REGISTRY]
        rows = [[s["point"], *(_num(s["values"].get(n, math.nan)) for n in names)] for s in board]
        out += ["Metric values:", *_grid(["point", *(f"{n} {g[metrics.REGISTRY[n].polarity]}" for n in names)], rows)]
        out += _made(report["made_by"]["values"]) + [""]
    for m in report.get("marginals", []):
        rows = [[v["value"], _times(v["effect"]) + (f" ({v['mark']})" if v["mark"] else ""), _num(v["effect_se"], 2),
                 "best" if v["same_as_best"] and v["vs_best"] == 0 else "≈ best" if v["same_as_best"]
                 else f"{_times(v['vs_best'])} ± {_num(v['vs_best_se'], 2)}", _times(v["level"]).lstrip("×"), str(v["n"]), f"{v['g']} + {v['g']}",
                 str(v["vetoed"]), str(v["unmatched"])] for v in m["values"]]
        out += [f"By {m['quantity']}: {m['headline']}",
                *_grid([m["quantity"], f"× vs strata {down}", "± SE", f"vs best {down}", f"level {down}", "n", "trimmed", "vetoed",
                        "unmatched"], rows)]
        out += ([f"  confounded: {m['confounded']}"] if m["confounded"] else []) + _made(m["made_by"]) + [""]
    if "baseline" in report:
        b = report["baseline"]
        given = ", ".join(f"{k} = {v}" for k, v in b["filter"].items())
        rows = [[r["point"] + (" (baseline)" if r["baseline"] else ""), r["partner"], _num(r["loss"]), _num(r["base"]), f"{r['delta']:+.3g}"]
                for r in b["rows"]]
        out += [f"Baseline {given} (negative: better):",
                *_grid(["point", "against", f"loss {down}", f"baseline {down}", f"Δloss {down}"], rows, 2)]
        out += [f"  unmatched: {u['point']} ({u['why']})" for u in b["unmatched"]] + _made(b["made_by"]) + [""]
    if "head_to_head" in report:
        for match in report["head_to_head"]["pages"]:
            members = match["points"]
            diff = {(p["a"], p["b"]): p["loss"] for p in match["pairs"]}
            diff.update({(b_, a): -v for (a, b_), v in list(diff.items())})
            rows = [[a, *("–" if a == b_ else f"{diff[(a, b_)]:+.3g}" for b_ in members), _num(match["losses"][a])] for a in members]
            out += [f"Head to head: {match['page']} (the row's loss less the column's):", *_grid(["point", *members, f"loss {down}"], rows)]
        out += _made(report["head_to_head"]["made_by"]) + [""]
    if report.get("warning"):
        out += [report["warning"], ""]
    return out + [f"note: {n}" for n in report["notes"]]


#: What rank prints beyond the polarity glyphs, as a terminal that is not UTF-8 can print it.
ASCII_TEXT = str.maketrans({"·": "-", "–": "-", "—": "-", "×": "x", "±": "+/-", "≈": "~", "≥": ">=", "≤": "<=", "Δ": "d",
                            "₂": "2", "²": "^2", "χ": "chi", "σ": "sigma", "ℓ": "l", "→": "->", "…": "...", "’": "'"})


def say(text: str) -> None:
    """Print `text` as this terminal can take it: unchanged on UTF-8, else in ASCII forms, and any sign still left
    replaced rather than refused (rank never fails on its own output)."""
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    if encoding.lower().replace("-", "").replace("_", "") != "utf8":
        text = text.translate(ASCII_TEXT).encode(encoding, "replace").decode(encoding)
    print(text)


def plain(value):
    """`value` for JSON: a number that is not finite (NaN, ±inf: a point with no loss, a value with one stratum) as null,
    through dicts, lists and tuples."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def run(args) -> int:
    """`heimdall rank <A>/<E>[/<R>] [--set S] [--across] [--by QUANTITIES] [--baseline q=value] [--trim ALPHA]
    [--head-to-head PAGE|all] [--detail] [--method] [--json]`."""
    tables = tables_of(args.target, args.set_name, args.across)
    flags = flags_of(args)
    by_run = {t.run for t in tables}
    if len(by_run) > 1 and not args.across:                  # an errand's Runs: a row a Run
        runs = runs_of(tables, flags)
        if args.json:
            print(json.dumps(plain({"runs": runs}), indent=2, allow_nan=False, default=str))
            return 0
        for set_ in dict.fromkeys(r["set"] for r in runs):
            mine = [r for r in runs if r["set"] == set_]
            say(f"{args.target} · {set_}: each Run's loss over the {mine[0]['pages']} page(s) its Runs share (lower is better)")
            rows = [[r["serial"] or "–", r["run"], str(r["points"]), _num(r["loss"]), r["best"], _num(r["best_loss"]),
                     r["worst_page"].rsplit("/", 1)[-1] or "–"] for r in mine]
            say("\n".join(_grid(["run", "folder", "points", "loss", "best point", "best", "worst page"], rows, 2)) + "\n")
        return 0
    reports = [report_of(t, flags) for t in tables]
    if args.json:
        print(json.dumps(plain({"tables": reports}), indent=2, allow_nan=False, default=str))
        return 0
    shown = method_lines if getattr(args, "method", False) else lines_of
    say("\n".join(line for r in reports for line in shown(r)))
    return 0
