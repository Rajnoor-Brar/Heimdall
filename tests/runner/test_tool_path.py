"""The tool search path (docs/audit_3/06_Plan.md, phase 4.1): a work dir's tools/, the machine root's tools/,
Heimdall's framework/tools/, nearest first; `extends` lays a folder over another; `hep tools` says which."""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from runner import paths, quantities, tools
from runner.errors import HepError
from support import HEP, REPO

SHIPPED = REPO / "framework" / "tools"
SCRIPT = ('#!/usr/bin/env python3\nimport sys\nargs = [a for a in sys.argv[1:] if a]          # [config,] output\n'
          'open(args[-1], "w").write(open(args[0]).read() if len(args) > 1 else "x\\n")\n')


@pytest.fixture
def roots(scratch, monkeypatch):
    """A work dir and a machine root of the test's own: their tools/ are searched before Heimdall's."""
    work, machine = scratch / "w", scratch / "m"
    (work / "configs" / "P").mkdir(parents=True)
    (work / "hep.toml").write_text('[work]\nname = "t"\n', encoding="utf-8")
    machine.mkdir()
    for var, value in (("HEP_WORK", work), ("HEP_RECORDS", work / "records"), ("HEP_LOGS", work / "logs"), ("HEP_CACHE", work / "cache"), ("HEP_RESULTS", work / "results"),
                       ("HEP_MACHINE", machine)):
        monkeypatch.setenv(var, str(value))
    paths.reset()
    yield work, machine
    paths.reset()


def folder(root: Path, name: str, text: str | None = None, copy_of: str | None = None) -> Path:
    target = root / "tools" / name
    if copy_of:
        shutil.copytree(SHIPPED / copy_of, target, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        target.mkdir(parents=True)
    if text is not None:
        (target / "tool.toml").write_text(text, encoding="utf-8")
    paths.reset()
    return target


def row(name: str) -> str:
    return next(line for line in tools.folder_rows() if line.split()[0] == name)


def test_the_shipped_folders_are_the_last_on_the_path(roots):
    work, machine = roots
    assert paths.tool_roots() == [("work", work / "tools"), ("machine", machine / "tools"), ("shipped", SHIPPED)]
    known = tools.folders()
    assert {"pythia", "rivet", "exec", "module"} <= set(known) and known["pythia"].origin == "shipped"
    assert "lhapdf" not in known and "figures" not in known           # plugins and mappings only: no tool.toml


def test_a_work_dirs_folder_is_a_tool_and_hep_tools_says_so(roots):
    work, _ = roots
    folder(work, "fit", copy_of="exec")
    assert tools.folders()["fit"].origin == "work" and tools.folders()["fit"].dir == work / "tools" / "fit"
    assert row("fit").split()[1] == "work" and row("pythia").split()[1] == "shipped"


def test_extends_lays_a_folder_over_the_shipped_one(roots):
    work, _ = roots
    folder(work, "sherpa", 'extends = "sherpa"\n[tool]\nexecutable = "/bin/true"\n')
    mine, shipped = tools.folders()["sherpa"], tomllib.loads((SHIPPED / "sherpa" / "tool.toml").read_text(encoding="utf-8"))
    assert mine.origin == "work" and mine.get("tool", "executable") == "/bin/true"
    assert mine.get("tool", "category") == shipped["tool"]["category"] and mine.spec["card"] == shipped["card"]
    assert "extends" not in mine.spec
    assert mine.find("render.py") == SHIPPED / "sherpa" / "render.py"            # the extended folder's files
    assert mine.plugin is tools.folders()["sherpa"].plugin
    assert "work, extends sherpa (shipped)" in row("sherpa")


def test_a_folder_without_extends_replaces_the_shipped_one(roots):
    work, _ = roots
    folder(work, "rivet", '[tool]\ncategory = "mine"\n')
    assert tools.folders()["rivet"].spec == {"tool": {"category": "mine"}}


def test_the_machine_roots_folders_sit_between(roots):
    work, machine = roots
    folder(machine, "fit", copy_of="exec")
    assert tools.folders()["fit"].origin == "machine"
    folder(work, "fit", 'extends = "fit"\n[tool]\nstatus = "mine"\n')
    fit = tools.folders()["fit"]
    assert fit.origin == "work" and [o for o, _ in fit.chain] == ["work", "machine"]
    assert fit.get("tool", "status") == "mine" and fit.get("tool", "config_file") is True


@pytest.mark.parametrize("texts, message", [
    ({"a": 'extends = "nope"\n'}, "no tool folder 'nope'"),
    ({"a": 'extends = "b"\n', "b": 'extends = "a"\n'}, "in a circle"),
    ({"a": 'extends = 3\n'}, "extends names one tool folder"),
    ({"a": '[tool]\nexecutible = "x"\n'}, "unknown key \\[tool\\].executible"),
])
def test_a_bad_folder_is_refused(roots, texts, message):
    work, _ = roots
    for name, text in texts.items():
        folder(work, name, text)
    with pytest.raises(HepError, match=message):
        tools.folders()


def test_a_folders_mappings_lay_over_the_extended_ones(roots):
    work, _ = roots
    shipped = tomllib.loads((SHIPPED / "pythia" / "quantities.toml").read_text(encoding="utf-8"))
    name = next(iter(shipped))
    mine = folder(work, "pythia", 'extends = "pythia"\n')
    (mine / "quantities.toml").write_text(f'{name} = "Mine:{name}"\n', encoding="utf-8")
    mapped = quantities.compatible(quantities.load_master("P", None), "pythia")
    assert mapped[name] == f"Mine:{name}" and set(shipped) <= set(mapped)


def test_a_run_uses_a_work_dirs_tool(roots):
    """06_Plan's row: a work dir's tools/fit/, copied from the shipped custom folder, runs; Heimdall's tree is not touched."""
    work, _ = roots
    folder(work, "fit", copy_of="exec")
    script = work / "make.py"
    script.write_text(SCRIPT, encoding="utf-8")
    script.chmod(0o755)
    (work / "configs" / "P" / "c.toml").write_text(f"""[run]
name = "c"
project = "P"
configuration = "two"
event_count = 1
threads = 1

[run.cfgs.two]
sweeps = ["q"]
tools  = ["make"]

[tools.make]
tool        = "fit"
executable  = "{script}"
arguments   = ["{{partial:output}}"]
consumes    = ["q"]
output_file = "x.txt"

[quantities.q]
values = [1, 2]
tags   = ["a", "b"]
""", encoding="utf-8")
    before = sorted(p for p in SHIPPED.rglob("*") if "__pycache__" not in p.parts)
    done = subprocess.run([str(HEP), "run", "P/c", "--plain"], cwd=work, capture_output=True, text=True, encoding="utf-8",
                          timeout=300, env={k: v for k, v in os.environ.items() if k != "HEP_CONFIGS"})
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(list((work / "results").rglob("x.txt"))) == 2
    assert sorted(p for p in SHIPPED.rglob("*") if "__pycache__" not in p.parts) == before
