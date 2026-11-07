"""The plot stage: one page per `plot_points` cell and object, drawn by Paint (rank 4).

doc:plots, doc:paint. After the points, from the complete ones:

* the objects are the 1D objects of the points' YODA product (not /RAW, /TMP or the run counters),
  narrowed by [plot].objects globs;
* the sweep is merged into one ROOT file, results/…/plots/root/<configuration>.root: a directory
  per point, raw entries included (so Paint can void by min_entries) and points.json inside. It is
  rebuilt only when a point's YODA changes, and it is what the pages read;
* titles and axis labels come from the analysis's Rivet .plot file (one label source, v1's D9), under
  a figure's own ([plot.figures.<figure>], V80); every text is LaTeX (V65), and may cite the points (V66):
  {cell}, {q:<quantity>} (a value's label), and what the tools' folders give ({opt:ETMIN}: Rivet's);
* reference data are drawn only through the explicit [plot.data].map (L18);
* one Paint config per page, records/…/plots/[<page>/]<object>.toml, drawn to
  results/…/plots/root/[<page>/]<object>.<fmt>; the mpl backend writes results/…/plots/mpl/, and
  backend = ["root", "mpl"] writes both from the same pages;
* the style is src/Apps/Paint/base.toml, which Paint reads itself; a page's [style] holds only
  what is changed over it: the machine root's style.toml, the work dir's style.toml, the
  [plot].root_style file, then [plot.style], then its figure's style, each checked against base.toml's
  keys and types.
"""

from __future__ import annotations

import contextvars
import fnmatch
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

import tomli_w

from . import hepfiles, plugins, schema, statstable
from .errors import HeimdallError, did_you_mean
from .labels import canonical, labels_of, lines_of, macros, root_text, tlatex  # noqa: F401 (tlatex et al. re-exported)
from .paths import apps_dir, cache_root, heimdall_root, log_settings, resolve, results_root
from .record import check_format, manifest_file, recorded_identity
from .status import clean_text, digest
from .statstable import STATISTIC_COLUMNS, heading_of, statistics_of, write_statistics  # noqa: F401 (re-exported)
from .tools import merge_files, run_folders, sha256_file
from .sweep import (Group, Listed, axes, check_set, chosen_points, group_key, group_labels, group_tag, label_of, set_cells,
                    set_entries, split_axes, tag_of)

BACKENDS = tuple(schema.keys("plot")["backend"]["choices"])
FORMATS = tuple(schema.keys("plot")["formats"]["choices"])
LEGENDS = ("top-right", "top-left", "bottom-right", "bottom-left", "best", "out-right", "out-left", "out-top", "out-bottom")
#: The legend's places outside the frame (V185), which Paint and mpl draw and mkhtml cannot.
OUTSIDE = ("out-right", "out-left", "out-top", "out-bottom")
#: Above the frame: the main title and the corners; the legend's first line (V51). [plot] sets them for
#: every page, a figure ([plot.figures.<figure>]) for its own: it inherits [plot]'s value and may
#: override it, and a key means the same at both levels.
TITLE_KEYS = ("title", "title_left", "title_right", "legend_header")
DEFAULT = schema.DEFAULT  # "keep it as it is" (V55): a child's is its parent's; [plot]'s sets nothing
PLACEHOLDER = re.compile(r"\{(cell|[a-z]+:[A-Za-z0-9_.:+-]+)\}")    # V66; a LaTeX group never has the colon


def formats_of(settings: dict) -> list[str]:
    """[plot].formats; "default" is Paint's own, pdf (mkhtml writes pdf and png whatever it is given)."""
    value = settings.get("formats", schema.default("plot", "formats"))
    return ["pdf"] if value == DEFAULT else list(value)
STYLE_CHOICES = {"page.font": ("serif", "sans", "mono"), "curves.errors": ("bars", "band", "none"),
                 "legend.position": LEGENDS}
COUNTERS = hepfiles.COUNTERS
#: Pages per Paint process (V64): ROOT starts once per batch, and argv stays short.
PAINT_BATCH = 200


@dataclass
class Page:
    name: str            # "<set>/<cell>/<object>" (V164), unique in a drawing; "<cell>/<object>" with no set
    config: Path         # the Paint config
    output: Path         # without extension: <root>/root/<rel>
    cell: str = ""       # the cell within its set: the plot_points tags, a set's page axes' tags; "" with one
    object: str = ""     # the YODA path without analysis options: what the page is of
    document: dict = field(default_factory=dict)    # the Paint config, as written
    sources: list = field(default_factory=list)     # each curve's YODA …
    variants: list = field(default_factory=list)    # … and its object there (options included)
    data: tuple | None = None                       # (reference YODA, its object path)
    overrides: set = field(default_factory=set)     # the keys its figure set
    ranges: dict = field(default_factory=dict)      # Paint --dump-ranges, for other backends
    style: dict = field(default_factory=dict)       # base.toml with the page's [style] over it
    overlay: str = ""                                # an overlay figure's name: curves are several objects (V51)
    bands: list = field(default_factory=list)        # per curve: its band members' (YODA, object), V69
    statistic: str = ""                              # legend_statistic: the number after each curve's entry (V160) …
    plain: list = field(default_factory=list)        # … and the curves' labels without it
    set: str = ""                                    # its set (V164): totality, a [plot].sets entry; "" none (compare)
    rel: str = ""                                    # its name within its set: "<cell>/<object>"
    root: Path | None = None                         # its set's folder: <root>/<backend>/<rel> (plots/<set>, compare/<name>)
    numbers: Path | None = None                      # its set's statistics folder (statistics/<set>)
    merged: dict = field(default_factory=dict)       # a set's merged curves on it: {curve name: the points it is made of}
    runs: dict = field(default_factory=dict)         # across: each curve's Run as it is named, {curve name: "03·nlo"}


@dataclass(frozen=True)
class Figure:
    """A recipe for pages (V80): [plot.figures.<key>]."""
    key: str
    kind: str                # its class: defined, overlay, merged, compare, derived, scan, sheet
    type: str                # what is drawn; "" from the objects
    name: str                # its pages' file stem (an overlay's; a defined figure's pages are the objects')
    objects: tuple           # globs
    labels: tuple            # an overlay's, one per object
    table: dict              # what it sets for its pages: [plot]'s page keys, x_label, y_label, style
    where: str
    over: tuple = ()         # a merged figure's: the axes it merges (V82)
    configurations: tuple = ()   # a compare figure's (V83); () under sweep_runs: its configurations
    op: str = ""             # a derived figure's (V84)
    x: str = ""              # a scan figure's quantity … (V85)
    y: str = ""              # … and the number it reads of each point
    table_pages: tuple = ()  # a sheet's page globs … (V89)
    columns: int = 0         # … and its columns
    statistic: str = ""      # a statistic figure's number … (V160)
    sort: bool = False       # … best first


def figures(errand) -> list[Figure]:
    """The declared figures, in file order. The implicit one, [plot].objects as defined pages, is pages()'."""
    from .config import figure_tables
    out = []
    for key, (table, written) in figure_tables(errand.plot or {}).items():
        out.append(Figure(key, table.get("class", "defined"), table.get("type", ""), table.get("name", key),
                          tuple(table.get("objects", ())), tuple(table.get("labels", ())),
                          {k: v for k, v in table.items() if k not in schema.FIGURE_OWN}, f"{errand.path}: {written}",
                          tuple(table.get("over", ())), tuple(table.get("configurations", ())), table.get("op", ""),
                          table.get("x", ""), table.get("y", ""), tuple(table.get("pages", ())), table.get("columns", 0),
                          table.get("statistic", ""), bool(table.get("sort", False))))
    return out


def _matches(path: str, glob: str, fulls=()) -> bool:
    """An object glob against the short name (d01-x01-y01), the option-free path, or any variant's path."""
    return (fnmatch.fnmatch(path.rsplit("/", 1)[-1], glob) or fnmatch.fnmatch(path, glob)
            or any(fnmatch.fnmatch(f, glob) for f in fulls))


def backend(name: str):
    """A backend other than Paint: framework/plot/<name>/backend.py, with validate(settings) and
    draw(cells, settings, say) -> failed pages."""
    path = heimdall_root() / "framework" / "plot" / name / "backend.py"
    if not path.is_file():
        raise HeimdallError(f"no plot backend '{name}'", hint=f"expected {path}")
    return plugins.load(path, "backend")


def backends(settings: dict) -> list[str]:
    """[plot].backend: a name or a list of names. Paint's first when drawn."""
    value = settings.get("backend", "root")
    value = "root" if value == DEFAULT else value
    names = [value] if isinstance(value, str) else list(value)
    return sorted(dict.fromkeys(names), key=lambda n: n != "root")


def validate(errand) -> None:
    """What [plot] needs beyond the schema (config.check_plot has every key, type and bound): the style
    layers against base.toml, the backends' own limits, and [plot.data]'s file and map together. Keys
    a backend cannot honour are errors at plan time, never dropped (v1's LegendXPos)."""
    settings = errand.plot
    where = f"{errand.path}: [plot]"
    names = backends(settings)
    if not names:
        raise HeimdallError("[plot].backend names no backend", where=f"{where}.backend", hint='"root", "mpl" or both in a list')
    errand_style(errand)
    for figure in figures(errand):
        check_style(figure.table.get("style", {}), f"{figure.where}.style")
    for name in names[1:] if names[0] == "root" else names:
        backend(name).validate(settings, beside_root=names[0] == "root",
                               curve_styles=[s for q in errand.quantities.values() for s in q.styles])
    data = settings.get("data", {})
    if data and not data.get("map"):
        raise HeimdallError("[plot.data] names a file but no map", where=f"{where}.data",
                       hint='reference data are matched only through an explicit map, "d01-x01-y01" = "/REF/…/d01-x01-y01"')
    if data and "file" not in data:
        raise HeimdallError("[plot.data] has a map but no file", where=f"{where}.data")


# ── the style: src/Apps/Paint/base.toml and the layers over it ─────────────────────────────

def base_style() -> dict:
    """src/Apps/Paint/base.toml: every style key, with its default. Paint reads the same file."""
    path = heimdall_root() / "src" / "Apps" / "Paint" / "base.toml"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HeimdallError(f"cannot read the base style: {error}", where=str(path)) from None


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check_style(layer: dict, where: str, base: dict | None = None, at: str = "") -> None:
    """A style layer names only keys base.toml has, each a value of the same kind: a number for a
    number, a pair for a pair, a list for the palette. legend.position is a corner or [x, y]."""
    base = base_style() if base is None else base
    for key, value in layer.items():
        name = f"{at}.{key}" if at else key
        if key in base and value == DEFAULT:        # set nothing: the layer below, at last base.toml, decides
            continue
        if key not in base:
            raise HeimdallError(f"the style has no key '{name}'", where=where,
                           hint=did_you_mean(key, list(base)) or f"src/Apps/Paint/base.toml has: {', '.join(base)}")
        mine = base[key]
        if isinstance(mine, dict) or isinstance(value, dict):
            if not (isinstance(mine, dict) and isinstance(value, dict)):
                raise HeimdallError(f"style '{name}' must be {'a table' if isinstance(mine, dict) else 'a value'}", where=where)
            check_style(value, where, mine, name)
            continue
        if name == "legend.position" and isinstance(value, list):
            ok = len(value) == 2 and all(_number(v) for v in value)
        elif _number(mine):
            ok = _number(value)
        elif isinstance(mine, list):
            ok = isinstance(value, list) and bool(value) and (
                len(value) == len(mine) and all(_number(v) for v in value) if all(_number(v) for v in mine)
                else all(isinstance(v, (str, int)) and not isinstance(v, bool) for v in value))
        else:
            ok = type(value) is type(mine)
        if not ok:
            raise HeimdallError(f"style '{name}' = {value!r} is not of the kind base.toml gives it ({mine!r})", where=where)
        if name in STYLE_CHOICES and isinstance(value, str) and value not in STYLE_CHOICES[name]:
            raise HeimdallError(f"style '{name}' must be one of {', '.join(STYLE_CHOICES[name])}, not '{value}'", where=where)


def merge_style(*layers: dict) -> dict:
    """Later layers win, key by key, into nested tables; a "default" value sets nothing."""
    out: dict = {}
    for layer in layers:
        for key, value in layer.items():
            if value == DEFAULT:
                continue
            out[key] = merge_style(out.get(key, {}), value) if isinstance(value, dict) else value
    return out


def style_file(value: str, assignment: str = "", where: str = "", folder: Path | None = None) -> dict:
    """A style layer from a file: [plot].root_style (beside the errand file, `folder`; configs/<A>/… without one),
    or `heimdall plot --style`."""
    path = (resolve(value, "root_style", assignment=assignment, folder=folder, where=where) if assignment or folder
            else Path(value).resolve())
    if path.suffix != ".toml":
        path = path.with_name(path.name + ".toml")
    try:
        layer = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise HeimdallError(f"no style file {path}", where=where or str(path)) from None
    except tomllib.TOMLDecodeError as error:
        raise HeimdallError(f"cannot parse the style file: {error}", where=str(path)) from None
    check_style(layer, str(path))
    return layer


def house_style() -> dict:
    """The style's layers over base.toml that are not a run's: the machine root's style.toml (every work
    dir's on this machine), then the work dir's style.toml (its studies'), each checked."""
    from .paths import find_work, machine_root
    layers = []
    for path in (machine_root() / "style.toml", *([find_work() / "style.toml"] if find_work() else [])):
        if path.is_file():
            try:
                layer = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as error:
                raise HeimdallError(f"cannot parse the style file: {error}", where=str(path)) from None
            check_style(layer, str(path))
            layers.append(layer)
    return merge_style(*layers)


def errand_style(errand) -> dict:
    """What a run changes of the base style: the machine's and the work dir's style.toml, its root_style
    file, then [plot.style]."""
    settings = errand.plot
    where = f"{errand.path}: [plot]"
    named = settings.get("root_style", DEFAULT)
    layer = style_file(named, errand.assignment, f"{where}.root_style", getattr(errand, "folder", None)) if named != DEFAULT else {}
    check_style(settings.get("style", {}), f"{where}.style")
    return merge_style(house_style(), layer, settings.get("style", {}))


# ── the page document as Paint reads it ──────────────────────────────────────────────────────

def for_root(document: dict) -> dict:
    """The page document Paint reads: every label through root_text (the in-memory document keeps the
    labels as written, which the mpl backend converts its own way)."""
    out = {**document, "page": {k: tlatex(v) if k in (*TITLE_KEYS, "x_label", "y_label") and isinstance(v, str) else v
                                for k, v in document["page"].items()},
           "curve": [{**c, "label": tlatex(c["label"])} for c in document["curve"]]}
    if "data" in document:
        out["data"] = {**document["data"], "label": tlatex(document["data"]["label"])}
    return out



# ── inputs ───────────────────────────────────────────────────────────────────────────────────

def root_name(path: str) -> str:
    """The object's name in App_yd2rt's file: /photo_eic:R=0.4/d01-x01-y01 → photo_eic__R-0.4/d01-x01-y01."""
    return path.lstrip("/").replace(":", "__").replace("=", "-").replace(" ", "_")


base_of = hepfiles.base_path


def objects_of(yoda: Path) -> list[str]:
    """The 1D objects of a YODA file that get pages (hepfiles.objects: .gz too)."""
    return hepfiles.objects(yoda)


def raws_of(yoda: Path) -> set[str]:
    """The /RAW Histo1D twins a YODA file has, whose entries App_yd2rt keeps (hepfiles.raw_twins)."""
    return hepfiles.raw_twins(yoda)


def _sha(path: Path) -> str:
    return sha256_file(path)


#: Where a drawing's failures are logged (V204): records/<A>/<E>/<R>/logs/plot/, set by draw() and measure() for the
#: drawing under way (a ContextVar: a pipelined sweep's runs draw on threads of their own).
_LOGS: contextvars.ContextVar = contextvars.ContextVar("plot_logs", default=None)


def logs_of(plans) -> Path | None:
    """A drawing's log folder: its configuration's records/<A>/<E>/<R>/logs/plot/ (None without one)."""
    first = next(iter(plans or []), None)
    folders = getattr(first, "folders", None)
    return folders.logs / "plot" if folders is not None else None


def failure_log(name: str, text: str, header: dict, append: bool = False) -> Path | None:
    """A failed program's output, cleaned and digested (V204), as `name`.log in the drawing's log folder; None
    when no drawing is under way (heimdall plot FILE)."""
    folder = _LOGS.get()
    if folder is None:
        return None
    lines = clean_text(text).rstrip("\n").split("\n")
    numbered = list(enumerate(lines, 1))
    settings = log_settings()
    path = folder / (re.sub(r"[^A-Za-z0-9_.-]+", "_", name) + ".log")
    path.parent.mkdir(parents=True, exist_ok=True)
    said = digest(numbered[:settings["head"]], numbered[-settings["tail"]:] if settings["tail"] else [],
                  [(n, line) for n, line in numbered if re.search(r"\b(?:Error|ERROR|error)\b", line)][:500],
                  0, len(lines), 0, header)
    with open(path, "a" if append else "w", encoding="utf-8") as handle:
        handle.write(said)
    return path


def convert(yoda: Path, target: Path) -> Path:
    """App_yd2rt --keep-raw, once per content: the stamp beside the target holds the YODA's sha256."""
    stamp = target.with_name(target.name + ".sha256")
    digest = _sha(yoda)
    if target.exists() and stamp.exists() and stamp.read_text(encoding="utf-8").strip() == digest:
        return target
    app = apps_dir() / "App_yd2rt.exe"
    if not app.exists():
        raise HeimdallError(f"{app} is not built", hint="heimdall build --framework")
    target.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([str(app), str(yoda), str(target), "--keep-raw"], capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        log = failure_log(f"convert-{yoda.stem}", done.stdout + done.stderr, {"tag": "App_yd2rt", "yoda": str(yoda),
                                                                             "exit": done.returncode})
        raise HeimdallError(f"converting {yoda.name} failed: {done.stderr.strip()[-300:]}"
                       + (f" (its output: {log})" if log else ""), where=str(log or yoda))
    stamp.write_text(digest + "\n", encoding="utf-8")
    return target


def data_source(name: str, errand) -> Path:
    """[plot.data].file: `rivet:<Analysis>` is Rivet's own reference file (its data directory, or
    build/Rivet for ours), which every installation has; anything else is under datasets/."""
    if name.startswith("rivet:"):
        analysis = name.split(":", 1)[1]
        places = hepfiles.rivet_dirs()
        for place in places:
            for candidate in (place / f"{analysis}.yoda", place / f"{analysis}.yoda.gz"):
                if candidate.is_file():
                    return candidate
        raise HeimdallError(f"Rivet has no reference data for {analysis}", where=f"{errand.path}: [plot.data].file",
                       hint=f"looked for {analysis}.yoda[.gz] in {', '.join(map(str, places))}")
    source = resolve(name, "data", assignment=errand.assignment, where=f"{errand.path}: [plot.data].file")
    if not source.is_file():
        from .paths import dataset_listed
        raise HeimdallError("the reference data file does not exist", where=str(source),
                       hint="datasets.toml lists it: `heimdall setup .` fetches it" if dataset_listed(source) else
                       "put it in datasets/ (tracked), or list it in datasets.toml (url, sha256) for heimdall setup to fetch; "
                       "`rivet:<Analysis>` names Rivet's own reference data")
    return source


def merge(sources: dict[str, Path], target: Path, stamp: Path, points: Path | None = None) -> Path:
    """App_yd2rt --merge: every point's YODA into one ROOT file, a directory per point. Rebuilt only
    when a point's YODA changed (the stamp holds each name and sha256)."""
    digest = "\n".join(f"{name} {_sha(path)}" for name, path in sources.items())
    if target.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == digest:
        return target
    app = apps_dir() / "App_yd2rt.exe"
    if not app.exists():
        raise HeimdallError(f"{app} is not built", hint="heimdall build --framework")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.stem + ".partial" + target.suffix)
    argv = [str(app), "--merge", str(partial), *(f"{name}={path}" for name, path in sources.items()), "--keep-raw"]
    if points is not None and points.is_file():
        argv += ["--points", str(points)]
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        log = failure_log(f"merge-{target.stem}", done.stdout + done.stderr, {"tag": "App_yd2rt --merge",
                                                                             "exit": done.returncode})
        raise HeimdallError(f"merging the sweep failed: {done.stderr.strip()[-300:]}" + (f" (its output: {log})" if log else ""),
                       where=str(log or target))
    partial.replace(target)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(digest, encoding="utf-8")
    return target


# ── what a page draws: points, as planned or as recorded (V158) ─────────────────────────────────

@dataclass
class Member:
    """A point (or combined group) the plot stage draws from its record, with no tool planned (V158): what
    a plan gives a page, read from the configuration's points.json and the point's records."""
    point: object                      # sweep.Point: its name and choice
    values: dict                       # each active quantity's value index, swept or fixed
    folders: object                    # tools.RunFolders
    yoda: Path | None                  # its YODA product
    texts: dict = field(default_factory=dict)       # what its tools' folders give page texts ({opt:…})
    context: dict = field(default_factory=dict)
    identity: str = ""                 # the identity points.json says it ran with …
    recorded: str | None = None        # … and the one its .complete holds (None: not complete)


def recorded(errand, configuration) -> list[Member]:
    """A configuration's points as its record has them: points.json's (every point the run planned), the run
    (the record's snapshot) giving their quantities; combined groups (`combine`) in their place. Each is
    complete when its .complete holds the identity points.json names."""
    from . import quantities as qmod
    from .sweep import points as sweep_points
    here = run_folders(errand, configuration)
    if not here.manifest.is_file():
        raise HeimdallError("this configuration has no record yet", where=str(here.manifest), hint="heimdall run it first")
    manifest = json.loads(here.manifest.read_text(encoding="utf-8"))
    check_format(manifest, here.manifest)
    entries = manifest.get("points", [])
    made = {p.name: p for p in sweep_points(errand, configuration)}
    static = qmod.static_values(errand, configuration)

    def marker(name: str) -> str | None:
        path = here.points / name / ".complete"
        return path.read_text(encoding="utf-8").strip() if path.is_file() else None

    out = []
    for entry in entries:
        point = made.get(entry.get("name"))
        if point is None:                      # not a point this configuration makes (an edited snapshot)
            continue
        yoda = next((Path(p) for p in entry.get("products", {}).values() if str(p).endswith(".yoda")), None)
        out.append(Member(point, {**static, **point.choice}, here, yoda, dict(entry.get("texts", {})), {},
                          entry.get("identity", ""), marker(point.name)))
    if not configuration.combine:
        return out
    combined = set(configuration.combine)                # post.plan_combined's groups, named as it names them
    kept = [n for entry in configuration.sweeps for n in (entry if isinstance(entry, list) else [entry]) if n not in combined]
    groups: dict[tuple, list] = {}
    for m in out:
        groups.setdefault(tuple(m.point.choice.get(n, -1) for n in kept), []).append(m)
    merged = []
    for number, (key, members) in enumerate(groups.items(), start=1):
        choice = {q: i for q, i in zip(kept, key) if i != -1}
        name = "_".join(tag_of(errand.quantities[q], choice[q]) for q in kept if q in choice and not errand.quantities[q].silent) or "combined"
        first = members[0]
        point = replace(first.point, index=number, name=name, choice=choice, stage="combined")
        group = here.products / name / first.yoda.name if first.yoda else None
        state = marker(name)
        merged.append(Member(point, {**static, **choice}, here, group, first.texts, {}, state or "", state))
    return merged


def drawable(members: list) -> tuple[list, list]:
    """The members a page draws, and those of them that ran with other inputs than their plan has now (V158):
    a member is drawn when its record is complete (a .complete there) and its YODA is on disk, whatever the
    config says today (a changed card, a rebuilt stack, a value left out). A record's member is drawn when
    its .complete holds the identity its points.json names."""
    drawn, other = [], []
    for m in members:
        if isinstance(m, Member):
            if m.recorded is not None and m.recorded == m.identity and m.yoda is not None and m.yoda.is_file():
                drawn.append(m)
                if m.context.get("planned") not in (None, m.identity):    # a document's: its plan now differs (V165)
                    other.append(m)
            continue
        made, yoda = recorded_identity(m), yoda_of(m)
        if made is not None and yoda is not None and yoda.is_file():
            drawn.append(m)
            if made != m.identity:
                other.append(m)
    return drawn, other


def yoda_of(plan) -> Path | None:
    if isinstance(plan, Member):
        return plan.yoda
    for interface in plan.interfaces.values():
        if interface.kind == "product" and not interface.shard and interface.path.suffix == ".yoda":
            return interface.path
    return None


# ── pages ────────────────────────────────────────────────────────────────────────────────────

def page_keys(keys: dict) -> dict:
    """A set's keys that lay over [plot]'s for its pages (V163): its objects choose its pages, its style is
    the page style's layer."""
    return {k: v for k, v in keys.items() if k not in ("objects", "style")}


RANGES = ("x_range", "y_range")


def layered(below: dict, above: dict) -> dict:
    """`above`'s page keys over `below`'s (a set's over [plot]'s, V163), a range's ends each over its own:
    `"default"` at one end is the layer below's end (V131)."""
    out = {**below, **above}
    for name in RANGES:
        if name in above:
            out[name] = endpoints(name, (above, below))
    return out


def endpoints(name: str, tables: tuple) -> list:
    """x_range or y_range for a page, `[minimum, maximum]`: each end from the most specific table that sets
    it, `"default"` there being the layer below's (V131); at the bottom, `"default"`: the range Paint
    calculates."""
    return [next((t[name][i] for t in tables if isinstance(t.get(name), list) and t[name][i] != DEFAULT), DEFAULT)
            for i in (0, 1)]


def pages(errand, configuration, plans, notes: list | None = None, documents: str = "") -> list[Page]:
    """Write the Paint config of every page from the points whose record is complete (drawable); returns the
    pages. `notes`: what the sets say (V163), for the stage to say. `documents`: a folder of the working
    folder's for the page documents (the statistics' own, V168), the merged sweep shared."""
    complete = drawable(plans)[0]
    if not complete:
        return []
    check_figures(errand, configuration)
    declared = figures(errand)
    here = complete[0].folders
    out_dir = here.pages                                          # .cache/<A>/plots/<E>/<R>: documents, working files (V164)
    page_groups, curve_groups = axes_of(configuration)
    sources = point_yodas(errand, complete)
    standins = merged_curves(errand, complete, sources, out_dir / "sets")       # set-merge: a `merge` entry's curves
    root = merge(sources, out_dir / f"{configuration.label}.root", out_dir / "merged.sha256",
                 manifest_file(complete))
    drawn = [f for f in declared if f.kind in ("defined", "overlay")] + derived_figures(declared)
    made = _pages(errand, complete, sources, root, drawn, page_groups, curve_groups, out_dir / documents if documents else out_dir,
                  here.plots, here.statistics, implicit=True, labels_from=_labels_from(declared, sources), notes=notes,
                  standins=standins)
    for figure in (f for f in declared if f.kind == "merged"):        # V82: points merged over an axis, for it alone
        members, yodas = _merged(errand, figure, complete, sources, page_groups + curve_groups, out_dir / "merged" / figure.name)
        kept = [g for g in curve_groups if not set(g) & set(figure.over)]
        root = merge(yodas, out_dir / "merged" / f"{figure.name}.root", out_dir / "merged" / f"{figure.name}.sha256")
        made += _pages(errand, members, yodas, root, [replace(figure, kind="defined")], page_groups, kept,
                       out_dir / documents if documents else out_dir, here.plots, here.statistics, implicit=False,
                       folder=figure.name, grouped=False)
    for figure in (f for f in declared if f.kind == "scan"):          # V85: a number per point against a quantity
        members, yodas = _scanned(errand, figure, complete, sources, page_groups + curve_groups, out_dir / "scan" / figure.name)
        kept = [g for g in curve_groups if figure.x not in g]
        root = merge(yodas, out_dir / "scan" / f"{figure.name}.root", out_dir / "scan" / f"{figure.name}.sha256")
        table = {"x_label": figure.x, "y_label": SCAN_LABELS.get(figure.y, figure.y.replace(":", " ")), **figure.table}
        made += _pages(errand, members, yodas, root, [replace(figure, kind="defined", objects=(f"/FIGURES/{figure.name}",),
                                                              table=table, type=figure.type or "Scatter2D")],
                       page_groups, kept, out_dir / documents if documents else out_dir, here.plots, here.statistics,
                       implicit=False, grouped=False)
    return made


#: A scan figure's y axis title when it sets none (V85).
SCAN_LABELS = {"sigma": r"$\sigma$ [pb]", "entries": "entries", "integral": "integral", "mean": "mean"}


def _scanned(errand, figure: Figure, complete: list, sources: dict, groups: list, where: Path) -> tuple[list, dict]:
    """A scan figure's members (V85): per value of the axes other than x, a stand-in plan named by their
    tags, its YODA one Scatter2D /FIGURES/<name>: a point per value of x, at that value, its y the number
    the figure reads of the point (framework/plot/figures/derive.py), its x range reaching halfway to its
    nearer neighbour on both sides, so it is centred on its value and every backend can draw it as a
    bin (a scan is drawn as markers, V86). Remade only when a member's YODA or the figure changed."""
    module = plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "derive.py", "derive")
    quantity = errand.quantities[figure.x]
    kept = [g for g in groups if figure.x not in g]
    by: dict[tuple, list] = {}
    for plan in complete:
        by.setdefault(tuple(group_key(g, plan.point.choice) for g in kept), []).append(plan)
    where.mkdir(parents=True, exist_ok=True)
    glob = figure.objects[0] if figure.objects else ""
    members, yodas = [], {}
    for key, plans in by.items():
        name = "_".join(group_tag(errand.quantities, g, plans[0].point.choice) for g in kept) or "scan"
        plans = sorted(plans, key=lambda p: float(quantity.values[p.values[figure.x]]))
        target, stamp = where / f"{name}.yoda", where / f"{name}.sha256"
        xs = [float(quantity.values[p.values[figure.x]]) for p in plans]
        gaps = [b - a for a, b in zip(xs, xs[1:])]
        halves = [min([g for g in (gaps[i - 1] if i else None, gaps[i] if i < len(gaps) else None) if g] or [1.0]) / 2
                  for i in range(len(xs))]
        digest = ("\n".join(f"{p.point.name} {_sha(sources[p.point.name])}" for p in plans)
                  + f"\n{figure.y} {glob} {xs} {halves}")
        if not (target.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == digest):
            points = []
            for plan, x, half in zip(plans, xs, halves):
                lo, hi = x - half, x + half
                try:
                    value, error = module.scan_value(str(sources[plan.point.name]), figure.y, glob)
                except ValueError as error:
                    raise HeimdallError(f"figure '{figure.key}' at {plan.point.name}: {error}", where=figure.where) from None
                points.append((x, x - lo, hi - x, value, error))
            target.write_text(module.scatter(f"/FIGURES/{figure.name}", points), encoding="utf-8")
            stamp.write_text(digest, encoding="utf-8")
        first = plans[0]
        members.append(replace(first, point=replace(first.point, name=name),
                               values={q: i for q, i in first.values.items() if q != figure.x}))
        yodas[name] = target
    return members, yodas


#: A compare figure's curve axis (V83): the configuration, in its members' choice; not a quantity name.
CONFIGURATION = "@configuration"


def compare_pages(errand, figure: Figure, sets: list[tuple]) -> list[Page]:
    """A compare figure's pages (V83): its objects' pages, one per page cell of the configurations, whose
    curves are every configuration's points (or combined groups), labelled by the configuration first.
    `sets`: (configuration, its complete plans) in the figure's order. Into
    records/<A>/<E>/compare/<name>/ and results/<A>/<E>/compare/<name>/<backend>/."""
    members, yodas = [], {}
    for number, (c, plans) in enumerate(sets):
        label = figure.labels[number] if figure.labels else c.configuration.label if c.own \
            else f"{c.errand.name} {c.configuration.label}"
        sources = point_yodas(c.errand, plans)
        for plan in plans:
            name = f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', c.ref)}_{plan.point.name}"
            members.append(replace(plan, point=replace(plan.point, name=name, choice={**plan.point.choice, CONFIGURATION: number}),
                                   context={**plan.context, "curve_label": label, **({} if c.errand is errand else {"errand": c.errand})}))
            yodas[name] = sources[plan.point.name]
    first = next(plans[0] for c, plans in sets if c.errand is errand)    # this run's folder (V88)
    out_dir, res_dir = first.folders.compare(figure.name)
    page_groups, curve_groups = axes_of(sets[0][0].configuration)
    root = merge(yodas, out_dir / f"{figure.name}.root", out_dir / "merged.sha256")
    return _pages(errand, members, yodas, root, [replace(figure, kind="defined")], page_groups,
                  [[CONFIGURATION]] + curve_groups, out_dir, res_dir, res_dir / "statistics", implicit=False,
                  grouped=False, set_name="")


def derived_figures(declared: list) -> list[Figure]:
    """A derived figure draws its object as a defined figure does (V84): /FIGURES/<name>, its pages."""
    return [replace(f, kind="defined", objects=(f"/FIGURES/{f.name}",)) for f in declared if f.kind == "derived"]


def _labels_from(declared: list, sources: dict) -> dict[str, str]:
    """A derived object's labels are its first object's (.plot): /FIGURES/<name> → that object's path."""
    out = {}
    every = list(dict.fromkeys(base_of(o) for path in sources.values() for o in objects_of(path)))
    for figure in (f for f in declared if f.kind == "derived"):
        first = next((o for o in every if not o.startswith("/FIGURES") and _matches(o, figure.objects[0])), None)
        if first:
            out[f"/FIGURES/{figure.name}"] = first
    return out


def _set_tables(errand) -> list[dict]:
    """The tables whose `sets` are drawn: [plot]'s, then each defined or overlay figure's own."""
    settings = errand.plot or {}
    return [settings] + [f.table for f in figures(errand) if f.kind in ("defined", "overlay")]


def merged_curves(errand, complete: list, sources: dict, where: Path) -> dict:
    """set-merge: the curve each `merge` entry of a drawn set makes, written under `where` and added to `sources`
    ({name: YODA}), with the stand-in member that draws it ({name: member}) and, for a band, the two stand-ins whose objects
    are its edges (`<name>__lo`, `<name>__hi`). `combine` pools the members' statistics (the combine folder's command); any
    other `how` is a mean taken bin by bin (stats/merge.py). Rebuilt only when a member, `how`, its settings or the band
    changed (a stamp of their sha256). A name two sets give different curves is refused."""
    merging = plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "curves.py", "curves")
    settings = errand.plot or {}
    drawing = settings.get("draw")
    stand: dict = {}
    seen: dict[str, tuple] = {}

    def file_of(item) -> Path:
        if isinstance(item, Group):
            return make(item)
        return sources[item.point.name]

    def make(group: Group) -> Path:
        name = group.point.name
        files = [file_of(m) for m in group.members]
        entry = group.entry
        identity = (tuple(leaf.point.name for leaf in group.leaves), entry.how, repr(sorted(entry.settings.items())), entry.band)
        if name in seen:
            if seen[name] != identity:
                raise HeimdallError(f"two sets draw different curves as '{name}'", where=f"{errand.path}: [plot].sets",
                                    hint="give each merge entry a tag of its own: tag = \"…\"")
            return sources[name]
        if name in sources:
            raise HeimdallError(f"the merged curve '{name}' has the name of a point", hint="give the entry a tag of its own: tag = \"…\"")
        target, stamp = where / f"{name}.yoda", where / f"{name}.sha256"
        digest = "\n".join([*(f"{f.name} {_sha(f)}" for f in files), *map(str, identity)])
        if not (target.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == digest):
            where.mkdir(parents=True, exist_ok=True)
            if entry.how == "combine":
                merge_files(files, target)
            else:
                merging.merge_yoda(files, target, entry.how, entry.settings)
            if entry.band:
                merging.band_yoda(files, where / f"{name}__lo.yoda", where / f"{name}__hi.yoda", entry.band)
            stamp.write_text(digest, encoding="utf-8")
        first = group.leaves[0]
        made = replace(first, point=group.point, values=group.values,
                       context={**first.context, "curve_label": group.label, "members": [leaf.point.name for leaf in group.leaves]},
                       **({"yoda": target, "identity": digest, "recorded": digest} if isinstance(first, Member) else {}))
        seen[name] = identity
        sources[name] = target
        stand[name] = made
        if entry.band:
            for side in ("lo", "hi"):
                edge = f"{name}__{side}"
                sources[edge] = where / f"{edge}.yoda"
                stand[edge] = replace(made, point=replace(group.point, name=edge),
                                      **({"yoda": sources[edge]} if isinstance(first, Member) else {}))
        return target

    for table in _set_tables(errand):
        wanted = table.get("sets")
        if not wanted or wanted == DEFAULT:
            continue
        for spec in set_entries(wanted, f"{errand.path}: [plot].sets"):
            if not spec.merge or (table is settings and drawing not in (None, DEFAULT) and spec.name not in drawing):
                continue
            cells, _ = set_cells(errand, complete, spec)
            for cell in cells:
                for member in cell.members:
                    if isinstance(member, Group):
                        make(member)
    return stand


def point_yodas(errand, complete: list) -> dict[str, Path]:
    """Each complete point's YODA, as the pages read it: its product, or with a derived figure (V84) a
    copy with the derived objects after its own (records/…/plots/derived/<point>.yoda), made by
    framework/plot/figures/derive.py and remade only when the product or the figures changed."""
    plain = {p.point.name: yoda_of(p) for p in complete}
    derived = [f for f in figures(errand) if f.kind == "derived"]
    if not derived:
        return plain
    module = plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "derive.py", "derive")
    where = complete[0].folders.pages / "derived"
    where.mkdir(parents=True, exist_ok=True)
    specs = [(f.name, f.op, list(f.objects)) for f in derived]
    out = {}
    for name, source in plain.items():
        target, stamp = where / f"{name}.yoda", where / f"{name}.sha256"
        digest = f"{_sha(source)} {json.dumps(specs)}"
        if not (target.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == digest):
            text = [hepfiles.yoda_text(source).rstrip("\n") + "\n\n"]
            for figure, spec in zip(derived, specs):
                try:
                    text.append(module.derive(str(source), [spec]))
                except ValueError as error:
                    raise HeimdallError(f"figure '{figure.key}' at {name}: {error}", where=figure.where) from None
            target.write_text("".join(text), encoding="utf-8")
            stamp.write_text(digest, encoding="utf-8")
        out[name] = target
    return out


def _merged(errand, figure: Figure, complete: list, sources: dict, groups: list, where: Path) -> tuple[list, dict]:
    """A merged figure's members: per value of the axes it does not merge, one stand-in plan named by
    their tags, its YODA the members' merged by the combine folder's command; rebuilt only when a
    member's YODA changed (a stamp of their sha256, as merge's)."""
    kept = [g for g in groups if not set(g) & set(figure.over)]
    by: dict[tuple, list] = {}
    for plan in complete:
        by.setdefault(tuple(group_key(g, plan.point.choice) for g in kept), []).append(plan)
    members, yodas = [], {}
    for key, plans in by.items():
        name = "_".join(group_tag(errand.quantities, g, plans[0].point.choice) for g in kept) or "merged"
        target = where / f"{name}.yoda"
        stamp = where / f"{name}.sha256"
        digest = "\n".join(f"{p.point.name} {_sha(sources[p.point.name])}" for p in plans)
        if not (target.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == digest):
            merge_files([sources[p.point.name] for p in plans], target)
            stamp.write_text(digest, encoding="utf-8")
        first = plans[0]
        members.append(replace(first, point=replace(first.point, name=name),
                               values={q: i for q, i in first.values.items() if q not in figure.over}))
        yodas[name] = target
    return members, yodas


def _pages(errand, complete: list, yodas: dict, merged: Path, declared: list, page_groups: list, curve_groups: list,
           out_dir: Path, plots_dir: Path, stats_dir: Path, *, implicit: bool, folder: str = "",
           labels_from: dict | None = None, grouped: bool = True, notes: list | None = None,
           set_name: str = "totality", standins: dict | None = None) -> list[Page]:
    """The pages of these figures from these members (a point, or a merged figure's stand-in: its name
    is its directory in `merged`, the ROOT file of their YODAs `yodas`). `implicit`: [plot].objects's
    pages too. `folder`: the figure's own, between the cell and the object. `grouped`: the members may be
    paged by `sets` and `split` (V159, V163); a merged, scan or compare figure's stand-ins page by plot_points.
    `notes`: what the sets say (an axis they page by themselves, a reference matching nothing). V164: a page is
    drawn into <plots_dir>/<set>/<backend>/<cell>/<object> (`set_name` with no [plot].sets: totality; "" none, a
    compare figure's), its numbers into <stats_dir>/<set>/, its document into <out_dir>/<set>/."""
    settings = errand.plot
    variants: dict[str, dict[str, list[str]]] = {}      # member → base path → its full paths
    standins = standins or {}                              # set-merge: the curves of `merge` entries, drawn by their sets
    everyone = [*complete, *standins.values()]
    raws = {plan.point.name: raws_of(yodas[plan.point.name]) for plan in everyone}
    two_d: set[str] = set()                                # V87: heat maps, a page per member
    for plan in everyone:
        for full in objects_of(yodas[plan.point.name]):
            variants.setdefault(plan.point.name, {}).setdefault(base_of(full), []).append(full)
        for full in hepfiles.objects_2d(yodas[plan.point.name]):
            variants.setdefault(plan.point.name, {}).setdefault(base_of(full), []).append(full)
            two_d.add(base_of(full))
    objects = list(dict.fromkeys(b for plan in complete for b in variants.get(plan.point.name, {})))     # the points' pages
    every = list(objects)                                  # a figure may name any object, drawn alone or not

    def fulls(o):
        return [f for v in variants.values() for f in v.get(o, [])]

    wanted = settings.get("objects", [])                   # the implicit figure: defined pages of these
    wanted = [] if wanted == DEFAULT else wanted
    if not implicit:
        objects = []
    elif wanted:
        objects = [o for o in objects if any(fnmatch.fnmatch(o, g) or any(fnmatch.fnmatch(f, g) for f in fulls(o))
                                             for g in wanted)]
        if not objects:
            raise HeimdallError(f"[plot].objects {wanted} match no object of the points' YODAs",
                           where=f"{errand.path}: [plot].objects")
    claimed: dict[str, Figure] = {}                        # a declared defined figure takes its objects' pages
    for figure in (f for f in declared if f.kind == "defined"):
        found = [o for o in every if any(_matches(o, g, fulls(o)) for g in figure.objects)]
        if not found:
            raise HeimdallError(f"figure '{figure.key}': {list(figure.objects)} match no object of the points' YODAs",
                           where=f"{figure.where}.objects")
        for o in found:
            if o in claimed:
                raise HeimdallError(f"figures '{claimed[o].key}' and '{figure.key}' both make the pages of {o}",
                               where=f"{figure.where}.objects",
                               hint="one recipe per page: narrow a glob; what every page shares goes in [plot]")
            claimed[o] = figure
    objects = [o for o in every if o in objects or o in claimed]

    # use_data = false (V44): the [plot.data] table stays but is not drawn; a ratio then divides by
    # each page's first curve, the first value of its curve axis. A figure may set it, and band, for its own
    data = settings.get("data", {})
    data_file = source = None

    def band_of(override, keys=None) -> list:
        return list(chosen("band", [], [], (override, keys or {}, settings)) or [])

    by_page: dict[str, list] = {}
    for plan in complete:                                  # a member of another run reads its own quantities (V88)
        key = "_".join(group_tag(_errand_of(errand, plan).quantities, g, plan.point.choice) for g in page_groups)
        by_page.setdefault(key, []).append(plan)

    style, base = errand_style(errand), base_style()
    known = {plan.point.name: texts_of(_errand_of(errand, plan), plan, ", ".join(
                 label for g in page_groups for label in group_labels(_errand_of(errand, plan).quantities, g, plan.point.choice)))
             for plan in everyone}
    where = f"{errand.path}: [plot]"

    def page_fill(plans, cell: str | None = None):
        texts = {p.point.name: known[p.point.name] if cell is None else {**known[p.point.name], "cell": cell} for p in plans}
        return filler(list(texts.values()), where)

    palette = list(merge_style(base, style).get("curves", {}).get("palette", []))

    def cells(override) -> list[tuple[str, str, list, str | None, list, dict, dict]]:
        """V159, V163, V164: the pages' cells, (set, key within it, members, {cell}'s text or None, the groups that
        label their curves, the set's page keys, each curve's look by point name): by plot_points (curves by the
        curve axes; the set `set_name`), or by [plot].sets; each cut by split. A V159 set's or a cut's curves are
        labelled by the quantities that differ on it; a V163 set's by its curve axes that differ (set_cells)."""
        tables = (override, settings)
        wanted = chosen("sets", [], [], tables) if grouped else []
        if wanted in (DEFAULT, None):
            wanted = []
        made = []                                     # (set, key, members, text, labelled or None, keys, looks)
        drawing = settings.get("draw") if not override.get("sets") else None    # V167: [plot].draw, --sets
        if wanted:
            for spec in set_entries(wanted, f"{where}.sets"):
                if drawing not in (None, DEFAULT) and spec.name not in drawing:
                    continue
                if spec.axes:                         # V163: a cell per combination of its page axes
                    found, said = set_cells(errand, complete, spec, merge_style({"curves": {"palette": palette}},
                                                                                spec.keys.get("style", {}))["curves"]["palette"],
                                            looked=set(settings.get("looks") or {}))
                    if notes is not None:
                        notes.extend(said)
                    made += [(spec.name, c.key, [standins[m.point.name] if isinstance(m, Group) else m for m in c.members],
                              c.text, c.labelled, spec.keys, c.looks) for c in found]
                    continue
                picked = []
                for selector in spec.selectors:
                    try:
                        found = chosen_points(errand, complete, selector, f"{where}.sets")
                    except HeimdallError:                  # its points are not complete (plan time names a typo)
                        found = []
                    picked += [m for m in found if m not in picked]
                name = spec.name
                if name.startswith("#"):
                    name = picked[0].point.name if picked else name[1:]
                if picked:
                    made.append((name, "", picked, name, None, spec.keys, {}))
        else:
            made = [(set_name, key, members, None, curve_groups, {}, {}) for key, members in by_page.items()]
        cut = []
        for set_, key, members, text, labelled, keys, looks in made:
            split = int(chosen("split", 0, 0, (override, keys, settings)) or 0) if grouped else 0
            if not split:
                cut.append((set_, key, members, text, labelled, keys, looks, False))
                continue
            cut += [(set_, f"{key}-{i}" if key else f"part{i}", members[at:at + split], text, labelled, keys, looks, True)
                    for i, at in enumerate(range(0, len(members), split), start=1)]
        every = page_groups + curve_groups
        out = []
        for set_, key, members, text, labelled, keys, looks, was_cut in cut:
            if labelled is None or (was_cut and labelled is curve_groups):
                differ = [g for g in every if len({group_key(g, m.point.choice) for m in members}) > 1]
                labelled = differ or every
            out.append((set_, key, members, text, labelled, keys, looks))
        return out

    def located(set_: str, rel: str) -> tuple[str, Path, Path, Path, Path]:
        """A page's name, document, output (Paint's), its set's folder and statistics folder (V164)."""
        name = f"{set_}/{rel}" if set_ else rel
        root = plots_dir / set_ if set_ else plots_dir
        return name, out_dir / f"{name}.toml", root / "root" / rel, root, stats_dir / set_ if set_ else stats_dir

    def curve_fill(plan):
        return filler([known[plan.point.name]], where)

    def place(key, stem):
        return "/".join(part for part in (key, folder, stem) if part)

    def written(name, config, output, cell, object_, page, layer, folded, label_of, look_of, override, keys, here, place_,
                data_entry=None, data_of=None, overlay="") -> Page:
        """A page's document from its curves (V170: one for the defined and the overlay pages): each curve's file,
        object, raw entries, label (`label_of`), look (`look_of`) and band; its data; written, and its Page."""
        set_, rel, root, numbers = place_
        document = {"page": page, "style": layer, "curve": [
            {"file": str(merged), "object": f"{plan.point.name}/{root_name(full)}",
             **({"raw": f"{plan.point.name}/RAW/{root_name(full)}"} if "/RAW" + full in raws[plan.point.name] else {}),
             "label": label_of(plan, full, folded_members),
             **({"style": look} if (look := look_of(plan)) else {}),
             **({"band": [{"file": str(merged), "object": f"{m.point.name}/{root_name(f)}"} for m, f in folded_members]}
                if folded_members else {})}
            for plan, full, folded_members in folded]}
        if data_entry:
            document["data"] = data_entry
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(tomli_w.dumps(for_root(document)), encoding="utf-8")
        return Page(name, config, output, cell=cell, object=object_, document=document,
                    sources=[yodas[plan.point.name] for plan, _, _ in folded], variants=[full for _, full, _ in folded],
                    bands=[[(yodas[m.point.name], f) for m, f in ms] for _, _, ms in folded], data=data_of,
                    overrides={k for k, v in {**keys, **override}.items() if v != DEFAULT},
                    style=merge_style(base, layer), statistic=_statistic_of(override, here), overlay=overlay,
                    set=set_, rel=rel, root=root, numbers=numbers,
                    merged={plan.point.name: plan.context["members"] for plan, _, _ in folded if "members" in plan.context},
                    runs={plan.point.name: plan.context["run"] for plan, _, _ in folded if plan.context.get("run")})

    for figure in declared:                                # what a figure draws is what its objects are
        mine = [o for o in objects if claimed.get(o) is figure] if figure.kind == "defined" else []
        flat = [o for o in mine if o not in two_d]
        if figure.type == "HeatMap" and flat:
            raise HeimdallError(f"figure '{figure.key}' is a HeatMap, and {flat[0]} is a 1D object", where=f"{figure.where}.type",
                           hint="a heat map draws a 2D object; leave type out to draw each as it is")
        if figure.type in ("Hist1D", "Scatter2D") and set(mine) & two_d:
            raise HeimdallError(f"figure '{figure.key}' is a {figure.type}, and {sorted(set(mine) & two_d)[0]} is a 2D object",
                           where=f"{figure.where}.type", hint='a 2D object is drawn as a heat map: type = "HeatMap", or leave it out')

    made = []
    own = {o: f for o, f in claimed.items() if o in objects and ({"sets", "split"} & set(f.table))}   # a figure's own cells
    def chosen_objects(keys, path) -> bool:
        """A set's own objects (V163): its pages are of these alone."""
        return not keys.get("objects") or any(_matches(path, g, fulls(path)) for g in keys["objects"])

    todo = [(*cell, path) for cell in cells({}) for path in objects if path not in own and chosen_objects(cell[5], path)]
    todo += [(*cell, path) for path, f in own.items() for cell in cells(override_of(f.table)) if chosen_objects(cell[5], path)]
    for set_, key, members, cell_text, labelled, keys, looks, path in todo:
        short = path.rsplit("/", 1)[-1]
        rel = place(key, short)
        name, config, output, root, numbers = located(set_, rel)
        figure = claimed.get(path)
        override = override_of(figure.table if figure else None)
        here = layered(settings, page_keys(keys))         # a set's page keys over [plot]'s, a figure's over both (V163)
        if path in two_d:                                  # V87: a page per member and variant
            made += [_heatmap(plan, full, *located(set_, place(key, f"{short}/{plan.point.name}")), here, override,
                              merged, (style, base), key, curve_fill(plan), set_)
                     for plan in members for full in variants.get(plan.point.name, {}).get(path, [])]
            continue
        drawn = data if chosen("use_data", True, True, (override, here)) is not False else {}
        reference = drawn.get("map", {}).get(short) if drawn else None
        if reference and data_file is None:                # converted once, when a page draws it
            source = data_source(data["file"], errand)
            data_file = convert(source, cache_root() / errand.assignment / "datasets" / f"{source.stem}.root")   # V149, V164
        band = band_of(override, keys)
        line_groups = [g for g in labelled if not set(g) & set(band)]     # what tells a band curve from another
        curves = [(plan, full) for plan in members for full in variants.get(plan.point.name, {}).get(path, [])]
        fill = page_fill([plan for plan, _ in curves] or members, cell_text)
        folded = _banded(curves, curve_groups, band, lambda p, f: variants[p.point.name][path].index(f))
        folded = [(plan, full, members or ([(standins[f"{plan.point.name}__lo"], full), (standins[f"{plan.point.name}__hi"], full)]
                                           if f"{plan.point.name}__lo" in standins else []))
                  for plan, full, members in folded]                     # a merged curve's own band: its edges
        envelope = f" ({', '.join(band)} envelope)" if band else ""
        page, override = page_settings(here, (labels_from or {}).get(path, path), name, output,
                                       reference is not None, fill=fill, child=override)
        if figure is not None and figure.type == "Scatter2D":
            page["markers"] = True                                       # V86
        several = {plan.point.name for plan, _ in curves if len(variants[plan.point.name][path]) > 1}
        layer = merge_style(style, keys.get("style", {}), override.get("style", {}))
        made.append(written(
            name, config, output, key, path, page, layer, folded,
            lambda plan, full, folded_members: _curve_label(errand, plan, line_groups, curve_fill(plan))
            + (f" [{full.strip('/').split('/')[0].partition(':')[2]}]" if plan.point.name in several else "")
            + (envelope if folded_members else ""),
            lambda plan: {**_curve_look(errand, plan, line_groups, settings.get("looks")), **looks.get(plan.point.name, {})},
            override, keys, here, (set_, rel, root, numbers),
            data_entry={"file": str(data_file), "object": root_name(reference),
                        "label": canonical(fill(data.get("legend", "Data")))} if reference else None,
            data_of=(source, reference) if reference else None))

    for figure in (f for f in declared if f.kind == "overlay"):     # V51: several objects of a point on one page
        name, table = figure.name, figure.table
        paths = []
        for glob in figure.objects:
            found = [o for o in every if _matches(o, glob)]
            if not found:
                raise HeimdallError(f"figure '{figure.key}': '{glob}' matches no object of the points' YODAs",
                               where=f"{figure.where}.objects")
            if found[0] in two_d:
                raise HeimdallError(f"figure '{figure.key}': {found[0]} is a 2D object, which a heat map draws alone",
                               where=f"{figure.where}.objects", hint="an overlay draws 1D objects together")
            paths.append(found[0])
        labels = list(figure.labels) or [p.rsplit("/", 1)[-1] for p in paths]
        for set_, key, members, cell_text, labelled, keys, _ in cells(override_of(table)):
            rel = place(key, name)
            full_name, config, output, root, numbers = located(set_, rel)
            here = layered(settings, page_keys(keys))
            named = {}
            for plan in members:
                for path, label in zip(paths, labels):
                    if path in variants.get(plan.point.name, {}):
                        named[(plan.point.name, variants[plan.point.name][path][0])] = canonical(curve_fill(plan)(label))
            curves = [(plan, full) for plan in members for (point, full) in named if point == plan.point.name]
            band = band_of(table, keys)
            line_groups = [g for g in labelled if not set(g) & set(band)]
            folded = _banded(curves, curve_groups, band, lambda p, f: f)          # V69, an overlay's own band
            envelope = f" ({', '.join(band)} envelope)" if band else ""
            page, override = page_settings(here, paths[0], full_name, output, False, child=table,
                                           fill=page_fill([plan for plan, _ in curves] or members, cell_text))
            if figure.type == "Scatter2D":
                page["markers"] = True                                       # V86
            layer = merge_style(style, keys.get("style", {}), override.get("style", {}))
            lines = {plan.point.name for plan, _, _ in folded}
            made.append(written(
                full_name, config, output, key, f"/overlay/{name}", page, layer, folded,
                lambda plan, full, folded_members: named[(plan.point.name, full)]
                + (f", {_curve_label(errand, plan, line_groups, curve_fill(plan))}" if len(lines) > 1 else "")
                + (envelope if folded_members else ""),
                lambda plan: {}, override, keys, here, (set_, rel, root, numbers), overlay=name))
    return made


# ── page statistics (V160): Paint's numbers, as it draws the page ──────────────────────────────

#: What each statistic is called after a legend entry (LaTeX, as every label).
STATISTIC_LABELS = {"area": "area", "abs_area": "$|\\Delta|$ area", "rel_abs_area": "$|\\Delta|$/ref",
                    "area_ratio": "area/ref", "ratio_mean": "mean ratio", "ratio_dev": "|ratio-1|", "chi2": "$\\chi^{2}$", "chi2_ndf": "$\\chi^{2}$/ndf"}


def _statistic_of(override: dict, settings: dict) -> str:
    chosen_one = chosen("legend_statistic", "none", "none", (override, settings))
    return "" if chosen_one in ("none", DEFAULT, None) else chosen_one


def _shown(value: float) -> str:
    return "–" if value != value else f"{value:.3g}"


def _with_statistics(paint: Path, todo: list[Page]) -> None:
    """legend_statistic (V160): Paint reads those pages first (--ranges-only writes their statistics), and each
    curve's legend entry gains its number, in the page document every backend draws from."""
    asked = [p for p in todo if p.statistic and not p.document["page"].get("heatmap")]
    if not asked:
        return
    _paint(paint, [p.config for p in asked], ["--ranges-only"])
    for page in asked:
        rows = statistics_of(page)
        if not rows:
            continue
        page.plain = [c["label"] for c in page.document["curve"]]
        for curve, row in zip(page.document["curve"], rows):
            if not row["is_reference"]:
                curve["label"] = f"{curve['label']} ({STATISTIC_LABELS[page.statistic]} {_shown(row[page.statistic])})"
        page.config.write_text(tomli_w.dumps(for_root(page.document)), encoding="utf-8")


def statistic_pages(errand, figure: Figure, todo: list[Page], where: Path) -> list[Page]:
    """A statistic figure's pages (V160): per cell and object its globs match among the drawn defined pages,
    the page's curves (its own reference curve left out) as bins 1, 2, …, labelled by the curves' labels, y
    their `statistic` against the page's reference; `sort`: the smallest first. A Scatter2D per page, as a
    scan figure's (derive.scatter), into .cache/…/statistic/<name>/, converted for Paint; drawn into the page's
    set's statistics/<set>/figures/<backend>/<cell>/<name>/<object> (V164)."""
    module = plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "derive.py", "derive")
    where.mkdir(parents=True, exist_ok=True)
    style, base = errand_style(errand), base_style()
    made = []
    for page in todo:
        if page.overlay or page.document["page"].get("heatmap") or page.object.startswith("/statistic/"):
            continue
        if not any(_matches(page.object, glob) for glob in figure.objects):
            continue
        rows = [r for r in (statistics_of(page) or []) if not r["is_reference"]]
        if figure.sort:
            rows.sort(key=lambda r: (r[figure.statistic] != r[figure.statistic], r[figure.statistic]))   # NaN last
        if not rows:
            continue
        short = page.object.rsplit("/", 1)[-1]
        rel = "/".join(part for part in (page.cell, figure.name, short) if part)
        stem = f"{page.set}/{rel}".replace("/", "__")
        path = f"/FIGURES/{figure.name}"
        points = [(i + 1.0, 0.5, 0.5, r[figure.statistic], r["area_err"] if figure.statistic == "area" else 0.0)
                  for i, r in enumerate(rows) if r[figure.statistic] == r[figure.statistic]]
        if not points:
            continue
        kept = [r for r in rows if r[figure.statistic] == r[figure.statistic]]
        (where / f"{stem}.yoda").write_text(module.scatter(path, points), encoding="utf-8")
        root = convert(where / f"{stem}.yoda", where / f"{stem}.root")
        reference = rows[0]["reference"]
        compared = "" if figure.statistic == "area" else f" against {reference}"
        table = {"y_label": f"{STATISTIC_LABELS[figure.statistic]}{compared}", "x_label": "", "logy": False,
                 **figure.table, "ratio": False, "normalise": False, "void_empty": False, "min_entries": 0,
                 "auto_range": False, "x_gutter": DEFAULT if "x_gutter" not in figure.table else figure.table["x_gutter"]}
        folder = page.numbers / "figures" if page.numbers else page.root
        name = f"{page.set}/figures/{rel}" if page.set else f"figures/{rel}"
        settings_page, override = page_settings(errand.plot, page.object, name, folder / "root" / rel, False, child=table,
                                                own_ranges=True)    # [plot]'s ranges are for its own pages
        settings_page.update({"markers": True, "x_labels": [r["curve"] for r in kept]})
        layer = merge_style(style, override.get("style", {}))
        document = {"page": settings_page, "style": layer,
                    "curve": [{"file": str(root), "object": root_name(path), "label": STATISTIC_LABELS[figure.statistic]}]}
        config = where / f"{stem}.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        document_root = for_root(document)
        document_root["page"]["x_labels"] = [tlatex(label) for label in settings_page["x_labels"]]
        config.write_text(tomli_w.dumps(document_root), encoding="utf-8")
        made.append(Page(name, config, folder / "root" / rel, cell=page.cell, object=f"/statistic/{figure.name}",
                         document=document, overrides={k for k, v in override.items() if v != DEFAULT},
                         style=merge_style(base, layer), set=page.set, rel=rel, root=folder))
    return made


def _heatmap(plan, full: str, name: str, config: Path, output: Path, root: Path, numbers: Path, settings: dict,
             override: dict, merged: Path, styles: tuple[dict, dict], cell: str, fill, set_name: str) -> Page:
    """A heat map page (V87): one member's 2D object, its .plot labels (ZLabel, LogZ too), its figure's
    and [plot]'s titles, coloured by Paint; no ratio, data, voiding or calculated range: x_range and
    y_range only from its own figure (a 1D page's y is not a heat map's). `styles`: the run's style layers
    and base.toml."""
    style, base = styles
    labels = labels_of(full)
    page, override = page_settings(settings, full, name, output, False, fill=fill, child=override, own_ranges=True)
    page.update({"heatmap": True, "ratio": False, "z_label": canonical(fill(labels.get("ZLabel", ""))),
                 "logz": bool(chosen("logz", labels.get("LogZ") == "1", labels.get("LogZ") == "1", (override, settings)))})
    layer = merge_style(style, override.get("style", {}))
    document = {"page": page, "style": layer, "curve": [{"file": str(merged), "object": f"{plan.point.name}/{root_name(full)}",
                                                         "label": plan.point.name}]}
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(tomli_w.dumps(for_root(document)), encoding="utf-8")
    rel = name.split("/", 1)[1] if set_name else name
    return Page(name, config, output, cell=cell, object=base_of(full), document=document, sources=[],
                variants=[full], overrides={k for k, v in override.items() if v != DEFAULT},
                style=merge_style(base, layer), set=set_name, rel=rel, root=root, numbers=numbers)


def texts_of(errand, plan, cell: str) -> dict[str, str]:
    """What a page text may cite at a point (V66): {cell}, {q:<quantity>} (the label of its value at the
    point, swept or static) and the texts the tools' folders give (rivet: {opt:NAME})."""
    out = {"cell": cell}
    for name, index in plan.values.items():
        if name in errand.quantities:
            out[f"q:{name}"] = label_of(errand.quantities[name], index)
    if isinstance(plan, Member):
        out.update(plan.texts)
    else:
        for step in plan.rendered.values():
            out.update(step.texts)
    return out


def axes_of(configuration) -> tuple[list, list]:
    """The sweep's axes that make pages (plot_points) and those that make curves; a combined axis is
    merged away (V35) and is neither."""
    pages_, curves = split_axes(configuration)                    # a listed group split between them (V154)
    combined = set(configuration.combine)
    return [g for g in pages_ if not set(g) & combined], [g for g in curves if not set(g) & combined]


def check_figures(errand, configuration) -> None:
    """At plan time too: a band (V69), [plot]'s or a figure's, and a merged figure's `over` (V82) name
    curve axes of the configuration, and a figure does not band what it merges."""
    curve_groups = axes_of(configuration)[1]
    listed = {name for group in axes(configuration) if isinstance(group, Listed) for name in group}
    settings = errand.plot or {}
    hint = f"curve axes: {', '.join(g[0] for g in curve_groups) or 'none'} (swept, not plot_points or combined)"
    tables = [("[plot]", settings, ())] + [(f.where.split(": ", 1)[1], f.table, f.over) for f in figures(errand)]
    for at, table, over in tables:
        band = table.get("band", [])
        for key, names in (("band", band if isinstance(band, list) else []), ("over", over)):
            for name in names:
                if not any(name in g for g in curve_groups):
                    raise HeimdallError(f"{at}.{key} names {name}, which is not a curve axis of {configuration.key}",
                                   where=f"{errand.path}: {at}.{key}", hint=hint)
                if name in listed:
                    raise HeimdallError(f"{at}.{key} names {name}, a quantity of listed points (vary's {{ points = … }})",
                                   where=f"{errand.path}: {at}.{key}",
                                   hint="listed points are not a grid to band or merge across: sweep it as an axis of its own")
        if set(band if isinstance(band, list) else []) & set(over):
            raise HeimdallError(f"{at} both merges and bands {sorted(set(band) & set(over))[0]}", where=f"{errand.path}: {at}.band",
                           hint="a merged axis is one curve already: band another, or merge less")
    from .quantities import static_values
    from .sweep import TOTALITY, named_sets
    from .sweep import points as sweep_points
    for key, given in (("plot", getattr(configuration, "draw", True)), ("stats", getattr(configuration, "measure", True))):
        known = {TOTALITY, *named_sets(settings.get("sets"))}                    # V167, V168: what [errand] picks
        for name in given if isinstance(given, list) else ():
            if name not in known:
                raise HeimdallError(f"{key} = [...] names '{name}', which is no set", where=f"{errand.path}: {key}",
                               hint=did_you_mean(name, sorted(known)) or f"sets: {', '.join(sorted(known))}")
    def mine(at: str, table: dict):
        """The sets of [plot] this configuration draws or measures (V179), None for every one: a file's sets are
        there to be picked, and one naming a value this configuration has not is another configuration's."""
        if at != "[plot]":
            return None
        draw, measure = getattr(configuration, "draw", True), getattr(configuration, "measure", True)
        if draw is True and isinstance(table.get("draw"), list):                  # a plot document's own picks
            draw = table["draw"]
        if draw is True or (draw is False and measure is True):
            return None
        return {TOTALITY, *(draw if isinstance(draw, list) else ()), *(measure if isinstance(measure, list) else ())}

    made = None
    for at, table, _ in tables:                                                     # V159, V163: what each set names
        if table.get("sets") and table.get("sets") != DEFAULT:
            made = made if made is not None else sweep_points(errand, configuration)
            static = static_values(errand, configuration)
            specs = set_entries(table["sets"], f"{errand.path}: {at}.sets")
            picked = table.get("draw")
            for name in picked if isinstance(picked, list) else ():                  # V167: what it draws
                if name not in {s.name for s in specs}:
                    raise HeimdallError(f"{at}.draw names '{name}', which is no set", where=f"{errand.path}: {at}.draw",
                                   hint=did_you_mean(name, [s.name for s in specs]) or f"sets: {', '.join(s.name for s in specs)}")
            checked = mine(at, table)
            for spec in specs:
                if checked is not None and spec.name not in checked:
                    continue                                                        # its shape is checked: set_entries
                for selector in spec.selectors:
                    chosen_points(errand, made, selector, f"{errand.path}: {at}.sets")
                if spec.axes:
                    check_set(errand, spec, made, set(configuration.combine),
                              values=lambda p: {**static, **p.choice})
    for figure in (f for f in figures(errand) if f.kind == "compare"):
        compared(errand, figure)
    for figure in (f for f in figures(errand) if f.kind == "scan"):                 # V85
        at = f"{errand.path}: {figure.where.split(': ', 1)[1]}.x"
        if not any(figure.x in g for g in curve_groups) or figure.x in listed:
            raise HeimdallError(f"a scan figure's x names {figure.x}, which is not a curve axis of {configuration.key}"
                           + (" of its own (it is in listed points)" if figure.x in listed else ""), where=at, hint=hint)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in errand.quantities[figure.x].values):
            raise HeimdallError(f"a scan figure's x, {figure.x}, has values that are not numbers", where=at,
                           hint="its values are the x axis: a quantity of numbers (a scan of named values is not drawn yet)")
        if figure.x in (figure.table.get("band") or []):
            raise HeimdallError(f"a scan figure's x, {figure.x}, is its axis: it cannot be banded", where=f"{at.removesuffix('.x')}.band")


@dataclass(frozen=True)
class Compared:
    """One configuration of a compare figure: `ref` as the figure names it ("cfg", or
    "<A>/<E>:<cfg>" in another errand file, V88), its run and its configuration."""
    ref: str
    errand: object
    configuration: object
    record: bool = False     # "<A>/<E>/<R>": a record, drawn as it recorded its points (V158)
    members: list | None = None   # a plot document's (V165): the other document's members ([] when it has none yet)

    @property
    def own(self) -> bool:
        return ":" not in self.ref and not self.record


def compared(errand, figure: Figure) -> list[Compared]:
    """A compare figure's configurations (V83): those it names, else the sweep_runs ones; two at least,
    one of them this file's, every one with the same page and curve axes (another run's page axes with
    the same tags too), so that their pages pair up."""
    from .config import load
    at = f"{figure.where}.configurations"
    if hasattr(errand, "sibling"):                           # a plot document's (V165): the others are documents too
        return _compared_documents(errand, figure, at)
    keys = list(figure.configurations) or (errand.runs(None) if errand.sweep_runs else [])
    if len(keys) < 2:
        raise HeimdallError("a compare figure needs two configurations or more", where=at,
                       hint='configurations = ["a", "b"], or [errand].sweep_runs: its configurations')
    if len(set(keys)) != len(keys):
        raise HeimdallError("a compare figure names a configuration twice", where=at)
    out = []
    for ref in keys:
        if ":" not in ref and ref.count("/") == 2:               # a record (V158): its snapshot's run
            from .paths import configs_at
            from .record import read_snapshot, record_of
            try:
                found = record_of(ref)
            except HeimdallError as error:
                raise HeimdallError(f"a compare figure names '{ref}': {error.message}", where=at, hint=error.hint) from None
            if found is None:
                raise HeimdallError(f"a compare figure names '{ref}', which is no record", where=at,
                               hint="a record is <A>/<E>/<R>, a folder of records/ with a snapshot")
            snap = read_snapshot(found)
            with configs_at(found / "config"):                             # V179: read for its configuration
                owner = load(snap["config"], sets=list(snap.get("sets", [])), configuration=snap["configuration"])
            out.append(Compared(ref, owner, owner.configurations[snap["configuration"]], record=True))
            continue
        owner, key = (errand, ref) if ":" not in ref else (None, ref.rsplit(":", 1)[1])
        if owner is errand and key in errand.configurations and errand.configurations[key].own != errand.applied:
            owner = load(str(errand.path), sets=list(errand.sets), configuration=key)       # V179: its own vars and data
        if owner is None:
            try:
                owner = load(ref.rsplit(":", 1)[0], configuration=key)
            except HeimdallError as error:
                raise HeimdallError(f"a compare figure names '{ref}': {error.message}", where=at, hint=error.hint) from None
        if key not in owner.configurations:
            raise HeimdallError(f"a compare figure names '{ref}', which is not a configuration", where=at,
                           hint=did_you_mean(key, list(owner.configurations)) or f"configurations: {', '.join(owner.configurations)}")
        out.append(Compared(ref, owner, owner.configurations[key]))
    if not any(c.own for c in out):
        raise HeimdallError("a compare figure names a configuration of its own file too", where=at,
                       hint="its pages are drawn by that configuration's plot stage, into this errand's compare/")
    shapes = {c.ref: axes_of(c.configuration) for c in out}
    first = out[0]
    for c in out[1:]:
        if shapes[c.ref] != shapes[first.ref]:
            raise HeimdallError(f"a compare figure's configurations differ in their axes: {first.ref} {_shape(shapes[first.ref])}, "
                           f"{c.ref} {_shape(shapes[c.ref])}", where=at,
                           hint="compared configurations sweep the same quantities, with the same plot_points and combine")
    for c in (c for c in out if not c.own):              # another run's page cells must be this run's
        for group in shapes[c.ref][0]:
            for name in (group if isinstance(group, Listed) else group[:1]):
                mine, theirs = errand.quantities[name], c.errand.quantities[name]
                if [tag_of(mine, i) for i in range(len(mine.values))] != [tag_of(theirs, i) for i in range(len(theirs.values))]:
                    raise HeimdallError(f"'{c.ref}' has other values of {name}, a page axis, than this file", where=at,
                                   hint="its pages pair with this file's by the page axes' tags")
    if figure.labels and len(figure.labels) != len(out):
        raise HeimdallError(f"a compare figure's labels give one label per configuration ({len(out)})", where=f"{figure.where}.labels")
    return out


def _compared_documents(errand, figure: Figure, at: str) -> list[Compared]:
    """A compare figure drawn from a plot document (V165): this document's configuration, and each other one's
    latest plot document (run.sibling: a configuration of the same errand file, a record, "<config>:<cfg>"); one
    with no document yet has no members (the figure waits). The found ones' axes must match, as compared's."""
    keys = list(figure.configurations)
    if len(keys) < 2:
        raise HeimdallError("a compare figure needs two configurations or more", where=at,
                       hint='configurations = ["a", "b"]: drawn from a plot document, it names them')
    out = []
    for ref in keys:
        record = ":" not in ref and ref.count("/") == 2
        if ref == errand.configuration.key:
            out.append(Compared(ref, errand, errand.configuration))
            continue
        found = errand.sibling(ref)
        out.append(Compared(ref, found[0] if found else None, found[1] if found else None, record=record,
                            members=found[2] if found else []))
    if not any(c.ref == errand.configuration.key for c in out):
        raise HeimdallError("a compare figure names a configuration of its own file too", where=at)
    shapes = {c.ref: axes_of(c.configuration) for c in out if c.configuration is not None}
    for c in out:
        if c.configuration is not None and shapes[c.ref] != shapes[errand.configuration.key]:
            raise HeimdallError(f"a compare figure's configurations differ in their axes: {errand.configuration.key} "
                           f"{_shape(shapes[errand.configuration.key])}, {c.ref} {_shape(shapes[c.ref])}", where=at,
                           hint="compared configurations sweep the same quantities, with the same plot_points and combine")
    if figure.labels and len(figure.labels) != len(out):
        raise HeimdallError(f"a compare figure's labels give one label per configuration ({len(out)})", where=f"{figure.where}.labels")
    return out


def _shape(shape) -> str:
    pages_, curves = shape
    return f"(pages: {', '.join(g[0] for g in pages_) or 'none'}; curves: {', '.join(g[0] for g in curves) or 'none'})"


def check_texts(errand, plans) -> None:
    """V66 at plan time: every placeholder the errand file's texts cite ([plot] and its children, the
    quantities' labels) is one the points have, so a typo costs no point run. Whether a page text has one
    value on its page is known only with the pages, at the plot stage."""
    if not errand.plot:
        return
    cited: list[tuple[str, str]] = []

    def walk(value, at):
        if isinstance(value, str):
            cited.extend((m.group(1), at) for m in PLACEHOLDER.finditer(value))
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(v, f"{at}.{k}")
        elif isinstance(value, list):
            for v in value:
                walk(v, at)
    walk(errand.plot, "[plot]")
    for name, quantity in errand.quantities.items():
        walk(quantity.labels, f"[quantities.{name}].labels")
    known = {"cell"} | {k for plan in plans for k in texts_of(errand, plan, "")}
    for key, at in cited:
        if key not in known:
            raise HeimdallError(f"a page text cites {{{key}}}, which is nothing the points have", where=f"{errand.path}: {at}",
                           hint=did_you_mean(key, sorted(known)) or f"they have: {', '.join('{' + k + '}' for k in sorted(known))}")


def filler(known: list[dict[str, str]], where: str):
    """A function filling a text's placeholders from the points it speaks for: a page's (all its curves'
    points: a value must be the same at every one) or a curve's (its own point)."""
    def fill(text: str) -> str:
        def one(match):
            key = match.group(1)
            values = {k.get(key) for k in known}
            if None in values:
                cited = sorted({k for d in known for k in d})
                raise HeimdallError(f"a page text cites {{{key}}}, which is nothing the points have", where=where,
                               hint=did_you_mean(key, cited) or f"they have: {', '.join('{' + k + '}' for k in cited)}")
            if len(values) > 1:
                raise HeimdallError(f"a page text cites {{{key}}}, which differs between the curves of the page: "
                               f"{', '.join(sorted(values))}", where=where,
                               hint="cite it in the curves' labels (a quantity's labels), or make it a plot_points axis")
            return values.pop()
        return PLACEHOLDER.sub(one, text) if isinstance(text, str) else text
    return fill


def page_settings(settings: dict, path: str, rel: str, output: Path, with_data: bool,
                  child: dict | None = None, fill=lambda text: text, own_ranges: bool = False) -> tuple[dict, dict]:
    """A page's [page] table: labels from the analysis's .plot, its figure's own values (`child`), and the
    [plot] values, their placeholders filled (`fill`, V66). `own_ranges`: x_range and y_range from the
    figure alone (a heat map's, a statistic figure's). Returns it and the figure's values."""
    labels = labels_of(path)
    override = override_of(child)

    def pick(name, ours, native, tables=(override, settings)):
        return chosen(name, ours, native, tables)

    def ours(name):
        return schema.default("plot", name)

    title, header = labels.get("Title", ""), labels.get("LegendTitle", "")     # as mkhtml (V51); LaTeX, as all text (V65)
    x_label, y_label = labels.get("XLabel", ""), labels.get("YLabel", "")
    log_x, log_y = labels.get("LogX") == "1", labels.get("LogY") == "1"
    ratio = labels["RatioPlot"] == "1" if labels.get("RatioPlot") in ("0", "1") else with_data   # mkhtml's rule
    page = {
        "name": rel, "output": str(output), "formats": formats_of(settings),
        "title": canonical(fill(pick("title", title, title))),
        "title_left": canonical(fill(pick("title_left", "", ""))),
        "title_right": canonical(fill(pick("title_right", "", ""))),
        "legend_header": canonical(fill(pick("legend_header", header, header))),
        "x_label": canonical(fill(pick("x_label", x_label, x_label, tables=(override,)))),
        "y_label": canonical(fill(pick("y_label", y_label, y_label, tables=(override,)))),
        "logx": bool(pick("logx", log_x, log_x)),
        "logy": bool(pick("logy", log_y, log_y)),
        "y_gutter": _gutter(pick("y_gutter", ours("y_gutter"), DEFAULT)),
        "x_gutter": _gutter(pick("x_gutter", DEFAULT, DEFAULT)),
        **{name: endpoints(name, (override,) if own_ranges else (override, settings)) for name in RANGES},
        "ratio": bool(pick("ratio", ours("ratio"), ratio)),
        "ratio_label": "MC/Data" if with_data else "Ratio",
        "normalise": pick("normalise", ours("normalise"), False),                 # V68: "area" or false
        "void_empty": bool(pick("void_empty", ours("void_empty"), False)),     # neither tool voids by itself
        "min_entries": int(pick("min_entries", ours("min_entries"), 0)),
        "auto_range": bool(pick("auto_range", ours("auto_range"), False)),    # the tool's own range
        "range_pad": int(pick("range_pad", ours("range_pad"), 0)),
    }
    return page, override


def override_of(child: dict | None) -> dict:
    """What a figure's own table sets for its pages: any [plot] key marked `page` in the schema, and
    x_label, y_label, style. The implicit figure sets nothing of its own."""
    return {k: v for k, v in (child or {}).items() if k not in schema.FIGURE_OWN}


def chosen(name: str, ours, native, tables: tuple):
    """V55: the most specific table that sets a value wins. "default" keeps it as it is: in a child
    (an object's or an overlay's table) it is the parent's value, as if the key were absent; in the
    last table (the top level) of a v2 file it is `native`, set nothing: what the drawing tool does by
    itself (a v3 file drops it: there, "default" is only the layer below). "native" (doc:errand-file) is `native`
    at any level. Nothing set anywhere is `ours`, the runner's default (the schema's)."""
    for table in tables:
        if name in table and table[name] != DEFAULT:
            return native if table[name] == schema.NATIVE else table[name]
    return native if tables[-1].get(name) == DEFAULT else ours


def _gutter(value):
    return value if value == "default" else float(value)


def _banded(curves: list, curve_groups: list, band: list, of_plan) -> list:
    """V69: the page's curves with the band quantities folded: one curve per value of the other curve
    axes (and per variant of the object, `of_plan(plan, full)` its place), the band axes' first value,
    with the others as its members. Without `band`: every curve, no members."""
    if not band:
        return [(plan, full, []) for plan, full in curves]
    banded = [g for g in curve_groups if set(g) & set(band)]
    rest = [g for g in curve_groups if g not in banded]
    groups: dict = {}
    for plan, full in curves:
        key = (tuple(group_key(g, plan.point.choice) for g in rest), of_plan(plan, full))
        groups.setdefault(key, []).append((plan, full))
    out = []
    for members in groups.values():
        members.sort(key=lambda pf: tuple(group_key(g, pf[0].point.choice) for g in banded))
        out.append((*members[0], members[1:]))
    return out


def _errand_of(errand, plan):
    """The run whose quantities a member's choice indexes: its own, for another run's (V88)."""
    return plan.context.get("errand") or errand


def _curve_look(errand, plan, curve_groups, looks=None) -> dict:
    """A curve's own look (V67): the styles of its curve axes' values at its point, a later axis's key
    over an earlier's, each under [plot.looks]' look of its tag (V171). Empty: the page style's palette, in turn."""
    errand = _errand_of(errand, plan)
    look: dict = {}
    for group in curve_groups:
        for name in group:
            if name not in errand.quantities or name not in plan.point.choice:
                continue
            quantity, index = errand.quantities[name], plan.point.choice[name]
            if quantity.styles:
                look.update(quantity.styles[index])
            given = (looks or {}).get(name, {}).get(tag_of(quantity, index)) if looks not in (None, DEFAULT) else None
            if given is not None:
                look.update({"colour": given} if isinstance(given, (str, int)) else {k: v for k, v in given.items() if v != DEFAULT})
    return look


def _curve_label(errand, plan, curve_groups, fill=lambda text: text) -> str:
    """The curve axes' labels at its point, after its own (a compared configuration's, V83); the run's
    name when it has neither."""
    if isinstance(plan, Group):                           # a merge's curve: the axes it keeps, then its own label
        labels = [canonical(fill(label)) for g in curve_groups if g[0] in errand.quantities and g[0] in plan.values
                  for label in group_labels(errand.quantities, g, plan.values)]
        return ", ".join(labels + [canonical(fill(plan.label))])
    errand = _errand_of(errand, plan)
    own = [canonical(fill(plan.context["curve_label"]))] if plan.context.get("curve_label") else []
    known = {**(getattr(plan, "values", None) or {}), **plan.point.choice}   # a fixed quantity's value too
    serial = plan.context.get("run", "").partition("·")[0] if plan.context.get("run", "").count("·") else ""
    labels = [canonical(fill(f"{serial}·{label}" if serial and g[0] == "@tag" else label))      # across: a Run is always named
              for g in curve_groups if g[0] in errand.quantities and g[0] in known
              for label in group_labels(errand.quantities, g, known)]
    return ", ".join(own + labels) or errand.name


def _paint(paint: Path, configs: list[Path], mode: list[str] = (), sets: dict[str, str] | None = None
           ) -> dict[str, tuple[bool, str]]:
    """Paint on many pages, PAINT_BATCH per process (V64): each config's (ok, why). A batch with a failed page
    leaves its output's digest in the drawing's log folder (V204), <set>.root.log for each set its pages are of
    (`sets`: config → set), and a failed page's why names it."""
    outcomes: dict[str, tuple[bool, str]] = {}
    for number, start in enumerate(range(0, len(configs), PAINT_BATCH), 1):
        batch = [str(c) for c in configs[start:start + PAINT_BATCH]]
        done = subprocess.run([str(paint), *batch, *mode], capture_output=True, text=True, encoding="utf-8")
        if len(batch) == 1:
            outcomes[batch[0]] = (done.returncode == 0, _why(done) if done.returncode else "")
        else:
            for line in done.stdout.splitlines():
                if line.startswith("{"):
                    entry = json.loads(line)
                    outcomes[entry["page"]] = (entry["ok"], entry["error"])
            for config in batch:                              # a crash leaves the rest without a line
                outcomes.setdefault(config, (False, _why(done)))
        failed = [c for c in batch if not outcomes[c][0]]
        for set_ in dict.fromkeys((sets or {}).get(c, "") or "pages" for c in failed):
            log = failure_log(f"{set_}.root", done.stdout + done.stderr,
                              {"tag": "Paint", "batch": number, "pages": len(batch), "exit": done.returncode}, append=True)
            for config in (c for c in failed if ((sets or {}).get(c, "") or "pages") == set_ and log is not None):
                ok, why = outcomes[config]
                outcomes[config] = (ok, f"{why} (Paint's output: {log})")
    return outcomes


def _why(done: subprocess.CompletedProcess) -> str:
    if done.returncode < 0 or done.returncode > 128:
        return f"Paint crashed (signal {abs(done.returncode) % 128})"
    for line in reversed((done.stderr + done.stdout).splitlines()):
        if line.strip() and not set(line.strip()) <= set("=-#"):
            return line.strip()[-200:]
    return f"exit {done.returncode}"


def write_index(where: Path, title: str, pages: list[tuple[str, str, Path]]) -> Path:
    """V70: <where>/index.html, the ROOT pages, as mpl's index is: a section per
    plot_points cell, each page shown by its PNG or SVG (an embedded PDF otherwise) and linked to every
    format drawn. `pages`: (cell, name, output without extension), in order."""
    def rel(path: Path) -> str:
        return html.escape(str(path.relative_to(where)) if path.is_relative_to(where) else str(path), quote=True)

    body, cells = [], {}
    for cell, name, output in pages:
        cells.setdefault(cell, []).append((name, output))
    for cell, members in cells.items():
        if cell:
            body.append(f"<h2>{html.escape(cell)}</h2>")
        body.append('<div class="grid">')
        for name, output in members:
            made = [output.with_name(f"{output.name}.{f}") for f in FORMATS]
            made = [m for m in made if m.is_file()]
            shown = next((m for m in made if m.suffix in (".png", ".svg")), None)
            pdf = next((m for m in made if m.suffix == ".pdf"), None)
            if shown:
                view = f'<a href="{rel(pdf or shown)}"><img src="{rel(shown)}" alt="{html.escape(name)}"></a>'
            elif pdf:
                view = f'<object data="{rel(pdf)}" type="application/pdf"><a href="{rel(pdf)}">{html.escape(name)}</a></object>'
            else:
                continue
            links = " ".join(f'<a href="{rel(m)}">{m.suffix[1:]}</a>' for m in made)
            body.append(f"<figure>{view}<figcaption>{html.escape(name.rsplit('/', 1)[-1])} · {links}</figcaption></figure>")
        body.append("</div>")
    index = where / "index.html"
    index.write_text(
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\"><title>" + html.escape(title) + "</title><style>"
        "body{font-family:sans-serif;margin:1.5em}.grid{display:flex;flex-wrap:wrap;gap:1em}"
        "figure{margin:0;width:22em}img,object{width:100%;height:auto;min-height:18em;border:1px solid #ddd}"
        "figcaption{font-size:.85em;color:#444}</style></head><body><h1>" + html.escape(title) + "</h1>\n"
        + "\n".join(body) + "\n</body></html>\n", encoding="utf-8")
    return index


def for_backend(page: Page, name: str) -> Page:
    """The page as another backend draws it: into its set's <name>/ instead of Paint's root/ (V164)."""
    return replace(page, output=page.root / name / page.rel) if page.root else page


def draw(errand, configuration, plans, say, others=None, stats=True) -> int:
    """The plot stage: Paint on every page, then any other backend on the same pages. Returns the
    number of pages that failed, summed over the backends. Then each compare figure that names this
    configuration (V83), once all of its configurations have complete points: `others(key)` gives
    another configuration's plans. A failed program's output is logged in records/<A>/<E>/<R>/logs/plot/ (V204)."""
    token = _LOGS.set(logs_of(plans))
    try:
        return _draw_stage(errand, configuration, plans, say, others, stats)
    finally:
        _LOGS.reset(token)


def _draw_stage(errand, configuration, plans, say, others=None, stats=True) -> int:
    if not errand.plot:
        return 0
    paint = apps_dir() / "Paint.exe"
    if not paint.exists():
        raise HeimdallError(f"{paint} is not built", hint="heimdall build --framework")
    _, other = drawable(plans)
    if other:                                        # V158: drawn as recorded, and named
        names = ", ".join(p.point.name for p in other[:4]) + (", …" if len(other) > 4 else "")
        say(f"plot: {len(other)} point(s) ran with other inputs than the config gives now ({names}): drawn as "
            f"recorded; heimdall run … --why says what changed")
    notes: list[str] = []
    todo = pages(errand, configuration, plans, notes)
    for note in dict.fromkeys(notes):                # V163: an axis a set pages by itself, a reference that matched nothing
        say(f"plot: {note}")
    separate = bool(getattr(errand, "stats", None)) or isinstance(stats, list)   # V168: [stats], or sets picked: a pass of its own
    failed = _draw(errand, paint, todo, f"{errand.name} · {configuration.label}", say, table=bool(stats) and not separate) if todo else 0
    if todo and stats and separate:
        failed += measure(errand, configuration, plans, say, picked=stats if isinstance(stats, list) else None)
    elif todo and stats:                                # V160: from what was drawn
        failed += _statistic_figures(errand, configuration, todo, plans, paint, say)
    if not todo:
        say("plot: no complete point has a YODA product to draw")
    for figure in (f for f in figures(errand) if f.kind == "sheet") if todo else ():
        failed += sheet(errand, figure, todo, say)
    for figure in (f for f in figures(errand) if f.kind == "compare"):
        named = compared(errand, figure)
        if configuration.key not in {c.ref for c in named if c.own or c.errand is errand}:
            continue
        sets, waiting = [], []
        for c in named:
            mine = (plans if c.ref == configuration.key and c.errand is errand else c.members if c.members is not None
                    else recorded(c.errand, c.configuration) if c.record else others(c.ref) if others else [])
            complete = drawable(mine)[0]
            if complete:
                sets.append((c, complete))
            else:
                waiting.append(c.ref)
        if waiting:
            say(f"plot: compare {figure.name} waits for {', '.join(waiting)}: no complete point yet")
            continue
        made = compare_pages(errand, figure, sets)
        say(f"plot: compare {figure.name}, {len(named)} configurations")
        failed += _draw(errand, paint, made, f"{errand.name} · {figure.name}", say)
    return failed


#: What each figure class makes, and where, for --plan (V170).
FIGURE_PLANS = {"defined": "its objects' pages, its keys over [plot]'s", "overlay": "a page per cell: <cell>/{name}",
                "derived": "a new object per point, /FIGURES/{name}, and its pages", "merged":
                "the points merged over {over}: plots/totality/<backend>/<cell>/{name}/<object>",
                "scan": "{y} per point against {x}: plots/totality/<backend>/<cell>/{name}",
                "compare": "its objects across {configurations}: compare/{name}/<backend>/",
                "sheet": "drawn pages tiled: plots/<set>/<backend>/sheets/{name}",
                "statistic": "{statistic} per curve: statistics/<set>/figures/<backend>/<cell>/{name}/<object>"}


def _plan_outputs(errand, configuration, complete: list) -> list[str]:
    """--plan's lines for what else a drawing makes (V170): where its pages go, its figures, its statistics, and
    the runs drawn together."""
    settings = errand.plot or {}
    lines = []
    if complete:
        here = complete[0].folders
        lines.append(f"pages ({', '.join(backends(settings))}; {', '.join(formats_of(settings))}): {here.plots}/<set>/<backend>/; "
                     f"documents in {here.pages}/<set>/")
    for figure in figures(errand):
        what = FIGURE_PLANS.get(figure.kind, figure.kind).format(
            name=figure.name, over=", ".join(figure.over) or "?", y=figure.y, x=figure.x, statistic=figure.statistic,
            configurations=", ".join(figure.configurations) or "the swept configurations")
        objects = f", objects {', '.join(figure.objects)}" if figure.objects else ""
        lines.append(f"figure {figure.key} ({figure.kind}{objects}): {what}")
    recipe = getattr(errand, "stats", None) or {}
    if chosen("statistics", True, True, (settings,)) is False:
        lines.append("statistics: none ([plot].statistics = false)")
    else:
        where = complete[0].folders.statistics if complete else "statistics"
        how = ("; measured by [stats]: " + ", ".join(f"{k} = {v}" for k, v in recipe.items())) if recipe else ", from the pages"
        lines.append(f"statistics: each set's {where}/<set>/ (statistics.csv, bars/, summary){how}")
    across = settings.get("across")
    if across:
        lines.append(f"across: {len(across)} set(s) of the Runs together ({', '.join(across)}): heimdall plot … --across")
    return lines


def plan_lines(errand, configuration, plans) -> list[str]:
    """`heimdall plot … --plan` (V163): each set's page cells and their curves, from the points whose record is
    complete, drawing nothing; with no sets, the plot_points cells. For writing sets against the real points."""
    complete = drawable(plans)[0]
    lines = [f"{errand.name} · {configuration.label}: {len(complete)} of {len(plans)} point(s) complete"]
    settings = errand.plot or {}
    tables = [("[plot]", settings)] + [(f.where.split(": ", 1)[1], f.table) for f in figures(errand)
                                       if f.kind in ("defined", "overlay")]
    shown = False
    for at, table in tables:
        wanted = table.get("sets")
        if not wanted or wanted == DEFAULT:
            continue
        shown = True
        drawing = table.get("draw") if table is settings else None
        for spec in set_entries(wanted, f"{errand.path}: {at}.sets"):
            if drawing not in (None, DEFAULT) and spec.name not in drawing:
                lines.append(f"set {spec.name} ({at}): not drawn ([plot].draw: {', '.join(drawing)})")
                continue
            split = int(chosen("split", 0, 0, (spec.keys, table, settings)) or 0)
            extra = (f", objects {', '.join(spec.keys['objects'])}" if spec.keys.get("objects") else "") + \
                    (f", split {split}" if split else "")
            if not spec.axes:
                picked = []
                for selector in spec.selectors:
                    try:
                        picked += [m for m in chosen_points(errand, complete, selector, at) if m not in picked]
                    except HeimdallError:
                        pass
                lines.append(f"set {spec.name} ({at}): {len(picked)} curve(s){extra}: "
                             + "; ".join(m.point.name for m in picked))
                continue
            palette = merge_style(base_style(), errand_style(errand), spec.keys.get("style", {})).get("curves", {}).get("palette", [])
            cells, notes = set_cells(errand, complete, spec, list(palette))
            roles = cells[0].roles if cells else {}
            look = ", ".join(f"{role} by {q}" for role, q in roles.items())
            lines.append(f"set {spec.name} ({at}): {len(cells)} page cell(s), {sum(len(c.members) for c in cells)} "
                         f"curve(s){extra}" + (f"; {look}" if look else ""))
            for c in cells:
                labels = [_curve_label(errand, m, c.labelled)
                          + (f" (merges {', '.join(leaf.point.name for leaf in m.leaves)}; {m.entry.how})" if isinstance(m, Group) else "")
                          for m in c.members]
                lines.append(f"  {spec.name}/{c.key}" if c.key else f"  {spec.name}")
                lines[-1] += f": {len(c.members)} curve(s): {'; '.join(labels)}"
            lines += [f"  note: {note}" for note in notes]
    lines += _plan_outputs(errand, configuration, complete)
    if not shown:
        page_groups, curve_groups = axes_of(configuration)
        by: dict[str, list] = {}
        for m in complete:
            by.setdefault("_".join(group_tag(errand.quantities, g, m.point.choice) for g in page_groups), []).append(m)
        lines.append(f"no sets: {len(by)} page cell(s) by plot_points ({', '.join(g[0] for g in page_groups) or 'none'})")
        for key, members in by.items():
            lines.append(f"  {key or '(one cell)'}: {len(members)} curve(s): "
                         + "; ".join(_curve_label(errand, m, curve_groups) for m in members))
    return lines


def sheet(errand, figure: Figure, todo: list[Page], say) -> int:
    """A sheet figure (V89): in each set (V164), the drawn pages its globs name (by their names in the set), in
    their order, tiled `columns` wide by framework/plot/figures/layout.py into plots/<set>/<backend>/sheets/
    <name>.pdf, and its .png rendered from that PDF (V102), for Paint's pages and mpl's (mkhtml lays its files
    out its own way). A set none of its globs names is passed over; 1 when no set has its pages, or one has
    some of them only, or it could not be made."""
    module = plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "layout.py", "layout")
    by_set: dict[str, list[Page]] = {}
    for page in todo:
        by_set.setdefault(page.set, []).append(page)
    tiled = 0
    for set_, pages_ in by_set.items():
        chosen_pages: list[Page] = []
        missing = []
        for glob in figure.table_pages:
            found = [p for p in pages_ if fnmatch.fnmatch(p.rel, glob) and p not in chosen_pages]
            if not found:
                missing.append(glob)
            chosen_pages += found
        if not chosen_pages:
            continue
        where = f"sheet {figure.name}" + (f" ({set_})" if set_ else "")
        if missing:
            say(f"plot: {where}: '{missing[0]}' names no page drawn here")
            return 1
        columns = figure.columns or min(3, len(chosen_pages))
        made = []
        for name in (n for n in backends(errand.plot) if n in ("root", "mpl")):
            drawn = [p if name == "root" else for_backend(p, name) for p in chosen_pages]
            files = {fmt: [Path(f"{p.output}.{fmt}") for p in drawn] for fmt in formats_of(errand.plot)}
            try:
                formats = module.tile(files, chosen_pages[0].root / name / "sheets" / figure.name, columns)
            except ValueError as error:
                say(f"plot: {where} ({name}): {error}")
                return 1
            made += [f"{name}: {', '.join(formats)}"] if formats else []
        say(f"plot: {where}, {len(chosen_pages)} page(s) in {columns} column(s)"
            + (f" ({'; '.join(made)})" if made else ": no pdf or png to tile"))
        tiled += 1
    if not tiled:
        say(f"plot: sheet {figure.name}: '{figure.table_pages[0]}' names no page drawn here")
        return 1
    return 0


def _clear(folder: Path) -> None:
    """A set's backend or statistics folder before it is drawn again (V164): it holds its last drawing alone.
    Only ever under results/."""
    if folder.is_dir() and not folder.is_symlink() and folder.resolve().is_relative_to(results_root().resolve()):
        shutil.rmtree(folder)


def write_sets_index(plots: Path, title: str) -> Path | None:
    """plots/index.html (V164): every set drawn there, linked to each backend's index of it and to its statistics'
    summary.html (V199)."""
    rows = []
    for folder in sorted(p for p in plots.iterdir() if p.is_dir()) if plots.is_dir() else ():
        links = [f'<a href="{html.escape(folder.name)}/{b}/index.html">{b}</a>' for b in BACKENDS
                 if (folder / b / "index.html").is_file()]
        if links and (plots.parent / "statistics" / folder.name / "summary.html").is_file():
            links.append(f'<a href="../statistics/{html.escape(folder.name)}/summary.html">statistics</a>')
        if links:
            rows.append(f"<li>{html.escape(folder.name)}: {' · '.join(links)}</li>")
    if not rows:
        return None
    index = plots / "index.html"
    index.write_text("<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\"><title>" + html.escape(title)
                     + "</title><style>body{font-family:sans-serif;margin:1.5em}</style></head><body><h1>"
                     + html.escape(title) + "</h1>\n<ul>\n" + "\n".join(rows) + "\n</ul>\n</body></html>\n", encoding="utf-8")
    return index


def _tables(errand, groups: dict, outcomes: dict, say, who: str) -> int:
    """Each set's statistics (V160, V164): statistics/<set>/statistics.csv, cleared first, its bar graphs and
    summary; the rows written."""
    bars = statstable.bars()                                    # V162
    counted, images, tables = 0, 0, []
    for (_, set_), pages_ in groups.items():
        numbers = pages_[0].numbers
        if numbers is None:
            continue
        _clear(numbers)
        read = [p for p in pages_ if outcomes[str(p.config)][0]]
        scored = statstable.score_of(errand, set_)
        count, drawn = statstable.write_set(read, numbers, formats_of(errand.plot), bars,
                                            statstable.metric_names(errand.stats, scored), scored)
        if count:
            counted += count
            tables.append(numbers)
            images += drawn
    if counted:
        shown = tables[0] if len(tables) == 1 else tables[0].parent
        say(f"{who}: statistics of {counted} curve(s), {len(tables)} set(s), {images} bar graph(s) → {shown}")
    return counted


#: The page keys [stats] may set for its numbers (V168).
STATS_PAGE_KEYS = ("normalise", "void_empty", "min_entries", "auto_range", "range_pad")


def measured(errand, picked=None):
    """The run as its statistics read it (V168): [stats]'s page keys over [plot]'s, its objects the implicit
    figure's, the sets it measures (`picked`, else [stats].sets, else [plot].draw, else every set) as `draw`;
    its reference "curves" (or a filter, given to every set of axes) drawing no data."""
    from .sweep import named_sets
    recipe = dict(getattr(errand, "stats", None) or {})
    settings = dict(errand.plot or {})
    settings.update({k: recipe[k] for k in STATS_PAGE_KEYS if k in recipe})
    if "objects" in recipe:                             # a short name (d01-*) as a figure's objects take it
        settings["objects"] = [g if "/" in g else f"*/{g}" for g in recipe["objects"]]
    chosen_sets = picked or recipe.get("sets")
    if chosen_sets:
        settings["draw"] = list(chosen_sets)
    reference = recipe.get("reference", "data")
    if reference != "data":
        settings["use_data"] = False
    if isinstance(reference, dict):
        settings["sets"] = {name: {**table, "reference": reference}
                            if isinstance(table, dict) and ("pages" in table or "curves" in table) and "reference" not in table
                            else table for name, table in named_sets(settings.get("sets")).items()}
    return replace(errand, plot=settings)


def measure(errand, configuration, plans, say, picked=None) -> int:
    """`heimdall stats`'s pass (V168), its failures logged as a drawing's (V204): see _measure."""
    token = _LOGS.set(logs_of(plans) or _LOGS.get())
    try:
        return _measure(errand, configuration, plans, say, picked)
    finally:
        _LOGS.reset(token)


def _measure(errand, configuration, plans, say, picked=None) -> int:
    """The statistics alone (V168): the pages [plot] defines (as `measured` reads them), their documents in the
    working folder's stats/, read by Paint --ranges-only (numbers, no images); each set's statistics/<set>/,
    its bar graphs, and the statistic figures' pages. The pages Paint could not read."""
    if not errand.plot:
        return 0
    paint = apps_dir() / "Paint.exe"
    if not paint.exists():
        raise HeimdallError(f"{paint} is not built", hint="heimdall build --framework")
    numbers = measured(errand, picked)
    notes: list[str] = []
    todo = pages(numbers, configuration, plans, notes, documents="stats")
    wanted = (getattr(errand, "stats", None) or {}).get("objects")
    if wanted:                                          # a figure's own pages too: [stats].objects alone
        todo = [p for p in todo if p.overlay == "" and any(_matches(p.object, g) for g in wanted)]
    for note in dict.fromkeys(notes):
        say(f"stats: {note}")
    if not todo:
        say("stats: no complete point has a YODA product to measure")
        return 0
    outcomes = _paint(paint, [p.config for p in todo], ["--ranges-only"])
    failed = 0
    for page in todo:
        ok, why = outcomes[str(page.config)]
        if not ok:
            failed += 1
            say(f"stats: {page.name} could not be read: {why}")
    groups: dict[tuple, list[Page]] = {}
    for page in todo:
        groups.setdefault((page.root, page.set), []).append(page)
    if not _tables(numbers, groups, outcomes, say, "stats"):
        say("stats: no page has numbers (heat maps and unread pages have none)")
    read = [p for p in todo if outcomes[str(p.config)][0]]
    failed += _statistic_figures(numbers, configuration, read, plans, paint, say)
    return failed


def _statistic_figures(errand, configuration, todo: list, plans: list, paint: Path, say) -> int:
    """The statistic figures' pages (V160): from the numbers of these pages, drawn into statistics/<set>/figures/."""
    failed = 0
    for figure in (f for f in figures(errand) if f.kind == "statistic") if todo else ():
        drawn = statistic_pages(errand, figure, todo, plans[0].folders.pages / "statistic" / figure.name)
        if drawn:
            say(f"plot: statistic {figure.name}, {len(drawn)} page(s)")
            failed += _draw(errand, paint, drawn, f"{errand.name} · {figure.name}", say, table=False)
        else:
            say(f"plot: statistic {figure.name}: no drawn page of {', '.join(figure.objects)} has its numbers")
    return failed


def _draw(errand, paint: Path, todo: list[Page], title: str, say, table: bool = True) -> int:
    """Paint on these pages, then the other backends on the same pages, an index each, and the statistics of
    each set (V164: plots/<set>/<backend>/ and statistics/<set>/, cleared first)."""
    names = backends(errand.plot)
    others = [n for n in names if n != "root"]
    # One Paint for many pages (V64): it draws them (root) and writes each page's ranges beside its config
    # for the other backends (--ranges), or only the ranges (--ranges-only, a yoda-only run).
    mode = ["--ranges"] if others and "root" in names else ["--ranges-only"] if others else []
    failed = 0
    groups: dict[tuple, list[Page]] = {}                     # a set's pages: one folder each
    for page in todo:
        groups.setdefault((page.root, page.set), []).append(page)
    for root, _ in groups:
        for name in names:
            _clear(root / name)
    _with_statistics(paint, todo)                            # V160: a legend's numbers, before any backend draws
    outcomes = _paint(paint, [p.config for p in todo], mode, sets={str(p.config): p.set for p in todo})
    for page in todo:
        ok, why = outcomes[str(page.config)]
        if not ok:
            failed += 1
            say(f"plot: {page.name} failed: {why}")
        elif others:
            page.ranges = json.loads(page.config.with_name(page.config.name + ".ranges.json").read_text(encoding="utf-8"))
    if "root" in names:
        where = Path(os.path.commonpath([str(p.config.parent) for p in todo]))  # the documents' folder
        say(f"plot: {len(todo) - failed} of {len(todo)} page(s) drawn; configs in {where}")
    if table and chosen("statistics", True, True, (errand.plot,)) is not False:       # V160, V164: a set's own
        _tables(errand, groups, outcomes, say, "plot")
    if "root" in names:
        for (root, set_), pages_ in groups.items():             # V70: the ROOT pages' own index, a set's
            drawn = [(p.cell, p.rel, p.output) for p in pages_ if outcomes[str(p.config)][0]]
            if drawn:
                write_index(root / "root", f"{title} · {set_}" if set_ else title, drawn)
    if others and failed:
        todo = [p for p in todo if p.ranges]                 # a page Paint could not read has no ranges
    maps = [p for p in todo if p.document["page"].get("heatmap")]
    if others and maps:                                      # V87: Paint's alone, for now
        say(f"plot: {len(maps)} heat map page(s) drawn by Paint only ({', '.join(others)} draw 1D pages)")
        todo = [p for p in todo if not p.document["page"].get("heatmap")]
    for name in others:
        cells: dict[str, list[Page]] = {}                    # a page set: one folder of pages (a cell's, or a merged figure's in it)
        for page in todo:
            cells.setdefault(page.name.rpartition("/")[0], []).append(for_backend(page, name))
        module = backend(name)
        failed += module.draw(cells, errand.plot, say)
        if getattr(module, "INDEX", False):                  # a backend without its own index.html (V71)
            for (root, set_), pages_ in groups.items():
                drawn = [for_backend(p, name) for p in pages_ if p in todo]
                drawn = [p for p in drawn if any(p.output.with_name(f"{p.output.name}.{f}").is_file() for f in FORMATS)]
                if drawn:
                    write_index(root / name, f"{title} · {set_}" if set_ else title, [(p.cell, p.rel, p.output) for p in drawn])
    for root in {root.parent for root, set_ in groups if set_ and root is not None}:
        write_sets_index(root, title)                      # V164: plots/index.html, every set drawn there
    return failed


# ── heimdall plot FILE…: pages from any YODA or ROOT files, no errand file ────────────────────────────

def _is_plot_file(path: str) -> bool:
    return path.endswith((".yoda", ".yoda.gz", ".root"))


def _root_curves(path: Path, label: str | None) -> list[tuple[str, Path, dict[str, tuple[str, str | None]]]]:
    """The curves a ROOT file holds: one per point of a merged sweep (its paths tree has a point
    column), else one. Each: (label, file, {yoda path: (object, raw object or None)})."""
    import json

    import uproot
    with uproot.open(path) as file:
        keys = {k.split(";")[0] for k in file.keys()}
        if "paths" not in keys:                         # not App_yd2rt's: every 1D object, by its path
            found = {"/" + k: (k, None) for k in keys
                     if not k.startswith("RAW/") and "/RAW/" not in k and not k.endswith("__entries")
                     and file[k].classname.startswith(("TH1", "TGraph"))}
            return [(label or path.stem, path, found)]
        table = file["paths"].arrays(library="np")
        names = {}
        if "points.json" in keys:                        # a sweep: the legend is the swept values
            try:
                for entry in json.loads(file["points.json"].member("fTitle"))["points"]:
                    swept = [v["label"] for v in entry["values"].values() if v.get("swept")]
                    names[entry["name"]] = ", ".join(swept) or entry["name"]
            except (ValueError, KeyError, TypeError):
                pass
    points = table["point"] if "point" in table else [""] * len(table["root_path"])
    curves: dict[str, dict] = {}
    for point, rpath, ypath in zip(points, table["root_path"], table["yoda_path"]):
        ypath, rpath = str(ypath), str(rpath)
        if ypath.startswith(("/RAW/", "/TMP/")) or ypath in COUNTERS or ypath.endswith("]"):
            continue
        raw_path = f"{point}/RAW/{rpath[len(point) + 1:]}" if point else f"RAW/{rpath}"
        raw = raw_path if raw_path in keys and f"{raw_path}__entries" in keys else None
        curves.setdefault(str(point), {})[ypath] = (rpath, raw)
    if len(curves) == 1 and "" in curves:
        return [(label or path.stem, path, curves[""])]
    return [(names.get(p, p), path, objects) for p, objects in curves.items()]


def files(targets: list[str], outdir: Path | None, *, labels: list[str] | None = None, objects: list[str] = (),
          formats: list[str] = ("pdf", "png"), ratio: bool = False, style: str | None = None, say=print) -> int:
    """Overlay YODA and ROOT files through Paint: one page per object any of them holds, one curve
    per file (per point, for a merged sweep). YODA files are merged into one ROOT file first.
    `style` is a style file over base.toml, as [plot].root_style is for a run."""
    paths = [Path(t).resolve() for t in targets]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise HeimdallError(f"no such file: {', '.join(missing)}")
    if labels and len(labels) != len(paths):
        raise HeimdallError(f"--labels gives {len(labels)} names for {len(paths)} files")
    paint = apps_dir() / "Paint.exe"
    if not paint.exists():
        raise HeimdallError(f"{paint} is not built", hint="heimdall build --framework")
    key = hashlib.sha256("\n".join(map(str, paths)).encode()).hexdigest()[:12]
    work = cache_root() / "overlay" / key                       # its page documents: derived, rebuilt on demand
    outdir = (outdir or (results_root() / "plots" / paths[0].name.split(".")[0])).resolve()

    yodas = [(i, p) for i, p in enumerate(paths) if p.name.endswith((".yoda", ".yoda.gz"))]
    curves: list[tuple[str, Path, dict]] = [None] * len(paths)       # in the order given
    if yodas:
        tags = {i: f"f{i}" for i, _ in yodas}
        merged = merge({tags[i]: p for i, p in yodas}, work / "files.root", work / "files.sha256")
        for i, p in yodas:
            raws = raws_of(p)
            found = {o: (f"{tags[i]}/{root_name(o)}",
                         f"{tags[i]}/RAW/{root_name(o)}" if "/RAW" + o in raws else None)
                     for o in objects_of(p)}
            curves[i] = [(labels[i] if labels else p.name.split(".")[0], merged, found)]
    for i, p in enumerate(paths):
        if curves[i] is None:
            curves[i] = _root_curves(p, labels[i] if labels else None)
    curves = [c for group in curves for c in group]

    pages_of = list(dict.fromkeys(o for _, _, found in curves for o in found))
    if objects:
        pages_of = [o for o in pages_of if any(fnmatch.fnmatch(o, g) for g in objects)]
    if not pages_of:
        raise HeimdallError("no 1D object to draw" + (f" matches {list(objects)}" if objects else ""))
    settings = {"formats": list(formats), "ratio": ratio, "auto_range": True}
    layer = merge_style(house_style(), style_file(style) if style else {})   # the machine's and work dir's, then --style
    failed, written = 0, {}
    for path in pages_of:
        rel = path.strip("/").replace(":", "__")
        page, _ = page_settings(settings, path, rel, outdir / rel, False)
        document = {"page": page, "style": layer, "curve": [
            {"file": str(file), "object": found[path][0], **({"raw": found[path][1]} if found[path][1] else {}),
             "label": label} for label, file, found in curves if path in found]}
        config = work / f"{rel}.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(tomli_w.dumps(for_root(document)), encoding="utf-8")
        written[str(config)] = rel
    drawn = []
    for config, (ok, why) in _paint(paint, [Path(c) for c in written]).items():
        if not ok:
            failed += 1
            say(f"plot: {written[config]} failed: {why}")
        else:
            drawn.append(("", written[config], outdir / written[config]))
    if drawn:
        write_index(outdir, "heimdall plot", drawn)                 # V70
    say(f"plot: {len(pages_of) - failed} of {len(pages_of)} page(s), {len(curves)} curve(s) → {outdir}")
    return failed
