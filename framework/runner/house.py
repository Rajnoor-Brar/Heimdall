"""Housekeeping: `heimdall ls`, `heimdall explain`, `heimdall status`, `heimdall clean` (rank 5, V74).

doc:everyday. Nothing here runs a tool; `clean` is the only command
that deletes, and only what the runner made and no plan uses (it never deletes from results/ but a
product's `.partial` leftover, and it refuses while a job is running).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import re
import textwrap
import time
import tomllib
from pathlib import Path

from . import config as configmod
from . import knowledge, schema, tools
from .errors import HeimdallError, did_you_mean
from . import runs
from .events import greeting, hubs
from .paths import cache_root, configs_root, find_work, records_root, results_root
from .record import (cause_text, constants, constants_lines, held_by, holder, provenance_file, read_labels, record_dir,
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
    before the Assignment/Errand names), so that reading it says what rewrites it."""
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


def _score_names() -> list[str]:
    from stats import means, metrics
    return [*metrics.REGISTRY, *means.REGISTRY]


def _score_lines(name: str) -> list[str]:
    """`heimdall explain score`: the keys of [score], the metrics by purpose and the means; `score.<name>` one in full."""
    from stats import means, metrics
    if name in metrics.REGISTRY:
        m = metrics.REGISTRY[name]
        thresholds = f"good {m.thresholds[0]:g}, bad {m.thresholds[1]:g}" if m.thresholds else "none (give [score].thresholds to score it)"
        return [f"metric {name}: {metrics.PURPOSES[m.purpose]}", f"  better     {m.better}", f"  thresholds {thresholds}",
                *([f"  because    {m.why}"] if m.why else []), f"  on         {'by default' if m.default else 'when named in [stats].metrics'}",
                f"  needs      {'a reference' if m.needs_reference else 'no reference'}{', and the page\'s other curves' if m.pool else ''}",
                f"  {m.note}"]
    if name in means.REGISTRY:
        m = means.REGISTRY[name]
        return [f"mean {name}: {m.kind}", f"  guard   {m.guard}", f"  error   {m.error_kind}", *([f"  takes   {', '.join(m.settings)}"] if m.settings else []), f"  {m.note}"]
    lines = ["[score]: how the statistics become a score (heimdall explain score.<key> for a key, score.<metric or mean> for one in full)"]
    lines += [f"  {k:12} {knowledge.plain(c["doc"])[:90]}" for k, c in schema.keys("score").items()]
    for purpose, title in metrics.PURPOSES.items():
        lines += ["", f"metrics, {title.lower()}:"]
        lines += [f"  {n:14} {'(default) ' if m.default else ''}{m.note[:80]}" for n, m in metrics.REGISTRY.items() if m.purpose == purpose]
    lines += ["", "means (scalar over pages; ensemble over histograms):"]
    lines += [f"  {n:18} {m.kind:8} {m.error_kind:11} {m.note[:60]}" for n, m in means.REGISTRY.items()]
    return lines


def _special(key: str) -> list[str] | None:
    """What explain answers beyond a key of the schema: a table, a v3 name, a tool folder's option, a
    style key, a report's recipe, machine.toml, [static]."""
    from . import tools as toolsmod
    word = key.strip("[]")
    if word == "stack" or word.startswith("stack."):                     # recipes/settings.toml
        stack = {k: (v, c) for k, v, c in schema.stack_entries()}
        name = word.removeprefix("stack").lstrip(".")
        if name in stack:
            return _stack_lines(name, stack[name])
        return ["the stack's build settings (recipes/settings.toml; heimdall stack build key=value, or machine.toml's [settings])",
                *(f"  {k:24} {knowledge.plain(c)[:90]}" for k, (_, c) in stack.items() if k.startswith(name)),
                "  (heimdall explain stack.<key> for one in full)"]
    if word == "style" or (word.startswith("style.") and not any(d == word[6:] for d, _, _ in schema.style_entries())):
        at = word.removeprefix("style").lstrip(".")
        rows = [(d, c) for d, _, c in schema.style_entries() if d.startswith(at)]
        if rows:
            return [f"style{'.' + at if at else ''}: a page's style (src/Apps/Paint/base.toml), set in [plot.style], a figure's style or a style file",
                    *(f"  {d:30} {knowledge.plain(c)[:80]}" for d, c in rows), "  (heimdall explain style.<key> for one in full)"]
    if word.split(".")[0].split("]")[0] == "run":                         # the old names
        raise HeimdallError(f"[run] is now [errand]: {key}",
                       hint="heimdall explain errand" + word.removeprefix("run").replace("]", "").replace(".project", ".assignment"))
    if word == "score" or (word.startswith("score.") and word[6:] in _score_names()):
        return _score_lines(word.removeprefix("score").lstrip("."))
    table = TABLES.get(word, {"file": "config", "cfgs": "configuration"}.get(word))
    if table and "." not in word:
        v3 = {"file": "file", "cfgs": "cfgs", "errand": "errand", "tools": "tools", "quantities": "quantities"}.get(word)
        entries = schema.v3_entries(v3) if v3 else schema.keys(table)
        return [TABLE_TEXT.get(table, f"[{table}]"), *(f"  {k:16} {e.get('doc', '')}" for k, e in entries.items()),
                "  (heimdall explain <table>.<key> for one in full)"]
    last = word.rsplit(".", 1)[-1]                                       # events, errand.events, tools.<tag>.card
    if last in V3_NAMES and (word == last or word.split(".")[0] in ("errand", "cfgs", "quantities", "tools")):
        word = last
        table, old, note = V3_NAMES[word]
        entry = schema.keys(table).get(old, {})
        return [word, *(_entry_lines(entry) if entry else []), *([f"  {note}"] if note else [])]
    if word in ("static",):
        return ["[static] (v2; v3: each quantity's fixed): quantity = tag, the point of a quantity no configuration varies"]
    if word in ("machine.toml", "machine"):
        return ["machine.toml (Himinbjorg's; recipes/machine.template.toml): this machine's layer",
                "  [settings] [env] [packages.<name>]  the stack's build: over the recipes and toolkits",
                "  [cluster]                            heimdall cluster's defaults for every work dir here"]
    if word.startswith("report.section."):                  # V209: [[report.section]]'s keys are the schema's section
        word = word.removeprefix("report.")
    if word in ("report", "section", "report.section", "report.toml"):
        tables = ("section",) if word.endswith("section") else schema.REPORT_TABLES
        return ["a report's recipe: [report] and its [[report.section]]s, in configs/<A>/<E>.toml ([report] alone), "
                "an errand file or a folder's report.toml",
                *(f"  {('report.' if t == 'section' else '') + t + '.' + k:30} {e.get('doc', '')}"
                  for t in tables for k, e in schema.keys(t).items())]
    if word.split(".")[0] in schema.REPORT_TABLES and word.count(".") == 1:
        table, key = word.split(".")
        entry = schema.keys(table).get(key)
        if entry is not None:
            return [f"{word} (a report's recipe)", f"  type     {entry.get('type', '')}",
                    *([f"  default  {entry['default']}"] if "default" in entry else []), f"  {entry.get('doc', '')}"]
    style = word.removeprefix("style.")
    for dotted, default, comment in schema.style_entries():
        if dotted == style:
            return [f"style {dotted} (src/Apps/Paint/base.toml; a style layer's key)",
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


def _other_table(parts: list[str]) -> tuple[str, dict] | None:
    """A key the schema holds under another name, or in a table of another: v3's tables, a figure's, a report's section."""
    last, entries = parts[-1], None
    if parts[:2] == ["errand", "cfgs"]:
        entries = schema.v3_entries("cfgs")
    elif parts[0] == "config":
        entries = schema.v3_entries("file")
    elif parts[0] in schema.v3_tables():
        entries = schema.v3_entries(parts[0])
    elif parts[:2] == ["plot", "figures"]:
        entries = schema.spec().get("figure", {})
    elif parts[:2] == ["report", "section"]:
        entries = schema.keys("section")
    elif parts[:1] == ["stats"]:
        entries = schema.keys("stats")
    return (f"{'.'.join(parts)}", entries[last]) if entries and last in entries else None


def _stack_lines(name: str, value_comment: tuple[str, str]) -> list[str]:
    value, comment = value_comment
    return [f"stack.{name} (recipes/settings.toml; heimdall stack build {name}=…, or machine.toml's [settings])",
            f"  default  {value}", *([f"  {knowledge.plain(comment)}"] if comment else [])]


def _entry_lines(entry: dict) -> list[str]:
    """A key's facts, for a name the schema holds under another: its type, default and meaning."""
    return [f"  type     {knowledge.kind_of(entry)}", *([f"  default  {entry['default']!r}"] if "default" in entry else []),
            *([f"  {knowledge.plain(entry['doc'])}"] if entry.get("doc") else [])]


def _key_lines(title: str, entry: dict) -> list[str]:
    """A key in full: its type, default, values and meaning."""
    lines = [title]
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
        lines.append(f'  "default": {knowledge.KEYWORDS["default_ok"][1]}')
    if entry.get("native_ok"):
        lines.append(f'  "native": {knowledge.KEYWORDS["native_ok"][1]}')
    if entry.get("doc"):
        lines.append(f"  {entry['doc']}")
    if entry.get("notes"):
        lines += [""] + [f"  {line}" for line in textwrap.wrap(entry["notes"], 96)]
    return lines


def explain(key: str) -> list[str]:
    """A key's type, default, choices, bounds, inheritance and doc, from framework/schema/run.toml.
    `plot.y_gutter`, `[plot].y_gutter`, `errand.event_count`, `quantities.<q>.styles`, `tools.<tag>.shards`,
    `plot.figures.<figure>.logy`, `errand.cfgs.<cfg>.threads` (a configuration's, V98); a bare key is looked
    up in every table."""
    if re.search(r"\.exe\b", key):                                      # a module program's own settings
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
    if not found and (other := _other_table(parts)) is not None:
        return _key_lines(*other)
    if not found and len(parts) == 1 and any(k == parts[0] for k, _, _ in schema.stack_entries()):
        return _stack_lines(parts[0], next((v, c) for k, v, c in schema.stack_entries() if k == parts[0]))
    if not found:
        every = sorted({k for t in schema.spec() if t != "sections" for k in schema.keys(t)})
        raise HeimdallError(f"no key '{key}' in the schema", hint=did_you_mean(parts[-1], every) or
                       "keys are written as plot.y_gutter, errand.events, cfgs.<name>.threads, quantities.<q>.points")
    lines = []
    if len(parts) == 1 and parts[0] in (stack := {k: (v, c) for k, v, c in schema.stack_entries()}):   # a stack setting too
        lines += [*_stack_lines(parts[0], stack[parts[0]]), ""]
    for table, name in found:
        lines += _key_lines(f"[{table}].{name}", schema.keys(table)[name])
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


def _states(entries: list[dict], by_pid: dict) -> list[tuple[dict, str]]:
    """Each entry with what it says now (runs.state); a cluster submission's from one squeue for them all (V184)."""
    states = [(e, runs.state(e, by_pid)) for e in entries]
    submitted = [e for e, s in states if e.get("kind") == "cluster" and s == "submitted"]
    if submitted and shutil.which("squeue"):
        from .cluster import active
        queued = {line.split("|")[0].split("_")[0] for line in active([str(j) for e in submitted for j in e.get("jobs", [])])}
        states = [(e, ("on Slurm" if {str(j) for j in e.get("jobs", [])} & queued else "ended") if e in submitted else s)
                  for e, s in states]
    return states


def _going(e: dict, state: str) -> bool:
    """Whether an entry's job still goes: running, or where this process cannot tell; a submission on Slurm."""
    return state.startswith("running") or state.startswith("on ") or state == "in another PID namespace" \
        or (e.get("kind") == "cluster" and state in ("submitted", "on Slurm"))


def _unrecorded(states: list[tuple[dict, str]], by_pid: dict) -> list[tuple[dict, str]]:
    """The live sockets with no entry of a going job (a run from inside an image), as entries."""
    recorded = {e.get("pid") for e, s in states if _going(e, s) and e.get("host") == runs.host()}
    return [({"id": f"(pid {hello.get('pid')})", **hello, "configurations": hello.get("configurations")},
             "running (unrecorded)") for pid, hello in by_pid.items() if pid not in recorded]


def live_entries(entries: list[dict], live: list[tuple[str, dict]]) -> list[tuple[dict, str]]:
    """The live runs, (entry, state), as `heimdall runs` numbers them, `heimdall watch -i` and `heimdall runs
    --resume`/`--forget` take them: the going jobs (recorded, and live sockets with no entry) and the paused runs
    neither resumed nor forgotten (runs.paused), in the order they began; a run that resumed a pause in that pause's
    place (its `resumed_by` chain's first start). [N] is the Nth, recomputed each time: a run that ends drops out."""
    by_pid = {hello.get("pid"): hello for _, hello in live}
    states = _states(entries, by_pid)
    resumed = {e["resumed_by"]: e for e in entries if e.get("resumed_by")}

    def began(e: dict, seen: frozenset = frozenset()) -> float:
        before = resumed.get(e.get("id"))
        if before is not None and before.get("id") not in seen:
            return began(before, seen | {e.get("id")})
        return e.get("started") or 0

    chosen = [(e, s) for e, s in states if _going(e, s) or runs.paused(e)] + _unrecorded(states, by_pid)
    return sorted(chosen, key=lambda item: (began(item[0]), item[0].get("started") or 0, item[0].get("id", "")))


def live_line(index: int, e: dict, state: str) -> str:
    """One live run in a line, for a refusal that lists them: `[2] <id>  <A>/<E> · <configurations> · paused`."""
    cfgs = ", ".join(e.get("configurations") or ([e["configuration"]] if e.get("configuration") else []))
    return f"[{index}] {e.get('id', '?')}  {_config_name(e.get('config', ''), e.get('work'))} · {cfgs} · {state}"


#: The states `heimdall runs --state` takes: what `runs.state` says first (a cluster submission's too).
RUN_STATES = ("running", "paused", "failed", "stopped", "done", "lost", "not run", "submitted", "on Slurm", "ended", "cancelled")

#: SGR codes of the listing's colour (never left to a library: `[N]` is no markup, and a test reads them).
SGR = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "magenta": "35", "cyan": "36", "grey": "90"}
STATE_STYLE = {"running": "green", "paused": "yellow", "failed": "red", "stopped": "magenta", "done": "dim", "lost": "grey"}


def wants_colour(stream, plain: bool = False) -> bool:
    """Colour for a listing: a terminal, not asked for plain, no NO_COLOR (set and not empty) and no dumb TERM."""
    import os
    return bool(getattr(stream, "isatty", lambda: False)()) and not plain and not os.environ.get("NO_COLOR") \
        and os.environ.get("TERM") != "dumb"


def paint(text: str, style: str, on: bool) -> str:
    return f"\x1b[{SGR[style]}m{text}\x1b[0m" if on and text else text


def link(shown: str, host: str, path: str, on: bool) -> str:
    """`shown` an OSC 8 hyperlink to file://<host><path> (a terminal checks the host, so over ssh a click opens no wrong
    file); `shown` alone when `on` is off, or the path is not absolute."""
    if not on or not shown or not path.startswith("/"):
        return shown
    from urllib.parse import quote
    return f"\x1b]8;;file://{host}{quote(path)}\x1b\\{shown}\x1b]8;;\x1b\\"


def state_word(state: str) -> str:
    """The first word of a state (`done, resumed` is done; `running (not reachable from here)` running)."""
    return state.split(",")[0].split(" (")[0].strip()


def check_states(text: str) -> set[str]:
    """`--state running,failed`: the states named, or refused with the list."""
    wanted = {part.strip() for part in text.split(",") if part.strip()}
    for name in wanted:
        if name not in RUN_STATES:
            raise HeimdallError(f"no such state '{name}'", hint="the states: " + ", ".join(RUN_STATES))
    return wanted


def _cut(text: str, width: int | None) -> str:
    """A line cut to `width` with a mark (its start, the index, is never cut): none when there is no width."""
    return text if not width or len(text) <= width else text[:max(width - 1, 1)] + "…"


def runs_listing(entries: list[dict], live: list[tuple[str, dict]], titles: dict[str, str],
                 now: float | None = None, limit: int | None = None, days: int | None = None,
                 states: set[str] | None = None, color: bool = False, width: int | None = None,
                 only: dict | None = None) -> list[str]:
    """`heimdall runs` (V182): the live runs by default (running, recorded or a live socket with no entry,
    unrecorded, as from inside an image; and paused), each with its index [N] (live_entries); `limit`, the latest N
    of any state; `days`, all begun within that age; `states` keeps those in these states (a live run keeps its [N]).
    Oldest first, a block each (a history list's names the run's id first, a live one's its [N]):
        [N] <host> | <work dir's title> | <config> [<configurations>]
            MM-DD HH:MM · <span>
            <A>/<E> · NN_cfg [tag], …   <points done, failed, stopped> (once it ended)
            <state> · <P> at once · <done>/<total> (<F> failed)       (NULL: not recorded, as by an older entry)
            pid P : heimdall watch -i N · heimdall stop -i N          (a pause's resume and forget, a failed or
            log <path>                                                 stopped one's --again, a cluster submission's)
    `color`: the state, the index, the commands and the log in colour (the caller says: wants_colour); `width`: the
    first line cut to it; `only`: this entry alone (of any list; a live one with its [N], its id first)."""
    now = time.time() if now is None else now
    by_pid = {hello.get("pid"): hello for _, hello in live}
    live_numbers = {id(e): n for n, (e, _) in enumerate(live_entries(entries, live), 1)}
    if only is not None:
        found = _states(entries, by_pid)
        selected = [(e, s) for e, s in found if e.get("id") == only.get("id")]
        heading = "run"
    elif limit is None and days is None:
        selected = live_entries(entries, live)
        heading = "live"
    else:
        found = _states(entries, by_pid)
        unrecorded = _unrecorded(found, by_pid)
        if limit is not None:
            selected = sorted(found + unrecorded, key=lambda item: (item[0].get("started") or 0, item[0].get("id", "")),
                              reverse=True)[:limit]
            heading = f"latest {limit} runs"
        else:
            cutoff = now - (days or 0) * 86400
            selected = [(e, s) for e, s in found + unrecorded if cutoff <= (e.get("started") or 0) <= now]
            heading = f"runs from the last {days} days"
        selected.sort(key=lambda item: (item[0].get("started") or 0, item[0].get("id", "")))
    live_list = heading == "live"
    numbers = {id(e): n for n, (e, _) in enumerate(selected, 1)} if live_list else live_numbers
    if states is not None:
        selected = [(e, s) for e, s in selected if state_word(s) in states]

    def where(work: str | None) -> str:
        return titles.get(work or "", "") or (Path(work).name if work else "")

    def row(e: dict, state: str, number: int | None) -> list[str]:
        started = e.get("started") or 0
        span = _ago((e.get("finished") or now) - started)
        when = time.strftime("%m-%d %H:%M", time.localtime(started))
        what = _config_name(e.get("config", ""), e.get("work"))
        keys = [k for k in (e.get("configurations") or ([e["configuration"]] if e.get("configuration") else [])) if k]
        serials, tags = e.get("configuration_serials", {}), e.get("configuration_tags", {})
        made = ", ".join((f"{serials[key]:02d}_{key}" if isinstance(serials.get(key), int) else key)
                         + (f" [{tags[key]}]" if tags.get(key) else "") for key in keys)      # NN_ only when it is known
        prefix = (f"[{number}] " if number else "") + ("" if live_list else f"{e.get('id', '?')} ")
        head = _cut(f"{prefix}{e.get('host') or runs.host()} | {where(e.get('work'))} | {what}"
                    + (f" [{', '.join(keys)}]" if keys else ""), width)
        if number:
            head = paint(f"[{number}]", "bold", color) + head[len(f"[{number}]"):]
        config_line = f"    {what} · {made}" if made else f"    {what}"
        if counts := e.get("counts"):                                   # V202: its points
            config_line += (f"   {counts.get('done', 0)} done"
                            + (f" ({counts['warned']} with warnings)" if counts.get("warned") else "")
                            + f", {counts.get('failed', 0)} failed"
                            + (f", {counts['stopped']} stopped" if counts.get("stopped") else ""))
        going, word = state.startswith("running"), state_word(state)
        completed, total = e.get("points_completed"), e.get("points_total")
        parts = [paint(state, STATE_STYLE.get(word, ""), color) if word in STATE_STYLE else state]
        size, active = e.get("parallelism"), e.get("active_parallel_points")
        if going and size is not None and active is not None:
            parts.append(f"{active} of {size} at once")
        elif size is not None:
            parts.append(f"{size} at once")
        parts.append(f"{completed if completed is not None else 'NULL'}/{total if total is not None else 'NULL'}"
                     + (f" ({e['points_failed']} failed)" if not e.get("counts") and e.get("points_failed") else ""))
        tail = []
        if e.get("kind") == "cluster":
            tail.append(f"    cluster jobs {', '.join(map(str, e.get('jobs', [])))}: "
                        + paint(f"heimdall cluster {what} {e.get('configuration', '')} --status", "cyan", color))
        elif going:
            watch = f"-i {number}" if number else f"--pid {e.get('pid')}"
            tail.append(f"    pid {e.get('pid')} : " + paint(f"heimdall watch {watch} · heimdall stop {watch}", "cyan", color))
        elif number and runs.paused(e):
            tail.append("    " + paint(f"heimdall runs --resume {number} · heimdall runs --forget {number}", "cyan", color))
        elif word in ("failed", "stopped", "lost") and e.get("id"):
            tail.append("    " + paint(f"heimdall runs --again {e['id']}", "cyan", color))
        if e.get("log"):
            tail.append("    log " + link(paint(e["log"], "dim", color), e.get("host") or runs.host(), e["log"], color))
        return [head.rstrip(), f"    {when} · {span}", config_line.rstrip(), "    " + " · ".join(parts), *tail]

    if not selected:
        if states is not None and (limit is not None or days is not None or live_list):
            return [f"no {'/'.join(sorted(states))} runs here" + ("" if limit is None and days is None else " in that list")]
        if limit is None:
            if days is not None:
                return [f"no runs in the last {days} days on this machine ({runs.folder()})"]
            return [f"no live runs on this machine: none running, none paused ({runs.folder()})"]
        return [f"no runs on this machine in the last {runs.KEEP_DAYS} days ({runs.folder()})"]
    lines = [heading]
    for i, (entry, state) in enumerate(selected):
        if i:
            lines.append("")
        lines += row(entry, state, numbers.get(id(entry)))
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


def tag_lines(record: Path, words: list[str] | None = None, clear: bool = False) -> list[str]:
    """`heimdall tag RECORD [WORD …] [--clear]` (V223): the folder's tag and labels, or them set or removed, in its record
    (records/<A>/<E>/<R>/tag, the source of truth) and, when the folder has one, its plot document's [source]. A word
    `key=value` sets that label, `key=` removes it, and a bare word is the tag (`tag=<word>`); `--clear` removes all, and a
    tag that stays cleared, so its configuration's `tag` key does not give it again."""
    from .config import check_tag
    from .plotdoc import path_of, write_tag
    from .record import check_label_key, read_labels, write_labels
    rel = record.relative_to(records_root())
    words = list(words or [])
    if clear and words:
        raise HeimdallError("a tag to give and --clear: one or the other", hint=f"heimdall tag {rel} --clear")
    had = read_labels(record)
    shown = {k: v for k, v in (had or {}).items() if v}
    if not words and not clear:
        return [f"{rel}: " + ", ".join(f"{k}={v}" if k != "tag" else str(v) for k, v in shown.items()) if shown else f"{rel} has no tag"]
    labels = dict(had or {})
    said = []
    for word in words:
        key, equals, value = word.partition("=")
        if not equals:                                       # a bare word: the tag
            was = labels.get("tag")
            labels["tag"] = check_tag(word, "heimdall tag WORD")
            said.append(f"tagged {word}" + (f" (was {was})" if was and was != word else ""))
            continue
        if key != "tag":
            check_label_key(key, f"heimdall tag {word}")
        if value:
            labels[key] = check_tag(value, f"heimdall tag {word}")
            said.append(f"{key} = {value}")
        else:
            labels.pop(key, None)
            said.append(f"{key} removed")
        if key == "tag" and not value:
            labels["tag"] = ""
    if clear:
        labels = {"tag": ""}
    write_labels(record, labels)
    document = path_of(results_root() / rel)
    if document.is_file():
        write_tag(document, labels.get("tag"), {k: v for k, v in labels.items() if k != "tag"})
    if clear:
        gone = [f"its tag {shown['tag']}" if k == "tag" else f"{k}={v}" for k, v in shown.items()]
        return [f"{rel}: " + ", ".join(gone) + " removed" if shown else f"{rel} has no tag"]
    return [f"{rel}: " + ", ".join(said)]


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


def _json_of(path: Path) -> dict:
    """A record's JSON file as a dict; {} when it is not there or not readable (a claim to check, never a failure)."""
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _attempt_rows(record: Path, point: str) -> list[dict]:
    rows = []
    try:
        for line in (record / "points" / point / "attempts.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return rows


def _sigma(rows: list[dict]) -> tuple[list | None, str]:
    """A point's cross section, [σ pb, its error], from what its latest attempt's tools reported (`reported.xsec_pb`, which a
    generator's reader sets); else None and why: a σ read from the products needs a reader of that tool's file."""
    if not rows:
        return None, "no attempt recorded"
    for tag, result in (rows[-1].get("tools") or {}).items():
        found = (result.get("reported") or {}).get("xsec_pb")
        if isinstance(found, list) and found:
            return found, f"reported by {tag}"
    return None, "no tool of the latest attempt reported a cross section"


def show_data(record: Path, point: str | None = None, tag: str | None = None, parts: bool = False) -> dict:
    """`heimdall show RECORD[/POINT[/TAG]]` (names P2): what a Run, a point or a tool did, read from the record alone
    (points.json, the points' identity.json, provenance.json and attempts.jsonl, and their logs), nothing run or checked.
    The Run's view lists its points; a point's has its identity, seed, tools, σ and products (`parts`: the identity's own
    parts); a tool's is its provenance entry and the end of its log."""
    rel = str(record.relative_to(records_root()))
    table = _json_of(record / "points.json")
    labels = read_labels(record) or {}
    if point is None:
        found = {}
        for entry in table.get("points") or []:
            rows = _attempt_rows(record, entry.get("name", ""))
            found[entry["name"]] = {"state": entry.get("state", "?"), "attempts": len(rows),
                                    "events": None, "seed": entry.get("seed")}
        if not table:
            for folder in sorted((record / "logs").iterdir()) if (record / "logs").is_dir() else []:
                if folder.is_dir():
                    rows = _attempt_rows(record, folder.name)
                    found[folder.name] = {"state": rows[-1].get("verdict", "?") if rows else "?", "attempts": len(rows),
                                          "events": None, "seed": None}
        consts = table.get("constants") or {}
        return {"view": "run", "record": rel, "tag": labels.get("tag") or "",
                "labels": {k: v for k, v in labels.items() if k != "tag" and v},
                "errand": table.get("run"), "configuration": table.get("configuration"), "config_file": table.get("config_file"),
                "events": consts.get("events"), "threads": consts.get("threads"), "seeds": consts.get("seeds"),
                "parallelism": consts.get("parallelism"), "points": found,
                "results": str(results_root() / Path(rel)), "records": str(record)}
    entry = next((e for e in table.get("points") or [] if e.get("name") == point), {})
    rows = _attempt_rows(record, point)
    if not entry and not rows and not (record / "points" / point).is_dir():
        names = sorted(e["name"] for e in table.get("points") or [])
        raise HeimdallError(f"no point {point} in {record.name}", hint=did_you_mean(point, names) or
                       (f"its points: {', '.join(names[:8])}{' …' if len(names) > 8 else ''}" if names else "it has none"))
    ident = _json_of(record / "points" / point / "identity.json")
    prov = _json_of(record / "points" / point / "provenance.json")
    if tag is not None:
        mine = next((t for t in prov.get("tools") or [] if t.get("tag") == tag), None)
        logfile = record / "logs" / point / f"{tag}.log"
        if mine is None and not logfile.is_file():
            there = [t.get("tag") for t in prov.get("tools") or []]
            raise HeimdallError(f"no tool {tag} in {rel}/{point}", hint=did_you_mean(tag, there) or
                           (f"its tools: {', '.join(there)}" if there else "it recorded no tools"))
        tail = logfile.read_text(encoding="utf-8", errors="replace").splitlines()[-20:] if logfile.is_file() else []
        return {"view": "tool", "record": rel, "point": point, "tag": tag, "provenance": mine, "log_tail": tail}
    sigma, why = _sigma(rows)
    last = rows[-1] if rows else {}
    out = {"view": "point", "record": rel, "point": point, "state": entry.get("state") or last.get("verdict") or "?",
           "identity": prov.get("identity") or entry.get("identity"), "seed": prov.get("seed", entry.get("seed")),
           "events": prov.get("events"), "threads": prov.get("threads"),
           "values": {k: v.get("tag") or v.get("value") for k, v in (prov.get("values") or {}).items()},
           "attempts": [{"n": r.get("n"), "finished": r.get("finished", ""), "verdict": r.get("verdict"),
                         "cause": cause_text(r)} for r in rows],
           "tools": [{"tag": t.get("tag"), "tool": t.get("tool"), "version": t.get("version"),
                      "exit": (t.get("result") or {}).get("exit"), "seconds": (t.get("result") or {}).get("seconds")}
                     for t in prov.get("tools") or []],
           "sigma_pb": sigma, "sigma_note": why,
           "products": sorted(entry.get("products") or {}),
           "provenance": {k: prov.get(k) for k in ("host", "user", "started", "finished", "git", "work") if k in prov},
           "log_tail": []}
    if parts:
        out["parts"] = ident
    logs = record / "logs" / point
    for path in sorted(logs.glob("*.log")) if logs.is_dir() else []:
        if not path.name.endswith(".full.log"):
            out["log_tail"].append({"log": path.name, "lines": path.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]})
    return out


def show_lines(data: dict) -> list[str]:
    """show_data's view as the plain text `heimdall show` prints."""
    rel = data["record"]
    if data["view"] == "run":
        head = f"{rel}" + (f"  [{data['tag']}]" if data["tag"] else "")
        out = [head]
        out += [f"  {k} = {v}" for k, v in data["labels"].items()]
        out.append(f"  errand {data['errand'] or '–'} · configuration {data['configuration'] or '–'}"
                   + (f" · {data['config_file']}" if data["config_file"] else ""))
        out.append(f"  events {data['events'] if data['events'] is not None else '–'} · threads {data['threads'] if data['threads'] is not None else '–'}"
                   f" · seeds {data['seeds'] or '–'} · parallelism {data['parallelism'] if data['parallelism'] is not None else '–'}")
        counts = ", ".join(f"{n} {s}" for s in STATES if (n := sum(1 for p in data["points"].values() if p["state"] == s)))
        out.append(f"  {len(data['points'])} point(s)" + (f": {counts}" if counts else ""))
        width = max([8] + [len(n) for n in data["points"]])
        for name, p in data["points"].items():
            out.append(f"    {name:{width}s}  {p['state']:10s} {p['attempts']} attempt(s)")
        out += [f"  records {data['records']}", f"  results {data['results']}"]
        return out
    if data["view"] == "tool":
        mine = data["provenance"] or {}
        out = [f"{rel}/{data['point']}/{data['tag']}"]
        for key in ("tool", "version", "exe", "exe_sha256", "ran"):
            if key in mine:
                out.append(f"  {key} = {mine[key]}")
        res = mine.get("result") or {}
        if res:
            out.append(f"  exit {res.get('exit')} in {res.get('seconds')} s" + (f" · {res['note']}" if res.get("note") else ""))
        if mine.get("argv"):
            out.append("  argv: " + " ".join(mine["argv"]))
        if data["log_tail"]:
            out += ["", f"── last {len(data['log_tail'])} line(s) of logs/{data['point']}/{data['tag']}.log", *data["log_tail"]]
        else:
            out.append("  no log kept")
        return out
    out = [f"{rel}/{data['point']}: {data['state']}"]
    out.append(f"  identity {(data['identity'] or '–')[:12]} · seed {data['seed'] if data['seed'] is not None else '–'}"
               f" · events {data['events'] if data['events'] is not None else '–'} · threads {data['threads'] if data['threads'] is not None else '–'}")
    if data["values"]:
        out.append("  " + " · ".join(f"{k} {v}" for k, v in data["values"].items()))
    if data["sigma_pb"]:
        sig = data["sigma_pb"]
        out.append(f"  σ = {sig[0]:.6g}" + (f" ± {sig[1]:.3g}" if len(sig) > 1 else "") + f" pb ({data['sigma_note']})")
    else:
        out.append(f"  σ = – ({data['sigma_note']})")
    for t in data["tools"]:
        version = str(t.get("version") or "")
        out.append(f"  tool {t['tag']}" + (f" ({version if version.startswith(t['tool']) else t['tool'] + ' ' + version})" if version else f" ({t['tool']})")
                   + f": exit {t['exit']} in {t['seconds']} s")
    out.append(f"  products: {', '.join(data['products'])}" if data["products"] else "  products: none recorded")
    for a in data["attempts"]:
        out.append(f"  attempt {a['n']:>3}  {_local(a['finished']):16s}  {a['verdict'] or '?':8s} {a['cause']}".rstrip())
    prov = data["provenance"]
    if prov:
        out.append(f"  ran on {prov.get('host', '?')} as {prov.get('user', '?')}, {prov.get('started', '?')} → {prov.get('finished', '?')}")
    if data.get("parts"):
        out += ["", "── identity parts", *json.dumps(data["parts"], indent=1, sort_keys=True).splitlines()]
    for log in data["log_tail"]:
        out += ["", f"── {log['log']} (end)", *log["lines"]]
    return out


def point_state(plan) -> str:
    """complete; stale (complete for an earlier identity: a changed setup reruns it); running (a
    session holds its lock); failed or stopped (its last attempt's verdict, V200); incomplete (begun,
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


#: Folders of a configuration's that are no point's: the stages, the pages, the submissions, the plot stage's
#: failures (logs/plot/, V204).
KEEP_NAMES = {"plots", "pre", "post", "cluster", "compare", "plot"}


def clean_targets(planned: list, everything: bool, records: bool = False) -> tuple[list[Path], list[Path]]:
    """What `heimdall clean` removes, and the results it only lists, by lifecycle (V157): within each
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
    recs |= {s.folders.points / s.point.name for s in outs_stages(planned) if s.library}      # a Run's link into the library
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
        if path.is_symlink():                  # a Run's link into the points library: the link goes, never the entry
            path.unlink()
            continue
        freed += _size(path)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    return freed
