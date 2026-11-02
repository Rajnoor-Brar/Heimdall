"""The two roots and path resolution (doc:layout; doc:paths)."""

from __future__ import annotations

from pathlib import Path

import pytest

from runner import paths, tools
from runner.errors import HeimdallError
from support import REPO, WORK


@pytest.fixture
def fresh():
    """The cached roots forgotten before and after: a test that moves the roots leaves no trace."""
    paths.reset()
    yield
    paths.reset()


def make_work(folder: Path, name: str = "w") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "heimdall.toml").write_text(f'[work]\nname = "{name}"\n', encoding="utf-8")
    return folder


# ── Heimdall ────────────────────────────────────────────────────────────────────────────────────

def test_heimdall_is_where_the_code_is():
    assert paths.heimdall_root() == REPO
    assert paths.is_heimdall(REPO)


def test_another_heimdalls_heimdall_is_refused(monkeypatch, scratch, fresh):
    monkeypatch.setenv("HEIMDALL", str(scratch))
    with pytest.raises(HeimdallError, match="two Heimdalls"):
        paths.heimdall_root()


@pytest.mark.parametrize("old,new", sorted(paths.RETIRED.items()))
def test_high_energys_variables_are_refused(monkeypatch, old, new):
    monkeypatch.setenv(old, "/anywhere")
    with pytest.raises(HeimdallError, match=f"\\${old} is set, and it is retired: Heimdall reads \\${new}"):
        paths.check_retired()


def test_apps_go_with_the_loaded_stack_in_the_machine_root(monkeypatch, tmp_path):
    for var in ("HEIMDALL_STACK", "HEIMDALL_APPS", "HEIMDALL_FORGE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HEIMDALL_MACHINE", str(tmp_path))
    assert paths.machine_root() == tmp_path
    assert paths.apps_dir() == tmp_path / "apps" and paths.forge_dir() == tmp_path / "forge"
    monkeypatch.setenv("HEIMDALL_STACK", "gpu-sim")
    assert paths.apps_dir() == tmp_path / "stacks" / "gpu-sim" / "apps"
    assert paths.forge_dir() == tmp_path / "stacks" / "gpu-sim" / "forge"
    monkeypatch.setenv("HEIMDALL_APPS", "/elsewhere/apps")                   # gjallarhorn.sh's own answer wins
    assert paths.apps_dir() == Path("/elsewhere/apps")
    monkeypatch.delenv("HEIMDALL_MACHINE")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert paths.machine_root() == tmp_path / "home" / "Himinbjorg"     # the default


def test_an_identity_names_paths_by_their_root(monkeypatch, tmp_path):
    monkeypatch.setenv("HEIMDALL_APPS", str(tmp_path / "apps"))
    assert paths.portable(tmp_path / "apps" / "App_Pythia.exe") == "{apps}/App_Pythia.exe"
    assert paths.portable(WORK / "build" / "Rivet" / "Rivet_x.so") == "{work}/build/Rivet/Rivet_x.so"
    assert paths.portable(REPO / "framework" / "x") == "{heimdall}/framework/x"
    assert paths.portable("/usr/bin/rivet") == "/usr/bin/rivet"


# ── the work dir ────────────────────────────────────────────────────────────────────────────────

def test_the_tests_work_in_the_scratch_copy_of_the_fixture():
    assert paths.work_root() == WORK
    assert paths.configs_root() == WORK / "configs"
    assert paths.work_meta(WORK)["name"] == "fixture"


def test_the_work_dir_is_found_by_walking_up(monkeypatch, scratch, fresh):
    monkeypatch.delenv("HEIMDALL_WORK")
    work = make_work(scratch / "study")
    (work / "configs" / "P").mkdir(parents=True)
    monkeypatch.chdir(work / "configs" / "P")
    assert paths.work_root() == work.resolve()


def test_a_heimdall_toml_without_work_is_no_marker(monkeypatch, scratch, fresh):
    monkeypatch.delenv("HEIMDALL_WORK")
    (scratch / "heimdall.toml").write_text('[framework]\nexpects = ""\n', encoding="utf-8")
    monkeypatch.chdir(scratch)
    assert not paths.is_work(scratch)
    assert paths.find_work() is None


def test_outside_a_work_dir_is_an_error_naming_heimdall_setup(monkeypatch, scratch, fresh):
    monkeypatch.delenv("HEIMDALL_WORK")
    monkeypatch.chdir(scratch)
    with pytest.raises(HeimdallError, match="not inside a work dir") as caught:
        paths.work_root()
    assert "heimdall setup" in caught.value.hint


def test_markers_under_heimdalls_tests_are_skipped(monkeypatch, fresh):
    monkeypatch.delenv("HEIMDALL_WORK")
    monkeypatch.chdir(REPO / "tests" / "fixtures" / "work" / "configs")
    assert paths.find_work() is None                     # the fixture is found only through HEIMDALL_WORK


def test_heimdall_work_must_be_a_work_dir(monkeypatch, scratch, fresh):
    monkeypatch.setenv("HEIMDALL_WORK", str(scratch))
    with pytest.raises(HeimdallError, match="is not a work dir"):
        paths.work_root()


def test_heimdall_toml_refuses_what_it_does_not_know(scratch):
    work = make_work(scratch / "w")
    (work / "heimdall.toml").write_text('[work]\nname = "w"\ncolour = "red"\n', encoding="utf-8")
    with pytest.raises(HeimdallError, match="unknown key 'work.colour'"):
        paths.work_meta(work)
    (work / "heimdall.toml").write_text('[work]\n[extra]\n', encoding="utf-8")
    with pytest.raises(HeimdallError, match="unknown table 'extra'"):
        paths.work_meta(work)


def test_a_work_dirs_name_is_its_folders_unless_given(scratch):
    work = make_work(scratch / "Top-Quark")
    (work / "heimdall.toml").write_text("[work]\n", encoding="utf-8")
    assert paths.work_meta(work) == {"name": "Top-Quark", "expects": "", "cluster": {}, "keep": [], "log": {}}


# ── resolution ──────────────────────────────────────────────────────────────────────────────────

def test_a_bare_name_takes_its_keys_convention_root():
    assert paths.resolve("ep.cmnd", "baseconfig", assignment="Demo") == \
        WORK / "configs" / "Demo" / "ep.cmnd"
    assert paths.resolve("Decay.exe", "executable", assignment="Decay") == WORK / "build" / "Decay" / "Decay.exe"
    assert paths.resolve("jets_data.yoda", "data") == WORK / "datasets" / "jets_data.yoda"


def test_dot_slash_is_the_work_dir_not_the_working_directory(monkeypatch, scratch):
    monkeypatch.chdir(scratch)
    assert paths.resolve("./datasets/jets_data.yoda", "baseconfig", assignment="X") == WORK / "datasets" / "jets_data.yoda"


def test_an_absolute_path_is_kept():
    assert paths.resolve("/tmp/x.cmnd", "baseconfig", assignment="P") == Path("/tmp/x.cmnd")


@pytest.mark.parametrize("value", ["../x.cmnd", "a/../b", ".."])
def test_climbing_out_is_refused(value):
    with pytest.raises(HeimdallError, match="climbs out") as caught:
        paths.resolve(value, "baseconfig", assignment="P")
    assert "./" in caught.value.hint


def test_an_explicit_root_wins():
    assert paths.resolve("events.hepmc", "prelim", root=Path("/o/p")) == Path("/o/p/events.hepmc")


def test_config_lookup_makes_toml_optional():
    target = WORK / "configs" / "Demo" / "jets.toml"
    assert paths.config_file("Demo/jets") == target
    assert paths.config_file("Demo/jets.toml") == target
    with pytest.raises(HeimdallError, match="no errand file"):
        paths.config_file("Demo/nope")


def test_tests_write_into_the_scratch():
    scratch = WORK.parent                                             # the machine root's forge/scratch
    assert paths.results_root() == scratch / "results"
    assert paths.records_root() == scratch / "records" and not hasattr(paths, "logs_root")   # logs: records/<run>/logs (V157)
    assert paths.cache_root() == scratch / "cache"
    assert paths.reports_root() == scratch / "reports"


def test_without_the_variables_the_work_dirs_folders(monkeypatch):
    for var in ("HEIMDALL_RESULTS", "HEIMDALL_RECORDS", "HEIMDALL_CACHE", "HEIMDALL_REPORTS"):
        monkeypatch.delenv(var)
    assert paths.results_root() == WORK / "results"
    assert paths.records_root() == WORK / "records"
    assert paths.cache_root() == WORK / ".cache"
    assert paths.reports_root() == WORK / "reports"


# ── placeholders ────────────────────────────────────────────────────────────────────────────────

def test_heimdall_and_work_are_the_placeholders():
    assert paths.placeholders() == {"heimdall": str(REPO), "apps": str(paths.apps_dir()), "work": str(WORK)}
    assert tools.expand("{apps}/Paint.exe", paths.placeholders(), "t") == f"{paths.apps_dir()}/Paint.exe"
    assert tools.expand("{work}/build/Rivet", paths.placeholders(), "t") == f"{WORK}/build/Rivet"


def test_repo_is_retired_with_its_replacements_named():
    with pytest.raises(HeimdallError, match=r"\{repo\} is retired: \{work\} for your files, \{heimdall\} for Heimdall's"):
        tools.expand("{repo}/modules/x.py", paths.placeholders(), "t")


def test_machine_settings_are_read_from_the_machine_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HEIMDALL_MACHINE", str(tmp_path))
    assert paths.machine_file() == tmp_path / "machine.toml" and paths.machine_settings() == {}
    (tmp_path / "machine.toml").write_text('[cluster]\naccount = "lab"\n', encoding="utf-8")
    assert paths.machine_settings() == {"cluster": {"account": "lab"}}
    (tmp_path / "machine.toml").write_text('[cluster\n', encoding="utf-8")
    with pytest.raises(HeimdallError, match="this machine's settings"):
        paths.machine_settings()
