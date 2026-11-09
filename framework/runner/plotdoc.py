"""A run's plot document (V165): results/<A>/<E>/<R>/plot.toml, what every drawing reads (rank 4).

doc:plots. It holds two kinds of table:

* **what the run knows**, rewritten by every run of that folder: [source] (the config, the configuration, the
  folder, its tag from its record, Heimdall's revision, when), [axes] (the sweep's axes, plot_points, combine, the fixed values),
  [quantities.<q>] (its points, in its order, as an errand file's: points = [{ tag, value, label, style }], V172)
  and [members.<point>] (each point
  or combined group the pages draw: its value indices, its YODA under the folder, the identity it ran with,
  whether it was complete, the texts its tools give);
* **what the user chooses**, [plot] and [stats]: written once, from the errand file's (resolved: its imports,
  --set, root_style laid into [plot.style], the data file's path made absolute), and then kept. It changes
  only by `heimdall plot … --style-sync` or by hand; a run that finds the config's otherwise says so.

So a drawing needs this file and the folder's points/ alone: no errand file, snapshot, tool folder or stack.
`load` gives what plot.py reads of a run, a configuration and its members (Doc, DocConfiguration,
plot.Member), so the page code is the same for a drawing from a document as it was from a plan.
"""

from __future__ import annotations

import re
import datetime
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

from . import schema
from .config import Quantity, check_read_for
from .errors import HeimdallError, did_you_mean
from .paths import cache_root, records_root, results_root
from .plot import DEFAULT, Member, data_source, style_file, yoda_of
from .sweep import Listed, Point
from .record import FORMAT, check_format
from .tools import RunFolders
from .v3 import NAMES_HINT

FILE = "plot.toml"
#: The tables a run rewrites, and those it writes once and keeps (the user's).
KNOWN = ("source", "axes", "quantities", "members")
HEADER = ("# A run's plot document: what every drawing of this folder reads. [source], [axes], [quantities] and\n"
          "# [members] are the run's, rewritten by every run of the folder; [plot] and [stats] are yours: edit them to\n"
          "# restyle this run alone, or take the config's with heimdall plot <A>/<E>/<R> --style-sync <config>.\n\n")


@dataclass
class DocConfiguration:
    """A configuration as a drawing reads it: its key, label, axes and fixed values."""
    key: str
    label: str
    sweeps: list
    plot_points: list
    combine: list
    static: dict                  # quantity → "#N" (sweep.select's), the fixed values; the document writes the tag
    serial: int | None = None
    title: str = ""


@dataclass
class Doc:
    """An errand as a drawing reads it (plot.py's `errand`): its plot document."""
    path: Path                    # the plot.toml (the page code's messages name it)
    assignment: str
    name: str
    plot: dict
    stats: dict
    quantities: dict
    configuration: DocConfiguration
    source: dict = field(default_factory=dict)
    sweep_runs: bool = False
    score: dict = field(default_factory=dict)     # [score]: how its statistics are scored, copied from the config
    left: dict = field(default_factory=dict)      # member → why it is not drawn (a value its [quantities] no longer lists)

    @property
    def configurations(self) -> dict:
        return {self.configuration.key: self.configuration}

    def runs(self, wanted=None) -> list[str]:
        return [self.configuration.key]

    def sibling(self, ref: str):
        """Another configuration's plot document, for a compare figure (V165): (Doc, DocConfiguration, members),
        or None when it has none yet. `ref` is a configuration of the same errand file (its newest folder beside
        this one), a record (<A>/<E>/<R>), or "<config>:<cfg>" (that config's configuration, its newest)."""
        if ":" not in ref and ref.count("/") == 2:
            target = results_root() / ref / FILE
        elif ":" in ref:
            from .config import load as load_config
            from .tools import run_folders, serials_taken
            owner = load_config(ref.rsplit(":", 1)[0])
            configuration = owner.configuration(ref.rsplit(":", 1)[1])
            if configuration.serial_auto and (taken := serials_taken(owner, configuration)):
                configuration.serial = max(taken)
            target = path_of(run_folders(owner, configuration).results)
        else:
            import tomllib
            found = []
            for candidate in sorted(self.path.parent.parent.glob(f"*/{FILE}")):
                try:
                    source = tomllib.loads(candidate.read_text(encoding="utf-8")).get("source", {})
                except (OSError, tomllib.TOMLDecodeError):
                    continue
                if source.get("configuration") == ref and source.get("config") == self.source.get("config"):
                    found.append(candidate)
            target = found[-1] if found else None
        return load(target) if target is not None and target.is_file() else None


def path_of(results: Path) -> Path:
    return results / FILE


#: [source]'s keys before the Assignment/Errand names → today's.
OLD_SOURCE = {"project": "assignment", "run": "errand"}


def refuse_old_source(source: dict, path: Path) -> None:
    """A document written before the Assignment/Errand names ([source].project, [source].run): refused, with the command that
    rewrites it."""
    for old, new in OLD_SOURCE.items():
        if old in source:
            raise HeimdallError(f"[source].{old} is now [source].{new}", where=f"{path}: [source].{old}",
                                hint=NAMES_HINT)


# ── writing ─────────────────────────────────────────────────────────────────────────────────────

def _sweeps(configuration) -> list:
    out = []
    for entry in configuration.sweeps:
        if isinstance(entry, Listed):
            out.append({"listed": list(entry), "rows": [dict(row) for row in entry.rows]})
        else:
            out.append(entry if isinstance(entry, str) else list(entry))
    return out


#: The tables of a document that get a header of their own (V173): everything below one of these is written
#: inline under it, as an errand file is written by hand ("*": any key). The document's order: members last.
HEADERS = (("source",), ("axes",), ("quantities", "*"), ("plot",), ("plot", "data"), ("plot", "data", "map"),
           ("plot", "style"), ("plot", "sets", "*"), ("plot", "across", "*"), ("plot", "figures", "*"),
           ("plot", "looks", "*"), ("stats",), ("score",), ("from",), ("members", "*"))
ORDER = ("source", "from", "axes", "quantities", "plot", "stats", "score", "members")
#: A member's keys in the order a document writes them: what it is first, its value indices after.
MEMBER_ORDER = ("index", "identity", "complete", "planned", "events", "stage", "yoda", "choice", "values", "texts")


def _key(k: str) -> str:
    import re
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else tomli_w.dumps({k: 0}).split(" = ")[0]


def _inline(value) -> str:
    """A value as an inline TOML value: a table { k = v, … }, a list [a, b], a string or number as tomli_w writes it."""
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_key(k)} = {_inline(v)}" for k, v in value.items()) + " }" if value else "{}"
    if isinstance(value, list):
        return "[" + ", ".join(_inline(v) for v in value) + "]"
    return tomli_w.dumps({"x": value})[len("x = "):].rstrip("\n")


def _matches_path(path: tuple, pattern: tuple) -> bool:
    return len(path) == len(pattern) and all(q == "*" or p == q for p, q in zip(path, pattern))


def _kind(path: tuple) -> str:
    """"header" (a table of its own), "collection" (a table whose entries are), or "inline"."""
    if any(_matches_path(path, h) for h in HEADERS):
        return "header"
    if any(len(h) > len(path) and _matches_path(path, h[:len(path)]) for h in HEADERS):
        return "collection"
    return "inline"


def _lines(key: str, value) -> list[str]:
    """`key = value`, a list of tables one entry a line (a quantity's points, a set's curves)."""
    if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
        return [f"{_key(key)} = ["] + [f"  {_inline(v)}," for v in value] + ["]"]
    return [f"{_key(key)} = {_inline(value)}"]


def _tags(table: dict) -> list[str]:
    """A document quantity's tags, in its points' order."""
    return [str(row.get("tag")) for row in table.get("points", [])] if "points" in table \
        else [str(t) for t in table.get("tags", [])] or [str(v) for v in table.get("values", [])]


def by_tag(data: dict) -> dict:
    """A document whose members name their values by tag, and its fixed values too, not by their place in
    [quantities.<q>].points: a point moved, added or taken out of the list leaves every other member's value as it
    was. A value already a tag, or of a quantity the document does not list, stays as it is."""
    tags = {q: _tags(t) for q, t in (data.get("quantities") or {}).items() if isinstance(t, dict)}

    def named(values: dict) -> dict:
        return {q: tags[q][i] if isinstance(i, int) and not isinstance(i, bool) and q in tags and 0 <= i < len(tags[q]) else i
                for q, i in values.items()}

    for entry in (data.get("members") or {}).values():
        for key in ("choice", "values"):
            if isinstance(entry.get(key), dict):
                entry[key] = named(entry[key])
    fixed = (data.get("axes") or {}).get("fixed")
    if isinstance(fixed, dict):
        for q, mark in list(fixed.items()):
            if isinstance(mark, str) and mark[:1] == "#" and mark[1:].isdigit() and q in tags \
                    and 0 <= int(mark[1:]) - 1 < len(tags[q]):
                fixed[q] = tags[q][int(mark[1:]) - 1]
    return data


def dumps(data: dict) -> str:
    """A document as TOML (V172, V173): a header for each of HEADERS' tables, everything below it inline (a member's
    choice and values, a set's pages and curves, a quantity's points a line each), the tables in ORDER (members last);
    its members' values and its fixed values by tag (by_tag), whichever writer made it."""
    data = by_tag(data)
    out: list[list[str]] = []

    def walk(path: tuple, table: dict) -> None:
        here = [f"[{'.'.join(_key(k) for k in path)}]"]
        nested = []
        items = list(table.items())
        if len(path) == 2 and path[0] == "members":
            items.sort(key=lambda kv: MEMBER_ORDER.index(kv[0]) if kv[0] in MEMBER_ORDER else len(MEMBER_ORDER))
        for k, v in items:
            if isinstance(v, dict) and _kind(path + (k,)) != "inline":
                nested.append((k, v))
            else:
                here += _lines(k, v)
        if len(here) > 1 or (_kind(path) == "header" and not nested):
            out.append(here)
        for k, v in nested:
            walk(path + (k,), v)

    for top in sorted(data, key=lambda k: (ORDER.index(k) if k in ORDER else len(ORDER), k)):
        value = data[top]
        if isinstance(value, dict) and _kind((top,)) != "inline":
            walk((top,), value)
        else:
            out.append(_lines(top, value))
    return "\n\n".join("\n".join(block) for block in out) + "\n"


def _rows(values: list, tags: list, labels: list, styles: list) -> list[dict]:
    """A quantity's points as an errand file writes them (V172): { tag, value, label }, and style where it has one."""
    return [{"tag": str(tag), "value": value, "label": label, **({"style": dict(style)} if style else {})}
            for tag, value, label, style in zip(tags, values, labels, styles or [{}] * len(values))]


def _quantity(q) -> dict:
    from .sweep import label_of, tag_of
    indices = range(len(q.values))
    out = {"points": _rows(list(q.values), [tag_of(q, i) for i in indices], [label_of(q, i) for i in indices], list(q.styles))}
    if q.exclude:
        out["exclude"] = list(q.exclude)
    if q.silent:
        out["silent"] = True
    return out


def _quantity_of(name: str, table: dict) -> Quantity:
    """A document's [quantities.<q>]: its points (V172), or the parallel lists a document written before had."""
    if "points" in table:
        rows = list(table["points"])
        styles = [dict(r.get("style", {})) for r in rows]
        return Quantity(name, [r.get("value") for r in rows], tags=[str(r["tag"]) for r in rows],
                        labels=[r.get("label", r["tag"]) for r in rows], styles=styles if any(styles) else [],
                        exclude=list(table.get("exclude", [])), silent=bool(table.get("silent", False)))
    return Quantity(name, list(table.get("values", [])), tags=list(table.get("tags", [])),
                    labels=list(table.get("labels", [])), styles=list(table.get("styles", [])),
                    exclude=list(table.get("exclude", [])), silent=bool(table.get("silent", False)))


def needs_upgrade(path: Path) -> bool:
    """A document whose quantities are parallel lists (V172), whose members name values by their place, or that has
    a table deeper than HEADERS' own, a member's choice or a set's pages under a header of its own, or [[…]] tables (V173)."""
    import re
    import tomllib
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    if any("points" not in q for q in data.get("quantities", {}).values()):
        return True
    if any(isinstance(i, int) for m in (data.get("members") or {}).values() for key in ("choice", "values")
           for i in (m.get(key) or {}).values()):
        return True                                          # its members' values by place, not by tag
    for line in text.splitlines():
        found = re.fullmatch(r"\[\[?(.+?)\]\]?\s*", line)
        if found:
            parts = tuple(p.strip('"') for p in re.findall(r'"[^"]*"|[^.]+', found[1]))
            if line.startswith("[[") or _kind(parts) == "inline":
                return True
    return False


def upgrade(path: Path) -> bool:
    """A document written with its quantities as parallel lists (values, tags, labels, styles), or with tables
    deeper than HEADERS' own, rewritten as dumps writes it (V172, V173), nothing in it changed; whether it was."""
    import tomllib
    if not needs_upgrade(path):
        return False
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    tables = data.get("quantities", {})
    for name, table in tables.items():
        if "points" not in table:
            tables[name] = _quantity(_quantity_of(name, table))
    header = HEADER if "members" in data else ACROSS_HEADER
    partial = path.with_name(path.name + ".partial")
    partial.write_text(header + dumps(data), encoding="utf-8")
    partial.replace(path)
    return True


def _member(plan) -> dict:
    """A plan's or a recorded member's entry: what the pages need of it. A planned point complete with other
    inputs than its plan has now (a card changed, the stack rebuilt) is drawn as recorded (V158): its entry
    names the identity it ran with, and `planned`, the one it would run with now."""
    from .record import recorded_identity
    yoda = yoda_of(plan)
    planned = None
    if isinstance(plan, Member):
        identity = plan.identity or ""
        complete, texts = plan.recorded is not None and plan.recorded == plan.identity, dict(plan.texts)
    else:
        made = recorded_identity(plan)
        identity, complete = made or plan.identity or "", made is not None
        if made is not None and made == plan.identity and getattr(plan, "library", ""):
            identity = plan.library          # a library point's .complete holds its key, which a reader compares with this
        planned = plan.identity if made is not None and made != plan.identity else None
        texts = {k: v for step in plan.rendered.values() for k, v in step.texts.items()}
    point = plan.point
    entry = {"index": point.index, "choice": dict(point.choice), "values": dict(plan.values),
             "identity": identity, "complete": bool(complete and yoda is not None and yoda.is_file())}
    if planned:
        entry["planned"] = planned
    events = getattr(plan, "events", 0) or _provenance_events(plan.folders, point.name)
    if events:
        entry["events"] = int(events)
    if point.stage:
        entry["stage"] = point.stage
    if yoda is not None:
        results = plan.folders.results
        entry["yoda"] = str(yoda.relative_to(results)) if yoda.is_relative_to(results) else str(yoda)
    if texts:
        entry["texts"] = texts
    return entry


def _provenance_events(folders, name: str) -> int:
    """The events a point ran with, as its provenance says (0 when none)."""
    import json
    path = folders.points / name / "provenance.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return 0
    check_format(data, path)
    value = data.get("events", 0)
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def from_manifest(record: Path, errand, configuration) -> Path:
    """A plot document for a record that has no snapshot (V165), from its points.json alone: each point's tags,
    labels and values (as they ran, whatever the config says now), its products, identity and completion, and
    its events (provenance); its axes the quantities its points swept, its plot_points points.json's. Only
    [plot] and [stats] come from the config, `errand` (its configuration's)."""
    import json
    from .record import run_labels, run_tag
    data = json.loads((record / "points.json").read_text(encoding="utf-8"))
    check_format(data, record / "points.json")
    rel = record.relative_to(records_root())
    folders = _folders(results_root() / rel, errand.assignment)
    names: dict[str, dict] = {}                                  # quantity → tag → (label, value)
    swept: list[str] = []
    for entry in data.get("points", []):
        for q, value in entry.get("values", {}).items():
            names.setdefault(q, {}).setdefault(str(value.get("tag")), (value.get("label", value.get("tag")), value.get("value")))
            if value.get("swept") and q not in swept:
                swept.append(q)
    quantities = {}
    for q, tags in names.items():
        live = errand.quantities.get(q)
        styles = [live.styles[live.tags.index(tag)] if live and live.styles and tag in live.tags else {} for tag in tags] \
            if live is not None and live.styles else []
        quantities[q] = {"points": _rows([v for _, v in tags.values()], list(tags), [l for l, _ in tags.values()],
                                         styles if any(styles) else [])}
    order = {q: list(tags) for q, tags in names.items()}
    members = {}
    for entry in data.get("points", []):
        name = entry["name"]
        values = {q: order[q].index(str(v.get("tag"))) for q, v in entry.get("values", {}).items()}
        yoda = next((Path(p) for p in entry.get("products", {}).values() if str(p).endswith(".yoda")), None)
        marker = folders.points / name / ".complete"
        made = marker.read_text(encoding="utf-8").strip() if marker.is_file() else None
        item = {"index": int(entry.get("index", 0)), "choice": {q: i for q, i in values.items() if q in swept},
                "values": values, "identity": entry.get("identity", ""),
                "complete": bool(made is not None and made == entry.get("identity") and yoda is not None and yoda.is_file())}
        if yoda is not None:
            item["yoda"] = str(yoda.relative_to(folders.results)) if yoda.is_relative_to(folders.results) else str(yoda)
        if entry.get("texts"):
            item["texts"] = dict(entry["texts"])
        if (events := _provenance_events(folders, name)):
            item["events"] = events
        members[name] = item
    head = record.name.split("_", 1)
    fixed = {q: f"#{order[q].index(str(v.get('tag'))) + 1}" for q, v in data["points"][0]["values"].items() if q not in swept} \
        if data.get("points") else {}
    made = {"source": {"format": FORMAT, "config": data.get("config", "") or _config_name(data.get("config_file", "")),
                       "configuration": data.get("configuration", configuration.key),
                       "label": head[1] if len(head) == 2 and head[0].isdigit() else record.name, "title": "",
                       "errand": data.get("run", errand.name), "assignment": data.get("project", errand.assignment), "folder": str(rel),
                       **({"serial": int(head[0])} if head[0].isdigit() else {}),
                       **({"tag": tag} if (tag := run_tag(record)) else {}),
                       **({"labels": labels} if (labels := run_labels(record)) else {}), "from": "points.json",
                       "written": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},
            "axes": {"vary": swept, "plot_points": list(data.get("plot_points", [])), "combine": [], "fixed": fixed},
            "quantities": quantities, "members": members}
    target = path_of(folders.results)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(HEADER + dumps(made), encoding="utf-8")
    _, kept, loaded = load(target)
    plot, stats = chosen_of(errand, kept, loaded, picks=configuration)
    write_chosen(target, plot, stats)
    return target


def _config_name(path: str) -> str:
    from .paths import configs_root
    try:
        return str(Path(path).resolve().relative_to(configs_root().resolve()).with_suffix(""))
    except (ValueError, OSError):
        return Path(path).stem


def chosen_of(errand, configuration, members: list, picks=None) -> tuple[dict, dict]:
    """The errand file's [plot] and [stats] as a document keeps them: root_style laid into [plot.style], the data
    file's path absolute (Rivet's own data named as it is); its sets named (V167), the totality set first
    (sweep.totality, from these members and `configuration`'s axes: the run's own, unless the config defines
    one), and [errand].plot's and [errand].stats' lists (of `picks`, the config's configuration; else
    `configuration`) as `draw` and `[stats].sets`."""
    picks = picks if picks is not None else configuration
    from .sweep import TOTALITY, named_sets, totality
    plot = {k: v for k, v in (errand.plot or {}).items() if k not in (ACROSS, FROM)}   # the Name level's (V169, V224)
    if plot:
        sets = named_sets(plot.get("sets"))
        plot["sets"] = {TOTALITY: totality(configuration, members), **sets} if TOTALITY not in sets else sets
        picked = getattr(picks, "draw", True)
        if isinstance(picked, list) and "draw" not in plot:
            plot["draw"] = list(picked)
    named = plot.pop("root_style", DEFAULT)
    if named not in (DEFAULT, None, schema.NATIVE):
        from .plot import merge_style
        plot["style"] = merge_style(style_file(named, errand.assignment, f"{errand.path}: [plot].root_style", errand.folder), plot.get("style", {}))
    data = plot.get("data")
    if isinstance(data, dict) and isinstance(data.get("file"), str) and not data["file"].startswith("rivet:"):
        plot["data"] = {**data, "file": str(data_source(data["file"], errand))}
    stats = dict(getattr(errand, "stats", None) or {})
    measured = getattr(picks, "measure", True)
    if isinstance(measured, list) and "sets" not in stats:
        stats["sets"] = list(measured)
    return plot, stats


def known(errand, configuration, members: list) -> dict:
    """The tables a run rewrites: [source], [axes], [quantities], [members]."""
    from .quantities import static_values
    from .record import config_name, run_labels, run_tag
    names = {q for m in members for q in (*m.values, *m.point.choice)}      # a combined group's: its choice alone
    names |= {q for e in configuration.sweeps for q in ([e] if isinstance(e, str) else e)}   # every axis, combined too
    static = static_values(errand, configuration) if hasattr(configuration, "tools") else {}
    from .paths import heimdall_root
    from .record import git_state
    revision = git_state(heimdall_root()).get("revision", "")
    results = members[0].folders.results if members else None
    tag = run_tag(members[0].folders.record) if members else None             # V223: the record's, the truth
    labels = run_labels(members[0].folders.record) if members else {}
    return {
        "source": {"format": FORMAT, "config": config_name(errand) if hasattr(errand, "imported") else errand.source.get("config", ""),
                   "configuration": configuration.key, "label": configuration.label,
                   "title": getattr(configuration, "title", "") or "",
                   "errand": errand.name, "assignment": errand.assignment,
                   "folder": str(results.relative_to(results_root())) if results and results.is_relative_to(results_root()) else "",
                   **({"serial": configuration.serial} if configuration.serial is not None else {}),
                   **({"tag": tag} if tag else {}),
                   **({"labels": labels} if labels else {}),
                   **({"heimdall": revision} if revision else {}),
                   "written": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},
        "axes": {"vary": _sweeps(configuration), "plot_points": list(configuration.plot_points),
                 "combine": list(configuration.combine),
                 "fixed": {q: f"#{i + 1}" for q, i in static.items()} if static else dict(getattr(configuration, "static", {}))},
        "quantities": {q: _quantity(errand.quantities[q]) for q in errand.quantities if q in names},
        "members": {m.point.name: _member(m) for m in members},
    }


def write(errand, configuration, members: list) -> tuple[Path | None, list[str]]:
    """results/<A>/<E>/<R>/plot.toml (V165) for these members (the points, or the combined groups): what the run knows
    rewritten, what the user chose kept (written from the config the first time). Returns the file and what to
    say: the config's [plot] differing from the document's kept one."""
    if not members:
        return None, []
    check_read_for(errand, configuration)                                       # V179: its own data, not another's
    target = path_of(members[0].folders.results)
    made = known(errand, configuration, members)
    notes = []
    plot, stats = chosen_of(errand, configuration, members)
    score = dict(getattr(errand, "score", None) or {})
    if target.is_file():
        import tomllib
        try:
            kept = tomllib.loads(target.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise HeimdallError(f"the plot document cannot be read: {error}", where=str(target),
                           hint="fix it, or remove it: the next run writes it again from the config") from None
        if "plot" in kept or "stats" in kept:
            if (kept.get("plot", {}), kept.get("stats", {})) != (plot, stats):
                rel = made["source"]["folder"] or str(target.parent)
                notes.append(f"the config's [plot] differs from {rel}/{FILE}'s, which is drawn: heimdall plot {rel} "
                             f"--style-sync {made['source']['config']} takes the config's")
            plot, stats = kept.get("plot", {}), kept.get("stats", {})
        if "score" in kept:
            score = kept["score"]                                               # the user's, as [plot] and [stats] are
    made["plot"] = plot
    if stats:
        made["stats"] = stats
    if score:
        made["score"] = score
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    partial.write_text(HEADER + dumps(made), encoding="utf-8")
    partial.replace(target)
    return target, notes


def write_chosen(target: Path, plot: dict, stats: dict, wanted: dict | None = None, score: dict | None = None) -> None:
    """A document's [plot] and [stats] replaced (--style-sync), its [score] when `score` is given, and a Name level's
    [from] when `wanted` (V224); what the run knows left as it is."""
    import tomllib
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    if wanted is not None:
        data["from"] = dict(wanted)
    data["plot"] = plot
    data.pop("stats", None)
    if stats:
        data["stats"] = stats
    if score is not None:
        data.pop("score", None)
        if score:
            data["score"] = dict(score)
    partial = target.with_name(target.name + ".partial")
    partial.write_text((ACROSS_HEADER if "members" not in data and "from" in data else HEADER) + dumps(data), encoding="utf-8")
    partial.replace(target)


def write_tag(target: Path, tag: str | None, labels: dict | None = None) -> None:
    """A document's [source].tag and [source].labels set from its record's (None, {}: removed), the rest left as it is
    (`heimdall tag`)."""
    import tomllib
    try:
        data = tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HeimdallError(f"the plot document cannot be read: {error}", where=str(target),
                            hint="fix it, or remove it: the next run writes it again from the config") from None
    source = data.setdefault("source", {})
    source.pop("tag", None)
    source.pop("labels", None)
    if tag:
        source["tag"] = tag
    if labels:
        source["labels"] = dict(labels)
    partial = target.with_name(target.name + ".partial")
    partial.write_text(HEADER + dumps(data), encoding="utf-8")
    partial.replace(target)


# ── reading ─────────────────────────────────────────────────────────────────────────────────────

def _folders(results: Path, assignment: str) -> RunFolders:
    """A document's folders: records/ and .cache/ where its folder of results/ says; a folder copied elsewhere
    has its working files in .cache/<A>/plots/elsewhere/<its path's hash>/."""
    results = results.resolve()
    root = results_root().resolve()
    if results.is_relative_to(root) and len(results.relative_to(root).parts) == 3:
        rel = results.relative_to(root)
        return RunFolders(assignment, records_root() / rel, results, cache_root() / rel.parts[0] / "plots" / Path(*rel.parts[1:]))
    key = hashlib.sha256(str(results).encode()).hexdigest()[:12]
    return RunFolders(assignment, results / ".records", results, cache_root() / assignment / "plots" / "elsewhere" / key)


def _sweeps_of(entries: list) -> list:
    out = []
    for entry in entries:
        if isinstance(entry, dict):
            out.append(Listed(entry["listed"], [dict(row) for row in entry["rows"]]))
        else:
            out.append(entry)
    return out


def load(path: Path, folders: RunFolders | None = None) -> tuple[Doc, DocConfiguration, list[Member]]:
    """A plot document: the run, configuration and members a drawing reads. A member is complete when its
    record's .complete holds the identity the document names (records/ there), else as the document says.
    `folders`: draw into these instead (pages, numbers, working files, logs); each member's YODA and
    completeness are still read from the document's own, which nothing writes then."""
    import tomllib
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise HeimdallError(f"no plot document: {error.strerror}", where=str(path),
                       hint="a run writes it; heimdall migrate --plot-docs writes one for a run made before") from None
    except tomllib.TOMLDecodeError as error:
        raise HeimdallError(f"the plot document cannot be read: {error}", where=str(path)) from None
    if "members" not in data and "from" in data:             # the runs of an errand file together (V169)
        return load_across(path, data, folders)
    missing = [t for t in ("source", "axes", "members") if t not in data]
    if missing:
        raise HeimdallError(f"the plot document has no [{missing[0]}]", where=str(path),
                       hint="a run writes it whole; heimdall migrate --plot-docs writes it again")
    source, axes = data["source"], data["axes"]
    check_format(source, path)
    refuse_old_source(source, path)
    quantities = {name: _quantity_of(name, table) for name, table in data.get("quantities", {}).items()}
    places = {name: {tag: i for i, tag in enumerate(_tags(table))} for name, table in data.get("quantities", {}).items()}
    fixed = {q: f"#{places[q][mark] + 1}" if isinstance(mark, str) and q in places and mark in places[q] else mark
             for q, mark in dict(axes.get("fixed", {})).items()}
    configuration = DocConfiguration(source.get("configuration", ""), source.get("label", source.get("configuration", "")),
                                     _sweeps_of(axes.get("vary", [])), list(axes.get("plot_points", [])),
                                     list(axes.get("combine", [])), fixed, source.get("serial"),
                                     source.get("title", ""))
    doc = Doc(path, source.get("assignment", ""), source.get("errand", ""), dict(data.get("plot", {})), dict(data.get("stats", {})),
              quantities, configuration, dict(source),
              score=dict(data.get("score", {})))
    own = _folders(path.parent, doc.assignment)
    members = []
    for name, entry in data["members"].items():
        values, choice, gone = _placed(entry.get("values", {}), places), _placed(entry.get("choice", {}), places), None
        for q, i in {**values, **choice}.items():
            if isinstance(i, str):
                gone = f"its {q} {i} is not in [quantities.{q}]"
                break
        if gone:
            doc.left[name] = gone
            continue
        yoda = entry.get("yoda")
        yoda = (own.results / yoda if not Path(yoda).is_absolute() else Path(yoda)) if yoda else None
        marker = own.points / name / ".complete"
        if own.record.is_dir():
            recorded = marker.read_text(encoding="utf-8").strip() if marker.is_file() else None
        else:                                                # copied away from its records: as it says
            recorded = entry.get("identity", "") if entry.get("complete") else None
        point = Point(index=int(entry.get("index", 0)), name=name, choice=choice, stage=entry.get("stage", ""))
        context = {**({"planned": entry["planned"]} if entry.get("planned") else {}),
                   **({"events": int(entry["events"])} if entry.get("events") else {})}
        members.append(Member(point, values, folders or own, yoda, dict(entry.get("texts", {})), context,
                              entry.get("identity", ""), recorded))
    check_indices(path, quantities, members)
    return doc, configuration, members


def _placed(values: dict, places: dict) -> dict:
    """A member's values as indices into its document's [quantities]: a tag by its place there now (a tag the list no
    longer has stays a string, for load to leave the member out), an index (a document written before tags) as it is."""
    return {q: places[q].get(i, i) if isinstance(i, str) and q in places else i for q, i in values.items()}


def check_indices(path: Path, quantities: dict, members: list) -> None:
    """Every member's value is one of its quantity's points: a document written before tags names a value by its place
    in [quantities.<q>].points, so a point taken out of its list would move every later one's label."""
    for member in members:
        for name, index in member.values.items():
            quantity = quantities.get(name)
            if quantity is not None and not (isinstance(index, int) and 0 <= index < len(quantity.values)):
                raise HeimdallError(f"member {member.point.name} has {name} #{index + 1 if isinstance(index, int) else index}, "
                                    f"but [quantities.{name}] has {len(quantity.values)} point(s)", where=str(path),
                                    hint="this document names its members' values by place: put the point back, then "
                                         "heimdall migrate --plot-docs --apply names them by tag, and a point taken out leaves "
                                         "its members out of the drawing")


def find(name: str) -> Path | None:
    """The plot document a command's argument names: a record (<A>/<E>/<R>), a path into records/ or
    results/ (or into a folder of results/), or any folder holding a plot.toml. None when it names none."""
    path = Path(name).expanduser()
    if path.is_dir() and (path / FILE).is_file():
        return (path / FILE).resolve()
    if path.is_file() and path.name == FILE:
        return path.resolve()
    from .record import record_of
    try:
        found = record_of(name, need_snapshot=False)
    except HeimdallError:
        return None
    if found is None:
        return None
    doc = results_root() / found.relative_to(records_root()) / FILE
    return doc if doc.is_file() else None


# ── the runs of an errand file together (V169): results/<A>/<E>/plot.toml ─────────────────────────────────

#: An errand file's sets across its runs, [plot.across.<set>] (V169).
ACROSS = "across"
#: [plot.across_from] (V224): the errand file's [from], its keys the schema's table of that name.
FROM = "across_from"
#: [from]'s keys when the config gives none (V169).
FROM_DEFAULT = {"runs": ["*"], "prefer": "last"}
#: An untagged run's @tag among tagged ones: its label (its value is "").
UNTAGGED = "untagged"
NO_LABEL = "unlabelled"            # a Run without a label among Runs with it: its tag there (its label "–")
UNSET = "unset"                    # a quantity a Run never names: its tag there, never guessed (across-axes)
UNSET_LABEL = "not set"


def run_label(folder: str, tag: str = "") -> str:
    """How a Run is named where Runs meet: `NN·<its tag, else its folder's label>` (03·nlo, 04·pdfs), its serial the folder's
    leading digits (one with none is named by its tag or folder alone). Always shown, so a Run added later changes no label."""
    found = re.match(r"(\d+)[_.-]?(.*)$", folder)
    serial, rest = (found.group(1), found.group(2)) if found else ("", folder)
    return f"{serial}·{tag or rest or folder}" if serial else (tag or folder)
ACROSS_HEADER = ("# The runs of an errand file together: their members, drawn into this folder's plots/<set>/ and\n"
                 "# statistics/<set>/. [from] says which runs (globs of their folders) and which point a duplicate is;\n"
                 "# [plot] and [stats] are yours (from the config's [plot] and its [plot.across] sets, by a run or --style-sync).\n\n")


def across_path(assignment: str, errand: str) -> Path:
    return results_root() / assignment / errand / FILE


def count_tag(events: int) -> str:
    """10000000 → 10M, 100000 → 100k, 1500000 → 1.5M: an event count as a tag."""
    for unit, size in (("G", 10 ** 9), ("M", 10 ** 6), ("k", 10 ** 3)):
        if events >= size and events % (size // 10) == 0:
            value = events / size
            return f"{value:g}{unit}"
    return str(events)


def across_chosen(errand) -> tuple[dict, dict]:
    """The Name level's [plot] and [stats], from an errand file: its [plot] (resolved as a run's) with its
    [plot.across] sets as the sets, and its [stats]."""
    from .sweep import named_sets
    plot = {k: v for k, v in (errand.plot or {}).items()}
    named = plot.pop("root_style", DEFAULT)
    if named not in (DEFAULT, None, schema.NATIVE):
        from .plot import merge_style
        plot["style"] = merge_style(style_file(named, errand.assignment, f"{errand.path}: [plot].root_style", errand.folder), plot.get("style", {}))
    data = plot.get("data")
    if isinstance(data, dict) and isinstance(data.get("file"), str) and not data["file"].startswith("rivet:"):
        plot["data"] = {**data, "file": str(data_source(data["file"], errand))}
    plot["sets"] = named_sets(plot.pop(ACROSS, None))
    plot.pop(FROM, None)                                    # the document's [from] (from_of)
    plot.pop("draw", None)
    figures = {k: v for k, v in (plot.get("figures") or {}).items() if not (isinstance(v, dict) and v.get("class") == "compare")}
    if "figures" in plot:                                   # a compare figure is one run's view of others: not here
        plot["figures"] = figures
    return plot, dict(getattr(errand, "stats", None) or {})


def from_of(errand) -> dict:
    """The Name level's [from] as an errand file gives it (V224): [plot.across_from] over the defaults (every run, the
    later of two the same point)."""
    return {**FROM_DEFAULT, **dict((errand.plot or {}).get(FROM) or {})}


def from_in(target: Path) -> dict:
    """The [from] a Name level's document holds."""
    import tomllib
    try:
        return dict(tomllib.loads(target.read_text(encoding="utf-8")).get("from", {}))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HeimdallError(f"the plot document cannot be read: {error}", where=str(target)) from None


def write_across(errand) -> tuple[Path | None, bool]:
    """results/<A>/<E>/plot.toml for an errand file with [plot.across] sets: written when there is none (what the
    user chooses is theirs after: --style-sync rewrites it). Returns it and whether it was written now."""
    if not (errand.plot or {}).get(ACROSS):
        return None, False
    target = across_path(errand.assignment, errand.name)
    if target.is_file():
        return target, False
    from .record import config_name
    plot, stats = across_chosen(errand)
    made = {"source": {"format": FORMAT, "config": config_name(errand), "errand": errand.name, "assignment": errand.assignment, "level": "name",
                       "written": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},
            "from": from_of(errand), "plot": plot}
    if stats:
        made["stats"] = stats
    if getattr(errand, "score", None):
        made["score"] = dict(errand.score)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(ACROSS_HEADER + dumps(made), encoding="utf-8")
    return target, True


def load_across(path: Path, data: dict, into: RunFolders | None = None) -> tuple[Doc, DocConfiguration, list[Member]]:
    """The Name level (V169): every run's plot document beside it ([from].runs, globs of their folders), their
    members together, each named <R>__<point>, its quantities' indices by tag across the runs, with the
    attributes @run (its folder), @events (its event count, a tag like 10M), @configuration and, when a run is
    tagged, @tag (its [source].tag; "" for an untagged one, labelled untagged; V224); @events and @tag count as
    axes (pages and labels may follow them), the others are named to be used. A point two runs of one tag have
    (every tag and the event count the same) is the later run's with prefer = "last" (said), both with "all".
    [from].ignore (V224): quantities (or @events) that are no axis: out of every member's choice and of what makes
    two points the same, kept in its values; each holds one value within a run."""
    import fnmatch
    from dataclasses import replace
    source, wanted = dict(data.get("source", {})), dict(data.get("from", {}))
    refuse_old_source(source, path)
    schema.check(wanted, FROM, f"{path}: [from]")             # as [plot.across_from] is (V224)
    globs, prefer = list(wanted.get("runs", FROM_DEFAULT["runs"])), wanted.get("prefer", FROM_DEFAULT["prefer"])
    ignored = list(dict.fromkeys(wanted.get("ignore", [])))
    folder = path.parent
    runs = [d for d in sorted(folder.iterdir()) if d.is_dir() and (d / FILE).is_file() and any(fnmatch.fnmatchcase(d.name, g) for g in globs)]
    if not runs:
        raise HeimdallError(f"no Run beside {path} has a plot document", where=f"{path}: [from].runs",
                       hint="heimdall migrate --plot-docs writes them; runs = [\"04_*\", …] names them")
    loaded = [(d.name, *load(d / FILE)) for d in runs]
    usual = {}                                               # a run's event count: what its members ran with
    for run_name, doc, _, own in loaded:
        seen_counts = [n for n in (_member_events(doc, m) for m in own) if n]
        usual[run_name] = max(set(seen_counts), key=seen_counts.count) if seen_counts else 0
    tags: dict[str, list] = {}
    for _, doc, _, _ in loaded:
        for name, q in doc.quantities.items():
            have = tags.setdefault(name, [])
            for i in range(len(q.values)):
                tag = q.tags[i] if q.tags else str(q.values[i])
                if tag not in [t for t, *_ in have]:
                    have.append((tag, q.labels[i] if q.labels else tag, q.values[i], q.styles[i] if q.styles else {}))
    lacking: dict[str, str] = {}                             # a quantity some Run never names: its tag there, "unset"
    for name, have in tags.items():
        if any(name not in m.values for _, _, _, own in loaded for m in own):
            blank = UNSET
            while blank in [t for t, *_ in have]:            # a value tagged "unset" keeps its name
                blank += "_"
            have.append((blank, UNSET_LABEL, blank, {}))
            lacking[name] = blank
    for name in ignored:                                     # V224: a quantity of the runs, or @events
        if name != "@events" and name not in tags:
            allowed = [*tags, "@events"]
            raise HeimdallError(f"[from].ignore names '{name}', which is no quantity of the Runs", where=f"{path}: [from].ignore",
                           hint=did_you_mean(name, allowed) or f"it takes: {', '.join(allowed)}")
    counts = sorted({n for run_name, doc, _, own in loaded for n in
                     [_member_events(doc, m) or usual[run_name] for m in own] if n})
    configurations = list(dict.fromkeys(conf.key for _, _, conf, _ in loaded))
    labels = {conf.key: conf.label for _, _, conf, _ in loaded}
    records = records_root() / folder.relative_to(results_root()) if folder.is_relative_to(results_root()) else None
    run_tags = {run_name: _tag_of(doc, records / run_name if records else None) for run_name, doc, _, _ in loaded}
    tagged = list(dict.fromkeys(run_tags.values())) if any(run_tags.values()) else []
    run_labels_ = {run_name: _labels_of(doc, records / run_name if records else None) for run_name, doc, _, _ in loaded}
    label_keys = sorted({k for found in run_labels_.values() for k in found})
    for key in label_keys:                                   # `@shower` is an axis beside the quantities: not a quantity's name
        if key in tags:
            raise HeimdallError(f"a Run's label '{key}' is also a quantity of the Runs", where=str(path),
                                hint=f"heimdall tag RUN {key}= removes the label, or give the label another name")
    label_values = {k: list(dict.fromkeys(found.get(k, "") for found in run_labels_.values())) for k in label_keys}
    quantities = {name: Quantity(name, [v for _, _, v, _ in have], tags=[t for t, *_ in have], labels=[l for _, l, _, _ in have],
                                 styles=[s for *_, s in have] if any(s for *_, s in have) else [])
                  for name, have in tags.items()}
    quantities["@run"] = Quantity("@run", [r for r, *_ in loaded], tags=[r for r, *_ in loaded],
                                  labels=[run_label(r, run_tags[r]) for r, *_ in loaded])
    quantities["@events"] = Quantity("@events", counts, tags=[count_tag(n) for n in counts],
                                     labels=[f"{count_tag(n)} events" for n in counts])
    quantities["@configuration"] = Quantity("@configuration", configurations, tags=configurations,
                                            labels=[labels[k] for k in configurations])
    if tagged:                                               # V224: only when a run is tagged
        blank = UNTAGGED
        while blank in tagged:                               # a run tagged "untagged" keeps its name
            blank += "_"
        quantities["@tag"] = Quantity("@tag", tagged, tags=[t or blank for t in tagged],
                                      labels=[t or blank for t in tagged])
    for key, found in label_values.items():                  # a Run without the label: "–"
        blank = NO_LABEL
        while blank in found:
            blank += "_"
        quantities[f"@{key}"] = Quantity(f"@{key}", found, tags=[v or blank for v in found], labels=[v or "–" for v in found])
    assignment = source.get("assignment") or loaded[0][1].assignment
    errand = source.get("errand") or loaded[0][1].name
    rel = folder.relative_to(results_root()) if folder.is_relative_to(results_root()) else Path(assignment) / errand
    folders = into or RunFolders(assignment, records_root() / rel, folder,
                                 cache_root() / assignment / "plots" / Path(*rel.parts[1:]) / "_across")
    members, seen, shadowed = [], {}, {}
    kept: dict[str, dict[str, str]] = {}                     # each run's ignored quantities' one value
    swept: list[str] = []
    for number, (run_name, doc, conf, own) in enumerate(loaded):
        index = {q: {(qq.tags[i] if qq.tags else str(qq.values[i])): i for i in range(len(qq.values))}
                 for q, qq in quantities.items()}
        held: dict[str, list] = {q: [] for q in ignored}     # what each ignored quantity holds in this run
        for m in own:
            def moved(choice: dict) -> dict:
                out = {}
                for q, i in choice.items():
                    original = doc.quantities[q]
                    tag = original.tags[i] if original.tags else str(original.values[i])
                    out[q] = index[q][tag]
                return out
            events = _member_events(doc, m) or usual[run_name]
            absent = {q: index[q][tag] for q, tag in lacking.items() if q not in m.values}      # never named in this Run
            attributes = {"@run": number, "@configuration": configurations.index(conf.key),
                          **({"@events": counts.index(events)} if events else {}),
                          **({"@tag": tagged.index(run_tags[run_name])} if tagged else {}),
                          **{f"@{k}": label_values[k].index(run_labels_[run_name].get(k, "")) for k in label_keys}}
            values = {**moved(m.values), **absent, **attributes}
            choice = {**{q: i for q, i in moved(m.point.choice).items() if q not in ignored},
                      **{q: attributes[q] for q in ("@events", "@tag", *(f"@{k}" for k in label_keys)) if q in attributes and q not in ignored}}
            for q in ignored:
                if q in values and quantities[q].tags[values[q]] not in held[q]:
                    held[q].append(quantities[q].tags[values[q]])
            swept += [q for q in choice if q not in swept]
            point = replace(m.point, name=f"{run_name}__{m.point.name}", choice=choice)
            member = replace(m, point=point, values=values, folders=folders,
                             context={**m.context, "run": run_label(run_name, run_tags[run_name])})
            key = (tuple(sorted((q, quantities[q].tags[i]) for q, i in values.items() if not q.startswith("@") and q not in ignored)),
                   events if "@events" not in ignored else None, run_tags[run_name],
                   tuple(sorted(run_labels_[run_name].items())))
            complete = member.recorded is not None and member.recorded == member.identity
            if prefer == "last" and key in seen:
                earlier, was_complete = seen[key]
                if complete or not was_complete:              # a later run's point, when it is there to draw
                    shadowed[earlier.point.name] = point.name
                    members = [x for x in members if x is not earlier]
                else:
                    continue
            seen[key] = (member, complete)
            members.append(member)
        for q, found in held.items():
            if len(found) > 1:
                raise HeimdallError(f"[from].ignore names {q}, which takes {len(found)} values in the Run {run_name}: "
                               f"{', '.join(found)}", where=f"{path}: [from].ignore",
                               hint=f"an ignored quantity holds one value in each Run: draw {q} as an axis (leave it out "
                                    "of ignore), or leave the Run out (runs = [\"<its folder's glob>\", …])")
        if ignored:
            kept[run_name] = {q: found[0] for q, found in held.items() if found}
    configuration = DocConfiguration(ACROSS, errand, [[q] for q in swept], [], [], {}, None, f"{errand}: its runs together")
    doc = Doc(path, assignment, errand, dict(data.get("plot", {})), dict(data.get("stats", {})), quantities, configuration,
              {**source, "shadowed": shadowed, **({"ignored": kept} if kept else {})}, score=dict(data.get("score", {})),
              left={f"{run_name}__{name}": why for run_name, run_doc, _, _ in loaded for name, why in run_doc.left.items()})
    return doc, configuration, members


def _tag_of(doc: Doc, record: Path | None) -> str:
    """A run's tag across runs: its record's, the truth, when the record is there (a tag given since its plot
    stage last wrote the document); else its document's [source].tag (a copied results/); checked either way."""
    from .config import check_tag
    from .record import run_tag
    if record is not None and record.is_dir() and (kept := run_tag(record)) is not None:
        return kept
    tag = doc.source.get("tag")
    return check_tag(str(tag), f"{doc.path}: [source].tag") if tag else ""


def _labels_of(doc: Doc, record: Path | None) -> dict[str, str]:
    """A run's labels other than its tag, as `_tag_of` has its tag: its record's, else its document's [source].labels."""
    from .record import TAG_FILE, check_label_key, config_tag, run_labels
    if record is not None and (record / TAG_FILE).is_file():
        return run_labels(record)
    given = doc.source.get("labels") or {}
    where = f"{doc.path}: [source].labels"
    return {check_label_key(k, where): config_tag(str(v), where) for k, v in given.items()}


def _member_events(doc: Doc, member: Member) -> int:
    """A member's event count: its document's, else its provenance's."""
    return int(member.context.get("events") or 0) or _provenance_events(member.folders, member.point.name)
