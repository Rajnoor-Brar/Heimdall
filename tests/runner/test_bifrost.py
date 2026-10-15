"""`bifrost`, the environment's packages (runner/bifrost.py, V144). The machine root is the test's own folder
($HEP_MACHINE), the base update and pip are replaced: nothing is downloaded or installed here."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from runner import bifrost, cli, paths
from runner.errors import HepError

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = (REPO / "recipes" / "machine.template.toml").read_text(encoding="utf-8")


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A machine root on a conda base (no venv/), with the template's machine.toml; the base's update counted."""
    monkeypatch.setenv("HEP_MACHINE", str(tmp_path / "Himinbjorg"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "Himinbjorg").mkdir()
    (tmp_path / "Himinbjorg" / "machine.toml").write_text(TEMPLATE, encoding="utf-8")
    updates: list[int] = []
    monkeypatch.setattr(bifrost, "update_base", lambda: updates.append(1))
    paths.reset()
    yield tmp_path / "Himinbjorg", updates
    paths.reset()


def settings_of(root: Path) -> dict:
    return tomllib.loads((root / "machine.toml").read_text(encoding="utf-8")).get("settings", {})


@pytest.mark.parametrize("word, spec", [("scipy", "scipy"), ("gsl=2.8", "gsl 2.8.*"), ("gsl=2.8.1", "gsl 2.8.1"),
                                        ("gsl>=2.8", "gsl >=2.8"), ("gsl 2.8.*", "gsl 2.8.*"),
                                        ("iminuit==2.30", "iminuit ==2.30"), ("scikit-learn", "scikit-learn")])
def test_a_package_is_written_as_base_toml_writes_one(word, spec):
    assert bifrost.spec_of(word) == spec and bifrost.name_of(spec) == word.split("=")[0].split(">")[0].split()[0]


def test_machine_toml_is_edited_in_place(tmp_path):
    added = bifrost.set_list(TEMPLATE, "base_packages", ["scipy"])
    assert added.startswith(TEMPLATE.rstrip("\n")) and added.endswith('[settings]\nbase_packages = ["scipy"]\n')
    mine = ("# mine\n[settings]   # this machine's\ncores = 8\nbase_packages = [\n  \"scipy\",   # for fits\n"
            "  \"pandas\",\n]   # data\n\n[env]\nCC = \"gcc\"\n")
    edited = bifrost.set_list(mine, "base_packages", ["pandas", "gsl 2.8.*"])
    assert edited == ('# mine\n[settings]   # this machine\'s\ncores = 8\nbase_packages = ["pandas", "gsl 2.8.*"]   # data\n'
                      '\n[env]\nCC = "gcc"\n')
    assert tomllib.loads(bifrost.set_list(mine, "base_pypi", ["x"]))["settings"] == {
        "cores": 8, "base_pypi": ["x"], "base_packages": ["scipy", "pandas"]}


def test_packages_are_recorded_once_dropped_and_the_base_made_again(root):
    machine, updates = root
    said: list[str] = []
    bifrost.change(["scipy", "gsl"], python=False, drop=False, out=said.append)
    bifrost.change(["gsl=2.8"], python=False, drop=False, out=said.append)          # a spec replaces the name
    bifrost.change(["iminuit>=2.30"], python=True, drop=False, out=said.append)
    assert settings_of(machine) == {"base_packages": ["scipy", "gsl 2.8.*"], "base_pypi": ["iminuit >=2.30"]}
    assert len(updates) == 3 and (machine / "machine.toml").read_text(encoding="utf-8").startswith(TEMPLATE.rstrip("\n"))
    bifrost.change(["gsl"], python=False, drop=True, out=said.append)
    assert settings_of(machine)["base_packages"] == ["scipy"]
    with pytest.raises(HepError, match="not among base_packages: numpy"):
        bifrost.change(["numpy"], python=False, drop=True)


def test_a_package_the_base_cannot_take_leaves_machine_toml_as_it_was(root, monkeypatch):
    machine, _ = root
    bifrost.change(["scipy"], python=False, drop=False, out=lambda _: None)

    def fails():
        raise SystemExit("heimdall: base: pixi install failed")
    monkeypatch.setattr(bifrost, "update_base", fails)
    with pytest.raises(HepError, match="could not be made with nosuch") as failed:
        bifrost.change(["nosuch"], python=False, drop=False, out=lambda _: None)
    assert "-python" in failed.value.hint and settings_of(machine)["base_packages"] == ["scipy"]


def test_a_package_the_stack_builds_is_refused(root):
    machine, updates = root
    (machine / "stack" / "fastjet").mkdir(parents=True)
    with pytest.raises(HepError, match="fastjet-cxx is fastjet's, which the stack builds") as refused:
        bifrost.change(["fastjet-cxx"], python=False, drop=False)
    assert "fastjet.from=conda-forge" in refused.value.hint and not updates
    bifrost.change(["eigen"], python=False, drop=False, out=lambda _: None)          # no recipe's: welcome


def test_on_a_system_root_python_packages_go_into_the_venv(root, monkeypatch):
    machine, updates = root
    (machine / "venv" / "bin").mkdir(parents=True)                                     # a root made before the base
    pips: list[tuple] = []
    monkeypatch.setattr(bifrost, "pip", lambda venv, specs, drop: pips.append((venv, specs, drop)))
    bifrost.change(["requests"], python=True, drop=False, out=lambda _: None)
    assert pips == [(machine / "venv", ["requests"], False)] and settings_of(machine) == {"python_packages": ["requests"]}
    assert not updates
    with pytest.raises(HepError, match="no conda base"):
        bifrost.change(["scipy"], python=False, drop=False)


def test_the_state_shows_the_base_what_was_added_and_the_shell(root):
    machine, _ = root
    env = machine / "base" / ".pixi" / "envs" / "default"
    (env / "conda-meta").mkdir(parents=True)
    for name in ("python-3.12.15-h0_0", "scipy-1.16.2-py312h0_0"):
        (env / "conda-meta" / f"{name}.json").write_text("{}", encoding="utf-8")
    (env / "lib" / "python3.12" / "site-packages" / "iminuit-2.31.1.dist-info").mkdir(parents=True)
    bifrost.record("base_packages", ["scipy", "pandas"])
    bifrost.record("base_pypi", ["iminuit >=2.30"])
    (Path.home() / ".bashrc").write_text("export A=1\n", encoding="utf-8")
    lines = bifrost.state()
    assert lines[0].startswith("the base:         conda-forge, 2 packages, Python 3.12.15")
    assert lines[1] == "base_packages:    scipy 1.16.2, pandas (not installed yet: bifrost makes the base again)"
    assert lines[2] == "base_pypi:        iminuit 2.31.1"
    assert lines[3] == "the tools:        none installed yet"
    assert lines[4] == f"the shell:        {Path.home() / '.bashrc'}: no gjallarhorn (bifrost --shell install)"
    assert bifrost.shell("install", out=lambda _: None) == 0
    assert bifrost.state()[4].endswith(": gjallarhorn and bifrost")


def test_bifrost_is_a_program_and_a_command():
    args = cli.parse(["bifrost", "-python", "iminuit", "--drop"])
    assert (args.command, args.packages, args.python, args.drop, args.shell) == ("bifrost", ["iminuit"], True, True, None)
    assert cli.parse(["bifrost", "--shell", "remove"]).shell == "remove"
    program = REPO / "framework" / "bin" / "bifrost"
    assert os.access(program, os.X_OK)
    done = subprocess.run([str(program), "--help"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0 and "usage: heimdall bifrost" in done.stdout


# ── tools: -c (ready-made) and -b (built) ─────────────────────────────────────────────────────────

@pytest.fixture
def builds(root, monkeypatch):
    """The build's calls, recorded instead of run."""
    calls: list[list[str]] = []
    monkeypatch.setattr(bifrost, "build", lambda argv: calls.append(argv))
    return calls


def froms(machine: Path) -> dict:
    data = tomllib.loads((machine / "machine.toml").read_text(encoding="utf-8")).get("packages", {})
    return {name: table.get("from") for name, table in data.items()}


def stamp_built(machine: Path, name: str):
    """A package built here: its install folder and its stamp."""
    bs = bifrost.builder()
    _, settings, packages = bs.options([f"machine={machine}"])
    c = bs.context(settings)
    stamp = bs.stamp(name, packages[name], c)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(bs.digest(name, packages[name], c), encoding="utf-8")
    Path(c["inst"], packages[name].get("install", name)).mkdir(parents=True, exist_ok=True)


def a_held_base(machine: Path, **installed):
    meta = machine / "base" / ".pixi" / "envs" / "default" / "conda-meta"
    meta.mkdir(parents=True, exist_ok=True)
    for name, version in {"python": "3.12.15", **installed}.items():
        (meta / f"{name.replace('_', '-')}-{version}-h0_0.json").write_text("{}", encoding="utf-8")


def test_the_flags_become_options():
    assert bifrost.flags(["-c", "root", "-conda"]) == ["--conda", "root", "--conda"]
    assert bifrost.flags(["-b@lab", "rivet", "-build", "--build@key4hep-src"]) == [
        "--build", "--toolkit", "lab", "rivet", "--build", "--build", "--toolkit", "key4hep-src"]
    with pytest.raises(HepError, match="a toolkit goes with -b"):
        bifrost.flags(["-c@lab"])
    args = cli.parse(["bifrost", "-b@lab", "rivet", "--yes"])
    assert (args.build, args.toolkit, args.packages, args.yes) == (True, "lab", ["rivet"], True)


def test_a_tool_ready_made_brings_what_it_needs_ready_made(root, builds):
    machine, _ = root
    said: list[str] = []
    assert bifrost.tools(["rivet"], conda=True, out=said.append) == 0
    assert froms(machine) == {n: "conda-forge" for n in ("rivet", "hepmc3", "yoda", "fastjet", "fjcontrib")}
    assert builds == [["packages=rivet"]]
    assert any("need" in line and "fastjet" in line for line in said)
    assert (machine / "machine.toml").read_text(encoding="utf-8").startswith(TEMPLATE.rstrip("\n"))
    with pytest.raises(HepError, match="conda-forge carries no madgraph"):
        bifrost.tools(["madgraph"], conda=True)


def test_switching_a_built_tool_says_what_it_costs_and_asks(root, builds, tmp_path, monkeypatch):
    machine, _ = root
    for name in ("fastjet", "fjcontrib"):
        stamp_built(machine, name)
    study = tmp_path / "Study"
    (study / "records" / "P" / "run" / "cfg" / "p1").mkdir(parents=True)
    (study / "hep.toml").write_text('[work]\nname = "Study"\n', encoding="utf-8")
    (study / "records" / "P" / "run" / "cfg" / "p1" / "provenance.json").write_text(
        '{"tools": [{"tool": "rivet"}, {"tool": "pythia", "packages": {"fastjet": "built 3.5.0"}}]}', encoding="utf-8")
    monkeypatch.setenv("HEP_WORKDIRS", str(tmp_path / "workdirs.toml"))
    from runner import workdirs
    workdirs.record(study)
    with pytest.raises(HepError, match="it asks first"):
        bifrost.tools(["fastjet"], conda=True, out=lambda _: None)
    assert not (machine / "machine.toml").read_text(encoding="utf-8").count("[packages.fastjet]") and not builds
    said: list[str] = []
    assert bifrost.tools(["fastjet"], conda=True, out=said.append, ask=lambda _: "n") == 1 and not builds
    assert any("1 recorded point(s) ran them (Study: 1)" in line for line in said)
    assert bifrost.tools(["fastjet"], conda=True, yes=True, out=said.append) == 0
    assert not (machine / "stack" / "fastjet").exists() and list((machine / "forge" / "retired").glob("*-fastjet"))
    assert builds == [["packages=fastjet fjcontrib", "--rebuild", "fjcontrib"]]           # built on it: again


def test_a_failed_switch_puts_everything_back(root, monkeypatch):
    machine, _ = root
    stamp_built(machine, "fastjet")
    before = (machine / "machine.toml").read_text(encoding="utf-8")

    def fails(argv):
        raise SystemExit("heimdall: fastjet: the base could not be made")
    monkeypatch.setattr(bifrost, "build", fails)
    with pytest.raises(HepError, match="as they were"):
        bifrost.tools(["fastjet"], conda=True, yes=True, out=lambda _: None)
    assert (machine / "stack" / "fastjet").is_dir() and (machine / "machine.toml").read_text(encoding="utf-8") == before


def test_building_a_ready_made_tool_is_refused_when_a_ready_made_one_needs_it(root, builds):
    machine, _ = root
    a_held_base(machine, rivet="4.1.4", fastjet_cxx="3.5.2", yoda="2.1.4", hepmc3="3.3.1", fastjet_contrib="1.105")
    with pytest.raises(HepError, match="ready-made, brings conda-forge's fastjet: building it here would make two") as refused:
        bifrost.tools(["fastjet"], conda=False, yes=True)
    assert refused.value.hint.startswith("build ") and "bifrost -b fastjet " in refused.value.hint and not builds
    assert bifrost.tools(["sherpa"], conda=False) == 0 and builds == [["packages=sherpa"]]   # not installed: built
    assert bifrost.tools(["rivet"], conda=False, toolkit="lab", yes=True, out=lambda _: None) == 0
    assert builds[-1] == ["packages=rivet@lab"] and froms(machine)["rivet"] == "source"


def test_a_bare_recipe_name_asks_how_it_comes(root):
    with pytest.raises(HepError, match="sherpa is a tool's recipe") as asked:
        bifrost.change(["sherpa"], python=False, drop=False)
    assert "bifrost -c sherpa" in asked.value.hint and "bifrost -b sherpa" in asked.value.hint


def test_the_stack_s_state_is_derived_and_printed_as_toml(root):
    machine, _ = root
    a_held_base(machine, yoda="2.1.4")                                         # the base first: stamps hold it
    stamp_built(machine, "fastjet")
    from runner import doctor
    data = tomllib.loads(doctor.stack_toml())
    assert data["packages"]["fastjet"] == {"version": "3.5.0", "how": "built", "folder": f"{machine}/stack/fastjet"}
    assert data["packages"]["yoda"]["how"] == "ready-made" and data["packages"]["yoda"]["version"] == "2.1.4"
    assert any(line.startswith("the tools:") and "fastjet 3.5.0 (built)" in line for line in bifrost.state())
