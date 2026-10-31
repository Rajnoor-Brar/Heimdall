"""Helpers the integration tests share: run `heimdall` in the scratch work, with its outputs under a scratch folder.

The work dir is forge/scratch/work, the fixture's synced copy (HEIMDALL_WORK, set by conftest.py and inherited
here): configs resolve under its configs/, module programs and plugins are in its build/ (`work_built`).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]                  # Heimdall
HEIMDALL = REPO / "framework" / "bin" / "heimdall"
WORK = Path(os.environ.get("HEIMDALL_FORGE") or Path(os.environ.get("HEIMDALL_MACHINE") or "~/Himinbjorg").expanduser() / "forge") / "scratch" / "work"
BUILD = WORK / "build"


def apps() -> Path:
    """Heimdall's compiled apps, for the loaded stack (`heimdall build --framework`)."""
    from runner.paths import apps_dir
    return apps_dir()


def env(where: Path) -> dict:
    """The environment of a run whose records/, cache/ and results/ are under `where`."""
    return dict(os.environ, HEIMDALL_RECORDS=str(where / "records"), HEIMDALL_CACHE=str(where / "cache"),
                HEIMDALL_RESULTS=str(where / "results"))


def heimdall(where: Path, *args: str, command: str = "run", plain: bool = True, timeout: float = 1800,
        wait: bool = True):
    """`heimdall <command> ARGS [--plain]` with outputs under `where`: the finished process, or (wait=False) the
    running one, its output merged into stdout."""
    argv = [str(HEIMDALL), command, *map(str, args), *(["--plain"] if plain else [])]
    if not wait:
        return subprocess.Popen(argv, cwd=WORK, env=env(where), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8")
    return subprocess.run(argv, cwd=WORK, env=env(where), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def heimdall_ok(where: Path, *args: str, timeout: float = 1800) -> str:
    """`heimdall run ARGS --plain`, which must succeed; its stdout."""
    done = heimdall(where, *args, timeout=timeout)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return done.stdout


def folder(config: str, configuration: str | None = None, where: Path | None = None) -> Path:
    """<project>/<run name>/<NN_label> of a configuration, as the runner names it (tools.run_dir, V45):
    tests never spell the layout out. A v3 configuration without a serial is numbered by the runner
    (V131): its newest folder under `where`'s records/ or results/, else 01, its first."""
    from runner import config as configmod, tools
    errand = configmod.load(config)
    c = errand.configuration(configuration)
    if c.serial_auto:
        taken = set()
        for root in ((where / "records", where / "results") if where is not None else ()):
            parent = root / errand.assignment / (c.run_folder or errand.name)
            taken |= {int(p.name.split("_", 1)[0]) for p in (parent.iterdir() if parent.is_dir() else ())
                      if p.name.split("_", 1)[0].isdigit() and p.name.split("_", 1)[-1] == c.label}
        c.serial = max(taken, default=1)
    return tools.run_dir(errand, c)


def records(where: Path) -> Path:
    """`where`'s records/: a configuration's points.json, cluster submissions, journal and folders (V157)."""
    return where / "records"


def point_records(where: Path, run_folder: Path, point: str) -> Path:
    """A point's provenance, identity and .complete: records/<run>/points/<point> (V157)."""
    return where / "records" / run_folder / "points" / point


def point_logs(where: Path, run_folder: Path, point: str) -> Path:
    """A point's working folder: its cards and configs, a failed tool's <tag>.log (all of them with --logs),
    its working files while it runs or with --keep work: records/<run>/logs/<point> (V157)."""
    return where / "records" / run_folder / "logs" / point


def point_results(where: Path, run_folder: Path, point: str) -> Path:
    """A point's products: results/<run>/points/<point> (V157)."""
    return where / "results" / run_folder / "points" / point


def pages(where: Path, run_folder: Path, set_name: str = "totality") -> Path:
    """A configuration's page documents, a set's (V164): .cache/<P>/plots/<name>/<NN_cfg>/<set>."""
    return where / "cache" / run_folder.parts[0] / "plots" / Path(*run_folder.parts[1:]) / set_name
