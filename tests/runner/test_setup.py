"""`heimdall setup` and `heimdall where` (docs/framework/01_Target.md §4–§5): a work dir from the template, never
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
from runner.errors import HeimdallError
from support import HEIMDALL, REPO, WORK, apps

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
    for name in ("heimdall.toml", "Makefile", ".gitignore", "README.md", "CLAUDE.md", ".vscode/settings.json"):
        assert name in added and (target / name).is_file()
    for folder in setup.FOLDERS:
        assert (target / folder).is_dir() and f"{folder}/" in added
    assert lines == [f"added {a}" for a in added] + ["recognised as Top-Quark (recorded): gjallarhorn Top-Quark goes here"]
    assert not (target / "configs" / "Starter").exists()            # no starter without --project
    marker = tomllib.loads((target / "heimdall.toml").read_text(encoding="utf-8"))
    assert marker["work"]["name"] == "Top-Quark" and marker["framework"]["expects"] == setup.revision()
    assert paths.is_work(target) and "{{" not in (target / "README.md").read_text(encoding="utf-8")


def test_a_project_gets_the_starter(scratch, quiet):
    target = scratch / "w"
    setup.setup(target, project="Jets", name="My study", out=quiet[0])
    toml = (target / "configs" / "Jets" / "jets.toml").read_text(encoding="utf-8")
    assert 'assignment = "Jets"' in toml and 'card   = "jets.cmnd"' in toml          # the v3 starter (03 §6)
    assert (target / "configs" / "Jets" / "jets.cmnd").is_file() and (target / "modules" / "Jets").is_dir()
    assert paths.work_meta(target)["name"] == "My study"


@pytest.mark.skipif(not (apps() / "App_Pythia.exe").exists(), reason="heimdall build --framework")
def test_the_starter_passes_heimdall_check(scratch, quiet):
    target = scratch / "w"
    setup.setup(target, project="Starter", out=quiet[0])
    done = subprocess.run([str(HEIMDALL), "check", "Starter/starter"], cwd=target, capture_output=True, text=True,
                          env={**os.environ, "HEIMDALL_WORK": str(target)}, encoding="utf-8")
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
    with pytest.raises(HeimdallError, match="is not empty and not a work dir") as caught:
        setup.setup(target, out=out)
    assert "--adopt" in caught.value.hint
    setup.setup(target, adopt=True, out=out)
    ignore = (target / ".gitignore").read_text(encoding="utf-8")
    assert ignore.startswith("build/\n") and setup.BLOCK in ignore             # kept, and what it lacks added (U67)
    assert any(line.startswith("merged .gitignore: records/ .cache/ results/") for line in lines)


@pytest.mark.parametrize("project", ["", "a/b", "_parked", ".hidden"])
def test_a_project_must_be_a_folder_name(scratch, quiet, project):
    with pytest.raises(HeimdallError, match="is not a project name"):
        setup.setup(scratch / "w", project=project, out=quiet[0])


def test_a_file_is_not_a_work_dir(scratch, quiet):
    (scratch / "f").write_text("", encoding="utf-8")
    with pytest.raises(HeimdallError, match="is a file"):
        setup.setup(scratch / "f", out=quiet[0])


@pytest.mark.skipif(not shutil.which("git"), reason="git")
def test_git_commits_what_was_added_once(scratch, quiet, git_identity):
    target = scratch / "w"
    setup.setup(target, project="Starter", git=True, out=quiet[0])
    log = subprocess.run(["git", "log", "--format=%s"], cwd=target, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    assert len(log) == 1 and log[0].startswith("heimdall setup: the work dir w (Heimdall ")
    tracked = subprocess.run(["git", "ls-files"], cwd=target, capture_output=True, text=True, encoding="utf-8").stdout.split()
    assert "heimdall.toml" in tracked and "configs/Starter/starter.toml" in tracked


# ── heimdall where ───────────────────────────────────────────────────────────────────────────────────

def test_where_names_heimdall_and_the_work_dir(quiet):
    out, lines = quiet
    assert setup.where(out=out, err=lambda line: None) == 0
    assert lines[0].startswith(f"heimdall={REPO} ") and lines[1] == f"work={WORK}"


def test_where_work_outside_a_work_dir_is_exit_2(monkeypatch, scratch, quiet):
    errors: list[str] = []
    monkeypatch.delenv("HEIMDALL_WORK")
    monkeypatch.chdir(scratch)
    paths.reset()
    try:
        assert setup.where("work", out=quiet[0], err=errors.append) == 2
    finally:
        paths.reset()
    assert errors == ["not inside a work dir (heimdall setup <dir> makes one)"]


def test_where_heimdall_is_one_line(quiet):
    out, lines = quiet
    assert setup.where("heimdall", out=out) == 0 and lines == [str(REPO)]


# ── [framework] expects ─────────────────────────────────────────────────────────────────────────

def expecting(folder: Path, revision: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "heimdall.toml").write_text(f'[work]\n[framework]\nexpects = "{revision}"\n', encoding="utf-8")
    return folder


def test_no_revision_is_no_warning(scratch):
    assert setup.expects_warning(expecting(scratch / "w", "")) == ""


@pytest.mark.skipif(not (REPO / ".git").exists(), reason="Heimdall is not a git checkout")
def test_a_revision_heimdall_contains_is_no_warning(scratch):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    assert setup.expects_warning(expecting(scratch / "w", head)) == ""


@pytest.mark.skipif(not (REPO / ".git").exists(), reason="Heimdall is not a git checkout")
def test_a_revision_heimdall_lacks_is_warned_about(scratch):
    warning = setup.expects_warning(expecting(scratch / "w", "0123456789abcdef0123456789abcdef01234567"))
    assert warning.startswith("warning: w was made by Heimdall 0123456789ab, which ") and "git pull" in warning


def shell(script: str) -> subprocess.CompletedProcess:
    """A clean bash, as a user's: nothing of this session's environment but HOME and a plain PATH."""
    env = {"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin"}
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=120, encoding="utf-8")


@pytest.mark.skipif(not Path(os.environ.get("HEIMDALL_VENV", "/nowhere"), "bin", "activate").exists(),
                    reason="no venv in the machine root: build the stack")
def test_heimdall_refresh_reloads_the_shell_in_place():
    out = shell(f"""set -e
        source {REPO}/gjallarhorn.sh >/dev/null
        before=$_HEIMDALL_ADDED
        export PATH=/nowhere:$PATH                       # the user's own, not the environment's: kept
        heimdall refresh >/dev/null
        type -t heimdall
        echo "$HEIMDALL_ENV_LOADED"
        [ "$_HEIMDALL_ADDED" = "$before" ] && echo same-additions
        tr ':' '\\n' <<< "$PATH" | grep -c '^{REPO}/framework/bin$'
        tr ':' '\\n' <<< "$PATH" | grep -c '^/nowhere$'
        heimdall where --heimdall""")
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("\n")[:5] == ["function", os.environ["HEIMDALL_INSTALL"], "same-additions", "1", "1"]
    assert str(REPO) in out.stdout.split("\n")[5]


@pytest.mark.parametrize("verb", ["refresh", "quit", "cd"])
def test_the_shell_verbs_without_the_shell_function_say_to_source_setup(verb):
    out = shell(f"{HEIMDALL} {verb}")
    assert out.returncode == 2
    assert "gjallarhorn.sh's shell function" in out.stderr and f"source {REPO}/gjallarhorn.sh" in out.stderr


# ── the shell (docs/audit_3/06_Plan.md, phase 3.3) ──────────────────────────────────────────────

NEEDS_VENV = pytest.mark.skipif(not Path(os.environ.get("HEIMDALL_VENV", "/nowhere"), "bin", "activate").exists(),
                                reason="no venv in the machine root: build the stack")


def a_machine(root: Path, machine_sh: str = "") -> Path:
    """A machine root of the test's: the real venv, linked; stack folders that are empty but there; an
    isolated toolkit's stack, kit, with the gjallarhorn.sh the build writes."""
    for base in (root, root / "stacks" / "kit"):
        for sub in ("root/bin", "root/lib"):
            (base / "stack" / sub).mkdir(parents=True)
        (base / "venv").symlink_to(os.environ["HEIMDALL_VENV"], target_is_directory=True)
    (root / "stacks" / "kit" / "gjallarhorn.sh").write_text(
        f'export HEIMDALL_MACHINE="{root}" HEIMDALL_STACK_REQUEST=kit\nsource "{REPO}/gjallarhorn.sh"\n', encoding="utf-8")
    if machine_sh:
        (root / "machine.sh").write_text(machine_sh, encoding="utf-8")
    return root


@pytest.mark.parametrize("other", ["dash", "zsh", "ksh"])
def test_a_shell_that_is_not_bash_is_turned_away_untouched(other):
    if not shutil.which(other):
        pytest.skip(f"no {other} here")
    out = subprocess.run([other, "-c", f". {REPO}/gjallarhorn.sh; echo rc=$?; env"], capture_output=True, text=True,
                         env={"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin"}, timeout=60, encoding="utf-8")
    assert out.stderr.count("\n") == 1 and "launch.sh" in out.stderr
    assert "rc=1" in out.stdout and not re.search(r"^(HEIMDALL|VIRTUAL_ENV|LD_LIBRARY_PATH)\w*=", out.stdout, re.M)
    assert re.search(r"^PATH=/usr/bin:/bin$", out.stdout, re.M)


@NEEDS_VENV
def test_heimdall_runs_without_the_environment_or_home():
    """bin/heimdall runs the machine's venv Python by path: cron, scripts and Slurm need no `source gjallarhorn.sh`."""
    out = subprocess.run([str(HEIMDALL), "where"], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
                         timeout=60, cwd="/", encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith(f"heimdall={REPO}") and "\nmachine=" in out.stdout


@NEEDS_VENV
def test_switching_to_an_isolated_stack_takes_the_other_out_and_refresh_keeps_it(scratch):
    root = a_machine(scratch / "machine")
    out = shell(f"""set -e
        export HEIMDALL_MACHINE={root}
        source {REPO}/gjallarhorn.sh >/dev/null
        echo "$HEIMDALL_ENV_LOADED"
        source {root}/stacks/kit/gjallarhorn.sh >/dev/null       # no quit first
        echo "$HEIMDALL_STACK $HEIMDALL_ENV_LOADED"
        tr ':' '\n' <<< "$PATH" | grep -c '^{root}/stack/root/bin$' || true
        heimdall refresh >/dev/null
        echo "$HEIMDALL_STACK $HEIMDALL_INSTALL"
        tr ':' '\n' <<< "$PATH" | grep -c '^{root}/stacks/kit/stack/root/bin$'
        heimdall where | tail -n 1""")
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("\n")[:6] == [
        f"{root}/stack", f"kit {root}/stacks/kit/stack", "0", f"kit {root}/stacks/kit/stack", "1",
        f"machine={root} (stack: {root}/stacks/kit)"]


@NEEDS_VENV
def test_quit_undoes_machine_sh_and_refresh_never_piles_it_up(scratch):
    """The Mac's machine.sh (DYLD_LIBRARY_PATH, the GNU tools first), a scalar it changes, one it adds, one it
    unsets: after gjallarhorn and quit, the environment is as it was."""
    root = a_machine(scratch / "machine", "export DYLD_LIBRARY_PATH=$LD_LIBRARY_PATH\n"
                                           "PATH=/opt/gnubin:$PATH; export PATH\n"
                                           "export FOO=machine KEPT=changed\nunset GONE\n")
    # (PS1 is the venv's: its deactivate leaves "(HEIMDALL) " when the prompt was empty, as only a script's is)
    keep = "grep -v -e '^_=' -e '^HEIMDALL=' -e '^SHLVL=' -e '^PWD=' -e '^OLDPWD=' -e '^PS1=' | sort"
    out = shell(f"""set -e
        export HEIMDALL_MACHINE={root} PATH=/opt/gnubin:/usr/bin:/bin KEPT=orig GONE=here
        before=$(env | {keep})
        source {REPO}/gjallarhorn.sh >/dev/null
        echo "$FOO $KEPT ${{GONE-gone}}"
        tr ':' '\n' <<< "$DYLD_LIBRARY_PATH" | grep -c '^{root}/stack/root/lib$'
        heimdall refresh >/dev/null
        heimdall refresh >/dev/null
        tr ':' '\n' <<< "$PATH" | grep -c '^/opt/gnubin$'
        heimdall quit
        after=$(env | {keep})
        [ "$before" = "$after" ] && echo as-before || diff <(echo "$before") <(echo "$after")""")
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("\n")[:4] == ["machine changed gone", "1", "2", "as-before"], out.stdout


def a_base_machine(root: Path) -> Path:
    """A machine root on a conda base, for the test: the real venv's Python dressed as the base's prefix
    (its pyvenv.cfg copied, bin/python and lib/ linked), an activate.d script as a compiler's, and the
    activate.sh the build writes (recipes/build_stack.py)."""
    from runner import plugins
    bs = plugins.load(REPO / "recipes" / "build_stack.py", "build_stack")
    env = root / "base" / ".pixi" / "envs" / "default"
    (env / "bin").mkdir(parents=True)
    venv = Path(os.environ["HEIMDALL_VENV"])
    (env / "pyvenv.cfg").write_text((venv / "pyvenv.cfg").read_text(encoding="utf-8"), encoding="utf-8")
    (env / "bin" / "python").symlink_to(venv / "bin" / "python")
    (env / "lib").symlink_to(venv / "lib", target_is_directory=True)
    (env / "etc" / "conda" / "activate.d").mkdir(parents=True)
    (env / "etc" / "conda" / "activate.d" / "activate-gxx.sh").write_text(
        "export CXX=x86_64-conda-linux-gnu-c++ CXXFLAGS='-march=nocona' CMAKE_ARGS=-DX=1\n", encoding="utf-8")
    (root / "base" / "activate.sh").write_text(bs.activate_text({"base": str(env), "base_dir": str(root / "base")}),
                                               encoding="utf-8")
    for sub in ("root/bin", "root/lib"):
        (root / "stack" / sub).mkdir(parents=True)
    return root


@NEEDS_VENV
def test_a_conda_base_is_loaded_kept_off_ld_library_path_and_quit_takes_it_out(scratch):
    """docs/conda/02 §5: gjallarhorn.sh sources base/activate.sh (the compilers, not their flags), the base is
    the Python environment, its lib/ never joins LD_LIBRARY_PATH, and quit leaves the shell as it was."""
    root = a_base_machine(scratch / "machine")
    env = root / "base" / ".pixi" / "envs" / "default"
    keep = "grep -v -e '^_=' -e '^HEIMDALL=' -e '^SHLVL=' -e '^PWD=' -e '^OLDPWD=' -e '^PS1=' | sort"
    out = shell(f"""set -e
        export HEIMDALL_MACHINE={root} CXXFLAGS=-O1
        before=$(env | {keep})
        source {REPO}/gjallarhorn.sh >/dev/null
        echo "$HEIMDALL_BASE|$HEIMDALL_VENV|$CONDA_PREFIX|$CXX|${{CXXFLAGS-unset}}|$CMAKE_ARGS"
        tr ':' '\n' <<< "$PATH" | grep -c '^{env}/bin$'
        tr ':' '\n' <<< "${{LD_LIBRARY_PATH-}}" | grep -c '^{env}' || true
        tr ':' '\n' <<< "$LD_LIBRARY_PATH" | grep -c '^{root}/stack/root/lib$'
        heimdall refresh >/dev/null
        tr ':' '\n' <<< "$PATH" | grep -c '^{env}/bin$'
        heimdall quit
        after=$(env | {keep})
        [ "$before" = "$after" ] && echo as-before || diff <(echo "$before") <(echo "$after")""")
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("\n")[:6] == [f"{env}|{env}|{env}|x86_64-conda-linux-gnu-c++|unset|-DX=1",
                                           "1", "0", "1", "1", "as-before"], out.stdout


def test_heimdall_cd_goes_to_a_project_folder_of_the_work_dir():
    out = shell(f"""set -e
        source {REPO}/gjallarhorn.sh >/dev/null
        export HEIMDALL_WORK={WORK}
        heimdall cd Demo
        pwd
        heimdall cd Demo modules >/dev/null 2>&1 || echo no-modules""")
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("\n")[0] == str(WORK / "configs" / "Demo")
