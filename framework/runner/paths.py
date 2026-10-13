"""Where things are, and how a name in a config becomes a path (rank 0).

docs/04_Config_Reference.md §2; docs/framework/01_Target.md §5.2–5.3. Three roots:

* **Heimdall** (`hep_root()`): the framework, as git has it. Always the one this code runs from; a
  `$HEP` that names another is refused.
* **the machine root** (`machine_root()`, `$HEP_MACHINE`, by default ~/Himinbjorg): what this machine
  built — the stack, the venv, Heimdall's compiled apps, downloads and builds (docs/audit_3/02 §3).
* **the work dir** (`work_root()`): configs, modules, datasets and what runs make. `$HEP_WORK`, or the
  first folder up from the working directory whose `hep.toml` has a `[work]` table (as git finds its
  repository). Markers under Heimdall's `tests/` are skipped: the tests' fixture is found only
  through `$HEP_WORK`.

Every key that takes a path has exactly one convention root: there is no search path and no
fallback, because a lookup that tries several places is how v1's 00/B18 happened.

    bare `name`     → the convention root of the key + name
    `./sub/name`    → the work dir + sub/name (not the working directory: V13)
    `/abs/path`     → as written
    `../x`          → refused; write ./… instead
"""

from __future__ import annotations

import functools
import os
import tomllib
from pathlib import Path

from .errors import HepError

#: A folder is Heimdall when it holds all of these.
MARKERS = ("framework/runner", "framework/tools", "framework/schema/run.toml")
#: A work dir's marker: a hep.toml with a [work] table.
MARKER_FILE = "hep.toml"

HEP_VAR = "HEP"
WORK_VAR = "HEP_WORK"
RESULTS_VAR = "HEP_RESULTS"
RECORDS_VAR = "HEP_RECORDS"
LOGS_VAR = "HEP_LOGS"
CACHE_VAR = "HEP_CACHE"
DECKS_VAR = "HEP_DECKS"
CONFIGS_VAR = "HEP_CONFIGS"
REPORTS_VAR = "HEP_REPORTS"

#: High-Energy's variables (K15): a shell that still sets one is refused, with its replacement named.
RETIRED = {"HEKIT_ROOT": "HEP", "HEKIT_CONFIGS": "HEP_CONFIGS", "HEKIT_OUTPUT": "HEP_RECORDS and HEP_LOGS",
           "HEKIT_RESULTS": "HEP_RESULTS", "HEKIT_REPORTS": "HEP_REPORTS",
           "HEP_OUTPUT": "HEP_RECORDS, HEP_LOGS and HEP_CACHE: output/ is split by lifecycle"}


def check_retired() -> None:
    """Refuse a retired variable: a stale shell or script fails loudly, not silently."""
    for old, new in RETIRED.items():
        if os.environ.get(old):
            raise HepError(f"${old} is set, and it is retired: Heimdall reads ${new}",
                           hint=f"unset {old} (a shell still loaded with High-Energy's environment?)")


def is_heimdall(path: Path) -> bool:
    return all((path / marker).exists() for marker in MARKERS)


@functools.cache
def hep_root() -> Path:
    """Heimdall: where this code is (framework/runner/paths.py, two levels up)."""
    root = Path(__file__).resolve().parents[2]
    if not is_heimdall(root):
        raise HepError(f"{root} is not a Heimdall", hint=f"it must contain {', '.join(MARKERS)}")
    given = os.environ.get(HEP_VAR)
    if given and Path(given).expanduser().resolve() != root:
        raise HepError(f"two Heimdalls: ${HEP_VAR} is {given}, this is {root}",
                       hint="source the setup.sh of the one you mean")
    return root


#: hep.toml's tables and keys (docs/framework/01_Target.md §4.2): any other is refused. [cluster] is the
#: machine's defaults for hep cluster (V114): its keys are the run TOML's, checked by cluster.py.
WORK_KEYS = {"work": ("name",), "framework": ("expects",)}
WORK_TABLES = ("cluster",)


def work_meta(root: Path) -> dict:
    """A work dir's hep.toml, checked: its name ([work] name, else the folder's), [framework] expects, and
    [cluster] as written."""
    marker = root / MARKER_FILE
    try:
        data = tomllib.loads(marker.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HepError(f"cannot read {marker}: {error}") from None
    known = ", ".join([*(f"[{table}] {' '.join(keys)}" for table, keys in WORK_KEYS.items()),
                       *(f"[{table}]" for table in WORK_TABLES)])
    for table, value in data.items():
        if table in WORK_TABLES and isinstance(value, dict):
            continue
        if table not in WORK_KEYS or not isinstance(value, dict):
            raise HepError(f"unknown table '{table}'", where=str(marker), hint=f"hep.toml has {known}")
        for key, item in value.items():
            if key not in WORK_KEYS[table]:
                raise HepError(f"unknown key '{table}.{key}'", where=str(marker), hint=f"hep.toml has {known}")
            if not isinstance(item, str):
                raise HepError(f"'{table}.{key}' must be a string, got {item!r}", where=str(marker))
    return {"name": data.get("work", {}).get("name") or root.name,
            "expects": data.get("framework", {}).get("expects", ""),
            "cluster": dict(data.get("cluster", {}))}


def is_work(path: Path) -> bool:
    """A work dir: a hep.toml with a [work] table."""
    marker = path / MARKER_FILE
    if not marker.is_file():
        return False
    try:
        return isinstance(tomllib.loads(marker.read_text(encoding="utf-8")).get("work"), dict)
    except (OSError, tomllib.TOMLDecodeError):
        return False


@functools.cache
def _search(start: str) -> Path | None:
    tests = hep_root() / "tests"
    for candidate in [Path(start), *Path(start).parents]:
        if candidate.is_relative_to(tests):
            continue
        if is_work(candidate):
            return candidate
    return None


def find_work(start: Path | None = None) -> Path | None:
    """The work dir: $HEP_WORK, or the walk up from `start` (the working directory); None outside one."""
    given = os.environ.get(WORK_VAR)
    if given:
        root = Path(given).expanduser().resolve()
        if not is_work(root):
            raise HepError(f"${WORK_VAR} = {root} is not a work dir",
                           hint=f"a work dir has a {MARKER_FILE} with a [work] table: hep setup <dir>")
        return root
    return _search(str((start or Path.cwd()).resolve()))


def work_root() -> Path:
    root = find_work()
    if root is None:
        raise HepError("not inside a work dir", where=str(Path.cwd()),
                       hint="cd into one, or make one: hep setup <dir>")
    return root


def reset() -> None:
    """Forget the cached search (tests that make and move work dirs, or tool folders)."""
    _search.cache_clear()
    hep_root.cache_clear()
    _tool_chains.cache_clear()


def _rooted(var: str, name: str) -> Path:
    value = os.environ.get(var)
    return Path(value).resolve() if value else work_root() / name


def results_root() -> Path:
    """Where products go: $HEP_RESULTS (tests set it) or <work>/results."""
    return _rooted(RESULTS_VAR, "results")


def records_root() -> Path:
    """What runs recorded, precious (U21): each point's provenance, identity and .complete, a
    configuration's points.json and cluster submissions. $HEP_RECORDS (tests set it) or <work>/records;
    `hep clean` leaves it unless told --records."""
    return _rooted(RECORDS_VAR, "records")


def logs_root() -> Path:
    """Ephemeral: each point's working folder (cards, configs, logs, FIFOs, scratch files, the context
    file), journals, page documents. $HEP_LOGS (tests set it) or <work>/logs."""
    return _rooted(LOGS_VAR, "logs")


def cache_root() -> Path:
    """Derived, rebuilt on demand: prepare caches, card checks, converted reference data. $HEP_CACHE
    (tests set it) or <work>/.cache."""
    return _rooted(CACHE_VAR, ".cache")


def reports_root() -> Path:
    """Where decks go (docs/reporter): $HEP_REPORTS (tests set it) or <work>/reports."""
    return _rooted(REPORTS_VAR, "reports")


def dataset_listed(path: Path) -> bool:
    """Whether the work dir's datasets.toml lists this file of datasets/ (U23: hep setup fetches it)."""
    import tomllib
    work = find_work()
    manifest = work / "datasets.toml" if work is not None else None
    try:
        files = tomllib.loads(manifest.read_text(encoding="utf-8")).get("files", {}) if manifest and manifest.is_file() else {}
        return Path(path).resolve().relative_to((work / "datasets").resolve()).as_posix() in files
    except (ValueError, OSError, tomllib.TOMLDecodeError):
        return False


def decks_root() -> Path:
    """Where decks are written (U22): decks/<deck>/{deck.md, deck.toml, extras}, tracked; they build into
    reports/<deck>/. $HEP_DECKS (tests set it) or <work>/decks."""
    return _rooted(DECKS_VAR, "decks")


def configs_root() -> Path:
    """Where run TOMLs and their cards are: $HEP_CONFIGS or <work>/configs."""
    return _rooted(CONFIGS_VAR, "configs")


def work_build() -> Path:
    """The work dir's compiled things: module programs, Rivet/, deps/, flags.mk."""
    return work_root() / "build"


def datasets_root() -> Path:
    return work_root() / "datasets"


STACK_VAR = "HEP_STACK"
MACHINE_VAR = "HEP_MACHINE"
#: The machine root when $HEP_MACHINE is not set (the user's choice, 2026-10-12: Heimdall's hall).
DEFAULT_MACHINE = "~/Himinbjorg"


def machine_root() -> Path:
    """What this machine built, apart from the checkout: $HEP_MACHINE, else ~/Himinbjorg."""
    return Path(os.environ.get(MACHINE_VAR) or DEFAULT_MACHINE).expanduser()


def machine_file() -> Path:
    """This machine's settings: <machine root>/machine.toml (recipes/machine.template.toml says what)."""
    return machine_root() / "machine.toml"


def machine_settings() -> dict:
    """machine.toml's tables ({} when there is none): [settings], [env] and [packages.<name>] are the
    stack build's (recipes/build_stack.py), [cluster] is hep cluster's defaults for every work dir."""
    file = machine_file()
    try:
        return tomllib.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HepError(f"cannot read this machine's settings: {error}", where=str(file)) from None


def stack_dir() -> Path:
    """The loaded stack's base: the machine root, or its stacks/<toolkit>/ for an isolated toolkit's
    (setup.sh sets $HEP_STACK; recipes/README.md §6). Its compiled apps and builds go with it: they
    are linked against that stack."""
    name = os.environ.get(STACK_VAR)
    return machine_root() / "stacks" / name if name else machine_root()


def apps_dir() -> Path:
    """Heimdall's compiled apps (App_*.exe, Paint.exe) and Herwig's repository, for the loaded stack."""
    return Path(os.environ["HEP_APPS"]) if os.environ.get("HEP_APPS") else stack_dir() / "apps"


def forge_dir() -> Path:
    """Builds in progress for the loaded stack: make/ (Heimdall's intermediates), tests/, scratch/."""
    return Path(os.environ["HEP_FORGE"]) if os.environ.get("HEP_FORGE") else stack_dir() / "forge"


def tool_roots() -> list[tuple[str, Path]]:
    """Where tool folders are, nearest first (docs/audit_3/04_Extending.md §2): the work dir's tools/
    ("work"), the machine root's tools/ ("machine"), Heimdall's framework/tools/ ("shipped")."""
    out = []
    work = find_work()
    if work is not None:
        out.append(("work", work / "tools"))
    out.append(("machine", machine_root() / "tools"))
    out.append(("shipped", hep_root() / "framework" / "tools"))
    return out


def tool_chains() -> dict[str, list[tuple[str, Path]]]:
    """Each tool folder's name → the folders that make it, nearest first: the first folder of that name on
    the search path (tool_roots), then, when its tool.toml says extends = "<name>", the chain of <name>
    (of its own name: the next folder of it down the path). A nearer folder without extends replaces a
    farther one whole."""
    return _tool_chains(tuple((origin, str(root)) for origin, root in tool_roots()))


@functools.cache
def _tool_chains(roots: tuple[tuple[str, str], ...]) -> dict[str, list[tuple[str, Path]]]:
    found: dict[str, list[tuple[str, Path]]] = {}
    for origin, root in roots:
        for folder in sorted(Path(root).iterdir()) if Path(root).is_dir() else ():
            if folder.is_dir() and not folder.name.startswith((".", "_")):
                found.setdefault(folder.name, []).append((origin, folder))

    def chain(name: str, level: int, seen: tuple[Path, ...]) -> list[tuple[str, Path]]:
        places = found.get(name, [])
        if level >= len(places):
            below = f" below {places[-1][1]}" if places else ""
            raise HepError(f"no tool folder '{name}'{below} to extend", where=str(seen[-1] / "tool.toml"),
                           hint="tool folders: " + ", ".join(sorted(found)))
        origin, folder = places[level]
        if folder in seen:
            raise HepError("tool folders extend each other in a circle: "
                           + " → ".join(f.name for f in (*seen, folder)), where=str(folder / "tool.toml"))
        spec_file = folder / "tool.toml"
        extends = None
        if spec_file.is_file():
            try:
                extends = tomllib.loads(spec_file.read_text(encoding="utf-8")).get("extends")
            except tomllib.TOMLDecodeError as error:
                raise HepError(f"not valid TOML: {error}", where=str(spec_file)) from None
        if extends is None:
            return [(origin, folder)]
        if not isinstance(extends, str):
            raise HepError("extends names one tool folder", where=str(spec_file))
        return [(origin, folder), *chain(extends, level + 1 if extends == name else 0, (*seen, folder))]

    return {name: chain(name, 0, ()) for name in found}


def placeholders() -> dict[str, str]:
    """{hep}, {apps} and {work} (docs/framework/01_Target.md §5.3); {work} only inside a work dir."""
    out = {"hep": str(hep_root()), "apps": str(apps_dir())}
    work = find_work()
    if work is not None:
        out["work"] = str(work)
    return out


def portable(path) -> str:
    """A path as an identity records it: under a known root, written with that root's placeholder, so
    a point's identity does not change when Heimdall, the machine root or a work dir moves."""
    text = str(path)
    roots = [("{apps}", apps_dir()), ("{machine}", machine_root()), ("{hep}", hep_root())]
    work = find_work()
    if work is not None:
        roots.insert(0, ("{work}", work))
    for name, root in roots:
        root = str(root)
        if text == root or text.startswith(root + "/"):
            return name + text[len(root):]
    return text


def unportable(text: str) -> str:
    """A path portable() wrote, under today's roots ({work}, {hep}, {apps}, {machine}); anything else as
    it is (a record written before, with absolute paths)."""
    roots = {"{apps}": apps_dir, "{machine}": machine_root, "{hep}": hep_root, "{work}": work_root}
    for name, root in roots.items():
        if text == name or text.startswith(name + "/"):
            return str(root()) + text[len(name):]
    return text


#: Keys whose root is the point's own directory: resolve() is always given it (`root=`).
POINT_KEYS = ("prelim", "input", "output")

#: The convention root of each path-taking key, as a function of the project (04 §2).
ROOTS = {
    "config":     lambda project: configs_root(),
    "master":     lambda project: configs_root() / project,
    "import":     lambda project: configs_root() / project,
    "baseconfig": lambda project: configs_root() / project,
    "executable": lambda project: work_build() / project,
    "data":       lambda project: datasets_root(),
    "filters":    lambda project: configs_root() / project,
    "root_style": lambda project: configs_root() / project,
}


def resolve(value: str, key: str, *, project: str = "", root: Path | None = None,
            where: str | None = None) -> Path:
    """The path a config value names, under the rules above.

    `root` overrides the convention root (the runner passes a point's directory for `[prelim]`
    names and outputs); otherwise `key` picks it from ROOTS.
    """
    if not isinstance(value, str) or not value:
        raise HepError(f"expected a path, got {value!r}", where=where)
    if value.startswith("../") or value == ".." or "/../" in value:
        raise HepError(f"'{value}' climbs out of its root", where=where,
                       hint="write it relative to the work dir as ./…, or give an absolute path")
    if value.startswith("/"):
        return Path(value)
    if value.startswith("./"):
        return work_root() / value[2:]
    if root is None:
        if key in POINT_KEYS:
            raise HepError(f"'{key}' paths are under a point's directory, which was not given", where=where)
        if key not in ROOTS:
            raise HepError(f"no convention root for key '{key}'", where=where)
        root = ROOTS[key](project)
    return root / value


def config_file(name: str) -> Path:
    """`hep run <config>`: configs/<config>, `.toml` optional, unless it starts with ./ or /."""
    path = resolve(name, "config")
    if path.suffix != ".toml" and not path.exists():
        path = path.with_name(path.name + ".toml")
    if not path.is_file():
        raise HepError(f"no run config '{name}'", where=str(path),
                       hint="configs are looked up under configs/<Project>/<name>.toml; "
                            "start the name with ./ to give a path from the work dir")
    return path
