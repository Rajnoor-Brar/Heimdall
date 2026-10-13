"""The run TOML's third form (docs/audit_3/03_Configuration.md §6), read as the second's (rank 0).

A v3 file is translated, table by table, into the v2 tables the loader has always read, so a study in
either form is one RunConfig: the same points, folders and identities. What v3 writes once and v2 wrote
in several places comes out as v2 had it:

  [file]                  → [config]
  [run] run, events,      → [run] configuration, event_count, tools, sweeps, seed_type/manual_seed;
        chain, vary, seed     [run] commands → [prelim] commands
  [cfgs.<name>]           → [run.cfgs.<name>]: folder → label, events → event_count (a list: one
                            configuration per count, <name>_<count>, run in turn as <name>), chain →
                            tools, vary → sweeps, fixed → static, seed → seed_type/manual_seed
  [tools.<name>]          → tool = <name> (uses = for a second instance), card → baseconfig,
                            output → output_file; keep = false marks a scratch file
  [quantities.<name>]     → points rows → values, tags, labels, styles; fixed → [static]; to → key
                            (a table) or target; fields → one quantity per field, swept together
  [quantities.beams]      → rows with a = {id, energy} and b = {…}: beams and energies, together
  [plot]                  → [plot], its own "default" values left out: "default" is only ever the layer
                            below; "native" (v2's [plot]-level "default") is the drawing tool's own

What only the merged file can say is the parser's (config.parse, for a file marked "_v3"): an input
that names a tool table reads its output, and each configuration's FIFOs and scratch files are
inferred from its chain (a reader in the producer's group: a FIFO; a later one: a file, a product unless
the producer says keep = false). The keys of the v2 form are refused in a v3 file, each naming its v3
name, and a v2 file is read as ever (`[file] schema = 2` says so, for one release).
"""

from __future__ import annotations

import copy
import re

from .errors import HepError, did_you_mean

#: The tables of a v3 file.
TABLES = ("file", "run", "cfgs", "tools", "quantities", "plot", "cluster")
#: v2 tables a v3 file may not have: where their content goes.
V2_TABLES = {"config": "[file]", "static": "each quantity's fixed (a configuration's own: fixed = { q = tag })",
             "prelim": "nothing: FIFOs and files are inferred from the chain (keep = false on a scratch file's producer; "
                       "[run] commands for per-point commands)"}
#: v2 keys renamed in v3, per table: the v2 name → the v3 name.
RUN_RENAMED = {"configuration": "run", "event_count": "events", "tools": "chain", "sweeps": "vary",
               "seed_type": "seed", "manual_seed": "seed"}
CFG_RENAMED = {**RUN_RENAMED, "label": "folder", "static": "fixed", "prelim": "(nothing: inferred from the chain)"}
TOOL_RENAMED = {"tool": "(the table's name; uses = for a second instance)", "baseconfig": "card", "output_file": "output"}
QUANTITY_RENAMED = {"tags": "points", "labels": "points", "styles": "points", "key": "to", "target": "to",
                    "static": "fixed"}
#: Private keys the translation leaves for the parser (stripped there).
MARK, FAMILY, KEEP, SILENT = "_v3", "_family", "_keep", "_silent"


def is_v3(raw: dict) -> bool:
    """A v3 file: [file] (unless it says schema = 2), [cfgs], or a [run] with a chain."""
    file = raw.get("file")
    if isinstance(file, dict) and file.get("schema") == 2:
        return False
    run = raw.get("run")
    return "file" in raw or "cfgs" in raw or (isinstance(run, dict) and "chain" in run)


def _refuse_renamed(table: dict, renamed: dict, where: str) -> None:
    for old, new in renamed.items():
        if old in table:
            raise HepError(f"'{old}' is the v2 form: this file is v3, where it is {new}", where=f"{where}.{old}",
                           hint="hep migrate --v3 rewrites a v2 file; [file] schema = 2 keeps one v2 for now")


def _seed(table: dict, out: dict, where: str) -> None:
    """seed = "identity" | "random" | <integer> → seed_type (and manual_seed)."""
    if "seed" not in table:
        return
    seed = table["seed"]
    if isinstance(seed, bool) or not isinstance(seed, (str, int)):
        raise HepError('seed is "identity", "random" or an integer', where=f"{where}.seed")
    if isinstance(seed, int):
        out["seed_type"], out["manual_seed"] = "manual", seed
    else:
        out["seed_type"] = seed


def count_name(n) -> str:
    """An event count as a folder name: 10000000 → 10M, 2500 → 2.5k, 500 → 500."""
    n = float(n)
    for size, unit in ((1e9, "G"), (1e6, "M"), (1e3, "k")):
        if n >= size:
            text = f"{n / size:.3g}"
            return text.rstrip("0").rstrip(".") + unit if "." in text else text + unit
    return f"{int(n)}" if n == int(n) else f"{n:g}"


def _run(table: dict, where: str) -> tuple[dict, dict]:
    """[run] → v2 [run] and the [prelim] its commands make."""
    if not isinstance(table, dict):
        raise HepError("[run] is a table", where=where)
    _refuse_renamed(table, RUN_RENAMED, where)
    if "cfgs" in table:
        raise HepError("configurations are [cfgs.<name>] at the top level in a v3 file", where=f"{where}.cfgs")
    out, prelim = {}, {}
    for key, value in table.items():
        if key == "run":
            out["configuration"] = value
        elif key == "events":
            if isinstance(value, list):
                raise HepError("[run].events is one count; a configuration's may be a list (one folder per count)",
                               where=f"{where}.events")
            out["event_count"] = value
        elif key == "chain":
            out["tools"] = value
        elif key == "vary":
            out["sweeps"] = value
        elif key == "seed":
            _seed(table, out, where)
        elif key == "commands":
            prelim["commands"] = value
        else:
            out[key] = value
    return out, prelim


def _cfg(name: str, table: dict, where: str) -> dict[str, dict]:
    """[cfgs.<name>] → one v2 configuration, or one per count of a list-valued events."""
    if not isinstance(table, dict):
        raise HepError("a configuration is a table", where=where)
    _refuse_renamed(table, CFG_RENAMED, where)
    out: dict = {}
    for key, value in table.items():
        if key == "folder":
            out["label"] = value
        elif key == "events":
            out["event_count"] = value
        elif key == "chain":
            out["tools"] = value
        elif key == "vary":
            out["sweeps"] = value
        elif key == "fixed":
            if not isinstance(value, dict):
                raise HepError("a configuration's fixed is a table: { quantity = tag }", where=f"{where}.fixed")
            out["static"] = value
        elif key == "seed":
            _seed(table, out, where)
        else:
            out[key] = value
    counts = out.get("event_count")
    if not isinstance(counts, list):
        return {name: out}
    if not counts or len(set(counts)) != len(counts):
        raise HepError("events lists different counts, one folder each", where=f"{where}.events")
    family = {}
    for count in counts:
        key = f"{name}_{count_name(count)}"
        family[key] = {**copy.deepcopy(out), "event_count": count, "label": f"{out.get('label', name)}_{count_name(count)}",
                       FAMILY: name}
    return family


def _tool(name: str, table: dict, where: str) -> dict:
    """[tools.<name>] → v2: tool = its name, or uses."""
    if not isinstance(table, dict):
        raise HepError("a tool is a table", where=where)
    _refuse_renamed(table, TOOL_RENAMED, where)
    out: dict = {"tool": table.get("uses", name)}
    for key, value in table.items():
        if key == "uses":
            continue
        if key == "card":
            out["baseconfig"] = value
        elif key == "output":
            out["output_file"] = value
        elif key == "keep":
            if not isinstance(value, bool):
                raise HepError("keep is true or false", where=f"{where}.keep")
            out[KEEP] = value
        else:
            out[key] = value
    return out


def _quantity(name: str, table: dict, where: str) -> tuple[dict[str, dict], dict[str, object]]:
    """[quantities.<name>] → the v2 quantities it is (one, or one per field) and their [static] values."""
    if not isinstance(table, dict):
        raise HepError("a quantity is a table", where=where)
    _refuse_renamed(table, QUANTITY_RENAMED, where)
    if "points" in table and "values" in table:
        raise HepError("points or values, not both", where=where, hint="points = [{ tag, value, label, style }]")
    rows = table.get("points")
    if name == "beams" and isinstance(rows, list) and rows and all(isinstance(r, dict) and "a" in r for r in rows):
        table = _beams(table, where)
        rows = table["points"]
    common = {k: v for k, v in table.items() if k not in ("points", "fixed", "to", "fields")}
    if "to" in table:
        common.update(_to(table["to"], f"{where}.to"))
    if rows is None:
        if "fields" in table:
            raise HepError("a quantity with fields has points: one row per point, a value per field", where=where)
        out = {name: common}
        return out, ({name: table["fixed"]} if "fixed" in table else {})
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise HepError("points is a list of rows: [{ tag = \"a\", value = 1, label = \"…\" }]", where=f"{where}.points")
    for i, row in enumerate(rows, start=1):
        if "tag" not in row:
            raise HepError(f"point {i} has no tag", where=f"{where}.points")
    tags = [row["tag"] for row in rows]
    labels = [row.get("label", row["tag"]) for row in rows]
    styles = [row.get("style", {}) for row in rows]
    fixed = {}
    fields = table.get("fields")
    if fields is None:
        for i, row in enumerate(rows, start=1):
            unknown = sorted(set(row) - {"tag", "value", "label", "style"})
            if unknown or "value" not in row:
                raise HepError(f"point {i} has {'no value' if 'value' not in row else 'no key ' + ', '.join(unknown)}",
                               where=f"{where}.points", hint="a row has tag, value, label, style; a quantity with fields "
                                                             "has a value per field")
        q = {**common, "values": [row["value"] for row in rows], "tags": tags}
        if any("label" in row for row in rows):
            q["labels"] = labels
        if any("style" in row for row in rows):
            q["styles"] = styles
        if "fixed" in table:
            fixed[name] = table["fixed"]
        return {name: q}, fixed
    # a compound quantity: one v2 quantity per field, swept together; the first names the points
    if not isinstance(fields, dict) or not fields:
        raise HepError("fields is a table: { field = \"<vocabulary word>\" or { tool = \"key\" } }", where=f"{where}.fields")
    out: dict[str, dict] = {}
    for n, (field, binding) in enumerate(fields.items()):
        missing = [i for i, row in enumerate(rows, start=1) if field not in row]
        if missing:
            raise HepError(f"point {missing[0]} has no {field}", where=f"{where}.points", hint="a compound point sets every field")
        if isinstance(binding, str):
            qname, q = binding, {}                                          # a vocabulary word: its own name binds it
        elif isinstance(binding, dict):
            qname, q = (name if n == 0 else f"{name}_{field}"), {"key": binding}
        else:
            raise HepError(f"field {field} is bound by a vocabulary word or {{ tool = \"key\" }}", where=f"{where}.fields")
        q.update({k: v for k, v in common.items() if k in ("description", "exclude")})
        q.update({"values": [row[field] for row in rows], "tags": tags})
        if n == 0:
            q["labels"] = labels
            if any("style" in row for row in rows):
                q["styles"] = styles
        else:
            q[SILENT] = True
        if qname in out:
            raise HepError(f"two fields bind {qname}", where=f"{where}.fields")
        out[qname] = q
        if "fixed" in table:
            fixed[qname] = table["fixed"]
    return out, fixed


def _to(to, where: str) -> dict:
    """to = { <target> = "<key>" or true }: v2's target and key. An entry is a tool table ("pythia"), an
    analysis option ("rivet/photo_eic") or a seed ("pythia/seed"); its value is the native key, or true for
    none. When any entry names a target (a "/", or true), the entries are the target list, as v2's
    target was; else only keys, for the tools that consume the quantity anyway (v2's key table)."""
    if not isinstance(to, dict) or not to or not all(isinstance(v, (str, bool)) and v is not False for v in to.values()):
        raise HepError('to is a table: { pythia = "PDF:pSet" }, { "rivet/photo_eic" = "R" }, { "pythia/seed" = true }',
                       where=where)
    keys = {name.split("/")[0]: value for name, value in to.items() if isinstance(value, str)}
    out: dict = {}
    if any("/" in name or value is True for name, value in to.items()):
        out["target"] = list(to)
    if keys:
        out["key"] = keys
    return out


def _beams(table: dict, where: str) -> dict:
    """[quantities.beams] with rows a = { id, energy }, b = { … }: the beams and their energies, one row."""
    rows = []
    for i, row in enumerate(table["points"], start=1):
        a, b = row.get("a"), row.get("b")
        if not (isinstance(a, dict) and isinstance(b, dict) and {"id", "energy"} <= set(a) and {"id", "energy"} <= set(b)):
            raise HepError(f"point {i}: a and b are {{ id = <pdg>, energy = <GeV> }}", where=f"{where}.points")
        rows.append({k: v for k, v in row.items() if k not in ("a", "b")}
                    | {"beams": [a["id"], b["id"]], "energies": [a["energy"], b["energy"]]})
    return {**{k: v for k, v in table.items() if k != "points"}, "points": rows,
            "fields": {"beams": "beams", "energies": "energies"}}


def _compounds(out: dict, compound: dict[str, list[str]]) -> None:
    """A compound quantity's name where a configuration uses it: in sweeps its fields, swept together; in
    static each field; in plot_points and combine its lead field (the one that names the points)."""
    def swept(entries):
        if not isinstance(entries, list):
            return entries
        result = []
        for entry in entries:
            if isinstance(entry, str) and entry in compound:
                result.append(list(compound[entry]))
            elif isinstance(entry, list):
                result.append([m for e in entry for m in (compound.get(e, [e]) if isinstance(e, str) else [e])])
            else:
                result.append(entry)
        return result
    tables = [out.get("run", {}), *out.get("run", {}).get("cfgs", {}).values()]
    for table in tables:
        if "sweeps" in table:
            table["sweeps"] = swept(table["sweeps"])
        if isinstance(table.get("static"), dict):
            table["static"] = {f: v for k, v in table["static"].items() for f in compound.get(k, [k])}
        for key in ("plot_points", "combine"):
            if isinstance(table.get(key), list):
                table[key] = [compound[n][0] if n in compound else n for n in table[key]]


def translate(raw: dict, where: str) -> dict:
    """A v3 file's tables as v2's (see the module's text), marked for the parser."""
    for table in raw:
        if table in V2_TABLES:
            raise HepError(f"[{table}] is the v2 form: this file is v3, where it is {V2_TABLES[table]}",
                           where=f"{where}: [{table}]", hint="hep migrate --v3 rewrites a v2 file")
        if table not in TABLES:
            raise HepError(f"unknown table [{table}]", where=where, hint=did_you_mean(table, TABLES) or ", ".join(TABLES))
    out: dict = {MARK: True}
    file = raw.get("file", {})
    if file:
        if file.get("schema", 3) != 3:
            raise HepError("[file] schema is 3 here (or 2, for a v2 file)", where=f"{where}: [file].schema")
        config = {k: v for k, v in file.items() if k != "schema"}
        if config:
            out["config"] = config
    prelim: dict = {}
    if "run" in raw:
        out["run"], prelim = _run(raw["run"], f"{where}: [run]")
    cfgs: dict = {}
    for name, table in raw.get("cfgs", {}).items():
        for key, cfg in _cfg(name, table, f"{where}: [cfgs.{name}]").items():
            cfgs[key] = cfg
    family_of = {c[FAMILY] for c in cfgs.values() if FAMILY in c}
    for key, cfg in cfgs.items():
        if cfg.get("extends") in family_of:
            raise HepError(f"'{cfg['extends']}' has several event counts: a configuration cannot extend it",
                           where=f"{where}: [cfgs.{key}].extends", hint="extend a configuration of one count")
    if cfgs:
        out.setdefault("run", {})["cfgs"] = cfgs
    if "tools" in raw:
        out["tools"] = {name: _tool(name, table, f"{where}: [tools.{name}]") for name, table in raw["tools"].items()}
    static: dict = {}
    quantities: dict = {}
    compound: dict[str, list[str]] = {}                 # a compound quantity → its fields' quantities, lead first
    for name, table in raw.get("quantities", {}).items():
        made, fixed = _quantity(name, table, f"{where}: [quantities.{name}]")
        if "fields" in table or (name == "beams" and "points" in table and any(isinstance(r, dict) and "a" in r
                                                                                for r in table["points"])):
            compound[name] = list(made)
        for qname, q in made.items():
            if qname in quantities:
                raise HepError(f"two quantities make '{qname}' (a field binds a word another quantity is)",
                               where=f"{where}: [quantities.{name}]")
            quantities[qname] = q
        static.update(fixed)
    if quantities:
        out["quantities"] = quantities
    if compound:
        _compounds(out, compound)
    if static:
        out["static"] = static
    if prelim:
        out["prelim"] = prelim
    if "plot" in raw:                                   # "default" is the layer below: as if absent
        out["plot"] = {k: v for k, v in raw["plot"].items() if v != "default"}
    if "cluster" in raw:
        out["cluster"] = raw["cluster"]
    return out


_V2_OF_RUN = {"run": "configuration", "events": "event_count", "chain": "tools", "vary": "sweeps"}
_V2_OF_CFG = {**_V2_OF_RUN, "folder": "label", "fixed": "static"}
_V2_OF_TOOL = {"card": "baseconfig", "output": "output_file", "uses": "tool"}


def v2_path(dotted: str) -> str:
    """A dotted key in v3's names (an import's `only`, `drop`) as the tables read as v2 have it:
    cfgs.pdf → run.cfgs.pdf, file.vars.x → config.vars.x, run.events → run.event_count, tools.rivet.output
    → tools.rivet.output_file, cfgs.pdf.folder → run.cfgs.pdf.label, quantities.pdf.fixed → static.pdf."""
    parts = dotted.strip().split(".")
    head = parts[0]
    if head == "file":
        return ".".join(["config", *parts[1:]])
    if head == "cfgs":
        if len(parts) >= 3:
            parts[2] = _V2_OF_CFG.get(parts[2], parts[2])
        return ".".join(["run", *parts])
    if head == "run" and len(parts) >= 2:
        parts[1] = _V2_OF_RUN.get(parts[1], parts[1])
    elif head == "tools" and len(parts) >= 3:
        parts[2] = _V2_OF_TOOL.get(parts[2], parts[2])
    elif head == "quantities" and len(parts) == 3 and parts[2] == "fixed":
        return f"static.{parts[1]}"
    return ".".join(parts)


__all__ = ["count_name", "is_v3", "translate", "v2_path"]
