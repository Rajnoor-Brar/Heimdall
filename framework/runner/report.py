"""`heimdall report` (I-108, .plans/report/): a quick, informal report of one or more runs' pages and numbers,
for colleagues or a supervisor, made only when asked (rank 4).

* **Sources** are result folders holding a plot document (plot.toml): a configuration's, or a run's runs-together
  folder (V169). They are named `<P>/<run>/<cfg>`, `<P>/<run>` (each of its configurations, then its own when it
  is drawn), a path, or a glob of them under results/.
* **A recipe** is `configs/<P>/<name>.toml` with a `[report]` table (framework/schema/report.toml): its title,
  its sources (`from`, which the command line's replace) and its `[[section]]`s, each one kind of item: pages,
  compare, stats, bars or files. Without one, the default recipe: a front page, the statistics' headline and
  each drawn set's pages, a grid per page cell.
* `resolve` turns a recipe and its sources into a `Plan`: its sections' grids of figures, each copied from its
  source or drawn for the report, and its statistics parts. Nothing is written until the build.
"""

from __future__ import annotations

import fnmatch
import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import config as configmod
from . import plotdoc, schema
from .errors import HepError, did_you_mean
from .paths import configs_root, reports_root, results_root

#: The tables of report.toml, a recipe's (I-108).
TABLES = ("report", "section")
#: What a section shows: exactly one of these.
ITEMS = ("pages", "compare", "stats", "bars", "files")
#: Whose drawn pages a section takes, in order of preference, when it names none.
BACKENDS = ("root", "mpl", "yoda")
#: The statistics summary's sections (bars.summary_model), and a statistic's parts by their item's key suffix.
STATISTICS = ("chi2_ndf", "rel_abs_area", "area_ratio", "ratio_mean", "ratio_dev", "area")
SUMMARY = ("top5", "scoreboard", "scoreboard-cells", "head-to-head", "scoreboards", *STATISTICS)
PARTS = ("ranking", "crossed", "table")
#: The default recipe's headline: the top five and each statistic's ranking (the area has none).
HEADLINE = ["top5", *(f"{key}:ranking" for key in STATISTICS if key != "area")]
#: Panels on an A4 page of a grid, for the listing's page count (the build lays them out).
PER_PAGE = 6
GLOB = re.compile(r"[*?\[]")
#: The default recipe's own mark on its sections: a source without the set (or its numbers) is passed over.
QUIET = "_quiet"
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

def _is_recipe(path: Path) -> bool:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return "report" in data and "run" not in data


def recipe_of(name: str) -> Path | None:
    """The recipe a command's first argument names: a .toml path, or configs/<P>/<name>.toml with [report]."""
    if name.endswith(".toml"):
        path = Path(name).expanduser()
        if not path.is_file():
            raise HepError(f"no recipe {path}", hint="a recipe is a TOML file with a [report] table")
        return path.resolve()
    if name.count("/") == 1 and not GLOB.search(name):
        path = configs_root() / f"{name}.toml"
        if path.is_file() and _is_recipe(path):
            return path
    return None


def recipes(project: str | None = None) -> list[str]:
    """Every configs/<P>/<name>.toml with a [report] table, as <P>/<name> (heimdall ls, check)."""
    root = configs_root()
    return [str(p.relative_to(root).with_suffix("")) for p in sorted(root.glob(f"{project or '*'}/*.toml")) if _is_recipe(p)]


def load_recipe(path: Path) -> dict:
    """A recipe, checked: [report] and its [[section]]s, every key against report.toml, each section one item."""
    where = str(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise HepError(f"cannot read the recipe: {error}", where=where) from None
    for table in data:
        if table not in TABLES:
            raise HepError(f"unknown table [{table}]", where=where,
                           hint=did_you_mean(table, TABLES) or "a recipe has [report] and [[section]]s")
    schema.check(data.get("report", {}), "report", f"{where}: [report]")
    sections = data.get("section", [])
    if not isinstance(sections, list):
        raise HepError("a section is a [[section]] table", where=f"{where}: [section]", hint="write [[section]], twice bracketed")
    for number, section in enumerate(sections, 1):
        at = f"{where}: section {number}"
        schema.check(section, "section", at)
        if "title" not in section:
            raise HepError("a section needs a title", where=at)
        kinds = [k for k in ITEMS if k in section]
        if len(kinds) != 1:
            raise HepError(f"a section shows one of {', '.join(ITEMS)}" + (f", not {' and '.join(kinds)}" if kinds else ""),
                           where=at, hint='pages = ["d01-*"], or stats = ["top5"], …')
        for key in section.get("stats", []):
            _check_stat(key, at)
        if "plot" in section:
            configmod.check_plot(section["plot"], f"{at}.plot")
    return data


def _check_stat(key: str, where: str) -> None:
    statistic, _, part = key.partition(":")
    if statistic not in SUMMARY or (part and (part not in PARTS or statistic not in STATISTICS)):
        hint = (f"a statistic's parts: {', '.join(f'{statistic}:{p}' for p in PARTS)}" if statistic in STATISTICS
                else did_you_mean(statistic, SUMMARY) or f"the sections: {', '.join(SUMMARY)}")
        raise HepError(f"stats: no section {key!r}", where=f"{where}.stats", hint=hint)


def default_recipe(found: list[Source]) -> dict:
    """No recipe (N1): the statistics' headline, then each set drawn (the documents' [plot].draw first), its pages
    a grid per page cell."""
    sets: list[str] = []
    for source in found:
        drawn = source.sets()
        wanted = [s for s in (source.doc.plot or {}).get("draw", []) if s in drawn] or drawn
        sets += [s for s in wanted if s not in sets]
    first = next((s for s in sets if any(source.numbers(s) for source in found)), None)
    sections = [{"title": "Standings", "stats": HEADLINE, "set": first, QUIET: True}] if first else []
    sections += [{"title": f"Pages: {set_}", "pages": ["*"], "set": set_, QUIET: True} for set_ in sets]
    return {"report": {}, "section": sections}


# ── the plan ───────────────────────────────────────────────────────────────────────────────────

@dataclass
class Figure:
    """One drawn page (or a file of the recipe's) in a grid: copied from where it is, or drawn for the report."""
    source: Source | None
    set: str
    page: str                    # its name in the set ([<cell>/]<object>), or the file's
    file: Path | None            # what is shown; None: drawn for the report (P4)
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
    csv: Path | None             # None: measured for the report (P4)


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
    name: str                    # <P>/<name>: where it builds, under reports/
    title: str
    subtitle: str
    sources: list[Source]        # every source a section takes, in order
    sections: list[Section]
    out: Path
    recipe: Path | None = None

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
                            + (f"; drawn there: {', '.join(source.sets())}" if source.sets() else ""))


def _pages_section(section: dict, found: list[Source], where: str, allow_drawn: bool) -> list[Grid]:
    set_, globs = section.get("set", "totality"), section["pages"]
    cells, backends = section.get("cells"), _backends(section)
    if section.get(QUIET):
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
    return [Grid(section["title"], [Figure(None, "", p.name, p.resolve(), p.stem) for p in files], section.get("columns"))]


def resolve(recipe: dict, given: list[str], *, path: Path | None = None, name: str = "", out: Path | None = None,
            allow_drawn: bool = False) -> Plan:
    """A recipe (or the default's) and its sources as a Plan. `given`: the command line's sources, which replace
    [report].from; a section's own from stays. `allow_drawn`: what is not on disk is drawn for the report (P4),
    else refused naming the command that makes it."""
    where = str(path) if path else "the default report"
    head = recipe.get("report", {})
    named = given or head.get("from", [])
    if not named and not any(s.get("from") for s in recipe.get("section", [])):
        raise HepError("a report needs a source", where=where,
                       hint="heimdall report <recipe> <P>/<run>/<cfg>, or from = [\"<P>/<run>/<cfg>\"] in [report]")
    every = sources(named, f"{where}: [report].from") if named else []
    if path is None and not recipe.get("section"):
        recipe = default_recipe(every)
    if not name:
        name = _common(every) if every else "report"
    sections: list[Section] = []
    used: list[Source] = list(every)
    for number, spec in enumerate(recipe.get("section", []), 1):
        at = f"{where}: section {number} ({spec.get('title', '')})"
        found = sources(spec["from"], f"{at}.from") if spec.get("from") else every
        used += [s for s in found if s not in used]
        section = Section(spec["title"], spec.get("note", ""), plot=dict(spec.get("plot", {})))
        set_ = spec.get("set", "totality")
        if "pages" in spec:
            section.grids = _pages_section(spec, found, at, allow_drawn)
        elif "compare" in spec:
            section.grids = _compare_section(spec, found, at)
        elif "files" in spec:
            section.grids = _files_section(spec, path.parent if path else Path.cwd(), at)
        elif "stats" in spec:
            for source in (s for s in found if not spec.get(QUIET) or s.numbers(set_)):
                csv = source.numbers(set_)
                if csv is None and not allow_drawn:
                    raise HepError(f"{source.address} has no statistics for {set_}", where=f"{at}.stats",
                                   hint=f"heimdall stats {source.address} --sets {set_} measures them")
                section.parts.append(Part(source, set_, list(spec["stats"]), csv))
        else:
            for source in found:
                csv = source.numbers(set_)
                if csv is None and not allow_drawn:
                    raise HepError(f"{source.address} has no statistics for {set_}", where=f"{at}.bars",
                                   hint=f"heimdall stats {source.address} --sets {set_} measures them")
                section.bars.append(Bars(source, set_, list(spec["bars"]), csv))
        sections.append(section)
    title = head.get("title") or (every[0].address if len(every) == 1 else name)
    return Plan(name, title, head.get("subtitle", ""), used, sections, out or reports_root() / name, path)


def _common(found: list[Source]) -> str:
    """The sources' common address: one source's own, else what their addresses share (eic/zeus_validation)."""
    parts = [s.address.split("/") for s in found]
    shared = []
    for column in zip(*parts):
        if len(set(column)) != 1:
            break
        shared.append(column[0])
    return "/".join(shared) or "report"


def planned(first: str | None, rest: list[str], out: Path | None = None, allow_drawn: bool = False) -> Plan:
    """`heimdall report [RECIPE] [SOURCE…]`: the first argument is a recipe when it names one, else a source."""
    path = recipe_of(first) if first else None
    given = rest if path else ([first] if first else []) + rest
    if path is None:
        return resolve({}, given, out=out, allow_drawn=allow_drawn)
    name = str(path.relative_to(configs_root().resolve()).with_suffix("")) if path.is_relative_to(configs_root().resolve()) \
        else path.stem
    if "/" in name and (results_root() / name).is_dir():
        raise HepError(f"{name} names both a report and a run's results", where=str(path),
                       hint="rename the recipe: its report would land where the run's would")
    return resolve(load_recipe(path), given, path=path, name=name, out=out, allow_drawn=allow_drawn)


def listing(plan: Plan) -> list[str]:
    """`heimdall report … --list`: its sources, then each section and what it shows, nothing written."""
    lines = [f"report {plan.name} → {plan.out}: {len(plan.sources)} source(s), {len(plan.sections)} section(s), "
             f"about {plan.pages()} page(s) of figures"]
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
    return lines


def starter(name: str, source: Source) -> str:
    """`--init`: the default report's sections as a recipe, each set's cells and pages listed, and the sets
    drawn that its document does not draw by default as sections commented out (V207)."""
    lines = [f"# configs/{name}.toml: a report, `heimdall report {name}` (docs/03_Plots.md §11; its keys 04 §15).",
             "# The sources on the command line replace `from`; each [[section]] shows one of pages, compare, stats,",
             "# bars or files.", "", "[report]", f'title = "{source.doc.name} · {source.name}"',
             '# subtitle = "for the group, <date>"', f'from  = ["{source.address}"]', ""]
    sections = default_recipe([source])["section"]
    shown = [s["set"] for s in sections if "pages" in s]
    for section in sections:
        if "stats" in section:
            lines += ["[[section]]", 'title = "Standings"', f'set   = "{section["set"]}"',
                      "stats = [" + ", ".join(f'"{k}"' for k in HEADLINE) + "]", ""]
    for set_ in [*shown, *(s for s in source.sets() if s not in shown)]:
        pages = source.pages(set_, BACKENDS)
        cells = sorted({_cell(n) for n in pages}, key=natural)
        objects = sorted({n.rsplit("/", 1)[-1] for n in pages}, key=natural)
        mark = "" if set_ in shown else "# "
        lines += [f"# {set_}: {len(pages)} page(s)" + (f" in {len(cells)} cell(s): {', '.join(cells[:8])}"
                                                        f"{' …' if len(cells) > 8 else ''}" if any(cells) else ""),
                  f"#   {', '.join(objects[:12])}{' …' if len(objects) > 12 else ''}",
                  *(mark + line for line in ("[[section]]", f'title = "{set_}"', f'set   = "{set_}"', 'pages = ["*"]')), ""]
    return "\n".join(lines)
