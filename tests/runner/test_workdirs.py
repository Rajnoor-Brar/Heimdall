"""`heimdall recognise` and the work dirs a machine knows by title (runner/workdirs.py, V143): the registry is
$HEIMDALL_WORKDIRS here, a file in each test's own folder."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from runner import cli, paths, setup as setupmod, workdirs
from runner.errors import HeimdallError


def a_work_dir(where: Path, name: str | None = None) -> Path:
    where.mkdir(parents=True, exist_ok=True)
    (where / "heimdall.toml").write_text("[work]\n" + (f'name = "{name}"\n' if name else ""), encoding="utf-8")
    return where


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("HEIMDALL_WORKDIRS", str(tmp_path / "workdirs.toml"))
    paths.reset()
    yield tmp_path / "workdirs.toml"
    paths.reset()


def test_a_work_dir_is_recorded_once_by_its_name(registry, tmp_path):
    study = a_work_dir(tmp_path / "Study", "Jets")
    assert workdirs.record(study) == ("Jets", "recorded")
    assert workdirs.record(study / ".") == ("Jets", "known")
    assert workdirs.record(a_work_dir(tmp_path / "Plain")) == ("Plain", "recorded")      # no name: its folder's
    assert workdirs.path_of("Jets") == study
    text = registry.read_text(encoding="utf-8")
    assert '["Jets"]' in text and f'path = "{study}"' in text
    titles = subprocess.run(["sed", "-n", r's/^\["\(.*\)"\]$/\1/p', str(registry)], capture_output=True, text=True, encoding="utf-8")
    assert titles.stdout.split() == ["Jets", "Plain"]                  # what gjallarhorn's completion reads


def test_a_title_follows_its_moved_work_dir_and_is_never_taken_from_another(registry, tmp_path):
    old = a_work_dir(tmp_path / "old", "Jets")
    workdirs.record(old)
    other = a_work_dir(tmp_path / "other", "Jets")
    with pytest.raises(HeimdallError, match="another work dir's") as refused:
        workdirs.record(other)
    assert "--as" in refused.value.hint
    assert workdirs.record(other, "Jets-2") == ("Jets-2", "recorded")
    shutil.rmtree(old)
    new = a_work_dir(tmp_path / "new", "Jets")
    assert workdirs.record(new) == ("Jets", f"moved from {old}")
    assert workdirs.record(new, "Photo") == ("Photo", "renamed from Jets")
    assert set(workdirs.load()) == {"Jets-2", "Photo"}
    with pytest.raises(HeimdallError, match="cannot be a title"):
        workdirs.record(new, 'say "hi"')


def test_a_title_s_path_says_what_became_of_it(registry, tmp_path):
    study = a_work_dir(tmp_path / "Study", "Jets")
    workdirs.record(study)
    with pytest.raises(HeimdallError, match="no work dir titled 'Jet'") as unknown:
        workdirs.path_of("Jet")
    assert "'Jets'" in unknown.value.hint
    (study / "heimdall.toml").unlink()
    with pytest.raises(HeimdallError, match="no longer a work dir"):
        workdirs.path_of("Jets")
    shutil.rmtree(study)
    with pytest.raises(HeimdallError, match="missing"):
        workdirs.path_of("Jets")
    assert workdirs.forget("Jets") == study and workdirs.load() == {}


def test_a_scan_finds_work_dirs_below_but_not_inside_one_outputs_or_hidden_folders(registry, tmp_path):
    root = tmp_path / "Github"
    a = a_work_dir(root / "A")
    b = a_work_dir(root / "deep" / "er" / "B")
    a_work_dir(root / "A" / "studies" / "C")                           # inside a work dir: not entered
    a_work_dir(root / ".hidden" / "D")
    a_work_dir(root / "x" / "results" / "E")
    a_work_dir(root / "1" / "2" / "3" / "4" / "F")                     # five folders down: too deep
    assert workdirs.scan(root) == [a, b]
    assert workdirs.scan(paths.heimdall_root()) == []                       # Heimdall's own fixtures are not studies


def test_heimdall_recognise_records_lists_and_answers_gjallarhorn(registry, tmp_path, capsys):
    root = tmp_path / "Github"
    a = a_work_dir(root / "A", "Alpha")
    b = a_work_dir(root / "B")
    assert cli.main(["recognise", str(root)]) == 0
    out = capsys.readouterr().out
    assert f"Alpha: {a} (recorded)" in out and f"B: {b} (recorded)" in out
    (a / "configs").mkdir()
    assert cli.main(["recognise", str(a / "configs")]) == 0                 # inside a work dir: that one
    assert capsys.readouterr().out == f"Alpha: {a} (known)\n"
    assert cli.main(["recognise", "--path", "Alpha"]) == 0
    assert capsys.readouterr().out == f"{a}\n"                             # all gjallarhorn reads
    assert cli.main(["recognise", "--path", "Alpah"]) == 2
    assert "did you mean 'Alpha'" in capsys.readouterr().err
    assert cli.main(["recognise", str(root), "--as", "X"]) == 2
    assert "--as titles one work dir" in capsys.readouterr().err
    shutil.rmtree(b)
    assert cli.main(["recognise", "--list"]) == 0
    assert capsys.readouterr().out.splitlines() == [f"Alpha  {a}", f"B      {b}  (missing)"]
    assert cli.main(["recognise", "--forget", "B"]) == 0
    assert set(workdirs.load()) == {"Alpha"}


def test_heimdall_setup_recognises_the_work_dir_it_makes(registry, tmp_path):
    said: list[str] = []
    setupmod.setup(tmp_path / "Top Quark", out=said.append)
    assert "recognised as 'Top Quark' (recorded): gjallarhorn 'Top Quark' goes here" in said
    a_work_dir(tmp_path / "elsewhere", "Top Quark")
    shutil.move(str(tmp_path / "Top Quark"), str(tmp_path / "moved"))
    said.clear()
    setupmod.setup(tmp_path / "elsewhere", out=said.append)                 # completing one: recorded too
    assert any(line.startswith("recognised as 'Top Quark' (moved from ") for line in said)
