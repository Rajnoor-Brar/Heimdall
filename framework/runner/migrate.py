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

from . import config as configmod
from . import tools
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


def exports_text(text: str) -> str:
    """An exec or module table's export keys (`pythia_cmnd = true`, C13) as generate_cards (audit 3,
    phase 4.2): the table each one named, as "<tag>:<product>" when its folder makes it on demand, in
    every configuration whose chain runs the asking table (in [run] when every configuration does), and
    `{std:<key>}` as `{context:<tag>.<card or product>}`. By line; the rest of the file is kept."""
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
            same = [t for t, other in tables.items() if other.get("tool") == kind]
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


def plan(names: list[str]) -> dict[Path, tuple[str, str]]:
    """Every file the configs touch: path → (its text, its migrated text), only those that change."""
    changes: dict[Path, tuple[str, str]] = {}
    for name in names:
        text = config_file(name).read_text(encoding="utf-8")
        first = exports_text(formerly_text(defaults_text(cfgs_text(config_text(figure_text(placeholder_text(text)))))))
        run = configmod.load(name, strict=False, text=first)
        new = toml_text(first, run, run.project)
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
