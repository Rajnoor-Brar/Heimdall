"""Where things are, and how a name in a config becomes a path (rank 0).

docs/04_Config_Reference.md §2; docs/framework/01_Target.md §5.2–5.3. Two roots:

* **Heimdall** (`hep_root()`): the framework, the stack and its environment. Always the one this code
  runs from; a `$HEP` that names another is refused.
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
OUTPUT_VAR = "HEP_OUTPUT"
CONFIGS_VAR = "HEP_CONFIGS"
REPORTS_VAR = "HEP_REPORTS"

#: High-Energy's variables (K15): a shell that still sets one is refused, with its replacement named.
RETIRED = {"HEKIT_ROOT": "HEP", "HEKIT_CONFIGS": "HEP_CONFIGS", "HEKIT_OUTPUT": "HEP_OUTPUT",
           "HEKIT_RESULTS": "HEP_RESULTS", "HEKIT_REPORTS": "HEP_REPORTS"}


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
    """Forget the cached search (tests that make and move work dirs)."""
    _search.cache_clear()
    hep_root.cache_clear()


def _rooted(var: str, name: str) -> Path:
    value = os.environ.get(var)
    return Path(value).resolve() if value else work_root() / name


def results_root() -> Path:
    """Where products go: $HEP_RESULTS (tests set it) or <work>/results."""
    return _rooted(RESULTS_VAR, "results")


def output_root() -> Path:
    """Where technical files go: $HEP_OUTPUT (tests set it) or <work>/output."""
    return _rooted(OUTPUT_VAR, "output")


def reports_root() -> Path:
    """Where decks go (docs/reporter): $HEP_REPORTS (tests set it) or <work>/reports."""
    return _rooted(REPORTS_VAR, "reports")


def configs_root() -> Path:
    """Where run TOMLs and their cards are: $HEP_CONFIGS or <work>/configs."""
    return _rooted(CONFIGS_VAR, "configs")


def work_build() -> Path:
    """The work dir's compiled things: module programs, Rivet/, deps/, flags.mk."""
    return work_root() / "build"


def datasets_root() -> Path:
    return work_root() / "datasets"


def apps_dir() -> Path:
    """Heimdall's compiled apps (App_*.exe, Paint.exe) and Herwig's repository."""
    return hep_root() / "framework" / "Apps"


def forge_dir() -> Path:
    """Heimdall's builds in progress: make/, tests/, scratch/."""
    return hep_root() / "forge"


def placeholders() -> dict[str, str]:
    """The {hep} and {work} placeholders (docs/framework/01_Target.md §5.3); {work} only inside a work dir."""
    out = {"hep": str(hep_root())}
    work = find_work()
    if work is not None:
        out["work"] = str(work)
    return out


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
