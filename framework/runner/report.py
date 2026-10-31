"""`heimdall report` (I-108, .plans/report/): a quick, informal report of one or more runs' pages and numbers,
for colleagues or a supervisor, made only when asked (rank 4).

* **Sources** are result folders holding a plot document (plot.toml): a configuration's, or a run's runs-together
  folder (V169). They are named `<P>/<run>/<cfg>`, `<P>/<run>` (each of its configurations, then its own when it
  is drawn), a path, or a glob of them under results/.
* **A recipe** is a `[report]` table and its `[[report.section]]`s (framework/schema/report.toml), each section one
  kind of item: pages, compare, stats, bars, files or tools (what each tool was given, read from the records). It is a file of its own (`configs/<P>/<name>.toml`, `[report]`
  alone), a run TOML's `[report]` (what its folders' reports show, its `template` laid under it), or the
  `report.toml` a run writes beside each folder's plot.toml from that (V209). With no sections, the default: the
  statistics' headline, then each set the sources' documents draw, then what their tools were given (V210).
* **Where:** reports/ mirrors results/: a folder's report in reports/<P>/<run>/<cfg>/, a run's in reports/<P>/<run>/,
  several runs' where their addresses meet; `-o` or the recipe's `output` says otherwise.
* `resolve` turns a recipe and its sources into a `Plan`: its sections' grids of figures, each copied from its
  source or drawn for the report, and its statistics parts. Nothing is written until the build.
* **Drawn for itself** (V211): what a source has not drawn or measured (or drew as PNG alone), and every section
  with `plot = {…}`, is drawn by plot.draw and plot.measure from the source's plot document into the report's
  cache, .cache/<P>/reports/<its place>/.drawn/; the source's results/ and records/ are only read.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import subprocess
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config as configmod
from . import plot as plotting
from . import plotdoc, plugins, record, statstable, viewer
from .config import STATISTICS
from .errors import HeimdallError, did_you_mean
from .paths import apps_dir, cache_root, config_file, configs_root, heimdall_root, reports_root, results_root, work_root
from .sweep import TOTALITY, label_of, named_sets, tag_of, totality
from .tools import RunFolders

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
                raise HeimdallError(f"{self.address}: no event count", hint='its points say none; label = "folder" labels it by its folder')
            return plotdoc.count_tag(n)
        return self.name

    def complete(self) -> list:
        return [m for m in self.members if m.recorded is not None and m.recorded == m.identity]

    def sets(self) -> list[str]:
        """The sets drawn here: plots/<set>/ with a backend's folder in it."""
        plots = self.folder / "plots"
        return sorted((d.name for d in plots.iterdir() if d.is_dir() and any((d / b).is_dir() for b in BACKENDS)),
                      key=natural) if plots.is_dir() else []

    def pages(self, set_: str, backends: tuple[str, ...], root: Path | None = None) -> dict[str, Path]:
        """A set's drawn pages, name → file: per page, the first of `backends` that drew it, its PDF (else its
        PNG). Sheets and indexes are not pages. `root`: a drawing's results/ instead of its folder (P6)."""
        out: dict[str, Path] = {}
        for backend in backends:
            where = (root or self.folder) / "plots" / set_ / backend
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

    def numbers(self, set_: str, root: Path | None = None) -> Path | None:
        """A set's statistics.csv, when measured (`root`: a drawing's results/)."""
        path = (root or self.folder) / "statistics" / set_ / "statistics.csv"
        return path if path.is_file() else None

    def drawable(self, set_: str, look: dict) -> bool:
        """Whether its document can draw or measure a set for the report (P6): a [plot] (its own, the section's
        plot keys over it), the set the totality or one of its sets, and a complete point with its YODA."""
        plot = looked(self.doc.plot or {}, look)
        return bool(plot) and set_ in {TOTALITY, *named_sets(plot.get("sets"))} and \
            any(m.yoda is not None and m.yoda.is_file() for m in self.complete())

    def facts(self) -> dict:
        """Where it came from (N2): its config and configuration, its tag (V223), Heimdall's revision and when its
        document was written, its points (complete or not), its events, what it is compared against, and whether its points
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
                "tag": str(given.get("tag", "") or ""),
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
        raise HeimdallError(f"no plot document in {path}", where=where, hint="a source is a result folder holding a plot.toml")
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
    raise HeimdallError(f"no result folder {address} under {root}", where=where,
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
        raise HeimdallError("cannot read the recipe", where=str(path)) from None
    except tomllib.TOMLDecodeError as error:
        raise HeimdallError(f"cannot read the recipe: {error}", where=str(path)) from None


def _is_recipe(path: Path) -> bool:
    try:
        return set(_read(path)) == {"report"}
    except HeimdallError:
        return False


def recipe_of(name: str) -> Path | None:
    """The recipe a command's first argument names, always a .toml file, named as a run config is: <P>/<name>.toml
    under configs/, ./… the work dir's, /… a path. A recipe of its own, a run TOML or a folder's report.toml. None:
    the argument is a source."""
    if not name.endswith(".toml"):
        return None
    try:
        return config_file(name).resolve()
    except HeimdallError:
        raise HeimdallError(f"no recipe {name}", where=str(configs_root()),
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
        raise HeimdallError(f"a recipe has [report] alone, not [{others[0]}]" if others else "a recipe has a [report] table",
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


def _sections(sets: list[str], measured: list[str], tools: list[str] | None) -> list[dict]:
    first = [] if tools == [] else [{"title": "Tools", "tools": list(tools or ["*"]), "optional": True}]
    head = [{"title": "Standings", "set": measured[0], "stats": list(HEADLINE), "optional": True}] if measured else []
    return first + head + [{"title": f"Pages: {s}", "set": s, "pages": ["*"], "optional": True} for s in sets]


def default_sections(plot: dict, stats: dict, tools: list[str] | None = None) -> list[dict]:
    """The default report's sections for a plot document's [plot] and [stats] (A1, A8, I-111): what its tools were
    given (`tools`: [report].tools; None every tool given a card or options, [] none), then Standings, the
    statistics' headline, on the first set it measures ([stats].sets, else the sets drawn), then the pages of each
    set it draws; every one optional, so a set drawn nowhere is left out."""
    sets = _drawn_sets(plot)
    return _sections(sets, list((stats or {}).get("sets") or sets), tools)


def default_recipe(found: list[Source], tools: list[str] | None = None) -> dict:
    """No recipe (N1, A1): the default sections over these sources, their sets together in order (a document with
    no [plot]: the sets drawn in its folder)."""
    sets: list[str] = []
    measured: list[str] = []
    for source in found:
        own = _drawn_sets(source.doc.plot or {}) or source.sets()
        sets += [s for s in own if s not in sets]
        measured += [s for s in ((source.doc.stats or {}).get("sets") or own) if s not in measured]
    return {"section": _sections(sets, measured, tools)}


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
        table["section"] = default_sections(data.get("plot", {}), data.get("stats", {}), table.get("tools"))
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


# ── what the tools were given (A7) ─────────────────────────────────────────────────────────────

#: A card's comment lines: kept in its baseline where every point has them alike, never among what varied.
COMMENTS = ("#", "!", "//", "%")
#: A context.toml table's keys that are not a tool's options: its card (or a module's config) and where it came from.
NOT_OPTIONS = ("tool", "card", "card_parts", "config")
_ASSIGNED = re.compile(r"([A-Za-z_][\w:.\-/\[\]]*)\s*=\s*(\S.*)")
_MAPPED = re.compile(r"([A-Za-z_][\w.\-]*):\s+(\S.*)")


def _is_comment(line: str) -> bool:
    text = line.strip()
    return not text or text.startswith(COMMENTS)


def key_value(line: str) -> tuple[str, str] | None:
    """A card line as (key, value) when it is `key = value` (Pythia, Herwig's `set` aside) or a top-level YAML
    `key: value`; else None (a nested line, a command, a block's head)."""
    if line[:1].isspace():
        return None
    found = _ASSIGNED.fullmatch(line.rstrip()) or _MAPPED.fullmatch(line.rstrip())
    return (found[1], found[2].strip()) if found else None


def split(cards: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """Cards' lines (A7): the lines every card has, as many times as each has it, in the first card's order (its
    baseline), and each card's other lines in its own order."""
    common = Counter(cards[0])
    for lines in cards[1:]:
        common &= Counter(lines)
    left, baseline = Counter(common), []
    for line in cards[0]:
        if left[line] > 0:
            left[line] -= 1
            baseline.append(line)
    others = []
    for lines in cards:
        left, own = Counter(common), []
        for line in lines:
            if left[line] > 0:
                left[line] -= 1
            else:
                own.append(line)
        others.append(own)
    return baseline, others


def plain(text: str) -> str:
    """A LaTeX label as plain text, for a table's row: `$e^{+}p$` → `e+p`, `PDF4LHC21\\_40` → `PDF4LHC21_40`."""
    text = re.sub(r"\\([_%&#$])", r"\1", text)
    text = re.sub(r"\\(mathrm|text|textrm|mathit)\b", "", text)
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    return re.sub(r"[{}$^]", "", text).replace("~", " ").strip()


@dataclass
class Given:
    """What one tool was given across a source's reported points (A7), from their records: its card's baseline
    (the lines every point had alike, comments too), its options alike, and each point's other lines (comments
    left out, `hide` applied)."""
    source: Source
    tag: str
    ext: str                                  # its card's own extension (".cmnd"); "" with no card
    baseline: list[str]
    options: dict
    varied: list[tuple[str, str, list[str]]]  # (point, its label, its other lines), every point in order
    notes: list[str] = field(default_factory=list)

    @property
    def caption(self) -> str:
        return f"{self.source.address} · {self.tag}"

    def table(self) -> tuple[list[str], list[dict[str, str]]] | None:
        """Its varied lines as a table, when every one is `key = value` (or `key: value`) and no key comes twice
        in a point: its keys in first-seen order, and a row per point (key → value). None: a list per point."""
        keys: list[str] = []
        rows = []
        for _, _, lines in self.varied:
            row: dict[str, str] = {}
            for line in lines:
                found = key_value(line)
                if found is None or found[0] in row:
                    return None
                row[found[0]] = found[1]
                keys += [found[0]] if found[0] not in keys else []
            rows.append(row)
        return keys, rows

    def points(self) -> int:
        return len(self.varied)

    def summary(self) -> str:
        """`19 point(s), 24 card line(s) alike, 2 varied key(s)`, as --list says it."""
        table = self.table()
        varied = any(lines for _, _, lines in self.varied)
        return ", ".join(part for part in (
            f"{self.points()} point(s)", f"{len(self.baseline)} card line(s) alike" if self.ext else "",
            f"{len(self.options)} option(s) alike" if self.options else "",
            ("" if not varied else f"{len(table[0])} varied key(s)" if table is not None else "a list of what varied"),
            "nothing varied" if not varied else "") if part)


def _point_tools(folder: Path) -> dict[str, dict] | None:
    """A point's tools as its record has them: context.toml's [tools.<tag>], each its card (cards/, or a
    module's config/: by name, wherever the record now is) and its options; a record without one, cards/<tag>.*
    (its .point. and .json files left out). None: no record of the point."""
    if not folder.is_dir():
        return None
    context = folder / "context.toml"
    if context.is_file():
        try:
            tables = tomllib.loads(context.read_text(encoding="utf-8")).get("tools", {})
        except (OSError, tomllib.TOMLDecodeError):
            tables = None
        if isinstance(tables, dict):
            out = {}
            for tag, table in tables.items():
                named = table.get("card") or table.get("config")
                card = folder / ("cards" if table.get("card") else "config") / Path(named).name if named else None
                out[tag] = {"card": card, "options": {k: v for k, v in table.items() if k not in NOT_OPTIONS}}
            return out
    cards = folder / "cards"
    out = {}
    for path in sorted(cards.iterdir()) if cards.is_dir() else ():
        if path.is_file() and ".point." not in path.name and path.suffix != ".json":
            out.setdefault(path.name.split(".", 1)[0], {"card": path, "options": {}})
    return out


def _label(source: Source, member) -> str:
    """A point's label as its curve's: its varied quantities' labels, as plain text; else its name."""
    names = [q for entry in source.doc.configuration.sweeps for q in (entry if isinstance(entry, list) else [entry])]
    parts = [plain(label_of(source.doc.quantities[q], member.values[q])) for q in names
             if q in source.doc.quantities and q in member.values]
    return ", ".join(p for p in parts if p) or member.point.name


def _hidden(line: str, hide: list[str]) -> bool:
    found = key_value(line)
    return any(fnmatch.fnmatchcase(found[0] if found else line.strip(), glob) for glob in hide)


def configured(source: Source, globs: list[str], hide: list[str], where: str, optional: bool = False) -> list[Given]:
    """What the tools `globs` name were given in a source's complete points (A7), from its records (never today's
    configs/): a tag by name even when it was given nothing, a glob only the tools given a card or options, each
    once, in natural order a glob. Points with no record are said; with none at all, refused (optional: none)."""
    logs = plotdoc._folders(source.folder, source.project).logs
    points = [(m, _point_tools(logs / m.point.name)) for m in source.complete()]
    recorded = [(m, tools) for m, tools in points if tools is not None]
    missing = [m.point.name for m, tools in points if tools is None]
    if not recorded:
        if optional:
            return []
        raise HeimdallError(f"{source.address}: no record of its points' tools in {logs}", where=f"{where}.tools",
                       hint="a point's tools are read from its records/ (cards/, context.toml); results copied alone have none")
    tags = sorted(dict.fromkeys(t for _, tools in recorded for t in tools), key=natural)
    chosen: list[str] = []
    for glob in globs:
        if GLOB.search(glob):
            chosen += [t for t in tags if fnmatch.fnmatchcase(t, glob) and t not in chosen
                       and any(tools[t]["card"] or tools[t]["options"] for _, tools in recorded if t in tools)]
        elif glob in tags:
            chosen += [glob] if glob not in chosen else []
        elif not optional:
            raise HeimdallError(f"tools: {source.address}'s points have no tool {glob!r}", where=f"{where}.tools",
                           hint=did_you_mean(glob, tags) or f"their tools: {', '.join(tags)}")
    out = []
    for tag in chosen:
        notes = [f"{len(missing)} complete point(s) with no record, not shown: {', '.join(missing[:6])}"
                 + (" …" if len(missing) > 6 else "")] if missing else []
        mine = [(m, tools[tag]) for m, tools in recorded if tag in tools]
        cards, options, kept = [], [], []
        for member, tool in mine:
            lines = None
            if tool["card"] is not None:
                try:
                    lines = [line.rstrip() for line in tool["card"].read_text(encoding="utf-8").splitlines()]
                except (OSError, UnicodeDecodeError):
                    notes.append(f"{member.point.name}: its card {tool['card'].name} is not a text file there")
            if tool["card"] is not None and lines is None:
                continue
            kept.append(member)
            cards.append(lines or [])
            options.append(tool["options"])
        if not kept:
            out.append(Given(source, tag, "", [], {}, [], notes))
            continue
        baseline, others = split(cards)
        alike = {k: v for k, v in options[0].items() if all(k in o and o[k] == v for o in options[1:])}
        varied = []
        for member, own, opts in zip(kept, others, options):
            lines = [line for line in own if not _is_comment(line)]
            lines += [f"{k} = {_value(v)}" for k, v in opts.items() if k not in alike]
            varied.append((member.point.name, _label(source, member), [line for line in lines if not _hidden(line, hide)]))
        card = next((tool["card"] for _, tool in mine if tool["card"] is not None), None)
        if card is None and not alike and not any(lines for _, _, lines in varied):
            notes.append("given no card and no options")
        out.append(Given(source, tag, card.suffix if card is not None else "", baseline, alike, varied, notes))
    return out


# ── the plan ───────────────────────────────────────────────────────────────────────────────────

@dataclass
class Figure:
    """One drawn page (or a file of the recipe's) in a grid: copied from where it is, or drawn for the report."""
    source: Source | None
    set: str
    page: str                    # its name in the set ([<cell>/]<object>), or the file's
    file: Path | None            # what is shown; None: to be drawn for the report (P6), its pages' globs as page
    label: str = ""              # a side-by-side panel's
    why: str = ""                # why it is drawn for the report


@dataclass
class SetHead:
    """A set's sub-header (I-110 R3), once over a source's grids of it (once a set, side by side): what its pages
    and curves are along, and the quantities its configuration holds fixed, each as (what, its lines); the labels
    as the run TOML wrote them (LaTeX, `$…$` math)."""
    set: str
    address: str
    facts: list[tuple[str, list[str]]]


@dataclass
class Grid:
    caption: str
    figures: list[Figure]
    columns: int | None = None
    head: SetHead | None = None   # the set's sub-header, over the first grid of a source's set
    cell: str = ""                # its page cell as labels (Pythia 8.318), its caption once the head says the rest


@dataclass
class Part:
    """A source's statistics, some of its summary's sections, from its set's statistics.csv."""
    source: Source
    set: str
    keys: list[str]
    csv: Path | None             # None: to be measured for the report (P6)
    look: bool = False           # measured with its section's plot keys


@dataclass
class Bars:
    """Bar graphs of a source's pages' numbers, drawn for the report from statistics.csv."""
    source: Source
    set: str
    pages: list[str]
    csv: Path | None
    look: bool = False


@dataclass
class Section:
    title: str
    note: str = ""
    grids: list[Grid] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    bars: list[Bars] = field(default_factory=list)
    given: list[Given] = field(default_factory=list)     # what its tools were given (A7)
    plot: dict = field(default_factory=dict)
    spec: dict = field(default_factory=dict)             # its recipe's table, its sources and where it is written:
    found: list = field(default_factory=list)            # resolved again once what it waits for is drawn (P6)
    at: str = ""

    @property
    def context(self) -> bool:
        """Whether it says what was run (a tools section), which a report shows before its results (I-111)."""
        return "tools" in self.spec

    def waiting(self) -> bool:
        """Whether it shows something not drawn yet: a figure with no file, numbers with no CSV."""
        return any(f.file is None for g in self.grids for f in g.figures) or any(p.csv is None for p in [*self.parts, *self.bars])


@dataclass
class Drawing:
    """A source's document drawn or measured for the report (P6: N3, N8), never into results/: its [plot] with a
    section's plot keys over it (`look`), drawing only the sets the report needs, into folders of its own under
    .cache/<P>/reports/<the report's place>/.drawn/ (results/, records/ for its logs, work/)."""
    source: Source
    look: dict                                                  # a section's plot keys; {}: the document's own
    sets: dict[str, str] = field(default_factory=dict)          # set → why its pages are drawn
    measured: dict[str, str] = field(default_factory=dict)      # set → why its numbers are measured
    backends: list[str] = field(default_factory=list)           # the ones its sections name, beside its own
    folder: Path | None = None                                  # where, once the build has drawn it
    failed: int = 0

    def want(self, kind: str, set_: str, why: str, backends=()) -> "Drawing":
        getattr(self, kind).setdefault(set_, why)
        self.backends += [b for b in backends if b not in self.backends]
        return self

    @property
    def results(self) -> Path | None:
        return self.folder / "results" if self.folder else None

    @property
    def logs(self) -> Path | None:
        return self.folder / "records" / "logs" / "plot" if self.folder else None

    def describe(self) -> str:
        """What it draws and why, for --list and the front page."""
        said = [f"{kind} of " + ", ".join(f"{s} ({why})" for s, why in table.items())
                for kind, table in (("pages", self.sets), ("numbers", self.measured)) if table]
        look = ", ".join(f"{k} = {_value(v)}" for k, v in self.look.items())
        return self.source.address + (f" with {look} over its [plot]" if look else "") + ": " + "; ".join(said)


def _drawing(drawings: list[Drawing], source: Source, look: dict) -> Drawing:
    """The drawing of this source with this look, one for every section that asks for it."""
    key = json.dumps(look, sort_keys=True)
    for drawing in drawings:
        if drawing.source.folder == source.folder and json.dumps(drawing.look, sort_keys=True) == key:
            return drawing
    drawings.append(Drawing(source, dict(look)))
    return drawings[-1]


def looked(plot: dict, look: dict) -> dict:
    """A document's [plot] with a section's plot keys over it (N8): its sets and figures added to the document's, its
    style laid over the document's, any other key replacing the document's."""
    if not look:
        return dict(plot)
    out = {**plot, **{k: v for k, v in look.items() if k not in ("sets", "figures", "style")}}
    if "sets" in look:
        out["sets"] = {**named_sets(plot.get("sets")), **named_sets(look["sets"])}
    if "figures" in look:
        out["figures"] = {**plot.get("figures", {}), **look["figures"]}
    if "style" in look:
        out["style"] = plotting.merge_style(plot.get("style") or {}, look["style"])
    return out


@dataclass(frozen=True)
class Look:
    """A report's look (I-110 R2), from [report]'s look keys: the body's font and size, the accent (section
    numbers, kickers, ranking bars, code keys), whether the front page holds the contents, a grid's columns."""
    font: str = "sans"           # "sans": TeX Gyre Heros throughout; "serif": TeX Gyre Termes for the body
    size: float = 9.5            # the body's pt (its line 1.42 times it)
    accent: str = "#2a78d6"
    contents: bool = True
    columns: int = 2


def look_of(recipe: dict) -> Look:
    """[report]'s look keys over the defaults."""
    given = {k: recipe[k] for k in ("font", "size", "accent", "contents", "columns") if k in recipe}
    return dataclasses.replace(Look(), **given)


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
    drawings: list[Drawing] = field(default_factory=list)
    look: Look = field(default_factory=Look)
    method: bool = True          # How the numbers are made, when it shows statistics (I-111)
    context: str = "first"       # where what was run and how the numbers are made go: before the results, or "last"

    def shows_numbers(self) -> bool:
        return any(s.parts or s.bars for s in self.sections)

    def drawn(self) -> list:
        """What is still to be drawn or measured for the report: figures with no file, parts and bars with no CSV."""
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


#: A filter's values named one by one up to this many; more are counted.
NAMED = 8


def _varied(doc) -> list[str]:
    return [q for entry in doc.configuration.sweeps for q in (entry if isinstance(entry, list) else [entry])]


def _values_of(doc, name: str, value) -> str:
    """A set filter's value for one quantity, as its labels: "all" (each, or how many), a tag, "!tag", a list of
    them (a styled value by its tag); a glob or a number as written."""
    quantity = doc.quantities.get(name)
    if quantity is None:
        return str(value)
    tags = [tag_of(quantity, i) for i in range(len(quantity.values))]

    def one(item) -> str:
        if isinstance(item, dict):
            item = item.get("tag", item.get("value", ""))
        text = str(item)
        if text in tags:
            return label_of(quantity, tags.index(text))
        if text.startswith("!") and text[1:] in tags:
            return f"all but {label_of(quantity, tags.index(text[1:]))}"
        return text
    if value == "all":
        shown = [label_of(quantity, i) for i in range(len(tags)) if i + 1 not in quantity.exclude]
        return ", ".join(shown) if len(shown) <= NAMED else f"all {len(shown)}"
    if isinstance(value, list):
        shown = [one(v) for v in value]
        return ", ".join(shown) if len(shown) <= NAMED else f"{len(shown)} of {len(tags)}"
    return one(value)


def set_head(source: Source, set_: str, look: dict | None = None) -> SetHead:
    """A source's set as its sub-header says it (I-110 R3): its table in the plot document ([plot].sets, a
    section's plot keys over them; the totality's own when it names none): Pages (its page axes and their values,
    as labels; none: a page per object), Curves (a line a curves filter), Objects, and Fixed (each quantity the
    configuration does not vary, its value's label)."""
    doc = source.doc
    table = named_sets(looked(doc.plot or {}, look or {}).get("sets")).get(set_)
    if table is None and set_ == TOTALITY:
        table = totality(doc.configuration, source.members)
    table = table if isinstance(table, dict) else {"points": table} if table else {}

    def said(flt: dict) -> str:
        return " · ".join(f"{q}: {_values_of(doc, q, v)}" for q, v in flt.items())
    facts: list[tuple[str, list[str]]] = []
    if "points" in table and not ("pages" in table or "curves" in table):
        facts.append(("Points", [", ".join(str(p) for p in table["points"])]))
    else:
        pages, curves = table.get("pages"), table.get("curves")
        filters = curves if isinstance(curves, list) else [curves] if isinstance(curves, dict) and curves else []
        if pages is None and filters:                    # the varied quantities the curves leave: a page each
            pages = {q: "all" for q in _varied(doc) if not any(q in f for f in filters)}
        facts.append(("Pages", [said(pages) if isinstance(pages, dict) and pages else "a page per object, every curve on it"]))
        if filters:
            facts.append(("Curves", [said(f) for f in filters]))
    if table.get("objects"):
        facts.append(("Objects", [", ".join(str(o) for o in table["objects"])]))
    varied = set(_varied(doc))
    fixed = []
    for name, mark in (doc.configuration.static or {}).items():
        quantity = doc.quantities.get(name)
        if name in varied or quantity is None or not str(mark).startswith("#"):
            continue
        index = int(str(mark)[1:]) - 1
        if 0 <= index < len(quantity.values):
            fixed.append(f"{name}: {label_of(quantity, index)}")
    if fixed:
        facts.append(("Fixed", [" · ".join(fixed)]))
    return SetHead(set_, source.address, facts)


def cell_label(doc, cell: str) -> str:
    """A page cell (its page axes' tags joined by _: `py8_27x920`) as their labels (`Pythia 8.318, 27.5x920 GeV`):
    the longest tag that starts it first; a cell no tag reads is itself."""
    known: dict[str, str] = {}
    for quantity in doc.quantities.values():
        for index in range(len(quantity.values)):
            known.setdefault(tag_of(quantity, index), label_of(quantity, index))
    out, rest = [], cell
    while rest:
        for tag in sorted(known, key=len, reverse=True):
            if rest == tag or rest.startswith(tag + "_"):
                out.append(known[tag])
                rest = rest[len(tag) + 1:]
                break
        else:
            return cell
    return ", ".join(out)


def _refuse_missing(source: Source, set_: str, where: str, measured: bool = False) -> None:
    """A source with a set neither on disk nor for its document to draw (P6): refused, naming what it has."""
    kind, sets = ("measured", "statistics") if measured else ("drawn", "plots")
    has = sorted((d.name for d in (source.folder / sets).iterdir() if d.is_dir()), key=natural) if (source.folder / sets).is_dir() else []
    own = [TOTALITY, *(s for s in named_sets((source.doc.plot or {}).get("sets")) if s != TOTALITY)] if source.doc.plot else []
    raise HeimdallError(f"{source.address} has no set {set_} {kind}" + (", and no complete point to draw it from" if set_ in own else
                                                                   f", and its plot document no set {set_} to draw"), where=where,
                   hint="; ".join(part for part in (f"{kind} there: {', '.join(has)}" if has else "",
                                                     f"its sets: {', '.join(own)}" if own else "",
                                                     "optional = true passes it over") if part))


def _from_drawing(source: Source, set_: str, look: dict, why: str, kind: str, section: dict, where: str,
                  drawings: list[Drawing]) -> tuple[Drawing | None, bool]:
    """A source's set drawn (or measured) for the report: (its drawing, True), or (None, False) when its document
    cannot draw it and the section is optional (refused when it is not)."""
    if not source.drawable(set_, look):
        if section.get("optional"):
            return None, False
        _refuse_missing(source, set_, where, kind == "measured")
    named = section.get("backend")
    return _drawing(drawings, source, look).want(kind, set_, why, [named] if isinstance(named, str) else named or ()), True


def _pages_section(section: dict, found: list[Source], where: str, drawings: list[Drawing]) -> list[Grid]:
    """A pages section's grids. A source's pages are copied from its plots/<set>/, or drawn for the report (P6)
    when it has not drawn the set, drew it as PNG alone, or the section has plot keys: until the build draws them
    a grid waits, a figure with no file each."""
    set_, globs = section.get("set", "totality"), section["pages"]
    cells, backends, look = section.get("cells"), _backends(section), dict(section.get("plot") or {})
    shown: list[Source] = []
    chosen: dict[str, dict[str, Path]] = {}
    waiting: dict[str, str] = {}
    for source in found:
        drawn = {} if look else source.pages(set_, backends)
        why = ("its section's plot keys" if look else "not drawn there" if not drawn else
               "drawn there as PNG alone" if any(p.suffix.lower() != ".pdf" for p in drawn.values()) else "")
        root = None
        if why:
            drawing, ok = _from_drawing(source, set_, look, why, "sets", section, where, drawings) \
                if look or not drawn or source.drawable(set_, look) else (None, True)
            if not ok:
                continue
            if drawing is not None and drawing.folder is None:
                waiting[source.address] = why
                shown.append(source)
                continue
            if drawing is not None:
                root = drawing.results
                drawn = source.pages(set_, backends, root)
                if not drawn:
                    if section.get("optional"):
                        continue
                    raise HeimdallError(f"{source.address}: {set_}, drawn for the report, has no page", where=where,
                                   hint=f"its points give it none; the drawing's log: {drawing.logs}")
        names = [n for n in drawn if any(_matches(n, g) for g in globs)
                 and (cells is None or any(fnmatch.fnmatchcase(_cell(n), c) for c in cells))]
        if not names:
            raise HeimdallError(f"pages: {', '.join(globs)} names no page drawn in "
                           f"{f'{root}/plots' if root else f'{source.address}/plots'}/{set_}/", where=f"{where}.pages",
                           hint=f"its pages: {', '.join(list(drawn)[:6])}{' …' if len(drawn) > 6 else ''}" if drawn else None)
        chosen[source.address] = {n: drawn[n] for n in names}
        shown.append(source)
    found = shown
    grids: list[Grid] = []
    if section.get("layout", "pages") == "sources":
        how = section.get("label", "folder")
        named = labels(found, how)
        twice = [label for label in named.values() if list(named.values()).count(label) > 1]
        if twice:
            raise HeimdallError(f"two sources are labelled {twice[0]}", where=f"{where}.label",
                           hint='label = "folder" labels them by their folders')
        if waiting:                                      # its pages are known once drawn
            return [Grid(f"{set_} · {', '.join(globs)}", [Figure(s, set_, ", ".join(globs), None if s.address in waiting else
                                                                 next(iter(chosen[s.address].values())), named[s.address],
                                                                 waiting.get(s.address, "")) for s in found])]
        names = sorted({n for pages in chosen.values() for n in pages}, key=natural)
        head = dataclasses.replace(set_head(found[0], set_, look), address=", ".join(s.address for s in found)) if found else None
        for name in names:
            absent = [s.address for s in found if name not in chosen[s.address]]
            if absent:
                raise HeimdallError(f"{absent[0]} has no page {name} in plots/{set_}/", where=f"{where}.pages",
                               hint="draw it there, or leave that source out of the section's from")
            cell = cell_label(found[0].doc, _cell(name))
            grids.append(Grid(f"{set_} · {name}", [Figure(s, set_, name, chosen[s.address][name], named[s.address]) for s in found],
                              section.get("columns") or (3 if len(found) >= 3 else None), head if not grids else None,
                              ", ".join(part for part in (cell, name.rsplit("/", 1)[-1]) if part)))
        return grids
    for source in found:
        if source.address in waiting:
            grids.append(Grid(f"{source.address} · {set_}", [Figure(source, set_, ", ".join(globs), None, "", waiting[source.address])],
                              section.get("columns")))
            continue
        by_cell: dict[str, list[str]] = {}
        for name in chosen[source.address]:
            by_cell.setdefault(_cell(name), []).append(name)
        head = set_head(source, set_, look)
        for k, (cell, names) in enumerate(by_cell.items()):
            caption = " · ".join(part for part in (source.address, set_, cell) if part)
            grids.append(Grid(caption, [Figure(source, set_, n, chosen[source.address][n], n.rsplit("/", 1)[-1]) for n in names],
                              section.get("columns"), head if k == 0 else None, cell_label(source.doc, cell) if cell else ""))
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
                raise HeimdallError(f"compare: no page of {name} drawn in {_address(run)}/compare/", where=f"{where}.compare",
                               hint="a compare figure is drawn by its configurations' plot stage (03 §7.5)")
    return grids


def _files_section(section: dict, base: Path, where: str) -> list[Grid]:
    files: list[Path] = []
    for glob in section["files"]:
        found = sorted((p for p in base.glob(glob) if p.suffix.lower() in (".pdf", ".png")), key=lambda p: natural(p.name))
        if not found:
            raise HeimdallError(f"files: '{glob}' names no PDF or PNG file in {base}", where=f"{where}.files")
        files += [p for p in found if p not in files]
    return [Grid(section["title"], [Figure(None, "", p.stem, p.resolve(), p.stem) for p in files], section.get("columns"))]


def _numbers(spec: dict, found: list[Source], set_: str, where: str, drawings: list[Drawing]) -> list[tuple[Source, Path | None]]:
    """A stats or bars section's sources and their set's statistics.csv: the source's, else measured for the report
    (P6; None until the build measures it), as with the section's plot keys always; optional: a source whose
    document cannot measure it passed over."""
    look = dict(spec.get("plot") or {})
    out = []
    for source in found:
        csv = None if look else source.numbers(set_)
        if csv is None:
            drawing, ok = _from_drawing(source, set_, look, "its section's plot keys" if look else "not measured there",
                                        "measured", spec, where, drawings)
            if not ok:
                continue
            if drawing.folder is not None:
                csv = source.numbers(set_, drawing.results)
                if csv is None:
                    if spec.get("optional"):
                        continue
                    raise HeimdallError(f"{source.address}: {set_}, measured for the report, has no numbers", where=where,
                                   hint=f"no page of it has numbers; the drawing's log: {drawing.logs}")
        out.append((source, csv))
    return out


def _section(spec: dict, found: list[Source], at: str, base: Path, drawings: list[Drawing]) -> tuple[Section | None, str]:
    """A recipe's section over its sources (`base`: where its files are): (None, why) when it is optional and none
    of them has what it shows."""
    section = Section(spec["title"], spec.get("note", ""), plot=dict(spec.get("plot", {})), spec=spec, found=found, at=at)
    set_, look = spec.get("set", "totality"), bool(spec.get("plot"))
    if "pages" in spec:
        section.grids = _pages_section(spec, found, at, drawings)
    elif "compare" in spec:
        section.grids = _compare_section(spec, found, at)
    elif "files" in spec:
        section.grids = _files_section(spec, base, at)
    elif "stats" in spec:
        section.parts = [Part(s, set_, list(spec["stats"]), csv, look) for s, csv in _numbers(spec, found, set_, f"{at}.stats", drawings)]
    elif "tools" in spec:
        section.given = [g for s in found for g in configured(s, list(spec["tools"]), list(spec.get("hide", [])), at,
                                                             spec.get("optional", False))]
    else:
        section.bars = [Bars(s, set_, list(spec["bars"]), csv, look) for s, csv in _numbers(spec, found, set_, f"{at}.bars", drawings)]
    if spec.get("optional") and not (section.grids or section.parts or section.bars or section.given):
        return None, f"{spec['title']}: " + ("no source has a record of its points' tools" if "tools" in spec else
                                             f"no source has {set_} drawn, or a page of it to draw" if "pages" in spec else
                                             f"no source has {set_} measured, or a page of it to measure")
    return section, ""


def _out(recipe: dict, used: list[Source], where: str) -> Path:
    """Where a report is built when -o names nowhere (A6): its [report].output (a folder under reports/, ./… the
    work dir's, /… a path), else where results/ has its sources: their common address under reports/."""
    given = recipe.get("output")
    if given:
        if given.startswith("../") or "/../" in given:
            raise HeimdallError(f"output '{given}' climbs out of reports/", where=f"{where}.output", hint="name a folder under reports/, or ./… or /…")
        return Path(given) if given.startswith("/") else work_root() / given[2:] if given.startswith("./") else reports_root() / given
    outside = [s.address for s in used if Path(s.address).is_absolute()]
    if outside:
        raise HeimdallError(f"{outside[0]} is not under results/, so its report has no place of its own under reports/", where=where,
                       hint='-o DIR builds it there, or output = "<folder>" in its [report]')
    common = _common(used)
    if not common:
        projects = ", ".join(dict.fromkeys(s.address.split("/", 1)[0] for s in used))
        raise HeimdallError(f"its sources are of several projects ({projects}), so its report has no one place under reports/",
                       where=where, hint='-o DIR builds it there, or output = "<folder>" in its [report]')
    return reports_root() / common


def resolve(recipe: dict, given: list[str], *, path: Path | None = None, command: str = "", out: Path | None = None,
            found: list[Source] | None = None) -> Plan:
    """A recipe ([report], its sections) and its sources as a Plan; with no sections, the default's. `given`: the
    command line's sources, which replace [report].from (`found`: them, read already); a section's own from stays.
    What a source has not drawn or measured is drawn for the report by the build (P6: the plan's drawings); an
    optional section no source has, nor can draw, is left out, and said."""
    where = str(path) if path else "the default report"
    named = given or recipe.get("from", [])
    if not named and not any(s.get("from") for s in recipe.get("section", [])):
        raise HeimdallError("a report needs a source", where=where,
                       hint="heimdall report <recipe>.toml <P>/<run>/<cfg>, or from = [\"<P>/<run>/<cfg>\"] in [report]")
    every = found if found is not None else sources(named, "the command line" if given else f"{where}: [report].from") if named else []
    specs = recipe.get("section") or default_recipe(every, recipe.get("tools"))["section"]
    sections: list[Section] = []
    left: list[str] = []
    drawings: list[Drawing] = []
    used: list[Source] = list(every)
    for number, spec in enumerate(specs, 1):
        at = f"{where}: section {number} ({spec.get('title', '')})"
        found_ = sources(spec["from"], f"{at}.from") if spec.get("from") else every
        used += [s for s in found_ if s not in used]
        section, why = _section(spec, found_, at, path.parent if path else Path.cwd(), drawings)
        if section is None:
            left.append(why)
            continue
        sections.append(section)
    facts = [s.doc.source for s in used]
    title = filled(recipe.get("title", ""), facts) or (used[0].address if len(used) == 1 else _common(used) or "report")
    context = recipe.get("context", "first")
    tools, results = [s for s in sections if s.context], [s for s in sections if not s.context]
    sections = tools + results if context == "first" else results + tools          # what was run first (I-111)
    return Plan(command or where, title, filled(recipe.get("subtitle", ""), facts), used, sections,
                out or _out(recipe, used, where), path, left, drawings, look_of(recipe), recipe.get("method", True), context)


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


def planned(first: str | None, rest: list[str], out: Path | None = None) -> Plan:
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
            raise HeimdallError("a run TOML's [report] is its folders' reports: name the folders", where=str(path),
                           hint=f"heimdall report {first} <P>/<run>/<cfg>")
        return resolve(recipe, rest, path=path, command=command, out=out)
    given = [first, *rest] if first else list(rest)
    if not given:
        raise HeimdallError("a report needs a source", hint="heimdall report <P>/<run>/<cfg>; heimdall report <recipe>.toml <source>")
    found = sources(given, "the command line")
    own = found[0].folder / RECIPE if len(found) == 1 else None
    if own is not None and own.is_file():
        return resolve(load_recipe(own), given, path=own, command=command, out=out, found=found)
    return resolve({}, given, command=command, out=out, found=found)


def listing(plan: Plan) -> list[str]:
    """`heimdall report … --list`: its sources, then each section and what it shows, nothing written."""
    lines = [f"report {plan.name} → {plan.out}: {len(plan.sources)} source(s), {len(plan.sections)} section(s), "
             f"about {plan.pages()} page(s) of figures" + (f"; from {plan.recipe}" if plan.recipe else "; the default")]
    for source in plan.sources:
        f = source.facts()
        lines.append(f"  source {f['address']}: {f['configuration'] or source.doc.name}" + (f" [{f['tag']}]" if f["tag"] else "")
                     + f", {f['complete']} of {f['points']} point(s)"
                     + (f", {f['events']} events" if f["events"] else "") + f", against {f['against']}"
                     + (", its points newer than its pages" if f["stale"] else ""))
    lines += [f"  drawn for the report: {drawing.describe()}" for drawing in plan.drawings]
    for number, section in enumerate(plan.sections, 1):
        figures = [fig for g in section.grids for fig in g.figures if fig.file is not None]
        drawn = list(dict.fromkeys(fig.source.address for g in section.grids for fig in g.figures if fig.file is None))
        what = []
        under = [f"{grid.caption}: " + (f"{len(grid.figures)}" if all(fig.file for fig in grid.figures) else "drawn for the report")
                 for grid in section.grids]
        if section.grids:
            what.append(f"{len(figures)} figure(s) in {sum(all(fig.file for fig in g.figures) for g in section.grids)} grid(s)"
                        + (f", the pages of {', '.join(drawn)} drawn for the report" if drawn else ""))
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
        for source in dict.fromkeys(g.source.address for g in section.given):
            mine = [g for g in section.given if g.source.address == source]
            what.append(f"tools of {source}: " + ", ".join(f"{g.tag} ({g.summary()})" for g in mine))
            under += [f"{g.tag}: {note}" for g in mine for note in g.notes]
        lines.append(f"  {number} {section.title}: " + "; ".join(what))
        lines += [f"      {line}" for line in under]
    if plan.method and plan.shows_numbers():
        lines.append(f"  {METHOD_TITLE} (unnumbered): each statistic's formula and meaning, "
                     + ("after what was run, before the results" if plan.context == "first" else "last"))
    lines += [f"  left out: {why}" for why in plan.left]
    return lines


def starter(name: str, source: Source) -> str:
    """`--init`: the default report's sections as a recipe, each set's cells and pages listed, and the sets
    drawn that its document does not draw by default as sections commented out (V207)."""
    lines = [f"# configs/{name}: a report, `heimdall report {name} <source>` (docs/03_Plots.md §11; its keys 04 §15).",
             "# The sources on the command line replace `from`; each [[report.section]] shows one of pages, compare,",
             "# stats, bars or files.", "", "[report]", f'title = "{source.doc.name} · {source.name}"',
             '# subtitle = "for the group, <date>"', f'from  = ["{source.address}"]',
             "# its look, each key's default (04 §15):", '# font     = "sans"      # "serif": TeX Gyre Termes for the body',
             "# size     = 9.5         # the body's pt, 8 to 12", '# accent   = "#2a78d6"   # section numbers, kickers, code\'s keys',
             "# columns  = 2           # a grid's, when its section names none", "# contents = true        # the contents on the front page",
             "# context  = \"first\"     # what was run and How the numbers are made: before the results, or \"last\"",
             "# method   = true        # How the numbers are made: each statistic's formula and meaning, a paragraph each",
             "", "# what each tool was given, from the records: the card's lines every point had, then what varied (shown first)",
             "[[report.section]]", 'title = "Tools"', 'tools = ["*"]', '# hide  = ["Random:seed", "RANDOM_SEED"]',
             "optional = true", ""]
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

FIGURES, STATS, TOOLS, STAMPS = "figures", "stats", "tools", ".stamps.json"
#: A varied table's key columns on an A4 page; more are carried on in a further table, the points again.
KEYS_PER_TABLE = 5
#: Characters pdflatex sets as they are (T1, textcomp); MATH's as math; any other is declared, shown as ?, so a
#: card in any script never stops the report.
SAFE = set("–—‘’“”…•·±×÷→←€µ")
MATH = {**{c: f"\\{n}" for c, n in zip("αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΥΦΨΩ",
                                        ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi rho "
                                         "sigma tau upsilon phi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon "
                                         "Phi Psi Omega").split())},
        "∞": r"\infty", "−": "-", "≤": r"\leq", "≥": r"\geq", "≈": r"\approx", "≠": r"\neq", "≡": r"\equiv",
        "√": r"\surd", "∑": r"\sum", "∫": r"\int", "∂": r"\partial", "∈": r"\in", "⊕": r"\oplus", "⊗": r"\otimes",
        "∝": r"\propto", "∼": r"\sim", "↔": r"\leftrightarrow", "⇒": r"\Rightarrow", "ℓ": r"\ell", "ħ": r"\hbar",
        "⁺": "^{+}", "⁻": "^{-}", "⁰": "^{0}", "⁴": "^{4}", "⁵": "^{5}", "⁶": "^{6}", "⁷": "^{7}", "⁸": "^{8}",
        "⁹": "^{9}", "₀": "_{0}", "₁": "_{1}", "₂": "_{2}", "₃": "_{3}", "₄": "_{4}"}
#: The page (I-110 R2), in bp: A4, 18 mm left and right, 22 mm top (the running header 8 mm over the body), 20 mm
#: bottom (the footer 11 mm under it). A grid is placed a row of panels at a time, each at most ROW_MOST high, so a
#: page breaks between rows; GAP between panels, LABEL a panel's label over it.
MM = 72 / 25.4
A4_BP = (595.28, 841.89)
SIDE, TOP, BOTTOM = 18 * MM, 22 * MM, 20 * MM
TEXT_W, TEXT_H = A4_BP[0] - 2 * SIDE, A4_BP[1] - TOP - BOTTOM
ROW_MOST = 0.55 * TEXT_H
GAP, LABEL = 6.0, 12.0
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
    return plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "layout.py", "layout")


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
    head: SetHead | None = None   # the set's sub-header over it
    toc: str = ""                 # its line in the contents ("": none)
    title: str = ""               # index.html's block title


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
        self.copied = self.drawn = self.data = 0

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

    def write(self, target: Path, text: str) -> Path:
        """`text` into `target`, unless it holds it already."""
        data = text.encode("utf-8")
        if not target.is_file() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            self.copied += 1
        self.shas[self.rel(target)] = hashlib.sha256(data).hexdigest()
        return target

    def prune(self) -> None:
        """What no section holds any more, removed from figures/, stats/ and tools/ (and their empty folders)."""
        for top in (FIGURES, STATS, TOOLS):
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


def _typeset():
    return plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "typeset.py", "typeset")


@dataclass
class Typeset:
    """Statistics typeset in the report (I-110 R5): a source's part of its summary, or its pages' bar tables, as
    LaTeX in the report's own fonts (figures/typeset.py), the numbers they are made from beside them (R6)."""
    title: str                   # its block's title, its line in the contents
    tagline: str
    lines: list[str]
    data: list[Path]             # the CSVs beside it
    page: Path | None = None     # the same document as one HTML page, for index.html
    toc: str = ""                # its line in the contents, when not its title
    notes: dict = field(default_factory=dict)    # the notes its items name, every one (key → text)
    refer: bool = False          # its definitions are How the numbers are made's, not its own (I-111)


#: The notes How the numbers are made gives (I-111): each statistic's definition (stat-<key>), how a page is compared,
#: and how points are scored and play their matches; a statistics part then leaves them out.
METHOD_NOTES = ("compared", "counted", "apart", "score", "h2h")
METHOD_TITLE = "How the numbers are made"


def _method_note(key: str) -> bool:
    return key.startswith("stat-") or key in METHOD_NOTES


def _measuring():
    """Matplotlib, headless: paper.py measures text with it."""
    import matplotlib
    matplotlib.use("Agg")


def _part(build: _Build, bars, part: Part, folder: Path, stem: str, say, method: bool = False) -> Typeset | None:
    """A source's statistics, the sections chosen, typeset (its facts, its items, its notes numbered at its end;
    `method`: those How the numbers are made gives left out); beside it its numbers, stats/<section>/<stem>__<set>.csv
    (the statistics.csv they were read from), and the same document, every note kept, as one HTML page."""
    heading = statstable.heading_of(part.csv.parent) if part.csv.is_relative_to(part.source.folder) else \
        f"{part.source.address} · {part.set}" + (" · as this report measures it" if part.look else "")
    _measuring()
    document, gone = chosen(bars.summary_model(statstable.read(part.csv), heading), part.keys)
    if gone:
        say(f"report: {heading} has no {', '.join(gone)} (too few curves or page cells for them)")
    if not document.sections:
        return None
    numbers = bars.paper.note_numbers(document)
    target = folder / f"{stem}__{slug(part.set)}"
    data = target.with_suffix(".csv")
    build.copy(part.csv, data)
    page = build.write(target.with_suffix(".html"), bars.webpage.render(document, numbers, bars.paper))
    summary = part.csv.with_name("summary.html")
    if summary.is_file():
        build.copy(summary, build.out / STATS / "summaries" / f"{slug(part.source.address)}__{slug(part.set)}.html")
    shown = dataclasses.replace(document, notes={k: v for k, v in document.notes.items() if not _method_note(k)}) \
        if method else document
    lines = _typeset().document(shown, bars.paper.note_numbers(shown), bars.paper, _layout().tex, TEXT_W)
    return Typeset(heading, "statistics" + (" · as this report measures it" if part.look and "measures" not in heading else ""),
                   lines, [data], page, notes={k: document.notes[k] for k in numbers}, refer=method)


def _raw_rows(path: Path) -> list[dict]:
    """statistics.csv's rows as written: text, so a page's rows are copied as they are."""
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _bars(build: _Build, bars, item: Bars, folder: Path, number: int, method: bool = False) -> Typeset:
    """A source's pages' statistics, a table each (a row a curve, a column a statistic, each a small bar and its
    value), from its statistics.csv; beside each, its rows: stats/<section>/<MM>_<source>/<NNN>_<page>.csv."""
    rows = _raw_rows(item.csv)
    pages: dict[str, list[dict]] = {}
    for row in rows:
        pages.setdefault(row["page"], []).append(row)
    names = [n for n in sorted(pages, key=natural) if any(_matches(n, g) for g in item.pages)]
    if not names:
        raise HeimdallError(f"bars: {', '.join(item.pages)} names no page measured in {item.csv}",
                       hint=f"its pages: {', '.join(list(sorted(pages, key=natural))[:6])} …" if pages else None)
    _measuring()
    typeset, tex = _typeset(), _layout().tex
    where = folder / f"{number:02d}_{slug(item.source.folder.name)}"
    lines, data = [], []
    for k, name in enumerate(names, 1):
        mine = pages[name]
        title = ", ".join(part for part in (cell_label(item.source.doc, _cell(name)), name.rsplit("/", 1)[-1]) if part)
        against = next((r.get("reference", "") for r in mine if r.get("reference")), "")
        lines += typeset.bars(mine, title, f"against {against}" if against else "", bars.PANELS, bars.paper, tex, TEXT_W)
        buffer = io.StringIO()
        out = csv.DictWriter(buffer, fieldnames=list(mine[0]), lineterminator="\n")
        out.writeheader()
        out.writerows(mine)
        data.append(build.write(where / f"{k:03d}_{slug(name)}.csv", buffer.getvalue()))
    title = f"{item.source.address} · {item.set}" + (" · as this report measures it" if item.look else "")
    notes = {"compared": bars.COMPARED, **{f"stat-{key}": bars.NOTES[key] for key, _ in bars.PANELS}}
    return Typeset(title, f"{len(names)} page(s), a table each", lines, data, notes=notes, refer=method)


#: A figure's data (I-110 R6): each curve's bins as the run made them (before the page's normalisation), and the
#: data's, read from the YODAs its page document names.
FIGURE_COLUMNS = ("curve", "label", "xlow", "xhigh", "y", "err_down", "err_up")


def _page_document(figure: Figure, drawings: list[Drawing]) -> Path | None:
    """A figure's page document: in its drawing's work/ when it was drawn for the report, else in its source's
    cache (.cache/<P>/plots/<run>/<cfg>/<set>/<page>.toml); None when there is none."""
    source = figure.source
    if source is None or figure.file is None:
        return None
    drawn = next((d for d in drawings if d.results is not None and figure.file.is_relative_to(d.results)), None)
    work = drawn.folder / "work" if drawn else plotdoc._folders(source.folder, source.project).cache
    path = work / figure.set / f"{figure.page}.toml"
    return path if path.is_file() else None


class _Yodas:
    """The YODA files a build reads figures' data from, each read once per analysis (YODA's Python, the stack's);
    none without it."""

    def __init__(self):
        try:
            import yoda
        except ImportError:
            yoda = None
        self.yoda = yoda
        self.read: dict[tuple[str, str], dict] = {}

    def points(self, path: Path, name: str) -> list[tuple] | None:
        """An object's points, (xlow, xhigh, y, err_down, err_up) each; None when it is not there."""
        prefix = "/".join(name.split("/")[:3 if name.startswith("/REF/") else 2]) + "/"
        key = (str(path), prefix)
        if key not in self.read:
            try:
                self.read[key] = self.yoda.read(str(path), patterns=["^" + re.escape(prefix)])
            except Exception:                                        # a file YODA cannot read: no data from it
                self.read[key] = {}
        found = self.read[key].get(name)
        if found is None:
            return None
        try:
            shown = found.mkScatter()
        except Exception:
            return None
        return [(p.x() - p.xErrs()[0], p.x() + p.xErrs()[1], p.y(), p.yErrs()[0], p.yErrs()[1]) for p in shown.points()]


def _figure_data(build: _Build, figure: Figure, document: Path, target: Path, yodas: _Yodas) -> Path | None:
    """figures/<section>/<stem>.csv: each curve of the figure's page document, a row a bin (FIGURE_COLUMNS), its
    member's YODA read; the page's data as curve `data`. Made again only when the page document or a YODA it names
    changed."""
    source = figure.source
    members = {m.point.name: m for m in source.members}
    page = tomllib.loads(document.read_text(encoding="utf-8"))
    wanted = []
    for curve in page.get("curve", []):
        member, _, name = str(curve.get("object", "")).partition("/")
        found = members.get(member)
        if found is not None and found.yoda is not None and found.yoda.is_file():
            wanted.append((member, str(curve.get("label", member)), found.yoda, "/" + name))
    data = page.get("data")
    if isinstance(data, dict) and data.get("object") and (source.doc.plot or {}).get("data"):
        try:
            file = plotting.data_source(str(source.doc.plot["data"].get("file", "")), source.doc)
            wanted.append(("data", str(data.get("label", "data")), file, "/" + str(data["object"]).lstrip("/")))
        except HeimdallError:
            pass
    if not wanted:
        return None

    def make() -> list[Path]:
        buffer = io.StringIO()
        out = csv.writer(buffer, lineterminator="\n")
        out.writerow(FIGURE_COLUMNS)
        for curve, label, path, name in wanted:
            out.writerows([curve, label, *(f"{v:.10g}" for v in point)] for point in yodas.points(path, name) or [])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(buffer.getvalue(), encoding="utf-8")
        return [target]
    key = _key(_sha(document), *(f"{c}:{n}:{_stat(p)}" for c, _, p, n in wanted))
    return build.stamped(target, key, make)[0]


@dataclass
class Configs:
    """What a tool was given as the report shows it (A9): the Given, its baseline as a card and its varied lines
    as a CSV, in tools/<NN>_<section>/<MM>_<source>/."""
    given: Given
    baseline: Path | None
    varied: Path | None


def _configs(build: _Build, item: Given, folder: Path) -> Configs:
    """tools/…/<tag>.baseline<ext> (the lines every point had, as the card has them) and <tag>.varied.csv (a row a
    point, a column a key; else a row a line), each written when it changed."""
    baseline = build.write(folder / f"{item.tag}.baseline{item.ext}", "\n".join(item.baseline) + "\n") \
        if item.ext and item.baseline else None
    varied = None
    if any(lines for _, _, lines in item.varied):
        buffer = io.StringIO()
        out = csv.writer(buffer, lineterminator="\n")
        table = item.table()
        if table is not None:
            out.writerow(["point", "label", *table[0]])
            out.writerows([point, label, *(row.get(k, "") for k in table[0])] for (point, label, _), row in zip(item.varied, table[1]))
        else:
            out.writerow(["point", "label", "line"])
            out.writerows([point, label, line] for point, label, lines in item.varied for line in lines)
        varied = build.write(folder / f"{item.tag}.varied.csv", buffer.getvalue())
    return Configs(item, baseline, varied)


def _place(build: _Build, plan: Plan, say) -> tuple[list[tuple[Section, list]], "Prose | None"]:
    """Every section's figures copied into figures/<NN>_<section>/, each with its data (a CSV, from its page
    document's YODAs), its statistics and bar tables typeset, their numbers into stats/<NN>_<section>/; each grid
    and part as the report shows it; and How the numbers are made, for the statistics shown (I-111)."""
    bars = statstable.bars()
    method = plan.method and plan.shows_numbers()
    yodas = _Yodas()
    figures = sum(1 for s in plan.sections for g in s.grids for f in g.figures if f.source is not None)
    if figures and yodas.yoda is None:
        say("report: no YODA module here, so no figure's data beside it (figures/…/<page>.csv)")
    data = 0
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
                document = _page_document(figure, plan.drawings) if yodas.yoda is not None else None
                if document is not None and _figure_data(build, figure, document, shown.with_suffix(".csv"), yodas):
                    data += 1
            columns = grid.columns or (1 if len(files) == 1 else plan.look.columns)
            caption = grid.cell if "pages" in section.spec else "" if "files" in section.spec else grid.caption
            head, set_ = grid.head, grid.figures[0].set if "pages" in section.spec else ""
            grids.append(Placed(caption, files, [f.label for f in grid.figures], [""] * len(files), pngs,
                                columns, _aspect(grid.figures[0].file), head=head,
                                toc=(head.set if len(plan.sources) == 1 else f"{head.set} · {head.address}") if head else
                                caption if "compare" in section.spec else "",
                                title=" · ".join(part for part in (set_, caption) if part) or section.title))
        for k, part in enumerate(section.parts, 1):
            shown = _part(build, bars, part, build.out / STATS / name, f"{k:02d}_{slug(part.source.folder.name)}", say, method)
            if shown is not None:
                shown.toc = f"{part.set} · statistics" if len(plan.sources) == 1 and not part.look else ""
                grids.append(shown)
        for k, item in enumerate(section.bars, 1):
            grids.append(_bars(build, bars, item, build.out / STATS / name, k, method))
            grids[-1].toc = f"{item.set} · a table a page" if len(plan.sources) == 1 and not item.look else ""
        sources = list(dict.fromkeys(g.source.address for g in section.given))
        for item in section.given:
            mm = sources.index(item.source.address) + 1
            grids.append(_configs(build, item, build.out / TOOLS / name / f"{mm:02d}_{slug(item.source.folder.name)}"))
        placed.append((section, grids))
    build.data = data
    shown = [g for _, grids in placed for g in grids if isinstance(g, Typeset)]
    return placed, _method(bars, shown, plan) if method and shown else None


@dataclass
class Prose:
    """How the numbers are made (I-111), as report.tex and index.html show it."""
    lines: list[str]
    html: str


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _method(bars, shown: list[Typeset], plan: Plan) -> Prose:
    """How the numbers are made, from the notes of the statistics shown: how a page is compared; each statistic
    shown, in the summary's order, its name, its formula set as display math and what it sums over and means, a
    paragraph each; how points are scored (each part's rule on the pages counted) and play their matches."""
    typeset, tex, esc = _typeset(), _layout().tex, html.escape
    notes: dict = {}
    for item in shown:
        notes.update({k: v for k, v in item.notes.items() if k not in notes})
    counted = list(dict.fromkeys(item.notes["counted"] for item in shown if "counted" in item.notes))
    labels = dict(bars.PANELS)
    used = [key for key, _, _ in bars.TABLES if f"stat-{key}" in notes]
    where = "below" if plan.context == "first" else "above"
    lines = [rf"\hdNote{{What each number in the statistics and bar tables {where} is: how a page is compared with its "
             r"reference, each statistic's formula and what it says, and how points are scored.}"]
    page = [f"<p>What each number in the statistics and bar tables {where} is.</p>"]

    def heading(title: str) -> None:
        lines.extend([r"\hdKeep{110bp}\phantomsection\addcontentsline{toc}{subsection}{" + tex(title) + "}",
                      rf"\hdStatSection{{{tex(title)}}}"])
        page.append(f"<h3>{esc(title)}</h3>")

    def paragraphs(texts: list[str]) -> None:
        lines.extend(typeset.paragraph(_sentence(text), tex) for text in texts)
        page.extend(f"<p>{esc(_sentence(text))}</p>" for text in texts)
    if "compared" in notes:
        heading("How a page is compared")
        paragraphs([bars.COMPARED])
    if used:
        heading("The statistics")
        for key in used:
            formula, rest = bars.DEFINITIONS[key]
            lines.extend(typeset.definition(labels[key], bars.FORMULAS[key], _sentence(rest), tex))
            page.append(f"<p><strong>{esc(bars.PLAIN[key])}</strong>: {esc(formula)}</p><p>{esc(_sentence(rest))}</p>")
    if "score" in notes:
        heading("How points are scored")
        paragraphs([bars.SCORE_TEXT, bars.APART, *counted])
    if "h2h" in notes:
        heading("Head to head")
        paragraphs([bars.H2H_TEXT])
    return Prose(lines, "\n".join(page))


def _breakable(text: str) -> str:
    """Text for LaTeX that may break after a / or an _ (an address, a folder's name)."""
    return _layout().tex(text).replace("/", "/\\allowbreak{}").replace("\\_", "\\_\\allowbreak{}")


def _rows(placed: Placed) -> tuple[float, float, list[tuple[int, int]]]:
    """A grid as rows of panels, a picture each, so that a page breaks between them: (cell width, cell height,
    each row's first and last figure)."""
    columns = placed.columns
    cw = (TEXT_W - (columns - 1) * GAP) / columns
    ch = min(cw / placed.aspect, ROW_MOST - placed.label)
    return cw, ch, [(start, min(len(placed.files), start + columns)) for start in range(0, len(placed.files), columns)]


#: report.tex's preamble (I-110 R2): its look, every size, colour and space set here once, as macros the body uses.
#: @…@ are the look's (Look): the fonts, the body's size and line, the accent, the title in the running header.
PREAMBLE = r"""\documentclass[a4paper]{article}
%% Made by heimdall report: every file it names is in this folder, so it compiles here as it is (pdflatex, twice).
%% Its look is set here, once: the fonts, sizes, colours and spaces as macros (\hd…), which the body uses alone.
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{textcomp}
\usepackage{lmodern}
\usepackage{tgheros}
@FONT@
\renewcommand{\ttdefault}{lmtt}
\usepackage[a4paper,left=18mm,right=18mm,top=22mm,bottom=20mm,headheight=14pt,headsep=8mm,footskip=11mm]{geometry}
\usepackage[table]{xcolor}
\usepackage{graphicx,array,longtable,booktabs}
\usepackage{fvextra}
\usepackage{enumitem}
\usepackage{titlesec,titletoc}
\usepackage{fancyhdr,lastpage}
\usepackage[letterspace=60]{microtype}
\usepackage[hidelinks,bookmarksdepth=2]{hyperref}
%% colours: ink, muted (taglines, captions, labels, notes), rules, a band's fill, the accent, code's numbers and words
\definecolor{hdink}{HTML}{0B0B0B}
\definecolor{hdmuted}{HTML}{52514E}
\definecolor{hdrule}{HTML}{E4E3DF}
\definecolor{hdframe}{HTML}{A3A29D}
\definecolor{hdband}{HTML}{EFEEEA}
\definecolor{hdaccent}{HTML}{@ACCENT@}
\definecolor{hdnumber}{HTML}{0B6E4F}
\definecolor{hdkeyword}{HTML}{7B3FB5}
%% sizes: \hdSize{pt}{line}; the body @SIZE@ on @LINE@
\newcommand\hdSize[2]{\fontsize{#1}{#2}\selectfont}
\makeatletter
\renewcommand\normalsize{\@setfontsize\normalsize{@SIZE@}{@LINE@}\abovedisplayskip 6pt plus 2pt\belowdisplayskip 6pt plus 2pt%
  \abovedisplayshortskip 3pt\belowdisplayshortskip 3pt}
\newcommand\hdContents{\@starttoc{toc}}
%% \hdKeep{len}: a new page unless len is left on this one (no penalty, unlike needspace's: TeX never prefers it)
\newcommand\hdKeep[1]{\par\begingroup\setlength{\dimen@}{#1}\dimen@ii\pagegoal\advance\dimen@ii-\pagetotal
  \ifdim\dimen@>\dimen@ii\ifdim\dimen@ii>\z@\vfil\fi\break\fi\endgroup}
\makeatother
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\setlength{\unitlength}{1bp}
\setcounter{tocdepth}{2}
\color{hdink}
%% the page: the title left and the section right over a rule; "page n of N" centred under the body
\newcommand\hdHeadFont{\sffamily\hdSize{7.5}{9}\color{hdmuted}}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\hdHeadFont @TITLE@}
\fancyhead[R]{\hdHeadFont\leftmark}
\fancyfoot[C]{\hdHeadFont page \thepage\ of \pageref*{LastPage}}
\renewcommand\headrulewidth{0.5pt}
\renewcommand\headrule{{\color{hdrule}\hrule height\headrulewidth width\headwidth\vskip-\headrulewidth}}
\fancypagestyle{front}{\fancyhf{}\renewcommand\headrulewidth{0pt}\fancyfoot[C]{\hdHeadFont page \thepage\ of \pageref*{LastPage}}}
\renewcommand\sectionmark[1]{\markboth{\thesection\quad #1}{}}
%% titles: a section starts a page, its number in the accent
\titleformat{\section}{\sffamily\hdSize{15}{18}\bfseries}{\textcolor{hdaccent}{\thesection}}{0.55em}{}
\titlespacing*{\section}{0pt}{0pt}{6pt}
\titleformat{\subsection}{\sffamily\hdSize{11}{14}\bfseries}{}{0pt}{}
\titlespacing*{\subsection}{0pt}{16pt}{4pt}
\titlecontents{section}[1.7em]{\addvspace{5pt}\sffamily\hdSize{9.5}{13}\bfseries}%
  {\contentslabel[\textcolor{hdaccent}{\thecontentslabel}]{1.7em}}{\hspace*{-1.7em}}{\hfill\contentspage}
\titlecontents{subsection}[1.7em]{\sffamily\hdSize{8.5}{11.5}\color{hdmuted}}{}{}{\titlerule*[5pt]{\hbox{.}}\contentspage}
%% tables: booktabs rules, rows 1.3 lines high, 5pt each side of a cell, set left
\setlength{\tabcolsep}{5pt}
\renewcommand{\arraystretch}{1.3}
\setlength{\aboverulesep}{0pt}
\setlength{\belowrulesep}{0pt}
\setlength{\heavyrulewidth}{0.6pt}
\setlength{\lightrulewidth}{0.4pt}
\setlength{\LTleft}{0pt}
\setlength{\LTright}{\fill}
\setlength{\LTpre}{3pt}
\setlength{\LTpost}{0pt}
\arrayrulecolor{hdframe}
\newenvironment{hdTable}[1]{\par\sffamily\hdSize{8}{10.5}\begin{longtable}{#1}}{\end{longtable}\par}
\newcommand\hdContinued{\textit{\color{hdmuted}(continued)}}
\newcommand\hdBlockGap{\par\vspace{8pt}}
\newcommand\hdSmall{\hdSize{7}{9}}
\newcommand\hdMuted[1]{\textcolor{hdmuted}{#1}}
%% text: a kicker (a block's name, small capitals in the accent), a tagline, a section's note, an item's title
\newcommand\hdKicker[1]{{\sffamily\hdSize{7.5}{9}\bfseries\color{hdaccent}\textls{\MakeUppercase{#1}}}}
\newcommand\hdTitle[1]{{\sffamily\hdSize{22}{26}\bfseries #1\par}}
\newcommand\hdSubtitle[1]{{\sffamily\hdSize{12.5}{16}\color{hdmuted}#1\par}}
\newcommand\hdTagline[1]{{\sffamily\hdSize{8}{11}\color{hdmuted}#1\par}}
\newcommand\hdNote[1]{{\hdSize{9}{13.5}\color{hdmuted}#1\par}\vspace{10pt}}
\newcommand\hdBlockTitle[2]{\par\addvspace{16pt}{\sffamily\hdSize{11}{14}\bfseries #1}\hspace{0.6em}{\sffamily\hdSize{8}{10}\color{hdmuted}#2}\par\vspace{4pt}}
\newcommand\hdLabel[2]{\par\addvspace{9pt}{\sffamily\hdSize{8}{10}\bfseries #1}\hspace{0.5em}{\hdSize{7.5}{9}\ttfamily\color{hdmuted}#2}\par\vspace{3pt}}
\newcommand\hdItem[1]{\par\addvspace{12pt}{\sffamily\hdSize{9.5}{12}\bfseries #1\par}\vspace{2pt}}
\newcommand\hdSub[1]{{\sffamily\hdSize{8}{10.5}\color{hdmuted}#1\par}\vspace{2pt}}
\newcommand\hdStatSection[1]{\par\addvspace{16pt}{\sffamily\hdSize{11}{14}\bfseries #1\par}\vspace{2pt}}
%% How the numbers are made: a statistic's name, its formula in display, what it means; a paragraph of prose
\newcommand\hdDefinition[3]{\par\addvspace{14pt}{\sffamily\hdSize{10}{13}\bfseries #1\par}\vspace{6pt}%
  {\centering\hdSize{11}{15}$\displaystyle #2$\par}\vspace{8pt}#3\par}
\newcommand\hdPara[1]{\par\addvspace{6pt}#1\par}
%% a set's sub-header: its name and source, then a line a fact (Pages, Curves, Fixed); a grid's caption; a panel's label
\newcommand\hdFact[2]{\par\hangindent=4.6em\hangafter=1\noindent\makebox[4.6em][l]{\textcolor{hdmuted}{#1}}#2\par}
\newcommand\hdSetHead[3]{\par\addvspace{18pt}{\sffamily\hdSize{11}{14}\bfseries #1}\hspace{0.7em}%
  {\hdSize{7.5}{9}\ttfamily\color{hdmuted}#2}\par\vspace{4pt}{\sffamily\hdSize{8.5}{12}#3\par}\vspace{8pt}}
\newcommand\hdCaption[1]{{\sffamily\hdSize{8.5}{11}\bfseries #1\par}\vspace{4pt}}
\newcommand\hdPanel{\sffamily\hdSize{7.5}{9}\color{hdmuted}}
\newcommand\hdGridGap{\par\vspace{8pt}}
\newenvironment{hdFacts}{\begin{itemize}[leftmargin=1.1em,itemsep=1pt,parsep=0pt,topsep=2pt,label={\textcolor{hdmuted}{\textbullet}}]%
  \sffamily\hdSize{8.5}{12}}{\end{itemize}}
\newenvironment{hdNotes}{\par\addvspace{14pt}{\color{hdrule}\rule{\linewidth}{0.5pt}}\par\vspace{4pt}\hdKicker{Notes}\par\vspace{2pt}%
  \begin{itemize}[leftmargin=1.8em,labelsep=0.4em,itemsep=3pt,parsep=0pt,topsep=2pt,align=left]\hdSize{7.5}{11}\color{hdmuted}}{\end{itemize}}
\newenvironment{hdFlags}{\begin{itemize}[leftmargin=1.1em,itemsep=2pt,parsep=0pt,topsep=3pt,label={\textcolor{hdmuted}{\textbullet}}]%
  \sffamily\hdSize{8}{11}\color{hdmuted}\itshape}{\end{itemize}}
%% code: Latin Modern Typewriter 7.5 on 9.5, a rule at its left; keys bold in the accent, = and : muted, numbers and
%% words (on, off, true, false) their own colours, comments muted italic
\newcommand\hdCode{\fontsize{7.5}{9.5}\selectfont}
\fvset{fontsize=\hdCode,breaklines,breakafter={/_:=,.-},frame=leftline,framerule=1.5pt,rulecolor=\color{hdrule},framesep=8pt,xleftmargin=2pt}
\newcommand\hdK[1]{\textcolor{hdaccent}{\bfseries #1}}
\newcommand\hdP[1]{\textcolor{hdmuted}{#1}}
\newcommand\hdN[1]{\textcolor{hdnumber}{#1}}
\newcommand\hdB[1]{\textcolor{hdkeyword}{#1}}
\newcommand\hdC{\color{hdmuted}\itshape}
\newcommand\hdBS{\char`\\}
\newcommand\hdLB{\char`\{}
\newcommand\hdRB{\char`\}}
"""

#: The fonts (Look.font): TeX Gyre Heros throughout, math in it too (sansmath; Greek capitals from Latin Modern
#: Sans, lowercase from Latin Modern's math); or TeX Gyre Termes for the body, the titles, tables and labels sans.
FONTS = {"sans": "\n".join([r"\renewcommand{\familydefault}{\sfdefault}", r"\usepackage[T1]{sansmath}",
                            r"\SetSymbolFont{letters}{sans}{OML}{lmm}{m}{it}", r"\SetSymbolFont{symbols}{sans}{OMS}{lmsy}{m}{n}",
                            r"\SetMathAlphabet{\mathsfsl}{sans}{T1}{qhv}{m}{it}", r"\DeclareSymbolFont{hdgreek}{OT1}{lmss}{m}{n}",
                            *(rf'\DeclareMathSymbol{{\{name}}}{{\mathord}}{{hdgreek}}{{"{k:02X}}}' for k, name in
                              enumerate("Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega".split())),
                            r"\sansmath"]),
         "serif": "\n".join([r"\usepackage{tgtermes}", r"\renewcommand{\familydefault}{\rmdefault}"])}


def _preamble(plan: Plan) -> str:
    """report.tex's preamble with the plan's look filled in."""
    look = plan.look
    title = plan.title if len(plan.title) <= 80 else plan.title[:78].rstrip() + "…"
    return (PREAMBLE.replace("@FONT@", FONTS[look.font]).replace("@ACCENT@", look.accent.lstrip("#").upper())
            .replace("@SIZE@", f"{look.size:g}").replace("@LINE@", f"{round(look.size * 1.42, 1):g}")
            .replace("@TITLE@", _layout().tex(title)))


def _front(plan: Plan) -> list[str]:
    """The front page: a kicker, the title, the subtitle, the tagline (by what, when, which Heimdall); the sources
    (a table, each with when its document was written), flags, what was drawn for the report; the contents."""
    tex = _layout().tex
    lines = [r"\thispagestyle{front}", r"\hdKicker{Heimdall report}\par\vspace{8pt}", rf"\hdTitle{{{tex(plan.title)}}}"]
    if plan.subtitle:
        lines += [r"\vspace{5pt}", rf"\hdSubtitle{{{tex(plan.subtitle)}}}"]
    lines += [r"\vspace{8pt}", r"\hdTagline{Made by \texttt{heimdall report " + _breakable(plan.name) + "} " + BUILT + ".}",
              rf"\hdBlockTitle{{Sources}}{{{len(plan.sources)} result folder{'s' if len(plan.sources) != 1 else ''}}}",
              r"\begin{hdTable}{@{}r>{\raggedright\arraybackslash}p{64mm}>{\raggedright\arraybackslash}p{30mm}"
              r"rr>{\raggedright\arraybackslash}p{34mm}@{}}",
              r"\toprule", r" & \textbf{Source} & \textbf{Configuration} & \textbf{Points} & \textbf{Events} & \textbf{Compared against}\\",
              r"\midrule", r"\endhead", r"\bottomrule", r"\endfoot"]
    flags = []
    for number, source in enumerate(plan.sources, 1):
        f = source.facts()
        drawn = " · ".join(part for part in (f["written"][:16].replace("T", " "), f"Heimdall {f['heimdall']}" if f["heimdall"] else "") if part)
        lines.append(f"\\hdMuted{{{number}}} & \\texttt{{{_breakable(f['address'])}}}"
                     + (f"\\newline{{\\hdSmall\\color{{hdmuted}} {tex(drawn)}}}" if drawn else "")
                     + f" & {_breakable(f['configuration'] or source.doc.name)}"
                     + (f"\\newline{{\\hdSmall\\color{{hdmuted}} tag {tex(f['tag'])}}}" if f["tag"] else "")
                     + f" & {f['complete']}/{f['points']}"
                     + f" & {tex(f['events'] or '?')} & {tex(f['against'])}\\\\")
        if f["incomplete"]:
            shown = ", ".join(f["incomplete"][:6]) + (" …" if len(f["incomplete"]) > 6 else "")
            flags.append(f"\\texttt{{{_breakable(f['address'])}}}: {len(f['incomplete'])} of {f['points']} point(s) not "
                         f"complete ({_breakable(shown)}); its pages show the complete ones.")
        copied = any(fig.source is not None and fig.source.folder == source.folder and fig.file is not None
                     and fig.file.is_relative_to(source.folder) for s in plan.sections for g in s.grids for fig in g.figures)
        if f["stale"] and copied:
            flags.append(f"\\texttt{{{_breakable(f['address'])}}}: its points are newer than its pages; "
                         f"\\texttt{{heimdall plot {_breakable(f['address'])}}} redraws them.")
    lines.append(r"\end{hdTable}")
    if flags:
        lines += [r"\begin{hdFlags}", *(r"\item " + flag for flag in flags), r"\end{hdFlags}"]
    if plan.drawings:
        lines += [r"\hdBlockTitle{Drawn for this report}{into its cache, never into results/}", r"\begin{hdFacts}",
                  *(r"\item \texttt{" + _breakable(d.source.address) + "}" + _breakable(d.describe()[len(d.source.address):])
                    for d in plan.drawings), r"\end{hdFacts}"]
    if plan.look.contents:
        lines += [r"\vspace{20pt}", r"\hdKicker{Contents}\par\vspace{4pt}", r"\hdContents"]
    return lines + [r"\clearpage"]


def _literal(text: str) -> str:
    """Text for LaTeX as it is written ($ too), breakable after / and _ (a card's key or value)."""
    return _breakable(text.replace("$", "\0"))


#: A card's line read for highlighting (I-110 R4): `key = value` (Pythia, a context's options) or `key: value`
#: (YAML, at any depth, a list's `- ` before it), Herwig's commands, a number, a word, a comment after the value.
_KEYED = re.compile(r"(\s*(?:-\s+)?)([A-Za-z_][\w:.\-/\[\]]*)(\s*)(=|:(?=\s|$))(\s*)(.*)")
_COMMAND = re.compile(r"(\s*)(set|insert|create|cd|read|saverun|newdef|erase|do|get|mkdir|library)(\s.*|$)")
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
WORDS = ("on", "off", "true", "false", "yes", "no")
VERBATIM = {"\\": r"\hdBS{}", "{": r"\hdLB{}", "}": r"\hdRB{}"}


def _escaped(text: str) -> str:
    """Text for Verbatim[commandchars=\\\\\\{\\}]: its \\, { and } as the preamble's \\hdBS, \\hdLB and \\hdRB."""
    return "".join(VERBATIM.get(c, c) for c in text)


def _comment_at(line: str) -> int:
    """Where a line's comment starts: its first character that is not a space, on a comment line; else a ! or #
    after a space, outside quotes (Pythia's, YAML's); -1 when it has none."""
    stripped = line.lstrip()
    if stripped.startswith(COMMENTS):
        return len(line) - len(stripped)
    quote = ""
    for at, char in enumerate(line):
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "!#" and at and line[at - 1].isspace():
            return at
    return -1


def _word(text: str) -> str:
    """A value as it is highlighted: a number, a word (on, off, true, …), else as it is."""
    bare = text.strip()
    if _NUMBER.fullmatch(bare):
        return text.replace(bare, rf"\hdN{{{bare}}}", 1)
    if bare.lower() in WORDS:
        return text.replace(bare, rf"\hdB{{{bare}}}", 1)
    return _escaped(text)


def highlight(line: str) -> str:
    """A card's line for Verbatim[commandchars=\\\\\\{\\}] (I-110 R4): its key bold in the accent, `=` or `:` muted,
    a number or a word coloured, a comment muted italic; anything else as it is."""
    at = _comment_at(line)
    body, comment = (line[:at], line[at:]) if at >= 0 else (line, "")
    tail = "{\\hdC " + _escaped(comment) + "}" if comment else ""
    keyed = _KEYED.fullmatch(body)
    if keyed:
        lead, key, space, mark, after, value = keyed.groups()
        trailing = value[len(value.rstrip()):]
        return (_escaped(lead) + rf"\hdK{{{_escaped(key)}}}" + space + rf"\hdP{{{mark}}}" + after
                + (_word(value.rstrip()) if value.strip() else "") + trailing + tail)
    command = _COMMAND.fullmatch(body)
    if command:
        lead, word, rest = command.groups()
        parts = rest.rsplit(" ", 1)
        rest = _escaped(parts[0]) + " " + _word(parts[1]) if len(parts) == 2 and parts[1].strip() else _escaped(rest)
        return lead + rf"\hdB{{{word}}}" + rest + tail
    return _escaped(body) + tail


def _verbatim(lines: list[str]) -> list[str]:
    """Lines of a card, or of options, highlighted in a Verbatim."""
    return [r"\begin{Verbatim}[commandchars=\\\{\}]", *(highlight(line) for line in lines), r"\end{Verbatim}"]


def _given_tex(shown: Configs, out: Path) -> list[str]:
    """A tool's configuration in report.tex: its tag and source, its points and notes; its options alike and its
    card's baseline, highlighted (fvextra: long lines broken at spaces and after / _ : = , . -); then what varied:
    tables of at most KEYS_PER_TABLE keys, the points' column in each, or each point's lines."""
    tex, item = _layout().tex, shown.given
    lines = [r"\hdKeep{110bp}\phantomsection\addcontentsline{toc}{subsection}{" + tex(item.caption) + "}",
             rf"\hdBlockTitle{{{tex(item.tag)}}}{{\texttt{{{_breakable(item.source.address)}}} · {item.points()} complete point(s)}}"]
    if item.notes:
        lines += [r"\begin{hdFlags}", *(r"\item " + tex(note) for note in item.notes), r"\end{hdFlags}"]
    if item.options:
        lines += [r"\hdLabel{Options, alike in every point}{}", *_verbatim([f"{k} = {_value(v)}" for k, v in item.options.items()])]
    if shown.baseline is not None:
        rel = shown.baseline.relative_to(out).as_posix()
        lines += [r"\hdLabel{Its card, alike in every point}{" + _breakable(rel) + "}", *_verbatim(item.baseline)]
    if not any(own for _, _, own in item.varied):
        return lines + [r"\hdLabel{Nothing else varied from point to point}{}"]
    rel = shown.varied.relative_to(out).as_posix()
    lines.append(r"\hdLabel{What varied, point by point}{" + _breakable(rel) + "}")
    table = item.table()
    if table is None:
        for _, label, own in item.varied:
            if own:
                lines += [rf"{{\sffamily\hdSize{{8}}{{10}}\bfseries {tex(label)}\par}}\vspace{{2pt}}", *_verbatim(own)]
        return lines
    keys, rows = table
    for start in range(0, len(keys), KEYS_PER_TABLE):
        shown_keys = keys[start:start + KEYS_PER_TABLE]
        n = len(shown_keys)
        point = 110.0 if n > 2 else 160.0
        width = (TEXT_W - 10.0 * n - point - 5.0) / n
        spec = rf"@{{}}>{{\raggedright\arraybackslash}}p{{{point:.0f}bp}}" + \
            "".join(rf">{{\raggedright\arraybackslash\ttfamily}}p{{{width:.0f}bp}}" for _ in shown_keys)
        head = r"\textbf{Point} & " + " & ".join(r"\textbf{\texttt{" + _literal(k) + "}}" for k in shown_keys) + r"\\"
        lines += ([r"\hdBlockGap"] if start else []) + [
            rf"\begin{{hdTable}}{{{spec}}}", r"\toprule", head, r"\midrule", r"\endfirsthead",
            rf"\multicolumn{{{n + 1}}}{{@{{}}l}}{{\hdContinued}}\\", r"\toprule", head, r"\midrule", r"\endhead",
            r"\bottomrule", r"\endfoot",
            *(_breakable(label) + " & " + " & ".join(_literal(row[k]) if k in row else r"\hdMuted{—}" for k in shown_keys) + r"\\"
              for (_, label, _), row in zip(item.varied, rows)),
            r"\end{hdTable}"]
    return lines


def _unicode(texts: list[str]) -> list[str]:
    """Each character pdflatex would stop at (outside Latin-1, Latin Extended-A and SAFE): as its math when MATH
    knows it (χ, Δ, ≤, …), else as ?."""
    odd = sorted({c for text in texts for c in text if ord(c) >= 0x180 and c not in SAFE})
    return [f"\\DeclareUnicodeCharacter{{{ord(c):04X}}}{{" + (f"\\ensuremath{{{MATH[c]}}}" if c in MATH else "?") + "}"
            for c in odd]


def _head_tex(head: SetHead) -> list[str]:
    """A set's sub-header: its name and source, then its facts, a line each."""
    tex = _layout().tex
    facts = "".join(rf"\hdFact{{{what}}}{{" + r"\newline ".join(tex(line) for line in lines) + "}" for what, lines in head.facts)
    return [rf"\hdSetHead{{{tex(head.set)}}}{{{_breakable(head.address)}}}{{{facts}}}"]


def _grid_tex(grid: Placed, out: Path) -> list[str]:
    """A grid: its set's sub-header when it starts one, its caption, then its rows, a picture each (the sub-header,
    the caption and the first row kept on one page)."""
    layout = _layout()
    cw, ch, rows = _rows(grid)
    row_h = ch + grid.label
    lines = []
    head = 0.0
    if grid.head is not None:
        head = 50.0 + 13.0 * sum(len(lines_) for _, lines_ in grid.head.facts)
    lines.append(rf"\hdKeep{{{head + (15.0 if grid.caption else 0.0) + row_h + 4:.0f}bp}}")
    if grid.toc:
        lines.append(rf"\phantomsection\addcontentsline{{toc}}{{subsection}}{{{layout.tex(grid.toc)}}}")
    if grid.head is not None:
        lines += _head_tex(grid.head)
    if grid.caption:
        lines.append(rf"\hdCaption{{{layout.tex(grid.caption)}}}")
    for k, (start, end) in enumerate(rows):
        names = [f.relative_to(out).as_posix() for f in grid.files[start:end]]
        lines += ([rf"\par\vspace{{{GAP:g}bp}}"] if k else []) + [
            rf"\noindent\begin{{picture}}({TEXT_W:.2f},{row_h:.2f})",
            *layout.picture(names, grid.labels[start:end], (TEXT_W, row_h), grid.columns, 1, cw, ch, grid.label,
                            "", 0.0, GAP, grid.options[start:end], style=r"\hdPanel"),
            r"\end{picture}"]
    return lines + [r"\hdGridGap"]


def _typeset_tex(item: Typeset, out: Path) -> list[str]:
    """Statistics typeset: its title (in the contents) and where its numbers are, then its LaTeX."""
    tex = _layout().tex
    rel = [p.relative_to(out).as_posix() for p in item.data]
    where = rel[0] if len(rel) == 1 else f"{rel[0].rsplit('/', 1)[0]}/, a CSV a page" if rel else ""
    return [r"\hdKeep{120bp}\phantomsection\addcontentsline{toc}{subsection}{" + tex(item.toc or item.title) + "}",
            rf"\hdBlockTitle{{{_breakable(item.title)}}}{{{tex(item.tagline)}}}",
            *([r"\hdTagline{its numbers: \texttt{" + _breakable(where) + "}"
                + (r" · each statistic's formula and meaning: \hyperref[hd:method]{" + METHOD_TITLE
                   + r", page~\pageref*{hd:method}}" if item.refer else "") + r"}\vspace{2pt}"] if where else []),
            *item.lines, r"\hdGridGap"]


def _method_at(plan: Plan, placed: list) -> int:
    """Where How the numbers are made goes among the sections: right after what was run (the tools sections), which
    come first, or last with it."""
    return sum(1 for section, _ in placed if section.context) if plan.context == "first" else len(placed)


def _tex(plan: Plan, placed: list[tuple[Section, list]], method: Prose | None, out: Path) -> str:
    """report.tex, with BUILT for when and by what it was made: its preamble (the look), its front page, then
    each section on a new page, its note, its grids a row of panels at a time, each file named relative to the
    folder; How the numbers are made, unnumbered, after what was run (I-111)."""
    tex = _layout().tex
    lines = [r"\hypersetup{pdftitle={" + tex(plan.title) + "}}", r"\begin{document}", *_front(plan)]
    at = _method_at(plan, placed) if method else -1
    for number, (section, grids) in enumerate([*placed, (None, [])]):
        if number == at:
            lines += [r"\clearpage", rf"\section*{{{METHOD_TITLE}}}\markboth{{{METHOD_TITLE}}}{{}}",
                      rf"\phantomsection\label{{hd:method}}\addcontentsline{{toc}}{{section}}{{{METHOD_TITLE}}}", *method.lines]
        if section is None:
            break
        lines += [r"\clearpage", f"\\section{{{tex(section.title)}}}"]
        if section.note:
            lines.append(rf"\hdNote{{{tex(section.note)}}}")
        for grid in grids:
            lines += _given_tex(grid, out) if isinstance(grid, Configs) else _typeset_tex(grid, out) \
                if isinstance(grid, Typeset) else _grid_tex(grid, out)
    body = "\n".join([*lines, r"\end{document}", ""])
    return "\n".join([_preamble(plan), *_unicode([body, plan.title]), body])


def _highlight_html(line: str) -> str:
    """A card's line as index.html shows it: highlight's colours as spans."""
    marked = highlight(line)
    out, at = [], 0
    pattern = re.compile(r"\\hd(K|P|N|B)\{((?:[^{}]|\\hd(?:LB|RB|BS)\{\})*)\}|\{\\hdC (.*)\}$|\\hd(LB|RB|BS)\{\}")
    colours = {"K": "var(--accent-code)", "P": "var(--muted)", "N": "#0b6e4f", "B": "#7b3fb5"}
    for found in pattern.finditer(marked):
        out.append(html.escape(marked[at:found.start()]))
        if found[1]:
            inner = re.sub(r"\\hd(LB|RB|BS)\{\}", lambda m: {"LB": "{", "RB": "}", "BS": "\\"}[m[1]], found[2])
            weight = ";font-weight:600" if found[1] == "K" else ""
            out.append(f'<span style="color:{colours[found[1]]}{weight}">{html.escape(inner)}</span>')
        elif found[3] is not None:
            inner = re.sub(r"\\hd(LB|RB|BS)\{\}", lambda m: {"LB": "{", "RB": "}", "BS": "\\"}[m[1]], found[3])
            out.append(f'<span style="color:var(--muted);font-style:italic">{html.escape(inner)}</span>')
        else:
            out.append(html.escape({"LB": "{", "RB": "}", "BS": "\\"}[found[4]]))
        at = found.end()
    return "".join(out) + html.escape(marked[at:])


def _given_html(shown: Configs, out: Path, accent: str) -> str:
    """A tool's configuration as index.html shows it: its notes, its options, its baseline (highlighted) and what
    varied, as text."""
    item, esc = shown.given, html.escape
    link = lambda path: f'<a href="{esc(path.relative_to(out).as_posix(), quote=True)}">{esc(path.name)}</a>'   # noqa: E731
    code = lambda lines: (f'<pre style="--accent-code:{accent}">'                                            # noqa: E731
                          + "\n".join(_highlight_html(line) for line in lines) + "</pre>")
    parts = [f"<p>{item.points()} complete point(s)</p>", *(f"<p><em>{esc(note)}</em></p>" for note in item.notes)]
    if item.options:
        parts.append("<p>Its options, alike in every point:</p>" + code([f"{k} = {_value(v)}" for k, v in item.options.items()]))
    if shown.baseline is not None:
        parts.append(f"<p>Its card, alike in every point ({link(shown.baseline)}):</p>{code(item.baseline)}")
    if not any(own for _, _, own in item.varied):
        return "\n".join([*parts, "<p>Nothing else varied from point to point.</p>"])
    parts.append(f"<p>What varied, point by point ({link(shown.varied)}):</p>")
    table = item.table()
    if table is None:
        parts += [f"<p><strong>{esc(label)}</strong></p>{code(own)}" for _, label, own in item.varied if own]
    else:
        keys, rows = table
        parts.append("<table><tr><th>Point</th>" + "".join(f"<th><code>{esc(k)}</code></th>" for k in keys) + "</tr>"
                     + "".join(f"<tr><td>{esc(label)}</td>" + "".join(f"<td><code>{esc(row.get(k, '—'))}</code></td>" for k in keys)
                               + "</tr>" for (_, label, _), row in zip(item.varied, rows)) + "</table>")
    return "\n".join(parts)


def shown_text(label: str) -> str:
    """A label as index.html's titles show it, plain Unicode: its $…$ as the statistics' pages read them
    (webpage.text_of: `$k_T$` → kT, `$\\sqrt{s}$` → √s), tags dropped."""
    return html.unescape(re.sub(r"<[^>]+>", "", statstable.bars().webpage.text_of(label)))


def _index(plan: Plan, placed: list[tuple[Section, list]], method: Prose | None, out: Path) -> Path:
    """index.html (the viewer): a block a grid, its panels the PNGs, a set's facts under its first grid's title,
    and a block a tool's configuration, as text, How the numbers are made where the PDF has it; the sources and their
    summaries' pages up front."""
    blocks = []
    at = _method_at(plan, placed) if method else -1
    for number, (section, grids) in enumerate(placed, 1):
        if number - 1 == at:
            blocks.append(viewer.Shown("method", METHOD_TITLE, [], body=method.html))
        for k, grid in enumerate(grids, 1):
            if isinstance(grid, Configs):
                blocks.append(viewer.Shown(f"s{number:02d}-{k:03d}", f"{shown_text(section.title)}: {grid.given.caption}", [],
                                           body=_given_html(grid, out, plan.look.accent)))
                continue
            if isinstance(grid, Typeset):
                link = lambda path: (f'<a href="{html.escape(path.relative_to(out).as_posix(), quote=True)}">'   # noqa: E731
                                     f"{html.escape(path.name)}</a>")
                said = [f"<p>Typeset in <a href=\"report.pdf\">report.pdf</a>"
                        + (f"; as one page: {link(grid.page)}" if grid.page else "") + ".</p>",
                        "<p>Its numbers: " + ", ".join(link(p) for p in grid.data) + "</p>"]
                blocks.append(viewer.Shown(f"s{number:02d}-{k:03d}", f"{shown_text(section.title)}: {shown_text(grid.title)}", [],
                                           body="\n".join(said)))
                continue
            panels = [(label or (f"page {n}" if len(grid.pngs) > 1 else ""), png) for n, (label, png)
                      in enumerate(zip(grid.labels, grid.pngs), 1)]
            notes = [f"{what}: " + "; ".join(shown_text(line) for line in lines) for what, lines in grid.head.facts] if grid.head else []
            blocks.append(viewer.Shown(f"s{number:02d}-{k:03d}", f"{shown_text(section.title)}: {shown_text(grid.title)}", panels, notes))
    if at == len(placed):
        blocks.append(viewer.Shown("method", METHOD_TITLE, [], body=method.html))
    summaries = {p.name: p for p in sorted((out / STATS / "summaries").glob("*.html"))} if (out / STATS / "summaries").is_dir() else {}
    rows = []
    for source in plan.sources:
        f = source.facts()
        links = [f'<a href="{STATS}/summaries/{html.escape(n, quote=True)}">{html.escape(n.split("__", 1)[1][:-5])}</a>'
                 for n in summaries if n.startswith(slug(source.address) + "__")]
        tagged = f" [{html.escape(f['tag'])}]" if f["tag"] else ""
        rows.append(f"<tr><td><code>{html.escape(f['address'])}</code></td><td>{html.escape(f['configuration'])}{tagged}</td>"
                    f"<td>{f['complete']}/{f['points']}</td><td>{html.escape(f['events'])}</td><td>{html.escape(f['against'])}</td>"
                    f"<td>{' · '.join(links)}</td></tr>")
    front = ('    <header><h2>Sources</h2><span class="more"><a href="report.pdf">report.pdf</a></span></header>\n'
             '    <table><tr><th>Source</th><th>Configuration</th><th>Points</th><th>Events</th><th>Compared against</th>'
             '<th>Statistics summary</th></tr>\n    ' + "\n    ".join(rows) + "\n    </table>")
    return viewer.page(out / "index.html", plan.title, blocks, front)


def drawings_root(plan: Plan) -> Path:
    """Where a report's drawings go (P6): .cache/<P>/reports/<its place under reports/, the project's folder
    left out>/.drawn/ (a report built elsewhere: …/reports/elsewhere/<its path's hash>/.drawn/)."""
    project = plan.sources[0].project if plan.sources else "report"
    out, root = plan.out.resolve(), reports_root().resolve()
    if out.is_relative_to(root) and out != root:
        rel = out.relative_to(root).parts
        place = Path(*rel[1:]) if rel[0] == project else Path(*rel)
    else:
        place = Path("elsewhere") / _key(str(out))[:12]
    return cache_root() / project / "reports" / place / ".drawn"


def _drawing_name(drawing: Drawing) -> str:
    name = slug(drawing.source.address)
    if len(name) > 80:
        name = f"{slug(drawing.source.folder.name)}-{_key(str(drawing.source.folder))[:8]}"
    return name + (f"-{_key(json.dumps(drawing.look, sort_keys=True))[:8]}" if drawing.look else "")


def _stat(path: Path | None) -> str:
    try:
        info = path.stat()
        return f"{info.st_size}:{info.st_mtime_ns}"
    except (AttributeError, OSError):
        return "-"


def _drawing_code() -> list[str]:
    """What a drawing is drawn by: Paint as built, the plot stage's code and the backends'."""
    framework = heimdall_root() / "framework"
    files = [framework / "runner" / "plot.py", framework / "runner" / "labels.py",
             *sorted((framework / "plot").rglob("*.py")), *sorted((framework / "plot").rglob("*.toml"))]
    return [_stat(apps_dir() / "Paint.exe"), *(_sha(f) for f in files if f.is_file())]


def _draw_for(plan: Plan, say) -> None:
    """Each drawing the report asks for (P6): the source's plot document loaded with its outputs sent to the
    drawing's folders, its [plot] with the look over it, drawing only the sets wanted, in pdf and png, its compare,
    sheet and statistic figures left out (the report shows a run's compare pages as drawn); its pages drawn
    (plot.draw, no numbers), then the sets' numbers measured (plot.measure). Drawn again only when its document,
    its points' YODAs, the look, the sets or the drawing's code changed (its stamp, drawn.key); a drawing no section
    asks for any more is removed. The source's results/ and records/ are only read."""
    root = drawings_root(plan)
    code = _drawing_code() if plan.drawings else []
    for drawing in plan.drawings:
        source = drawing.source
        drawing.folder = folder = root / _drawing_name(drawing)
        folders = RunFolders(source.project, folder / "records", folder / "results", folder / "work")
        doc, configuration, members = plotdoc.load(source.folder / plotdoc.FILE, folders=folders)
        settings = looked(doc.plot or {}, drawing.look)
        wanted = [*drawing.sets, *drawing.measured]
        if "sets" in settings and TOTALITY in wanted and TOTALITY not in named_sets(settings["sets"]):
            settings["sets"] = {TOTALITY: totality(configuration, members), **named_sets(settings["sets"])}
        figures = {k: t for k, t in (settings.get("figures") or {}).items()
                   if not isinstance(t, dict) or t.get("class") not in ("compare", "sheet", "statistic")}
        settings = {**{k: v for k, v in settings.items() if k not in ("figures", "draw")}, **({"figures": figures} if figures else {}),
                    "formats": ["pdf", "png"]}
        if drawing.backends:
            settings["backend"] = list(dict.fromkeys([*plotting.backends(settings), *drawing.backends]))
        doc.plot = settings
        doc.stats = {k: v for k, v in (doc.stats or {}).items() if k not in drawing.look}
        key = _key(_sha(source.folder / plotdoc.FILE), json.dumps([settings, doc.stats], sort_keys=True, default=str),
                   *drawing.sets, "|", *drawing.measured,
                   *(f"{m.point.name}:{m.recorded}:{_stat(m.yoda)}" for m in members), *code)
        stamp = folder / "drawn.key"
        if stamp.is_file() and stamp.read_text(encoding="utf-8") == key and drawing.results.is_dir():
            continue
        stamp.unlink(missing_ok=True)
        shutil.rmtree(drawing.results, ignore_errors=True)
        say(f"report: drawing {drawing.describe()}")
        plotting.validate(doc)
        failed = 0
        if drawing.sets:
            doc.plot = {**settings, "draw": list(drawing.sets)}
            plotting.check_figures(doc, configuration)
            plotting.check_texts(doc, members)
            failed += plotting.draw(doc, configuration, members, say, stats=False)
        if drawing.measured:
            doc.plot = settings
            plotting.check_figures(plotting.measured(doc, list(drawing.measured)), configuration)
            failed += plotting.measure(doc, configuration, members, say, picked=list(drawing.measured))
        drawing.failed = failed
        if failed:
            say(f"report: {failed} page(s) of {source.address} could not be drawn for the report: {drawing.logs}")
        else:
            stamp.write_text(key, encoding="utf-8")
    names = {_drawing_name(d) for d in plan.drawings}
    for old in (p for p in root.iterdir() if p.is_dir() and p.name not in names) if root.is_dir() else ():
        shutil.rmtree(old)


def _settle(plan: Plan) -> None:
    """Once drawn (P6): each section that waited for a drawing resolved again from what was drawn, and one that is
    optional and came to nothing left out, and said."""
    base = plan.recipe.parent if plan.recipe else Path.cwd()
    kept = []
    for section in plan.sections:
        if section.waiting():
            section, why = _section(section.spec, section.found, section.at, base, plan.drawings)
            if section is None:
                plan.left.append(why)
                continue
        kept.append(section)
    plan.sections = kept


def _pages_of(pdf: Path) -> int:
    try:
        done = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return 0
    found = re.search(r"^Pages:\s+(\d+)", done.stdout, re.M)
    return int(found[1]) if found else 0


def build(plan: Plan, say=print) -> list[Path]:
    """The report, into plan.out (I-108 P3, P6): first what it draws for itself, into its cache (_draw_for); then
    figures/ (each figure copied as drawn, its PNG beside it), stats/ (the chosen statistics and bar graphs, drawn
    from each source's statistics.csv, or the numbers measured for it), report.tex (A4, naming only files in the
    folder), report.pdf (pdflatex, twice: the contents) and index.html. Only what changed is copied or drawn again
    (`.stamps.json`, a drawing's drawn.key), and what no section holds any more is removed. The files made."""
    out = plan.out
    for place in (results_root(), *(s.folder for s in plan.sources)):
        if out.resolve().is_relative_to(Path(place).resolve()):
            raise HeimdallError(f"a report is never built into results/: {out}", hint="leave -o out (reports/ mirrors results/), or name another folder")
    _draw_for(plan, say)
    _settle(plan)
    if plan.drawn():
        raise HeimdallError(f"{len(plan.drawn())} figure(s) or part(s) were not drawn for the report", where=str(drawings_root(plan)),
                       hint="the lines above say why")
    out.mkdir(parents=True, exist_ok=True)
    books = _Build(out)
    placed, method = _place(books, plan, say)
    books.prune()
    figures = sum(len(g.figures) for s in plan.sections for g in s.grids)
    tools = sum(len(s.given) for s in plan.sections)
    say(f"report: {figures} figure(s)" + (f" ({books.data} with their data, a CSV each)" if books.data else "")
        + f", {books.copied} file(s) copied or written; "
        f"{sum(len(s.parts) + len(s.bars) for s in plan.sections)} statistics part(s), {books.drawn} drawn"
        + (f"; {tools} tool configuration(s)" if tools else ""))
    text = _tex(plan, placed, method, out)
    key = _key(text, *(f"{rel}:{sha}" for rel, sha in sorted(books.shas.items())))
    source, pdf = out / "report.tex", out / "report.pdf"
    made = [source, out / "index.html"]
    stamp = books.old.get("report.pdf")
    revision = record.git_state(heimdall_root()).get("revision", "")[:12]
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
                raise HeimdallError(str(error), where=str(source), hint=f"pdflatex's log: {source.with_suffix('.log')}") from None
            for suffix in LEFTOVERS:
                source.with_suffix(suffix).unlink(missing_ok=True)
            books.new["report.pdf"] = {"key": key}
            say(f"report: report.pdf, {_pages_of(pdf)} A4 page(s)")
            made.insert(0, pdf)
        else:
            say("report: no pdflatex on PATH, so no report.pdf: report.tex compiles anywhere else as it is (Overleaf)")
    _index(plan, placed, method, out)
    books.save()
    for why in plan.left:
        say(f"report: left out: {why}")
    say(f"report: {', '.join(p.name for p in made)} in {out}")
    return made
