"""The errand file: load it, check it strictly, and hand back a typed model (rank 1).

doc:errand-file. The checks here are the ones that need only the file (rules C1, C2,
C3, C5 and the shape of every key). The ones that need the tool folders, the master TOML or the
point are in `quantities`, `tools` and `execute`.

Every error names the file and the key (`where`) and says what to do (`hint`).
"""

from __future__ import annotations

import contextvars
import copy
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import plugins, schema, v3
from .errors import HeimdallError, did_you_mean
from .paths import config_file, configs_root, heimdall_root, in_record, resolve
from .quantities import check_shapes, select
from .sweep import Listed, check_curve_style, set_entries

#: How a point's seeds are chosen (V39, doc:identity); the schema's [errand.seed_type].choices.
SEED_TYPES = tuple(schema.keys("errand")["seed_type"]["choices"])
DEFAULT = schema.DEFAULT
#: A run's tag (V223): a short name that tells its configuration folder apart, never part of an identity.
TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,39}")              # it names folders: never . or ..


def check_tag(tag, where: str | None = None) -> str:
    """A tag as given (`--tag`, a configuration's `tag`, `heimdall tag`) or read back: a letter or digit, then
    letters, digits, `.`, `_`, `+` and `-`, 40 at most; anything else refused, naming the rule."""
    if not isinstance(tag, str) or not TAG.fullmatch(tag):
        raise HeimdallError(f"the tag {tag!r} is not a tag: a letter or digit, then letters, digits, '.', '_', '+' "
                            "and '-', at most 40",
                            where=where, hint="e.g. nlo, run2.v1, pdf+scale")
    return tag


@dataclass
class Tool:
    tag: str
    tool: str
    baseconfig: list[str] = field(default_factory=list)
    input: list[str] = field(default_factory=list)
    output_file: list[str] = field(default_factory=list)
    timeout: float = 0.0
    stall_after: float = 0.0
    status: str = ""
    executable: str = ""
    arguments: list = field(default_factory=list)
    consumes: list[str] = field(default_factory=list)
    config: dict | None = None
    streamable: bool | None = None
    consumes_events: bool | None = None
    shards: int = 1                                  # K > 1: K processes on a share of the events each (V31)
    settings: dict = field(default_factory=dict)     # native card settings, as written (V59)
    cores: int = 0                                   # cores it keeps busy, for --plan's note (0: estimated, V60)
    filters: str = ""                                # its own filters.toml (configs/<A>/…), V61
    extra: dict = field(default_factory=dict)       # tool-specific keys and export requests


@dataclass
class Quantity:
    name: str
    values: list
    tags: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    styles: list[dict] = field(default_factory=list)   # one per value: its curves' look (V67)
    shape: str | list = ""                             # its values' shape, the vocabulary's grammar (V76)
    key: str | dict | None = None
    target: list[str] = field(default_factory=list)
    format: str = ""
    description: str = ""
    exclude: list[int] = field(default_factory=list)   # 1-based value indices a sweep leaves out (V42)
    silent: bool = False                               # a compound quantity's later field: not in point names (v3)


@dataclass
class Configuration:
    key: str
    label: str                                      # its folder: [errand.cfgs.<cfg>].label, else the table key (V45)
    serial: int | None
    description: str
    event_count: int
    threads: int
    sweeps: list                                    # entries: str | list[str]
    plot_points: list[str]
    tools: list[list[str]]                          # groups
    post: list[list[str]]
    static: dict
    prelim: dict
    pre: list[list[str]] = field(default_factory=list)   # tools run once before every point
    generate_cards: list[str] = field(default_factory=list)   # tags (and tag:product) for the context file, beyond the chain
    combine: list[str] = field(default_factory=list)    # swept quantities whose points are merged into one (V35)
    parallelism: int = 1                                # points run at once (V36); never in an identity
    parallelism_auto: bool = False                      # "auto" (V75): set from the plans, cores ÷ a point's
    swept: bool = True                                  # run by [errand].sweep_runs (V38)
    title: str = ""                                     # the `run NN - <title> -` header of a sweep
    run_folder: str = ""                                # <A>/<run_folder>/…: [errand.cfgs.<cfg>].name, else [errand].name (V46)
    seed_type: str = "identity"                         # SEED_TYPES (V39)
    manual_seed: int | None = None                      # seed_type = "manual": every point's seed
    origins: dict = field(default_factory=dict)         # key → where its value came from (--show-config, V56)
    cluster: dict = field(default_factory=dict)         # [cluster], this configuration's over the run's (V114); never in an identity
    serial_auto: bool = False                           # v3 without a serial: the runner numbers its folder (doc:errand-file)
    draw: object = True                                 # [errand].plot (V167): true, false, or the sets the run draws
    measure: object = True                              # [errand].stats (V168): true, false, or the sets it measures
    library: object = False                             # [errand].library: pool the generation points (false, true, "only")
    serial_note: str = ""                               # why the runner chose the number it did (--plan)
    inference: dict | None = None                       # v3: what infers a resolved chain's interfaces per point (V153)
    own: dict = field(default_factory=dict)             # V179: its own vars and data (OWN_TABLES), over the file's
    tag: str = ""                                       # its folder's tag when a run gives none and it has none (V223)


@dataclass
class Errand:
    path: Path
    assignment: str
    name: str
    serial: int | None
    default_configuration: str | None                  # None only under sweep_runs
    configurations: dict[str, Configuration]
    prelim: dict
    static: dict
    tools: dict[str, Tool]
    quantities: dict[str, Quantity]
    plot: dict
    master_toml: str | None
    raw: dict
    sweep_runs: bool = False                            # `heimdall run` executes every swept configuration (V38)
    sweep_list: list = field(default_factory=list)      # sweep_runs = ["a", "b"]: these, in this order (V79)
    sets: list = field(default_factory=list)            # the --set overrides it was loaded with (V77: provenance)
    included: dict = field(default_factory=dict)        # "<section>.<name>" → the [config].import file it came from
    imported: list = field(default_factory=list)        # the files it imports, every level (a record's snapshot copies them)
    meta: dict = field(default_factory=dict)            # [config.meta]: descriptive; versions warned about (V97)
    families: dict = field(default_factory=dict)        # v3: a configuration with several event counts → its configurations
    form: int = 2                                       # the file's form: 2, or 3 (runner/v3.py)
    stats: dict = field(default_factory=dict)           # [stats] (V168): what the statistics measure, over the pages
    ranking: dict = field(default_factory=dict)         # [ranking]: how the statistics become each point's loss
    applied: dict = field(default_factory=dict)         # V179: the configuration's own vars and data it was read with
    report: dict = field(default_factory=dict)          # V209: [report], its template laid under it (a report's recipe)
    templates: list = field(default_factory=list)       # V209: the report templates it read (a record's snapshot copies them)

    @property
    def folder(self) -> Path:
        """Its file's folder: where the bare names it gives (cards, filters, imports, its master, a root_style)
        are."""
        return Path(self.path).parent

    def configuration(self, name: str | None) -> Configuration:
        wanted = name or self.default_configuration
        if wanted in self.families:
            raise HeimdallError(f"'{wanted}' is several configurations, one per event count: {', '.join(self.families[wanted])}",
                           where=f"{self.path}", hint=f"heimdall run runs them in turn; name one, e.g. {self.families[wanted][0]}")
        if wanted is None:
            raise HeimdallError("[errand] runs every configuration (sweep_runs) and names none", where=f"{self.path}: [errand]",
                           hint=f"name one: configurations {', '.join(self.configurations)}")
        if wanted not in self.configurations:
            raise HeimdallError(f"no configuration '{wanted}'", where=f"{self.path}: [errand]",
                           hint=did_you_mean(wanted, self.configurations)
                           or f"configurations: {', '.join(self.configurations) or '(none)'}")
        return self.configurations[wanted]

    def runs(self, name: str | None) -> list[str]:
        """The configurations `heimdall run` executes, in order (V38): the one named on the command line,
        even under sweep_runs; else, under [errand].sweep_runs, every configuration not `swept = false`, in the
        order of the file; else [errand].configuration."""
        if name in self.families:                       # v3: one configuration per event count
            return list(self.families[name])
        if name:
            return [self.configuration(name).key]
        if self.sweep_list:
            return [k for key in self.sweep_list for k in (self.families.get(key) or [self.configuration(key).key])]
        if self.sweep_runs:
            return [key for key, c in self.configurations.items() if c.swept]
        if self.default_configuration in self.families:
            return list(self.families[self.default_configuration])
        return [self.configuration(None).key]


# ── checking ───────────────────────────────────────────────────────────────────────────────────

#: [run.defaults] (V56) is gone: [errand] itself gives every configuration its keys (V99).
DEFAULTS = "defaults"
#: [errand.cfgs.<cfg>]: the configurations (V98; they were [errand.<cfg>], beside [errand]'s own keys).
CFGS = "cfgs"


def _layers(errand: dict, where: str) -> dict[str, list[tuple[str, dict]]]:
    """Each configuration's layers, most specific first (V56): its own table ([errand.cfgs.<cfg>], V98), the
    ones it `extends`, in turn. [errand] (V99) and the schema's defaults come after, in `inherited`."""
    tables = errand.get(CFGS, {})
    for key, table in tables.items():
        if not isinstance(table, dict):
            raise HeimdallError("a configuration is a table", where=f"{where}: [errand.{CFGS}.{key}]")
    out = {}
    for key, table in tables.items():
        # swept is refused in a strict load (V79); heimdall migrate's lenient one reads it to write sweep_runs
        schema.check({k: v for k, v in table.items() if k != "swept"}, "configuration", f"{where}: [errand.{CFGS}.{key}]")
        chain, seen, parent = [(f"[errand.{CFGS}.{key}]", table)], {key}, table.get("extends")
        while parent:
            if parent not in tables:
                raise HeimdallError(f"extends names '{parent}', which is not a configuration", where=f"{where}: {chain[-1][0]}.extends",
                               hint=did_you_mean(parent, tables) or f"configurations: {', '.join(tables)}")
            if parent in seen:
                raise HeimdallError(f"extends goes round in a circle: {' → '.join([*seen, parent])}", where=f"{where}: [errand.{CFGS}.{key}].extends")
            seen.add(parent)
            chain.append((f"[errand.{CFGS}.{parent}]", tables[parent]))
            parent = tables[parent].get("extends")
        out[key] = chain
    return out


def _deep(base: dict, over: dict) -> dict:
    """`over` merged into `base`, tables recursively, anything else replaced; a "default" keeps base's."""
    out = dict(base)
    for key, value in over.items():
        if value == DEFAULT:
            continue
        out[key] = _deep(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def _generate_cards(entries, where: str, tools: dict) -> list[str]:
    """generate_cards: tool tables (and "<tag>:<product>") the context file gets beyond the chain (doc:connections);
    whether a product exists is the tool folder's, checked when the point is planned."""
    if not isinstance(entries, list) or not all(isinstance(e, str) for e in entries):
        raise HeimdallError("generate_cards is a list of tool tables: [\"pythia\", \"rivet\", \"herwig:run\"]", where=where)
    for entry in entries:
        tag = entry.partition(":")[0]
        if tag not in tools:
            raise HeimdallError(f"generate_cards names '{tag}', which is not a [tools.<tag>] table", where=where,
                           hint=did_you_mean(tag, tools))
    return list(dict.fromkeys(entries))


def _inferred(groups: list[list[str]], tools: dict, keep: dict, base: dict, quantities: dict) -> dict:
    """A v3 configuration's [prelim] (runner/v3.py): an output of its chain read by a tool of the same group
    is a FIFO; read only later, a file in the point's folder when its producer says keep = false (else a
    product, as any output); [errand] commands as written. "@<quantity>" stands for each tool it may choose."""
    def members(entry: str) -> list[str]:
        if entry.startswith("@") and entry[1:] in quantities:
            return [t for v in quantities[entry[1:]].values for t in fragment_tags(v) if t in tools]
        return [entry] if entry in tools else []
    group_of = {tag: g for g, group in enumerate(groups) for entry in group for tag in members(entry)}
    fifo: list[str] = []
    files: list[str] = []
    for tag, g in group_of.items():
        for name in tools[tag].output_file:
            readers = [t for t in group_of if name in tools[t].input]
            same = [t for t in readers if group_of[t] == g and t != tag]
            later = [t for t in readers if group_of[t] > g]
            if same and later:
                raise HeimdallError(f"'{name}' is read in {tag}'s group ({', '.join(same)}) and after it ({', '.join(later)}): "
                               "a FIFO has one reader", where=f"[tools.{tag}].output",
                               hint="write two outputs, one for each: fan-out")
            if same and name not in fifo:
                fifo.append(name)
            elif later and keep.get(tag) is False and name not in files:
                files.append(name)
    out: dict = {}
    if fifo:
        out["fifo"] = fifo
    if files:
        out["files"] = files
    if base.get("commands"):
        out["commands"] = base["commands"]
    return out


def _own_prelim(chain, prelim: dict, origins: dict) -> dict:
    """A configuration's [prelim] is the nearest layer's, whole, else the file's: the interfaces belong to
    one chain (jets.toml's delphes writes a file where the default chain has a FIFO), so they are not merged."""
    for origin, layer in chain:
        if isinstance(layer.get("prelim"), dict):
            origins["prelim"] = origin
            return layer["prelim"]
    origins["prelim"] = "[prelim]"
    return prelim


def _as_list(value) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _groups(entries: list, where: str, tools: dict) -> list[list[str]]:
    """`tools = [A, [B, C], D]` → [[A], [B, C], [D]] (doc:sweeps, C5)."""
    groups = []
    for entry in entries:
        members = entry if isinstance(entry, list) else [entry]
        if not members:
            raise HeimdallError("an empty group in the tool list", where=where)
        for member in members:
            if isinstance(member, list):
                raise HeimdallError("tool groups nest one level only", where=where,
                               hint="write [A, [B, C], D]: an inner list is one group that runs together")
            if not isinstance(member, str):
                raise HeimdallError(f"a tool entry must be a tool tag, got {member!r}", where=where)
            if member.startswith("@"):
                continue                               # a tool chosen by a quantity (V19): resolved per point
            if member not in tools:
                raise HeimdallError(f"'{member}' is not a [tools.<tag>] table", where=where,
                               hint=did_you_mean(member, tools) or "define [tools." + member + "]")
        groups.append(list(members))
    return groups


def resolve_chain(groups: list[list[str]], choose, tools: dict) -> list[list[str]]:
    """Groups with each `@<quantity>` replaced by what `choose(name)` gives, (value, where) (V19, V153): a tool tag,
    or a fragment of chain, spliced where the entry stands. `@q` alone in its group (`"@q"` or `["@q"]`) is a
    chain entry: a fragment's items become entries there (a tag a group of one, a list a group), so
    ["@q", "D"] with ["A", ["B", "C"]] is ["A", ["B", "C"], "D"]. Beside other members, a fragment's tags join
    that group, and a group inside it is refused (groups nest one level). [] splices nothing. The result is
    checked as a written chain is: each tag a [tools.<tag>] table (C5), no empty group, a tool once."""
    def items(name: str) -> tuple[list, str]:
        value, where = choose(name)
        if isinstance(value, str):
            return [value], where
        if isinstance(value, list):
            return value, where
        raise HeimdallError(f"@{name} took {value!r}: a selector's value is a tool tag or a list of them (a piece of chain)",
                       where=where, hint='value = "pythia", or ["madgraph", "pythia"], or ["a", ["b", "c"]]')

    out: list[list[str]] = []
    for group in groups:
        if len(group) == 1 and group[0].startswith("@"):                  # an entry of its own: splice entries
            name = group[0][1:]
            fragment, where = items(name)
            for item in fragment:
                members = item if isinstance(item, list) else [item]
                if any(isinstance(m, list) for m in members):
                    raise HeimdallError(f"@{name}'s value nests a group two deep", where=where,
                                   hint='a piece of chain is tags and groups of tags: ["A", ["B", "C"]]')
                if not members:
                    raise HeimdallError(f"@{name}'s value holds an empty group", where=where)
                out.append([(m, where) for m in members])
            continue
        resolved = []
        for member in group:
            if not member.startswith("@"):
                resolved.append((member, ""))
                continue
            name = member[1:]
            fragment, where = items(name)
            if any(isinstance(item, list) for item in fragment):
                raise HeimdallError(f"@{name}'s value puts a group inside the group of @{name}", where=where,
                               hint=f"groups nest one level: write @{name} as a chain entry of its own")
            resolved += [(item, where) for item in fragment]
        if not resolved:
            raise HeimdallError("a group of the chain is empty once its @ entries are chosen",
                           where=next((w for m in group if m.startswith("@") for _, w in [items(m[1:])]), ""))
        out.append(resolved)
    seen: dict[str, str] = {}
    for group in out:
        for tag, where in group:
            if not isinstance(tag, str) or tag not in tools:
                raise HeimdallError(f"'{tag}' is not a [tools.<tag>] table", where=where,
                               hint=did_you_mean(str(tag), tools) or "a selector's values name tool tables (see C5)")
            if tag in seen:
                raise HeimdallError(f"'{tag}' is twice in the chain", where=where or seen[tag] or "the chain",
                               hint="a tool table runs once per point: give the second its own table (uses = …)")
            seen[tag] = where
    return [[tag for tag, _ in group] for group in out]


def fragment_tags(value) -> list[str]:
    """The tool tags a selector's value names: itself, or a fragment's, flattened (V153)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [tag for item in value for tag in fragment_tags(item)]
    return []


def chain_prelim(configuration: "Configuration", groups: list[list[str]], tools: dict, quantities: dict) -> dict:
    """A resolved chain's interfaces (V153): v3 infers them from that chain, so an alternative that reads an output in
    its own group has a FIFO where another reads it later from a file; a v2 [prelim] is written, and kept."""
    if configuration.inference is None:
        return configuration.prelim
    return _inferred(groups, tools, configuration.inference["keep"], configuration.inference["base"], quantities)


def check_selectors(configuration: "Configuration", quantities: dict, tools: dict, where: str) -> None:
    """Every value of every quantity that chooses a tool here splices into a valid chain (V153), the values no
    point runs included: checked with the file, the others' selectors as nothing."""
    names = {m[1:] for group in configuration.tools for m in group if m.startswith("@")}
    for name in sorted(names):
        if name not in quantities:
            raise HeimdallError(f"@{name} names no [quantities.{name}]", where=where, hint=did_you_mean(name, quantities))
        quantity = quantities[name]
        for value, tag in zip(quantity.values, quantity.tags or [str(v) for v in quantity.values]):
            def choose(asked: str, value=value, tag=tag):
                return (value, f"[quantities.{name}] {tag}") if asked == name else ([], "")
            try:
                resolve_chain(configuration.tools, choose, tools)
            except HeimdallError as error:
                if "empty once" in error.message:                  # another selector, left out here, fills it
                    continue
                raise


def _listed(entry, where: str, quantities: dict) -> Listed:
    """`{ points = [{ generator = "py8", pdf = "nn23" }, { generator = "hw7" }] }`: listed combinations (V154), each
    row naming one point of each quantity it sets, by tag, value or "#N"; a quantity left out of a row is not set
    there. Equal rows are refused; a quantity's exclude does not apply (the rows are explicit)."""
    form = 'vary = [{ points = [{ <quantity> = "<tag>", … }, …] }]'
    if not isinstance(entry, dict) or set(entry) != {"points"} or not isinstance(entry["points"], list) or not entry["points"]:
        raise HeimdallError("a table in vary lists combinations: { points = [...] }, a row of quantities each", where=where,
                       hint=form)
    members: list[str] = []
    rows: list[dict[str, int]] = []
    for number, row in enumerate(entry["points"], start=1):
        if not isinstance(row, dict) or not row:
            raise HeimdallError(f"listed point {number} is not a table naming a point of each quantity it sets", where=where,
                           hint=form)
        indices = {}
        for name, ref in row.items():
            if name not in quantities:
                raise HeimdallError(f"listed point {number} sets '{name}', which is not a [quantities.<q>] table", where=where,
                               hint=did_you_mean(name, quantities) or f"declare [quantities.{name}]")
            indices[name] = select(quantities[name], ref, f"{where}: listed point {number}")
            if name not in members:
                members.append(name)
        if indices in rows:
            raise HeimdallError(f"listed points {rows.index(indices) + 1} and {number} are the same point", where=where)
        rows.append(indices)
    return Listed(members, rows)


def _sweeps(entries: list, where: str, quantities: dict) -> list:
    """C3: every entry names a declared quantity; an inner list is one entangled group; a table lists
    combinations (V154). No quantity is in two entries."""
    seen: set[str] = set()
    out = []
    for entry in entries:
        if isinstance(entry, dict):
            listed = _listed(entry, where, quantities)
            if twice := sorted(set(listed) & seen):
                raise HeimdallError(f"'{twice[0]}' is swept twice", where=where)
            seen |= set(listed)
            out.append(listed)
            continue
        members = entry if isinstance(entry, list) else [entry]
        for name in members:
            if not isinstance(name, str):
                raise HeimdallError(f"sweeps entries are quantity names, got {name!r}", where=where)
            if name not in quantities:
                raise HeimdallError(f"sweeps names '{name}', which is not a [quantities.<q>] table", where=where,
                               hint=did_you_mean(name, quantities) or f"declare [quantities.{name}]")
            if name in seen:
                raise HeimdallError(f"'{name}' is swept twice", where=where)
            seen.add(name)
        if isinstance(entry, list):
            counts = {name: len(quantities[name].values) for name in members}
            if len(set(counts.values())) > 1:
                raise HeimdallError("entangled quantities need equal value counts", where=where,
                               hint=", ".join(f"{n}: {c}" for n, c in counts.items()))
        out.append(list(members) if isinstance(entry, list) else entry)
    return out


def _resolved_threads(value: int) -> int:
    return value or (os.cpu_count() or 1)             # 0 = every core: resolved here, never passed on as 0


# ── --set ──────────────────────────────────────────────────────────────────────────────────────

def _literal(text: str):
    try:
        return tomllib.loads(f"v = {text}")["v"]
    except tomllib.TOMLDecodeError:
        return text


def apply_sets(raw: dict, sets: list[str]) -> None:
    """`--set static.energies=18x275`, `--set errand.cfgs.pdf.threads=4`: override one value (dotted keys);
    a v3 file's in its own names, before it is read as v2: `--set errand.events=100`, `--set cfgs.pdf.vary=[]`."""
    for item in sets:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise HeimdallError(f"--set expects KEY=VALUE, got '{item}'")
        parts = key.strip().split(".")
        if parts[0] == "run":                                       # the old names
            raise HeimdallError(f"--set {key.strip()}: [run] is now [errand]",
                           hint=f"--set {'.'.join(['errand', *parts[1:]])}={value.strip()}")
        table = raw
        for part in parts[:-1]:
            table = table.setdefault(part, {})
            if not isinstance(table, dict):
                raise HeimdallError(f"--set {key}: '{part}' is not a table")
        table[parts[-1]] = _literal(value.strip())


# ── loading ────────────────────────────────────────────────────────────────────────────────────

def _read(path: Path) -> dict:
    """An errand file's tables, a v3 file's as v2's (runner/v3.py)."""
    return _form(_toml(path), path)


def _form(raw: dict, path: Path) -> dict:
    """A v3 file as v2's tables; a v2 file as it is ([file] schema = 2 says so: its other keys are [config]'s).
    A file in the names before Assignment/Errand ([run]) is refused, with the command that rewrites it."""
    v3.refuse_old_names(raw, str(path))
    if v3.is_v3(raw):
        return v3.translate(raw, str(path))
    if isinstance(raw.get("file"), dict):
        given = {k: v for k, v in raw["file"].items() if k != "schema"}
        raw = {k: v for k, v in raw.items() if k != "file"}
        if given:
            raw["config"] = {**raw.get("config", {}), **given}
    return raw


# ── old names (a record keeps the names it was written in) ──────────────────────────────────────

#: Each old name read from a record by this process, said once by the CLI (`` `<old>` → `<new>` ``).
OLD_NAMES: list[str] = []
#: True while a lenient load reads a file (heimdall migrate, completion): old names are read there, never refused.
LENIENT: contextvars.ContextVar[bool] = contextvars.ContextVar("lenient", default=False)


def _metric_ids() -> dict:
    from stats import metrics                     # numpy loads here, only when a file names a metric
    return metrics.ALIASES


def _id(found: list, place: str, name):
    """A metric id at `place`: its id now, the rename noted in `found`."""
    if isinstance(name, str) and name in (aliases := _metric_ids()):
        found.append((place, name, aliases[name]))
        return aliases[name]
    return name


def _ids_in(found: list, place: str, table: dict, key: str) -> None:
    """`table[key]` names metrics: a list of ids, or a table keyed by them."""
    given = table.get(key)
    if isinstance(given, list):
        table[key] = [_id(found, f"{place}.{key}", n) for n in given]
    elif isinstance(given, dict):
        table[key] = {_id(found, f"{place}.{key}", n): v for n, v in given.items()}


#: A page's key, a figure's key and a figure's class as they were (old → new).
PAGE_KEYS = {"legend_statistic": "legend_metric"}
FIGURE_KEYS = {"statistic": "metric"}
OLD_CLASSES = {"statistic": "metric"}


def _page_keys(found: list, place: str, table) -> None:
    """The key a page may carry that names a metric, under its name now."""
    if not isinstance(table, dict):
        return
    _keys(found, place, table, PAGE_KEYS)
    if "legend_metric" in table:
        table["legend_metric"] = _id(found, f"{place}.legend_metric", table["legend_metric"])


def _figure(found: list, place: str, table) -> None:
    """A figure's table: its page keys, its class and its own key under their names now."""
    if not isinstance(table, dict):
        return
    _page_keys(found, place, table)
    if table.get("class") in OLD_CLASSES:
        old, table["class"] = table["class"], OLD_CLASSES[table["class"]]
        found.append((f"{place}.class", f'class = "{old}"', f'class = "{table["class"]}"'))
    _keys(found, place, table, FIGURE_KEYS)
    if "metric" in table:
        table["metric"] = _id(found, f"{place}.metric", table["metric"])


#: The ranking table's name and keys as they were (old → new): the table was [score].
RANKING_TABLE = ("score", "ranking")
RANKING_KEYS = {"normalise": "cost", "mean": "over_pages", "veto": "veto_loss"}


def _keys(found: list, place: str, table: dict, keys: dict) -> None:
    """`table`'s keys renamed in place, as `keys` says (old → new), each noted in `found`."""
    for old, new in keys.items():
        if old in table and new not in table:
            table[new] = table.pop(old)
            found.append((f"{place}.{old}", old, new))


def _table(found: list, owner, names: tuple, place: str, said: tuple) -> None:
    """`owner[names[0]]` moved to `owner[names[1]]` (a table under its old name), noted in `found` as `said` (old, new)."""
    old, new = names
    if isinstance(owner, dict) and old in owner and new not in owner:
        owner[new] = owner.pop(old)
        found.append((place, *said))


def _scoring(found: list, place: str, table) -> None:
    """A ranking table: its old keys and the metric ids it names."""
    if isinstance(table, dict):
        _keys(found, place, table, RANKING_KEYS)
        for key in ("metrics", "thresholds"):
            _ids_in(found, place, table, key)


#: A metric's category, by the key it had as a report's `purpose:<key>`; a summary section's key as it was.
OLD_CATEGORIES = {"shape": "accuracy"}
OLD_SECTIONS = {"standings": "leaderboard"}


def _stats_entry(found: list, place: str, entry):
    """A report section's `stats` entry: `<what>[:<part>]`, the part before `:` a metric's id or a section's key;
    `purpose:<key>` is `category:<key>`, and `standings` is `leaderboard`."""
    if not isinstance(entry, str):
        return entry
    head, colon, tail = entry.partition(":")
    if entry in OLD_SECTIONS:
        found.append((place, entry, OLD_SECTIONS[entry]))
        return OLD_SECTIONS[entry]
    if head == "purpose":
        new = f"category:{OLD_CATEGORIES.get(tail, tail)}"
        found.append((place, entry, new))
        return new
    return _id(found, place, head) + colon + tail


def _report(found: list, place: str, table) -> None:
    sections = table.get("section") if isinstance(table, dict) else None
    for k, section in enumerate(sections if isinstance(sections, list) else [], start=1):
        if not isinstance(section, dict):
            continue
        at = f"{place}.section[{k}]"
        if isinstance(section.get("stats"), list):
            section["stats"] = [_stats_entry(found, f"{at}.stats", e) for e in section["stats"]]
        _page_keys(found, f"{at}.plot", section.get("plot"))


def _sets(found: list, place: str, sets) -> None:
    entries = sets.items() if isinstance(sets, dict) else enumerate(sets if isinstance(sets, list) else [], start=1)
    for key, entry in entries:
        if isinstance(entry, dict):
            at = f"{place}.{key}" if isinstance(sets, dict) else f"{place}[{key}]"
            _table(found, entry, RANKING_TABLE, f"{at}.score", ("score", "ranking"))
            _scoring(found, f"{at}.ranking", entry.get("ranking"))
            _page_keys(found, at, entry)


def renamed(raw: dict, where: str, recorded: bool) -> dict:
    """A file's tables with every old name in its new one's place. `recorded` (a record's snapshot, a Run's plot.toml, a
    lenient load): the copy is returned and each rename joins OLD_NAMES once; else the first old name is refused, with the
    command that rewrites it. A file with no old name is returned as it is."""
    out = copy.deepcopy(raw)
    found: list = []
    if isinstance(out.get("stats"), dict):
        _ids_in(found, "[stats]", out["stats"], "metrics")
    _table(found, out, RANKING_TABLE, "[score]", ("[score]", "[ranking]"))
    _scoring(found, "[ranking]", out.get("ranking"))
    plot = out.get("plot")
    if isinstance(plot, dict):
        _page_keys(found, "[plot]", plot)
        for name, figure in (plot.get("figures") or {}).items() if isinstance(plot.get("figures"), dict) else ():
            _figure(found, f"[plot.figures.{name}]", figure)
        _sets(found, "[plot].sets", plot.get("sets"))
    if "report" in out:
        _report(found, "[report]", out["report"])
    if not found:
        return raw
    if not recorded:
        place, old, new = found[0]
        raise HeimdallError(f"renamed: {old} is {new}", where=f"{where}: {place}", hint="heimdall migrate rewrites it")
    for _, old, new in found:
        said = f"`{old}` → `{new}`"
        if said not in OLD_NAMES:
            OLD_NAMES.append(said)
    return out


def _loaded(text: str, path: Path) -> dict:
    """A TOML file's tables, its old names read or refused (`renamed`)."""
    return renamed(tomllib.loads(text), str(path), in_record() or LENIENT.get())


def _toml(path: Path) -> dict:
    try:
        return _loaded(path.read_text(encoding="utf-8"), path)
    except OSError:
        raise HeimdallError("cannot read the file", where=str(path)) from None
    except tomllib.TOMLDecodeError as error:
        escape = "escape" in str(error).lower() or "'\\'" in str(error)
        raise HeimdallError(f"not valid TOML: {error}", where=str(path),
                       hint="in a \"…\" string a backslash starts a TOML escape: write the label in single quotes, "
                            "'PDF4LHC21\\_40', or double the backslash, \"PDF4LHC21\\\\_40\"" if escape else None) from None


#: How an included file's sections meet the file's (V56): whole entries replace for quantities and tools
#: (a redefined quantity takes nothing of the included one), keys for [static], tables recursively else.
ENTRIES = ("quantities", "tools")


def _over(base: dict, over: dict) -> dict:
    """`over`'s tables laid over `base`'s (V56): whole entries for quantities and tools, but a v3 file's
    merge key by key (doc:errand-file: a tool's one key changed, a quantity's fixed given); [errand]'s keys one by one;
    tables deep. The v3 mark is the file's
    own (the last one laid: the file being run)."""
    out = {k: v for k, v in base.items() if k != v3.MARK}
    if over.get(v3.MARK):
        out[v3.MARK] = True
    for section, value in over.items():
        if section == v3.MARK:
            continue
        if section in ENTRIES and over.get(v3.MARK) and isinstance(value, dict):    # v3: key by key
            below = dict(out.get(section, {}))
            for tag, table in value.items():
                below[tag] = _deep(below[tag], table) if isinstance(below.get(tag), dict) and isinstance(table, dict) else table
            out[section] = below
        elif section in ENTRIES and isinstance(value, dict):
            out[section] = {**out.get(section, {}), **value}
        elif section == "errand" and isinstance(value, dict):          # [errand] keys one by one, configurations whole
            below = out.get(section, {})
            out[section] = {**below, **value}
            if isinstance(below.get(CFGS), dict) and isinstance(value.get(CFGS), dict):
                out[section][CFGS] = {**below[CFGS], **value[CFGS]}
        elif isinstance(value, dict) and isinstance(out.get(section), dict):
            out[section] = _deep(out[section], value)
        else:
            out[section] = value
    return out


def _import_path(name, assignment: str, where: str, folder: Path | None = None) -> Path:
    """An import, named as `heimdall run` names a config (V94): `name` a file beside the one importing it (in
    `folder`; configs/<A>/ without one), `<A>/<E>` another assignment's, `./…` from the repository root, `/…`
    absolute; `.toml` optional."""
    if not isinstance(name, str) or not name:
        raise HeimdallError(f"an import names a file, got {name!r}", where=where)
    plain = "/" in name and not name.startswith(("./", "/"))
    source = resolve(name, "config" if plain else "import", assignment=assignment, folder=folder, where=where)
    if source.suffix != ".toml" and not source.exists():
        source = source.with_name(source.name + ".toml")
    if not source.is_file():
        raise HeimdallError(f"no file '{name}' to import", where=where,
                       hint="a bare name is beside the file naming it; <A>/<E> another assignment's; ./… the repository's")
    return source


def _parts(dotted, where: str) -> list[str]:
    if not isinstance(dotted, str) or not dotted or any(not p for p in dotted.split(".")):
        raise HeimdallError(f"expected a dotted key (quantities.pdf, cfgs.default, plot.figures.eta), got {dotted!r}", where=where)
    if dotted.split(".")[0] == "run":                                       # the old names
        raise HeimdallError(f"'{dotted}': [run] is now [errand]", where=where, hint=v3.NAMES_HINT)
    return dotted.split(".")


def _has(table: dict, parts: list[str]) -> bool:
    for part in parts:
        if not isinstance(table, dict) or part not in table:
            return False
        table = table[part]
    return True


def _nearest(table: dict, parts: list[str]) -> str | None:
    """The nearest existing key at the level where a dotted path stops matching."""
    for part in parts:
        if not isinstance(table, dict) or part not in table:
            return did_you_mean(part, list(table)) if isinstance(table, dict) else None
        table = table[part]
    return None


def _without(table: dict, parts: list[str]) -> dict:
    out = dict(table)
    if len(parts) == 1:
        del out[parts[0]]
    else:
        out[parts[0]] = _without(out[parts[0]], parts[1:])
    return out


def _only(part: dict, keys: list, source: Path, where: str) -> dict:
    """An import's `only` (V95): just these sections or dotted keys of the file, each of which it has."""
    out: dict = {}
    for dotted in _as_list(keys):
        parts = _parts(dotted, where)
        if not _has(part, parts):
            raise HeimdallError(f"only names '{dotted}', which {source.name} has not", where=where,
                           hint=_nearest(part, parts) or f"its sections: {', '.join(part)}")
        value, target = part, out
        for name in parts[:-1]:
            value = value[name]
            target = target.setdefault(name, {})
        target[parts[-1]] = value[parts[-1]]
    return out


def _entry(entry, where: str) -> tuple[str, list | None]:
    """An import entry: a name, or { from = name, only = [keys] }."""
    if isinstance(entry, dict):
        unknown = sorted(set(entry) - {"from", "only"})
        if unknown or "from" not in entry:
            raise HeimdallError("an import table is { from = \"<config>\", only = [\"<section or dotted key>\", …] }",
                           where=where, hint=f"not {unknown[0]}" if unknown else "it needs from")
        return entry["from"], _as_list(entry.get("only")) or None
    return entry, None


def _assignment_of(path: Path, raw: dict, fallback: str) -> str:
    """The assignment a file's bare paths are relative to: its folder under configs/, else its [errand].assignment."""
    try:
        parts = path.resolve().relative_to(configs_root().resolve()).parts
    except ValueError:
        parts = ()
    return parts[0] if len(parts) > 1 else raw.get("errand", {}).get("assignment") or fallback


def _rebased(raw: dict, assignment: str, folder: Path) -> dict:
    """An imported file of another folder, its bare path keys made absolute against its own folder (cards,
    filters, its master: beside it) and assignment (V94), so its tools find their cards wherever it is imported. The keys are those the schema marks `path`; a value
    that is ./…, /… or path:<command> is left as it is. Paths are resolved alike either way, so no
    identity moves."""
    def fixed(value, root: str):
        if isinstance(value, list):
            return [fixed(v, root) for v in value]
        if not isinstance(value, str) or not value or value.startswith(("./", "/", "path:")) or value == DEFAULT:
            return value
        return str(resolve(value, root, assignment=assignment, folder=folder))

    def marked(table: str) -> dict[str, str]:
        return {k: e["path"] for k, e in schema.spec().get(table, {}).items() if "path" in e}

    out = {**raw}
    if isinstance(raw.get("tools"), dict):
        out["tools"] = {tag: {k: fixed(v, marked("tool")[k]) if k in marked("tool") else v for k, v in table.items()}
                        if isinstance(table, dict) else table for tag, table in raw["tools"].items()}
    for section in ("plot", "config"):
        if isinstance(raw.get(section), dict):
            out[section] = {k: fixed(v, marked(section)[k]) if k in marked(section) else v for k, v in raw[section].items()}
    return out


def _imports(raw: dict, path: Path, assignment: str, chain: tuple[Path, ...]) -> tuple[dict, dict, list]:
    """[config].import = ["common", "Other/run"]: the run starts from those files' tables, in order, and its
    own win (V56, V93). Each imported file is read the same way first, so imports nest (V94), depth-first;
    a circle is refused. Returns the merged tables, which file gave each quantity, tool and configuration
    ("b.toml" or, through b, "b.toml ← c.toml"), and every imported file's (assignment, name)."""
    names = _as_list(raw.get("config", {}).get("import"))
    if not names:
        if raw.get("config", {}).get("drop"):
            raise HeimdallError("drop removes what an import brought in, and this file imports nothing", where=f"{path}: [config].drop")
        return raw, {}, []
    where = f"{path}: [config].import"
    merged: dict = {}
    origins: dict[str, str] = {}
    located: list = []
    named = v3.v2_path if raw.get(v3.MARK) else (lambda dotted: dotted)    # a v3 file names keys in its own names
    for entry in names:
        name, only = _entry(entry, where)
        only = None if only is None else [named(k) for k in only]
        source = _import_path(name, assignment, where, path.parent)
        if source.resolve() in chain:
            circle = " → ".join(p.name for p in (*chain, source.resolve()))
            raise HeimdallError(f"imports go round in a circle: {circle}", where=where)
        part = _read(source)
        if "master" in part:
            raise HeimdallError("[master] is [config] now: master_toml is master, include is import",
                           where=f"{source}: [master]", hint="heimdall migrate rewrites it")
        theirs = _assignment_of(source, part, assignment)
        part, inner, deeper = _imports(part, source, theirs, (*chain, source.resolve()))
        if only is not None:                     # V101: a file's vars come with whatever is taken of it
            given = part.get("config", {}).get("vars")
            part = _only(part, only, source, where)
            if given:
                part = {**part, "config": {**part.get("config", {}), "vars": given}}
        if theirs != assignment or source.resolve().parent != path.resolve().parent:
            part = _rebased(part, theirs, source.parent)
        if "name" in part.get("errand", {}):
            located.append((part["errand"].get("assignment", theirs), part["errand"]["name"], source))
        located += deeper
        part = {**part, "config": {k: v for k, v in part.get("config", {}).items() if k not in ("import", "drop")}}
        if not part["config"]:
            del part["config"]
        for key in [f"{s}.{k}" for s in ENTRIES for k in part.get(s, {})] + _run_entries(part):
            origins[key] = f"{source.name} ← {inner[key]}" if key in inner else source.name
        merged = _over(merged, part)
    for dotted in map(named, _as_list(raw.get("config", {}).get("drop"))):   # V95: out of what came in, before this file
        parts = _parts(dotted, f"{path}: [config].drop")
        if not _has(merged, parts):
            raise HeimdallError(f"drop names '{dotted}', which no import gave", where=f"{path}: [config].drop",
                           hint=_nearest(merged, parts) or "drop removes what an import brought in")
        merged = _without(merged, parts)
        origins = {k: v for k, v in origins.items() if k != dotted and not k.startswith(dotted + ".")}
    for section in ENTRIES:                                           # the file's own entries are its own
        for key in raw.get(section, {}):
            origins.pop(f"{section}.{key}", None)
    for key in _run_entries(raw):
        origins.pop(key, None)
    return _over(merged, raw), origins, located


def _run_entries(raw: dict) -> list[str]:
    """The tables of [errand] an import gives whole: run.cfgs.<cfg>."""
    return [f"errand.{CFGS}.{k}" for k in raw.get("errand", {}).get(CFGS, {})]


def _with_imports(raw: dict, path: Path) -> tuple[dict, dict, list]:
    """The file being run, its imports laid under it (V94). Its location is its own: it sets [errand].name
    and assignment itself (that no folder of it is an imported run's is load's to check, V100)."""
    if not _as_list(raw.get("config", {}).get("import")):
        if raw.get("config", {}).get("drop"):
            raise HeimdallError("drop removes what an import brought in, and this file imports nothing", where=f"{path}: [config].drop")
        return raw, {}, []
    own = raw.get("errand", {})
    missing = [k for k in ("assignment", "name") if k not in own]
    if missing:
        raise HeimdallError(f"a file that imports sets its own [errand].{' and '.join(missing)}: its location is never imported",
                       where=f"{path}: [errand]")
    merged, origins, located = _imports(raw, path, own["assignment"], (path.resolve(),))
    return merged, origins, sorted({source for *_, source in located})


def _imported_files(raw: dict, path: Path, assignment: str, chain: tuple[Path, ...] = ()) -> list[Path]:
    """Every file an errand file imports, at every level, depth-first (a record's snapshot copies them, V158);
    _imports' own list holds only the imported runs."""
    out: list[Path] = []
    chain = chain or (path.resolve(),)
    for entry in _as_list(raw.get("config", {}).get("import")):
        name, _ = _entry(entry, f"{path}: [config].import")
        source = _import_path(name, assignment, f"{path}: [config].import", path.parent)
        if source.resolve() in chain or source.resolve() in out:
            continue
        out.append(source.resolve())
        part = _read(source)
        out += [f for f in _imported_files(part, source, _assignment_of(source, part, assignment), (*chain, source.resolve()))
                if f not in out]
    return out


def _folder_list(errand) -> list[tuple[str, str]]:
    """Each configuration's folder, <A>/<E>/<NN_><label> (as tools.run_dir makes it; NN_ literally
    when the runner numbers it), with its key."""
    out = []
    for key, c in errand.configurations.items():
        folder = f"{c.serial:02d}_{c.label}" if c.serial is not None else f"NN_{c.label}" if c.serial_auto else c.label
        out.append((f"{errand.assignment}/{c.run_folder or errand.name}/{folder}", key))
    return out


def _folders(errand) -> dict[str, str]:
    return dict(_folder_list(errand))


def _clash(one: str, other: str) -> bool:
    """Two folders are one: the same, or a folder the runner numbers (NN_<label>) and any numbered one
    of its label."""
    if one == other:
        return True
    a, b = one.rsplit("/", 1), other.rsplit("/", 1)
    if a[0] != b[0] or not (a[1].startswith("NN_") or b[1].startswith("NN_")):
        return False
    label = lambda name: name.split("_", 1)[1] if "_" in name and (name[:2] == "NN" or name.split("_", 1)[0].isdigit()) else None
    return label(a[1]) is not None and label(a[1]) == label(b[1])


def _own_folders(errand) -> None:
    """A configuration the runner numbers has its folder to itself: another of this file with its label
    would share the numbers. A run with compare figures keeps the folder `compare` for them."""
    figures = (errand.plot or {}).get("figures") or {}
    if any(isinstance(f, dict) and f.get("class") == "compare" for f in figures.values()):
        for key, c in errand.configurations.items():
            if c.serial is None and not c.serial_auto and c.label == "compare":
                raise HeimdallError(f"configuration '{key}' would write the folder 'compare', where this errand's compare "
                               "figures go", where=f"{errand.path}", hint="give it another folder (label), or a serial")
    mine = _folder_list(errand)
    for i, (folder, key) in enumerate(mine):
        for other, other_key in mine[i + 1:]:
            if _clash(folder, other):
                shown = folder if folder == other else f"{folder.rsplit('/', 1)[0]}/NN_{folder.rsplit('/', 1)[1].split('_', 1)[1]}"
                raise HeimdallError(f"configurations '{key}' and '{other_key}' would both write {shown}", where=f"{errand.path}",
                               hint="give one of them another folder (or name); a folder the runner numbers is one configuration's")


def _shared_folders(errand, imported: list[Path]) -> None:
    """V100: an imported run may share this file's [errand].name (its results beside the other's), but no
    configuration of the two may have the same folder, or their points would overwrite each other's."""
    mine = _folders(errand)
    for source in imported:
        try:
            theirs = _folders(load(str(source), strict=False))
        except HeimdallError:                                     # a file that cannot run on its own writes nothing
            continue
        for folder in sorted(f for f in mine if any(_clash(f, t) for t in theirs)):
            other = next(theirs[t] for t in theirs if _clash(folder, t))
            raise HeimdallError(f"[errand.cfgs.{mine[folder]}] and {source.name}'s [errand.cfgs.{other}] would both write "
                           f"{folder}", where=f"{errand.path}: [errand]",
                           hint="give one of them another serial, label or name: a folder belongs to one configuration")


#: A var cited in an errand file's text (V96); a page text's {q:…}/{opt:…} placeholders are the plot stage's.
VAR = re.compile(r"\{var:([A-Za-z_][A-Za-z0-9_]*)\}")


def _toml_text(value) -> str:
    return ("true" if value else "false") if isinstance(value, bool) else str(value)


def with_vars(raw: dict, path: Path) -> dict:
    """[config.vars] (V96): `{var:name}` in any string of the file replaced, after the imports and --set,
    before anything is checked, so an identity sees only the result. A string that is one var takes the
    var's value as it is (a number stays a number); inside a longer string a var must be a scalar. An
    imported file's {var:…} takes this file's value, so a shared file may be written with parameters."""
    found = raw.get("config", {}).get("vars", {})
    where = f"{path}: [config.vars]"
    if not isinstance(found, dict):
        raise HeimdallError("[config.vars] is a table: name = value", where=where)
    for name, value in found.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise HeimdallError(f"a var's name is a word (letters, digits, _), not '{name}'", where=where)
        if isinstance(value, dict) or (isinstance(value, str) and VAR.search(value)):
            raise HeimdallError(f"var '{name}' is a value, not a table or another var", where=f"{where}.{name}")

    def lookup(name: str, at: str):
        if name not in found:
            raise HeimdallError(f"{{var:{name}}} is not in [config.vars]", where=f"{path}: {at}",
                           hint=did_you_mean(name, list(found)) or (f"vars: {', '.join(found)}" if found else "declare it in [config.vars]"))
        return found[name]

    def walk(value, at: str):
        if isinstance(value, str):
            if (whole := VAR.fullmatch(value)):
                return lookup(whole[1], at)

            def inline(match):
                given = lookup(match[1], at)
                if isinstance(given, list):
                    raise HeimdallError(f"{{var:{match[1]}}} is a list: it can only be a whole value", where=f"{path}: {at}")
                return _toml_text(given)
            return VAR.sub(inline, value)
        if isinstance(value, dict):
            return {k: walk(v, f"{at}.{k}" if at else k) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, at) for v in value]
        return value

    out = {section: walk(value, section) for section, value in raw.items() if section != "config"}
    if "config" in raw:
        out["config"] = {k: (v if k == "vars" else walk(v, f"config.{k}")) for k, v in raw["config"].items()}
    return out


#: What a configuration may set of the file's own (V179): its vars, over [file.vars]; its data, for [plot.data].
OWN_TABLES = ("vars", "data")


def _own_of(raw: dict, key: str | None) -> dict:
    """A configuration's own vars and data (V179), through the configurations it extends: vars merged (its
    own win), data the nearest."""
    cfgs = raw.get("errand", {}).get("cfgs", {}) if isinstance(raw.get("errand"), dict) else {}
    chain, seen = [], set()
    while isinstance(cfgs.get(key), dict) and key not in seen:
        seen.add(key)
        chain.append(cfgs[key])
        key = cfgs[key].get("extends")
    out: dict = {}
    for table in reversed(chain):
        if isinstance(table.get("vars"), dict):
            out["vars"] = {**out.get("vars", {}), **table["vars"]}
        if "data" in table:
            out["data"] = table["data"]
    return out


def _with_own(raw: dict, own: dict) -> dict:
    """The file as one configuration reads it (V179): its vars over [config.vars], its data for [plot].data."""
    if not own:
        return raw
    out = {**raw, "config": {**raw.get("config", {})}}
    if "vars" in own:
        out["config"]["vars"] = {**raw.get("config", {}).get("vars", {}), **own["vars"]}
    if "data" in own:
        out["plot"] = {**raw.get("plot", {}), "data": own["data"]}
    return out


def for_configuration(errand: Errand, name: str | None) -> tuple[Errand, Configuration]:
    """The file read for one configuration (V179): `errand` itself when that configuration sets nothing of its
    own (OWN_TABLES) or `errand` was read with what it sets, else the file read again with it."""
    configuration = errand.configuration(name)
    if configuration.own == errand.applied:
        return errand, configuration
    again = load(str(errand.path), sets=list(errand.sets), configuration=configuration.key)
    return again, again.configuration(configuration.key)


def check_read_for(errand: Errand, configuration: Configuration) -> None:
    """A configuration planned or drawn from a file read for another (V179): refused, never quietly with the
    other's cards or data."""
    if configuration.own != errand.applied:
        raise HeimdallError(f"configuration '{configuration.key}' sets its own {' and '.join(configuration.own) or 'nothing'}, "
                       "and this file was read for another", where=str(errand.path),
                       hint="(Heimdall's) read it with config.for_configuration(run, name)")


def load(name: str, *, sets: list[str] = (), strict: bool = True, text: str | None = None,
         configuration: str | None = None) -> Errand:
    """An errand file, checked. `strict=False` (heimdall migrate only, V79) still reads the forms it rewrites;
    `text` (heimdall migrate's, V81) is read in place of the file's. Read for `configuration` (else the
    default one), with its own vars and data (V179)."""
    token = LENIENT.set(True) if not strict else None
    try:
        return _load(name, sets=sets, strict=strict, text=text, configuration=configuration)
    finally:
        if token is not None:
            LENIENT.reset(token)


def _load(name: str, *, sets, strict: bool, text: str | None, configuration: str | None) -> Errand:
    path = config_file(name)
    if text is None:
        given = _toml(path)
    else:
        try:
            given = _loaded(text, path)
        except tomllib.TOMLDecodeError as error:
            raise HeimdallError(f"not valid TOML, even migrated: {error}", where=str(path)) from None
    own_names = v3.is_v3(given)                 # a v3 file takes --set in its own names: run.events, cfgs.pdf.vary
    if own_names:
        apply_sets(given, list(sets))
    raw, included, imported = _with_imports(_form(given, path), path)
    if not own_names:
        apply_sets(raw, list(sets))
    key = configuration or (raw.get("errand", {}).get("configuration") if isinstance(raw.get("errand"), dict) else None)
    raw = with_vars(_with_own(raw, _own_of(raw, key)), path)
    errand = parse(raw, path, strict=strict)
    errand.applied = errand.configurations[key].own if key in errand.configurations else {}
    _own_folders(errand)
    _shared_folders(errand, imported)
    errand.included = included
    errand.imported = _imported_files(_form(given, path), path, errand.assignment)
    report, errand.templates = report_of(raw.get("report", {}), path, errand.assignment, f"{path}: [report]")
    errand.report = {k: v for k, v in report.items() if k not in NOT_IN_A_RUN}   # a template's from and output: a recipe's
    errand.sets = list(sets)
    if strict:
        _check_used(errand)
    return errand


def heimdall_table(name: str, *, sets: list[str] = ()) -> dict:
    """[heimdall] (V188): the flags an errand file gives the commands that read it, its imports' under its own,
    --set applied as load applies it. {} when it has none."""
    path = config_file(name)
    given = _toml(path)
    own_names = v3.is_v3(given)
    if own_names:
        apply_sets(given, list(sets))
    raw, _, _ = _with_imports(_form(given, path), path)
    if not own_names:
        apply_sets(raw, list(sets))
    table = raw.get("heimdall", {})
    if not isinstance(table, dict):
        raise HeimdallError("[heimdall] is a table: a command's option = its value", where=f"{path}: [heimdall]",
                       hint='[heimdall.run] journal = true, keep = ["work"]')
    return table


def plot_of(name: str) -> dict:
    """`heimdall plot … --plot FILE` (V158): a file's [plot], in either form, checked as a run's is, for one
    drawing in place of the run's own. The file is named as a config is (configs/<A>/<E>, ./…, /…); it
    needs nothing but [plot] (and [file] schema = 3)."""
    path = config_file(name)
    raw = _form(_toml(path), path)
    if "plot" not in raw:
        raise HeimdallError("a plot file holds a [plot] table", where=str(path), hint="[plot] and its figures, as an errand file's")
    plot = raw["plot"]
    if "legend" in plot:
        raise HeimdallError("[plot].legend is now part of the style", where=f"{path}: [plot].legend")
    check_plot(plot, f"{path}: [plot]")
    return plot


def _check_used(errand: Errand) -> None:
    """A quantity of this file's own (not an import's) that no configuration varies, fixes or chooses a tool
    by would change nothing: refused, with the fix."""
    used: set[str] = set()
    for configuration in errand.configurations.values():
        used |= {n for entry in configuration.sweeps for n in (entry if isinstance(entry, list) else [entry])}
        used |= set(configuration.static)
        used |= {m[1:] for groups in (configuration.tools, configuration.pre, configuration.post)
                 for group in groups for m in group if m.startswith("@")}
    for name in errand.quantities:
        if name in used or f"quantities.{name}" in errand.included:
            continue
        if errand.form == 3:
            raise HeimdallError(f"quantity '{name}' is declared but neither varied nor fixed: it would change nothing",
                           where=f"{errand.path}: [quantities.{name}]",
                           hint="give it fixed = \"<tag>\", vary it in a configuration (vary = [...]), or remove it")
        raise HeimdallError(f"quantity '{name}' is declared but neither swept nor static: it would change nothing",
                       where=f"{errand.path}: [quantities.{name}]",
                       hint="set it in [static] (or a configuration's static), sweep it in a configuration, or remove it")


def _marks(raw: dict) -> tuple[dict, int, dict, dict, dict]:
    """runner/v3.py's private keys out of the tables (copied): the form, each tool's keep, each quantity's
    silence, each configuration's family."""
    raw = dict(raw)
    form = 3 if raw.pop(v3.MARK, False) else 2
    keep, silent, families = {}, {}, {}
    if isinstance(raw.get("tools"), dict):
        keep = {t: tb[v3.KEEP] for t, tb in raw["tools"].items() if isinstance(tb, dict) and v3.KEEP in tb}
        raw["tools"] = {t: ({k: v for k, v in tb.items() if k != v3.KEEP} if isinstance(tb, dict) else tb)
                        for t, tb in raw["tools"].items()}
    if isinstance(raw.get("quantities"), dict):
        silent = {q for q, tb in raw["quantities"].items() if isinstance(tb, dict) and tb.get(v3.SILENT)}
        raw["quantities"] = {q: ({k: v for k, v in tb.items() if k != v3.SILENT} if isinstance(tb, dict) else tb)
                             for q, tb in raw["quantities"].items()}
    errand = raw.get("errand")
    if isinstance(errand, dict) and isinstance(errand.get(CFGS), dict):
        cfgs = {}
        for key, tb in errand[CFGS].items():
            if isinstance(tb, dict) and v3.FAMILY in tb:
                families.setdefault(tb[v3.FAMILY], []).append(key)
                tb = {k: v for k, v in tb.items() if k != v3.FAMILY}
            cfgs[key] = tb
        raw["errand"] = {**errand, CFGS: cfgs}
    return raw, form, keep, silent, families


def parse(raw: dict, path: Path, strict: bool = True) -> Errand:
    where = str(path)
    raw, form, keep, silent, families = _marks(raw)
    sections = schema.sections()
    if "master" in raw:                                    # break and migrate (V93)
        raise HeimdallError("[master] is [config] now: master_toml is master, include is import", where=f"{where}: [master]",
                       hint="heimdall migrate rewrites it")
    v3.refuse_old_names(raw, where)                        # the old names
    for key in raw:
        if key not in sections:
            raise HeimdallError(f"unknown section [{key}]", where=where,
                           hint=did_you_mean(key, sections) or f"sections: {', '.join(sections)}")

    file_config = raw.get("config", {})
    schema.check(file_config, "config", f"{where}: [config]")
    check_meta(file_config.get("meta", {}), f"{where}: [config.meta]")

    errand = raw.get("errand")
    if not isinstance(errand, dict):
        raise HeimdallError("missing [errand]", where=where, hint="every errand file has [errand] name, assignment, configuration")
    if isinstance(errand.get(DEFAULTS), dict):                      # V99: [errand] gives what it gave
        if strict:
            raise HeimdallError(f"[errand.{DEFAULTS}] is [errand] now: its keys go in [errand] itself, which every configuration "
                           "starts from", where=f"{where}: [errand.{DEFAULTS}]", hint="heimdall migrate moves them")
        errand = {**{k: v for k, v in errand.items() if k != DEFAULTS}, **errand[DEFAULTS]}   # it was above [errand]
        raw = {**raw, "errand": errand}
    old = [k for k, v in errand.items() if isinstance(v, dict) and k != CFGS and k not in schema.keys("errand")]
    if old and strict:                                                # break and migrate (V98)
        raise HeimdallError(f"[errand.{old[0]}] is a configuration, and configurations are [errand.{CFGS}.<cfg>] now (see V98)",
                       where=f"{where}: [errand.{old[0]}]",
                       hint=f"write [errand.{CFGS}.{old[0]}]; heimdall migrate rewrites the file")
    if old:                                      # heimdall migrate reads the old form it rewrites (V79, V98)
        errand = {**{k: v for k, v in errand.items() if k not in old}, CFGS: {**{k: errand[k] for k in old}, **errand.get(CFGS, {})}}
        raw = {**raw, "errand": errand}
    schema.check(errand, "errand", f"{where}: [errand]")
    sweep_on = errand.get("sweep_runs") is True or (isinstance(errand.get("sweep_runs"), list) and bool(errand["sweep_runs"]))
    if strict:                                  # V79: the forms heimdall migrate rewrites
        for key, table in errand.get(CFGS, {}).items():
            if isinstance(table, dict) and "swept" in table:
                raise HeimdallError(f"[errand.{CFGS}.{key}].swept is gone: [errand].sweep_runs lists the configurations it runs (see V79)",
                               where=f"{where}: [errand.{CFGS}.{key}].swept",
                               hint="sweep_runs = [\"a\", \"b\"], in the order to run them; heimdall migrate rewrites this file")
    for required in ("name", "assignment") + (() if sweep_on else ("configuration",)):
        if required not in errand:
            raise HeimdallError(f"[errand] needs '{required}'", where=f"{where}: [errand]")
    assignment = errand["assignment"]
    # A config under configs/<X>/ belongs to assignment X; one given as ./path elsewhere (tests) need not.
    if path.parent.parent == configs_root() and path.parent.name != assignment:
        raise HeimdallError(f"[errand].assignment is '{assignment}' but the file is in configs/{path.parent.name}/",
                       where=f"{where}: [errand].assignment", hint="they must match")

    prelim = raw.get("prelim", {})
    schema.check(prelim, "prelim", f"{where}: [prelim]")

    quantities: dict[str, Quantity] = {}
    for name, table in raw.get("quantities", {}).items():
        at = f"{where}: [quantities.{name}]"
        if not isinstance(table, dict):
            raise HeimdallError("a quantity is a table", where=at)
        schema.check(table, "quantity", at)
        if "values" not in table or not table["values"]:
            raise HeimdallError("a quantity needs values", where=at)
        values = table["values"]
        for listed in ("tags", "labels", "styles"):
            if listed in table and len(table[listed]) != len(values):
                raise HeimdallError(f"'{listed}' must have one entry per value ({len(values)})", where=f"{at}.{listed}")
        for i, look in enumerate(table.get("styles", []), start=1):
            check_curve_style(look, f"{at}.styles[{i}]")
        exclude = table.get("exclude", [])
        for index in exclude:
            if isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= len(values):
                raise HeimdallError(f"exclude names {index!r}, which is not a value's place", where=f"{at}.exclude",
                               hint=f"1-based: 1 to {len(values)}, as static \"#2\" and --points 2 count")
        if len(set(exclude)) == len(values):
            raise HeimdallError("exclude leaves no value to sweep", where=f"{at}.exclude")
        quantity = Quantity(name=name, values=values, tags=[str(t) for t in table.get("tags", [])],
                                    labels=[str(l) for l in table.get("labels", [])], key=table.get("key"),
                                    styles=[{k: v for k, v in s.items() if v != DEFAULT} for s in table.get("styles", [])],
                                    shape=table.get("shape", ""),
                                    target=_as_list(table.get("target")), format=table.get("format", ""),
                                    description=table.get("description", ""), exclude=sorted(set(exclude)),
                                    silent=name in silent)
        check_shapes(quantity, at)                                          # V58: the vocabulary's shape
        if strict:
            no_tlatex(quantity.labels, f"{at}.labels")
        quantities[name] = quantity

    tools: dict[str, Tool] = {}
    for tag, table in raw.get("tools", {}).items():
        at = f"{where}: [tools.{tag}]"
        if not isinstance(table, dict):
            raise HeimdallError("a tool is a table", where=at)
        extras = schema.check(table, "tool", at, extra=True)
        if "tool" not in table:
            raise HeimdallError("a tool table needs tool = \"<tool folder>\" (heimdall tools lists them)", where=at)
        tools[tag] = Tool(tag=tag, tool=table["tool"], baseconfig=_as_list(table.get("baseconfig")),
                          input=_as_list(table.get("input")), output_file=_as_list(table.get("output_file")),
                          timeout=float(table.get("timeout", 0)), stall_after=float(table.get("stall_after", 0)),
                          status=table.get("status", ""), executable=table.get("executable", ""),
                          arguments=list(table.get("arguments", [])), consumes=list(table.get("consumes", [])),
                          config=table.get("config"), streamable=table.get("streamable"),
                          consumes_events=table.get("consumes_events"), shards=int(table.get("shards", 1)),
                          settings=dict(table.get("settings", {})), cores=int(table.get("cores", 0)),
                          filters=table.get("filters", ""),
                          extra=extras)

    outputs = {name for tool in tools.values() for name in tool.output_file}
    for tag, tool in tools.items():                    # an input that names its producer reads its output (v3)
        resolved = []
        for name in tool.input:
            if name in tools and name not in outputs:
                made = tools[name].output_file
                if len(made) != 1:
                    raise HeimdallError(f"input names '{name}', which writes {len(made)} outputs: name the one it reads",
                                   where=f"{where}: [tools.{tag}].input", hint=", ".join(made) or f"{name} writes none")
                resolved.append(made[0])
            else:
                resolved.append(name)
        tool.input = resolved

    static = raw.get("static", {})
    if not isinstance(static, dict):
        raise HeimdallError("[static] is a table of quantity = value", where=where)
    for name in static:
        if name not in quantities:
            raise HeimdallError(f"[static] sets '{name}', which is not a [quantities.<q>] table",
                           where=f"{where}: [static]", hint=did_you_mean(name, quantities))

    cluster = raw.get("cluster", {})
    check_cluster(cluster, f"{where}: [cluster]")

    configurations: dict[str, Configuration] = {}
    for key, chain in _layers(errand, where).items():
        table = chain[0][1]
        at = f"{where}: [errand.{CFGS}.{key}]"
        origins: dict[str, str] = {}

        def inherited(name: str, fallback=None):
            """The most specific layer's value (V56): own, extended, then [errand] (V99); a
            "default" in a layer is the next one's (V55); else the schema's default."""
            layers = chain
            if name in schema.keys("errand"):
                layers = [*layers, ("[errand]", errand)]
            for origin, layer in layers:
                if name in layer and layer[name] != DEFAULT:
                    origins[name] = origin
                    return layer[name]
            origins[name] = "default"
            value = schema.default("configuration", name, schema.default("errand", name))
            return fallback if value is None else value

        def merged(name: str, base: dict) -> dict:
            """A table merged through the layers, parent first ([static], [prelim])."""
            out = dict(base)
            for origin, layer in reversed(chain):
                if isinstance(layer.get(name), dict):
                    out = _deep(out, layer[name])
                    origins[name] = origin
            return out

        tools_entries = inherited("tools")
        if tools_entries is None:
            raise HeimdallError("a configuration needs tools = [...]", where=at,
                           hint="here, in the configuration it extends, or in [errand]")
        sweeps = _sweeps(inherited("sweeps", []), f"{at}.sweeps", quantities)
        swept = {n for entry in sweeps for n in (entry if isinstance(entry, list) else [entry])}
        plot_points = inherited("plot_points", [])
        for name in plot_points:
            if name not in swept:
                raise HeimdallError(f"plot_points names '{name}', which is not swept here", where=f"{at}.plot_points",
                               hint="pages are cells of the grid of swept quantities (docs/stable/guide/sweeps.md)")
            for entry in (e for e in sweeps if isinstance(e, Listed) and name in e):     # V154
                if missing := [n for n, row in enumerate(entry.rows, start=1) if name not in row]:
                    raise HeimdallError(f"plot_points names '{name}', which listed point {missing[0]} leaves out",
                                   where=f"{at}.plot_points", hint=f"set {name} in every listed point, or page by another")
        combine = inherited("combine", [])
        axes = {entry for entry in sweeps if isinstance(entry, str)}
        for name in combine:                                                # C14
            if name not in axes:
                raise HeimdallError(f"combine names '{name}', which is not swept here as an axis of its own",
                               where=f"{at}.combine",
                               hint="the points that differ only in a combined quantity are merged into one (docs/stable/guide/scale.md)")
            if name in plot_points:
                raise HeimdallError(f"'{name}' is both combined and a page axis (plot_points)", where=f"{at}.combine",
                               hint="a combined quantity's points become one curve: it cannot also make pages")
        local_static = merged("static", {})
        for name in local_static:
            if name not in quantities:
                raise HeimdallError(f"static sets '{name}', which is not a [quantities.<q>] table", where=f"{at}.static",
                               hint=did_you_mean(name, quantities))
        for _, layer in chain:
            if isinstance(layer.get("prelim"), dict):
                schema.check(layer["prelim"], "prelim", f"{at}.prelim")
            if "cluster" in layer:
                check_cluster(layer["cluster"], f"{at}.cluster")
        event_count = inherited("event_count")
        if event_count is None:
            raise HeimdallError("no event_count: set it here or in [errand]", where=at)
        static_values = {k: v for k, v in _deep(static, local_static).items() if v != DEFAULT}   # top-level "default": unset
        if tag := inherited("tag", ""):                                  # "": none, over [errand]'s
            origin = origins["tag"].replace(f"[errand.{CFGS}.", "[cfgs.") if form == 3 else origins["tag"]
            check_tag(tag, f"{where}: {origin}.tag")
        configurations[key] = Configuration(
            key=key, label=table.get("label") or key, serial=inherited("serial"),                     # V45
            serial_auto=form == 3 and inherited("serial") is None,
            run_folder=inherited("name") or errand["name"],                                           # V46
            swept=table.get("swept", True), title=table.get("title", key),
            seed_type=inherited("seed_type"), manual_seed=inherited("manual_seed"),
            description=inherited("description", ""), event_count=int(event_count),
            threads=_resolved_threads(int(inherited("threads"))), parallelism=1 if inherited("parallelism") == "auto" else int(inherited("parallelism")),
            parallelism_auto=inherited("parallelism") == "auto",
            sweeps=sweeps, plot_points=list(plot_points), combine=list(combine),
            tools=(groups := _groups(tools_entries, f"{at}.tools", tools)),
            post=_groups(inherited("post", []), f"{at}.post", tools),
            pre=_groups(inherited("pre", []), f"{at}.pre", tools),
            generate_cards=_generate_cards(inherited("generate_cards", []), f"{at}.generate_cards", tools),
            static=static_values,
            prelim=(_inferred(groups, tools, keep, prelim, quantities) if form == 3     # v3: from the chain
                    else _own_prelim(chain, prelim, origins)),                 # replaced whole: its chain's interfaces
            origins=origins, cluster=merged("cluster", cluster), draw=inherited("plot", True),
            measure=inherited("stats", True), library=inherited("library", False),
            inference={"keep": keep, "base": prelim} if form == 3 else None, own=_own_of(raw, key), tag=tag)
        check_selectors(configurations[key], quantities, tools, f"{at}.tools")

    a_cfg = "[cfgs.<name>]" if form == 3 else "[errand.cfgs.<cfg>]"   # in the file's own names
    if isinstance(errand.get("sweep_runs"), list):         # V79: the members, in order
        listed = errand["sweep_runs"]
        for name in listed:
            if name not in configurations:
                raise HeimdallError(f"[errand].sweep_runs names '{name}', which is not a {a_cfg} table",
                               where=f"{where}: [errand].sweep_runs", hint=did_you_mean(name, configurations) or
                               f"configurations: {', '.join(configurations)}")
        if len(set(listed)) != len(listed):
            raise HeimdallError("[errand].sweep_runs names a configuration twice", where=f"{where}: [errand].sweep_runs")
    if sweep_on and not any(c.swept for c in configurations.values()):
        raise HeimdallError("[errand].sweep_runs is on but every configuration has swept = false", where=f"{where}: [errand].sweep_runs",
                       hint="leave one in, or turn the sweep off")
    if "configuration" in errand and errand["configuration"] not in configurations:
        key = "run" if form == 3 else "configuration"
        raise HeimdallError(f"[errand].{key} is '{errand['configuration']}', which is not a {a_cfg} table", where=f"{where}: [errand].{key}",
                       hint=did_you_mean(errand["configuration"], configurations)
                       or f"configurations: {', '.join(configurations) or '(none)'}")

    plot = raw.get("plot", {})
    if "legend" in plot:
        raise HeimdallError("[plot].legend is now part of the style", where=f"{where}: [plot].legend",
                       hint=f'[plot.style] legend.position = "{plot["legend"]}" (or in the root_style file)')
    check_plot(plot, f"{where}: [plot]", strict=strict)
    stats = raw.get("stats", {})
    check_stats(stats, f"{where}: [stats]")
    ranking = raw.get("ranking", {})
    check_ranking(ranking, f"{where}: [ranking]")
    if "report" in raw:                                    # V209: what its folders' reports show
        check_report(raw["report"], f"{where}: [report]", run_toml=True)

    return Errand(path=path, assignment=assignment, name=errand["name"], serial=errand.get("serial"),
                  default_configuration=errand.get("configuration"), configurations=configurations,
                  prelim=prelim, static=static, tools=tools, quantities=quantities, plot=plot,
                  master_toml=file_config.get("master"), meta=dict(file_config.get("meta", {})), raw=raw, sweep_runs=sweep_on,
                  sweep_list=list(errand["sweep_runs"]) if isinstance(errand.get("sweep_runs"), list) else [],
                  families=families, form=form, stats=dict(stats), ranking=dict(ranking))


TEXT_KEYS = ("labels", "title", "title_left", "title_right", "legend_header", "x_label", "y_label", "legend")


def check_meta(meta: dict, where: str) -> None:
    """[config.meta] (V97): free keys for people; `versions` names packages of env/stack.toml, each
    with the version (a string) the file was run with. A misspelt package is refused, or its warning
    would never come; a version that differs is only a warning (tools.meta_notes), never a refusal."""
    versions = meta.get("versions", {})
    if not isinstance(versions, dict):
        raise HeimdallError("[config.meta].versions is a table: package = \"version\"", where=f"{where}.versions",
                       hint='versions = { pythia8 = "8.317", rivet = "4.1.3" }')
    known = list(plugins.load(heimdall_root() / "env" / "stack.py", "stack").entries())
    for name, version in versions.items():
        if name not in known:
            raise HeimdallError(f"'{name}' is not a package of env/stack.toml", where=f"{where}.versions",
                           hint=did_you_mean(name, known) or f"packages: {', '.join(known)}")
        if not isinstance(version, str):
            raise HeimdallError(f"{name}'s version is a string (\"8.317\"), so its digits stay as written", where=f"{where}.versions.{name}")


def no_tlatex(value, where: str) -> None:
    """V79 (B5, break and migrate): a label is LaTeX. One written in TLatex is refused, with the LaTeX
    for it (labels.natural, what heimdall migrate writes)."""
    from .labels import is_tlatex, natural
    for text in value if isinstance(value, list) else [value]:
        if isinstance(text, str) and is_tlatex(text):
            raise HeimdallError(f"'{text}' is TLatex; labels are LaTeX (see V65)", where=where,
                           hint=f"write '{natural(text)}', or run heimdall migrate on the file")


def _plot_texts(table: dict, where: str) -> None:
    for key in TEXT_KEYS:
        if key in table:
            no_tlatex(table[key], f"{where}.{key}")
    for name, sub in table.get("figures", {}).items() if isinstance(table.get("figures"), dict) else ():
        if isinstance(sub, dict):
            _plot_texts(sub, f"{where}.figures.{name}")
    if isinstance(table.get("data"), dict):
        _plot_texts(table["data"], f"{where}.data")


#: What [plot.figures] replaced (V81): the table, and what a file says instead.
FIGURE_TABLES = {"overlay": '[plot.figures.<name>] class = "overlay"', "object": '[plot.figures.<name>] objects = ["<glob>"]'}


def figure_tables(plot: dict) -> dict[str, tuple[dict, str]]:
    """The declared figures, key → (its table, where it was written)."""
    return {key: (table, f"[plot.figures.{key}]") for key, table in plot.get("figures", {}).items()}


#: The keys a [cluster.pre] or [cluster.finish] table may set: a job's resources (doc:scale).
CLUSTER_JOB_KEYS = ("time", "partition", "account", "qos", "constraint", "gres", "memory", "cpus", "sbatch")


def check_cluster(values, where: str) -> None:
    """[cluster] (V114), in an errand file, a configuration or a work dir's heimdall.toml: the schema's keys, and its
    pre and finish tables the resource keys only."""
    if not isinstance(values, dict):
        raise HeimdallError("[cluster] is a table", where=where)
    schema.check(values, "cluster", where)
    for job in ("pre", "finish"):
        if job in values:
            schema.check(values[job], "cluster", f"{where}.{job}", only=CLUSTER_JOB_KEYS)
    _one_line(values, where)


def _one_line(value, where: str) -> None:
    """Every [cluster] string is one line of a job script (an #SBATCH option, a setup line): a newline or another
    control character (a tab aside) would add a line of its own (V194)."""
    if isinstance(value, str) and any((ord(ch) < 32 and ch != "\t") or ord(ch) == 127 for ch in value):
        raise HeimdallError(f"{where} holds a control character (a newline?): each value is one line of the job script",
                       where=where, hint="split it into a list's entries, one line each")
    if isinstance(value, list):
        for i, item in enumerate(value):
            _one_line(item, f"{where}[{i}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            _one_line(item, f"{where}.{key}")


def check_stats(stats: dict, where: str) -> None:
    """[stats] (V168) against the schema, its reference a filter when a table."""
    if not isinstance(stats, dict):
        raise HeimdallError("[stats] is a table", where=where)
    schema.check(stats, "stats", where)
    _check_stats_metrics(stats, where)
    if isinstance(stats.get("reference"), dict):
        from .sweep import _filter_shape
        _filter_shape(stats["reference"], f"{where}.reference")


# ── a report's recipe ([report]) ─────────────────────────────────────────────────────────

#: What a report's section shows: exactly one of these (framework/schema/report.toml).
def check_ranking(ranking: dict, where: str, *, whole: bool = True) -> None:
    """[ranking] (or a set's `ranking`) against the schema; its metric, mean and threshold names against the registries."""
    if not isinstance(ranking, dict):
        raise HeimdallError("[ranking] is a table", where=where)
    schema.check(ranking, "ranking", where)
    from stats import means, metrics            # numpy loads here, only when a file has a [ranking]
    known = list(metrics.REGISTRY)

    def metric_name(name, at):
        if name not in metrics.REGISTRY:
            raise HeimdallError(f"no metric '{name}'", where=at, hint=did_you_mean(name, known) or "metrics: heimdall explain ranking")

    given = ranking.get("metrics")
    for name in (given if isinstance(given, list) else (given or {})):
        metric_name(name, f"{where}.metrics")
    if isinstance(given, dict):
        for name, weight in given.items():
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
                raise HeimdallError(f"the weight of '{name}' is a number of zero or more", where=f"{where}.metrics.{name}", hint=f"got {weight!r}")
    for name, pair in (ranking.get("thresholds") or {}).items():
        metric_name(name, f"{where}.thresholds")
        if (not isinstance(pair, list) or len(pair) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in pair)
                or pair[0] == pair[1]):
            raise HeimdallError(f"thresholds of '{name}' are [good, bad], two different numbers", where=f"{where}.thresholds.{name}", hint=f"got {pair!r}")
    for glob, weight in (ranking.get("weights") or {}).items():
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
            raise HeimdallError(f"the weight of '{glob}' is a number of zero or more", where=f"{where}.weights.{glob}", hint=f"got {weight!r}")
    mean = ranking.get("over_pages")
    if mean is not None and mean not in means.MEANS_BY_NAME:
        raise HeimdallError(f"no mean '{mean}'", where=f"{where}.over_pages", hint=did_you_mean(mean, means.MEANS_BY_NAME) or "means: heimdall explain ranking")


def _check_stats_metrics(stats: dict, where: str) -> None:
    names = stats.get("metrics")
    if names:
        from stats import metrics
        for name in names:
            if name not in metrics.REGISTRY:
                raise HeimdallError(f"no metric '{name}'", where=f"{where}.metrics", hint=did_you_mean(name, metrics.REGISTRY) or "metrics: heimdall explain ranking")


REPORT_ITEMS = ("pages", "compare", "stats", "bars", "files", "tools")
#: The statistics summary's sections (bars.summary_model): the leaderboard, a category (`category:<name>`), a metric (`<metric>`,
#: or `<metric>:<part>`) and the head to head. Names from before the ranking was rebuilt are refused with the name that replaced them.
SUMMARY = ("leaderboard", "marginals", "baseline", "head-to-head")
PARTS = ("ranking", "crossed", "table")
REPLACED = {"top5": "leaderboard", "scoreboard": "leaderboard", "scoreboard-cells": "leaderboard", "scoreboards": "leaderboard",
            "head-to-head-": "head-to-head"}


def check_stats_key(key: str, at: str) -> None:
    """One entry of a section's `stats`: `leaderboard`, `head-to-head`, `category:<name>`, or a metric with an optional part."""
    from stats import metrics
    statistic, _, part = key.partition(":")
    for old, new in REPLACED.items():
        if statistic == old or (old.endswith("-") and statistic.startswith(old)):
            raise HeimdallError(f"stats: '{key}' is now '{new}'", where=f"{at}.stats",
                                hint="the summary is ranked by category now: leaderboard, category:<name>, <metric>:ranking|table, head-to-head")
    if statistic == "area":
        raise HeimdallError("stats: 'area' is no longer a summary table", where=f"{at}.stats",
                            hint="its numbers are the area column of statistics.csv")
    if statistic == "category":
        if part not in metrics.CATEGORIES:
            raise HeimdallError(f"stats: no category '{part}'", where=f"{at}.stats",
                                hint=did_you_mean(part, metrics.CATEGORIES) or f"the categories: {', '.join(metrics.CATEGORIES)}")
        return
    if statistic in SUMMARY:
        if part:
            raise HeimdallError(f"stats: '{statistic}' has no parts", where=f"{at}.stats")
        return
    if statistic in metrics.REGISTRY:
        if part and part not in PARTS:
            raise HeimdallError(f"stats: no part '{part}' of {statistic}", where=f"{at}.stats",
                                hint=f"its parts: {', '.join(f'{statistic}:{p}' for p in PARTS)}")
        return
    raise HeimdallError(f"stats: no section {key!r}", where=f"{at}.stats",
                        hint=did_you_mean(statistic, [*SUMMARY, *metrics.REGISTRY]) or f"the sections: {', '.join(SUMMARY)}, category:<name>, <metric>")


#: An errand file's [report] says neither: each folder is its own report's source, built where results/ has it (V209).
NOT_IN_A_RUN = ("from", "output")


#: A report title's placeholders before the Assignment/Errand names → today's ([source]'s keys).
OLD_PLACEHOLDERS = {"project": "assignment", "run": "errand"}


def check_report(table, where: str, run_toml: bool = False) -> None:
    """[report], a report's recipe (V209): every key against schema/report.toml, each [[report.section]]
    titled and showing one item, its stats keys known and its plot keys checked as [plot]'s. An errand file's
    names neither from nor output: each of its folders is its report's source, and is built where it is."""
    if not isinstance(table, dict):
        raise HeimdallError("[report] is a table", where=where)
    schema.check(table, "report", where)
    if "accent" in table and not re.fullmatch(r"#[0-9A-Fa-f]{6}", table["accent"]):
        raise HeimdallError(f"accent is a colour as #rrggbb, not {table['accent']!r}", where=f"{where}.accent", hint='accent = "#2a78d6"')
    for key in ("title", "subtitle"):                                   # the old names
        for old, new in OLD_PLACEHOLDERS.items():
            if isinstance(table.get(key), str) and "{" + old + "}" in table[key]:
                raise HeimdallError(f"{{{old}}} is now {{{new}}}", where=f"{where}.{key}", hint=v3.NAMES_HINT)
    for key, most in (("size", 12), ("columns", 4)):
        if key in table and table[key] > most:
            raise HeimdallError(f"{key} is at most {most}, not {table[key]}", where=f"{where}.{key}")
    for key in NOT_IN_A_RUN if run_toml else ():
        if key in table:
            raise HeimdallError(f"an errand file's [report] takes no {key}: each folder it writes is its report's source, "
                           "built into reports/ where results/ has it", where=f"{where}.{key}",
                           hint="a recipe of its own (configs/<A>/<E>.toml, [report] alone) takes from and output")
    for number, section in enumerate(table.get("section", []), 1):
        at = f"{where} section {number}"
        schema.check(section, "section", at)
        if "title" not in section:
            raise HeimdallError("a section needs a title", where=at)
        kinds = [k for k in REPORT_ITEMS if k in section]
        if len(kinds) != 1:
            raise HeimdallError(f"a section shows one of {', '.join(REPORT_ITEMS)}" + (f", not {' and '.join(kinds)}" if kinds else ""),
                           where=at, hint='pages = ["d01-*"], or stats = ["leaderboard"], …')
        for key in section.get("stats", []):
            check_stats_key(key, at)
        if "plot" in section:
            if kinds[0] not in ("pages", "stats", "bars"):
                raise HeimdallError(f"plot is a pages, stats or bars section's: the [plot] keys its pages or numbers are drawn with, "
                               f"not a {kinds[0]} section's", where=f"{at}.plot")
            check_plot(section["plot"], f"{at}.plot")
        if "hide" in section and "tools" not in section:
            raise HeimdallError("hide is a tools section's: the varied lines it leaves out", where=f"{at}.hide")


def report_of(table: dict, path: Path, assignment: str, where: str, chain: tuple[Path, ...] = ()) -> tuple[dict, list[Path]]:
    """[report] with its template laid under it (V209): `template` names a recipe as [config].import names a file
    (a bare name beside the file naming it, <A>/<E> another assignment's, ./… the work dir's; .toml optional), whose keys this
    table's replace and whose sections come first; a template naming its own is followed, a circle refused.
    The table (without template), and the templates read."""
    named = table.get("template")
    if not named:
        return dict(table), []
    at = f"{where}.template"
    try:
        source = _import_path(named, assignment, at, path.parent)
    except HeimdallError:
        raise HeimdallError(f"no report template '{named}'", where=at,
                       hint="a bare name is beside the file naming it; <A>/<E> another assignment's; ./… the work dir's") from None
    chain = chain or (path.resolve(),)
    if source.resolve() in chain:
        raise HeimdallError("report templates go round in a circle: " + " → ".join(p.name for p in (*chain, source.resolve())), where=at)
    data = _toml(source)
    if set(data) != {"report"}:
        raise HeimdallError("a report's template is a recipe: a file with a [report] table and nothing else", where=str(source),
                       hint=f"its tables: {', '.join(data) or '(none)'}")
    check_report(data["report"], f"{source}: [report]")
    below, read = report_of(data["report"], source, _assignment_of(source, data, assignment), f"{source}: [report]",
                            (*chain, source.resolve()))
    merged = {k: v for k, v in below.items() if k != "section"}
    merged.update({k: v for k, v in table.items() if k not in ("section", "template")})
    sections = [*below.get("section", []), *table.get("section", [])]
    if sections:
        merged["section"] = sections
    return merged, [source.resolve(), *(p for p in read if p != source.resolve())]


#: Plot backends that were, and what draws their pages now (as a backend value).
RETIRED_BACKENDS = {"yoda": '"mpl"', "both": '["root", "mpl"]'}


def check_plot(plot: dict, where: str, strict: bool = True) -> None:
    """[plot] and its figures against the schema, when the file is read (C11, V55): every key, type and
    bound of [plot], [plot.data], [plot.across_from] and [plot.figures.<figure>]. What needs the style (base.toml), the
    objects or a backend is plot.validate's and plot.pages'."""
    for old, new in FIGURE_TABLES.items():                 # break and migrate (V81)
        if old in plot:
            raise HeimdallError(f"[plot.{old}] is a figure now: {new} (see V81)", where=f"{where}.{old}",
                           hint="heimdall migrate rewrites it")
    chosen = plot.get("backend")
    for name in [chosen] if isinstance(chosen, str) else chosen if isinstance(chosen, list) else ():
        if name in RETIRED_BACKENDS:                       # rivet-mkhtml's pages are mpl's now
            raise HeimdallError(f'backend = "{name}" is retired: mpl draws the pages rivet-mkhtml did', where=f"{where}.backend",
                           hint=f'backend = {RETIRED_BACKENDS[name]}; heimdall migrate rewrites it')
    if strict:
        _plot_texts(plot, where)
    schema.check(plot, "plot", where)
    schema.check(plot.get("data", {}), "data", f"{where}.data")
    schema.check(plot.get("across_from") or {}, "across_from", f"{where}.across_from")   # V224: as [from] is
    if plot.get("sets") and plot["sets"] != schema.DEFAULT:                 # V159, V163: their shapes, when read
        set_entries(plot["sets"], f"{where}.sets")
    if plot.get("across"):                                                 # V169: the sets across the runs
        set_entries(plot["across"], f"{where}.across")
    for quantity, looks in (plot.get("looks") or {}).items():               # V171: a value's look, by its tag
        if not isinstance(looks, dict):
            raise HeimdallError(f"[plot.looks.{quantity}] is a table: tag = \"#rrggbb\" or {{ colour, line, width }}",
                           where=f"{where}.looks.{quantity}")
        for tag, look in looks.items():
            check_curve_style({"colour": look} if isinstance(look, (str, int)) else look, f"{where}.looks.{quantity}.{tag}")
    for key, (table, written) in figure_tables(plot).items():
        at = f"{where.removesuffix(': [plot]')}: {written}"
        if not isinstance(table, dict):
            raise HeimdallError("a figure is a table", where=at)
        schema.check(table, "figure", at)
        kind, objects, labels = table.get("class", "defined"), table.get("objects"), table.get("labels")
        if table.get("sets") and table["sets"] != schema.DEFAULT and kind not in ("merged", "scan", "compare"):
            set_entries(table["sets"], f"{at}.sets")
        y = table.get("y", "")
        if kind == "sheet":                                # V89: pages laid out, as drawn
            if not table.get("pages"):
                raise HeimdallError("a sheet needs pages = [\"<cell>/<page>\", …]: globs of the pages it lays out",
                               where=f"{at}.pages", hint='pages = ["*/d02-x01-y01"]: that object in every cell')
            extra = sorted(set(table) - {"class", "name", "pages", "columns"})
            if extra:
                raise HeimdallError(f"a sheet takes no {extra[0]}: it lays out pages as their figures drew them", where=f"{at}.{extra[0]}",
                               hint="set it on the figure whose pages the sheet shows")
            continue
        if "pages" in table or "columns" in table:
            raise HeimdallError(f"a {kind} figure draws pages: pages and columns are a sheet's", where=at, hint='class = "sheet"')
        if (kind == "metric") != ("metric" in table) or ("sort" in table and kind != "metric"):   # V160
            raise HeimdallError("a metric figure needs metric = \"chi2_ndf\" | …" if kind == "metric"
                           else f"metric and sort are a metric figure's, not a {kind} figure's",
                           where=f"{at}.metric", hint='class = "metric", metric = "chi2_ndf", objects = ["d01-*"]')
        if kind == "metric":
            extra = sorted(set(table) & {"labels", "over", "op", "x", "y", "configurations", "band", "ratio", "normalise"})
            if extra:
                raise HeimdallError(f"a metric figure takes no {extra[0]}: its page is a number per point", where=f"{at}.{extra[0]}")
        if kind in ("merged", "scan", "compare") and {"sets", "split"} & set(table):     # V159
            own = sorted({"sets", "split"} & set(table))[0]
            raise HeimdallError(f"a {kind} figure pages by plot_points: {own} is a defined or overlay figure's (or [plot]'s)",
                           where=f"{at}.{own}", hint="its members are groups the figure makes, not the run's points")
        if (kind == "scan") != ("x" in table or "y" in table):
            raise HeimdallError("x and y are a scan figure's" if kind != "scan" else "a scan figure needs x and y",
                           where=at, hint='class = "scan", x = "<swept quantity>", y = "sigma"')
        if kind == "scan":
            if "x" not in table or not re.fullmatch(r"sigma|entries|integral|mean|bin:[1-9][0-9]*", y):
                raise HeimdallError(f"a scan figure needs x, and y one of sigma, entries, integral, mean, bin:N (not {y!r})",
                               where=f"{at}.y", hint='y = "sigma"; y = "bin:3", objects = ["d01-x01-y01"]')
        counted = kind == "scan" and table.get("y") in ("sigma", "entries")
        if not objects and not counted:
            raise HeimdallError("a figure needs objects = [\"d02-x01-y01\", …]: the objects its pages are made of",
                           where=f"{at}.objects")
        objects = objects or []
        if kind == "scan":
            if len(objects) > 1 or (not counted and y != "entries" and len(objects) != 1):
                raise HeimdallError(f"y = \"{y}\" reads one object, and the figure names {len(objects)}", where=f"{at}.objects")
            if "labels" in table:
                raise HeimdallError("a scan figure takes no labels", where=f"{at}.labels",
                               hint="its curves are the other curve axes' values, labelled by them")
        if kind == "defined":
            for own in ("labels", "name"):
                if own in table:
                    raise HeimdallError(f"a defined figure takes no {own}", where=f"{at}.{own}",
                                   hint="its pages are the objects' own, named and labelled as the analysis has them; "
                                        "class = \"overlay\" draws several objects on one page")
        if kind != "compare" and "configurations" in table:
            raise HeimdallError(f"a {kind} figure draws one configuration's points: configurations is a compare figure's",
                           where=f"{at}.configurations", hint='class = "compare"')
        if kind == "compare" and labels is not None:
            count = len(table.get("configurations", [])) or None
            if count is not None and len(labels) != count:
                raise HeimdallError(f"a compare figure's labels give one label per configuration ({count})", where=f"{at}.labels")
        if (kind == "derived") != ("op" in table):
            raise HeimdallError("op = \"ratio\" | … is a derived figure's, and it needs one" if kind == "derived"
                           else f"a {kind} figure derives nothing: op is a derived figure's", where=f"{at}.op",
                           hint='class = "derived", op = "ratio", objects = ["d11-x01-y01", "d12-x01-y01"]')
        if kind == "derived":
            wanted = 1 if table["op"].startswith("projection") else 2
            if len(objects) != wanted:
                raise HeimdallError(f"op = \"{table['op']}\" takes {wanted} object{'s' if wanted > 1 else ''}, not {len(objects)}",
                               where=f"{at}.objects")
            if "labels" in table:
                raise HeimdallError("a derived figure takes no labels", where=f"{at}.labels",
                               hint="its object is drawn as any object: its curves are the points")
        if kind == "merged" and "labels" in table:
            raise HeimdallError("a merged figure takes no labels", where=f"{at}.labels",
                           hint="its pages are the objects' own, their curves the merged groups")
        if (kind == "merged") != bool(table.get("over")):
            raise HeimdallError("over = [\"<quantity>\", …] is a merged figure's, and it needs one" if kind == "merged"
                           else f"a {kind} figure merges nothing: over is a merged figure's",
                           where=f"{at}.over", hint='class = "merged", over = ["replica"]: the points merged over replica')
        if kind != "compare" and labels is not None and len(labels) != len(objects):
            raise HeimdallError(f"labels must give one label per object ({len(objects)})", where=f"{at}.labels")

