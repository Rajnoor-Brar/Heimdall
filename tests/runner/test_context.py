"""The point's context file (doc:connections): every tool's card and config,
written when the point starts, at $HEIMDALL_CONTEXT for every tool, kept with its record (V187); generate_cards for
tools not in the chain; `heimdall tools new`."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from runner import paths, tools
from runner.errors import HeimdallError
from support import HEIMDALL, REPO

#: An exec tool that copies the context file it was given (by $HEIMDALL_CONTEXT and by {context}) to its output.
SCRIPT = ('#!/usr/bin/env python3\nimport os, sys\n'
          'given = sys.argv[-2]\nassert given == os.environ["HEIMDALL_CONTEXT"], (given, os.environ["HEIMDALL_CONTEXT"])\n'
          'open(sys.argv[-1], "w").write(open(given).read())\n')


@pytest.fixture
def work(scratch, monkeypatch):
    root = scratch / "w"
    (root / "configs" / "P").mkdir(parents=True)
    (root / "heimdall.toml").write_text('[work]\nname = "t"\n', encoding="utf-8")
    script = root / "copy.py"
    script.write_text(SCRIPT, encoding="utf-8")
    script.chmod(0o755)
    (root / "configs" / "P" / "c.toml").write_text(f"""[errand]
name = "c"
assignment = "P"
configuration = "one"
event_count = 1
threads = 1

[errand.cfgs.one]
tools          = ["copy"]
generate_cards = ["spare"]

[tools.copy]
tool        = "exec"
executable  = "{script}"
arguments   = ["{{context}}", "{{partial:output}}"]
output_file = "context.txt"

[tools.copy.config]
level = 1

[tools.spare]                 # not run: its config, for copy
tool       = "exec"
executable = "/bin/true"

[tools.spare.config]
level = 2

[tools.unused]                # not run, not named: no card, not in the context
tool       = "exec"
executable = "/bin/true"
""", encoding="utf-8")
    for var, value in (("HEIMDALL_WORK", root), ("HEIMDALL_RECORDS", root / "records"), ("HEIMDALL_CACHE", root / "cache"), ("HEIMDALL_RESULTS", root / "results")):
        monkeypatch.setenv(var, str(value))
    paths.reset()
    yield root
    paths.reset()


def test_every_tool_reads_the_context_file_which_the_point_keeps(work):
    done = subprocess.run([str(HEIMDALL), "run", "P/c", "--plain"], cwd=work, capture_output=True, text=True, timeout=300,
                          env={k: v for k, v in os.environ.items() if k != "HEIMDALL_CONFIGS"}, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    [copied] = (work / "results").rglob("context.txt")
    context = tomllib.loads(copied.read_text(encoding="utf-8"))["tools"]
    assert set(context) == {"copy", "spare"}                        # the chain's and generate_cards'
    assert tomllib.loads(Path(context["spare"]["config"]).read_text(encoding="utf-8")) == {"level": 2}
    assert tomllib.loads(Path(context["copy"]["config"]).read_text(encoding="utf-8")) == {"level": 1}
    [kept] = (work / "records").rglob("logs/*/context.toml")       # V187: kept with the point's cards, its record
    assert tomllib.loads(kept.read_text(encoding="utf-8"))["tools"].keys() == context.keys()
    commands = (kept.parent / "commands.sh").read_text(encoding="utf-8")
    assert f"export HEIMDALL_CONTEXT={kept}" in commands and "# group 1: copy" in commands
    assert "HEIMDALL_CONTEXT" not in os.environ                           # never the user's shell's


def test_heimdall_tools_new_copies_a_template_or_extends_a_tool(work):
    made = tools.new_folder("fit", "exec")
    text = made.joinpath("tool.toml").read_text(encoding="utf-8")
    assert "extends" not in text and "config_file" in text and tools.folders()["fit"].origin == "work"
    made = tools.new_folder("sherpa", "sherpa")
    assert "\nextends = \"sherpa\"\n" in made.joinpath("tool.toml").read_text(encoding="utf-8")
    sherpa = tools.folders()["sherpa"]
    assert sherpa.origin == "work" and sherpa.plugin is not None and sherpa.get("tool", "category")
    with pytest.raises(HeimdallError, match="exists already"):
        tools.new_folder("fit", "exec")
    with pytest.raises(HeimdallError, match="no tool folder 'nope'"):
        tools.new_folder("mine", "nope")
    assert any("product results" in line for line in tools.folder_lines("sherpa"))


def test_a_tool_of_ones_own_names_its_program_and_package(work):
    made = tools.new_folder("unfold", "exec", ["root"], "unfold-it")
    spec = tools.folders()["unfold"]
    assert spec.get("tool", "executable") == "unfold-it" and spec.get("tool", "packages") == ["root"]
    assert "config_file" in made.joinpath("tool.toml").read_text(encoding="utf-8")
    made = tools.new_folder("rivet", "rivet", ["rivet", "yoda", "hdf5"])                 # extending: a [tool] of its own
    assert tools.folders()["rivet"].get("tool", "packages") == ["rivet", "yoda", "hdf5"]
    with pytest.raises(HeimdallError, match="no recipe nosuch"):
        tools.new_folder("other", "exec", ["nosuch"])


def test_an_unknown_product_or_table_is_named(work):
    from runner import cli
    text = (work / "configs" / "P" / "c.toml").read_text(encoding="utf-8")
    (work / "configs" / "P" / "c.toml").write_text(text.replace('generate_cards = ["spare"]', 'generate_cards = ["spare:run"]'),
                                                   encoding="utf-8")
    done = subprocess.run([str(HEIMDALL), "check", "P/c"], cwd=work, capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert done.returncode != 0 and "exec makes no product 'run'" in done.stdout + done.stderr


def test_a_renamed_folder_says_its_new_name(work):
    text = (work / "configs" / "P" / "c.toml").read_text(encoding="utf-8")
    (work / "configs" / "P" / "c.toml").write_text(text.replace('tool        = "exec"', 'tool        = "custom"'),
                                                   encoding="utf-8")
    done = subprocess.run([str(HEIMDALL), "check", "P/c"], cwd=work, capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert 'tool = "custom" is tool = "exec" now' in done.stdout + done.stderr and "heimdall migrate" in done.stdout + done.stderr
