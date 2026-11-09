"""A tool's card as entries, merged and written as the final config the tool reads (doc:tool-contract).

A card is parsed by its folder's grammar (`[card] line`, `comment`, `drop`, `trailing`,
`drop_inside_braces`) into entries; comments are dropped, after the directives they carry are read.
Sources merge by priority, the last given winning (a base, a later base, the point, the runner), and
the final config is written in the folder's `[card] order`:

- `free`: the settings commute. The `leading` keys come first (they reset others when read: Pythia's
  tunes), then every other setting sorted by key, then each `group` (a particle's commands) in written
  order. A setting twice in one source is refused.
- `sequential`: a script, whose commands run in order. Each source's lines are kept as written, except
  a source marked `sort`, whose lines (the point's own `set` lines, one per key) are sorted.

It knows no tool: what differs between tools is the `[card]` table it is handed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .errors import HeimdallError

ORDERS = ("free", "sequential")


@dataclass(frozen=True)
class Entry:
    """A line of a card. `key` is "" for a command that sets nothing (`cd …`, `module … {`)."""
    key: str
    value: str
    origin: str                                  # `ep.cmnd:12`, `[tools.pythia].settings`, `built-in events`, …
    line: str                                    # as the tool reads it

    @property
    def normal(self) -> str:
        return normal(self.key)


@dataclass(frozen=True)
class Source:
    """A card's entries from one place. `sort`: its lines commute, so a sequential card sorts them."""
    entries: tuple[Entry, ...]
    sort: bool = False


@dataclass
class Merged:
    """The winners in the order they are read, and what each winner overrode (key → the losers)."""
    entries: list[Entry]
    overrode: dict[str, list[Entry]] = field(default_factory=dict)


def normal(key: str) -> str:
    return "".join(key.split()).lower()


def grammar(rules: dict):
    """A function line → (key, value) or None, from `[card] line` (V59): "{key} = {value}" reads
    `PDF:pSet = 13` and `PDF:pSet=13`, "set {key} {value}" reads `set X:Y 1`. The template that writes a line
    reads it."""
    pieces = [p for p in re.split(r"(\{key\}|\{value\}|\s+)", rules.get("line", "{key} = {value}")) if p]
    pattern = ""
    for i, piece in enumerate(pieces):
        if piece == "{key}":
            pattern += r"(?P<key>[^\s=]+)"
        elif piece == "{value}":
            pattern += r"(?P<value>.*?)"
        elif piece.isspace():                    # optional beside punctuation (`a=1`), needed between words (`set a 1`)
            beside = [q for q in pieces[max(i - 1, 0):i + 2:2] if not q.startswith("{")]
            pattern += r"\s*" if any(not re.search(r"\w", q) for q in beside) else r"\s+"
        else:
            pattern += re.escape(piece)
    regex = re.compile(r"^\s*" + pattern + r"\s*$")

    def parse(line: str):
        match = regex.match(line)
        return (match["key"], match["value"].strip()) if match else None
    return parse


def cleaned(text: str, rules: dict):
    """(line number, line) of a card's commands: no blank lines or comments (V54). `drop` is a full-line
    comment (a regex), `trailing` a comment after a value; `drop_inside_braces = false` keeps
    comment-looking lines inside { … } (Tcl: there they can be list elements)."""
    comment = rules.get("comment", "#")
    drop = re.compile(rules.get("drop", r"^\s*" + re.escape(comment)))
    trailing = re.compile(rules["trailing"]) if rules.get("trailing") else None
    inside = rules.get("drop_inside_braces", True)
    depth = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.strip() and not ((inside or depth == 0) and drop.match(line)):
            yield number, trailing.sub("", line) if trailing else line
        depth = max(0, depth + line.count("{") - line.count("}"))


def directives(text: str, rules: dict, origin: str) -> dict[str, tuple[str, str]]:
    """What a card's comments tell the runner (`[card] directives`, a regex with a name and a value
    group: Whizard's `# heimdall: beam_structure = …`): name → (value, origin). Read before the
    comments go. A name given twice is refused, as a setting is."""
    pattern = rules.get("directives")
    found: dict[str, tuple[str, str]] = {}
    for number, line in enumerate(text.splitlines(), start=1) if pattern else ():
        match = re.match(pattern, line)
        if match is None:
            continue
        name, value = match.group(1), match.group(2).strip()
        if name in found:
            raise HeimdallError(f"the directive '{name}' is given twice", where=f"{found[name][1]} and {origin}:{number}",
                                hint="keep one")
        found[name] = (value, f"{origin}:{number}")
    return found


def parse(text: str, rules: dict, origin: str) -> Source:
    """A base card's entries, comments and blank lines gone; `origin` names the file (`ep.cmnd`)."""
    read = grammar(rules)
    entries = []
    for number, line in cleaned(text, rules):
        parsed = read(line)
        key, value = parsed if parsed else ("", "")
        entries.append(Entry(key, value, f"{origin}:{number}", line.strip()))
    return Source(tuple(entries))


def given(lines: list[str], rules: dict, origin: str) -> Source:
    """Lines the runner writes (the footer, the seeds), each read by the grammar and all from `origin`."""
    read = grammar(rules)
    return Source(tuple(Entry(*(read(line) or ("", "")), origin, line.strip()) for line in lines if line.strip()))


def setting(key: str, value: str, origin: str, rules: dict) -> Entry:
    """An entry the runner writes (a quantity, a setting, a built-in), in the folder's `[card] line`."""
    line = rules.get("line", "{key} = {value}").replace("{key}", key).replace("{value}", value)
    return Entry(key, value, origin, line)


def _repeatable(entry: Entry, rules: dict) -> bool:
    """`[card] repeatable`: commands that add up rather than replace (23:onIfMatch), by their last part."""
    return entry.normal.rpartition(":")[2] in {r.lower() for r in rules.get("repeatable", [])}


def _order(rules: dict) -> str:
    order = rules.get("order", "sequential")
    if order not in ORDERS:
        raise HeimdallError(f"[card] order = '{order}' is not one of {', '.join(ORDERS)}", where="tool.toml [card].order")
    return order


def merge(sources: list[Source], rules: dict) -> Merged:
    """The sources as one card, the last source given winning (doc:tool-contract). A `free` card holds
    each setting once: one set twice in one source is refused, naming both lines, and across sources
    the later one's value replaces the earlier one's, which is kept in `overrode`. A repeatable command
    is kept every time. A `sequential` card is a script: nothing replaces anything, since a later `set`
    is read later; a source marked `sort` is sorted."""
    if _order(rules) == "sequential":
        return Merged([entry for source in sources
                       for entry in (sorted(source.entries, key=lambda e: (e.normal, e.value)) if source.sort else source.entries)])
    winners: dict[str, Entry] = {}
    overrode: dict[str, list[Entry]] = {}
    kept: list[Entry] = []
    for source in sources:
        seen: dict[str, Entry] = {}
        for entry in source.entries:
            if not entry.key:
                raise HeimdallError(f"'{entry.line}' is not a setting", where=entry.origin,
                                    hint=f"a {rules.get('line', '{key} = {value}')} line, or a comment")
            if _repeatable(entry, rules):
                kept.append(entry)
                continue
            if entry.normal in seen:
                raise HeimdallError(f"'{entry.key}' is set twice in one card", where=f"{seen[entry.normal].origin} and {entry.origin}",
                                    hint="keep one: the tool reads one value of it")
            seen[entry.normal] = entry
            if entry.normal in winners:
                overrode.setdefault(entry.normal, []).append(winners[entry.normal])
                kept.remove(winners[entry.normal])
            winners[entry.normal] = entry
            kept.append(entry)
    return Merged(kept, overrode)


def _group_of(entry: Entry, rules: dict):
    """`[card] group`, a regex on the key whose first group names a set of commands read in order
    (Pythia's particle data, `23:…`): the name, sorted as a number when it is one, else None."""
    pattern = rules.get("group")
    match = re.match(pattern, entry.normal) if pattern else None
    if match is None:
        return None
    name = match.group(1)
    return (0, int(name), "") if re.fullmatch(r"-?\d+", name) else (1, 0, name)


def final(merged: Merged, rules: dict) -> list[Entry]:
    """The final config's entries in the order the tool reads them, in the folder's `[card] order`. A free
    card's lines are made again from the template, so its layout is the folder's, not the writer's; a
    sequential card's are its lines as merge ordered them."""
    if _order(rules) == "sequential":
        return list(merged.entries)
    leading = [normal(k) for k in rules.get("leading", [])]
    first, free, groups = [], [], {}
    for entry in merged.entries:
        group = _group_of(entry, rules)
        if entry.normal in leading:
            first.append(entry)
        elif group is not None:
            groups.setdefault(group, []).append(entry)
        else:
            free.append(entry)
    first.sort(key=lambda e: leading.index(e.normal))
    free.sort(key=lambda e: (e.normal, e.value))
    return [setting(e.key, e.value, e.origin, rules) for e in first + free + [e for name in sorted(groups) for e in groups[name]]]


def write(merged: Merged, rules: dict) -> list[str]:
    """The final config's lines: no comments, no blank lines."""
    return [entry.line for entry in final(merged, rules)]


def sidecar(merged: Merged) -> dict[str, dict]:
    """`cards/<tag>.json`: each setting's value, where it comes from, and what it overrode. A command
    kept every time it is written (23:onIfMatch) is `<key> #2`, `#3` … after its first."""
    out: dict[str, dict] = {}
    for entry in merged.entries:
        if not entry.key:
            continue
        name, n = entry.key, 1
        while name in out:
            n += 1
            name = f"{entry.key} #{n}"
        row = {"value": entry.value, "from": entry.origin}
        if merged.overrode.get(entry.normal) and n == 1:
            row["overrode"] = [{"value": e.value, "from": e.origin} for e in merged.overrode[entry.normal]]
        out[name] = row
    return out


def load_tree(text: str, origin: str):
    """A YAML card (Sherpa) as data, a key given twice in one mapping refused (yaml would keep the last)."""
    import yaml                                  # only a tree folder needs it

    class Loader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        seen: dict = {}
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                raise HeimdallError(f"'{key}' is set twice in one card", where=f"{origin}:{seen[key]} and {origin}:{key_node.start_mark.line + 1}",
                                    hint="keep one: the tool reads one value of it")
            seen[key] = key_node.start_mark.line + 1
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        return yaml.load(text, Loader=Loader)
    except yaml.YAMLError as error:
        raise HeimdallError(f"not YAML: {error}", where=origin) from None


def dump_tree(data) -> str:
    """A YAML card's final config: mappings by sorted key, lists in their order (their order is meaning)."""
    import yaml
    return yaml.safe_dump(data, sort_keys=True, default_flow_style=None, width=100)
