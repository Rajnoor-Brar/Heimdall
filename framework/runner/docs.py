"""The manual's generated parts (rank 5, V91): what the code states, the manual does not restate by hand.

A page of docs/ holds blocks

    <!-- generated: keys plot -->
    …
    <!-- /generated -->

and `make docs` rewrites what is between from the code; tests/runner/test_docs.py fails while a block
differs ("run `make docs`"). What a block may name:

* `keys <table>`: a schema table's keys (framework/schema/run.toml: type, choices, bounds, default,
  inheritance, doc and notes, V90); `keys figure` lists a figure's own keys, then the [plot] keys it
  inherits;
* `style`: src/Apps/Paint/base.toml's keys, their defaults and their comments;
* `commands`: `hep`'s subcommands and their options, from cli.parser()'s help.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from . import cli, schema
from .paths import hep_root

BLOCK = re.compile(r"(<!-- generated: ([^>]+?) -->\n)(.*?)(<!-- /generated -->)", re.S)


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


_value = schema.toml_value


def _type(entry: dict) -> str:
    out = schema.type_name(entry["type"])
    if entry.get("items"):
        out += f" ({schema.type_name(entry['items'])} each)"
    if entry.get("choices"):
        out += ": " + ", ".join(f"`{_value(c)}`" for c in entry["choices"])
    if "min" in entry:
        out += f", ≥ {entry['min']}"
    if entry.get("default_ok"):
        out += ', or `"default"`'
    if entry.get("native_ok"):
        out += ' or `"native"`'
    return out


def keys(table: str) -> str:
    """A schema table as the reference's table: Key | Type | Default | Meaning."""
    entries = schema.spec().get(table, {}) if table == "figure" else schema.keys(table)
    rows = ["| Key | Type | Default | Meaning |", "|---|---|---|---|"]
    for name, entry in entries.items():
        default = "**required**" if entry.get("required") else f"`{_value(entry['default'])}`" if "default" in entry else ""
        meaning = entry.get("notes") or entry.get("doc", "")
        if entry.get("inherit"):
            meaning += " A configuration inherits it from `[run]`."
        rows.append(f"| `{name}` | {_cell(_type(entry))} | {default} | {_cell(meaning)} |")
    if table == "figure":
        inherited = [k for k, e in schema.spec().get("plot", {}).items() if e.get("page")]
        rows.append(f"| *every page key of `[plot]`* | as there | `[plot]`'s | {', '.join(f'`{k}`' for k in inherited)}: "
                    "the figure's value, for its pages only |")
    return "\n".join(rows)


_SEED = {"type": "str|int", "default": "identity",
         "doc": '`"identity"`: from the generator\'s identity; `"random"`: drawn when the point runs; an integer: '
                'exactly that seed for every point (a replica, `to = { "pythia/seed" = true }`, gives a point its '
                'own: 04 §8.2; 06 §8)'}
#: v3's tables (03 §6; runner/v3.py) as the reference shows them: the v2 table each is read as, its keys
#: renamed (v2 → v3), the rows v3 has of its own, and v2's keys v3 does not have. A renamed key keeps its
#: v2 entry (type, default) under its v3 name, with v3's words where v2's would mislead (V3_DOCS).
V3_TABLES = {
    "file": ("config", {}, {"schema": {"type": "int", "doc": "`3`, or `2` to keep a v2 file v2 for one release; "
                                                              "a file with `[file]` is v3 without it"}}, ()),
    "run": ("run", {"configuration": "run", "event_count": "events", "tools": "chain", "sweeps": "vary"},
            {"seed": _SEED, "commands": {"type": "list", "doc": "argv arrays run in each point's output folder before "
                                         "its tools, in order; output to `logs/prelim.log`; a nonzero exit fails the "
                                         "point. Placeholders: `{work}`, `{hep}`, `{out}`, `{res}`, `{file:<name>}`"}},
            ("seed_type", "manual_seed", "cfgs")),
    "cfgs": ("configuration", {"label": "folder", "event_count": "events", "tools": "chain", "sweeps": "vary",
                               "static": "fixed"}, {"seed": _SEED}, ("seed_type", "manual_seed", "prelim")),
    "tools": ("tool", {"tool": "uses", "baseconfig": "card", "output_file": "output"},
              {"keep": {"type": "bool", "default": True, "doc": "`false`: what it writes for a later group is a scratch "
                                                              "file of the point (`output/`), not a product (`results/`)"}},
              ()),
    "quantities": ("quantity", {"key": "to"},
                   {"points": {"type": "list", "doc": "the points, one row each: `{ tag, value, label, style }`; "
                                                      "`value` is required, `tag` names the point's folder"},
                    "fixed": {"type": "str|int|float", "doc": "the point a configuration that does not vary the "
                                                             "quantity takes: a tag, a value or `\"#N\"` (04 §7)"},
                    "fields": {"type": "table", "doc": "a compound quantity: `{ <field> = <its binding> }`, each "
                                                       "field a quantity of its own, its rows' values set together "
                                                       "(04 §8.4)"}},
                   ("values", "tags", "labels", "styles", "target")),
}
V3_DOCS = {
    ("run", "run"): "the configuration `hep run <file>` runs, a `[cfgs.<name>]` (C2). Under `sweep_runs` it may "
                    "be left out",
    ("run", "events"): "every configuration's event count, unless it gives its own",
    ("run", "chain"): "every configuration's tools, unless it gives its own (04 §5.3)",
    ("run", "vary"): "04 §5.1; `[]` is one point",
    ("run", "serial"): "the prefix `NN_` of each configuration's folder, `<name>/NN_<folder>`: **location, never "
                       "identity**. Left out, the runner numbers it: the newest folder made from these inputs, else a "
                       "new one (04 §2). Set, a changed configuration is refused there rather than overwrite what it "
                       "made (`--rerun` overwrites)",
    ("cfgs", "serial"): "this configuration's `NN_`, over `[run]`'s; left out in both, the runner numbers it (04 §2)",
    ("cfgs", "folder"): "the configuration's folder, after the serial: `NN_<folder>`; empty means the table key",
    ("cfgs", "events"): "required here if `[run]` has none. A list is one configuration per count, "
                        "`<name>_<count>` (`pdf_10k`), run in turn as `<name>` (04 §5.6)",
    ("cfgs", "chain"): "04 §5.3; `[run]`'s when left out",
    ("cfgs", "vary"): "04 §5.1; `[]` is one point",
    ("cfgs", "fixed"): "`{ quantity = \"tag\" }`: this configuration's fixed points, over each quantity's own "
                       "`fixed` (04 §7)",
    ("tools", "uses"): "the tool folder, when it is not the table's name: a second table of one tool, "
                       "`[tools.<name>] uses = \"<folder>\"` (05 §3; `hep tools` lists the folders)",
    ("tools", "card"): "native base card(s), read in order (root `configs/<project>/`). Tools with a card only.",
    ("tools", "input"): "what it reads: a producer's table name (`input = \"pythia\"`: what that tool writes), "
                        "another tool's output by name, a pre product, (post) a product of every point, or a path. "
                        "The first input is `{input}`",
    ("tools", "output"): "what it writes. Read in its own group, a FIFO; in a later group, a file: a product in "
                         "`results/`, or with `keep = false` a scratch file in `output/` (04 §6). An array is "
                         "fan-out (V16); one writer per output (C6)",
    ("quantities", "to"): "where the value goes: `{ pythia = \"PDF:pSet\" }` a native key per tool table or tool; "
                          "`{ \"rivet/photo_eic\" = \"R\" }` an analysis option; `{ \"pythia/seed\" = true }` a replica. "
                          "An entry with a `/` or `true` makes the entries the only consumers (04 §8.1)",
    ("quantities", "exclude"): "points a vary leaves out, by their **1-based** place (as `fixed = \"#2\"` and "
                               "`--points 2` count): `exclude = [2]` varies the others. The remaining points keep "
                               "their names and identities and are numbered 1… over what is varied. In an entangled "
                               "group, a point any member excludes leaves the group. `fixed` may still pick an "
                               "excluded point. Refused: a place outside the points, or none left (V42)",
    ("tools", "shards"): "K > 1: K processes of this tool, each on a share of the events, merged into its `output` "
                         "by the folder's merge tool (V31; rivet, 05 §5.1). The chain is unchanged.",
    ("file", "import"): "run TOMLs this one starts from, in order, named as `hep run` names a config: `name` is this "
                        "project's (`configs/<project>/name.toml`), `<Project>/<name>` another project's, `./…` from "
                        "the work dir; `.toml` optional. **This file wins** (V56): a quantity or configuration of the "
                        "file replaces the imported one whole; a tool table, `[plot]`, `[cluster]` and `[run]`'s own "
                        "keys merge key by key, tables recursively. Imports nest (V94), depth-first; a circle is "
                        "refused. Another project's file keeps its bare paths its own project's. The file that "
                        "imports sets its own `[run].name` and `project` (V100). An entry may be `{ from = "
                        "\"<config>\", only = [\"quantities\", \"cfgs.default\", …] }`: only those tables or dotted "
                        "keys, each of which the file must have (V95)",
    ("file", "vars"): "`name = value`, cited in any string of the file as `{var:name}` and replaced when the file is "
                      "read, after its imports and `--set`, so an identity sees only the result (V96). A string that "
                      "is exactly one var takes its value as it is: `events = \"{var:events}\"` is an integer, and a "
                      "list stays a list; inside a longer string a var must be a scalar (`\"rivet:{var:ana}\"`). An "
                      "unknown name is refused with the nearest. An imported file's `{var:…}` takes this file's "
                      "value; its own `[file.vars]` come with whatever is taken of it (V101), under this file's. "
                      "`--set file.vars.<name>=…` changes one for a run",
}


def keys3(table: str) -> str:
    """A v3 table as the reference's table, from the v2 schema table it is read as (V3_TABLES)."""
    base, renamed, own, gone = V3_TABLES[table]
    rows = ["| Key | Type | Default | Meaning |", "|---|---|---|---|"]
    entries: dict[str, dict] = {}
    for name, entry in schema.keys(base).items():
        if name in gone:
            continue
        new = renamed.get(name, name)
        entries[new] = {**entry, "required": entry.get("required") and new not in ("chain", "uses")}
        if (table, new) in V3_DOCS:
            entries[new] = {k: v for k, v in entries[new].items() if k != "notes"} | {"doc": V3_DOCS[table, new]}
    entries |= own
    for name, entry in entries.items():
        default = "**required**" if entry.get("required") else f"`{_value(entry['default'])}`" if "default" in entry else ""
        meaning = entry.get("notes") or entry.get("doc", "")
        if entry.get("inherit") and table == "run":
            meaning += " A configuration inherits it from `[run]`."
        rows.append(f"| `{name}` | {_cell(_type(entry))} | {default} | {_cell(meaning)} |")
    return "\n".join(rows)


def style() -> str:
    rows = ["| Key | Default | Means |", "|---|---|---|"]
    rows += [f"| `{name}` | `{_cell(value)}` | {_cell(comment)} |" for name, value, comment in schema.style_entries()]
    return "\n".join(rows)


def _option(action: argparse.Action) -> str:
    if action.option_strings:
        name = ", ".join(action.option_strings)
        if action.nargs != 0:
            name += f" {action.metavar or ('|'.join(map(str, action.choices)) if action.choices else action.dest.upper())}"
            name += "…" if action.nargs in ("+", "*") else ""
        return name
    shown = action.metavar or action.dest
    return f"{shown}…" if action.nargs in ("+", "*") else f"[{shown}]" if action.nargs == "?" else shown


def commands() -> str:
    """Each subcommand: its help, then a table of its arguments."""
    top = cli.parser()
    sub = next(a for a in top._actions if isinstance(a, argparse._SubParsersAction))
    helps = {a.dest: a.help for a in sub._choices_actions}
    out = []
    for name, parser in sub.choices.items():
        out.append(f"**`hep {name}`**: {helps.get(name, '')}\n")
        rows = ["| Argument | Meaning |", "|---|---|"]
        for action in parser._actions:
            if isinstance(action, argparse._HelpAction):
                continue
            meaning = action.help or ""
            rows.append(f"| `{_cell(_option(action))}` | {_cell(meaning)} |")
        out.append("\n".join(rows) + "\n")
    return "\n".join(out).rstrip("\n")


def render(what: str) -> str:
    kind, _, arg = what.strip().partition(" ")
    if kind == "keys" and arg in schema.TABLES + schema.DECK_TABLES:
        return keys(arg)
    if kind == "keys3" and arg in V3_TABLES:
        return keys3(arg)
    if kind == "style" and not arg:
        return style()
    if kind == "commands" and not arg:
        return commands()
    raise ValueError(f"no generated block '{what}': keys <{'|'.join(schema.TABLES + schema.DECK_TABLES)}>, style or commands")


def updated(text: str) -> str:
    return BLOCK.sub(lambda m: f"{m.group(1)}{render(m.group(2))}\n{m.group(4)}", text)


def pages() -> list[Path]:
    docs = hep_root() / "docs"
    return sorted(p for p in docs.rglob("*.md") if "audit_" not in str(p.relative_to(docs)))


def stale() -> list[str]:
    """The pages whose generated blocks differ from what the code says now."""
    return [str(p.relative_to(hep_root())) for p in pages()
            if BLOCK.search(text := p.read_text(encoding="utf-8")) and updated(text) != text]


if __name__ == "__main__":                                  # make docs
    for page in pages():
        text = page.read_text(encoding="utf-8")
        if BLOCK.search(text) and (new := updated(text)) != text:
            page.write_text(new, encoding="utf-8")
            print(page.relative_to(hep_root()))
