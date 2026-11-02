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
* `commands`: `heimdall`'s subcommands and their options, from cli.parser()'s help.
"""

from __future__ import annotations

import argparse
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import cli, knowledge, schema
from .paths import heimdall_root

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
            meaning += " A configuration inherits it from `[errand]`."
        rows.append(f"| `{name}` | {_cell(_type(entry))} | {default} | {_cell(meaning)} |")
    if table == "figure":
        inherited = [k for k, e in schema.spec().get("plot", {}).items() if e.get("page")]
        rows.append(f"| *every page key of `[plot]`* | as there | `[plot]`'s | {', '.join(f'`{k}`' for k in inherited)}: "
                    "the figure's value, for its pages only |")
    return "\n".join(rows)


def keys3(table: str) -> str:
    """A v3 table as the old reference's table (schema.v3_entries)."""
    rows = ["| Key | Type | Default | Meaning |", "|---|---|---|---|"]
    for name, entry in schema.v3_entries(table).items():
        default = "**required**" if entry.get("required") else f"`{_value(entry['default'])}`" if "default" in entry else ""
        meaning = entry.get("notes") or entry.get("doc", "")
        if entry.get("inherit") and table == "errand":
            meaning += " A configuration inherits it from `[errand]`."
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
    """Each subcommand: its help, then a table of its arguments (none when every one is hidden: a retired command's)."""
    top = cli.parser()
    sub = next(a for a in top._actions if isinstance(a, argparse._SubParsersAction))
    helps = {a.dest: a.help for a in sub._choices_actions}
    out = []
    for name, parser in sub.choices.items():
        out.append(f"**`heimdall {name}`**: {helps.get(name, '')}\n")
        rows = ["| Argument | Meaning |", "|---|---|"]
        for action in parser._actions:
            if isinstance(action, argparse._HelpAction) or action.help == argparse.SUPPRESS:   # hidden (V181)
                continue
            meaning = action.help or ""
            rows.append(f"| `{_cell(_option(action))}` | {_cell(meaning)} |")
        if len(rows) > 2:
            out.append("\n".join(rows) + "\n")
    return "\n".join(out).rstrip("\n")


#: A record id the user pages leave out (V138): V…, L…, F…, U… and 00/B…; C1–C14 stay (04 §13 defines them).
_ID = r"(?:[VLFU]\d{1,3}[a-z]?|00/B\d+)"
_IDS = rf"{_ID}(?:[ \t]*(?:,|–|-|and)[ \t]*{_ID})*"
_PLAIN = [(re.compile(rf"[ \t]*\((?:see[ \t]+)?{_IDS}\)"), ""),             # (V45, V46): gone
          (re.compile(rf"\((?:see[ \t]+)?{_IDS}[;,:][ \t]*"), "("),          # (V31; rivet, …): (rivet, …)
          (re.compile(rf"[;,:][ \t]*(?:see[ \t]+)?{_IDS}\)"), ")")]          # (rivet, V31), (… in-process: V71)


def plain(text: str) -> str:
    """Text for the user pages: the record's ids taken out of its parentheses, code spans as they are.
    The schema and the CLI keep them for developers (`heimdall explain`, 06, 07)."""
    out, at = [], 0
    for span in re.finditer(r"`[^`\n]*`", text):
        out.append(_plain(text[at:span.start()]))
        out.append(span.group(0))
        at = span.end()
    return "".join(out) + _plain(text[at:])


def _plain(chunk: str) -> str:
    for pattern, new in _PLAIN:
        chunk = pattern.sub(new, chunk)
    return chunk


def render(what: str) -> str:
    return plain(_render(what))


def _render(what: str) -> str:
    kind, _, arg = what.strip().partition(" ")
    if kind == "keys" and arg in schema.TABLES + schema.REPORT_TABLES:
        return keys(arg)
    if kind == "keys3" and arg in schema.v3_tables():
        return keys3(arg)
    if kind == "style" and not arg:
        return style()
    if kind == "commands" and not arg:
        return commands()
    raise ValueError(f"no generated block '{what}': keys <{'|'.join(schema.TABLES + schema.REPORT_TABLES)}>, style or commands")


# ── Whole generated pages (doc:docs-system) ───────────────────────────────────────────────────────

@dataclass
class Section:
    """A heading of a settings page: its keys one level down, then its sections, nested as the file's tables nest."""
    title: str
    text: str = ""
    keys: list[tuple[str, str]] = field(default_factory=list)      # (name, what follows its heading)
    subs: list[Section] = field(default_factory=list)


def _facts(kind: str, default: str, accepts: str) -> str:
    return f"| Type | Default | Acceptable |\n|---|---|---|\n| {_cell(kind)} | {_cell(default)} | {_cell(accepts) or '—'} |"


def key_block(entry: dict) -> str:
    """A key of the schema: its facts as a table, its special keywords as a list, then what it does."""
    default = "**required**" if entry.get("required") else f"`{_value(entry['default'])}`" if "default" in entry else "—"
    accepts = ", ".join(f"`{_value(c)}`" for c in entry.get("choices", []))
    if "min" in entry:
        accepts += (", " if accepts else "") + f"at least {entry['min']}"
    parts = [_facts(knowledge.kind_of(entry), default, accepts)]
    if words := knowledge.keywords_of(entry):
        parts.append("\n".join(f"- `{word}`: {means}" for word, means in words))
    prose = knowledge.sentence(knowledge.plain(entry.get("notes") or entry.get("doc", "")))
    if entry.get("page"):
        prose += " A figure may override it."
    if entry.get("inherit"):
        prose += " A configuration inherits it from `[errand]`."
    parts.append(prose.strip())
    return "\n\n".join(p for p in parts if p)


def _table(title: str, entries: dict[str, dict], text: str = "", subs: list[Section] | None = None) -> Section:
    return Section(title, text, [(k, key_block(e)) for k, e in entries.items()], subs or [])


def _literal_block(default: str, comment: str) -> str:
    """A key known by its value and its comment (base.toml, settings.toml). A comment opening `a | b | c` names its values."""
    accepts, prose = "", knowledge.plain(comment)
    if found := re.match(r"([\w.+-]+(?: \| [\w.+-]+)+)\s*(.*)", prose, re.S):
        accepts, prose = ", ".join(f"`{w}`" for w in found.group(1).split(" | ")), found.group(2)
    shown = f"`{default}`" if len(default) <= 60 else f"{len(tomllib.loads(f'v = {default}')['v'])} entries, in the file"
    return f"{_facts(knowledge.literal_kind(default), shown, accepts)}\n\n{knowledge.sentence(prose)}".rstrip()


def _nested(entries: list[tuple[str, str, str]], top: str = "") -> list[Section]:
    """Dotted keys as sections: `page.margins.left` is `left` under `margins` under `page`."""
    root = Section("")
    for dotted, default, comment in entries:
        path = dotted.split(".")
        here = root
        for part in path[:-1]:
            here = next((s for s in here.subs if s.title == f"`{part}`"), None) or _added(here, f"`{part}`")
        here.keys.append((path[-1], _literal_block(default, comment)))
    return ([Section(top, keys=root.keys)] if root.keys else []) + root.subs


def _added(parent: Section, title: str) -> Section:
    parent.subs.append(Section(title))
    return parent.subs[-1]


def _tool_options() -> list[Section]:
    out = []
    for path in sorted((heimdall_root() / "framework" / "tools").glob("*/tool.toml")):
        options = tomllib.loads(path.read_text(encoding="utf-8")).get("options", {})
        if options:
            out.append(Section(f"`{path.parent.name}`", keys=[(k, _facts(
                {"list": "list", "table": "table", "str": "string", "int": "integer", "float": "number", "bool": "true or false",
                 "flag": "flag"}.get(o.get("kind"), "any"),
                "**required**" if o.get("required") else f"`{_value(o['default'])}`" if "default" in o else "—", "") +
                f"\n\n{knowledge.sentence(knowledge.plain(o.get('doc', '')))}") for k, o in options.items()]))
    return out


#: A settings page: its id, summary, readers' note, and its sections from the code.
SETTINGS = {
    "errand": ("settings-errand", "every key of an errand file's [file], [errand], [cfgs.*] and [quantities.*]: type, default, values, effect",
               "Plot, tool and cluster keys have their own pages.",
               lambda: [_table(f"`{title}`", schema.v3_entries(t)) for title, t in
                        (("[file]", "file"), ("[errand]", "errand"), ("[cfgs.<name>]", "cfgs"), ("[quantities.<q>]", "quantities"))]),
    "tools": ("settings-tools", "every key of a [tools.<name>] table, and each standard tool's own options",
              "A tool's own settings beyond these go in its card; `heimdall tools <folder>` shows a folder.",
              lambda: [_table("`[tools.<name>]`", schema.v3_entries("tools"), subs=[Section("Each tool's own options", subs=_tool_options())])]),
    "plot": ("settings-plot", "every key of [plot], its figures, data and runs together, and [stats]: type, default, values, effect",
             "The style's keys have their own page.",
             lambda: [_table("`[plot]`", schema.keys("plot"), subs=[
                 _table("`[plot.figures.<name>]`", schema.spec().get("figure", {})),
                 _table("`[plot.data]`", schema.keys("data")),
                 _table("`[plot.across_from]`", schema.keys("across_from"))]),
                 _table("`[stats]`", schema.keys("stats"))]),
    "style": ("settings-style", "every style key a page may set in [plot.style] or a style file, nested as the file nests them",
              "From `src/Apps/Paint/base.toml`, which every page starts from. A layer names only what it changes.",
              lambda: _nested(schema.style_entries())),
    "report": ("settings-report", "every key of a report's recipe: [report] and [[report.section]]",
               "", lambda: [_table("`[report]`", schema.keys("report"), subs=[_table("`[[report.section]]`", schema.keys("section"))])]),
    "cluster": ("settings-cluster", "every key of [cluster], for running a job on Slurm",
                "", lambda: [_table("`[cluster]`", schema.keys("cluster"))]),
    "stack": ("settings-stack", "every setting of the stack's build: what is built, with what, how many cores, nested as the file nests them",
              "From `recipes/settings.toml`. Set one on the command line (`cores=8`), in a `--config` file, or in the machine root's `machine.toml`.",
              lambda: _nested(schema.stack_entries(), "`[settings]`")),
}
#: Where each settings page's facts live, for the drift report.
SOURCES = {"errand": "framework/schema/run.toml, framework/schema/v3.toml", "tools": "framework/schema/v3.toml, framework/tools",
           "plot": "framework/schema/run.toml", "style": "src/Apps/Paint/base.toml", "report": "framework/schema/report.toml",
           "cluster": "framework/schema/run.toml", "stack": "recipes/settings.toml"}


def _slug(title: str) -> str:
    return re.sub(r"[^\w\- ]", "", title.lower()).strip().replace(" ", "-")


def _anchors(sections: list[Section]) -> dict[int, str]:
    """GitHub's anchor of each heading, in reading order: a repeated one gets -1, -2 …"""
    seen: dict[str, int] = {}
    out: dict[int, str] = {}

    def give(title: str, key: int) -> None:
        slug = _slug(title)
        out[key] = f"{slug}-{seen[slug]}" if seen.get(slug) else slug
        seen[slug] = seen.get(slug, 0) + 1

    def walk(section: Section) -> None:
        give(section.title, id(section))
        for pair in section.keys:
            give(pair[0], id(pair))
        for sub in section.subs:
            walk(sub)

    for section in sections:
        walk(section)
    return out


def _render_section(section: Section, level: int, anchors: dict[int, str]) -> list[str]:
    out = [f"{'#' * level} {section.title}", ""]
    if section.text:
        out += [section.text, ""]
    if len(section.keys) > 1:
        out += [" · ".join(f"[`{name}`](#{anchors[id(pair)]})" for pair in section.keys for name in [pair[0]]), ""]
    for pair in section.keys:
        out += [f"{'#' * (level + 1)} `{pair[0]}`", "", pair[1], ""]
    for sub in section.subs:
        out += _render_section(sub, level + 1, anchors)
    return out


def _head(ident: str, summary: str, code: str) -> list[str]:
    return ["---", f"id: {ident}", f"summary: {summary}", f"code: {code}", "generated: true", "---", ""]


def settings_page(name: str) -> str:
    ident, summary, note, build = SETTINGS[name]
    sections = build()
    anchors = _anchors(sections)
    out = _head(ident, summary, SOURCES[name])
    out += [f"Generated from the code; change it there. `heimdall explain <key>` says the same.{' ' + note if note else ''}", ""]
    for section in sections:
        out += _render_section(section, 1, anchors)
    return "\n".join(out).rstrip() + "\n"


def commands_page() -> str:
    top = cli.parser()
    sub = next(a for a in top._actions if isinstance(a, argparse._SubParsersAction))
    helps = {a.dest: a.help for a in sub._choices_actions}
    out = _head("commands", "every heimdall command and its arguments", "framework/runner/cli.py")
    out += ["# Commands", "", "Generated from the CLI's help; change it there.", ""]
    for name, parser in sub.choices.items():
        out += [f"## `heimdall {name}`", "", knowledge.plain(helps.get(name) or ""), ""]
        rows = [f"| `{_cell(_option(a))}` | {_cell(knowledge.plain(a.help or ''))} |" for a in parser._actions
                if not isinstance(a, argparse._HelpAction) and a.help != argparse.SUPPRESS]
        if rows:
            out += ["| Argument | Meaning |", "|---|---|", *rows, ""]
    return "\n".join(out).rstrip() + "\n"


def keys_page() -> str:
    """One line a key, for grep: where it lives, its type and default."""
    out = _head("keys", "every setting in one line each, for grep: key, type, default", "framework/schema, src/Apps/Paint/base.toml, recipes/settings.toml")
    out += ["# Every key", "", "`key | type | default`. Generated. What each does: `heimdall explain <key>`, or its settings page.", "", "```"]
    for prefix, entries in knowledge.key_lines():
        out += [f"{prefix}.{name} | {kind} | {default}" if prefix else f"{name} | {kind} | {default}" for name, kind, default in entries]
    return "\n".join([*out, "```"]) + "\n"


def legacy_page() -> str:
    """The second form's names, from v3.toml."""
    out = _head("legacy", "the errand file's older (v2) names and today's", "framework/schema/v3.toml")
    out += ["# v2 names", "", "`heimdall migrate --v3` rewrites a v2 file. Generated from `framework/schema/v3.toml`.", "",
            "| Table | v2 | Today |", "|---|---|---|"]
    for table, data in schema.spec("v3").items():
        title = f"`[{data['reads']}]` → `[{table}]`"
        out += [f"| {title} | `{old}` | `{new}` |" for old, new in data["renamed"].items()]
        out += [f"| {title} | `{old}` | gone |" for old in data["gone"]]
    return "\n".join(out) + "\n"


def context_page() -> str:
    """docs/client/CONTEXT.md: what an AI in a work dir needs first. The model's page and the first errand file are the
    guide's own, so this cannot contradict them; the rest is the CLI's words and where to look."""
    pages = {p.id: p for p in knowledge.pages()}
    model = re.sub(r"\]\([^)]*\)", "]", pages["model"].body).replace("More: [glossary].", "").replace("Details: [outputs].", "").strip()
    errand = re.search(r"```toml\n.*?```", pages["errand-file"].body, re.S).group(0)
    wanted = re.sub(r"\]\([^)]*\)", "]", pages["everyday"].body.split("## What to write", 1)[1].split("\n\nA whole file", 1)[0]).strip()
    wanted = re.sub(r" \| \[[^\]]*\] \|$", " |", wanted.replace("| To | Write | See |", "| To | Write |").replace("|---|---|---|", "|---|---|"), flags=re.M)
    top = cli.parser()
    sub = next(a for a in top._actions if isinstance(a, argparse._SubParsersAction))
    rows = [f"- `heimdall {a.dest}`: {_cell(knowledge.plain(a.help or ''))}" for a in sub._choices_actions if a.help != argparse.SUPPRESS]
    out = _head("context", "what an AI working in a work dir needs first; heimdall context prints it", "framework/runner/docs.py")
    out += ["# Heimdall, for an agent in a work dir", "",
            "Generated: printed by `heimdall context`, and matching the Heimdall this shell uses.", "",
            "## How to work here", "",
            "- `configs/` and `modules/` are the user's: change them only when asked, and show the diff.",
            "- `results/`, `records/`, `.cache/`, `build/` and `reports/` are made by runs. Never write into them by hand.",
            "- Before running, `heimdall check <A>/<E>`, then `heimdall run <A>/<E> [cfg] --plan`. Say what a run will cost before starting a long one.",
            "- Look a key up rather than guessing: `heimdall explain <key>` gives its type, default, accepted values and effect, for errand keys, `plot.*`, `style.*`, `stack.*` and tool options; `heimdall explain plot` lists a table.",
            "- A rebuilt program or changed card reruns the points that used it, by design. A plot change reruns nothing.",
            "- Commit by path, never `git commit -a`.", "",
            model, "", "## A complete errand file", "", errand, "",
            "A configuration with `plot_points = [\"energies\"]` gets a page per value of it, the other varied quantities being the curves. "
            "Left out, every point is on one page.", "",
            "## What to write", "", wanted, "",
            "Refused at plan time, each with a hint: an unknown key; a quantity no tool consumes; a FIFO across groups or into Delphes; an undeclared Rivet option; an uninstalled PDF set; a label in TLatex rather than LaTeX.", "",
            "## Commands", "", *rows, "",
            "## Where to read more", "",
            "`heimdall where --heimdall` is Heimdall's folder. Under it, `docs/MAP.md` lists every page in a line. For a work dir:", "",
            "| To | Read |", "|---|---|",
            "| vary things, target native keys | `docs/stable/guide/sweeps.md` |",
            "| wire tools together, other generators | `docs/stable/guide/chains.md`, `docs/stable/tools/` |",
            "| your own programs | `docs/stable/guide/programs.md` |",
            "| pages, sets, figures, statistics | `docs/stable/guide/plots.md` and its neighbours |",
            "| a failure | `docs/stable/guide/failures.md` |",
            "| every key, in full | `docs/reference/settings/`, `docs/reference/keys.md` for grep |"]
    return "\n".join(out).rstrip() + "\n"


def generated() -> dict[str, str]:
    """Whole pages under docs/, by path. The map comes last: it lists what the others are on disk."""
    out = {f"reference/settings/{name}.md": settings_page(name) for name in SETTINGS}
    return out | {"reference/commands.md": commands_page(), "reference/keys.md": keys_page(), "reference/legacy.md": legacy_page(),
                  "client/CONTEXT.md": context_page()}


def write_generated() -> list[str]:
    root, written = knowledge.docs_root(), []
    for rel, text in generated().items():
        path = root / rel
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written.append(rel)
    path = root / "MAP.md"
    text = knowledge.map_text()
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
        written.append("MAP.md")
    return written


def updated(text: str) -> str:
    return BLOCK.sub(lambda m: f"{m.group(1)}{render(m.group(2))}\n{m.group(4)}", text)


def pages() -> list[Path]:
    docs = heimdall_root() / "docs"
    return sorted(p for p in docs.rglob("*.md") if "audit_" not in str(p.relative_to(docs)))


def stale() -> list[str]:
    """The pages whose generated blocks differ from what the code says now."""
    root = knowledge.docs_root()
    whole = {**generated(), "MAP.md": knowledge.map_text()}
    return [str(p.relative_to(heimdall_root())) for p in pages()
            if BLOCK.search(text := p.read_text(encoding="utf-8")) and updated(text) != text] + \
           [f"docs/{rel}" for rel, text in whole.items()
            if not (root / rel).is_file() or (root / rel).read_text(encoding="utf-8") != text]


if __name__ == "__main__":                                  # make docs
    for page in pages():
        text = page.read_text(encoding="utf-8")
        if BLOCK.search(text) and (new := updated(text)) != text:
            page.write_text(new, encoding="utf-8")
            print(page.relative_to(heimdall_root()))
    for rel in write_generated():
        print(f"docs/{rel}")
