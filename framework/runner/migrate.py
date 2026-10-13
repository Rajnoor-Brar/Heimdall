"""`hep migrate [CONFIG…] [--apply]` (rank 5, V79): run TOMLs and their cards in today's forms.

audit 1's final phase, "break and migrate": what the runner now refuses, rewritten in what it takes.
A dry run (the default) prints a diff per file; `--apply` writes them. Only these, by line, so comments
and layout stay:

* labels (`labels`, `title`, `title_left`, `title_right`, `legend_header`, `x_label`, `y_label`,
  `legend`): TLatex → LaTeX, as a physicist writes it (labels.natural, the user's choice);
* `[run.<cfg>].swept`: gone; under `sweep_runs = true`, the list of the configurations it ran
  (`sweep_runs = ["a", "b"]`), in the order it ran them;
* a custom tool's bare `executable` that is not built but is a command on PATH → `"path:<name>"`;
* a base card's lines for keys the runner sets (its folder's `[card] owned`), which the plan already
  said were not used;
* (V81) `[plot.overlay.<name>]` → `[plot.figures.<name>]` with `class = "overlay"`, and
  `[plot.object."<glob>"]` → `[plot.figures.<glob, as a name>]` with `objects = ["<glob>"]`, their
  subtables too; in a figure, a style key written bare (`ratio.range = […]`, which beside `ratio = true`
  is not even TOML) → `style.ratio.range`. This runs on the text first, so a file it makes TOML reads.
* (V93) `[master]` → `[config]`, its `master_toml` → `master` and `include` → `import`, on the text too.
* (V98) `[run.<cfg>]` → `[run.cfgs.<cfg>]`, its subtables too (`[run.<cfg>.static]`), and the same
  headers in comments (a configuration commented out stays one to uncomment).
* (V99) `[run.defaults]` → its keys moved into `[run]`, at the end of its keys; one [run] sets too is
  [run.defaults]'s value (it was the nearer layer). Its comments go with it.
* (Heimdall, docs/framework/01_Target.md §5.3) `{repo}` → `{work}`, or `{hep}` for what moved into
  Heimdall: `{repo}/build/App_*`, `Paint.exe` and `Herwig/` → `{apps}/…`, `{repo}/utils/` → `{hep}/src/`.
  On the text, anywhere in the file (a comment's example too).
* (audit 3, phase 3.1) `{hep}/framework/Apps/` → `{apps}/`: the compiled apps are in the machine root.
* (audit 3, phase 4.2) `tool = "custom"` → `tool = "exec"`; the export keys of an exec or module table
  (`pythia_cmnd = true`, `herwig_run = true`) → `generate_cards` (the context file gives every tool's card
  and config), in each configuration whose chain runs that table, or in [run] when every one does;
  `{std:<key>}` → `{context:<tag>.<card or product>}`.
"""

from __future__ import annotations

import difflib
import re
import shutil
import tomllib
from pathlib import Path

import tomli_w

from . import config as configmod
from . import schema, tools
from .errors import HepError
from .labels import is_tlatex, natural
from .paths import config_file, resolve

LABEL_KEYS = {"labels", "title", "title_left", "title_right", "legend_header", "x_label", "y_label", "legend"}
_KEY = re.compile(r"^(\s*)([A-Za-z0-9_\-]+|\"[^\"]+\")(\s*=\s*)(.*)$")
_TABLE = re.compile(r"^\s*\[\[?([^\]]+)\]\]?\s*(#.*)?$")
_OLD_FIGURE = re.compile(r'^(\s*)\[\s*plot\.(overlay|object)\.("[^"]+"|[A-Za-z0-9_\-]+)((?:\.[A-Za-z0-9_\-]+)*)\s*\](\s*(?:#.*)?)$')
_DOTTED = re.compile(r"^(\s*)([A-Za-z_]+)(\.[A-Za-z0-9_.\-]+\s*=.*)$")
#: base.toml's tables: a key under one of them, in a figure, is a style key.
STYLE_TABLES = ("page", "text", "curves", "data", "axes", "legend", "ratio")


def _slug(glob: str, taken: set) -> str:
    """A figure's name for an object glob: d04-* → d04."""
    base = re.sub(r"[^A-Za-z0-9_]+", "_", glob.rsplit("/", 1)[-1]).strip("_") or "objects"
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base}_{n}"
    taken.add(name)
    return name


_RUN_TABLE = re.compile(r"^(\s*#*\s*)\[\s*run\.([A-Za-z0-9_\-]+)((?:\.[A-Za-z0-9_\-]+)*)\s*\](.*)$", re.S)


def cfgs_text(text: str) -> str:
    """[run.<cfg>] as [run.cfgs.<cfg>] (V98), by line: a table header (or a commented-out one) under
    [run] that is not one of [run]'s own keys, `defaults` (V99's to move) or `cfgs`."""
    from . import schema
    own = set(schema.keys("run")) | {"defaults", "cfgs"}
    out = []
    for line in text.splitlines(keepends=True):
        match = _RUN_TABLE.match(line)
        if match and match[2] not in own:
            tail = match[4]
            pad = len(tail) - len(tail.lstrip(" "))
            if pad and tail.lstrip(" ").startswith("#"):             # a comment after it keeps its column
                tail = " " * max(1, pad - len("cfgs.")) + tail.lstrip(" ")
            line = f"{match[1]}[run.cfgs.{match[2]}{match[3]}]{tail}"
        out.append(line)
    return "".join(out)


def defaults_text(text: str) -> str:
    """[run.defaults]'s keys into [run] (V99), by line: the block is taken out (its header and its
    lines up to the next table) and its lines go after [run]'s own; a key [run] sets too loses [run]'s
    line, since [run.defaults] was the nearer layer."""
    lines = text.splitlines(keepends=True)
    heads = [i for i, l in enumerate(lines) if _TABLE.match(l)]
    start = next((i for i in heads if _TABLE.match(lines[i])[1].strip() == "run.defaults"), None)
    run = next((i for i in heads if _TABLE.match(lines[i])[1].strip() == "run"), None)
    if start is None or run is None:
        return text
    end = next((i for i in heads if i > start), len(lines))
    block = lines[start + 1:end]
    while block and not block[-1].strip():
        block.pop()
    moved = {m[2] for l in block if (m := _KEY.match(l.rstrip("\n")))}
    rest = lines[:start] + lines[end:]
    run = next(i for i, l in enumerate(rest) if _TABLE.match(l) and _TABLE.match(l)[1].strip() == "run")
    after = next((i for i in range(run + 1, len(rest)) if _TABLE.match(rest[i])), len(rest))
    body = [l for l in rest[run + 1:after] if not ((m := _KEY.match(l.rstrip("\n"))) and m[2] in moved)]
    tail = []
    while body and not body[-1].strip():
        tail.insert(0, body.pop())
    return "".join(rest[:run + 1] + body + block + (tail or ["\n"]) + rest[after:])


#: High-Energy's single root, split (framework/01 §5.3): the first prefix that matches wins.
PLACEHOLDERS = (("{repo}/build/App_", "{apps}/App_"),
                ("{repo}/build/Paint.exe", "{apps}/Paint.exe"),
                ("{repo}/build/Herwig/", "{apps}/Herwig/"),
                ("{hep}/framework/Apps/", "{apps}/"),
                ("{repo}/utils/", "{hep}/src/"),
                ("{repo}", "{work}"))
_REPO = re.compile("|".join(re.escape(old) for old, _ in PLACEHOLDERS))


def placeholder_text(text: str) -> str:
    """{repo} as {work}, {apps} for the compiled apps, {hep} for Heimdall's files (PLACEHOLDERS)."""
    return _REPO.sub(lambda match: dict(PLACEHOLDERS)[match[0]], text)


#: [master]'s keys as [config] names them (V93).
CONFIG_KEYS = {"master_toml": "master", "include": "import"}


def config_text(text: str) -> str:
    """[master] as [config] (V93), by line: the table's header and its two keys."""
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        header = _TABLE.match(line)
        if header:
            inside = header[1].strip() == "master"
            if inside:
                line = re.sub(r"\[\s*master\s*\]", "[config]", line, count=1)
        elif inside and (key := _KEY.match(line.rstrip("\n"))) and key[2] in CONFIG_KEYS:
            line = f"{key[1]}{CONFIG_KEYS[key[2]]}{key[3]}{key[4]}\n"
        out.append(line)
    return "".join(out)


def figure_text(text: str) -> str:
    """The old figure tables of a run TOML as [plot.figures] (V81), by line; see the module's doc."""
    taken = set(re.findall(r"^\s*\[\s*plot\.figures\.([A-Za-z0-9_\-]+)", text, re.M))
    names: dict[tuple[str, str], str] = {}
    out, in_figure = [], False
    for line in text.splitlines(keepends=True):
        old = _OLD_FIGURE.match(line.rstrip("\n"))
        if old:
            indent, kind, key, sub, tail = old.groups()
            plain = key.strip('"')
            if (kind, plain) not in names:
                names[(kind, plain)] = _slug(plain, taken) if kind == "object" else plain
                taken.add(names[(kind, plain)])
                first = True
            else:
                first = False
            own = f'{indent}class = "overlay"\n' if kind == "overlay" else f"{indent}objects = [{_literal(plain)}]\n"
            if first and sub:                              # its subtable first: the figure's own table before it
                out += [f"{indent}[plot.figures.{names[(kind, plain)]}]\n", own]
            out.append(f"{indent}[plot.figures.{names[(kind, plain)]}{sub}]{tail}\n")
            if first and not sub:
                out.append(own)
            in_figure = not sub
            continue
        header = _TABLE.match(line)
        if header:
            in_figure = header[1].strip().startswith("plot.figures.") and header[1].strip().count(".") == 2
            out.append(line)
            continue
        dotted = _DOTTED.match(line.rstrip("\n"))
        if in_figure and dotted and dotted[2] in STYLE_TABLES:
            out.append(f"{dotted[1]}style.{dotted[2]}{dotted[3]}\n")
            continue
        out.append(line)
    return "".join(out)


def _split_comment(text: str) -> tuple[str, str]:
    """A TOML value and its trailing comment: a `#` outside every string."""
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if quote == '"' and c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#":
            return text[:i].rstrip(), text[i:]
        i += 1
    return text.rstrip(), ""


def _literal(text: str) -> str:
    """A TOML string for it: a literal '…' when it holds a backslash (LaTeX), else a basic "…"."""
    if "\\" in text and "'" not in text and "\n" not in text:
        return f"'{text}'"
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _value(lines: list[str], start: int, head: str) -> tuple[int, str, str]:
    """The value that starts on line `start` (after `head`), maybe spread over lines: (lines it took,
    the value's text, its comments, every line's, kept)."""
    text, comment = _split_comment(head)
    comments = [comment] if comment else []
    end = start
    while True:
        try:
            tomllib.loads("x = " + text)
            return end - start + 1, text, " ".join(comments)
        except tomllib.TOMLDecodeError:
            end += 1
            if end >= len(lines) or end - start > 60:
                raise
            more, extra = _split_comment(lines[end].rstrip("\n"))
            text += " " + more.strip()
            if extra:
                comments.append(extra)


def toml_text(text: str, run=None, project: str = "") -> str:
    """One run TOML migrated (see the module's doc): its new text."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    table = ""
    swept_members = run.runs(None) if run is not None and run.sweep_runs else None
    has_swept = run is not None and any("swept" in run.raw.get("run", {}).get("cfgs", {}).get(k, {}) for k in run.configurations)
    i = 0
    while i < len(lines):
        line = lines[i]
        header = _TABLE.match(line)
        if header:
            table = header[1].strip()
            out.append(line)
            i += 1
            continue
        match = _KEY.match(line.rstrip("\n"))
        if not match:
            out.append(line)
            i += 1
            continue
        indent, key, eq, rest = match.groups()
        key = key.strip('"')
        taken, value_text, comment = _value(lines, i, rest)
        value = tomllib.loads("x = " + value_text)["x"]
        new = None
        if key in LABEL_KEYS:
            if isinstance(value, str) and is_tlatex(value):
                new = _literal(natural(value))
            elif isinstance(value, list) and any(isinstance(v, str) and is_tlatex(v) for v in value):
                new = "[" + ", ".join(_literal(natural(v)) if isinstance(v, str) else repr(v) for v in value) + "]"
        elif key == "swept" and table.startswith("run."):
            i += taken                                     # gone: sweep_runs lists the members
            continue
        elif key == "sweep_runs" and table == "run" and value is True and has_swept and swept_members:
            new = "[" + ", ".join(_literal(k) for k in swept_members) + "]"
        elif key == "executable" and table.startswith("tools.") and isinstance(value, str) and run is not None:
            tag = table.split(".", 1)[1].strip('"')
            tool = run.tools.get(tag)
            if tool is not None and tool.executable and not value.startswith("path:") and "/" not in value:
                built = resolve(value, "executable", project=project, where="")
                if not built.exists() and shutil.which(value):
                    new = _literal("path:" + value)
        if new is None:
            out.extend(lines[i:i + taken])
        else:
            tail = (" " + comment) if comment else ""
            out.append(_wrapped(f"{indent}{match.group(2)}{eq}", new, tail))
        i += taken
    return "".join(out)


def _wrapped(prefix: str, value: str, tail: str, width: int = 110) -> str:
    """`key = [a, b, …]`, broken after a comma once a line passes `width`, the items under the bracket."""
    line = prefix + value + tail
    if len(line) <= width or not value.startswith("["):
        return line + "\n"
    items, depth, quote, start = [], 0, None, 1
    for i, c in enumerate(value):                       # split the array at its top-level commas
        if quote:
            if c == quote and (quote == "'" or value[i - 1] != "\\"):
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == "," and depth == 1:
            items.append(value[start:i].strip())
            start = i + 1
    items.append(value[start:-1].strip())
    pad = " " * (len(prefix) + 1)
    lines, current = [], prefix + "["
    for n, item in enumerate(items):
        piece = item + ("," if n < len(items) - 1 else "]")
        if current.strip() not in ("", prefix.strip() + "[") and len(current) + len(piece) + 1 > width:
            lines.append(current.rstrip())
            current = pad
        current += (piece if current.endswith("[") or current == pad else " " + piece)
    lines.append(current + tail)
    return "\n".join(lines) + "\n"


def card_text(text: str, folder) -> str:
    """A base card without the lines for keys the runner sets (the folder's [card] owned)."""
    owned = {tools._normal(k) for k in folder.get("card", "owned", [])}
    if not owned or folder.get("card", "style", "append") != "append":
        return text
    parse = tools.card_parser(folder)
    kept = [line for line in text.splitlines(keepends=True)
            if not ((parsed := parse(line.rstrip("\n"))) and parsed[0] in owned)]
    return "".join(kept)


#: The exports that were a tool's card under another name (V21): pythia_cmnd, herwig_in, sherpa_yaml …
CARD_EXPORTS = {"card", "cmnd", "in", "yaml", "proc", "tcl", "sin"}


def formerly_text(text: str) -> str:
    """A tool folder's old name as its name: tool = "<old>" → tool = "<name>", for every folder whose
    [tool] formerly lists it (custom → exec, audit 3, phase 4.2)."""
    for name, folder in tools.folders().items():
        for old in folder.get("tool", "formerly", []):
            text = re.sub(rf'^(\s*tool\s*=\s*)"{re.escape(old)}"', lambda m: f'{m[1]}"{name}"', text, flags=re.M)
    return text


def _flat(entries) -> list[str]:
    return [x for e in entries or [] for x in (_flat(e) if isinstance(e, list) else [e]) if isinstance(x, str)]


def _block_end(lines: list[str], header: int) -> int:
    """Where a table's keys end: before the blank lines and comments ahead of the next table header."""
    end = next((i for i in range(header + 1, len(lines)) if _TABLE.match(lines[i])), len(lines))
    while end > header + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return end


def exports_text(text: str, imported: dict | None = None) -> str:
    """An exec or module table's export keys (`pythia_cmnd = true`, C13) as generate_cards (audit 3,
    phase 4.2): the table each one named, as "<tag>:<product>" when its folder makes it on demand, in
    every configuration whose chain runs the asking table (in [run] when every configuration does), and
    `{std:<key>}` as `{context:<tag>.<card or product>}`. By line; the rest of the file is kept. `imported`
    ({tag: tool}) names the tables the file's imports give, which an export key may name too."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return text
    tables = {t: v for t, v in data.get("tools", {}).items() if isinstance(v, dict)}
    known = tools.folders()
    wants: dict[str, list[str]] = {}                       # asking tag → generate_cards entries
    drop: dict[str, set[str]] = {}
    renamed: dict[str, str] = {}
    for tag, table in tables.items():
        folder = known.get(table.get("tool", "")) or next(
            (f for f in known.values() if table.get("tool") in f.get("tool", "formerly", [])), None)
        if folder is None or not folder.get("tool", "config_file"):
            continue
        for key, value in table.items():
            m = tools.EXPORT.match(key)
            if not m or m["tool"] not in known or key in folder.spec.get("options", {}) or isinstance(value, dict):
                continue
            drop.setdefault(tag, set()).add(key)
            if value is False:
                continue
            kind, export = m["tool"], m["export"]
            same = [t for t, other in tables.items() if other.get("tool") == kind] or \
                   [t for t, other in (imported or {}).items() if other == kind]
            target = value if isinstance(value, str) else kind if kind in same else same[0] if len(same) == 1 else None
            if target is None:
                drop[tag].discard(key)                     # ambiguous: left for the plan to name
                continue
            products = known[kind].spec.get("context", {}).get("products", {})
            wants.setdefault(tag, []).append(f"{target}:{export}" if export in products else target)
            renamed[key] = f"{target}.{export if export in products else 'card' if export in CARD_EXPORTS else export}"
    if not drop:
        return text
    lines = text.splitlines(keepends=True)
    for tag, keys in drop.items():                         # the keys out of their tables
        header = next((i for i, l in enumerate(lines) if _TABLE.match(l) and _TABLE.match(l)[1].strip() == f"tools.{tag}"), None)
        if header is None:
            continue
        end = next((i for i in range(header + 1, len(lines)) if _TABLE.match(lines[i])), len(lines))
        lines[header + 1:end] = [l for l in lines[header + 1:end]
                                 if not ((m := _KEY.match(l.rstrip("\n"))) and m[2] in keys)]
    text = "".join(lines)
    for key, new in renamed.items():
        text = text.replace("{std:" + key + "}", "{context:" + new + "}")
    run = data.get("run", {})
    cfgs = run.get("cfgs", {}) if isinstance(run.get("cfgs"), dict) else {}

    def chain_of(name: str, seen=()) -> list[str]:
        table = cfgs.get(name, {})
        if "tools" in table:
            return _flat(table["tools"])
        if isinstance(table.get("extends"), str) and table["extends"] not in seen:
            return chain_of(table["extends"], (*seen, name))
        return _flat(run.get("tools"))

    needs = {name: list(dict.fromkeys(e for tag in chain_of(name) for e in wants.get(tag, []))) for name in cfgs}
    def put(header_name: str, entries: list[str]) -> None:
        nonlocal text
        lines = text.splitlines(keepends=True)
        header = next((i for i, l in enumerate(lines) if _TABLE.match(l) and _TABLE.match(l)[1].strip() == header_name), None)
        if header is None or not entries:
            return
        at = _block_end(lines, header)
        lines.insert(at, "generate_cards = [" + ", ".join(f'"{e}"' for e in entries) + "]   # their cards in the context file\n")
        text = "".join(lines)
    every = list(dict.fromkeys(e for entries in wants.values() for e in entries))
    if not cfgs or (all(needs.values()) and len({tuple(v) for v in needs.values()}) == 1):
        put("run", next(iter(needs.values())) if cfgs else every)
    else:
        for name, entries in needs.items():
            put(f"run.cfgs.{name}", entries)
    return text


# ── v3 (audit 3, phase 6.3; runner/v3.py) ──────────────────────────────────────────────────────

RUN_V3 = {"configuration": "run", "event_count": "events", "tools": "chain", "sweeps": "vary"}
CFG_V3 = {**RUN_V3, "label": "folder", "static": "fixed"}
TOOL_V3 = {"baseconfig": "card", "output_file": "output"}


def _depth(text: str) -> int:
    """Brackets opened and not closed on a line, outside strings and comments."""
    depth, quote, i = 0, "", 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == "#":
            break
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        i += 1
    return depth


def _blocks(text: str) -> list[dict]:
    """A file's tables: each {name, header, lead, entries}; an entry is (key or None, its lines). The
    comment lines right above a header (no blank line between) are that table's lead."""
    blocks = [{"name": None, "header": None, "lead": [], "entries": []}]
    pending: list[str] = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        table = _TABLE.match(line)
        if table and not line.lstrip().startswith("#"):
            lead = []
            while blocks[-1]["entries"] and blocks[-1]["entries"][-1][0] is None \
                    and blocks[-1]["entries"][-1][1][0].lstrip().startswith("#"):
                lead.insert(0, blocks[-1]["entries"].pop()[1][0])
            blocks.append({"name": table[1].strip(), "header": line, "lead": lead, "entries": []})
            i += 1
            continue
        key = _KEY.match(line.rstrip("\n"))
        if key and not line.lstrip().startswith("#"):
            chunk, depth = [line], _depth(key[4])
            while depth > 0 and i + 1 < len(lines):
                i += 1
                chunk.append(lines[i])
                depth += _depth(lines[i])
            blocks[-1]["entries"].append((key[2].strip('"'), chunk))
        else:
            blocks[-1]["entries"].append((None, [line]))
        i += 1
    return blocks


def _renamed(chunk: list[str], new: str) -> list[str]:
    """An entry under a new key, its `=` where it was (an aligned table stays aligned)."""
    match = _KEY.match(chunk[0].rstrip("\n"))
    before, after = match[3].split("=", 1)
    column = len(match[2]) + len(before)
    first = f"{match[1]}{new}{' ' * max(1, column - len(new))}={after}{match[4]}" + ("\n" if chunk[0].endswith("\n") else "")
    return [first, *chunk[1:]]


def _tv(value) -> str:
    """A TOML value as written: a string with backslashes in single quotes (labels' LaTeX)."""
    if isinstance(value, str) and "\\" in value and "'" not in value and "\n" not in value:
        return f"'{value}'"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_tk(k)} = {_tv(v)}" for k, v in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(_tv(v) for v in value) + "]"
    return tomli_w.dumps({"v": value}).split("=", 1)[1].strip()


def _tk(key: str) -> str:
    return key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else f'"{key}"'


def _seed_entry(table: dict, chunk: list[str]) -> list[str]:
    seed = table.get("manual_seed") if table.get("seed_type") == "manual" else table.get("seed_type")
    match = _KEY.match(chunk[0].rstrip("\n"))
    return [f"{match[1]}seed = {_tv(seed)}\n"]


def _quantity_v3(name: str, block: dict, q: dict, fixed) -> list[str]:
    """A v2 quantity's table as v3's: its other keys as they were, then to, fixed and its points as rows."""
    from .sweep import tag_of
    from .config import Quantity
    moved = ("values", "tags", "labels", "styles", "key", "target")
    out = [line for key, chunk in block["entries"] if key not in moved for line in chunk]
    while out and not out[-1].strip():
        out.pop()
    target = q.get("target")
    key = q.get("key")
    if target is not None or key is not None:
        targets = [target] if isinstance(target, str) else list(target or [])
        if targets:
            to = {}
            for entry in targets:
                tag = entry.split("/")[0]
                given = key if isinstance(key, str) else (key or {}).get(tag)
                to[entry] = given if given is not None else True
        else:
            to = dict(key)
        out.append(f"to     = {_tv(to)}\n")
    if fixed is not None:
        out.append(f"fixed  = {_tv(fixed)}\n")
    values = q.get("values", [])
    probe = Quantity(name=name, values=values, tags=[str(x) for x in q.get("tags", [])])
    rows = []
    for i, value in enumerate(values):
        row = {"tag": tag_of(probe, i), "value": value}
        if q.get("labels"):
            row["label"] = q["labels"][i]
        if q.get("styles") and q["styles"][i]:
            row["style"] = q["styles"][i]
        rows.append("{ " + ", ".join(f"{k} = {_tv(v)}" for k, v in row.items()) + " }")
    if len(rows) == 1 and len(rows[0]) < 80:
        out.append(f"points = [{rows[0]}]\n")
    else:
        out += ["points = [\n", *(f"  {r},\n" for r in rows), "]\n"]
    return out


_COMMENTED_CFG = re.compile(r"^(\s*#\s*)\[run\.cfgs\.([^\]]+)\](.*)$")
_COMMENTED_KEY = re.compile(r"^(\s*#\s*)([A-Za-z_]+)(\s*)=(.*)$")


def _commented_cfgs(text: str) -> str:
    """A configuration commented out stays one to uncomment (as V98's did): its header and its commented
    keys in v3's names (`# [cfgs.<name>]`, `# vary`, `# fixed`, `# chain`, `# folder`, `# events`), the
    `=` column kept."""
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        bare, end = line.rstrip("\n"), ("\n" if line.endswith("\n") else "")
        if (head := _COMMENTED_CFG.match(bare)):
            out.append(f"{head[1]}[cfgs.{head[2]}]{head[3]}{end}")
            inside = True
            continue
        if inside and (key := _COMMENTED_KEY.match(bare)) and key[2] in CFG_V3:
            new, column = CFG_V3[key[2]], len(key[2]) + len(key[3])
            out.append(f"{key[1]}{new}{' ' * max(1, column - len(new))}={key[4]}{end}")
            continue
        if inside and not bare.lstrip().startswith("#"):
            inside = False
        out.append(line)
    return "".join(out)


def v3_text(text: str) -> str:
    """A v2 run TOML in v3's form (03 §6), by table, comments kept: [config] → [file], [run.cfgs.<name>] →
    [cfgs.<name>], keys renamed, tools typed by their table's name, [prelim] inferred (keep = false on a
    scratch file's producer; its commands to [run]), [static] into each quantity's fixed, quantities as
    rows. A v3 file is left as it is."""
    from .v3 import is_v3
    data = tomllib.loads(text)
    if is_v3(data):
        return text
    run, prelim, static = data.get("run", {}), data.get("prelim", {}), data.get("static", {})
    cfgs, tool_tables, quantities = run.get("cfgs", {}), data.get("tools", {}), data.get("quantities", {})
    scratch = set(prelim.get("files", []))
    for cfg in cfgs.values():
        if isinstance(cfg, dict) and isinstance(cfg.get("prelim"), dict):
            scratch |= set(cfg["prelim"].get("files", []))
    def outputs(tb) -> list:
        given = tb.get("output_file", []) if isinstance(tb, dict) else []
        return given if isinstance(given, list) else [given]
    unkept = {tag for tag, tb in tool_tables.items() if set(outputs(tb)) & scratch}
    writers: dict[str, list[str]] = {}
    for tag, tb in tool_tables.items():
        for name in outputs(tb):
            writers.setdefault(name, []).append(tag)
    producer = {name: tags[0] for name, tags in writers.items()        # input = "<producer>" where it is clear
                if len(tags) == 1 and len(outputs(tool_tables[tags[0]])) == 1 and name not in tool_tables}
    chains = [repr(cfg["tools"]) for cfg in cfgs.values() if isinstance(cfg, dict) and "tools" in cfg]

    def tags_of(layer: dict) -> set:
        return {t for key in ("tools", "pre", "post", "generate_cards") for g in layer.get(key, []) or []
                for t in (g if isinstance(g, list) else [g]) if isinstance(t, str)}
    runs = [tags_of(run) | tags_of(cfg) for cfg in cfgs.values() if isinstance(cfg, dict)] or [tags_of(run)]

    def together(reader: str, writer: str) -> bool:
        """An input is written as its producer only where they run together in this file: a file
        imported in part (only its rivet and merge tables, say) keeps the file's name, which whatever
        the importer runs may write."""
        return any(reader in tags and writer in tags for tags in runs)
    hoisted = None                                                  # the chain most configurations share: [run]'s
    if "tools" not in run and chains:
        common = max(set(chains), key=chains.count)
        if chains.count(common) >= 2:
            hoisted = next(cfg["tools"] for cfg in cfgs.values() if isinstance(cfg, dict) and repr(cfg.get("tools")) == common)
    out: list[str] = []
    for block in _blocks(text):
        name, entries = block["name"], block["entries"]
        lines: list[str] = []
        if name is None:
            out += [l for _, chunk in entries for l in chunk]
            continue
        if name in ("prelim", "static") or (name.startswith("run.cfgs.") and name.endswith(".prelim")):
            continue                                                    # inferred, and into fixed
        if name == "config" or name.startswith("config."):
            header = block["header"].replace("[config", "[file", 1)
            lines = [l for _, chunk in entries for l in chunk]
        elif name == "run":
            header = block["header"]
            for key, chunk in entries:
                if key in RUN_V3:
                    lines += _renamed(chunk, RUN_V3[key])
                elif key == "seed_type":
                    lines += _seed_entry(run, chunk)
                elif key == "manual_seed":
                    continue
                else:
                    lines += chunk
            tail = []
            while lines and not lines[-1].strip():
                tail.insert(0, lines.pop())
            if hoisted is not None:
                lines.append(f"chain         = {_tv(hoisted)}   # every configuration's, unless it says its own\n")
            if prelim.get("commands"):
                lines.append(f"commands      = {_tv(prelim['commands'])}   # in each point's folder, before its tools\n")
            lines += tail
        elif name.startswith("run.cfgs."):
            rest = name[len("run.cfgs."):]
            cfg_name, _, sub = rest.partition(".")
            sub = "fixed" if sub == "static" else sub
            header = block["header"].replace(f"[{name}]", f"[cfgs.{cfg_name}{'.' + sub if sub else ''}]", 1)
            cfg = cfgs.get(cfg_name.strip('"'), {})
            for key, chunk in entries:
                if sub:
                    lines += chunk
                elif key == "prelim":
                    continue
                elif key == "tools" and hoisted is not None and repr(cfg.get("tools")) == repr(hoisted):
                    continue                                            # [run]'s chain
                elif key == "sweeps" and cfg.get("sweeps") == [] and "extends" not in cfg and "sweeps" not in run:
                    continue                                            # the default
                elif key in CFG_V3:
                    lines += _renamed(chunk, CFG_V3[key])
                elif key == "seed_type":
                    lines += _seed_entry(cfg, chunk)
                elif key == "manual_seed":
                    continue
                else:
                    lines += chunk
        elif name.startswith("tools.") and name.count(".") == 1:
            tag = name[len("tools."):].strip('"')
            table = tool_tables.get(tag, {})
            header, placed = block["header"], False
            for key, chunk in entries:
                if key == "tool":
                    if table.get("tool") != tag:
                        lines += _renamed(chunk, "uses")
                    continue
                if (key == "input" and isinstance(table.get("input"), str) and table["input"] in producer
                        and together(tag, producer[table["input"]])):
                    match = _KEY.match(chunk[0].rstrip("\n"))
                    comment = match[4].split("#", 1)[1] if "#" in match[4] else ""
                    lines.append(f"{match[1]}input{match[3]}\"{producer[table['input']]}\"" + (f"   #{comment}" if comment else "") + "\n")
                    continue
                if key in TOOL_V3:
                    lines += _renamed(chunk, TOOL_V3[key])
                    if key == "output_file" and tag in unkept:
                        lines.append("keep        = false              # a scratch file of the point, not a product\n")
                        placed = True
                    continue
                lines += chunk
            if tag in unkept and not placed:
                lines.append("keep = false\n")
        elif name == "plot":                                            # v2's [plot]-level "default": v3's "native"
            header = block["header"]
            native = {k for k, e in schema.keys("plot").items() if e.get("native_ok")}
            for key, chunk in entries:
                if key in native and data.get("plot", {}).get(key) == schema.DEFAULT:
                    chunk = [chunk[0].replace('"default"', '"native"', 1), *chunk[1:]]
                lines += chunk
        elif name.startswith("quantities.") and name.count(".") == 1:
            qname = name[len("quantities."):].strip('"')
            header = block["header"]
            fixed = static.get(qname)
            lines = _quantity_v3(qname, block, quantities.get(qname, {}), None if fixed == "default" else fixed)
            lines.append("\n")
        else:
            header = block["header"]
            lines = [l for _, chunk in entries for l in chunk]
        out += [*block["lead"], header, *lines]
    for qname, fixed in static.items():                               # an imported quantity, fixed here
        if qname not in quantities and fixed != "default":
            out += [f"\n[quantities.{_tk(qname)}]                # the imported quantity, fixed here\n",
                    f"fixed = {_tv(fixed)}\n"]
    text = "".join(out)
    if "[cfgs." not in text and "chain" not in run and "[file]" not in text:
        text = "[file]\nschema = 3                     # the run TOML's third form (hep migrate --v3)\n\n" + text
    return re.sub(r"\n{3,}", "\n\n", _commented_cfgs(text))


#: What a point's or a configuration's folder of output/ recorded: it goes to records/ (U21).
RECORDED = ("provenance.json", "identity.json", ".complete", "points.json")


def layout_moves(work: Path) -> list[tuple[Path, Path]]:
    """`hep migrate --layout` (5.1): every file of a work dir's output/ and where it goes now. Records
    (provenance, identity, .complete, points.json, cluster submissions) to records/; prepare caches,
    card checks and converted data (output/<P>/.cache/) to .cache/<P>/; everything else (cards, configs,
    logs, scratch files, journals, page documents, reproductions) to logs/."""
    output = work / "output"
    moves = []
    for path in sorted(output.rglob("*")) if output.is_dir() else ():
        if path.is_dir() and not path.is_symlink():
            continue
        rel = path.relative_to(output)
        parts = rel.parts
        if len(parts) > 2 and parts[1] == ".cache":
            target = work / ".cache" / parts[0] / Path(*parts[2:])
        elif path.name in RECORDED or (len(parts) > 4 and parts[3] == "cluster"):
            target = work / "records" / rel
        else:
            target = work / "logs" / rel
        moves.append((path, target))
    return moves


def deck_moves(work: Path) -> list[tuple[Path, Path]]:
    """A deck written in reports/<deck>/ (before decks/, U22): its sources to decks/<deck>/, everything but
    what `hep deck` builds there (panels/, figures/, build/ and the outputs)."""
    from .deck import BUILD, FIGURES, OUTPUTS, PANELS
    moves = []
    reports = work / "reports"
    for folder in sorted(p for p in reports.iterdir() if p.is_dir()) if reports.is_dir() else ():
        if not any((folder / name).is_file() for name in ("deck.toml", "deck.md")):
            continue
        for path in sorted(folder.iterdir()):
            if path.name in (PANELS, FIGURES, BUILD, *OUTPUTS) or path.name.endswith(".sha256"):
                continue
            moves.append((path, work / "decks" / folder.name / path.name))
    return moves


def apply_layout(moves: list[tuple[Path, Path]], work: Path) -> int:
    """The moves made (renames, so nothing is copied); a file already where it goes is left in output/,
    and named. output/ goes when nothing is left in it."""
    left = 0
    for source, target in moves:
        if target.exists() or target.is_symlink():
            print(f"left    {source}: {target} exists")
            left += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
    output = work / "output"
    for folder in sorted((p for p in output.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    if output.is_dir() and not any(output.iterdir()):
        output.rmdir()
    return left


def plan(names: list[str], v3: bool = False) -> dict[Path, tuple[str, str]]:
    """Every file the configs touch: path → (its text, its migrated text), only those that change. With
    v3, a file then takes the third form (v3_text)."""
    changes: dict[Path, tuple[str, str]] = {}
    for name in names:
        text = config_file(name).read_text(encoding="utf-8")
        first = formerly_text(defaults_text(cfgs_text(config_text(figure_text(placeholder_text(text))))))
        given = configmod.load(name, strict=False, text=first)          # the tables its imports give, too
        first = exports_text(first, {tag: tool.tool for tag, tool in given.tools.items()})
        run = configmod.load(name, strict=False, text=first)
        new = toml_text(first, run, run.project)
        if v3:
            new = v3_text(new)
        if new != text:
            changes[run.path] = (text, new)
        cards: dict[Path, object] = {}
        for tool in run.tools.values():                    # each base card, by its folder's rules (no planning)
            folder = tools.folders().get(tool.tool)
            for base in tool.baseconfig if folder is not None else ():
                try:
                    path = resolve(base, "baseconfig", project=run.project, where=f"[tools.{tool.tag}].baseconfig")
                except HepError:
                    continue
                if path.is_file():
                    cards.setdefault(path, folder)
        for base, folder in cards.items():
            text = base.read_text(encoding="utf-8")
            new = card_text(text, folder)
            if new != text:
                changes.setdefault(base, (text, new))
    return changes


def diff(path: Path, old: str, new: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=str(path), tofile=str(path) + " (migrated)"))


def apply(changes: dict[Path, tuple[str, str]]) -> None:
    for path, (_, new) in changes.items():
        path.write_text(new, encoding="utf-8")
