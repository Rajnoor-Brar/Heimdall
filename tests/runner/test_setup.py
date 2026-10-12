"""`hep setup` and `hep where` (docs/framework/01_Target.md §4–§5): a work dir from the template, never
overwriting; which Heimdall and work dir a shell sees; the [framework] expects warning."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from runner import paths, setup
from runner.errors import HepError
from support import HEP, REPO, WORK, apps

PLACEHOLDERS = {"name", "revision", "date", "P", "p"}


@pytest.fixture
def quiet():
    lines: list[str] = []
    return lines.append, lines


@pytest.fixture
def git_identity(monkeypatch):
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "Heimdall tests")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "tests@heimdall.invalid")


def test_the_template_names_only_known_placeholders():
    for path in setup.TEMPLATE.rglob("*"):
        if path.is_file():
            names = set(re.findall(r"\{\{(\w+)\}\}", path.read_text(encoding="utf-8")))
            assert names <= PLACEHOLDERS, f"{path.relative_to(REPO)}: {sorted(names - PLACEHOLDERS)}"


def test_a_new_folder_gets_the_template_and_the_key_folders(scratch, quiet):
    out, lines = quiet
    target = scratch / "Top-Quark"
    added = setup.setup(target, out=out)
    for name in ("hep.toml", "Makefile", ".gitignore", "README.md", "CLAUDE.md", ".vscode/settings.json"):
        assert name in added and (target / name).is_file()
    for folder in setup.FOLDERS:
        assert (target / folder).is_dir() and f"{folder}/" in added
    assert lines == [f"added {a}" for a in added]
    assert not (target / "configs" / "Starter").exists()            # no starter without --project
    marker = tomllib.loads((target / "hep.toml").read_text(encoding="utf-8"))
    assert marker["work"]["name"] == "Top-Quark" and marker["framework"]["expects"] == setup.revision()
    assert paths.is_work(target) and "{{" not in (target / "README.md").read_text(encoding="utf-8")


def test_a_project_gets_the_starter(scratch, quiet):
    target = scratch / "w"
    setup.setup(target, project="Jets", name="My study", out=quiet[0])
    toml = (target / "configs" / "Jets" / "jets.toml").read_text(encoding="utf-8")
    assert 'project       = "Jets"' in toml and 'baseconfig  = "jets.cmnd"' in toml
    assert (target / "configs" / "Jets" / "jets.cmnd").is_file() and (target / "modules" / "Jets").is_dir()
    assert paths.work_meta(target)["name"] == "My study"


@pytest.mark.skipif(not (apps() / "App_Pythia.exe").exists(), reason="hep build --framework")
def test_the_starter_passes_hep_check(scratch, quiet):
    target = scratch / "w"
    setup.setup(target, project="Starter", out=quiet[0])
    done = subprocess.run([str(HEP), "check", "Starter/starter"], cwd=target, capture_output=True, text=True,
                          env={**os.environ, "HEP_WORK": str(target)})
    assert done.returncode == 0, done.stdout + done.stderr
    assert "ok    Starter/starter: 2 configuration(s), 3 point(s)" in done.stdout


def test_setup_never_overwrites_and_completes_a_work_dir(scratch, quiet):
    target = scratch / "w"
    setup.setup(target, out=quiet[0])
    (target / "README.md").write_text("mine\n", encoding="utf-8")
    shutil.rmtree(target / "datasets")
    added = setup.setup(target, out=quiet[0])
    assert added == ["datasets/"]                                     # what a fresh clone lacks
    assert (target / "README.md").read_text(encoding="utf-8") == "mine\n"


def test_a_folder_with_files_is_adopted_only_when_asked(scratch, quiet):
    out, lines = quiet
    target = scratch / "old"
    target.mkdir()
    (target / ".gitignore").write_text("build/\n", encoding="utf-8")
    with pytest.raises(HepError, match="is not empty and not a work dir") as caught:
        setup.setup(target, out=out)
    assert "--adopt" in caught.value.hint
    setup.setup(target, adopt=True, out=out)
    assert (target / ".gitignore").read_text(encoding="utf-8") == "build/\n"   # kept, and what it lacks said
    assert any(line.startswith("kept .gitignore; the template's lines it lacks: output/ results/") for line in lines)


@pytest.mark.parametrize("project", ["", "a/b", "_parked", ".hidden"])
def test_a_project_must_be_a_folder_name(scratch, quiet, project):
    with pytest.raises(HepError, match="is not a project name"):
        setup.setup(scratch / "w", project=project, out=quiet[0])


def test_a_file_is_not_a_work_dir(scratch, quiet):
    (scratch / "f").write_text("", encoding="utf-8")
    with pytest.raises(HepError, match="is a file"):
        setup.setup(scratch / "f", out=quiet[0])


@pytest.mark.skipif(not shutil.which("git"), reason="git")
def test_git_commits_what_was_added_once(scratch, quiet, git_identity):
    target = scratch / "w"
    setup.setup(target, project="Starter", git=True, out=quiet[0])
    log = subprocess.run(["git", "log", "--format=%s"], cwd=target, capture_output=True, text=True).stdout.splitlines()
    assert len(log) == 1 and log[0].startswith("hep setup: the work dir w (Heimdall ")
    tracked = subprocess.run(["git", "ls-files"], cwd=target, capture_output=True, text=True).stdout.split()
    assert "hep.toml" in tracked and "configs/Starter/starter.toml" in tracked


# ── hep where ───────────────────────────────────────────────────────────────────────────────────

def test_where_names_heimdall_and_the_work_dir(quiet):
    out, lines = quiet
    assert setup.where(out=out, err=lambda line: None) == 0
    assert lines[0].startswith(f"hep={REPO} ") and lines[1] == f"work={WORK}"


def test_where_work_outside_a_work_dir_is_exit_2(monkeypatch, scratch, quiet):
    errors: list[str] = []
    monkeypatch.delenv("HEP_WORK")
    monkeypatch.chdir(scratch)
    paths.reset()
    try:
        assert setup.where("work", out=quiet[0], err=errors.append) == 2
    finally:
        paths.reset()
    assert errors == ["not inside a work dir (hep setup <dir> makes one)"]


def test_where_hep_is_one_line(quiet):
    out, lines = quiet
    assert setup.where("hep", out=out) == 0 and lines == [str(REPO)]


# ── [framework] expects ─────────────────────────────────────────────────────────────────────────

def expecting(folder: Path, revision: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "hep.toml").write_text(f'[work]\n[framework]\nexpects = "{revision}"\n', encoding="utf-8")
    return folder


def test_no_revision_is_no_warning(scratch):
    assert setup.expects_warning(expecting(scratch / "w", "")) == ""


@pytest.mark.skipif(not (REPO / ".git").exists(), reason="Heimdall is not a git checkout")
def test_a_revision_heimdall_contains_is_no_warning(scratch):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert setup.expects_warning(expecting(scratch / "w", head)) == ""


@pytest.mark.skipif(not (REPO / ".git").exists(), reason="Heimdall is not a git checkout")
def test_a_revision_heimdall_lacks_is_warned_about(scratch):
    warning = setup.expects_warning(expecting(scratch / "w", "0123456789abcdef0123456789abcdef01234567"))
    assert warning.startswith("warning: w was made by Heimdall 0123456789ab, which ") and "git pull" in warning


def shell(script: str) -> subprocess.CompletedProcess:
    """A clean bash, as a user's: nothing of this session's environment but HOME and a plain PATH."""
    env = {"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin"}
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(not Path(os.environ.get("HEP_VENV", "/nowhere"), "bin", "activate").exists(),
                    reason="no venv in the machine root: build the stack")
def test_hep_refresh_reloads_the_shell_in_place():
    out = shell(f"""set -e
        source {REPO}/setup.sh >/dev/null
        before=$_HEP_ADDED
        export PATH=/nowhere:$PATH                       # the user's own, not the environment's: kept
        hep refresh >/dev/null
        type -t hep
        echo "$HEP_ENV_LOADED"
        [ "$_HEP_ADDED" = "$before" ] && echo same-additions
        tr ':' '\\n' <<< "$PATH" | grep -c '^{REPO}/framework/bin$'
        tr ':' '\\n' <<< "$PATH" | grep -c '^/nowhere$'
        hep where --hep""")
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("\n")[:5] == ["function", "1", "same-additions", "1", "1"]
    assert str(REPO) in out.stdout.split("\n")[5]


def test_hep_refresh_without_the_shell_function_says_to_source_setup():
    out = shell(f"{HEP} refresh")
    assert out.returncode == 2
    assert "setup.sh's shell function" in out.stderr and f"source {REPO}/setup.sh" in out.stderr
