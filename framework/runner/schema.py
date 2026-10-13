"""The run TOML's schema: framework/schema/run.toml, and checking a table against it (rank 0). A deck's
recipe has its own, framework/schema/deck.toml (tables "deck" and "block", V103).

docs/04_Config_Reference.md. Every key's type, allowed values, smallest value, default, inheritance and
whether it takes "default" is written once, in run.toml (V55); config.py and plot.py check their tables
here, and the editor schema (`make schema`) and the reference's key lists come from the same file.

"default" means "keep it as it is": the layer below's value, as if the key were absent. Only a key whose
entry says `default_ok` takes it. In a v2 file, [plot]'s own "default" sets nothing, and the drawing tool
decides; v3 gives that its own word, "native" (03 §6: "default" has one meaning), which a page key
(`native_ok`: marked `page` and `default_ok`) takes at any level.
"""

from __future__ import annotations

import functools
import json
import re
import tomllib
from pathlib import Path
from typing import Any

from .errors import HepError, did_you_mean
from .paths import hep_root

DEFAULT = "default"
NATIVE = "native"           # a page key: what the drawing tool does by itself (v2: [plot]'s own "default")
TYPES = {"int": int, "float": (int, float), "str": str, "bool": bool, "list": list, "table": dict}
NAMES = {"int": "an integer", "float": "a number", "str": "a string", "bool": "true or false", "list": "a list",
         "table": "a table"}
#: The tables of run.toml that describe keys (the rest, [sections], describe the file).
TABLES = ("config", "run", "configuration", "prelim", "quantity", "tool", "plot", "figure", "data", "cluster")
#: The tables of deck.toml, a deck's recipe (reports/<name>/deck.toml, V103).
DECK_TABLES = ("deck", "block")
#: A figure's own keys: the rest are what it sets for its pages.
FIGURE_OWN = ("class", "type", "name", "objects", "labels", "over", "configurations", "op", "x", "y", "pages", "columns")


def path(name: str = "run") -> Path:
    return hep_root() / "framework" / "schema" / f"{name}.toml"


@functools.cache
def spec(name: str = "run") -> dict:
    try:
        return tomllib.loads(path(name).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HepError(f"cannot read the schema: {error}", where=str(path(name))) from None


#: Configuration keys [run] gives every configuration (V99; they were [run.defaults]'s), besides the
#: ones the schema marks `inherit` in [run] itself.
RUN_GIVES = ("tools", "sweeps", "plot_points", "combine", "pre", "post", "generate_cards")


#: How a table is named in an error that sends a key to it.
HOMES = {"run": "[run] (or a configuration)", "configuration": "a configuration ([cfgs.<name>], v2's [run.cfgs.<name>])",
         "quantity": "[quantities.<q>]", "tool": "[tools.<tag>]", "plot": "[plot]", "figure": "a figure ([plot.figures.<f>])",
         "data": "[plot.data]", "cluster": "[cluster]", "config": "[file] (v2's [config])", "prelim": "[prelim] (v2)"}
#: v3's own keys (runner/v3.py), where they belong.
V3_HOMES = {"events": "[run] (or a configuration)", "chain": "[run] (or a configuration)", "vary": "a configuration (or [run])",
            "seed": "[run] (or a configuration)", "run": "[run]", "commands": "[run]", "folder": "a configuration",
            "fixed": "a quantity, or a configuration's fixed = { q = tag }", "points": "[quantities.<q>]",
            "to": "[quantities.<q>]", "fields": "[quantities.<q>]", "card": "[tools.<tag>]", "output": "[tools.<tag>]",
            "uses": "[tools.<tag>]", "keep": "[tools.<tag>]"}


def home_of(key: str, here: str) -> str:
    """Where a key that is unknown in table `here` belongs: "threads belongs in [run] (or a configuration)",
    or "" when no other table has it."""
    tables = [t for t in spec() if t not in ("sections", here) and key in keys(t)]
    if here in ("run", "configuration"):
        tables = [t for t in tables if t not in ("run", "configuration")]
    if "run" in tables and "configuration" in tables:
        tables.remove("configuration")
    homes = [HOMES.get(t, f"[{t}]") for t in tables]
    if not homes and key in V3_HOMES:
        homes = [V3_HOMES[key]]
    return f"'{key}' belongs in {' or '.join(homes)}" if homes else ""


def keys(table: str) -> dict[str, dict]:
    """The keys of one schema table: name → its entry. A figure's are every [plot] key marked `page`, as
    a child has them ("default" is [plot]'s value; no default of its own), then its own."""
    if table == "figure":
        inherited = {k: {f: v for f, v in e.items() if f not in ("default", "page")} | {"default_ok": True,
                         "native_ok": bool(e.get("default_ok")), "doc": f"as [plot].{k}, for these pages"}
                     for k, e in spec().get("plot", {}).items() if e.get("page")}
        return inherited | spec().get(table, {})
    if table == "plot":
        return {k: e | {"native_ok": True} if e.get("page") and e.get("default_ok") else e
                for k, e in spec().get("plot", {}).items()}
    if table == "run":
        given = {k: {**spec()["configuration"][k], "inherit": True} for k in RUN_GIVES}
        return spec().get("run", {}) | given
    if table in DECK_TABLES:
        return spec("deck").get(table, {})
    return spec().get(table, {})


def sections() -> tuple[str, ...]:
    return tuple(spec()["sections"]["order"])


def default(table: str, key: str, fallback: Any = None) -> Any:
    return keys(table).get(key, {}).get("default", fallback)


def type_name(kinds: str) -> str:
    return " or ".join(NAMES[k] for k in kinds.split("|"))


def _is(value, kinds: str) -> bool:
    for kind in kinds.split("|"):
        if isinstance(value, bool) and kind != "bool":
            continue                                       # true is not an integer here
        if isinstance(value, TYPES[kind]):
            return True
    return False


def check(values: dict, table: str, where: str, *, subtables: bool = False, extra: bool = False,
          only: tuple[str, ...] = ()) -> dict:
    """Unknown keys are errors (C1) and known keys have their type, choices and bounds. Returns the keys
    the schema does not know when `extra` (a tool's folder options); `subtables` lets a table-valued key
    the schema does not know through (a configuration inside [run]); `only` restricts the known keys."""
    known = {k: v for k, v in keys(table).items() if not only or k in only}
    extras = {}
    for key, value in values.items():
        entry = known.get(key)
        if entry is None:
            if subtables and isinstance(value, dict):
                continue
            if extra:
                extras[key] = value
                continue
            raise HepError(f"unknown key '{key}'", where=where,
                           hint=home_of(key, table) or did_you_mean(key, known) or f"known keys: {', '.join(known)}")
        if subtables and isinstance(value, dict) and "table" not in entry["type"].split("|"):
            continue                                       # a configuration named like a key ([run.threads])
        check_value(key, value, entry, f"{where}.{key}" if not where.endswith("]") else f"{where}.{key}")
    return extras


def check_value(key: str, value, entry: dict, where: str) -> None:
    kinds = entry["type"]
    if value == DEFAULT and entry.get("default_ok") or value == NATIVE and entry.get("native_ok"):
        return
    if value == DEFAULT and "str" not in kinds.split("|"):
        raise HepError(f"'{key}' does not take \"default\"", where=where,
                       hint=f"give it {type_name(kinds)}, or leave it out")
    if not _is(value, kinds):
        if isinstance(value, bool):
            raise HepError(f"'{key}' must be {type_name(kinds)}, not true/false", where=where)
        raise HepError(f"'{key}' must be {type_name(kinds)}", where=where, hint=f"got {value!r}")
    items = entry.get("items")
    members = value if isinstance(value, list) else [value]
    if items and isinstance(value, list):
        for item in value:
            if not _is(item, items):
                raise HepError(f"'{key}' entries must be {type_name(items)}", where=where, hint=f"got {item!r}")
    choices = entry.get("choices")
    if choices:
        for item in members:                     # a choice may be false (normalise = "area" | false, V68)
            if isinstance(item, (str, bool)) and not any(type(item) is type(c) and item == c for c in choices):
                shown = ", ".join(c if isinstance(c, str) else str(c).lower() for c in choices)
                raise HepError(f"{key} must be one of {shown}, not {item!r}", where=where,
                               hint=did_you_mean(item, [c for c in choices if isinstance(c, str)]) if isinstance(item, str) else None)
    if "min" in entry and _is(value, "float") and value < entry["min"]:
        raise HepError(f"'{key}' must be at least {entry['min']}", where=where, hint=f"got {value!r}")


# ── the editor schema (F6) ───────────────────────────────────────────────────────────────────

def _json_type(kinds: str) -> list[str]:
    return [{"int": "integer", "float": "number", "str": "string", "bool": "boolean", "list": "array",
             "table": "object"}[k] for k in kinds.split("|")]


def _json_key(entry: dict) -> dict:
    out: dict = {"description": "\n\n".join(t for t in (entry.get("doc", ""), entry.get("notes", "")) if t)}
    types = _json_type(entry["type"])
    one = {"type": types if len(types) > 1 else types[0]}
    if "min" in entry:
        one["minimum"] = entry["min"]
    if entry.get("choices") and "array" not in types:
        one["enum"] = entry["choices"]
    if entry.get("items"):
        one["items"] = {"type": _json_type(entry["items"])[0], **({"enum": entry["choices"]} if entry.get("choices") else {})}
    words = [{"const": DEFAULT}] * bool(entry.get("default_ok")) + [{"const": NATIVE}] * bool(entry.get("native_ok"))
    out.update({"anyOf": [one, *words]} if words else one)
    if "default" in entry:
        out["default"] = entry["default"]
    return out


def _object(table: str, open_: bool = False) -> dict:
    properties = {k: _json_key(v) for k, v in keys(table).items()}
    required = [k for k, v in keys(table).items() if v.get("required")
                and not (table in ("run", "configuration") and k in RUN_GIVES)]   # given by [run] or a configuration
    return {"type": "object", "properties": properties, **({"required": required} if required else {}),
            "additionalProperties": open_}


def _folder_options() -> dict[str, dict]:
    """Each shipped tool folder's [options] as JSON-schema properties (read as data: the folders are
    tools.py's, a higher rank), for the tool tables' typed keys."""
    kinds = {"list": "array", "table": "object", "str": "string", "int": "integer", "float": "number",
             "bool": "boolean", "flag": "boolean"}
    out = {}
    for spec_file in sorted((hep_root() / "framework" / "tools").glob("*/tool.toml")):
        options = tomllib.loads(spec_file.read_text(encoding="utf-8")).get("options", {})
        out[spec_file.parent.name] = {k: {"description": v.get("doc", ""), **({"type": kinds[v["kind"]]} if v.get("kind") in kinds else {})}
                                      for k, v in options.items()}
    return out


def _tools_v2() -> dict:
    """[tools.<tag>]: the common keys, and each folder's options when `tool` names it."""
    base = _object("tool", open_=True)
    base["allOf"] = [{"if": {"properties": {"tool": {"const": name}}, "required": ["tool"]},
                      "then": {"properties": options}} for name, options in _folder_options().items() if options]
    return {"type": "object", "additionalProperties": base}


def json_schema() -> dict:
    """run.schema.json: the run TOML for an editor (Even Better TOML / Taplo, `#:schema` or settings)."""
    configuration = _object("configuration")
    run = _object("run")
    run["properties"]["cfgs"] = {"type": "object", "additionalProperties": configuration}   # [run.cfgs.<cfg>] (V98)
    figure = _object("figure")
    plot = _object("plot")
    plot["properties"]["figures"] = {"type": "object", "additionalProperties": figure}
    plot["properties"]["data"] = _object("data")
    plot["properties"]["data"]["properties"]["map"] = {"type": "object", "additionalProperties": {"type": "string"}}
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "hep run TOML (generated from framework/schema/run.toml)",
        "type": "object",
        "properties": {
            "config": _object("config"), "run": run, "prelim": _object("prelim"),
            "static": {"type": "object", "description": "quantity = a tag, a value or \"#N\"",
                       "additionalProperties": {"type": ["string", "number", "boolean", "array"]}},
            "tools": _tools_v2(),
            "quantities": {"type": "object", "additionalProperties": _object("quantity")},
            "plot": plot,
            "cluster": _object("cluster"),
        },
        "required": ["run"],
        "additionalProperties": False,
    }


def _renamed(table: str, names: dict[str, str], drop=(), extra: dict | None = None) -> dict:
    """A table's JSON object under v3's names (runner/v3.py): `names` v2 → v3, `drop` gone, `extra` added."""
    out = _object(table)
    props = {names.get(k, k): v for k, v in out["properties"].items() if k not in drop}
    props.update(extra or {})
    out["properties"] = props
    out.pop("required", None)
    return out


def json_schema_v3() -> dict:
    """run.v3.schema.json: the run TOML's third form for an editor (03 §6, runner/v3.py)."""
    seed = {"description": "\"identity\", \"random\" or an integer: the points' seeds", "type": ["string", "integer"]}
    events = {"description": "events per point; a configuration's may be a list: one configuration per count",
              "type": ["integer", "number", "array"]}
    names = {"configuration": "run", "event_count": "events", "tools": "chain", "sweeps": "vary"}
    run = _renamed("run", names, drop=("cfgs", "seed_type", "manual_seed"),
                   extra={"seed": seed, "events": events,
                          "commands": {"type": "array", "description": "run in each point's folder before its tools"}})
    cfg = _renamed("configuration", {**names, "label": "folder", "static": "fixed"}, drop=("seed_type", "manual_seed", "prelim"),
                   extra={"seed": seed, "events": events})
    row = {"type": "object", "properties": {"tag": {"type": "string"}, "label": {"type": "string"}, "style": {"type": "object"}},
           "required": ["tag"]}
    quantity = _renamed("quantity", {}, drop=("tags", "labels", "styles", "key", "target"), extra={
        "points": {"type": "array", "items": row, "description": "one row a point: tag, value (or a value per field), label, style"},
        "fixed": {"type": ["string", "number", "boolean", "array"], "description": "the point no configuration varies: a tag"},
        "to": {"type": "object", "additionalProperties": {"type": ["string", "boolean"]},
               "description": "{ <target> = \"<key>\" or true }: where the value goes"},
        "fields": {"type": "object", "description": "a compound quantity: { field = \"<word>\" or { tool = \"key\" } }"}})
    tool = _renamed("tool", {"tool": "uses", "baseconfig": "card", "output_file": "output"},
                    extra={"keep": {"type": "boolean", "description": "false: what it writes for a later group is a scratch file"}})
    tool["additionalProperties"] = True
    by_name = {name: {**tool, "properties": {**tool["properties"], **options}, "additionalProperties": False}
               for name, options in _folder_options().items()}           # a shipped tool's keys are known: closed
    v2 = json_schema()
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "hep run TOML, the third form (generated from framework/schema/run.toml)",
        "type": "object",
        "properties": {
            "file": {**_object("config"), "properties": {**_object("config")["properties"],
                                                         "schema": {"const": 3, "description": "the form: 3 (2 keeps a file v2)"}}},
            "run": run, "cfgs": {"type": "object", "additionalProperties": cfg},
            "tools": {"type": "object", "properties": by_name, "additionalProperties": tool},
            "quantities": {"type": "object", "additionalProperties": quantity},
            "plot": v2["properties"]["plot"], "cluster": v2["properties"]["cluster"],
        },
        "additionalProperties": False,
    }


def write_json_schema(target: Path | None = None) -> Path:
    target = target or path().with_name("run.schema.json")
    target.write_text(json.dumps(json_schema(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    target.with_name("run.v3.schema.json").write_text(json.dumps(json_schema_v3(), indent=1, ensure_ascii=False) + "\n",
                                                      encoding="utf-8")
    return target


if __name__ == "__main__":                                  # make schema
    print(write_json_schema())


def toml_value(value) -> str:
    """A value as the TOML that writes it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    return str(value)


def style_entries() -> list[tuple[str, str, str]]:
    """base.toml's keys in file order: (dotted key, default as written, comment). A comment-only line
    under a key, indented to its comment, continues that key's comment; a key without one has its
    table's (`[page.margins]   # fractions of the page`)."""
    path = hep_root() / "src" / "Apps" / "Paint" / "base.toml"
    text = path.read_text(encoding="utf-8")
    values = tomllib.loads(text)
    out: list[list[str]] = []
    table, column, about = "", None, ""
    for line in text.splitlines():
        if (head := re.match(r"\[([\w.]+)\]", line)):
            table, column = head.group(1), None
            about = found.group(1).strip() if (found := re.search(r"\s#\s?(.*)$", line)) else ""
            continue
        if (key := re.match(r"(\w+)\s*=", line)):
            name = f"{table}.{key.group(1)}" if table else key.group(1)
            comment = about
            if (found := re.search(r"\s#\s?(.*)$", line)):
                comment, column = found.group(1).strip(), found.start() + 1
            value = values
            for part in name.split("."):
                value = value[part]
            out.append([name, toml_value(value), comment])
            continue
        if out and column is not None and line.strip().startswith("#") and line.index("#") == column:
            out[-1][2] += " " + line.strip()[1:].strip()
        else:
            column = None
    return [tuple(e) for e in out]
