"""`heimdall report` (I-108, .plans/report/): a quick, informal report of one or more runs' pages and numbers,
for colleagues or a supervisor, made only when asked (rank 4).

* **Sources** are result folders holding a plot document (plot.toml): a configuration's, or a run's runs-together
  folder (V169). They are named `<P>/<run>/<cfg>`, `<P>/<run>` (each of its configurations, then its own when it
  is drawn), a path, or a glob of them under results/.
* **A recipe** is a `[report]` table and its `[[report.section]]`s (framework/schema/report.toml), each section one
  kind of item: pages, compare, stats, bars or files. It is a file of its own (`configs/<P>/<name>.toml`, `[report]`
  alone), a run TOML's `[report]` (what its folders' reports show, its `template` laid under it), or the
  `report.toml` a run writes beside each folder's plot.toml from that (V209). With no sections, the default: the
  statistics' headline, then each set the sources' documents draw.
* **Where:** reports/ mirrors results/: a folder's report in reports/<P>/<run>/<cfg>/, a run's in reports/<P>/<run>/,
  several runs' where their addresses meet; `-o` or the recipe's `output` says otherwise.
* `resolve` turns a recipe and its sources into a `Plan`: its sections' grids of figures, each copied from its
  source or drawn for the report, and its statistics parts. Nothing is written until the build.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config as configmod
from . import plotdoc, plugins, record, statstable, viewer
from .config import STATISTICS
from .errors import HepError, did_you_mean
from .paths import config_file, configs_root, hep_root, reports_root, results_root, work_root

#: What a run writes beside each folder's plot.toml: its report's recipe (V209).
RECIPE = "report.toml"
#: Whose drawn pages a section takes, in order of preference, when it names none.
BACKENDS = ("root", "mpl", "yoda")
#: The default report's headline: the top five and each statistic's ranking (the area has none).
HEADLINE = ["top5", *(f"{key}:ranking" for key in STATISTICS if key != "area")]
#: What a title or subtitle may name, filled in from its sources' plot documents.
PLACEHOLDERS = ("project", "run", "configuration", "title")
#: Panels on an A4 page of a grid, for the listing's page count (the build lays them out).
PER_PAGE = 6
GLOB = re.compile(r"[*?\[]")
SERIAL = re.compile(r"^\d+_")


def natural(text: str) -> list:
    """A sort key that orders numbers by value: d2 < d10, 10M < 150M."""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.lower()) for t in re.split(r"(\d+)", text) if t]


def _matches(name: str, glob: str) -> bool:
    """A page name against a glob: the whole name, or (a glob without /) its last part."""
    return fnmatch.fnmatchcase(name, glob) or ("/" not in glob and fnmatch.fnmatchcase(name.rsplit("/", 1)[-1], glob))


# ── sources ────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Source:
    """A result folder holding a plot document, as a report reads it."""
    address: str                 # <P>/<run>/<cfg> (or <P>/<run>) under results/, else its path
    folder: Path
    doc: object                  # plotdoc.Doc
    members: list                # plot.Member

    @property
    def project(self) -> str:
        return self.doc.project

    @property
    def name(self) -> str:
        """Its folder's name without the serial: `generator_pdf`."""
        return SERIAL.sub("", self.folder.name)

    def events(self) -> int:
        """The events its points ran with, the most common count (0: unknown)."""
        counts = [n for n in (plotdoc._member_events(self.doc, m) for m in self.members) if n]
        return max(set(counts), key=counts.count) if counts else 0

    def label(self, how: str) -> str:
        if how == "events":
            n = self.events()
            if not n:
                raise HepError(f"{self.address}: no event count", hint='its points say none; label = "folder" labels it by its folder')
            return plotdoc.count_tag(n)
        return self.name

    def complete(self) -> list:
        return [m for m in self.members if m.recorded is not None and m.recorded == m.identity]

    def sets(self) -> list[str]:
        """The sets drawn here: plots/<set>/ with a backend's folder in it."""
        plots = self.folder / "plots"
        return sorted((d.name for d in plots.iterdir() if d.is_dir() and any((d / b).is_dir() for b in BACKENDS)),
                      key=natural) if plots.is_dir() else []

    def pages(self, set_: str, backends: tuple[str, ...]) -> dict[str, Path]:
        """A set's drawn pages, name → file: per page, the first of `backends` that drew it, its PDF (else its
        PNG). Sheets and indexes are not pages."""
        out: dict[str, Path] = {}
        for backend in backends:
            where = self.folder / "plots" / set_ / backend
            found: dict[str, Path] = {}
            for path in sorted(where.rglob("*")) if where.is_dir() else ():
                rel = path.relative_to(where)
                if path.suffix.lower() not in (".pdf", ".png") or rel.parts[0] == "sheets":
                    continue
                name = rel.with_suffix("").as_posix()
                if name not in found or path.suffix.lower() == ".pdf":
                    found[name] = path
            for name, path in found.items():
                out.setdefault(name, path)
        return dict(sorted(out.items(), key=lambda item: natural(item[0])))

    def numbers(self, set_: str) -> Path | None:
        """A set's statistics.csv, when measured."""
        path = self.folder / "statistics" / set_ / "statistics.csv"
        return path if path.is_file() else None

    def facts(self) -> dict:
        """Where it came from (N2): its config and configuration, Heimdall's revision and when its document was
        written, its points (complete or not), its events, what it is compared against, and whether its points
        are newer than its pages."""
        given = self.doc.source
        complete = self.complete()
        reference = (self.doc.stats or {}).get("reference", "data")
        if isinstance(reference, dict):
            against = "the curve " + ", ".join(f"{q} = {t}" for q, t in reference.items())
        elif reference == "curves" or not (self.doc.plot or {}).get("data"):
            against = "each page's first curve"
        else:
            against = "data"
        yodas = [m.yoda.stat().st_mtime for m in complete if m.yoda is not None and m.yoda.is_file()]
        drawn = [p.stat().st_mtime for set_ in self.sets() for p in (self.folder / "plots" / set_).rglob("*.p[dn][fg]")]
        return {"address": self.address, "config": given.get("config", ""), "configuration": given.get("configuration", ""),
                "heimdall": str(given.get("heimdall", ""))[:12], "written": str(given.get("written", "")),
                "points": len(self.members), "complete": len(complete),
                "incomplete": [m.point.name for m in self.members if m not in complete],
                "events": plotdoc.count_tag(n) if (n := self.events()) else "", "against": against,
                "stale": bool(yodas and drawn and max(yodas) > min(drawn))}


def labels(found: list[Source], how: str) -> dict[str, str]:
    """Each source's side-by-side label, by address. folder: its folder's name without the serial, with it where
    two sources share that (a configuration run again: 02_generator_pdf, 03_generator_pdf), then with its run;
    events: the events its points ran with."""
    if how == "events":
        return {s.address: s.label("events") for s in found}
    for name in (lambda s: s.name, lambda s: s.folder.name, lambda s: f"{s.folder.parent.name}/{s.folder.name}"):
        out = {s.address: name(s) for s in found}
        if len(set(out.values())) == len(out):
            return out
    return {s.address: s.address for s in found}


def _address(folder: Path) -> str:
    root = results_root().resolve()
    return folder.relative_to(root).as_posix() if folder.is_relative_to(root) else str(folder)


def _run_sources(run: Path) -> list[Path]:
    """A run's folder: each configuration's folder with a plot document, then its own when it is drawn."""
    found = sorted((d for d in run.iterdir() if d.is_dir() and (d / plotdoc.FILE).is_file()), key=lambda d: natural(d.name))
    if (run / plotdoc.FILE).is_file() and (run / "plots").is_dir():
        found.append(run)
    return found


def _folders_of(address: str, where: str) -> list[Path]:
    path = Path(address).expanduser()
    if address.startswith(("./", "../", "/", "~")):
        if (path / plotdoc.FILE).is_file():
            return [path.resolve()]
        if path.is_dir() and (found := _run_sources(path)):
            return [p.resolve() for p in found]
        raise HepError(f"no plot document in {path}", where=where, hint="a source is a result folder holding a plot.toml")
    root = results_root()
    matches = sorted(root.glob(address), key=lambda p: natural(str(p))) if GLOB.search(address) else [root / address]
    out: list[Path] = []
    for match in (m for m in matches if m.is_dir()):
        depth = len(match.relative_to(root).parts)
        if depth == 3 and (match / plotdoc.FILE).is_file():
            out.append(match.resolve())
        elif depth == 2:
            out += [p.resolve() for p in _run_sources(match)]
    if out:
        return out
    parent = root / address.rsplit("/", 1)[0] if "/" in address else root
    present = sorted(p.name for p in parent.iterdir() if p.is_dir()) if parent.is_dir() and not GLOB.search(address) else []
    raise HepError(f"no result folder {address} under {root}", where=where,
                   hint=did_you_mean(address.rsplit("/", 1)[-1], present) or "a source is <P>/<run>/<cfg>, <P>/<run>, a path or a glob")


def sources(addresses: list[str], where: str) -> list[Source]:
    """The result folders these name, each once, in the order named (a glob's in natural order)."""
    out: list[Source] = []
    seen: set[Path] = set()
    for address in addresses:
        for folder in _folders_of(address, where):
            if folder in seen:
                continue
            seen.add(folder)
            doc, _, members = plotdoc.load(folder / plotdoc.FILE)
            out.append(Source(_address(folder), folder, doc, members))
    return out


# ── recipes ────────────────────────────────────────────────────────────────────────────────────

def _read(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise HepError("cannot read the recipe", where=str(path)) from None
    except tomllib.TOMLDecodeError as error:
        raise HepError(f"cannot read the recipe: {error}", where=str(path)) from None


def _is_recipe(path: Path) -> bool:
    try:
        return set(_read(path)) == {"report"}
    except HepError:
        return False


def recipe_of(name: str) -> Path | None:
    """The recipe a command's first argument names, always a .toml file, named as a run config is: <P>/<name>.toml
    under configs/, ./… the work dir's, /… a path. A recipe of its own, a run TOML or a folder's report.toml. None:
    the argument is a source."""
    if not name.endswith(".toml"):
        return None
    try:
        return config_file(name).resolve()
    except HepError:
        raise HepError(f"no recipe {name}", where=str(configs_root()),
                       hint="a recipe is a .toml file: <P>/<name>.toml under configs/, ./… from the work dir, or /…") from None


def recipes(project: str | None = None) -> list[str]:
    """Every recipe of its own under configs/ ([report] alone), as <P>/<name>.toml (heimdall ls, check)."""
    root = configs_root()
    return [p.relative_to(root).as_posix() for p in sorted(root.glob(f"{project or '*'}/*.toml")) if _is_recipe(p)]


def load_recipe(path: Path) -> dict:
    """A recipe's [report] table, checked, its template laid under it (V209): a recipe of its own ([report] alone,
    every key against report.toml), or a run TOML's [report] as it is read (its from and output a recipe's)."""
    data = _read(path)
    if "run" in data:
        return dict(configmod.load(str(path)).report)
    if set(data) != {"report"}:
        others = sorted(set(data) - {"report"})
        raise HepError(f"a recipe has [report] alone, not [{others[0]}]" if others else "a recipe has a [report] table",
                       where=str(path), hint="[report] title = …, then [[report.section]] tables (04 §15)")
    configmod.check_report(data["report"], f"{path}: [report]")
    project = configmod._project_of(path, data, "")
    table, _ = configmod.report_of(data["report"], path, project, f"{path}: [report]")
    return table


def filled(text: str, facts: list[dict]) -> str:
    """A title with {project}, {run}, {configuration} and {title} filled in from its sources' [source] tables
    (several values joined by commas; a title: the configuration's, else its name)."""
    for word in PLACEHOLDERS:
        mark = "{" + word + "}"
        if mark in text:
            values = [str(f.get("title") or f.get("configuration", "") if word == "title" else f.get(word, "")) for f in facts]
            text = text.replace(mark, ", ".join(dict.fromkeys(v for v in values if v)))
    return text


def _drawn_sets(plot: dict) -> list[str]:
    """The sets a plot document draws: its [plot].draw, else every set of its [plot].sets (the totality alone when
    it names none); none without a [plot]."""
    if not plot:
        return []
    if isinstance(plot.get("draw"), list):
        return list(plot["draw"])
    sets = plot.get("sets")
    return list(sets) if isinstance(sets, dict) and sets else ["totality"]


def _sections(sets: list[str], measured: list[str]) -> list[dict]:
    head = [{"title": "Standings", "set": measured[0], "stats": list(HEADLINE), "optional": True}] if measured else []
    return head + [{"title": f"Pages: {s}", "set": s, "pages": ["*"], "optional": True} for s in sets]


def default_sections(plot: dict, stats: dict) -> list[dict]:
    """The default report's sections for a plot document's [plot] and [stats] (A1): Standings, the statistics'
    headline, on the first set it measures ([stats].sets, else the sets drawn), then the pages of each set it
    draws; every one optional, so a set drawn nowhere is left out."""
    sets = _drawn_sets(plot)
    return _sections(sets, list((stats or {}).get("sets") or sets))


def default_recipe(found: list[Source]) -> dict:
    """No recipe (N1, A1): the default sections over these sources, their sets together in order (a document with
    no [plot]: the sets drawn in its folder)."""
    sets: list[str] = []
    measured: list[str] = []
    for source in found:
        own = _drawn_sets(source.doc.plot or {}) or source.sets()
        sets += [s for s in own if s not in sets]
        measured += [s for s in ((source.doc.stats or {}).get("sets") or own) if s not in measured]
    return {"section": _sections(sets, measured)}


def _value(value) -> str:
    return plotdoc._inline(value)


def dumps(table: dict) -> str:
    """A recipe as TOML: [report]'s keys, then each [[report.section]], its title first."""
    lines = ["[report]", *(f"{k} = {_value(v)}" for k, v in table.items() if k != "section")]
    for section in table.get("section", []):
        lines += ["", "[[report.section]]", *(f"{k} = {_value(v)}" for k, v in
                                               sorted(section.items(), key=lambda kv: kv[0] != "title"))]
    return "\n".join(lines) + "\n"


def _named(path: Path) -> str:
    root = configs_root().resolve()
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def write_recipe(run, document: Path) -> Path:
    """results/<P>/<run>/<cfg>/report.toml (V209), beside the plot document just written: the run TOML's [report]
    (its template laid under it), else the default report for the document's sets, its title's placeholders filled
    in. Rewritten whole each time; `heimdall report <folder>` builds it."""
    data = _read(document)
    table = {k: v for k, v in (getattr(run, "report", None) or {}).items()}
    if not table.get("section"):
        table["section"] = default_sections(data.get("plot", {}), data.get("stats", {}))
    for key in ("title", "subtitle"):
        if table.get(key):
            table[key] = filled(table[key], [data.get("source", {})])
    address = _address(document.parent)
    config = f"{record.config_name(run)}.toml"
    templates = [_named(Path(p)) for p in getattr(run, "templates", [])]
    own = getattr(run, "report", None) or {}
    given = (f"{config}'s [report]" + (f" and its template {', '.join(templates)}" if templates else "")
             + ("" if own.get("section") else ", its sections the default report's") if own
             else f"the default report ({config} has no [report])")
    header = [f"# This folder's report (V209): `heimdall report {address}` builds it into reports/.",
              f"# The run wrote it from {given}.",
              "# It is written again each time plot.toml is: edit the config (or its template), or copy this file",
              f"# into configs/ as a recipe of your own: heimdall report <P>/<name>.toml {address}"]
    target = document.with_name(RECIPE)
    partial = target.with_name(f"{target.name}.{os.getpid()}.partial")
    partial.write_text("\n".join(header) + "\n\n" + dumps(table), encoding="utf-8")
    partial.replace(target)
    return target


# ── the plan ───────────────────────────────────────────────────────────────────────────────────

@dataclass
class Figure:
    """One drawn page (or a file of the recipe's) in a grid: copied from where it is, or drawn for the report."""
    source: Source | None
    set: str
    page: str                    # its name in the set ([<cell>/]<object>), or the file's
    file: Path | None            # what is shown; None: drawn for the report (P6)
    label: str = ""              # a side-by-side panel's
    why: str = ""                # why it is drawn for the report


@dataclass
class Grid:
    caption: str
    figures: list[Figure]
    columns: int | None = None


@dataclass
class Part:
    """A source's statistics, some of its summary's sections, from its set's statistics.csv."""
    source: Source
    set: str
    keys: list[str]
    csv: Path | None             # None: measured for the report (P6)


@dataclass
class Bars:
    """Bar graphs of a source's pages' numbers, drawn for the report from statistics.csv."""
    source: Source
    set: str
    pages: list[str]
    csv: Path | None


@dataclass
class Section:
    title: str
    note: str = ""
    grids: list[Grid] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    bars: list[Bars] = field(default_factory=list)
    plot: dict = field(default_factory=dict)


@dataclass
class Plan:
    name: str                    # the command that builds it: heimdall report <name>
    title: str
    subtitle: str
    sources: list[Source]        # every source a section takes, in order
    sections: list[Section]
    out: Path
    recipe: Path | None = None
    left: list[str] = field(default_factory=list)      # optional sections no source has, and why

    def drawn(self) -> list:
        """What is drawn or measured for the report: figures with no file, parts and bars with no CSV."""
        return [f for s in self.sections for g in s.grids for f in g.figures if f.file is None] + \
               [p for s in self.sections for p in [*s.parts, *s.bars] if p.csv is None]

    def pages(self) -> int:
        """About how many pages its figures take (the statistics' are counted when they are laid out)."""
        return 1 + sum(math.ceil(len(g.figures) / PER_PAGE) for s in self.sections for g in s.grids)


def _backends(section: dict) -> tuple[str, ...]:
    chosen = section.get("backend")
    return BACKENDS if chosen is None else (chosen,) if isinstance(chosen, str) else tuple(chosen)


def _cell(name: str) -> str:
    return name.rsplit("/", 1)[0] if "/" in name else ""


def _refuse_missing(source: Source, set_: str, where: str, allow_drawn: bool) -> None:
    if not allow_drawn:
        raise HepError(f"{source.address} has no set {set_} drawn", where=where,
                       hint=f"heimdall plot {source.address} --sets {set_} draws it"
                            + (f"; drawn there: {', '.join(source.sets())}" if source.sets() else "")
                            + "; optional = true passes it over")


def _pages_section(section: dict, found: list[Source], where: str, allow_drawn: bool) -> list[Grid]:
    set_, globs = section.get("set", "totality"), section["pages"]
    cells, backends = section.get("cells"), _backends(section)
    if section.get("optional"):
        found = [s for s in found if s.pages(set_, backends)]
    chosen: dict[str, dict[str, Path]] = {}
    for source in found:
        drawn = source.pages(set_, backends)
        if not drawn:
            _refuse_missing(source, set_, where, allow_drawn)
        names = [n for n in drawn if any(_matches(n, g) for g in globs)
                 and (cells is None or any(fnmatch.fnmatchcase(_cell(n), c) for c in cells))]
        if not names:
            raise HepError(f"pages: {', '.join(globs)} names no page drawn in {source.address}/plots/{set_}/", where=f"{where}.pages",
                           hint=f"its pages: {', '.join(list(drawn)[:6])}{' …' if len(drawn) > 6 else ''}" if drawn else None)
        chosen[source.address] = {n: drawn[n] for n in names}
    grids: list[Grid] = []
    if section.get("layout", "pages") == "sources":
        how = section.get("label", "folder")
        named = labels(found, how)
        twice = [label for label in named.values() if list(named.values()).count(label) > 1]
        if twice:
            raise HepError(f"two sources are labelled {twice[0]}", where=f"{where}.label",
                           hint='label = "folder" labels them by their folders')
        names = sorted({n for pages in chosen.values() for n in pages}, key=natural)
        for name in names:
            absent = [s.address for s in found if name not in chosen[s.address]]
            if absent:
                raise HepError(f"{absent[0]} has no page {name} in plots/{set_}/", where=f"{where}.pages",
                               hint="draw it there, or leave that source out of the section's from")
            grids.append(Grid(f"{set_} · {name}", [Figure(s, set_, name, chosen[s.address][name], named[s.address]) for s in found],
                              section.get("columns") or (3 if len(found) >= 3 else None)))
        return grids
    for source in found:
        by_cell: dict[str, list[str]] = {}
        for name in chosen[source.address]:
            by_cell.setdefault(_cell(name), []).append(name)
        for cell, names in by_cell.items():
            caption = " · ".join(part for part in (source.address, set_, cell) if part)
            grids.append(Grid(caption, [Figure(source, set_, n, chosen[source.address][n], n.rsplit("/", 1)[-1]) for n in names],
                              section.get("columns")))
    return grids


def _compare_section(section: dict, found: list[Source], where: str) -> list[Grid]:
    grids: list[Grid] = []
    runs = list(dict.fromkeys(s.folder.parent for s in found))
    for run in runs:
        for name in section["compare"]:
            for backend in _backends(section):
                where_ = run / "compare" / name / backend
                pages = sorted((p for p in where_.rglob("*.p[dn][fg]")), key=lambda p: natural(str(p))) if where_.is_dir() else []
                shown: dict[str, Path] = {}
                for p in pages:
                    rel = p.relative_to(where_).with_suffix("").as_posix()
                    if rel.startswith("sheets/"):
                        continue
                    if rel not in shown or p.suffix.lower() == ".pdf":
                        shown[rel] = p
                if shown:
                    grids.append(Grid(f"{_address(run)} · compare {name}", [Figure(None, "", rel, path, rel.rsplit('/', 1)[-1])
                                                                         for rel, path in shown.items()], section.get("columns")))
                    break
            else:
                raise HepError(f"compare: no page of {name} drawn in {_address(run)}/compare/", where=f"{where}.compare",
                               hint="a compare figure is drawn by its configurations' plot stage (03 §7.5)")
    return grids


def _files_section(section: dict, base: Path, where: str) -> list[Grid]:
    files: list[Path] = []
    for glob in section["files"]:
        found = sorted((p for p in base.glob(glob) if p.suffix.lower() in (".pdf", ".png")), key=lambda p: natural(p.name))
        if not found:
            raise HepError(f"files: '{glob}' names no PDF or PNG file in {base}", where=f"{where}.files")
        files += [p for p in found if p not in files]
    return [Grid(section["title"], [Figure(None, "", p.stem, p.resolve(), p.stem) for p in files], section.get("columns"))]


def _numbers(spec: dict, found: list[Source], set_: str, where: str, allow_drawn: bool) -> list[tuple[Source, Path | None]]:
    """A stats or bars section's sources and their set's statistics.csv; optional: those without it passed over."""
    out = []
    for source in found:
        csv = source.numbers(set_)
        if csv is None and spec.get("optional"):
            continue
        if csv is None and not allow_drawn:
            raise HepError(f"{source.address} has no statistics for {set_}", where=where,
                           hint=f"heimdall stats {source.address} --sets {set_} measures them; optional = true passes it over")
        out.append((source, csv))
    return out


def _out(recipe: dict, used: list[Source], where: str) -> Path:
    """Where a report is built when -o names nowhere (A6): its [report].output (a folder under reports/, ./… the
    work dir's, /… a path), else where results/ has its sources: their common address under reports/."""
    given = recipe.get("output")
    if given:
        if given.startswith("../") or "/../" in given:
            raise HepError(f"output '{given}' climbs out of reports/", where=f"{where}.output", hint="name a folder under reports/, or ./… or /…")
        return Path(given) if given.startswith("/") else work_root() / given[2:] if given.startswith("./") else reports_root() / given
    outside = [s.address for s in used if Path(s.address).is_absolute()]
    if outside:
        raise HepError(f"{outside[0]} is not under results/, so its report has no place of its own under reports/", where=where,
                       hint='-o DIR builds it there, or output = "<folder>" in its [report]')
    common = _common(used)
    if not common:
        projects = ", ".join(dict.fromkeys(s.address.split("/", 1)[0] for s in used))
        raise HepError(f"its sources are of several projects ({projects}), so its report has no one place under reports/",
                       where=where, hint='-o DIR builds it there, or output = "<folder>" in its [report]')
    return reports_root() / common


def resolve(recipe: dict, given: list[str], *, path: Path | None = None, command: str = "", out: Path | None = None,
            allow_drawn: bool = False, found: list[Source] | None = None) -> Plan:
    """A recipe ([report], its sections) and its sources as a Plan; with no sections, the default's. `given`: the
    command line's sources, which replace [report].from (`found`: them, read already); a section's own from stays.
    `allow_drawn`: what is not on disk is drawn for the report (P6), else refused naming the command that makes it.
    An optional section no source has is left out, and said."""
    where = str(path) if path else "the default report"
    named = given or recipe.get("from", [])
    if not named and not any(s.get("from") for s in recipe.get("section", [])):
        raise HepError("a report needs a source", where=where,
                       hint="heimdall report <recipe>.toml <P>/<run>/<cfg>, or from = [\"<P>/<run>/<cfg>\"] in [report]")
    every = found if found is not None else sources(named, "the command line" if given else f"{where}: [report].from") if named else []
    specs = recipe.get("section") or default_recipe(every)["section"]
    sections: list[Section] = []
    left: list[str] = []
    used: list[Source] = list(every)
    for number, spec in enumerate(specs, 1):
        at = f"{where}: section {number} ({spec.get('title', '')})"
        found_ = sources(spec["from"], f"{at}.from") if spec.get("from") else every
        used += [s for s in found_ if s not in used]
        section = Section(spec["title"], spec.get("note", ""), plot=dict(spec.get("plot", {})))
        set_ = spec.get("set", "totality")
        if "pages" in spec:
            section.grids = _pages_section(spec, found_, at, allow_drawn)
        elif "compare" in spec:
            section.grids = _compare_section(spec, found_, at)
        elif "files" in spec:
            section.grids = _files_section(spec, path.parent if path else Path.cwd(), at)
        elif "stats" in spec:
            section.parts = [Part(s, set_, list(spec["stats"]), csv) for s, csv in _numbers(spec, found_, set_, f"{at}.stats", allow_drawn)]
        else:
            section.bars = [Bars(s, set_, list(spec["bars"]), csv) for s, csv in _numbers(spec, found_, set_, f"{at}.bars", allow_drawn)]
        if spec.get("optional") and not (section.grids or section.parts or section.bars):
            left.append(f"{spec['title']}: no source has {set_} {'drawn' if 'pages' in spec else 'measured'}")
            continue
        sections.append(section)
    facts = [s.doc.source for s in used]
    title = filled(recipe.get("title", ""), facts) or (used[0].address if len(used) == 1 else _common(used) or "report")
    return Plan(command or where, title, filled(recipe.get("subtitle", ""), facts), used, sections,
                out or _out(recipe, used, where), path, left)


def _common(found: list[Source]) -> str:
    """The sources' common address: one source's own, else what their addresses share (eic/zeus_validation); ""
    when they share no project."""
    parts = [s.address.split("/") for s in found]
    shared = []
    for column in zip(*parts):
        if len(set(column)) != 1:
            break
        shared.append(column[0])
    return "/".join(shared)


def planned(first: str | None, rest: list[str], out: Path | None = None, allow_drawn: bool = False) -> Plan:
    """`heimdall report [RECIPE.toml] [SOURCE…]` (A5): a first argument ending .toml is a recipe (of its own, a run
    TOML's [report], a folder's report.toml), over the sources after it, else over its own from; else every
    argument is a source, and one folder's report is its report.toml (else the default), several sources' the
    default."""
    command = " ".join(n for n in (first, *rest) if n)
    path = recipe_of(first) if first else None
    if path is not None:
        recipe = load_recipe(path)
        if path.name == RECIPE and not rest and not recipe.get("from") and (path.parent / plotdoc.FILE).is_file():
            rest = [str(path.parent)]                     # a folder's own report.toml: that folder
        if "run" in _read(path) and not rest:
            raise HepError("a run TOML's [report] is its folders' reports: name the folders", where=str(path),
                           hint=f"heimdall report {first} <P>/<run>/<cfg>")
        return resolve(recipe, rest, path=path, command=command, out=out, allow_drawn=allow_drawn)
    given = [first, *rest] if first else list(rest)
    if not given:
        raise HepError("a report needs a source", hint="heimdall report <P>/<run>/<cfg>; heimdall report <recipe>.toml <source>")
    found = sources(given, "the command line")
    own = found[0].folder / RECIPE if len(found) == 1 else None
    if own is not None and own.is_file():
        return resolve(load_recipe(own), given, path=own, command=command, out=out, allow_drawn=allow_drawn, found=found)
    return resolve({}, given, command=command, out=out, allow_drawn=allow_drawn, found=found)


def listing(plan: Plan) -> list[str]:
    """`heimdall report … --list`: its sources, then each section and what it shows, nothing written."""
    lines = [f"report {plan.name} → {plan.out}: {len(plan.sources)} source(s), {len(plan.sections)} section(s), "
             f"about {plan.pages()} page(s) of figures" + (f"; from {plan.recipe}" if plan.recipe else "; the default")]
    for source in plan.sources:
        f = source.facts()
        lines.append(f"  source {f['address']}: {f['configuration'] or source.doc.name}, {f['complete']} of {f['points']} point(s)"
                     + (f", {f['events']} events" if f["events"] else "") + f", against {f['against']}"
                     + (", its points newer than its pages" if f["stale"] else ""))
    for number, section in enumerate(plan.sections, 1):
        figures = [fig for g in section.grids for fig in g.figures]
        drawn = [fig for fig in figures if fig.file is None]
        what, under = [], [f"{grid.caption}: {len(grid.figures)}" for grid in section.grids]
        if section.grids:
            what.append(f"{len(section.grids)} grid(s), {len(figures)} figure(s)" + (f", {len(drawn)} drawn for the report" if drawn else ""))
        for kind, items in (("statistics", section.parts), ("bar graphs", section.bars)):
            if not items:
                continue
            shown = ", ".join(items[0].keys if kind == "statistics" else items[0].pages)
            if len(items) == 1:
                what.append(f"{kind} of {items[0].source.address} · {items[0].set}: {shown}")
            else:
                what.append(f"{kind} of {len(items)} sources: {shown}")
            under += [f"{item.source.address} · {item.set}" + ("" if item.csv else " (measured for the report)")
                      for item in items if len(items) > 1 or not item.csv]
        lines.append(f"  {number} {section.title}: " + "; ".join(what))
        lines += [f"      {line}" for line in under]
    lines += [f"  left out: {why}" for why in plan.left]
    return lines


def starter(name: str, source: Source) -> str:
    """`--init`: the default report's sections as a recipe, each set's cells and pages listed, and the sets
    drawn that its document does not draw by default as sections commented out (V207)."""
    lines = [f"# configs/{name}: a report, `heimdall report {name} <source>` (docs/03_Plots.md §11; its keys 04 §15).",
             "# The sources on the command line replace `from`; each [[report.section]] shows one of pages, compare,",
             "# stats, bars or files.", "", "[report]", f'title = "{source.doc.name} · {source.name}"',
             '# subtitle = "for the group, <date>"', f'from  = ["{source.address}"]', ""]
    sections = default_recipe([source])["section"]
    shown = [s["set"] for s in sections if "pages" in s]
    for section in sections:
        if "stats" in section:
            lines += ["[[report.section]]", 'title = "Standings"', f'set   = "{section["set"]}"',
                      "stats = [" + ", ".join(f'"{k}"' for k in HEADLINE) + "]", "optional = true", ""]
    for set_ in [*shown, *(s for s in source.sets() if s not in shown)]:
        pages = source.pages(set_, BACKENDS)
        cells = sorted({_cell(n) for n in pages}, key=natural)
        objects = sorted({n.rsplit("/", 1)[-1] for n in pages}, key=natural)
        mark = "" if set_ in shown else "# "
        lines += [f"# {set_}: {len(pages)} page(s)" + (f" in {len(cells)} cell(s): {', '.join(cells[:8])}"
                                                        f"{' …' if len(cells) > 8 else ''}" if any(cells) else ""),
                  f"#   {', '.join(objects[:12])}{' …' if len(objects) > 12 else ''}",
                  *(mark + line for line in ("[[report.section]]", f'title = "{set_}"', f'set   = "{set_}"', 'pages = ["*"]',
                                             "optional = true")), ""]
    return "\n".join(lines)


# ── the build ──────────────────────────────────────────────────────────────────────────────────

FIGURES, STATS, STAMPS = "figures", "stats", ".stamps.json"
#: A4 in bp and its text block (15 mm margins). A grid's picture is at most ROOM high, leaving its caption and, on a
#: section's first page, the section's heading and note.
A4_BP = (595.28, 841.89)
MARGIN = 42.52
TEXT_W, TEXT_H = A4_BP[0] - 2 * MARGIN, A4_BP[1] - 2 * MARGIN
ROOM = TEXT_H - 80.0
GAP, LABEL = 6.0, 11.0
#: What pdflatex leaves beside report.tex, removed once report.pdf is made.
LEFTOVERS = (".aux", ".log", ".out", ".toc")
BUILT = "\0built\0"


def slug(text: str) -> str:
    """A part of a file's name: letters, digits, `.` and `-`; anything else `_`."""
    return re.sub(r"[^A-Za-z0-9.-]+", "_", text).strip("_.") or "x"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _layout():
    return plugins.load(hep_root() / "framework" / "plot" / "figures" / "layout.py", "layout")


@dataclass
class Placed:
    """A grid as the report shows it: its files in the report's folder, their labels and \\includegraphics keys
    (`page=2`), their PNGs for index.html (else the file itself), its columns and its first file's aspect."""
    caption: str
    files: list[Path]
    labels: list[str]
    options: list[str]
    pngs: list[Path]
    columns: int
    aspect: float
    label: float = LABEL


class _Build:
    """A build's books: the stamps read and written, the files the report holds and their sha256, what was copied
    and what drawn. A stamp, `.stamps.json`, says what a file was made from, so a rebuild makes only what changed."""

    def __init__(self, out: Path):
        self.out = out
        try:
            self.old = json.loads((out / STAMPS).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.old = {}
        self.new: dict = {}
        self.shas: dict[str, str] = {}
        self.copied = self.drawn = 0

    def rel(self, path: Path) -> str:
        return path.relative_to(self.out).as_posix()

    def copy(self, source: Path, target: Path) -> str:
        """`source` copied to `target`, unless it holds the same bytes already; its sha256."""
        sha = _sha(source)
        if not target.is_file() or _sha(target) != sha:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            self.copied += 1
        self.shas[self.rel(target)] = sha
        return sha

    def stamped(self, first: Path, key: str, make) -> list[Path]:
        """The files `make()` makes (a list, `first` first), unless `first`'s stamp says they were made from `key`
        and each is still there; those files."""
        stamp = self.old.get(self.rel(first))
        files = [self.out / f for f in stamp["files"]] if stamp and stamp.get("key") == key else []
        if not files or not all(f.is_file() for f in files):
            files = make()
            self.drawn += 1
        self.new[self.rel(first)] = {"key": key, "files": [self.rel(f) for f in files]}
        for f in files:
            self.shas[self.rel(f)] = _sha(f)
        return files

    def prune(self) -> None:
        """What no section holds any more, removed from figures/ and stats/ (and their empty folders)."""
        for top in (FIGURES, STATS):
            root = self.out / top
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if path.is_file() and self.rel(path) not in self.shas:
                    path.unlink()
                elif path.is_dir() and not any(path.iterdir()):
                    path.rmdir()

    def save(self) -> None:
        (self.out / STAMPS).write_text(json.dumps(self.new, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _aspect(path: Path, default: float = 4 / 3) -> float:
    try:
        w, h = _layout().size_of(path)
        return w / h if h else default
    except ValueError:
        return default


def _figure(build: _Build, figure: Figure, folder: Path, stem: str) -> tuple[Path, Path]:
    """A figure into the report's folder: its PDF (else its PNG) copied, and its PNG copied, or rendered from the
    PDF when it has none (none either without pdftoppm); (what report.tex shows, what index.html shows)."""
    given = figure.file
    if given.suffix.lower() != ".pdf":
        shown = folder / f"{stem}{given.suffix.lower()}"
        build.copy(given, shown)
        return shown, shown
    pdf, png = folder / f"{stem}.pdf", folder / f"{stem}.png"
    sha = build.copy(given, pdf)
    if given.with_suffix(".png").is_file():
        build.copy(given.with_suffix(".png"), png)
        return pdf, png

    def render() -> list[Path]:
        _layout().png(pdf, png, dpi=150)
        return [png]
    try:
        build.stamped(png, sha, render)
    except ValueError:
        return pdf, pdf
    return pdf, png


def chosen(document, keys: list[str]):
    """The summary's sections that `keys` name, in their order: a whole section, or one of a statistic's parts
    (`chi2_ndf:ranking`, `:crossed`, `:table`). Its facts and notes stay (only the notes its items name are
    numbered). (The document, the keys it has no part for.)"""
    by_key = {s.key: s for s in document.sections}
    kept, missing = [], []
    for key in keys:
        statistic, _, part = key.partition(":")
        section = by_key.get(statistic)
        want = statistic if part == "table" else f"{statistic}-{part}"
        items = [] if section is None else [i for i in section.items if not part or i.key == want]
        if items:
            kept.append(dataclasses.replace(section, items=items))
        else:
            missing.append(key)
    return dataclasses.replace(document, sections=kept), missing


def _code(bars) -> str:
    """What the statistics' pages are drawn by: bars.py and paper.py, as they are."""
    return _key(_sha(Path(bars.__file__)), _sha(Path(bars.paper.__file__)))


def _part(build: _Build, bars, part: Part, folder: Path, stem: str, say) -> Placed | None:
    """A source's statistics, the sections chosen, as A4 pages: stats/<section>/<stem>.pdf and a PNG a page."""
    heading = statstable.heading_of(part.csv.parent)
    target = folder / stem
    missing: list[str] = []

    def make() -> list[Path]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        document, gone = chosen(bars.summary_model(statstable.read(part.csv), heading), part.keys)
        missing.extend(gone)
        if not document.sections:
            return []
        return bars.paper.write(document, target, ["pdf", "png"], f"Statistics: {heading}", plt)
    key = _key(_sha(part.csv), heading, *part.keys, _code(bars))
    stamp = build.old.get(build.rel(target.with_suffix(".pdf")))
    files = build.stamped(target.with_suffix(".pdf"), key, make)
    gone = missing or (stamp or {}).get("missing", [])
    build.new[build.rel(target.with_suffix(".pdf"))]["missing"] = gone
    if gone:
        say(f"report: {heading} has no {', '.join(gone)} (too few curves or page cells for them)")
    pdf, pngs = (files[0], sorted(files[1:], key=lambda p: natural(p.name))) if files else (None, [])
    if pdf is None:
        build.new.pop(build.rel(target.with_suffix(".pdf")), None)
        return None
    summary = part.csv.with_name("summary.html")
    if summary.is_file():
        build.copy(summary, build.out / STATS / "summaries" / f"{slug(part.source.address)}__{slug(part.set)}.html")
    return Placed(f"Statistics: {heading}", [pdf] * len(pngs), [""] * len(pngs), [f"page={k}" for k in range(1, len(pngs) + 1)],
                  pngs, 1, paper_aspect(bars), 0.0)


def paper_aspect(bars) -> float:
    w, h = bars.paper.A4
    return w / h


def _bars(build: _Build, bars, item: Bars, folder: Path) -> Placed:
    """A source's pages' bar graphs, drawn from its statistics.csv: stats/<section>/<NNN>_<source>_<page>.pdf."""
    rows = statstable.read(item.csv)
    pages: dict[str, list[dict]] = {}
    for row in rows:
        pages.setdefault(row["page"], []).append(row)
    names = [n for n in sorted(pages, key=natural) if any(_matches(n, g) for g in item.pages)]
    if not names:
        raise HepError(f"bars: {', '.join(item.pages)} names no page measured in {item.csv}",
                       hint=f"its pages: {', '.join(list(sorted(pages, key=natural))[:6])} …" if pages else None)
    base = _key(_sha(item.csv), _code(bars))
    files, options, pngs = [], [], []
    for number, name in enumerate(names, 1):
        target = folder / f"{number:03d}_{slug(item.source.folder.name)}_{slug(name)}"
        made = build.stamped(target.with_suffix(".pdf"), _key(base, name),
                             lambda name=name, target=target: bars.page(pages[name], target, ["pdf", "png"],
                                                                       f"{item.source.address} · {name}"))
        shown = sorted((f for f in made if f.suffix == ".png"), key=lambda p: natural(p.name))
        files += [target.with_suffix(".pdf")] * len(shown)
        options += [f"page={k}" for k in range(1, len(shown) + 1)]
        pngs += shown
    return Placed(f"Bar graphs: {item.source.address} · {item.set}", files, [""] * len(files), options, pngs, 1,
                  paper_aspect(bars), 0.0)


def _place(build: _Build, plan: Plan, say) -> list[tuple[Section, list[Placed]]]:
    """Every section's figures copied into figures/<NN>_<section>/, its statistics and bar graphs drawn into
    stats/<NN>_<section>/; each grid as the report shows it."""
    bars = statstable.bars()
    placed = []
    for number, section in enumerate(plan.sections, 1):
        name = f"{number:02d}_{slug(section.title)}"
        grids: list[Placed] = []
        count = 0
        for grid in section.grids:
            files, pngs = [], []
            for figure in grid.figures:
                count += 1
                stem = f"{count:03d}_{slug(figure.source.folder.name)}_{slug(figure.page)}" if figure.source else \
                    f"{count:03d}_{slug(figure.page)}"
                shown, png = _figure(build, figure, build.out / FIGURES / name, stem)
                files.append(shown)
                pngs.append(png)
            columns = grid.columns or (1 if len(files) == 1 else 2)
            grids.append(Placed(grid.caption, files, [f.label for f in grid.figures], [""] * len(files), pngs,
                                columns, _aspect(grid.figures[0].file)))
        for k, part in enumerate(section.parts, 1):
            shown = _part(build, bars, part, build.out / STATS / name, f"{k:02d}_{slug(part.source.folder.name)}", say)
            if shown is not None:
                grids.append(shown)
        for item in section.bars:
            grids.append(_bars(build, bars, item, build.out / STATS / name))
        placed.append((section, grids))
    return placed


def _breakable(text: str) -> str:
    """Text for LaTeX that may break after a / or an _ (an address, a folder's name)."""
    return _layout().tex(text).replace("/", "/\\allowbreak{}").replace("\\_", "\\_\\allowbreak{}")


def _chunks(placed: Placed) -> list[tuple[int, int, tuple[float, float], float, float]]:
    """A grid cut into pictures that each fit a page: (first, last figure, box, cell width, cell height)."""
    columns = placed.columns
    cw = (TEXT_W - (columns - 1) * GAP) / columns
    ch = min(cw / placed.aspect, ROOM - placed.label)
    rows = max(1, int((ROOM + GAP) // (ch + placed.label + GAP)))
    out = []
    for start in range(0, len(placed.files), rows * columns):
        end = min(len(placed.files), start + rows * columns)
        shown_rows = math.ceil((end - start) / columns)
        out.append((start, end, (TEXT_W, shown_rows * (ch + placed.label) + (shown_rows - 1) * GAP), cw, ch))
    return out


PREAMBLE = r"""\documentclass[a4paper,10pt]{article}
%% Made by heimdall report: every file it names is in this folder, so it compiles here as it is (pdflatex, twice).
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=15mm]{geometry}
\usepackage{graphicx}
\usepackage{array}
\usepackage[hidelinks,bookmarksdepth=2]{hyperref}
\renewcommand{\familydefault}{\sfdefault}
\setlength{\parindent}{0pt}
\setcounter{tocdepth}{1}
\setlength{\unitlength}{1bp}
"""


def _front(plan: Plan) -> list[str]:
    """The front page's lines: the title, when and by what it was made, each source's facts and its flags."""
    tex = _layout().tex
    lines = [r"{\LARGE\bfseries " + tex(plan.title) + r"\par}"]
    if plan.subtitle:
        lines += [r"\vspace{3pt}", r"{\large " + tex(plan.subtitle) + r"\par}"]
    lines += [r"\vspace{6pt}", r"{\small Made by \texttt{heimdall report " + _breakable(plan.name) + "} " + BUILT + r".\par}",
              r"\vspace{12pt}", r"{\large\bfseries Sources\par}\vspace{4pt}",
              r"{\small\begin{tabular}{@{}r>{\raggedright\arraybackslash}p{64mm}>{\raggedright\arraybackslash}p{30mm}"
              r"rr>{\raggedright\arraybackslash}p{34mm}@{}}",
              r" & Source & Configuration & Points & Events & Compared against\\", r"\hline"]
    flags = []
    for number, source in enumerate(plan.sources, 1):
        f = source.facts()
        drawn = " · ".join(part for part in (f["written"][:16].replace("T", " "), f"Heimdall {f['heimdall']}" if f["heimdall"] else "") if part)
        lines.append(f"{number} & \\texttt{{{_breakable(f['address'])}}}" + (f"\\newline{{\\scriptsize {tex(drawn)}}}" if drawn else "")
                     + f" & {_breakable(f['configuration'] or source.doc.name)} & {f['complete']}/{f['points']}"
                     + f" & {tex(f['events'] or '?')} & {tex(f['against'])}\\\\")
        if f["incomplete"]:
            shown = ", ".join(f["incomplete"][:6]) + (" …" if len(f["incomplete"]) > 6 else "")
            flags.append(f"\\texttt{{{_breakable(f['address'])}}}: {len(f['incomplete'])} of {f['points']} point(s) not "
                         f"complete ({_breakable(shown)}); its pages show the complete ones.")
        if f["stale"]:
            flags.append(f"\\texttt{{{_breakable(f['address'])}}}: its points are newer than its pages; "
                         f"\\texttt{{heimdall plot {_breakable(f['address'])}}} redraws them.")
    lines += [r"\end{tabular}\par}"]
    if flags:
        lines += [r"\vspace{6pt}", r"{\small\begin{itemize}\setlength{\itemsep}{1pt}",
                  *(r"\item " + flag for flag in flags), r"\end{itemize}\par}"]
    return lines + [r"\vspace{8pt}", r"\tableofcontents", r"\clearpage"]


def _tex(plan: Plan, placed: list[tuple[Section, list[Placed]]], out: Path) -> str:
    """report.tex, with BUILT for when and by what it was made: its front page, its contents, then each section
    on a new page, each grid in pictures that fit a page, each file named relative to the folder."""
    layout = _layout()
    tex = layout.tex
    lines = [PREAMBLE + f"\\hypersetup{{pdftitle={{{tex(plan.title)}}}}}", r"\begin{document}", *_front(plan)]
    for section, grids in placed:
        lines += [r"\clearpage", f"\\section{{{tex(section.title)}}}"]
        if section.note:
            lines += [tex(section.note) + r"\par", r"\vspace{6pt}"]
        for grid in grids:
            pieces = _chunks(grid)
            lines.append(f"\\phantomsection\\addcontentsline{{toc}}{{subsection}}{{{tex(grid.caption)}}}")
            for k, (start, end, box, cw, ch) in enumerate(pieces, 1):
                rows = math.ceil((end - start) / grid.columns)
                caption = grid.caption + (f" ({k}/{len(pieces)})" if len(pieces) > 1 else "")
                names = [f.relative_to(out).as_posix() for f in grid.files[start:end]]
                lines += [r"\noindent\begin{minipage}{\textwidth}", r"{\small " + _breakable(caption) + r"\par}\vspace{3pt}",
                          f"\\begin{{picture}}({box[0]:.2f},{box[1]:.2f})",
                          *layout.picture(names, grid.labels[start:end], box, grid.columns, rows, cw, ch, grid.label,
                                          "", 0.0, GAP, grid.options[start:end]),
                          r"\end{picture}", r"\end{minipage}\par\vspace{10pt}"]
    return "\n".join([*lines, r"\end{document}", ""])


def _index(plan: Plan, placed: list[tuple[Section, list[Placed]]], out: Path) -> Path:
    """index.html (the viewer): a block a grid, its panels the PNGs; the sources and their summaries' pages up front."""
    blocks = []
    for number, (section, grids) in enumerate(placed, 1):
        for k, grid in enumerate(grids, 1):
            panels = [(label or (f"page {n}" if len(grid.pngs) > 1 else ""), png) for n, (label, png)
                      in enumerate(zip(grid.labels, grid.pngs), 1)]
            blocks.append(viewer.Shown(f"s{number:02d}-{k:03d}", f"{section.title}: {grid.caption}", panels))
    summaries = {p.name: p for p in sorted((out / STATS / "summaries").glob("*.html"))} if (out / STATS / "summaries").is_dir() else {}
    rows = []
    for source in plan.sources:
        f = source.facts()
        links = [f'<a href="{STATS}/summaries/{html.escape(n, quote=True)}">{html.escape(n.split("__", 1)[1][:-5])}</a>'
                 for n in summaries if n.startswith(slug(source.address) + "__")]
        rows.append(f"<tr><td><code>{html.escape(f['address'])}</code></td><td>{html.escape(f['configuration'])}</td>"
                    f"<td>{f['complete']}/{f['points']}</td><td>{html.escape(f['events'])}</td><td>{html.escape(f['against'])}</td>"
                    f"<td>{' · '.join(links)}</td></tr>")
    front = ('    <header><h2>Sources</h2><span class="more"><a href="report.pdf">report.pdf</a></span></header>\n'
             '    <table><tr><th>Source</th><th>Configuration</th><th>Points</th><th>Events</th><th>Compared against</th>'
             '<th>Statistics summary</th></tr>\n    ' + "\n    ".join(rows) + "\n    </table>")
    return viewer.page(out / "index.html", plan.title, blocks, front)


def _pages_of(pdf: Path) -> int:
    try:
        done = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return 0
    found = re.search(r"^Pages:\s+(\d+)", done.stdout, re.M)
    return int(found[1]) if found else 0


def build(plan: Plan, say=print) -> list[Path]:
    """The report, into plan.out (I-108 P3): figures/ (each figure copied as drawn, its PNG beside it), stats/ (the
    chosen statistics and bar graphs, drawn from each source's statistics.csv), report.tex (A4, naming only files in
    the folder), report.pdf (pdflatex, twice: the contents) and index.html. Only what changed is copied or drawn
    again (`.stamps.json`), and what no section holds any more is removed. The files made."""
    out = plan.out
    for place in (results_root(), *(s.folder for s in plan.sources)):
        if out.resolve().is_relative_to(Path(place).resolve()):
            raise HepError(f"a report is never built into results/: {out}", hint="leave -o out (reports/ mirrors results/), or name another folder")
    if plan.drawn():
        raise HepError("this report needs pages or numbers drawn for it, which comes with its next step",
                       hint="--list says which; heimdall plot or heimdall stats draws them in the source")
    out.mkdir(parents=True, exist_ok=True)
    books = _Build(out)
    placed = _place(books, plan, say)
    books.prune()
    figures = sum(len(g.figures) for s in plan.sections for g in s.grids)
    say(f"report: {figures} figure(s), {books.copied} file(s) copied; "
        f"{sum(len(s.parts) + len(s.bars) for s in plan.sections)} statistics part(s), {books.drawn} drawn")
    text = _tex(plan, placed, out)
    key = _key(text, *(f"{rel}:{sha}" for rel, sha in sorted(books.shas.items())))
    source, pdf = out / "report.tex", out / "report.pdf"
    made = [source, out / "index.html"]
    stamp = books.old.get("report.pdf")
    revision = record.git_state(hep_root()).get("revision", "")[:12]
    when = f"on {datetime.now().strftime('%Y-%m-%d %H:%M')}" + (f", Heimdall {revision}" if revision else "")
    if stamp and stamp.get("key") == key and pdf.is_file() and source.is_file():
        books.new["report.pdf"] = stamp
        say(f"report: report.pdf unchanged ({_pages_of(pdf)} pages)")
        made.insert(0, pdf)
    else:
        source.write_text(text.replace(BUILT, when), encoding="utf-8")
        if shutil.which("pdflatex"):
            try:
                _layout().pdflatex(source, "the report", runs=2)
            except ValueError as error:
                raise HepError(str(error), where=str(source), hint=f"pdflatex's log: {source.with_suffix('.log')}") from None
            for suffix in LEFTOVERS:
                source.with_suffix(suffix).unlink(missing_ok=True)
            books.new["report.pdf"] = {"key": key}
            say(f"report: report.pdf, {_pages_of(pdf)} A4 page(s)")
            made.insert(0, pdf)
        else:
            say("report: no pdflatex on PATH, so no report.pdf: report.tex compiles anywhere else as it is (Overleaf)")
    _index(plan, placed, out)
    books.save()
    say(f"report: {', '.join(p.name for p in made)} in {out}")
    return made
