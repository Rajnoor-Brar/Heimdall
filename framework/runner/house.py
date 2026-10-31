"""Housekeeping: `heimdall ls`, `heimdall explain`, `heimdall status`, `heimdall clean` (rank 5, V74).

docs/05_Commands_and_Tools.md §1, audit 1 F5. Nothing here runs a tool; `clean` is the only command
that deletes, and only what the runner made and no plan uses (it never deletes from results/ but a
product's `.partial` leftover, and it refuses while a job is running).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import time
import tomllib
from pathlib import Path

from . import config as configmod
from . import schema, tools
from .errors import HeimdallError, did_you_mean
from . import runs
from .events import greeting, hubs
from .paths import cache_root, configs_root, find_work, records_root, results_root
from .record import (cause_text, constants, constants_lines, held_by, holder, provenance_file, record_dir,
                     run_tag, state_of, write_run_tag)

TABLES = {"errand": "errand", "config": "config", "prelim": "prelim", "plot": "plot", "data": "data",
          "across_from": "across_from", "configuration": "configuration", "quantity": "quantity", "quantities": "quantity", "tool": "tool",
          "tools": "tool", "figure": "figure", "figures": "figure"}


# ── heimdall ls ─────────────────────────────────────────────────────────────────────────────────────

def importers() -> dict[str, list[str]]:
    """Every config another one imports ([config] or [file] import), with the configs that import it:
    <A>/<E> → [<A>/<E>, …]."""
    root = configs_root()
    out: dict[str, list[str]] = {}
    for path in sorted(root.glob("*/*.toml")):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        given = (data.get("file") or data.get("config") or {}).get("import", [])
        for entry in given if isinstance(given, list) else [given]:
            name = entry.get("from") if isinstance(entry, dict) else entry
            if not isinstance(name, str):
                continue
            name = name.removesuffix(".toml")
            full = name if "/" in name else f"{path.parent.name}/{name}"
            out.setdefault(full, []).append(str(path.relative_to(root).with_suffix("")))
    return out


def unused_tools(errand) -> list[str]:
    """This file's own tool tables that no configuration runs (tools, pre, post, an @quantity's choice)
    or names in generate_cards: likely left over (an import's spare tables are its own business)."""
    used: set[str] = set()
    for configuration in errand.configurations.values():
        for groups in (configuration.tools, configuration.pre, configuration.post):
            for group in groups:
                for entry in group:
                    if entry.startswith("@") and entry[1:] in errand.quantities:
                        used |= {t for v in errand.quantities[entry[1:]].values for t in configmod.fragment_tags(v)}
                    used.add(entry)
        used |= {entry.partition(":")[0] for entry in configuration.generate_cards}
    return [f"[tools.{tag}] is defined but no configuration runs it or names it in generate_cards"
            for tag in errand.tools if tag not in used and f"tools.{tag}" not in errand.included]


def config_names(assignment: str | None = None) -> list[str]:
    """Every configs/<A>/<E>.toml that has an [errand], as <A>/<E>; one with [run] too (the names
    before I-112), so that reading it says what rewrites it."""
    root = configs_root()
    names = []
    for path in sorted(root.glob(f"{assignment or '*'}/*.toml")):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            has_run = "errand" in data or "run" in data
        except (OSError, tomllib.TOMLDecodeError):
            has_run = True                                   # a broken file is listed, and says so
        if has_run:
            names.append(str(path.relative_to(root).with_suffix("")))
    return names


def ls(assignment: str | None = None) -> list[str]:
    """Each config, then each configuration: its title and description, and whether a sweep runs it."""
    names = config_names(assignment)
    if not names:
        raise HeimdallError(f"no errand file under {configs_root() / (assignment or '')}", hint="a config has an [errand] table")
    lines = []
    for name in names:
        try:
            errand = configmod.load(name)
        except HeimdallError as error:
            lines.append(f"{name}   (does not load: {error.message})")
            continue
        swept = set(errand.runs(None)) if errand.sweep_runs else {errand.raw.get("errand", {}).get("configuration")}
        lines.append(f"{name}   run {errand.name}" + ("   sweep_runs" if errand.sweep_runs else ""))
        for key, configuration in errand.configurations.items():
            mark = "*" if key in swept else " "
            about = configuration.description or (configuration.title if configuration.title != key else "")
            lines.append(f"  {mark} {key:16s} {about}")
    from . import report as reportmod
    found = reportmod.recipes(assignment)                  # V207: the reports' recipes
    if found:
        lines.append("reports: " + ", ".join(found) + "   (heimdall report <recipe>.toml <source>)")
    return lines


# ── heimdall explain ────────────────────────────────────────────────────────────────────────────────

def module_settings(key: str) -> list[str]:
    """`heimdall explain <Name>.exe[.<setting>]`: a module program's settings, as it lists them itself
    (`<Name>.exe --describe`, src/Module.hh): name, type, default, doc. Found in the work dir's build/."""
    name, _, setting = key.partition(".exe")
    setting = setting.lstrip(".")
    exe = Path(name + ".exe")
    if not exe.is_file():
        work = find_work()
        found = sorted((work / "build").rglob(f"{exe.name}")) if work is not None else []
        if not found:
            raise HeimdallError(f"no program {exe.name} built in this work dir", hint="heimdall build makes it (build/<A>/)")
        exe = found[0]
    try:
        done = subprocess.run([str(exe), "--describe"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HeimdallError(f"{exe.name} --describe did not answer: {error}") from None
    rows = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    if done.returncode != 0 or not rows and done.stderr.strip():
        raise HeimdallError(f"{exe.name} --describe failed", hint=(done.stderr.strip().splitlines() or [""])[-1][:200])
    if setting:
        chosen = [r for r in rows if r["name"] == setting]
        if not chosen:
            raise HeimdallError(f"{exe.name} reads no setting '{setting}'",
                           hint=did_you_mean(setting, [r["name"] for r in rows]) or ", ".join(r["name"] for r in rows))
        rows = chosen
    lines = [f"{exe} — the settings it reads ([tools.<tag>.config]; an unknown one is refused)"]
    width = max((len(r["name"]) for r in rows), default=4)
    for row in rows:
        default = json.dumps(row["default"]) if row["type"] == "str" else row["default"]
        lines.append(f"  {row['name']:{width}}  {row['type']:5}  default {default}" + (f"  {row['doc']}" if row["doc"] else ""))
    if not rows:
        lines.append("  (none read before it asks for its input: read settings first, src/Module.hh)")
    return lines


def _quantity_lines(key: str) -> list[str]:
    """`heimdall explain <quantity>`: a vocabulary name's shape, unit, doc, who declared it, and how each tool
    maps it; [] for a name the vocabulary lacks."""
    from . import quantities as qmod
    entry = qmod.vocabulary().get(key) if "." not in key else None
    if entry is None:
        return []
    mapped = {tool: table["compatible_quantities"][key] for tool, table in qmod.load_master("", None)["quantities"].items()
              if key in table["compatible_quantities"]}
    source = ("declared by " + entry["declared"]) if "declared" in entry else "the vocabulary: framework/schema/quantities.toml"
    lines = [f"quantity '{key}' ({source})", f"  shape    {qmod._shape_text(entry['shape'])}"]
    lines += [f"  unit     {entry['unit']}"] if entry.get("unit") else []
    lines += ["  per beam yes, in the run's beam order"] if entry.get("per_beam") else []
    lines += [f"  doc      {entry['doc']}"] if entry.get("doc") else []
    lines += (["  tools    " + "; ".join(f"{t} {m}" for t, m in sorted(mapped.items()))] if mapped
              else ["  tools    none map it: a tool table gives it a key"])
    return lines


#: v3's names (runner/v3.py): the v2 key each stands for, and what v3 adds.
V3_NAMES = {
    "events": ("errand", "event_count", "a configuration's may be a list: one configuration per count, <name>_<count>"),
    "chain": ("errand", "tools", "[errand]'s is every configuration's, unless one gives its own"),
    "vary": ("configuration", "sweeps", "a compound quantity's name sweeps its fields together"),
    "fixed": ("configuration", "static", "a quantity's own fixed = \"<tag>\" ([static] in v2), or a configuration's "
                                          "fixed = { quantity = \"<tag>\" }"),
    "points": ("quantity", "values", "rows { tag, value, label, style }: v2's values, tags, labels and styles"),
    "to": ("quantity", "key", "{ <target> = \"<key>\" or true }: v2's key and target in one table"),
    "card": ("tool", "baseconfig", ""), "output": ("tool", "output_file", ""),
    "uses": ("tool", "tool", "the tool folder of a second table of one tool; else the table's name is the tool"),
    "folder": ("configuration", "label", ""),
    "seed": ("errand", "seed_type", "\"identity\", \"random\" or an integer (v2's seed_type and manual_seed)"),
    "commands": ("prelim", "commands", "[errand] commands: run in each point's folder before its tools"),
}
#: What a table is, for `heimdall explain <table>`.
TABLE_TEXT = {
    "config": "[file] (v2's [config]): how the file is read: imports, a master, vars, meta",
    "errand": "[errand]: the errand's name, assignment and defaults, which every configuration starts from",
    "configuration": "[cfgs.<name>] (v2's [errand.cfgs.<name>]): one configuration: what it varies, fixes and runs",
    "quantity": "[quantities.<q>]: a quantity: its points, fixed point and bindings",
    "tool": "[tools.<tag>]: a tool table; its folder's own keys are `heimdall tools <folder>`",
    "plot": "[plot]: the pages", "figure": "[plot.figures.<f>]: one figure's pages", "data": "[plot.data]: reference data",
    "across_from": "[plot.across_from]: the runs drawn together and how (the drawing's [from])",
    "cluster": "[cluster]: heimdall cluster's Slurm keys (machine.toml, heimdall.toml, the errand file, a configuration)",
    "prelim": "[prelim] (v2 only; v3 infers it): FIFOs, files and commands of each point",
}


def _special(key: str) -> list[str] | None:
    """What explain answers beyond a key of the schema: a table, a v3 name, a tool folder's option, a
    style key, a report's recipe, machine.toml, [static]."""
    from . import tools as toolsmod
    word = key.strip("[]")
    if word.split(".")[0].split("]")[0] == "run":                         # I-112's names
        raise HeimdallError(f"[run] is now [errand] (I-112's names): {key}",
                       hint="heimdall explain errand" + word.removeprefix("run").replace("]", ""))
    table = TABLES.get(word, {"file": "config", "cfgs": "configuration"}.get(word))
    if table and "." not in word:
        entries = schema.keys(table)
        return [TABLE_TEXT.get(table, f"[{table}]"), *(f"  {k:16} {e.get('doc', '')}" for k, e in entries.items()),
                "  (heimdall explain <table>.<key> for one in full)"]
    last = word.rsplit(".", 1)[-1]                                       # events, errand.events, tools.<tag>.card
    if last in V3_NAMES and (word == last or word.split(".")[0] in ("errand", "cfgs", "quantities", "tools")):
        word = last
        table, old, note = V3_NAMES[word]
        entry = schema.keys(table).get(old, {})
        return [f"{word} (v3; v2's {'[' + table + '].' + old})", *([f"  {note}"] if note else []),
                *([f"  {entry['doc']}"] if entry.get("doc") else [])]
    if word in ("static",):
        return ["[static] (v2; v3: each quantity's fixed): quantity = tag, the point of a quantity no configuration varies"]
    if word in ("machine.toml", "machine"):
        return ["machine.toml (the machine root's; recipes/machine.template.toml): this machine's layer",
                "  [settings] [env] [packages.<name>]  the stack's build: over the recipes and toolkits (recipes/README.md §1)",
                "  [cluster]                            heimdall cluster's defaults for every work dir here (04 §16)"]
    if word.startswith("report.section."):                  # V209: [[report.section]]'s keys are the schema's section
        word = word.removeprefix("report.")
    if word in ("report", "section", "report.section", "report.toml"):
        tables = ("section",) if word.endswith("section") else schema.REPORT_TABLES
        return ["a report's recipe: [report] and its [[report.section]]s, in configs/<A>/<E>.toml ([report] alone), "
                "an errand file or a folder's report.toml (04 §15)",
                *(f"  {('report.' if t == 'section' else '') + t + '.' + k:30} {e.get('doc', '')}"
                  for t in tables for k, e in schema.keys(t).items())]
    if word.split(".")[0] in schema.REPORT_TABLES and word.count(".") == 1:
        table, key = word.split(".")
        entry = schema.keys(table).get(key)
        if entry is not None:
            return [f"{word} (a report's recipe, 04 §15)", f"  type     {entry.get('type', '')}",
                    *([f"  default  {entry['default']}"] if "default" in entry else []), f"  {entry.get('doc', '')}"]
    style = word.removeprefix("style.")
    for dotted, default, comment in schema.style_entries():
        if dotted == style:
            return [f"style {dotted} (src/Apps/Paint/base.toml; a style layer's key, 04 §12)",
                    f"  default  {default}", *([f"  {comment}"] if comment else [])]
    parts = word.split(".")
    if parts[0] == "tools":
        parts = parts[1:]
    if len(parts) == 2 and parts[0] in toolsmod.folders():
        option = toolsmod.folders()[parts[0]].spec.get("options", {}).get(parts[1])
        if option is not None:
            return [f"{parts[0]}'s option {parts[1]} (its tool folder's [options])",
                    f"  kind     {option.get('kind', 'any')}" + (", required" if option.get("required") else ""),
                    *([f"  default  {option['default']}"] if "default" in option else []),
                    *([f"  {option['doc']}"] if option.get("doc") else [])]
    return None


def explain(key: str) -> list[str]:
    """A key's type, default, choices, bounds, inheritance and doc, from framework/schema/run.toml.
    `plot.y_gutter`, `[plot].y_gutter`, `errand.event_count`, `quantities.<q>.styles`, `tools.<tag>.shards`,
    `plot.figures.<figure>.logy`, `errand.cfgs.<cfg>.threads` (a configuration's, V98); a bare key is looked
    up in every table."""
    if ".exe" in key:                                                   # a module program's own settings
        return module_settings(key)
    special = _special(key)
    if special is not None:
        return special
    vocab = _quantity_lines(key)                                        # a quantity's name too (V58)
    if vocab and not any(key in schema.keys(t) for t in schema.spec() if t != "sections"):
        return vocab

    parts = [p for p in key.replace("[", "").replace("]", ".").split(".") if p]
    if not parts:
        raise HeimdallError("explain which key?", hint="e.g. heimdall explain plot.y_gutter")
    if parts[0] == "cfgs" and len(parts) >= 3:                          # v3's names: cfgs.pdf.threads, file.vars
        parts = ["errand", *parts]
    elif parts[0] == "file":
        parts[0] = "config"
    found = []
    if len(parts) >= 2 and parts[0] in TABLES:
        table = TABLES[parts[0]]
        if parts[0] == "errand" and len(parts) >= 3 and parts[1] == "cfgs":   # a configuration's (V98)
            table = "configuration"
        elif parts[0] == "plot" and len(parts) >= 3 and parts[1] in ("data", "across_from"):   # a table of [plot]'s
            table = TABLES[parts[1]]
        name = parts[-1]
        if name in schema.keys(table):
            found.append((table, name))
    else:
        found = [(table, parts[-1]) for table in schema.spec() if table != "sections" and parts[-1] in schema.keys(table)]
    if not found:
        every = sorted({k for t in schema.spec() if t != "sections" for k in schema.keys(t)})
        raise HeimdallError(f"no key '{key}' in the schema", hint=did_you_mean(parts[-1], every) or
                       "keys are written as plot.y_gutter, errand.events, cfgs.<name>.threads, quantities.<q>.points")
    lines = []
    for table, name in found:
        entry = schema.keys(table)[name]
        lines.append(f"[{table}].{name}")
        lines.append(f"  type     {schema.type_name(entry['type'])}" +
                     (f" ({schema.type_name(entry['items'])} each)" if entry.get("items") else ""))
        if "choices" in entry:
            lines.append("  choices  " + ", ".join(c if isinstance(c, str) else str(c).lower() for c in entry["choices"]))
        if "min" in entry:
            lines.append(f"  min      {entry['min']}")
        if "default" in entry:
            lines.append(f"  default  {entry['default']!r}")
        if entry.get("required"):
            lines.append("  required")
        if entry.get("inherit"):
            lines.append("  a configuration inherits it from [errand]")
        if entry.get("default_ok"):
            lines.append('  "default": the layer below\'s value, as if left out (v2\'s [plot] itself: the drawing tool\'s own)')
        if entry.get("native_ok"):
            lines.append('  "native": what the drawing tool does by itself, at any level')
        if entry.get("doc"):
            lines.append(f"  {entry['doc']}")
        if entry.get("notes"):
            lines += [""] + [f"  {line}" for line in textwrap.wrap(entry["notes"], 96)]
    return lines + ([""] + vocab if vocab else [])


# ── heimdall status ─────────────────────────────────────────────────────────────────────────────────

def _size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _human(size: int) -> str:
    for unit in ("B", "kB", "MB", "GB"):
        if size < 1000 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1000
    return ""


def live_runs(config: str | None = None, configuration: str | None = None, pid: int | None = None) -> list[tuple[str, dict]]:
    """The runs this user has going on this machine, as their watch sockets answer (V182): (name, greeting),
    newest first; only those of `config` (its path), naming `configuration`, of process `pid`."""
    import os
    found = []
    for name in hubs():
        hello = greeting(name)
        if not hello or hello.get("uid", os.getuid()) != os.getuid():
            continue
        if config is not None and hello.get("config") != config:
            continue
        if configuration and configuration not in hello.get("configurations", []):
            continue
        if pid is not None and hello.get("pid") != pid:
            continue
        found.append((name, hello))
    return sorted(found, key=lambda item: item[1].get("started", 0), reverse=True)


def running_configs() -> dict[str, list[str]]:
    """The jobs running on this machine (their watch sockets): config path → its configurations."""
    out: dict[str, list[str]] = {}
    for _, hello in live_runs():
        out.setdefault(hello.get("config", ""), []).extend(hello.get("configurations", []))
    return out


def runs_here(work: Path) -> list[dict]:
    """This user's live runs of the work dir `work` (V182): what clean and migrate --layout wait for. A run
    from before the greeting named its work dir counts when its config is under `work`."""
    out = []
    for _, hello in live_runs():
        where = hello.get("work") or ""
        config = Path(hello.get("config") or "/")
        if where == str(work) or (not where and config.is_relative_to(work)):
            out.append(hello)
    return out


def _ago(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"
    return f"{seconds // 86400}d {seconds % 86400 // 3600}h"


def _config_name(config: str, work: str | None) -> str:
    """A config as `heimdall run` names it: <A>/<E> under its work dir's configs/, else its path."""
    path = Path(config or "")
    for root in ([Path(work) / "configs"] if work else []):
        try:
            return str(path.relative_to(root).with_suffix(""))
        except ValueError:
            pass
    return str(path)


def runs_listing(entries: list[dict], live: list[tuple[str, dict]], titles: dict[str, str],
                 now: float | None = None, limit: int | None = None, days: int | None = None) -> list[str]:
    """`heimdall runs` (V182): what runs now by default (recorded, and live sockets with no entry: unrecorded, as
    from inside an image); `limit`, the latest N of any state; `days`, all begun within that age. Oldest first,
    a block each: id and work dir (its title); the config and its configurations (`NN key` when the serial is
    known), its points' counts once it ended; when, for how long, its state, and its progress, configuration
    points ended of those planned (NULL: not recorded, as by an older entry or a cluster submission), and while
    it runs those running; its pid's watch and stop commands, or a cluster submission's; its log."""
    now = time.time() if now is None else now
    by_pid = {hello.get("pid"): hello for _, hello in live}
    states = [(e, runs.state(e, by_pid)) for e in entries]
    submitted = [e for e, s in states if e.get("kind") == "cluster" and s == "submitted"]
    if submitted and shutil.which("squeue"):                     # one squeue for every submission (V184)
        from .cluster import active
        queued = {line.split("|")[0].split("_")[0] for line in active([str(j) for e in submitted for j in e.get("jobs", [])])}
        states = [(e, ("on Slurm" if {str(j) for j in e.get("jobs", [])} & queued else "ended") if e in submitted else s)
                  for e, s in states]
    running = [(e, s) for e, s in states if s.startswith("running") or s.startswith("on ") or s == "in another PID namespace"
               or (e.get("kind") == "cluster" and s in ("submitted", "on Slurm"))]
    recorded = {e.get("pid") for e, s in running if e.get("host") == runs.host()}
    unrecorded = [hello for pid, hello in by_pid.items() if pid not in recorded]
    if limit is None and days is None:
        selected = [(e, s) for e, s in running]
        selected += [({"id": f"(pid {hello.get('pid')})", **hello,
                       "configurations": hello.get("configurations")}, "running (unrecorded)") for hello in unrecorded]
        heading = "running"
    elif limit is not None:
        selected = list(states)
        selected += [({"id": f"(pid {hello.get('pid')})", **hello,
                       "configurations": hello.get("configurations")}, "running (unrecorded)") for hello in unrecorded]
        selected.sort(key=lambda item: (item[0].get("started") or 0, item[0].get("id", "")), reverse=True)
        selected = selected[:limit]
        heading = f"latest {limit} runs"
    else:
        cutoff = now - (days or 0) * 86400
        selected = [(e, s) for e, s in states if cutoff <= (e.get("started") or 0) <= now]
        selected += [({"id": f"(pid {hello.get('pid')})", **hello,
                       "configurations": hello.get("configurations")}, "running (unrecorded)") for hello in unrecorded
                     if cutoff <= (hello.get("started") or 0) <= now]
        heading = f"runs from the last {days} days"
    selected.sort(key=lambda item: (item[0].get("started") or 0, item[0].get("id", "")))

    def where(work: str | None) -> str:
        return titles.get(work or "", "") or (Path(work).name if work else "")

    def row(e: dict, state: str) -> list[str]:
        started = e.get("started") or 0
        span = _ago((e.get("finished") or now) - started)
        when = time.strftime("%m-%d %H:%M", time.localtime(started))
        what = _config_name(e.get("config", ""), e.get("work"))
        cfgs = ", ".join(e.get("configurations") or ([e["configuration"]] if e.get("configuration") else []))
        serials, tags = e.get("configuration_serials", {}), e.get("configuration_tags", {})
        configurations = ", ".join((f"{serials[key]:02d} {key}" if isinstance(serials.get(key), int) else key)
                                   + (f" [{tags[key]}]" if tags.get(key) else "")
                                   for key in cfgs.split(", ") if key)          # NN only when it is known
        head = f"  {e.get('id', '?'):28s}  |   {where(e.get('work'))}"
        completed = e.get("points_completed")
        total = e.get("points_total")
        progress = f"{completed if completed is not None else 'NULL'}/{total if total is not None else 'NULL'}"
        detail = f"      {when} ({span}) · {state}  ·  {progress}"
        if state.startswith("running"):
            active = e.get("active_parallel_points")
            detail += f" ·  {active if active is not None else 'NULL'}"
        config_line = f"      {what} · {configurations}"
        if counts := e.get("counts"):                                   # V202: its points
            config_line += (f"   {counts.get('done', 0)} done"
                            + (f" ({counts['warned']} with warnings)" if counts.get("warned") else "")
                            + f", {counts.get('failed', 0)} failed"
                            + (f", {counts['stopped']} stopped" if counts.get("stopped") else ""))
        tail = []
        if e.get("kind") == "cluster":
            tail.append(f"      cluster jobs {', '.join(map(str, e.get('jobs', [])))}: heimdall cluster {what} "
                        f"{e.get('configuration', '')} --status")
        elif state.startswith("running"):
            tail.append(f"      pid {e.get('pid')} : heimdall watch --pid {e.get('pid')} · heimdall stop --pid {e.get('pid')}")
        if e.get("log"):
            tail.append(f"      log {e['log']}")
        return [head.rstrip(), config_line.rstrip(), detail.rstrip(), *tail]

    if not selected:
        if limit is None:
            if days is not None:
                return [f"no runs in the last {days} days on this machine ({runs.folder()})"]
            return [f"no running runs on this machine ({runs.folder()})"]
        return [f"no runs on this machine in the last {runs.KEEP_DAYS} days ({runs.folder()})"]
    lines = [heading]
    for i, (entry, state) in enumerate(selected):
        if i:
            lines.append("")
        lines += row(entry, state)
    return lines


def log_target(target: str) -> tuple[Path, str | None, str | None]:
    """`heimdall log`'s argument (V202): a record, `<A>/<E>/<R>`, then a point and a tool, as names
    (`Demo/jets/01_pdf/MSTW08lo/pythia`) or as a path under records/ or results/ (a point's logs/<point>/<tag>.log
    too). (the record's folder, the point or None, the tool or None)."""
    path = Path(target).expanduser()
    parts = None
    if path.is_absolute() or target.startswith(("./", "../")) or path.exists():
        resolved = path.resolve()
        for root in (records_root().resolve(), results_root().resolve()):
            if resolved.is_relative_to(root):
                parts = list(resolved.relative_to(root).parts)
                break
    if parts is None:
        parts = [part for part in target.split("/") if part]
    if len(parts) < 3:
        raise HeimdallError(f"'{target}' names no record", hint="a record is <A>/<E>/<R> (heimdall runs names them), then "
                       "a point and a tool: heimdall log Demo/jets/01_pdf/MSTW08lo/pythia")
    record = records_root() / Path(*parts[:3])
    if not record.is_dir():
        raise HeimdallError(f"no record {'/'.join(parts[:3])}", where=str(record))
    rest = parts[3:]
    if rest and rest[0] in ("logs", "points"):
        rest = rest[1:]
    tag = rest[1].removesuffix(".log").removesuffix(".full") if len(rest) > 1 else None
    return record, (rest[0] if rest else None), tag


def tag_lines(record: Path, name: str | None = None, clear: bool = False) -> list[str]:
    """`heimdall tag RECORD [NAME] [--clear]` (V223): the folder's tag, or it set to `name` or removed, in its record
    (records/<A>/<E>/<R>/tag, the source of truth) and, when the folder has one, its plot document's [source].tag."""
    from .config import check_tag
    from .plotdoc import path_of, write_tag
    rel = record.relative_to(records_root())
    if clear and name is not None:
        raise HeimdallError("a tag to give and --clear: one or the other", hint=f"heimdall tag {rel} --clear")
    had = run_tag(record)
    if name is None and not clear:
        return [f"{rel}: {had}" if had else f"{rel} has no tag"]
    if name is not None:
        check_tag(name, "heimdall tag NAME")
    write_run_tag(record, name, cleared=clear)
    document = path_of(results_root() / rel)
    if document.is_file():
        write_tag(document, name)
    if name is None:
        return [f"{rel}: its tag {had} removed" if had else f"{rel} has no tag"]
    return [f"{rel}: tagged {name}" + (f" (was {had})" if had and had != name else "")]


def point_log(record: Path, point: str, tag: str | None = None, full: bool = False,
              attempt: int | None = None) -> list[str]:
    """`heimdall log RECORD/POINT[/TAG]` (V202): a point's attempts (when, verdict, why), then each of its tools'
    digests (`full`: their whole logs), the latest attempt's or (`attempt`) an earlier one's from its history/;
    with `tag`, that tool's alone."""
    logs, rows = record / "logs" / point, []
    try:
        for line in (record / "points" / point / "attempts.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    if not logs.is_dir() and not rows:
        names = sorted(p.name for p in (record / "logs").iterdir() if p.is_dir()) if (record / "logs").is_dir() else []
        raise HeimdallError(f"no point {point} in {record.name}", hint=did_you_mean(point, names) or
                       (f"its points: {', '.join(names[:8])}{' …' if len(names) > 8 else ''}" if names else "it has none"))
    latest = rows[-1]["n"] if rows else None
    folder = logs if attempt is None or attempt == latest else logs / "history" / str(attempt)
    if not folder.is_dir():
        kept = sorted(int(p.name) for p in (logs / "history").iterdir() if p.name.isdigit()) if (logs / "history").is_dir() else []
        raise HeimdallError(f"no logs of attempt {attempt} kept", where=str(folder),
                       hint=f"kept: {', '.join(map(str, kept))}" + (f" and the latest, {latest}" if latest else "") if kept
                       else "a point keeps its latest attempt's logs, and earlier ones' from the next attempt on")
    suffix = ".full.log" if full else ".log"
    if tag is not None:
        path = folder / f"{tag}{suffix}"
        if not path.is_file():
            there = sorted(p.name for p in folder.glob(f"*{suffix}") if full or not p.name.endswith(".full.log"))
            raise HeimdallError(f"no {path.name} in {folder}", hint=f"there: {', '.join(there)}" if there else
                           ("--full needs a run with --logs" if full else "nothing was logged there"))
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    out = [f"{point}: {len(rows)} attempt(s) recorded" + ("" if rows else " (it ran before attempts were recorded)")]
    for row in rows:
        out.append(f"  {row.get('n', '?'):>3}  {_local(row.get('finished', '')):16s}  {row.get('verdict', '?'):8s} "
                   f"{cause_text(row)}".rstrip())
    said = sorted(p for p in folder.glob(f"*{suffix}") if full or not p.name.endswith(".full.log"))
    for path in said:
        out += ["", f"── {path.relative_to(record)}", *path.read_text(encoding="utf-8", errors="replace").splitlines()]
    if not said:
        out.append(f"no {'whole logs' if full else 'logs'} kept in {folder.relative_to(record)}"
                   + (" (--logs keeps them)" if full else ""))
    return out


def point_state(plan) -> str:
    """complete; stale (complete for an earlier identity: a changed setup reruns it); running (a
    session holds its lock, U66); failed or stopped (its last attempt's verdict, V200); incomplete (begun,
    not done, with no attempt recorded: before V200); to run (never begun, or its logs are gone). From its
    records and its lock: deleting logs/ or .cache/ changes no state but incomplete's (record.state_of)."""
    return state_of(plan)[0]


def status(planned: list, running: dict[str, list[str]]) -> list[str]:
    """Per configuration, its counts by state, its constants (V200: events, threads, seeds, tools), then a line
    per point: its state, when it finished, its results' size, and why a failed or stopped one ended."""
    lines = []
    for p in planned:
        stages = [*([p.pre] if p.pre else []), *p.every, *p.combined, *([p.post] if p.post else [])]
        found = [state_of(s) for s in stages]
        states = [state for state, _ in found]
        live = p.configuration.key in running.get(str(p.errand.path), [])
        counts = ", ".join(f"{states.count(s)} {s}" for s in STATES if states.count(s))
        tag = run_tag(tools.run_folders(p.errand, p.configuration).record)         # V223
        lines.append(f"{p.errand.name} · {p.configuration.key}{f' [{tag}]' if tag else ''} "
                     f"({tools.run_dir(p.errand, p.configuration)}): {counts}" + ("   [running]" if live else ""))
        lines += constants_lines(constants(p.every, p.errand, p.configuration, machine=False))
        width = max([24] + [len(s.point.name) for s in stages])        # the states in one column
        for stage, (state, last) in zip(stages, found):
            when, why = "", ""
            provenance = provenance_file(stage)
            if state == "complete" and provenance.exists():
                when = time.strftime("%Y-%m-%d %H:%M", time.localtime(provenance.stat().st_mtime))
            elif state == "running" and (who := holder(stage)):
                when = f"({held_by(who)})"
            elif state in ("failed", "stopped") and last:
                when, why = _local(last.get("finished", "")), cause_text(last)
            size = _human(_size(stage.res)) if stage.res.exists() else ""
            lines.append(f"  {stage.point.name:{width}s} {state:10s} {when:16s} {size:>9s}  {why}".rstrip())
    return lines


#: A point's states, in the order `heimdall status` counts them.
STATES = ("complete", "stale", "running", "failed", "stopped", "incomplete", "to run")


def _local(stamp: str) -> str:
    """An attempt's time (ISO, UTC) as local "YYYY-mm-dd HH:MM"; as given when it is not one."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(stamp).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(stamp)


# ── heimdall clean ──────────────────────────────────────────────────────────────────────────────────

def outs_stages(planned) -> list:
    return [s for p in planned for s in [*([p.pre] if p.pre else []), *p.every, *p.combined, *([p.post] if p.post else [])]]


def _stage_dirs(planned) -> tuple[set[Path], set[Path]]:
    outs, ress = set(), set()
    for p in planned:
        for stage in [*([p.pre] if p.pre else []), *p.every, *p.combined, *([p.post] if p.post else [])]:
            outs.add(stage.out)
            ress.add(stage.res)
    return outs, ress


#: Folders of a configuration's that are no point's: the stages, the pages, the submissions (U30), the plot stage's
#: failures (logs/plot/, V204).
KEEP_NAMES = {"plots", "pre", "post", "cluster", "compare", "plot"}


def clean_targets(planned: list, everything: bool, records: bool = False) -> tuple[list[Path], list[Path]]:
    """What `heimdall clean` removes, and the results it only lists, by lifecycle (U21, V157): within each
    planned configuration's records/<A>/<E>/<R>/logs/ (ephemeral), the working folders no plan has, and `.partial`
    leftovers there and in results/<A>/<E>/<R>/. With `everything` (no config named: every config was planned):
    also the logs/ of an assignment's configuration folders no configuration has, and the prepare caches of
    .cache/ (derived) no plan references. A point's records (records/<A>/<E>/<R>/points/) only with `records`:
    those no plan has (never a configuration's cluster/ submissions). results/ is never removed, only
    listed."""
    remove: list[Path] = []
    kept: list[Path] = []
    outs, ress = _stage_dirs(planned)
    recs = {record_dir(s) for s in outs_stages(planned)}
    for p in planned:
        run_folders = tools.run_folders(p.errand, p.configuration)
        base_out, base_res, base_rec = run_folders.logs, run_folders.products, run_folders.points
        for folder in sorted(base_out.iterdir()) if base_out.is_dir() else ():
            if folder.is_dir() and folder not in outs and folder.name not in KEEP_NAMES:
                remove.append(folder)
        for folder in sorted(base_rec.iterdir()) if records and base_rec.is_dir() else ():
            if folder.is_dir() and folder not in recs and folder.name not in KEEP_NAMES:
                remove.append(folder)
        for folder in sorted(base_res.iterdir()) if base_res.is_dir() else ():
            if folder.is_dir() and folder not in ress and folder.name not in KEEP_NAMES:
                kept.append(folder)
        for root in (base_out, run_folders.results):
            if root.is_dir():
                remove.extend(sorted(f for f in root.rglob("*.partial*") if f.is_file()))
    if everything:
        used_runs: dict[str, set[Path]] = {}
        referenced: set[Path] = set()
        for p in planned:
            used_runs.setdefault(p.errand.assignment, set()).add(tools.run_folders(p.errand, p.configuration).record)
            for stage in [*p.every, *p.combined, *([p.pre] if p.pre else []), *([p.post] if p.post else [])]:
                for step in stage.rendered.values():
                    if step.prepare_dir is not None:
                        referenced.add(step.prepare_dir)
        for assignment, used in used_runs.items():
            root = records_root() / assignment
            for run_folder in sorted(root.iterdir()) if root.is_dir() else ():
                if run_folder.name.startswith(".") or not run_folder.is_dir():
                    continue
                for cfg in sorted(run_folder.iterdir()):           # another configuration's: its working folders only
                    if cfg.is_dir() and cfg not in used and (cfg / "logs").is_dir():
                        remove.append(cfg / "logs")
            cache = cache_root() / assignment
            for tool_dir in sorted(cache.iterdir()) if cache.is_dir() else ():
                if tool_dir.name in ("checks", "datasets", "plots") or not tool_dir.is_dir():   # plots/: the drawings' (V164)
                    continue
                for entry in sorted(tool_dir.iterdir()):
                    if entry.is_dir() and entry not in referenced:
                        remove.append(entry)
                        lock = entry.with_name(entry.name + ".lock")
                        if lock.exists():
                            remove.append(lock)
    return list(dict.fromkeys(remove)), kept


def remove(paths: list[Path]) -> int:
    """Deletes them (folders whole); returns the bytes freed."""
    freed = 0
    for path in paths:
        freed += _size(path)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    return freed
