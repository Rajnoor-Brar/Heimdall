"""One command line (audit 3, phase 7.1): every command is the runner's (build, make, help, stack and the
shell verbs too), described, with did-you-mean, `--dry-run` and `--set` where they belong, `--plain`
anywhere, and record ids in messages only as "(see V93)" (U59–U62)."""

from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path

import pytest

from runner import cli
from runner.errors import HepError

REPO = Path(__file__).resolve().parents[2]
HEP = REPO / "framework" / "bin" / "hep"


def run(*args, **env) -> subprocess.CompletedProcess:
    return subprocess.run([str(HEP), *args], capture_output=True, text=True, encoding="utf-8", timeout=120,
                          env={**os.environ, **env})


def test_an_unknown_command_gets_the_nearest():
    done = run("rn")
    assert done.returncode == 2 and "no command 'rn'" in done.stderr and "did you mean 'run'" in done.stderr


def test_every_command_has_a_description_and_hep_help_shows_it(capsys):
    top = cli.parser()
    commands = cli._described(top)
    assert all(p.description for p in commands.choices.values())
    assert cli.main(["help", "run"]) == 0 and "Plan and run a configuration." in capsys.readouterr().out
    assert cli.main(["help", "stack"]) == 0 and "hep stack build" in capsys.readouterr().out
    assert cli.main(["help", "rn"]) == 2 and "did you mean 'run'" in capsys.readouterr().err


def test_build_parses_its_own_options():
    """U61: argparse, not bash: -j wants a number; --tests is the framework's."""
    done = run("build", "-j")
    assert done.returncode == 2 and "-j" in done.stderr and "expected one argument" in done.stderr
    with pytest.raises(HepError, match=r"--tests builds Heimdall's C\+\+ tests"):
        cli.cmd_build(cli.parse(["build", "--tests"]))
    assert "--framework" in run("build", "--help").stdout


def test_the_shell_verbs_say_to_source_setup():
    done = run("refresh", HEP_ENV_LOADED="")
    assert done.returncode == 2 and "setup.sh's shell function" in done.stderr and "source " in done.stderr


def test_plain_and_dry_run_anywhere():
    args = cli.parse(["--plain", "run", "Demo/jets", "--dry-run", "pdf"])
    assert args.plain and args.plan and args.configuration == "pdf"
    assert cli.parse(["deck", "talk", "--dry-run"]).list
    assert cli.parse(["status", "--set", "run.events=10"]).set == ["run.events=10"]
    assert cli.parse(["check", "--set", "run.events=10"]).set == ["run.events=10"]
    assert cli.parse(["clean", "--set", "run.events=10", "--dry-run"]).set == ["run.events=10"]


def test_check_plans_what_the_set_run_would(capsys):
    assert cli.main(["check", "Demo/jets", "--set", "run.events=10"]) == 0
    assert cli.main(["check", "Demo/jets", "--set", "run.eventz=10"]) == 2
    assert "unknown key 'eventz'" in capsys.readouterr().out


def test_record_ids_in_messages_follow_their_explanation():
    """U62: an error is read without 07_Record.md; an id, when there is one, comes last as "(see V93)"."""
    roots = [REPO / "framework" / "runner", REPO / "framework" / "plot", REPO / "framework" / "tools"]
    bad = []
    for path in sorted(p for root in roots for p in root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "HepError":
                text = " ".join(s.value for s in ast.walk(node) if isinstance(s, ast.Constant) and isinstance(s.value, str))
                for found in re.finditer(r"\b[VCLU]\d{1,3}\b", text):
                    if not re.search(r"\(see [^()]*$", text[:found.start()]):
                        bad.append(f"{path.relative_to(REPO)}:{node.lineno}: {found.group(0)}")
    assert not bad, "record ids not as (see …):\n  " + "\n  ".join(bad)
