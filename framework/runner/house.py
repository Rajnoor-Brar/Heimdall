"""Housekeeping: `hep ls`, `hep explain`, `hep status`, `hep clean` (rank 5, V74).

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
from .errors import HepError, did_you_mean
from .events import greeting, hubs
from .paths import configs_root, find_work, output_root, results_root
from .record import is_complete, complete_marker

TABLES = {"run": "run", "config": "config", "prelim": "prelim", "plot": "plot", "data": "data",
          "configuration": "configuration", "quantity": "quantity", "quantities": "quantity", "tool": "tool",
          "tools": "tool", "figure": "figure", "figures": "figure"}


# ── hep ls ─────────────────────────────────────────────────────────────────────────────────────

def importers() -> dict[str, list[str]]:
    """Every config another one imports ([config] or [file] import), with the configs that import it:
    <Project>/<name> → [<Project>/<name>, …]."""
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


def unused_tools(run) -> list[str]:
    """This file's own tool tables that no configuration runs (tools, pre, post, an @quantity's choice)
    or names in generate_cards: likely left over (an import's spare tables are its own business)."""
    used: set[str] = set()
    for configuration in run.configurations.values():
        for groups in (configuration.tools, configuration.pre, configuration.post):
            for group in groups:
                for entry in group:
                    if entry.startswith("@") and entry[1:] in run.quantities:
                        used |= {v for v in run.quantities[entry[1:]].values if isinstance(v, str)}
                    used.add(entry)
        used |= {entry.partition(":")[0] for entry in configuration.generate_cards}
    return [f"[tools.{tag}] is defined but no configuration runs it or names it in generate_cards"
            for tag in run.tools if tag not in used and f"tools.{tag}" not in run.included]


def config_names(project: str | None = None) -> list[str]:
    """Every configs/<Project>/<name>.toml that has a [run], as <Project>/<name>."""
    root = configs_root()
    names = []
    for path in sorted(root.glob(f"{project or '*'}/*.toml")):
        try:
            has_run = "run" in tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            has_run = True                                   # a broken file is listed, and says so
        if has_run:
            names.append(str(path.relative_to(root).with_suffix("")))
    return names


def ls(project: str | None = None) -> list[str]:
    """Each config, then each configuration: its title and description, and whether a sweep runs it."""
    names = config_names(project)
    if not names:
        raise HepError(f"no run TOML under {configs_root() / (project or '')}", hint="a config has a [run] table")
    lines = []
    for name in names:
        try:
            run = configmod.load(name)
        except HepError as error:
            lines.append(f"{name}   (does not load: {error.message})")
            continue
        swept = set(run.runs(None)) if run.sweep_runs else {run.raw.get("run", {}).get("configuration")}
        lines.append(f"{name}   run {run.name}" + ("   sweep_runs" if run.sweep_runs else ""))
        for key, configuration in run.configurations.items():
            mark = "*" if key in swept else " "
            about = configuration.description or (configuration.title if configuration.title != key else "")
            lines.append(f"  {mark} {key:16s} {about}")
    return lines


# ── hep explain ────────────────────────────────────────────────────────────────────────────────

def module_settings(key: str) -> list[str]:
    """`hep explain <Name>.exe[.<setting>]`: a module program's settings, as it lists them itself
    (`<Name>.exe --describe`, src/Module.hh): name, type, default, doc. Found in the work dir's build/."""
    name, _, setting = key.partition(".exe")
    setting = setting.lstrip(".")
    exe = Path(name + ".exe")
    if not exe.is_file():
        work = find_work()
        found = sorted((work / "build").rglob(f"{exe.name}")) if work is not None else []
        if not found:
            raise HepError(f"no program {exe.name} built in this work dir", hint="hep build makes it (build/<project>/)")
        exe = found[0]
    try:
        done = subprocess.run([str(exe), "--describe"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HepError(f"{exe.name} --describe did not answer: {error}") from None
    rows = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    if done.returncode != 0 or not rows and done.stderr.strip():
        raise HepError(f"{exe.name} --describe failed", hint=(done.stderr.strip().splitlines() or [""])[-1][:200])
    if setting:
        chosen = [r for r in rows if r["name"] == setting]
        if not chosen:
            raise HepError(f"{exe.name} reads no setting '{setting}'",
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
    """`hep explain <quantity>`: a vocabulary name's shape, unit, doc, who declared it, and how each tool
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
    "events": ("run", "event_count", "a configuration's may be a list: one configuration per count, <name>_<count>"),
    "chain": ("run", "tools", "[run]'s is every configuration's, unless one gives its own"),
    "vary": ("configuration", "sweeps", "a compound quantity's name sweeps its fields together"),
    "fixed": ("configuration", "static", "a quantity's own fixed = \"<tag>\" ([static] in v2), or a configuration's "
                                          "fixed = { quantity = \"<tag>\" }"),
    "points": ("quantity", "values", "rows { tag, value, label, style }: v2's values, tags, labels and styles"),
    "to": ("quantity", "key", "{ <target> = \"<key>\" or true }: v2's key and target in one table"),
    "card": ("tool", "baseconfig", ""), "output": ("tool", "output_file", ""),
    "uses": ("tool", "tool", "the tool folder of a second table of one tool; else the table's name is the tool"),
    "folder": ("configuration", "label", ""),
    "seed": ("run", "seed_type", "\"identity\", \"random\" or an integer (v2's seed_type and manual_seed)"),
    "commands": ("prelim", "commands", "[run] commands: run in each point's folder before its tools"),
}
#: What a table is, for `hep explain <table>`.
TABLE_TEXT = {
    "config": "[file] (v2's [config]): how the file is read: imports, a master, vars, meta",
    "run": "[run]: the run's name, project and defaults, which every configuration starts from",
    "configuration": "[cfgs.<name>] (v2's [run.cfgs.<name>]): one configuration: what it varies, fixes and runs",
    "quantity": "[quantities.<q>]: a quantity: its points, fixed point and bindings",
    "tool": "[tools.<tag>]: a tool table; its folder's own keys are `hep tools <folder>`",
    "plot": "[plot]: the pages", "figure": "[plot.figures.<f>]: one figure's pages", "data": "[plot.data]: reference data",
    "cluster": "[cluster]: hep cluster's Slurm keys (machine.toml, hep.toml, the run TOML, a configuration)",
    "prelim": "[prelim] (v2 only; v3 infers it): FIFOs, files and commands of each point",
}


def _special(key: str) -> list[str] | None:
    """What explain answers beyond a key of the schema: a table, a v3 name, a tool folder's option, a
    style key, deck.toml, machine.toml, [static]."""
    from . import tools as toolsmod
    word = key.strip("[]")
    table = TABLES.get(word, {"file": "config", "cfgs": "configuration"}.get(word))
    if table and "." not in word:
        entries = schema.keys(table)
        return [TABLE_TEXT.get(table, f"[{table}]"), *(f"  {k:16} {e.get('doc', '')}" for k, e in entries.items()),
                "  (hep explain <table>.<key> for one in full)"]
    last = word.rsplit(".", 1)[-1]                                       # events, run.events, tools.<tag>.card
    if last in V3_NAMES and (word == last or word.split(".")[0] in ("run", "cfgs", "quantities", "tools")):
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
                "  [cluster]                            hep cluster's defaults for every work dir here (04 §16)"]
    if word in ("deck", "deck.toml"):
        return ["deck.toml: a deck's recipe (04 §15)",
                *(f"  {k:16} {e.get('doc', '')}" for t in schema.DECK_TABLES for k, e in schema.keys(t).items())]
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
    `plot.y_gutter`, `[plot].y_gutter`, `run.event_count`, `quantities.<q>.styles`, `tools.<tag>.shards`,
    `plot.figures.<figure>.logy`, `run.cfgs.<cfg>.threads` (a configuration's, V98); a bare key is looked
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
        raise HepError("explain which key?", hint="e.g. hep explain plot.y_gutter")
    found = []
    if len(parts) >= 2 and parts[0] in TABLES:
        table = TABLES[parts[0]]
        if parts[0] == "run" and len(parts) >= 3 and parts[1] == "cfgs":   # a configuration's (V98)
            table = "configuration"
        name = parts[-1]
        if name in schema.keys(table):
            found.append((table, name))
    else:
        found = [(table, parts[-1]) for table in schema.spec() if table != "sections" and parts[-1] in schema.keys(table)]
    if not found:
        every = sorted({k for t in schema.spec() if t != "sections" for k in schema.keys(t)})
        raise HepError(f"no key '{key}' in the schema", hint=did_you_mean(parts[-1], every) or
                       "keys are written as plot.y_gutter, run.event_count, quantities.<q>.styles")
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
            lines.append("  a configuration inherits it from [run]")
        if entry.get("default_ok"):
            lines.append('  "default": the layer below\'s value, as if left out (v2\'s [plot] itself: the drawing tool\'s own)')
        if entry.get("native_ok"):
            lines.append('  "native": what the drawing tool does by itself, at any level')
        if entry.get("doc"):
            lines.append(f"  {entry['doc']}")
        if entry.get("notes"):
            lines += [""] + [f"  {line}" for line in textwrap.wrap(entry["notes"], 96)]
    return lines + ([""] + vocab if vocab else [])


# ── hep status ─────────────────────────────────────────────────────────────────────────────────

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


def running_configs() -> dict[str, list[str]]:
    """The jobs running on this machine (their watch sockets): config path → its configurations."""
    out: dict[str, list[str]] = {}
    for name in hubs():
        hello = greeting(name)
        if hello:
            out.setdefault(hello.get("config", ""), []).extend(hello.get("configurations", []))
    return out


def point_state(plan) -> str:
    """complete; stale (complete for an earlier identity: a changed setup reruns it); incomplete (begun,
    not done: failed, stopped or running); to run (never begun)."""
    if is_complete(plan):
        return "complete"
    if complete_marker(plan).exists():
        return "stale"
    if plan.out.exists() and any(plan.out.iterdir()):
        return "incomplete"
    return "to run"


def status(planned: list, running: dict[str, list[str]]) -> list[str]:
    """Per configuration, a line per point: its state, when it finished, its results' size."""
    lines = []
    for p in planned:
        stages = [*([p.pre] if p.pre else []), *p.every, *p.combined, *([p.post] if p.post else [])]
        states = [point_state(s) for s in stages]
        live = p.configuration.key in running.get(str(p.run.path), [])
        counts = ", ".join(f"{states.count(s)} {s}" for s in ("complete", "stale", "incomplete", "to run") if states.count(s))
        lines.append(f"{p.run.name} · {p.configuration.key} ({tools.run_dir(p.run, p.configuration)}): {counts}"
                     + ("   [running]" if live else ""))
        for stage, state in zip(stages, states):
            when = ""
            provenance = stage.out / "provenance.json"
            if state == "complete" and provenance.exists():
                when = time.strftime("%Y-%m-%d %H:%M", time.localtime(provenance.stat().st_mtime))
            size = _human(_size(stage.res)) if stage.res.exists() else ""
            lines.append(f"  {stage.point.name:24s} {state:10s} {when:16s} {size}")
    return lines


# ── hep clean ──────────────────────────────────────────────────────────────────────────────────

def _stage_dirs(planned) -> tuple[set[Path], set[Path]]:
    outs, ress = set(), set()
    for p in planned:
        for stage in [*([p.pre] if p.pre else []), *p.every, *p.combined, *([p.post] if p.post else [])]:
            outs.add(stage.out)
            ress.add(stage.res)
    return outs, ress


def clean_targets(planned: list, everything: bool) -> tuple[list[Path], list[Path]]:
    """What `hep clean` removes, and the results it only lists. Within each planned configuration's
    folder: point folders no plan has (output side), and `.partial` leftovers (both sides). With
    `everything` (no config named: every config was planned): also a project's run folders no
    configuration has, and prepare cache entries no plan references."""
    remove: list[Path] = []
    kept: list[Path] = []
    outs, ress = _stage_dirs(planned)
    keep_names = {"plots", "pre", "post"}
    for p in planned:
        base_out = output_root() / tools.run_dir(p.run, p.configuration)
        base_res = results_root() / tools.run_dir(p.run, p.configuration)
        for folder in sorted(base_out.iterdir()) if base_out.is_dir() else ():
            if folder.is_dir() and folder not in outs and folder.name not in keep_names:
                remove.append(folder)
        for folder in sorted(base_res.iterdir()) if base_res.is_dir() else ():
            if folder.is_dir() and folder not in ress and folder.name not in keep_names:
                kept.append(folder)
        for root in (base_out, base_res):
            if root.is_dir():
                remove.extend(sorted(f for f in root.rglob("*.partial*") if f.is_file()))
    if everything:
        used_runs: dict[str, set[Path]] = {}
        referenced: set[Path] = set()
        for p in planned:
            used_runs.setdefault(p.run.project, set()).add(output_root() / tools.run_dir(p.run, p.configuration))
            for stage in [*p.every, *p.combined, *([p.pre] if p.pre else []), *([p.post] if p.post else [])]:
                for step in stage.rendered.values():
                    if step.prepare_dir is not None:
                        referenced.add(step.prepare_dir)
        for project, used in used_runs.items():
            root = output_root() / project
            for run_folder in sorted(root.iterdir()) if root.is_dir() else ():
                if run_folder.name.startswith(".") or not run_folder.is_dir():
                    continue
                for cfg in sorted(run_folder.iterdir()):
                    if cfg.is_dir() and cfg not in used and not any(u.is_relative_to(cfg) or cfg.is_relative_to(u) for u in used):
                        remove.append(cfg)
            cache = root / ".cache"
            for tool_dir in sorted(cache.iterdir()) if cache.is_dir() else ():
                if tool_dir.name in ("checks", "datasets") or not tool_dir.is_dir():
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
