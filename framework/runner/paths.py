"""Where things are, and how a name in a config becomes a path (rank 0).

doc:paths; doc:layout Three roots:

* **Heimdall** (`heimdall_root()`): the framework, as git has it. Always the one this code runs from; a
  `$HEIMDALL` that names another is refused.
* **the machine root** (`machine_root()`, `$HEIMDALL_MACHINE`, by default ~/Himinbjorg): what this machine
  built — the stack, the venv, Heimdall's compiled apps, downloads and builds.
* **the work dir** (`work_root()`): configs, modules, datasets and what runs make. `$HEIMDALL_WORK`, or the
  first folder up from the working directory whose `heimdall.toml` has a `[work]` table (as git finds its
  repository). Markers under Heimdall's `tests/` are skipped: the tests' fixture is found only
  through `$HEIMDALL_WORK`.

Every key that takes a path has exactly one convention root: there is no search path and no
fallback, because a lookup that tries several places is how one of v1's bugs happened.

    bare `name`     → the convention root of the key + name
    `./sub/name`    → the work dir + sub/name (not the working directory: V13)
    `/abs/path`     → as written
    `../x`          → refused; write ./… instead
"""

from __future__ import annotations

import contextlib
import functools
import os
import re
import tomllib
from pathlib import Path

from .errors import HeimdallError, did_you_mean

#: A folder is Heimdall when it holds all of these.
MARKERS = ("framework/runner", "framework/tools", "framework/schema/run.toml")
#: A work dir's marker: a heimdall.toml with a [work] table.
MARKER_FILE = "heimdall.toml"

HEIMDALL_VAR = "HEIMDALL"
WORK_VAR = "HEIMDALL_WORK"
RESULTS_VAR = "HEIMDALL_RESULTS"
RECORDS_VAR = "HEIMDALL_RECORDS"
CACHE_VAR = "HEIMDALL_CACHE"
CONFIGS_VAR = "HEIMDALL_CONFIGS"
REPORTS_VAR = "HEIMDALL_REPORTS"

#: High-Energy's variables (K15): a shell that still sets one is refused, with its replacement named.
#: Heimdall's environment before its names moved (V213): each is HEIMDALL_<X> now.
OLD_NAMES = ("HEP", "HEP_MACHINE", "HEP_INSTALL", "HEP_BASE", "HEP_STACK", "HEP_STACK_REQUEST", "HEP_VENV", "HEP_APPS",
             "HEP_FORGE", "HEP_WORK", "HEP_CONFIGS", "HEP_RESULTS", "HEP_RECORDS", "HEP_CACHE", "HEP_REPORTS", "HEP_RUNS",
             "HEP_WORKDIRS", "HEP_ENV_LOADED", "HEP_CONTEXT", "HEP_STATUS_FD", "HEP_MAKELIBS_JOBS", "HEP_DETACH",
             "HEP_CLUSTER_JOB", "HEP_BUILD_SH", "HEP_PLAIN")
RETIRED = {"HEKIT_ROOT": "HEIMDALL", "HEKIT_CONFIGS": "HEIMDALL_CONFIGS", "HEKIT_OUTPUT": "HEIMDALL_RECORDS",
           "HEKIT_RESULTS": "HEIMDALL_RESULTS", "HEKIT_REPORTS": "HEIMDALL_REPORTS",
           "HEP_OUTPUT": "HEIMDALL_RECORDS and HEIMDALL_CACHE: output/ is split by lifecycle",
           "HEP_LOGS": "HEIMDALL_RECORDS: a point's logs live in records/<A>/<E>/<R>/logs/",
           **{old: "HEIMDALL" + old[3:] for old in OLD_NAMES}}


def check_retired() -> None:
    """Refuse a retired variable: a stale shell or script fails loudly, not silently."""
    for old, new in RETIRED.items():
        if os.environ.get(old):
            raise HeimdallError(f"${old} is set, and it is retired: Heimdall reads ${new}",
                                hint=f"unset {old}, or load Heimdall's environment again (gjallarhorn): its names moved, "
                                     "hep → heimdall" if old in OLD_NAMES else f"unset {old} (a shell still loaded with "
                                     "High-Energy's environment?)")


def is_heimdall(path: Path) -> bool:
    return all((path / marker).exists() for marker in MARKERS)


@functools.cache
def heimdall_root() -> Path:
    """Heimdall: where this code is (framework/runner/paths.py, two levels up)."""
    root = Path(__file__).resolve().parents[2]
    if not is_heimdall(root):
        raise HeimdallError(f"{root} is not a Heimdall", hint=f"it must contain {', '.join(MARKERS)}")
    given = os.environ.get(HEIMDALL_VAR)
    if given and Path(given).expanduser().resolve() != root:
        raise HeimdallError(f"two Heimdalls: ${HEIMDALL_VAR} is {given}, this is {root}",
                       hint="source the gjallarhorn.sh of the one you mean")
    return root


#: heimdall.toml's tables and keys (doc:layout): any other is refused. [cluster] is the
#: machine's defaults for heimdall cluster (V114): its keys are the errand file's, checked by cluster.py.
WORK_KEYS = {"work": ("name",), "framework": ("expects",), "run": ("keep", "log")}
#: What a point's logs keep (V201), `[run] log` in heimdall.toml or machine.toml (the work dir's over the machine's):
#: a digest's first and last lines, the earlier attempts kept with their digests and cards and with their whole
#: logs, and a detached worker's progress line every so many seconds.
LOG_DEFAULTS = {"head": 100, "tail": 200, "digests": 9, "full": 3, "worker_every": 600}
#: What a run keeps beyond records/ and results/ (V149); by default nothing more than a finished point's cards
#: and configs, each tool's digest (V201), and the prepare caches.
KEEP_WORDS = {"logs": "every tool's whole output (records/<A>/<E>/<R>/logs/<point>/<tag>.full.log; its digest, <tag>.log, always)",
              "journal": "every status event (status.jsonl, for heimdall watch --file)",
              "work": "a finished point's whole working folder (scratch files, shards, what its tools left)",
              "cache": "card checks, converted reference data, the plot stage's working files and skip markers"}
WORK_TABLES = ("cluster",)


def work_meta(root: Path) -> dict:
    """A work dir's heimdall.toml, checked: its name ([work] name, else the folder's), [framework] expects, and
    [cluster] as written."""
    marker = root / MARKER_FILE
    try:
        data = tomllib.loads(marker.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HeimdallError(f"cannot read {marker}: {error}") from None
    known = ", ".join([*(f"[{table}] {' '.join(keys)}" for table, keys in WORK_KEYS.items()),
                       *(f"[{table}]" for table in WORK_TABLES)])
    for table, value in data.items():
        if table in WORK_TABLES and isinstance(value, dict):
            continue
        if table not in WORK_KEYS or not isinstance(value, dict):
            raise HeimdallError(f"unknown table '{table}'", where=str(marker), hint=f"heimdall.toml has {known}")
        for key, item in value.items():
            if key not in WORK_KEYS[table]:
                raise HeimdallError(f"unknown key '{table}.{key}'", where=str(marker), hint=f"heimdall.toml has {known}")
            if (table, key) == ("run", "keep"):
                keep_words(item, f"{marker}: [run] keep")
            elif (table, key) == ("run", "log"):
                log_values(item, f"{marker}: [run] log")
            elif not isinstance(item, str):
                raise HeimdallError(f"'{table}.{key}' must be a string, got {item!r}", where=str(marker))
    return {"name": data.get("work", {}).get("name") or root.name,
            "expects": data.get("framework", {}).get("expects", ""),
            "cluster": dict(data.get("cluster", {})),
            "keep": sorted(keep_words(data.get("run", {}).get("keep", []), f"{marker}: [run] keep")),
            "log": log_values(data.get("run", {}).get("log", {}), f"{marker}: [run] log")}


def log_values(given, where: str) -> dict:
    """`[run] log`'s table, checked: each key one of LOG_DEFAULTS, each value a whole number ≥ 0."""
    if not isinstance(given, dict):
        raise HeimdallError(f"{where}: a table, {{ {', '.join(f'{k} = {v}' for k, v in LOG_DEFAULTS.items())} }}", where=where)
    for key, value in given.items():
        if key not in LOG_DEFAULTS:
            raise HeimdallError(f"{where}: no '{key}' to set", where=where,
                           hint=did_you_mean(key, LOG_DEFAULTS) or f"it has {', '.join(LOG_DEFAULTS)}")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HeimdallError(f"{where}: {key} must be a whole number ≥ 0, got {value!r}", where=where)
    return dict(given)


def log_settings() -> dict:
    """What a run's logs keep (V201): LOG_DEFAULTS, under machine.toml's [run] log, under the work dir's."""
    out = dict(LOG_DEFAULTS)
    out.update(log_values(machine_settings().get("run", {}).get("log", {}), f"{machine_file()}: [run] log"))
    try:
        work = find_work()
    except HeimdallError:
        work = None
    if work is not None:
        out.update(work_meta(work)["log"])
    return out


def keep_words(given, where: str = "--keep") -> set[str]:
    """`keep` words, from a list or "logs,work": each one of KEEP_WORDS."""
    words = given.split(",") if isinstance(given, str) else given
    if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
        raise HeimdallError(f"{where}: a list of words ({', '.join(KEEP_WORDS)})", where=where)
    out = {w.strip() for w in words if w.strip()}
    if unknown := sorted(out - set(KEEP_WORDS)):
        raise HeimdallError(f"nothing called {', '.join(repr(u) for u in unknown)} to keep", where=where,
                       hint=did_you_mean(unknown[0], KEEP_WORDS) or "; ".join(f"{w}: {d}" for w, d in KEEP_WORDS.items()))
    return out


_KEEP_ASKED: set[str] = set()                     # this command's own (--keep, --logs, --journal)


def ask_keep(words) -> None:
    """The command line's keep words, for this process (cli.main)."""
    _KEEP_ASKED.clear()
    _KEEP_ASKED.update(keep_words(list(words)))


def keep() -> set[str]:
    """What this run keeps: the command line's words, the work dir's heimdall.toml [run] keep and the machine's
    machine.toml [run] keep, together."""
    words = set(_KEEP_ASKED) | keep_words(machine_settings().get("run", {}).get("keep", []), f"{machine_file()}: [run] keep")
    try:
        work = find_work()
    except HeimdallError:
        work = None
    return words | (set(work_meta(work)["keep"]) if work is not None else set())


def keeping(word: str) -> bool:
    return word in keep()


def is_work(path: Path) -> bool:
    """A work dir: a heimdall.toml with a [work] table."""
    marker = path / MARKER_FILE
    if not marker.is_file():
        return False
    try:
        return isinstance(tomllib.loads(marker.read_text(encoding="utf-8")).get("work"), dict)
    except (OSError, tomllib.TOMLDecodeError):
        return False


@functools.cache
def _search(start: str) -> Path | None:
    tests = heimdall_root() / "tests"
    for candidate in [Path(start), *Path(start).parents]:
        if candidate.is_relative_to(tests):
            continue
        if is_work(candidate):
            return candidate
    return None


def find_work(start: Path | None = None) -> Path | None:
    """The work dir: $HEIMDALL_WORK, or the walk up from `start` (the working directory); None outside one."""
    given = os.environ.get(WORK_VAR)
    if given:
        root = Path(given).expanduser().resolve()
        if not is_work(root):
            raise HeimdallError(f"${WORK_VAR} = {root} is not a work dir",
                           hint=f"a work dir has a {MARKER_FILE} with a [work] table: heimdall setup <dir>")
        return root
    return _search(str((start or Path.cwd()).resolve()))


def work_root() -> Path:
    root = find_work()
    if root is None:
        raise HeimdallError("not inside a work dir", where=str(Path.cwd()),
                       hint="cd into one, or make one: heimdall setup <dir>")
    return root


def reset() -> None:
    """Forget the cached search (tests that make and move work dirs, or tool folders)."""
    _search.cache_clear()
    heimdall_root.cache_clear()
    _tool_chains.cache_clear()


def _rooted(var: str, name: str) -> Path:
    value = os.environ.get(var)
    return Path(value).resolve() if value else work_root() / name


def results_root() -> Path:
    """Where products go: $HEIMDALL_RESULTS (tests set it) or <work>/results."""
    return _rooted(RESULTS_VAR, "results")


def records_root() -> Path:
    """What runs recorded, a folder per configuration (V157, tools.RunFolders): its points' provenance,
    identity and .complete (`points/`, precious), their working folders (`logs/`: cards, configs,
    logs, FIFOs, scratch files; safe to delete), the page documents (`plots/`), the run's snapshot
    (`config/`), points.json and cluster submissions. $HEIMDALL_RECORDS (tests set it) or <work>/records;
    `heimdall clean` takes only logs and leftovers unless told --records."""
    return _rooted(RECORDS_VAR, "records")


def cache_root() -> Path:
    """Derived, rebuilt on demand: prepare caches, card checks, converted reference data. $HEIMDALL_CACHE
    (tests set it) or <work>/.cache."""
    return _rooted(CACHE_VAR, ".cache")


def reports_root() -> Path:
    """Where reports are built (heimdall report, V207–V211): $HEIMDALL_REPORTS (tests set it) or <work>/reports."""
    return _rooted(REPORTS_VAR, "reports")


def dataset_listed(path: Path) -> bool:
    """Whether the work dir's datasets.toml lists this file of datasets/ (heimdall setup fetches it)."""
    import tomllib
    work = find_work()
    manifest = work / "datasets.toml" if work is not None else None
    try:
        files = tomllib.loads(manifest.read_text(encoding="utf-8")).get("files", {}) if manifest and manifest.is_file() else {}
        return Path(path).resolve().relative_to((work / "datasets").resolve()).as_posix() in files
    except (ValueError, OSError, tomllib.TOMLDecodeError):
        return False


def configs_root() -> Path:
    """Where errand files and their cards are: $HEIMDALL_CONFIGS or <work>/configs (a record's snapshot, V158)."""
    return _rooted(CONFIGS_VAR, "configs")


@contextlib.contextmanager
def configs_at(folder: Path):
    """configs_root() at `folder` while the block runs: a record's snapshot, read as configs/ is (V158)."""
    before = os.environ.get(CONFIGS_VAR)
    os.environ[CONFIGS_VAR] = str(folder)
    try:
        yield folder
    finally:
        if before is None:
            os.environ.pop(CONFIGS_VAR, None)
        else:
            os.environ[CONFIGS_VAR] = before


def work_build() -> Path:
    """The work dir's compiled things: module programs, Rivet/, deps/, flags.mk."""
    return work_root() / "build"


def datasets_root() -> Path:
    return work_root() / "datasets"


STACK_VAR = "HEIMDALL_STACK"
MACHINE_VAR = "HEIMDALL_MACHINE"
#: The machine root when $HEIMDALL_MACHINE is not set (the user's choice, 2026-10-12: Heimdall's hall).
DEFAULT_MACHINE = "~/Himinbjorg"


def machine_root() -> Path:
    """What this machine built, apart from the checkout: $HEIMDALL_MACHINE, else ~/Himinbjorg."""
    return Path(os.environ.get(MACHINE_VAR) or DEFAULT_MACHINE).expanduser()


def machine_file() -> Path:
    """This machine's settings: <machine root>/machine.toml (recipes/machine.template.toml says what)."""
    return machine_root() / "machine.toml"


def machine_settings() -> dict:
    """machine.toml's tables ({} when there is none): [settings], [env] and [packages.<name>] are the
    stack build's (recipes/build_stack.py), [cluster] is heimdall cluster's defaults for every work dir."""
    file = machine_file()
    try:
        return tomllib.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HeimdallError(f"cannot read this machine's settings: {error}", where=str(file)) from None


def stack_dir() -> Path:
    """The loaded stack's base: the machine root, or its stacks/<toolkit>/ for an isolated toolkit's
    (gjallarhorn.sh sets $HEIMDALL_STACK; doc:stack). Its compiled apps and builds go with it: they
    are linked against that stack."""
    name = os.environ.get(STACK_VAR)
    return machine_root() / "stacks" / name if name else machine_root()


def apps_dir() -> Path:
    """Heimdall's compiled apps (App_*.exe, Paint.exe) and Herwig's repository, for the loaded stack."""
    return Path(os.environ["HEIMDALL_APPS"]) if os.environ.get("HEIMDALL_APPS") else stack_dir() / "apps"


def forge_dir() -> Path:
    """Builds in progress for the loaded stack: make/ (Heimdall's intermediates), tests/, scratch/."""
    return Path(os.environ["HEIMDALL_FORGE"]) if os.environ.get("HEIMDALL_FORGE") else stack_dir() / "forge"


def tool_roots() -> list[tuple[str, Path]]:
    """Where tool folders are, nearest first: the work dir's tools/
    ("work"), the machine root's tools/ ("machine"), Heimdall's framework/tools/ ("shipped")."""
    out = []
    work = find_work()
    if work is not None:
        out.append(("work", work / "tools"))
    out.append(("machine", machine_root() / "tools"))
    out.append(("shipped", heimdall_root() / "framework" / "tools"))
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
            raise HeimdallError(f"no tool folder '{name}'{below} to extend", where=str(seen[-1] / "tool.toml"),
                           hint="tool folders: " + ", ".join(sorted(found)))
        origin, folder = places[level]
        if folder in seen:
            raise HeimdallError("tool folders extend each other in a circle: "
                           + " → ".join(f.name for f in (*seen, folder)), where=str(folder / "tool.toml"))
        spec_file = folder / "tool.toml"
        extends = None
        if spec_file.is_file():
            try:
                extends = tomllib.loads(spec_file.read_text(encoding="utf-8")).get("extends")
            except tomllib.TOMLDecodeError as error:
                raise HeimdallError(f"not valid TOML: {error}", where=str(spec_file)) from None
        if extends is None:
            return [(origin, folder)]
        if not isinstance(extends, str):
            raise HeimdallError("extends names one tool folder", where=str(spec_file))
        return [(origin, folder), *chain(extends, level + 1 if extends == name else 0, (*seen, folder))]

    return {name: chain(name, 0, ()) for name in found}


def placeholders() -> dict[str, str]:
    """{heimdall}, {apps} and {work} (doc:layout); {work} only inside a work dir."""
    out = {"heimdall": str(heimdall_root()), "apps": str(apps_dir())}
    work = find_work()
    if work is not None:
        out["work"] = str(work)
    return out


def portable(path) -> str:
    """A path as an identity records it: under a known root, written with that root's placeholder, so
    a point's identity does not change when Heimdall, the machine root, the stack or a work dir moves."""
    return portable_texts()(str(path))


def portable_texts():
    """A function writing every known root inside a string as its placeholder ({apps}, {stack}, {base},
    {work}, {machine}, {heimdall}), the longest root first, as it is written and as it resolves: an argv's
    `--input=/…/x`, a card's path, paths joined with commas. What a fingerprint holds (V137). {stack}
    is the loaded stack's installs ($HEIMDALL_INSTALL), where a standard tool's program is found; {base} the
    loaded conda base ($HEIMDALL_BASE), whose Python runs a script tool (it moves with its stack, not with
    the machine root's name)."""
    work = find_work()
    return _portable_texts(str(apps_dir()), str(installs_dir()), str(machine_root()), str(heimdall_root()),
                           str(work) if work is not None else "", str(base_dir() or ""))


def identity_texts():
    """portable_texts for what an identity hashes: also a configs root other than the work dir's configs/ (a
    record's snapshot, V158) written as it reads there, `{work}/configs/…`, so a run of its snapshot plans its
    points to the identities they ran with (a card's path is in Pythia's argv; its content's sha256 is
    hashed anyway). A record's provenance keeps the real paths (portable)."""
    work = find_work()
    if work is None or configs_root().resolve() == (work / "configs").resolve():
        return portable_texts()
    return _portable_texts(str(apps_dir()), str(installs_dir()), str(machine_root()), str(heimdall_root()),
                           str(work), str(base_dir() or ""), str(configs_root()))


def installs_dir() -> Path:
    """The loaded stack's installs: $HEIMDALL_INSTALL, else <stack>/stack."""
    return Path(os.environ["HEIMDALL_INSTALL"]) if os.environ.get("HEIMDALL_INSTALL") else stack_dir() / "stack"


def base_dir() -> Path | None:
    """The loaded stack's conda base ($HEIMDALL_BASE: base/.pixi/envs/default), or None (a venv's stack)."""
    return Path(os.environ["HEIMDALL_BASE"]) if os.environ.get("HEIMDALL_BASE") else None


@functools.lru_cache(maxsize=8)
def _portable_texts(apps: str, installs: str, machine: str, heimdall: str, work: str, base: str = "", configs: str = ""):
    roots = [("{apps}", apps), ("{stack}", installs), ("{machine}", machine), ("{heimdall}", heimdall)]
    if work:
        roots.append(("{work}", work))
    if configs:                                          # identity_texts: a configs root elsewhere reads as configs/
        roots.append(("{work}/configs", configs))
    if base:
        roots.append(("{base}", base))
    pairs = []
    for name, root in roots:
        for form in {str(Path(root).expanduser()), str(Path(root).expanduser().resolve())}:
            if form not in ("", "/"):
                pairs.append((form, name))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    patterns = [(re.compile(re.escape(form) + r"(?=/|$|[^\w.\-])"), name) for form, name in pairs]

    def portable_text(text: str) -> str:
        for pattern, name in patterns:
            text = pattern.sub(lambda _: name, text)
        return text
    return portable_text


def unportable(text: str) -> str:
    """A path portable() wrote, under today's roots ({work}, {heimdall}, {apps}, {machine}); anything else as
    it is (a record written before, with absolute paths)."""
    roots = {"{apps}": apps_dir, "{stack}": installs_dir, "{machine}": machine_root, "{heimdall}": heimdall_root, "{work}": work_root,
             "{base}": lambda: base_dir() or ""}
    for name, root in roots.items():
        if text == name or text.startswith(name + "/"):
            return str(root()) + text[len(name):]
    return text


#: Keys whose root is the point's own directory: resolve() is always given it (`root=`).
POINT_KEYS = ("prelim", "input", "output")

#: Keys whose bare names are beside the file that names them (the errand file, an imported file): resolve() is
#: given that file's folder (`folder=`); without one, configs/<A>/ as ROOTS says.
BESIDE = ("master", "import", "baseconfig", "filters", "root_style")

#: The convention root of each path-taking key, as a function of the assignment (doc:paths).
ROOTS = {
    "config":     lambda assignment: configs_root(),
    "master":     lambda assignment: configs_root() / assignment,
    "import":     lambda assignment: configs_root() / assignment,
    "baseconfig": lambda assignment: configs_root() / assignment,
    "executable": lambda assignment: work_build() / assignment,
    "data":       lambda assignment: datasets_root(),
    "filters":    lambda assignment: configs_root() / assignment,
    "root_style": lambda assignment: configs_root() / assignment,
}


def resolve(value: str, key: str, *, assignment: str = "", root: Path | None = None, folder: Path | None = None,
            where: str | None = None) -> Path:
    """The path a config value names, under the rules above.

    `root` overrides the convention root (the runner passes a point's directory for `[prelim]`
    names and outputs); `folder`, the folder of the file naming it, is the root of a BESIDE key's bare
    name; otherwise `key` picks it from ROOTS.
    """
    if not isinstance(value, str) or not value:
        raise HeimdallError(f"expected a path, got {value!r}", where=where)
    if value.startswith("../") or value == ".." or "/../" in value:
        raise HeimdallError(f"'{value}' climbs out of its root", where=where,
                       hint="write it relative to the work dir as ./…, or give an absolute path")
    if value.startswith("/"):
        return Path(value)
    if value.startswith("./"):
        return work_root() / value[2:]
    if root is None:
        if key in POINT_KEYS:
            raise HeimdallError(f"'{key}' paths are under a point's directory, which was not given", where=where)
        if key not in ROOTS:
            raise HeimdallError(f"no convention root for key '{key}'", where=where)
        root = Path(folder) if folder is not None and key in BESIDE else ROOTS[key](assignment)
    return root / value


def config_file(name: str) -> Path:
    """`heimdall run <config>`: configs/<config>, `.toml` optional, unless it starts with ./ or /."""
    path = resolve(name, "config")
    if path.suffix != ".toml" and not path.exists():
        path = path.with_name(path.name + ".toml")
    if not path.is_file():
        raise HeimdallError(f"no errand file '{name}'", where=str(path),
                       hint="configs are looked up under configs/<A>/<E>.toml; "
                            "start the name with ./ to give a path from the work dir")
    return path
