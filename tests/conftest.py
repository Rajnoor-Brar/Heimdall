"""Test setup shared by every suite (doc:layout).

* The runner package is importable as `runner` (framework/ on sys.path), and tests/ is on sys.path for
  `support` (the shared helpers).
* The tests run in a work dir of their own: tests/fixtures/work/ (frozen) is synced into
  forge/scratch/work/, which HEIMDALL_WORK names; HEIMDALL_RESULTS, HEIMDALL_RECORDS, HEIMDALL_CACHE and HEIMDALL_REPORTS point into
  forge/scratch/, and HEIMDALL_WORKDIRS (the registry of work dirs) too. So a test reads and writes no real work dir, whatever the shell has set, and fails
  only when the code changed. $HEIMDALL is this Heimdall; a shell's retired HEKIT_* are dropped (the
  tests of their refusal set them).
* The basetemp is forge/scratch/pytest, wherever pytest is started.
* The machine root is a shadow, forge/scratch/machine/ ($HEIMDALL_MACHINE for the session): the real root's
  stack/, base/, apps/ and forge/downloads/ linked, its own empty machine.toml, recipes.toml, runs/ and
  workdirs.toml. So no live setting decides what a test keeps or sees. $HEIMDALL_APPS, _INSTALL and _FORGE
  are pinned to the real root's before the switch, so the stack, the apps and the identities are as they were.
* The session guard: tests/fixtures and tests/reference must come out byte for byte as they went in.
* The scratch work's module programs and Rivet plugins are made once per session (framework/work.mk)
  when the stack is loaded: planning reads a plugin's .info. `work_built` is that build, or a skip
  without the stack; every `slow` test has it (they run real processes, through the work's plugins).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]                  # Heimdall
sys.path.insert(0, str(REPO / "framework"))

REAL_MACHINE = Path(os.environ.get("HEIMDALL_MACHINE") or "~/Himinbjorg").expanduser()   # live: read, never written
SCRATCH = Path(os.environ.get("HEIMDALL_FORGE") or REAL_MACHINE / "forge") / "scratch"   # the machine root's, never the checkout
SHADOW = SCRATCH / "machine"
FIXTURE = REPO / "tests" / "fixtures" / "work"
WORK = SCRATCH / "work"


def _sync(src: Path, dst: Path) -> None:
    """dst mirrors src file by file: only what differs is copied, and dst's build/ is left alone (so make
    rebuilds only what changed)."""
    want = {p.relative_to(src) for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    for rel in sorted(want):
        a, b = src / rel, dst / rel
        if not b.is_file() or b.read_bytes() != a.read_bytes():
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(a, b)
    for path in sorted(dst.rglob("*"), reverse=True) if dst.is_dir() else ():
        rel = path.relative_to(dst)
        if rel.parts[0] == "build":
            continue
        if path.is_file() and rel not in want:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def _shadow_machine() -> None:
    """Build SHADOW and make it the machine root: the built parts linked, the settings its own."""
    from runner import paths
    pinned = {"HEIMDALL_APPS": paths.apps_dir(), "HEIMDALL_INSTALL": paths.installs_dir(), "HEIMDALL_FORGE": paths.forge_dir()}
    SHADOW.mkdir(parents=True, exist_ok=True)
    (SHADOW / "forge").mkdir(exist_ok=True)
    links = {name: REAL_MACHINE / name for name in ("stack", "base", "apps", "venv", "stacks")}
    links["forge/downloads"] = REAL_MACHINE / "forge" / "downloads"
    for name, target in links.items():
        link = SHADOW / name
        if link.is_symlink() and link.resolve() != target.resolve():
            link.unlink()
        if target.exists() and not link.is_symlink():
            link.symlink_to(target)
    for name, template in (("machine.toml", "machine.template.toml"), ("recipes.toml", "recipes.template.toml")):
        (SHADOW / name).write_bytes((REPO / "recipes" / template).read_bytes())
    os.environ["HEIMDALL_MACHINE"] = str(SHADOW)
    for name, value in pinned.items():
        os.environ[name] = str(value)


_sync(FIXTURE, WORK)
os.environ["HEIMDALL"] = str(REPO)
from runner.paths import RETIRED  # noqa: E402
_shadow_machine()

for name in ("HEIMDALL_CONFIGS", *RETIRED):                 # a shell's retired names, the old HEP_* too
    os.environ.pop(name, None)
os.environ["HEIMDALL_WORK"] = str(WORK)
os.environ["HEIMDALL_RESULTS"] = str(SCRATCH / "results")
os.environ["HEIMDALL_RECORDS"] = str(SCRATCH / "records")
os.environ["HEIMDALL_CACHE"] = str(SCRATCH / "cache")
os.environ["HEIMDALL_REPORTS"] = str(SCRATCH / "reports")
os.environ["HEIMDALL_WORKDIRS"] = str(SCRATCH / "workdirs.toml")     # what heimdall recognise and setup record
os.environ["HEIMDALL_RUNS"] = str(SCRATCH / "runs")                  # the run registry (V182)
os.environ.pop("HEIMDALL_CLUSTER_JOB", None)

OURS = (REPO / "tests" / "fixtures", REPO / "tests" / "reference")         # must not change: content hashes


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if not config.option.basetemp:                       # before the tmp_path factory reads it
        config.option.basetemp = str(SCRATCH / "pytest")


def _hashes(tops) -> dict[str, str]:
    seen = {}
    for top in tops:
        for path in sorted(top.rglob("*")) if top.is_dir() else ():
            if path.is_file() and "__pycache__" not in path.parts:
                seen[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return seen


def _changed(before: dict, after: dict) -> list[str]:
    return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))


@pytest.fixture(scope="session", autouse=True)
def the_fixtures_are_left_alone():
    ours = _hashes(OURS)
    yield
    changed = _changed(ours, _hashes(OURS))
    assert not changed, "tests changed their fixtures or reference data:\n  " + "\n  ".join(changed[:20])


def _live_state() -> dict[str, str]:
    """What the real machine root holds that a test must not touch: its settings (hashed), its stamps and its
    apps (name, size and mtime; a rebuilt app changes its hash into every identity)."""
    seen = {}
    for name in ("machine.toml", "recipes.toml"):
        path = REAL_MACHINE / name
        seen[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    apps = Path(os.environ["HEIMDALL_APPS"])
    stamps = Path(os.environ["HEIMDALL_INSTALL"]) / ".stamps"
    for top in (apps, stamps):
        for path in sorted(top.rglob("*")) if top.is_dir() else ():
            if path.is_file() and "__pycache__" not in path.parts:
                info = path.stat()
                seen[str(path)] = f"{info.st_size}:{info.st_mtime_ns}"
    return seen


@pytest.fixture(scope="session", autouse=True)
def the_live_himinbjorg_is_left_alone():
    live = _live_state()
    yield
    changed = _changed(live, _live_state())
    assert not changed, "tests changed the live machine root:\n  " + "\n  ".join(changed[:20])


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("slow"):
            item.fixturenames.insert(0, "work_built")


_made: list[subprocess.CompletedProcess] = []


def _make_work() -> subprocess.CompletedProcess | None:
    """`make all` in the scratch work, once per session; None without the stack."""
    if not os.environ.get("HEIMDALL_INSTALL") or not shutil.which("rivet-build"):
        return None
    if not _made:
        _made.append(subprocess.run(["make", "-C", str(WORK), "--no-print-directory", "-j", str(os.cpu_count() or 1),
                                     "all"], capture_output=True, text=True, encoding="utf-8"))
    return _made[0]


@pytest.fixture(scope="session", autouse=True)
def the_scratch_work_is_built():
    _make_work()                                         # a failure is work_built's to report


@pytest.fixture(scope="session")
def work_built() -> Path:
    """The scratch work's build/ (module programs, Rivet/), made by framework/work.mk."""
    done = _make_work()
    if done is None:
        pytest.skip("the stack is not loaded (source Heimdall's gjallarhorn.sh)")
    if done.returncode:
        pytest.fail("make in the scratch work failed:\n" + done.stdout[-3000:] + done.stderr[-3000:])
    return WORK / "build"


@pytest.fixture(autouse=True)
def an_empty_registry():
    """Each test starts with no work dir recorded ($HEIMDALL_WORKDIRS, which heimdall setup writes too), no run
    recorded ($HEIMDALL_RUNS, V182), and no keep word asked (paths.ask_keep: what a run keeps, V149)."""
    Path(os.environ["HEIMDALL_WORKDIRS"]).unlink(missing_ok=True)
    shutil.rmtree(os.environ["HEIMDALL_RUNS"], ignore_errors=True)
    from runner import paths
    paths.ask_keep([])


@pytest.fixture
def scratch(tmp_path_factory) -> Path:
    """A fresh directory under the basetemp (forge/scratch/pytest/) for one test."""
    return Path(tmp_path_factory.mktemp("t", numbered=True))
