"""The block Heimdall keeps in ~/.bashrc and ~/.zshrc (runner/shellrc.py, V143): `gjallarhorn [title]` and
`bifrost`. Every rc file here is in the test's own folder; HOME is never the user's."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from runner import plugins, shellrc, workdirs

REPO = Path(__file__).resolve().parents[2]
NEEDS_VENV = pytest.mark.skipif(not Path(os.environ.get("HEIMDALL_VENV", "/nowhere"), "bin", "activate").exists(),
                                reason="no venv in the machine root: build the stack")


def test_the_block_goes_in_once_and_comes_out_leaving_the_rest(tmp_path):
    rc = tmp_path / ".bashrc"
    mine = "# my settings\nexport A=1\nalias ll='ls -l'"                    # no final newline
    rc.write_text(mine, encoding="utf-8")
    text = shellrc.block("bash", REPO, Path("~/Himinbjorg").expanduser())
    assert shellrc.status(rc, text) == "absent"
    assert shellrc.install(rc, text) == "written" and shellrc.install(rc, text) == "unchanged"
    written = rc.read_text(encoding="utf-8")
    assert written.startswith(mine + "\n\n") and written.count(shellrc.BEGIN) == 1 and written.endswith(shellrc.END + "\n")
    assert shellrc.status(rc, text) == "installed"
    assert shellrc.remove(rc) and rc.read_text(encoding="utf-8") == mine + "\n"
    assert not shellrc.remove(rc)


def test_another_root_s_block_is_left_unless_replaced(tmp_path):
    rc = tmp_path / ".bashrc"
    here = shellrc.block("bash", REPO, tmp_path / "Himinbjorg")
    other = shellrc.block("bash", REPO, tmp_path / "Elsewhere")
    shellrc.install(rc, other)
    rc.write_text(rc.read_text(encoding="utf-8") + "export AFTER=1\n", encoding="utf-8")
    assert shellrc.install(rc, here, replace=False) == "another" and shellrc.status(rc, here) == "another"
    assert shellrc.install(rc, here) == "replaced"
    assert shellrc.status(rc, here) == "installed" and rc.read_text(encoding="utf-8").endswith("export AFTER=1\n")
    assert f"export HEIMDALL_MACHINE={tmp_path / 'Himinbjorg'}" in here                  # not the default: named
    assert "HEIMDALL_MACHINE" not in shellrc.block("bash", REPO, Path("~/Himinbjorg").expanduser())


def test_a_linked_rc_keeps_its_link(tmp_path):
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    (dotfiles / "bashrc").write_text("export A=1\n", encoding="utf-8")
    rc = tmp_path / ".bashrc"
    rc.symlink_to(dotfiles / "bashrc")
    shellrc.install(rc, shellrc.block("bash", REPO, tmp_path))
    assert rc.is_symlink() and shellrc.BEGIN in (dotfiles / "bashrc").read_text(encoding="utf-8")


def test_the_files_follow_the_login_shell_and_what_is_there(tmp_path):
    assert shellrc.rc_files(tmp_path, "/bin/bash") == [("bash", tmp_path / ".bashrc")]
    assert shellrc.rc_files(tmp_path, "/usr/bin/zsh") == [("zsh", tmp_path / ".zshrc")]
    (tmp_path / ".bashrc").write_text("", encoding="utf-8")
    assert shellrc.rc_files(tmp_path, "/bin/zsh") == [("bash", tmp_path / ".bashrc"), ("zsh", tmp_path / ".zshrc")]


def test_both_blocks_define_gjallarhorn_and_bifrost(tmp_path):
    bash = shellrc.block("bash", REPO, tmp_path)
    assert subprocess.run(["bash", "-n"], input=bash, text=True, encoding="utf-8").returncode == 0
    assert f"source {REPO}/gjallarhorn.sh \"$@\"" in bash and f"{REPO}/framework/bin/bifrost \"$@\"" in bash
    zsh = shellrc.block("zsh", REPO, tmp_path)
    assert f"{REPO}/launch.sh --gjallarhorn \"$@\"" in zsh and "compdef _gjallarhorn gjallarhorn" in zsh
    with pytest.raises(ValueError):
        shellrc.block("fish", REPO, tmp_path)


def test_a_build_writes_the_block_once_and_leaves_another(tmp_path, monkeypatch, capsys):
    bs = plugins.load(REPO / "recipes" / "build_stack.py", "build_stack")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", "/bin/bash")
    bs.shell_block(tmp_path / "Himinbjorg")
    assert "gjallarhorn [title] and bifrost written in" in capsys.readouterr().err
    assert shellrc.status(home / ".bashrc", shellrc.block("bash", REPO, tmp_path / "Himinbjorg")) == "installed"
    bs.shell_block(tmp_path / "Scratch")                                      # a scratch root's build
    assert "another checkout's or machine root's" in capsys.readouterr().err
    assert shellrc.status(home / ".bashrc", shellrc.block("bash", REPO, tmp_path / "Himinbjorg")) == "installed"


@NEEDS_VENV
def test_gjallarhorn_loads_the_environment_and_goes_to_the_work_dir(tmp_path, monkeypatch):
    study = tmp_path / "Study"
    study.mkdir()
    (study / "heimdall.toml").write_text('[work]\nname = "Demo"\n', encoding="utf-8")
    monkeypatch.setenv("HEIMDALL_WORKDIRS", str(tmp_path / "workdirs.toml"))
    workdirs.record(study)
    machine = Path(os.environ["HEIMDALL_MACHINE"]).expanduser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))                                       # the block's ~ is this one's
    shellrc.install(home / ".bashrc", shellrc.block("bash", REPO, machine))
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "HEIMDALL_WORKDIRS": str(tmp_path / "workdirs.toml")}
    done = subprocess.run(["bash", "-c", """source ~/.bashrc
        gjallarhorn Demo >/dev/null; pwd; echo "$HEIMDALL_ENV_LOADED"
        gjallarhorn Demi; echo "rc=$?"; pwd; type -t bifrost"""], env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.stdout.splitlines() == [str(study), os.environ["HEIMDALL_INSTALL"], "rc=1", str(study), "function"], done.stderr
    assert "no work dir titled 'Demi'" in done.stderr and "did you mean 'Demo'" in done.stderr


@NEEDS_VENV
def test_launch_runs_a_command_whose_words_are_not_a_title(tmp_path):
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "HEIMDALL_MACHINE": os.environ["HEIMDALL_MACHINE"]}
    done = subprocess.run([str(REPO / "launch.sh"), "heimdall", "where", "--heimdall"], env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0 and done.stdout.strip() == str(REPO), done.stderr
