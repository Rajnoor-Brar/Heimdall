"""A tool folder names the packages it runs ([tool] packages, V146): `heimdall tools` says how each is installed,
a missing program says how to get it, and a point's provenance records it. The machine roots here are the
test's own folders."""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import plan, raw
from runner import paths, plugins, record, tools
from runner.errors import HeimdallError

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """An empty machine root on a conda base, the stack's view read afresh."""
    monkeypatch.setenv("HEIMDALL_MACHINE", str(tmp_path / "Himinbjorg"))
    monkeypatch.delenv("HEIMDALL_STACK", raising=False)
    (tmp_path / "Himinbjorg").mkdir()
    tools._installed.cache_clear()
    yield tmp_path / "Himinbjorg"
    tools._installed.cache_clear()


def test_the_shipped_folders_name_recipes():
    bs = plugins.load(REPO / "recipes" / "build_stack.py", "build_stack")
    _, _, packages = bs.options([])
    for name, folder in tools.folders().items():
        named = folder.get("tool", "packages", [])
        assert all(n in packages for n in named), (name, named)
        runs = folder.get("tool", "executable")
        assert named or folder.get("tool", "template"), f"{name} names no package"
        assert not runs or named                                            # a program of a package's


def test_a_package_is_built_ready_made_installed_or_missing(machine):
    bs = plugins.load(REPO / "recipes" / "build_stack.py", "build_stack")
    meta = machine / "base" / ".pixi" / "envs" / "default" / "conda-meta"      # the base first: stamps hold it
    meta.mkdir(parents=True)
    for name in ("python-3.12.15-h0_0", "yoda-2.1.4-py312h0_0"):
        (meta / f"{name}.json").write_text("{}", encoding="utf-8")
    _, settings, packages = bs.options([])
    c = bs.context(settings)
    stamp = bs.stamp("sherpa", packages["sherpa"], c)
    stamp.parent.mkdir(parents=True)
    stamp.write_text(bs.digest("sherpa", packages["sherpa"], c), encoding="utf-8")
    (machine / "stack" / "delphes").mkdir()                                 # there, not by the build
    assert tools.package_states(["sherpa", "yoda", "delphes", "whizard", "nosuch"]) == {
        "sherpa": "built 3.0.5", "yoda": "ready-made 2.1.4", "delphes": "installed", "whizard": "missing",
        "nosuch": "unknown"}


def test_a_missing_program_says_how_to_get_its_package(machine, monkeypatch):
    folder = tools.folders()["sherpa"]
    monkeypatch.setenv("PATH", "/nowhere")
    with pytest.raises(HeimdallError) as missing:
        tools.executable_of(type("T", (), {"executable": "", "tag": "s"})(), folder, "P")
    assert "'Sherpa' is not on PATH" in str(missing.value)
    assert "bifrost -b sherpa" in missing.value.hint and "bifrost -c sherpa" in missing.value.hint
    assert tools.missing_hint(tools.folders()["exec"]).startswith("gjallarhorn first")


def test_a_point_records_how_its_tools_packages_were_installed(scratch):
    run, conf, point = plan(raw(), scratch)
    made = record.provenance(point, run, conf, "a", "b", {})
    pythia = next(t for t in made["tools"] if t["tool"] == "pythia")
    assert set(pythia["packages"]) == {"pythia8", "hepmc3"}
    assert all(isinstance(s, str) and s for s in pythia["packages"].values())
