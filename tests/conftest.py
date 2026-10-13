"""Test setup shared by every suite (docs/framework/01_Target.md §5.7).

* The runner package is importable as `runner` (framework/ on sys.path), and tests/ is on sys.path for
  `support` (the shared helpers).
* The tests run in a work dir of their own: tests/fixtures/work/ (frozen) is synced into
  forge/scratch/work/, which HEP_WORK names; HEP_RESULTS, HEP_RECORDS, HEP_LOGS, HEP_CACHE and HEP_REPORTS point into
  forge/scratch/. So a test reads and writes no real work dir, whatever the shell has set, and fails
  only when the code changed. $HEP is this Heimdall; a shell's retired HEKIT_* are dropped (the
  tests of their refusal set them).
* The basetemp is forge/scratch/pytest, wherever pytest is started.
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

MACHINE = Path(os.environ.get("HEP_MACHINE") or "~/Himinbjorg").expanduser()
SCRATCH = Path(os.environ.get("HEP_FORGE") or MACHINE / "forge") / "scratch"   # the machine root's, never the checkout
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


_sync(FIXTURE, WORK)
os.environ["HEP"] = str(REPO)
for name in ("HEKIT_ROOT", "HEKIT_CONFIGS", "HEKIT_OUTPUT", "HEKIT_RESULTS", "HEKIT_REPORTS", "HEP_CONFIGS", "HEP_OUTPUT"):
    os.environ.pop(name, None)
os.environ["HEP_WORK"] = str(WORK)
os.environ["HEP_RESULTS"] = str(SCRATCH / "results")
os.environ["HEP_RECORDS"] = str(SCRATCH / "records")
os.environ["HEP_LOGS"] = str(SCRATCH / "logs")
os.environ["HEP_CACHE"] = str(SCRATCH / "cache")
os.environ["HEP_REPORTS"] = str(SCRATCH / "reports")

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


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("slow"):
            item.fixturenames.insert(0, "work_built")


_made: list[subprocess.CompletedProcess] = []


def _make_work() -> subprocess.CompletedProcess | None:
    """`make all` in the scratch work, once per session; None without the stack."""
    if not os.environ.get("HEP_INSTALL") or not shutil.which("rivet-build"):
        return None
    if not _made:
        _made.append(subprocess.run(["make", "-C", str(WORK), "--no-print-directory", "-j", str(os.cpu_count() or 1),
                                     "all"], capture_output=True, text=True))
    return _made[0]


@pytest.fixture(scope="session", autouse=True)
def the_scratch_work_is_built():
    _make_work()                                         # a failure is work_built's to report


@pytest.fixture(scope="session")
def work_built() -> Path:
    """The scratch work's build/ (module programs, Rivet/), made by framework/work.mk."""
    done = _make_work()
    if done is None:
        pytest.skip("the stack is not loaded (source Heimdall's setup.sh)")
    if done.returncode:
        pytest.fail("make in the scratch work failed:\n" + done.stdout[-3000:] + done.stderr[-3000:])
    return WORK / "build"


@pytest.fixture
def scratch(tmp_path_factory) -> Path:
    """A fresh directory under the basetemp (forge/scratch/pytest/) for one test."""
    return Path(tmp_path_factory.mktemp("t", numbered=True))
