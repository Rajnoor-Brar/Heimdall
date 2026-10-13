"""The point's context file (docs/audit_3/06_Plan.md, phase 4.2; 04 §9.4): every tool's card and config,
written when the point starts, at $HEP_CONTEXT for every tool, removed when it ends; generate_cards for
tools not in the chain; `hep tools new`."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from runner import paths, tools
from runner.errors import HepError
from support import HEP, REPO

#: An exec tool that copies the context file it was given (by $HEP_CONTEXT and by {context}) to its output.
SCRIPT = ('#!/usr/bin/env python3\nimport os, sys\n'
          'given = sys.argv[-2]\nassert given == os.environ["HEP_CONTEXT"], (given, os.environ["HEP_CONTEXT"])\n'
          'open(sys.argv[-1], "w").write(open(given).read())\n')


@pytest.fixture
def work(scratch, monkeypatch):
    root = scratch / "w"
    (root / "configs" / "P").mkdir(parents=True)
    (root / "hep.toml").write_text('[work]\nname = "t"\n', encoding="utf-8")
    script = root / "copy.py"
    script.write_text(SCRIPT, encoding="utf-8")
    script.chmod(0o755)
    (root / "configs" / "P" / "c.toml").write_text(f"""[run]
name = "c"
project = "P"
configuration = "one"
event_count = 1
threads = 1

[run.cfgs.one]
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
    for var, value in (("HEP_WORK", root), ("HEP_RECORDS", root / "records"), ("HEP_LOGS", root / "logs"), ("HEP_CACHE", root / "cache"), ("HEP_RESULTS", root / "results")):
        monkeypatch.setenv(var, str(value))
    paths.reset()
    yield root
    paths.reset()


def test_every_tool_reads_the_context_file_which_goes_when_the_point_ends(work):
    done = subprocess.run([str(HEP), "run", "P/c", "--plain"], cwd=work, capture_output=True, text=True, timeout=300,
                          env={k: v for k, v in os.environ.items() if k != "HEP_CONFIGS"})
    assert done.returncode == 0, done.stdout + done.stderr
    [copied] = (work / "results").rglob("context.txt")
    context = tomllib.loads(copied.read_text(encoding="utf-8"))["tools"]
    assert set(context) == {"copy", "spare"}                        # the chain's and generate_cards'
    assert tomllib.loads(Path(context["spare"]["config"]).read_text()) == {"level": 2}
    assert tomllib.loads(Path(context["copy"]["config"]).read_text()) == {"level": 1}
    assert not list((work / "logs").rglob("context.toml"))          # removed when the point ended
    assert "HEP_CONTEXT" not in os.environ                           # never the user's shell's


def test_hep_tools_new_copies_a_template_or_extends_a_tool(work):
    made = tools.new_folder("fit", "exec")
    text = made.joinpath("tool.toml").read_text(encoding="utf-8")
    assert "extends" not in text and "config_file" in text and tools.folders()["fit"].origin == "work"
    made = tools.new_folder("sherpa", "sherpa")
    assert "\nextends = \"sherpa\"\n" in made.joinpath("tool.toml").read_text(encoding="utf-8")
    sherpa = tools.folders()["sherpa"]
    assert sherpa.origin == "work" and sherpa.plugin is not None and sherpa.get("tool", "category")
    with pytest.raises(HepError, match="exists already"):
        tools.new_folder("fit", "exec")
    with pytest.raises(HepError, match="no tool folder 'nope'"):
        tools.new_folder("mine", "nope")
    assert any("product results" in line for line in tools.folder_lines("sherpa"))


def test_an_unknown_product_or_table_is_named(work):
    from runner import cli
    text = (work / "configs" / "P" / "c.toml").read_text(encoding="utf-8")
    (work / "configs" / "P" / "c.toml").write_text(text.replace('generate_cards = ["spare"]', 'generate_cards = ["spare:run"]'),
                                                   encoding="utf-8")
    done = subprocess.run([str(HEP), "check", "P/c"], cwd=work, capture_output=True, text=True, timeout=120)
    assert done.returncode != 0 and "exec makes no product 'run'" in done.stdout + done.stderr


def test_a_renamed_folder_says_its_new_name(work):
    text = (work / "configs" / "P" / "c.toml").read_text(encoding="utf-8")
    (work / "configs" / "P" / "c.toml").write_text(text.replace('tool        = "exec"', 'tool        = "custom"'),
                                                   encoding="utf-8")
    done = subprocess.run([str(HEP), "check", "P/c"], cwd=work, capture_output=True, text=True, timeout=120)
    assert 'tool = "custom" is tool = "exec" now' in done.stdout + done.stderr and "hep migrate" in done.stdout + done.stderr
