"""Tab completion: `heimdall __complete CWORD WORD…` answers by the argument's kind, from the parser and from the readers
heimdall has; it writes nothing, says nothing and is quick; env/complete.bash turns the answer into `COMPREPLY`."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from runner import cli, complete, paths, runs
from runner.paths import records_root, results_root

REPO = Path(__file__).resolve().parents[2]


def ask(*words: str) -> tuple[list[str], str]:
    """What TAB gives after `heimdall WORDS…`: the last word is the one being typed ("" for a new word)."""
    return complete.complete(cli.parser(), len(words), list(words))


@pytest.fixture
def tree(scratch, monkeypatch):
    """records/, results/ and the run registry of one test, with Runs, points and tool logs in them."""
    for var, name in (("HEIMDALL_RECORDS", "records"), ("HEIMDALL_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    for run in ("01_first", "02_second"):
        base = records_root() / "Demo" / "jets" / run
        (base / "points" / "pdf_a").mkdir(parents=True)
        (base / "logs" / "pdf_a").mkdir(parents=True)
        (base / "logs" / "pdf_a" / "pythia.log").write_text("x\n", encoding="utf-8")
        (base / "logs" / "pdf_a" / "pythia.full.log").write_text("x\n", encoding="utf-8")
    (records_root() / "Demo" / "library" / "0123456789abcdef").mkdir(parents=True)
    (records_root() / "Generators" / "generators" / "01_only").mkdir(parents=True)
    (results_root() / "Demo" / "jets" / "03_results_only").mkdir(parents=True)
    (results_root() / "Demo" / "jets" / "01_first").mkdir(parents=True)
    return scratch


@pytest.fixture
def registry(monkeypatch):
    """Three entries: a running one (this process), a finished one and one that is lost."""
    now = time.time()
    running, done, lost = (runs.new_id(now - back) for back in (10, 20, 30))
    runs.begin(running, {"started": now - 10})
    runs.begin(done, {"started": now - 20})
    runs.finish(done, 0)
    runs.begin(lost, {"started": now - 30, "pid": 2 ** 22 + 7, "pstart": "1"})
    return running, done, lost


# ── the walk: commands, options and choices ─────────────────────────────────────────────────────

def test_commands_and_options_come_from_the_parser():
    assert ask("run", "--q") == (["--queued-to"], "plain")
    assert ask("records", "") == (["upgrade"], "plain")
    assert ask("--plain", "r")[0] == ["rank", "recognise", "records", "refresh", "report", "reproduce", "run", "runs"]
    assert "--plain" in ask("--")[0] and "stats" not in ask("s")[0] and "deck" not in ask("d")[0]
    assert ask("library", "")[0] == ["adopt", "list", "prune", "verify"]
    assert ask("run", "--only", "p")[0] == ["plot", "post", "pre"] and ask("run", "--only", "po")[0] == ["post"]
    assert ask("setup", "x", "--git", "")[0] == ["new", "yes"] and ask("bifrost", "--shell", "")[0] == ["install", "remove"]
    assert ask("stack", "")[0] == ["build", "doctor", "list", "status"] and ask("stack", "build", "")[0] == []
    assert ask("nonesuch", "")[0] == [] and ask("stats", "")[0] == []


def test_an_option_given_is_not_offered_again_unless_it_adds():
    assert "--points" not in ask("run", "Demo/jets", "--points", "x", "--p")[0]
    assert ask("run", "Demo/jets", "--set", "a=b", "--se")[0] == ["--set"]


def test_every_argument_of_every_command_has_a_kind_or_is_free_text():
    """A new command or option cannot go uncompleted unnoticed."""
    missing = []
    for name, sub in complete._commands(cli.parser()).items():
        if name in complete.RETIRED or name in complete.REST:
            continue
        options, positionals = complete.parts_of(sub)
        for action in {*options.values(), *positionals}:
            takes = bool(action.option_strings == [] or action.nargs != 0)
            if action.dest == "help" or not takes or action.choices or action.help == argparse.SUPPRESS:
                continue
            if (name, action.dest) not in complete.KINDS and (name, action.dest) not in complete.FREE:
                missing.append(f"{name} {action.dest}")
    assert not missing, missing
    assert not {k for k in complete.KINDS if k in complete.FREE}                     # one or the other
    assert set(complete.KINDS.values()) <= set(complete.KIND)


# ── the kinds, on the scratch work dir ──────────────────────────────────────────────────────────

def test_an_errand_is_a_config_and_after_its_slash_a_run_of_records(tree):
    assert ask("run", "")[0][:2] == ["Decay/", "Demo/"] and ask("run", "Demo/je") == (["Demo/jets"], "plain")
    assert ask("run", "Demo/")[1] == "plain" or ask("run", "Demo/")[1] == "nospace"
    assert ask("run", "Demo/jets/") == (["Demo/jets/01_first", "Demo/jets/02_second"], "plain")     # records/ alone
    assert ask("status", "Demo/jets/0")[0] == ["Demo/jets/01_first", "Demo/jets/02_second"]
    assert ask("run", "./") == ([], "files:*.toml") and ask("run", "/tmp/") == ([], "files:*.toml")
    assert "Demo/library" not in ask("run", "Demo/")[0] and "Demo/jets/library" not in ask("run", "Demo/jets/")[0]


def test_a_drawing_takes_the_runs_of_records_and_of_results_alike(tree):
    assert ask("plot", "Demo/jets/") == (["Demo/jets/01_first", "Demo/jets/02_second", "Demo/jets/03_results_only"], "plain")
    assert "Demo/jets/03_results_only" not in ask("run", "Demo/jets/")[0]
    assert ask("plot", "./") == ([], "files:*.toml")


def test_a_configuration_is_one_of_the_errand_already_typed(tree):
    names = ask("run", "Demo/jets", "")[0]
    assert names and all(not n.startswith("Demo") for n in names) and ask("run", "Demo/jets", "p")[0] == [n for n in names if n.startswith("p")]
    assert ask("plot", "Demo/jets/01_first", "")[0] == names                         # a Run of it names the same errand
    assert ask("run", "", "")[0] == [] and ask("run", "Demo/nonesuch", "")[0] == []   # a missing errand: nothing, no error


def test_a_broken_errand_gives_no_configurations_and_no_error(tree, monkeypatch, scratch, capsys):
    configs = scratch / "configs"
    (configs / "Demo").mkdir(parents=True)
    (configs / "Demo" / "broken.toml").write_text("[errand\n", encoding="utf-8")
    monkeypatch.setenv("HEIMDALL_WORK", str(scratch))
    monkeypatch.setattr(paths, "configs_root", lambda: configs)
    assert ask("run", "Demo/broken", "")[0] == []
    assert cli.main(["__complete", "3", "run", "Demo/broken", ""]) == 0
    assert capsys.readouterr().out == ":plain\n"


def test_check_migrate_and_clean_take_errands_without_runs(tree):
    for command in ("check", "migrate", "clean"):
        assert ask(command, "Demo/je")[0] == ["Demo/jets"]
        assert ask(command, "Demo/jets/")[0] == []
    assert ask("ls", "")[0] == ["Decay", "Demo", "Generators"]


def test_a_record_deep_goes_from_a_run_to_a_point_to_a_tool(tree):
    assert ask("show", "")[0] == ["Demo/", "Generators/"] and ask("show", "Demo/jets/0")[0] == [
        "Demo/jets/01_first", "Demo/jets/01_first/", "Demo/jets/02_second", "Demo/jets/02_second/"]
    assert ask("log", "Demo/jets/01_first/") == (["Demo/jets/01_first/pdf_a", "Demo/jets/01_first/pdf_a/"], "nospace")
    assert ask("log", "Demo/jets/01_first/pdf_a/") == (["Demo/jets/01_first/pdf_a/pythia"], "plain")
    assert ask("show", "./")[1] == "dirs" and ask("log", "Demo/nonesuch/x/")[0] == []


def test_a_record_a_result_and_a_scope(tree):
    assert ask("tag", "Demo/jets/")[0] == ["Demo/jets/01_first", "Demo/jets/02_second"]
    assert ask("diff", "Demo/jets/01_first", "02")[0] == ["02_second"]                  # the bare Run of the first one's Errand
    assert "Demo/jets/02_second" in ask("diff", "Demo/jets/01_first", "Demo/jets/0")[0]
    assert ask("rank", "Demo/jets/")[0] == ["Demo/jets/01_first", "Demo/jets/03_results_only"]
    assert ask("rank", "Demo/je") == (["Demo/jets", "Demo/jets/"], "nospace")         # an Errand's results, or a Run's
    assert ask("records", "upgrade", "Demo/")[0] == ["Demo/jets", "Demo/jets/"] and ask("library", "list", "")[0] == ["Demo", "Demo/", "Generators", "Generators/"]
    assert ask("library", "list", "Demo/")[0] == ["Demo/jets", "Demo/jets/"] and "Demo/library" not in ask("records", "upgrade", "Demo/")[0]
    assert ask("migrate", "--snapshot", "Demo/jets/0")[0] == ["Demo/jets/01_first", "Demo/jets/02_second"]


def test_a_report_takes_a_recipe_or_a_result_and_files_complete_by_their_name(tree):
    assert ask("report", "Demo/jets/")[0] == ["Demo/jets/01_first", "Demo/jets/03_results_only"]
    assert ask("report", "./") == ([], "files:*.toml")
    assert ask("reproduce", "")[1] == "files:provenance.json"
    assert ask("overlay", "a.yoda", "")[1] == "files:@(*.yoda|*.yoda.gz|*.root)"
    assert ask("plot", "Demo/jets", "--plot", "")[1] == "files:" and ask("watch", "--file", "")[1] == "files:"
    assert ask("setup", "")[1] == "dirs" and ask("recognise", "")[1] == "dirs"


def test_names_of_the_schema_the_tools_and_the_commands():
    assert ask("explain", "pl")[0] == ["plot."] and ask("explain", "pl")[1] == "nospace"
    keys = ask("explain", "plot.y_")[0]
    assert "plot.y_gutter" in keys and all(k.startswith("plot.y_") for k in keys)
    assert ask("explain", "nonesuch.")[0] == []
    assert "new" in ask("tools", "")[0] and "pythia" in ask("tools", "p")[0]
    assert ask("help", "ru")[0] == ["run", "runs"]


def test_runs_complete_by_id_and_by_pid_and_never_prune_the_registry(registry):
    running, done, lost = registry
    before = sorted(p.name for p in runs.folder().iterdir())
    everyone = sorted([running, done, lost])
    assert ask("runs", "--again", "")[0] == everyone and ask("runs", "-i", "")[0] == everyone
    assert ask("runs", "--resume-queue", running[:15])[0] == [running]
    assert ask("run", "Demo/jets", "--queued-to", "")[0] == sorted([running, lost])          # the ones that have not finished
    assert ask("stop", "--pid", "")[0] == sorted({str(os.getpid()), str(2 ** 22 + 7)})
    assert ask("runs", "--resume", "")[0] == [] and ask("watch", "-i", "")[0] == []        # a live number is not offered
    assert sorted(p.name for p in runs.folder().iterdir()) == before


def test_the_run_states_complete_after_the_last_comma_too():
    assert ask("runs", "--state", "ru")[0] == ["running"]
    assert ask("runs", "--state", "failed,lo")[0] == ["failed,lost"]
    assert "failed,done" in ask("runs", "--state", "failed,")[0]


def test_outside_a_work_dir_the_path_kinds_give_nothing_and_commands_still_complete(tmp_path, monkeypatch):
    for var in ("HEIMDALL_WORK", "HEIMDALL_RECORDS", "HEIMDALL_RESULTS"):
        monkeypatch.delenv(var)
    monkeypatch.chdir(tmp_path)
    assert ask("run", "")[0] == [] and ask("show", "")[0] == [] and ask("ls", "")[0] == []
    assert "run" in ask("r")[0] and ask("run", "--q")[0] == ["--queued-to"]


# ── silent, read-only and quick, as bash calls it ───────────────────────────────────────────────

def snapshot(*roots: Path) -> dict[str, float]:
    return {str(p): p.stat().st_mtime_ns for root in roots if root.exists() for p in [root, *root.rglob("*")]}


def hear(*words: str, cwd: Path | None = None) -> tuple[list[str], str, float]:
    """`heimdall __complete` as a program: (the candidates, the directive, seconds)."""
    started = time.time()
    done = subprocess.run([sys.executable, "-X", "utf8", str(REPO / "framework" / "bin" / "run"), "__complete", str(len(words)), *words],
                          capture_output=True, text=True, check=False, cwd=cwd or os.environ["HEIMDALL_WORK"], timeout=30)
    elapsed = time.time() - started
    assert done.returncode == 0 and done.stderr == "", done.stderr
    *found, last = done.stdout.splitlines()
    assert last.startswith(":")
    return found, last[1:], elapsed


CASES = [("",), ("r",), ("run", "--q"), ("run", ""), ("run", "Demo/jets/"), ("run", "Demo/jets", ""), ("plot", "Demo/jets/"),
         ("show", "Demo/jets/01_first/pdf_a/"), ("rank", "Demo/"), ("explain", "plot.y_"), ("tools", "p"),
         ("runs", "--again", ""), ("runs", "--state", "failed,"), ("stop", "--pid", ""), ("diff", "Demo/jets/01_first", ""),
         ("records", "upgrade", ""), ("library", "list", ""), ("report", ""), ("ls", ""), ("help", "")]


def test_completion_writes_nothing_and_says_nothing_as_a_program(tree, registry):
    watched = (Path(os.environ["HEIMDALL_WORK"]), records_root(), results_root(), runs.folder())
    before = snapshot(*watched)
    for words in CASES:
        found, directive, elapsed = hear(*words)
        assert directive in ("plain", "nospace", "dirs") or directive.startswith("files:")
        assert elapsed < 2.0, (words, elapsed)                              # Python's start is most of it; bash waits on this
    assert snapshot(*watched) == before                                     # nothing written, the registry not pruned
    assert hear("run", "")[0][:2] == ["Decay/", "Demo/"]
    assert hear("show", "Demo/jets/01_first/pdf_a/")[:2] == (["Demo/jets/01_first/pdf_a/pythia"], "plain")


def test_each_kind_answers_within_150_ms_once_python_is_up(tree, registry):
    parser = cli.parser()
    for words in CASES:
        started = time.perf_counter()
        complete.complete(parser, len(words), list(words))
        assert time.perf_counter() - started < 0.15, words


def test_a_failure_in_a_reader_is_no_candidates_and_no_traceback(monkeypatch, capsys):
    monkeypatch.setattr(complete, "_configs", lambda: 1 / 0)
    assert cli.main(["__complete", "2", "run", ""]) == 0
    assert capsys.readouterr().out == ":plain\n"
    assert cli.main(["__complete", "x"]) == 0 and capsys.readouterr().out == ":plain\n"


# ── the bash function ───────────────────────────────────────────────────────────────────────────

def reply(*words: str) -> tuple[list[str], list[str]]:
    """`_heimdall` of env/complete.bash with `words` typed (the last being the one TAB is on): (COMPREPLY, what it asked of
    compopt). compopt is a function here: outside a completion the builtin refuses."""
    script = ('compopt() { OPTS+=("$*"); }; OPTS=(); source "$HEIMDALL/env/complete.bash"; '
              f'COMP_WORDS=(heimdall {" ".join(repr(w) for w in words)}); COMP_CWORD={len(words)}; _heimdall; '
              'printf "%s\\n" "${COMPREPLY[@]}"; echo "--"; printf "%s\\n" "${OPTS[@]}"')
    env = {**os.environ, "PATH": f"{REPO / 'framework' / 'bin'}:{os.environ['PATH']}"}
    done = subprocess.run(["bash", "--noprofile", "--norc", "-c", script], capture_output=True, text=True, check=False,
                          cwd=os.environ["HEIMDALL_WORK"], env=env, timeout=60)
    assert done.returncode == 0, done.stderr
    found, _, opts = done.stdout.partition("--\n")
    return found.split(), [o for o in opts.split("\n") if o]


def test_the_bash_function_sets_compreply_from_the_answer(tree):
    assert reply("r") == (["rank", "recognise", "records", "refresh", "report", "reproduce", "run", "runs"], [])
    assert reply("run", "--q") == (["--queued-to"], [])
    assert reply("run", "Demo/jets/") == (["Demo/jets/01_first", "Demo/jets/02_second"], [])
    assert reply("run", "Demo/je") == (["Demo/jets"], [])
    assert reply("show", "Demo/jets/01_first/") == (["Demo/jets/01_first/pdf_a", "Demo/jets/01_first/pdf_a/"], ["-o nospace"])
    assert reply("run", "Dem")[0] == ["Demo/"] and reply("run", "Dem")[1] == ["-o nospace"]        # a level that goes on: no space


def test_the_bash_function_hands_files_and_folders_to_the_shell(tree):
    found, opts = reply("run", "./co")
    assert found == ["./configs"] and opts == ["-o filenames"]                                       # a folder
    found, opts = reply("run", "./configs/Demo/je")
    assert found == ["./configs/Demo/jets.toml"] and opts == ["-o filenames"]                       # *.toml only
    assert reply("run", "./configs/Demo/ep.c") == ([], ["-o filenames"])                             # not a .toml
    assert reply("setup", "./co")[0] == ["./configs"]


def test_heimdall_cd_is_answered_in_bash(tree):
    assert reply("cd", "D") == (["Decay", "Demo"], []) and reply("cd", "Demo", "r") == (["results", "records"], [])
    assert reply("cd", "Demo", "x") == ([], []) and reply("quit", "") == ([], []) and reply("refresh", "") == ([], [])


def test_the_environment_wires_the_completion_in_and_quit_takes_it_out(tree):
    script = ('source "$HEIMDALL/env/heimdall_env.sh"; complete -p heimdall | grep -c "_heimdall heimdall"; '
              'quit >/dev/null; complete -p heimdall 2>/dev/null | grep -c _heimdall')
    done = subprocess.run(["bash", "--noprofile", "--norc", "-c", script], capture_output=True, text=True, check=False, timeout=60)
    assert done.stdout.split() == ["1", "0"], (done.stdout, done.stderr)
