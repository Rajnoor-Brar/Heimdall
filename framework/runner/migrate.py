"""`heimdall migrate [CONFIG…] [--apply]` (rank 5, V79): errand files and their cards in today's forms.

"break and migrate": what the runner now refuses, rewritten in what it takes.
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
* (Heimdall, doc:layout) `{repo}` → `{work}`, or `{heimdall}` for what moved into
  Heimdall: `{repo}/build/App_*`, `Paint.exe` and `Herwig/` → `{apps}/…`, `{repo}/utils/` → `{heimdall}/src/`.
  On the text, anywhere in the file (a comment's example too).
* `{heimdall}/framework/Apps/` → `{apps}/`: the compiled apps are in Himinbjorg.
* `tool = "custom"` → `tool = "exec"`; the export keys of an exec or module table
  (`pythia_cmnd = true`, `herwig_run = true`) → `generate_cards` (the context file gives every tool's card
  and config), in each configuration whose chain runs that table, or in [run] when every one does;
  `{std:<key>}` → `{context:<tag>.<card or product>}`.

* `[run]` → `[errand]`, `[run].project` → `[errand].assignment` (`errand_text`), first: the functions
  above read today's names (`[errand.<cfg>]`, `[errand.defaults]`).

`heimdall migrate --names [--apply]` (V213) is a work dir's own: Heimdall's old names in its files
(`names_changes`), its marker `hep.toml` → `heimdall.toml` first; then the Errand names' (`errand_changes`): its configs, its
records' snapshots and provenance, its plot documents' [source].
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
import tomllib
from pathlib import Path

import tomli_w

from . import config as configmod
from . import schema, tools
from .errors import HeimdallError
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


_RUN_TABLE = re.compile(r"^(\s*#*\s*)\[\s*errand\.([A-Za-z0-9_\-]+)((?:\.[A-Za-z0-9_\-]+)*)\s*\](.*)$", re.S)


def cfgs_text(text: str) -> str:
    """[run.<cfg>] as [run.cfgs.<cfg>] (V98), by line, in today's names ([errand.<cfg>] as [errand.cfgs.<cfg>],
    after errand_text): a table header (or a commented-out one) under [errand] that is not one of [errand]'s own
    keys, `defaults` (V99's to move) or `cfgs`."""
    from . import schema
    own = set(schema.keys("errand")) | {"defaults", "cfgs"}
    out = []
    for line in text.splitlines(keepends=True):
        match = _RUN_TABLE.match(line)
        if match and match[2] not in own:
            tail = match[4]
            pad = len(tail) - len(tail.lstrip(" "))
            if pad and tail.lstrip(" ").startswith("#"):             # a comment after it keeps its column
                tail = " " * max(1, pad - len("cfgs.")) + tail.lstrip(" ")
            line = f"{match[1]}[errand.cfgs.{match[2]}{match[3]}]{tail}"
        out.append(line)
    return "".join(out)


def defaults_text(text: str) -> str:
    """[run.defaults]'s keys into [run] (V99), by line, in today's names ([errand.defaults] into [errand]): the
    block is taken out (its header and its lines up to the next table) and its lines go after [errand]'s own; a
    key [errand] sets too loses [errand]'s line, since [errand.defaults] was the nearer layer."""
    lines = text.splitlines(keepends=True)
    heads = [i for i, l in enumerate(lines) if _TABLE.match(l)]
    start = next((i for i in heads if _TABLE.match(lines[i])[1].strip() == "errand.defaults"), None)
    run = next((i for i in heads if _TABLE.match(lines[i])[1].strip() == "errand"), None)
    if start is None or run is None:
        return text
    end = next((i for i in heads if i > start), len(lines))
    block = lines[start + 1:end]
    while block and not block[-1].strip():
        block.pop()
    moved = {m[2] for l in block if (m := _KEY.match(l.rstrip("\n")))}
    rest = lines[:start] + lines[end:]
    run = next(i for i, l in enumerate(rest) if _TABLE.match(l) and _TABLE.match(l)[1].strip() == "errand")
    after = next((i for i in range(run + 1, len(rest)) if _TABLE.match(rest[i])), len(rest))
    body = [l for l in rest[run + 1:after] if not ((m := _KEY.match(l.rstrip("\n"))) and m[2] in moved)]
    tail = []
    while body and not body[-1].strip():
        tail.insert(0, body.pop())
    return "".join(rest[:run + 1] + body + block + (tail or ["\n"]) + rest[after:])


#: High-Energy's single root, split (doc:layout): the first prefix that matches wins.
PLACEHOLDERS = (("{repo}/build/App_", "{apps}/App_"),
                ("{repo}/build/Paint.exe", "{apps}/Paint.exe"),
                ("{repo}/build/Herwig/", "{apps}/Herwig/"),
                ("{heimdall}/framework/Apps/", "{apps}/"),
                ("{repo}/utils/", "{heimdall}/src/"),
                ("{repo}", "{work}"))
_REPO = re.compile("|".join(re.escape(old) for old, _ in PLACEHOLDERS))


def placeholder_text(text: str) -> str:
    """{repo} as {work}, {apps} for the compiled apps, {heimdall} for Heimdall's files (PLACEHOLDERS)."""
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


def backend_text(text: str) -> str:
    """The retired plot backends of `[plot] backend`, by line, comment and layout kept: "yoda" is "mpl" (which draws
    the pages rivet-mkhtml did), "both" is ["root", "mpl"], and a list drops what it then names twice. Idempotent."""
    out, plot = [], False
    for line in text.splitlines(keepends=True):
        header = _TABLE.match(line.rstrip("\n"))
        if header:
            plot = header.group(1).strip() == "plot"
        key = _KEY.match(line.rstrip("\n")) if plot and not line.lstrip().startswith("#") else None
        if key and key.group(2) == "backend":
            rest = key.group(4)
            body, comment = _split_comment(rest)
            gap = rest[len(body):len(rest) - len(comment)] if comment else ""
            try:
                value = tomllib.loads(f"v = {body}")["v"]
            except tomllib.TOMLDecodeError:
                value = None
            names = [value] if isinstance(value, str) else value
            if isinstance(names, list) and any(n in ("yoda", "both") for n in names):
                swap = [m for n in names for m in (("root", "mpl") if n == "both" else ("mpl",) if n == "yoda" else (n,))]
                swap = list(dict.fromkeys(swap))
                shown = _literal(swap[0]) if isinstance(value, str) and len(swap) == 1 else "[" + ", ".join(_literal(n) for n in swap) + "]"
                line = f"{key.group(1)}{key.group(2)}{key.group(3)}{shown}{gap}{comment}" + ("\n" if line.endswith("\n") else "")
        out.append(line)
    return "".join(out)


def figure_text(text: str) -> str:
    """The old figure tables of an errand file as [plot.figures] (V81), by line; see the module's doc."""
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


def toml_text(text: str, errand=None, assignment: str = "") -> str:
    """One errand file migrated (see the module's doc): its new text."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    table = ""
    swept_members = errand.runs(None) if errand is not None and errand.sweep_runs else None
    has_swept = errand is not None and any("swept" in errand.raw.get("errand", {}).get("cfgs", {}).get(k, {}) for k in errand.configurations)
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
        elif key == "swept" and table.startswith("errand."):
            i += taken                                     # gone: sweep_runs lists the members
            continue
        elif key == "sweep_runs" and table == "errand" and value is True and has_swept and swept_members:
            new = "[" + ", ".join(_literal(k) for k in swept_members) + "]"
        elif key == "executable" and table.startswith("tools.") and isinstance(value, str) and errand is not None:
            tag = table.split(".", 1)[1].strip('"')
            tool = errand.tools.get(tag)
            if tool is not None and tool.executable and not value.startswith("path:") and "/" not in value:
                built = resolve(value, "executable", assignment=assignment, where="")
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
    [tool] formerly lists it (custom → exec)."""
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
    """An exec or module table's export keys (`pythia_cmnd = true`, C13) as generate_cards (
    phase 4.2): the table each one named, as "<tag>:<product>" when its folder makes it on demand, in
    every configuration whose chain runs the asking table (in [errand] when every configuration does), and
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
    errand = data.get("errand", {})
    cfgs = errand.get("cfgs", {}) if isinstance(errand.get("cfgs"), dict) else {}

    def chain_of(name: str, seen=()) -> list[str]:
        table = cfgs.get(name, {})
        if "tools" in table:
            return _flat(table["tools"])
        if isinstance(table.get("extends"), str) and table["extends"] not in seen:
            return chain_of(table["extends"], (*seen, name))
        return _flat(errand.get("tools"))

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
        put("errand", next(iter(needs.values())) if cfgs else every)
    else:
        for name, entries in needs.items():
            put(f"errand.cfgs.{name}", entries)
    return text


# ── v3 (runner/v3.py) ──────────────────────────────────────────────────────

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


_COMMENTED_CFG = re.compile(r"^(\s*#\s*)\[errand\.cfgs\.([^\]]+)\](.*)$")
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
    """A v2 errand file in v3's form (doc:errand-file), by table, comments kept: [config] → [file], [errand.cfgs.<name>] →
    [cfgs.<name>], keys renamed, tools typed by their table's name, [prelim] inferred (keep = false on a
    scratch file's producer; its commands to [errand]), [static] into each quantity's fixed, quantities as
    rows. A v3 file is left as it is."""
    from .v3 import is_v3
    data = tomllib.loads(text)
    if is_v3(data):
        return text
    errand, prelim, static = data.get("errand", {}), data.get("prelim", {}), data.get("static", {})
    cfgs, tool_tables, quantities = errand.get("cfgs", {}), data.get("tools", {}), data.get("quantities", {})
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
    runs = [tags_of(errand) | tags_of(cfg) for cfg in cfgs.values() if isinstance(cfg, dict)] or [tags_of(errand)]

    def together(reader: str, writer: str) -> bool:
        """An input is written as its producer only where they run together in this file: a file
        imported in part (only its rivet and merge tables, say) keeps the file's name, which whatever
        the importer runs may write."""
        return any(reader in tags and writer in tags for tags in runs)
    hoisted = None                                                  # the chain most configurations share: [errand]'s
    if "tools" not in errand and chains:
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
        if name in ("prelim", "static") or (name.startswith("errand.cfgs.") and name.endswith(".prelim")):
            continue                                                    # inferred, and into fixed
        if name == "config" or name.startswith("config."):
            header = block["header"].replace("[config", "[file", 1)
            lines = [l for _, chunk in entries for l in chunk]
        elif name == "errand":
            header = block["header"]
            for key, chunk in entries:
                if key in RUN_V3:
                    lines += _renamed(chunk, RUN_V3[key])
                elif key == "seed_type":
                    lines += _seed_entry(errand, chunk)
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
        elif name.startswith("errand.cfgs."):
            rest = name[len("errand.cfgs."):]
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
                    continue                                            # [errand]'s chain
                elif key == "sweeps" and cfg.get("sweeps") == [] and "extends" not in cfg and "sweeps" not in errand:
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
    if "[cfgs." not in text and "chain" not in errand and "[file]" not in text:
        text = "[file]\nschema = 3                     # the errand file's third form (heimdall migrate --v3)\n\n" + text
    return re.sub(r"\n{3,}", "\n\n", _commented_cfgs(text))


#: What a point's or a configuration's folder of output/ recorded: it goes to records/.
RECORDED = ("provenance.json", "identity.json", ".complete", "points.json")


def layout_moves(work: Path) -> list[tuple[Path, Path]]:
    """`heimdall migrate --layout` (5.1): every file of a work dir's output/ and where it goes now. Records
    (provenance, identity, .complete, points.json, cluster submissions) to records/; prepare caches,
    card checks and converted data (output/<A>/.cache/) to .cache/<A>/; everything else (cards, configs,
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


#: What lives in a configuration's folder of records/ beside its points (V157), and of results/: the
#: stages' products (later stages name them, so they stay) and the pages.
RECORD_FOLDERS = ("points", "logs", "plots", "config", "cluster")
RESULT_FOLDERS = ("points", "plots", "pre", "post")


def _configurations(root: Path) -> list[Path]:
    """A tree's configuration folders, <A>/<E>/<R> relative to it (not compare/, nothing hidden)."""
    def dirs(folder: Path) -> list[Path]:
        return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")) if folder.is_dir() else []
    return [cfg.relative_to(root) for assignment in dirs(root) for name in dirs(assignment) for cfg in dirs(name)
            if cfg.name != "compare"]


def logs_moves(work: Path) -> list[tuple[Path, Path]]:
    """`heimdall migrate --layout` (V157): a work dir's logs/ into records/, and each configuration's points
    into points/ of records/ and results/ (renames of whole folders):
    * records/<A>/<E>/<R>/<point>/ → records/…/<R>/points/<point>/ (a stage's too);
    * results/<A>/<E>/<R>/<point>/ → results/…/<R>/points/<point>/ (pre/, post/ and plots/ stay);
    * logs/<A>/<E>/<R>/<point>/ → records/…/<R>/logs/<point>/ (apply_logs takes its logs/*.log up one);
    * logs/<A>/<E>/<R>/plots/ and status.jsonl → records/…/<R>/; logs/<A>/<E>/compare/<figure>/ →
      records/<A>/<E>/compare/<figure>/;
    * logs/<A>/.reproduce/ → .cache/<A>/reproduce/; logs/plots/ (heimdall overlay's page documents) →
      .cache/overlay/."""
    records, results, logs = work / "records", work / "results", work / "logs"
    moves: list[tuple[Path, Path]] = []
    for rel in _configurations(records):
        moves += [(e, records / rel / "points" / e.name) for e in sorted((records / rel).iterdir())
                  if e.is_dir() and e.name not in RECORD_FOLDERS]
    for rel in _configurations(results):
        moves += [(e, results / rel / "points" / e.name) for e in sorted((results / rel).iterdir())
                  if e.is_dir() and e.name not in RESULT_FOLDERS]
    for top in sorted(logs.iterdir()) if logs.is_dir() else ():
        if top.name == "plots":
            moves.append((top, work / ".cache" / "overlay"))
            continue
        for name in sorted(top.iterdir()) if top.is_dir() else ():
            if name.name == ".reproduce":
                moves.append((name, work / ".cache" / top.name / "reproduce"))
                continue
            for cfg in sorted(name.iterdir()) if name.is_dir() else [name]:
                rel = cfg.relative_to(logs)
                if not cfg.is_dir():
                    moves.append((cfg, records / rel))
                elif cfg.name == "compare":
                    moves += [(figure, records / rel / figure.name) for figure in sorted(cfg.iterdir())]
                else:
                    for entry in sorted(cfg.iterdir()):
                        kept_here = entry.name in ("plots", "status.jsonl") or not entry.is_dir()
                        moves.append((entry, records / rel / (entry.name if kept_here else f"logs/{entry.name}")))
    return moves


def apply_logs(moves: list[tuple[Path, Path]], work: Path) -> int:
    """logs_moves made (renames: nothing is copied); a move whose target exists is left, and named. Then
    each working folder's logs/*.log up one level, each moved configuration's points.json pointed at the
    new folders, and logs/ removed once empty. Returns the moves left."""
    left = 0
    for source, target in moves:
        if target.exists() or target.is_symlink():
            print(f"left    {source}: {target} exists")
            left += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        inner = target / "logs"
        if target.parent.name == "logs" and inner.is_dir():           # a point's working folder: its logs flat
            for log in sorted(inner.iterdir()):
                if not (target / log.name).exists():
                    log.rename(target / log.name)
            if not any(inner.iterdir()):
                inner.rmdir()
    for rel in _configurations(work / "records"):
        _point_manifest(work, rel)
    logs = work / "logs"
    for folder in sorted((p for p in logs.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True) \
            if logs.is_dir() else ():
        if not any(folder.iterdir()):
            folder.rmdir()
    if logs.is_dir() and not any(logs.iterdir()):
        logs.rmdir()
    return left


def _point_manifest(work: Path, rel: Path) -> None:
    """A configuration's points.json with each point's results, products and working folder where V157 puts
    them (a path already there is left as it is)."""
    path = work / "records" / rel / "points.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    roots = {"results": (work / "results" / rel, work / "results" / rel / "points"),
             "output": (work / "logs" / rel, work / "records" / rel / "logs")}

    def moved(value: str, kind: str) -> str:
        old, new = roots[kind]
        try:
            tail = Path(value).relative_to(old)
        except ValueError:
            try:                                       # the manifest names the work dir as it was resolved
                tail = Path(value).resolve().relative_to(old.resolve())
            except (ValueError, OSError):
                return value
        if not tail.parts or tail.parts[0] in (RESULT_FOLDERS if kind == "results" else ("plots",)):
            return value
        return str(new / tail)

    for point in data.get("points", []):
        if isinstance(point.get("results"), str):
            point["results"] = moved(point["results"], "results")
        if isinstance(point.get("output"), str):
            point["output"] = moved(point["output"], "output")
        point["products"] = {k: moved(v, "results") if isinstance(v, str) else v for k, v in point.get("products", {}).items()}
    path.write_text(json.dumps(data, indent=1, default=str) + "\n", encoding="utf-8")


#: The backends' folders of results/<A>/<E>/<R>/plots/ before sets had folders of their own (V164).
OLD_BACKENDS = ("root", "mpl", "yoda")


def old_plots(work: Path) -> bool:
    """A configuration's pages still in results/<A>/<E>/<R>/plots/<backend>/, its numbers in plots/statistics*, or its
    page documents in records/<A>/<E>/<R>/plots/: from before V164."""
    results, records = work / "results", work / "records"
    for rel in _configurations(results):
        plots = results / rel / "plots"
        if any((plots / b).is_dir() for b in OLD_BACKENDS) or (plots / "statistics.csv").exists() or (plots / "statistics").is_dir():
            return True
    return any((records / rel / "plots").is_dir() for rel in _configurations(records))


def sets_moves(work: Path) -> list[tuple[Path, Path]]:
    """`heimdall migrate --layout` (V164): each configuration's pages into its totality set, its numbers out of
    plots/, the drawing's working files out of records/ (renames of whole folders and files):
    * results/<A>/<E>/<R>/plots/<backend>/<entry> → results/<A>/<E>/<R>/plots/totality/<backend>/<entry> (but the merged
      sweep, plots/root/<cfg>.root → .cache/<A>/plots/<name>/<cfg>/, beside its stamp);
    * results/<A>/<E>/<R>/plots/statistics.csv → results/<A>/<E>/<R>/statistics/totality/statistics.csv, the bar graphs of
      plots/statistics/<cell>/ → statistics/totality/bars/<cell>/, plots/statistics/summary.* →
      statistics/totality/;
    * records/<A>/<E>/<R>/plots/ → .cache/<A>/plots/<name>/<cfg>/ (the page documents, rebuilt by the next drawing);
    * a compare figure's: records/<A>/<E>/compare/<figure>/ → .cache/<A>/plots/<name>/compare/<figure>/, its
      statistics.csv and bar graphs into its statistics/."""
    records, results = work / "records", work / "results"
    moves: list[tuple[Path, Path]] = []

    def cache_of(rel: Path) -> Path:
        return work / ".cache" / rel.parts[0] / "plots" / Path(*rel.parts[1:])

    def numbers(old: Path, table: Path, into: Path) -> None:
        if table.is_file():
            moves.append((table, into / "statistics.csv"))
        if old.is_dir():
            for entry in sorted(old.iterdir()):
                if entry.name.startswith("summary."):
                    moves.append((entry, into / entry.name))
                elif entry.name != "bars" and entry.name != "statistics.csv":
                    moves.append((entry, into / "bars" / entry.name))

    for rel in _configurations(records):                       # first: the folder the merged sweep then joins
        if (records / rel / "plots").is_dir():
            moves.append((records / rel / "plots", cache_of(rel)))
    for rel in _configurations(results):
        plots = results / rel / "plots"
        for backend in OLD_BACKENDS:
            for entry in sorted((plots / backend).iterdir()) if (plots / backend).is_dir() else ():
                if backend == "root" and entry.suffix == ".root" and entry.is_file():
                    moves.append((entry, cache_of(rel) / entry.name))
                else:
                    moves.append((entry, plots / "totality" / backend / entry.name))
        numbers(plots / "statistics", plots / "statistics.csv", results / rel / "statistics" / "totality")
    for assignment in sorted(p for p in records.iterdir() if p.is_dir()) if records.is_dir() else ():
        for name in sorted(p for p in assignment.iterdir() if p.is_dir()):
            for figure in sorted((name / "compare").iterdir()) if (name / "compare").is_dir() else ():
                moves.append((figure, cache_of(figure.relative_to(records))))
    for assignment in sorted(p for p in results.iterdir() if p.is_dir()) if results.is_dir() else ():
        for name in sorted(p for p in assignment.iterdir() if p.is_dir()):
            for figure in sorted((name / "compare").iterdir()) if (name / "compare").is_dir() else ():
                if (figure / "statistics.csv").is_file():                      # the old layout's table beside its pages
                    old = figure / "statistics"
                    moves.append((figure / "statistics.csv", old / "statistics.csv"))
                    for entry in sorted(old.iterdir()) if old.is_dir() else ():
                        if entry.is_dir() and entry.name != "bars":
                            moves.append((entry, old / "bars" / entry.name))
    return moves


def apply_sets(moves: list[tuple[Path, Path]], work: Path) -> int:
    """sets_moves made (renames); a move whose target exists is left, and named; emptied folders removed.
    Returns the moves left."""
    left = 0
    emptied = set()
    for source, target in moves:
        if target.exists() or target.is_symlink():
            print(f"left    {source}: {target} exists")
            left += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        emptied.add(source.parent)
    for folder in sorted(emptied, key=lambda p: len(p.parts), reverse=True):
        while folder.is_dir() and not any(folder.iterdir()) and folder != work:
            folder.rmdir()
            folder = folder.parent
    return left


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
        first = formerly_text(defaults_text(cfgs_text(config_text(figure_text(placeholder_text(backend_text(errand_text(text))))))))
        given = configmod.load(name, strict=False, text=first)          # the tables its imports give, too
        first = exports_text(first, {tag: tool.tool for tag, tool in given.tools.items()})
        errand = configmod.load(name, strict=False, text=first)
        new = toml_text(first, errand, errand.assignment)
        if v3:
            new = v3_text(new)
        if new != text:
            changes[errand.path] = (text, new)
        cards: dict[Path, object] = {}
        for tool in errand.tools.values():                 # each base card, by its folder's rules (no planning)
            folder = tools.folders().get(tool.tool)
            for base in tool.baseconfig if folder is not None else ():
                try:
                    path = resolve(base, "baseconfig", assignment=errand.assignment, folder=errand.folder, where=f"[tools.{tool.tag}].baseconfig")
                except HeimdallError:
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


# ── record files and their format ─────────────────────────────────────────────────────────────

_RECORD_FILES = (("records", "points.json"), ("records", "provenance.json"), ("records", "identity.json"), ("results", "plot.toml"))


def format_files(scope: str = "") -> list[tuple[Path, str]]:
    """The record files below the current format, under records/ and results/ (all, or `<A>[/<E>[/<R>]]`): (file,
    what upgrading does). A file of a newer format is not listed: a newer Heimdall wrote it."""
    from .paths import records_root, results_root
    from .record import FORMAT
    roots = {"records": records_root(), "results": results_root()}
    found: list[tuple[Path, str]] = []
    for root, name in _RECORD_FILES:
        base = roots[root] / scope if scope else roots[root]
        for path in sorted(base.rglob(name)) if base.is_dir() else ():
            try:
                if name.endswith(".json"):
                    data = json.loads(path.read_text(encoding="utf-8"))
                    have = data.get("format", 0) if isinstance(data, dict) else None
                else:
                    have = tomllib.loads(path.read_text(encoding="utf-8")).get("source", {}).get("format", 0)
            except (OSError, ValueError):
                found.append((path, "unreadable: left as it is"))
                continue
            if have is None:
                found.append((path, "not a table: left as it is"))
            elif isinstance(have, int) and have < FORMAT:
                found.append((path, f"add format = {FORMAT}" + (f" (it is {have})" if have else "")))
    return found


def upgrade_file(path: Path) -> bool:
    """One record file to the current format, a copy of it beside it first (`<name>.bak`, the first of
    `.bak`, `.bak2`, …); False when it was left (unreadable, or no [source] to hold the key)."""
    from .record import FORMAT, write_atomic
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(text)
        data = {"format": FORMAT, **{k: v for k, v in data.items() if k != "format"}}
        new = json.dumps(data, indent=1, sort_keys=path.name == "identity.json", default=str) + "\n"
    else:
        lines = text.splitlines(keepends=True)
        at = next((i for i, line in enumerate(lines) if re.match(r"^\[source\]\s*(#.*)?$", line)), None)
        if at is None:
            return False
        end = next((i for i in range(at + 1, len(lines)) if _TABLE.match(lines[i].rstrip("\n"))), len(lines))
        own = next((i for i in range(at + 1, end) if re.match(r"^format\s*=", lines[i])), None)
        if own is None:
            lines.insert(at + 1, f"format = {FORMAT}\n")
        else:
            lines[own] = f"format = {FORMAT}\n"
        new = "".join(lines)
        tomllib.loads(new)
    copy = path.with_name(path.name + ".bak")
    n = 1
    while copy.exists():
        n += 1
        copy = path.with_name(f"{path.name}.bak{n}")
    shutil.copy2(path, copy)
    write_atomic(path, new)
    return True


# ── a work dir's uses of Heimdall's old names ─────────────────────────────────────────────

#: A work dir's marker before the heimdall names.
OLD_MARKER = "hep.toml"
#: The names that moved (hep → heimdall), as a work dir's files use them: its configs' placeholders and comments,
#: its modules' imports and environment, its Makefile, its editor settings, Whizard's directive.
NAME_RULES = [(re.compile(a, re.M), b) for a, b in (
    (r"\{hep\}", "{heimdall}"),
    (r"(?<![A-Za-z0-9])_HEP_", "_HEIMDALL_"),
    (r"\bHEP_", "HEIMDALL_"),
    (r"\$HEP\b", "$HEIMDALL"),
    (r"\$\{HEP(?=[}:\-?+=#%])", "${HEIMDALL"),
    (r"\$\(HEP\)", "$(HEIMDALL)"),
    (r"\bifndef HEP\b", "ifndef HEIMDALL"),
    (r"\bHEP is not set\b", "HEIMDALL is not set"),
    (r"""(environ(?:\.get)?\(|environ\[|getenv\()(["'])HEP\2""", r"\1\2HEIMDALL\2"),
    (r"\bhepkit\b", "heimdallkit"),
    (r"\bHepError\b", "HeimdallError"),
    (r"\bhep_root\b", "heimdall_root"),
    (r"\bhep_env\.sh\b", "heimdall_env.sh"),
    (r"\bhep\.toml\b", "heimdall.toml"),
    (r"^(\s*#\s*)hep:", r"\1heimdall:"),
    (r"\bHEP Contrast", "Heimdall Contrast"),
    (r"\bHEP Icons\b", "Heimdall Icons"),
    (r"\bhep-(contrast|icons)\b", r"heimdall-\1"),
    (r"\b(heimdall|hep) where --hep\b", "heimdall where --heimdall"),
    (r"\bhep (where|setup|run|plot|stats|status|check|build|ls|explain|migrate|report|watch|clean|overlay)\b", r"heimdall \1"),
)]
#: Where a work dir's files use Heimdall's names: its top-level files (the marker, Makefile, CLAUDE.md, HEIMDALL.md,
#: README.md), its editor settings, its configs and modules. Anything else (notes, analyses) may mean another HEP.
SOURCES = (".vscode", "configs", "modules")
NOT_SOURCES = {".git", "results", "records", ".cache", "build", "reports", "datasets", "node_modules", "__pycache__"}
SOURCE_LIMIT = 2_000_000


def old_marker(start: Path | None = None) -> Path | None:
    """The folder holding a marker from before the heimdall names (hep.toml with a [work] table), here or above; None."""
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        marker = folder / OLD_MARKER
        if marker.is_file():
            try:
                if isinstance(tomllib.loads(marker.read_text(encoding="utf-8")).get("work"), dict):
                    return folder
            except (OSError, tomllib.TOMLDecodeError):
                return None
    return None


def _sources(work: Path) -> list[Path]:
    out = []
    for path in sorted(work.rglob("*")):
        rel = path.relative_to(work)
        if any(part in NOT_SOURCES for part in rel.parts) or not path.is_file() or path.is_symlink():
            continue
        if len(rel.parts) > 1 and rel.parts[0] not in SOURCES and path.suffix != ".code-workspace":
            continue
        if path.stat().st_size > SOURCE_LIMIT:
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        out.append(path)
    return out


def names_changes(work: Path) -> dict[Path, tuple[str, str]]:
    """Each of a work dir's own text files that uses Heimdall's old names (its top-level files, .vscode/, configs/,
    modules/ and any *.code-workspace; never results/, records/, .cache/, build/, reports/, datasets/), before
    and after NAME_RULES."""
    changes = {}
    for path in _sources(work):
        old = path.read_text(encoding="utf-8")
        new = old
        for pattern, repl in NAME_RULES:
            new = pattern.sub(repl, new)
        if new != old:
            changes[path] = (old, new)
    return changes



# ── the result levels' names, <Assignment>/<Errand>/<Run> ────────────────────────────────

#: A table header, or one commented out: `[run]`, `[run.cfgs.pdf]`, `# [[run.x]]` (the `run` at group 3).
_OLD_HEADER = re.compile(r"^(\s*(?:#+\s*)?)(\[\[?\s*)run(\s*[.\]])")
#: `[run]`, `[run.…]` anywhere else: a comment's, a string's.
_OLD_TABLE = re.compile(r"\[run(?=[.\]])")
#: A key `project` (or `run`, [source]'s), its `=` column: (indent, key, spaces, rest).
_KEY_PAD = re.compile(r"^(\s*)([A-Za-z_]+)(\s*)(=.*)$", re.S)
#: Dotted names on command lines and in prose, any file: `--set run.x=`, `heimdall explain run.x`.
SET_RULES = [(re.compile(a), b) for a, b in (
    (r"""(--set(?:=|\s+)["']?)run\.project\b""", r"\1errand.assignment"),
    (r"""(\bexplain\s+["']?)run\.project\b""", r"\1errand.assignment"),
    (r"""(--set(?:=|\s+)["']?)run\.""", r"\1errand."),
    (r"""(\bexplain\s+["']?)run\.""", r"\1errand."),
    (r"""(\bexplain\s+["']?)\[run\]""", r"\1[errand]"),
)]
#: A dotted name in an import's `only` or `drop`: `"run.cfgs.x"` → `"errand.cfgs.x"`, `"run"` → `"errand"`.
_DOTTED_NAME = re.compile(r"""(["'])run(?=[."'])""")
_DOTTED_PROJECT = re.compile(r"""(["'])errand\.project(?=["'])""")
#: A root key `run.x = …` however spelt (`run . x`, `"run".x`, `run."pt-50".x`): (indent, the rest from its dot).
_ROOT_RUN = re.compile(r"""^(\s*)(?:run|"run"|'run')\s*(\..*=.*)$""")
#: `config.import = …` (`only`, `drop`; `file.` in a v3 file) at the root: (indent, its key and `=`, the key, the value).
_ROOT_LIST = re.compile(r"^(\s*)((?:config|file)\.(only|drop|import)\s*=\s*)(.*)$")
#: A report title's placeholders ([source]'s keys).
PLACEHOLDER_RULES = ((re.compile(r"\{project\}"), "{assignment}"), (re.compile(r"\{run\}"), "{errand}"))


def _header(line: str) -> str:
    """A table header (or a commented one) in today's names, a comment after it in its column when it can be."""
    new = _OLD_HEADER.sub(r"\1\2errand\3", line)
    if new != line and (tail := re.match(r"^(.*?\]\]?)( +)(#.*)$", new)):
        new = tail[1] + " " * max(1, len(tail[2]) - len("errand") + len("run")) + tail[3]
    return new


def _renamed_key(line: str, new: str) -> str:
    """`key   = value` with its key `new`, its `=` where it was when the spaces allow."""
    match = _KEY_PAD.match(line)
    pad = len(match[3]) - (len(new) - len(match[2]))
    return f"{match[1]}{new}{' ' * max(1, pad) if match[3] else ''}{match[4]}"


def _comment_of(line: str) -> tuple[str, str]:
    """A TOML line as its code and its comment (from an unquoted `#`; the whole line when it is one)."""
    quote, i = "", 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == "#":
            return line[:i], line[i:]
        i += 1
    return line, ""


def _only_names(text: str, key: str) -> str:
    """Dotted names in today's: a drop's or only's whole value; an import's only its `only = [ … ]` (its `from` is
    a file's name, left as it is)."""
    def renamed(names: str) -> str:
        return _DOTTED_PROJECT.sub(r"\1errand.assignment", _DOTTED_NAME.sub(r"\1errand", names))
    if key != "import":
        return renamed(text)
    return re.sub(r"(\bonly\s*=\s*\[)([^\]]*)", lambda m: m[1] + renamed(m[2]), text)


def errand_text(text: str) -> str:
    """A config's text in today's names (by line, so comments and layout stay): `[run]` → `[errand]` and every
    `[run.…]` → `[errand.…]` (its headers, commented ones too, and where a comment names them), `[run].project` →
    `[errand].assignment` (its key, the `=` column kept), dotted names (a root's `run.x = …`, an import's `only`
    and `drop`, `--set run.x=`, `heimdall explain run.x`), a report title's `{project}` and `{run}`. Idempotent."""
    out: list[str] = []
    table = ""
    depth, listing, multi = 0, "", None    # a value spread over lines: the brackets it leaves open, its key; a """ string
    inside_only = False
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\n")
        end = line[len(bare):]
        line = bare
        comment = line.lstrip().startswith("#")
        value = None
        if multi:
            multi = None if line.count(multi) % 2 else multi
        elif depth > 0:
            if listing == "import" and inside_only:                       # an only = [ … ] over lines
                line = _only_names(line, "only")
            elif listing:
                line = _only_names(line, listing)
            if listing == "import":
                opened = re.search(r"\bonly\s*=\s*\[[^\]]*$", line.split("#", 1)[0])
                inside_only = bool(opened) or (inside_only and "]" not in line.split("#", 1)[0])
            depth = max(0, depth + _depth(line))
            listing = listing if depth else ""
        elif comment:
            line = _header(line)
        elif _TABLE.match(line):
            line = _header(line)
            table = _TABLE.match(line)[1].strip()
        elif table == "" and (dotted := _ROOT_LIST.match(line)):                        # config.import = … at the root
            line, value, listing = dotted[1] + dotted[2] + _only_names(dotted[4], dotted[3]), dotted[4], dotted[3]
            inside_only = bool(re.search(r"\bonly\s*=\s*\[[^\]]*$", dotted[4].split("#", 1)[0]))
        elif table == "" and (dotted := _ROOT_RUN.match(line)):                         # run.x = … at the root
            rest = dotted[2]
            rest = ".assignment" + rest[len(".project"):] if re.match(r"\.project\s*=", rest) else rest
            line, value = f"{dotted[1]}errand{rest}", rest.split("=", 1)[1]
        elif (key := _KEY.match(line)):
            name, value = key[2].strip('"'), key[4]
            if table == "errand" and name == "project":
                line = _renamed_key(line, "assignment")
            elif table == "" and name == "run" and value.lstrip().startswith("{"):          # run = { … }, inline
                line = key[1] + "errand" + line[len(key[1]) + len(key[2]):]
                line = re.sub(r"(\{\s*|,\s*)project(\s*=)", r"\1assignment\2", line)
            elif table in ("config", "file") and name in ("only", "drop", "import"):
                line = key[1] + key[2] + key[3] + _only_names(value, name)
                listing = name
                inside_only = name == "import" and bool(re.search(r"\bonly\s*=\s*\[[^\]]*$", value.split("#", 1)[0]))
            elif table in ("config.import", "file.import") and name == "only":             # [[config.import]] only = …
                line = key[1] + key[2] + key[3] + _only_names(value, name)
                listing = name
            elif table.startswith("report") and name in ("title", "subtitle"):
                for pattern, repl in PLACEHOLDER_RULES:
                    line = pattern.sub(repl, line)
        if value is not None:
            multi = next((q for q in ('"""', "'''") if value.count(q) % 2), None)
            depth = 0 if multi else max(0, _depth(value))
            listing = listing if depth else ""
        code, note = _comment_of(line)          # the prose rules touch a comment only, never a value (it may be hashed)
        if note:
            had = note
            note = _OLD_TABLE.sub("[errand", note).replace("[errand].project", "[errand].assignment")
            note = re.sub(r"\b([Aa]) (`?)\[errand", r"\1n \2[errand", note) if note != had else note   # "a [run]" → "an [errand]"
            for pattern, repl in SET_RULES:
                note = pattern.sub(repl, note)
            line = code + note
        if out and re.search(r"--set\s*$", out[-1]):         # `--set` at a comment's line end, its key on the next
            line = re.sub(r"^(\s*#\s*[`'\"]?)run\.", r"\1errand.", line)
        out.append(line + end)
    return "".join(out)


def source_text(text: str) -> str:
    """A plot document's text in today's names: [source].project → assignment, [source].run → errand. Idempotent."""
    out, table = [], ""
    for line in text.splitlines(keepends=True):
        header = _TABLE.match(line)
        if header:
            table = header[1].strip()
        elif table == "source" and (key := _KEY.match(line.rstrip("\n"))) and key[2] in OLD_SOURCE_KEYS:
            line = _renamed_key(line, OLD_SOURCE_KEYS[key[2]])
        out.append(line)
    return "".join(out)


#: [source]'s keys before the Assignment/Errand names (plotdoc.OLD_SOURCE, a higher rank's) → today's.
OLD_SOURCE_KEYS = {"project": "assignment", "run": "errand"}


def snapshot_text(text: str, digests: dict[str, str]) -> str:
    """A record's snapshot.toml after its files were rewritten: each file's sha256 (`digests`: its path → the new
    one) and its --set overrides in today's names; its comment kept."""
    data = tomllib.loads(text)
    snap, files = data.get("snapshot", {}), data.get("files", {})
    sets = [_set_name(s) for s in snap.get("sets", [])]
    changed = {k: v for k, v in digests.items() if k in files and files[k] != v}
    if sets == snap.get("sets", []) and not changed:
        return text
    snap["sets"] = sets
    files.update(changed)
    head = "".join(l for l in text.splitlines(keepends=True)[:1] if l.startswith("#"))
    return head + tomli_w.dumps(data)


def _set_name(item: str) -> str:
    """One --set override in today's names: run.x=… → errand.x=…"""
    if not isinstance(item, str) or not item.startswith("run."):
        return item
    rest = item[len("run."):]
    return "errand.assignment" + rest[len("project"):] if re.match(r"project\s*=", rest) else "errand." + rest


def provenance_text(text: str) -> str:
    """A point's provenance.json with its --set overrides (`sets`, what reproduces it) in today's names, its layout
    kept: each old override's JSON string replaced in place."""
    try:
        sets = json.loads(text).get("sets", [])
    except (json.JSONDecodeError, AttributeError):
        return text
    for item in sets:
        if _set_name(item) != item:
            text = text.replace(json.dumps(item, ensure_ascii=False), json.dumps(_set_name(item), ensure_ascii=False), 1)
            text = text.replace(json.dumps(item), json.dumps(_set_name(item)), 1)
    return text


def errand_changes(work: Path, changes: dict[Path, tuple[str, str]] | None = None) -> dict[Path, tuple[str, str]]:
    """Each of a work dir's files the Assignment/Errand names change: its configs (configs/**/*.toml, errand_text), its records'
    snapshots (records/**/config/: the configs, snapshot.toml's digests and --set overrides) and points' provenance
    (its --set overrides), its plot documents (results/**/plot.toml, source_text) and folders' report.toml (their
    title's placeholders); --set and explain lines in its own sources (_sources; never modules/, whose source is
    its programs' identity). Before and after, added to
    `changes` (names_changes', which a file's text then starts from)."""
    changes = {} if changes is None else changes

    def put(path: Path, new_of) -> None:
        try:
            old = changes[path][0] if path in changes else path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        now = changes[path][1] if path in changes else old
        new = new_of(now)
        if new != old:
            changes[path] = (old, new)
        else:
            changes.pop(path, None)

    def lines_of(text: str) -> str:
        for pattern, repl in SET_RULES:
            text = pattern.sub(repl, text)
        return text

    for path in _sources(work):
        if path.is_relative_to(work / "modules"):          # a module's source is its programs' identity: left
            continue
        if path.is_relative_to(work / "configs") and path.suffix not in (".toml", ".md", ".sh", ".txt"):
            continue                                       # a base card: its bytes are its points' identity
        put(path, errand_text if path.suffix == ".toml" and path.is_relative_to(work / "configs") else lines_of)
    records = work / "records"
    for snapshot in sorted(records.glob("*/*/*/config/snapshot.toml")) if records.is_dir() else ():
        folder, digests = snapshot.parent, {}
        for path in sorted(folder.rglob("*.toml")):
            if path == snapshot or path.is_symlink():
                continue
            put(path, errand_text)
            if path in changes:
                digests[str(path.relative_to(folder))] = hashlib.sha256(changes[path][1].encode("utf-8")).hexdigest()
        put(snapshot, lambda text: snapshot_text(text, digests))
    for provenance in sorted(records.glob("*/*/*/points/*/provenance.json")) if records.is_dir() else ():
        put(provenance, provenance_text)
    results = work / "results"
    for document in sorted(results.rglob("plot.toml")) if results.is_dir() else ():
        put(document, source_text)
    for recipe in sorted(results.rglob("report.toml")) if results.is_dir() else ():
        put(recipe, errand_text)
    return changes


# ── heimdall library adopt (points-library P5) ──────────────────────────────────────────────────────

DUPLICATE = ".adopted-duplicate"


def adopt_points(run: str, apply: bool = False) -> list[str]:
    """`heimdall library adopt <A>/<E>/<R> [--yes]`: a Run's complete generation points (those its points.json lists, whose
    `.complete` is the hash of their recorded `identity.json`) moved into the Assignment's points library under their keys, and
    linked back as a Run that used the library has them: a reorganisation, nothing is run. A point whose key is already complete
    in the library is linked to that entry, and its own folders are kept beside the link as `<name>.adopted-duplicate`
    (`heimdall library prune --duplicates` removes them). Without `apply` it says what it would do. The Run's points.json gets
    `library` and the key as `identity` for each adopted point; a plot document of the Run still names the old identities and is
    drawn "as recorded" until it is written again."""
    import hashlib
    import shutil
    from . import record
    from .paths import records_root, results_root
    parts_ = [p for p in run.strip("/").split("/") if p]
    if len(parts_) != 3:
        raise HeimdallError(f"'{run}' is not a Run", hint="a Run is <A>/<E>/<R> (heimdall runs names them)")
    assignment = parts_[0]
    here, products = records_root() / Path(*parts_), results_root() / Path(*parts_)
    manifest_path = here / "points.json"
    if not manifest_path.is_file():
        raise HeimdallError(f"no points.json in {run}: adopt reads which points it ran", where=str(manifest_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    library_records, library_results = records_root() / assignment / record.LIBRARY, results_root() / assignment / record.LIBRARY
    out: list[str] = []
    changed = False
    verb = "" if apply else "would "
    for entry in manifest.get("points", []):
        name = entry.get("name", "")
        folder, results = here / "points" / name, products / "points" / name
        if folder.is_symlink():
            out.append(f"{name}: already in the library")
            continue
        try:
            parts = json.loads((folder / "identity.json").read_text(encoding="utf-8"))
            marker = (folder / ".complete").read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            out.append(f"{name}: left (no recorded identity or not complete)")
            continue
        recorded = {k: v for k, v in parts.items() if k != "format"}
        if hashlib.sha256(json.dumps(recorded, sort_keys=True, default=str).encode("utf-8")).hexdigest() != marker:
            out.append(f"{name}: left (its .complete is not the hash of its identity.json)")
            continue
        if not results.is_dir():
            out.append(f"{name}: left (no products folder {results})")
            continue
        key = record.library_key_of_recorded(parts)
        entry_rec, entry_res = library_records / key[:16], library_results / key[:16]
        shared = (entry_rec / ".complete").is_file() and (entry_rec / ".complete").read_text(encoding="utf-8").strip() == key
        if not shared and (entry_rec.exists() or entry_res.exists()):
            out.append(f"{name}: left (the library has an unfinished entry {key[:16]}: prune it, or finish it)")
            continue
        out.append(f"{verb}{'link ' + name + ' to the library entry ' + key[:16] + ' (its own folders kept as ' + name + DUPLICATE + ')' if shared else 'move ' + name + ' into the library as ' + key[:16]}")
        if not apply:
            continue
        if shared:
            folder.rename(folder.with_name(name + DUPLICATE))
            results.rename(results.with_name(name + DUPLICATE))
        else:
            entry_rec.parent.mkdir(parents=True, exist_ok=True)
            entry_res.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder), str(entry_rec))
            shutil.move(str(results), str(entry_res))
            record.write_atomic(entry_rec / ".complete", key + "\n")
        record.link_into(folder, entry_rec)
        record.link_into(results, entry_res)
        prov = {}
        try:
            prov = json.loads((entry_rec / "provenance.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        line = {"key": key, "run": run.strip("/"), "kind": "used" if shared else "created"}
        if not shared:
            line.update({"coordinates": {q: v.get("tag") for q, v in entry.get("values", {}).items()},
                         "events": prov.get("events"), "threads": prov.get("threads"), "seed": prov.get("seed")})
        record.index_append(assignment, line)
        entry["library"], entry["identity"] = key[:16], key
        changed = True
    if apply and changed:
        record.write_atomic(manifest_path, json.dumps(manifest, indent=1, default=str) + "\n")
    if not apply:
        out.append("a dry run: --yes makes these moves")
    return out
