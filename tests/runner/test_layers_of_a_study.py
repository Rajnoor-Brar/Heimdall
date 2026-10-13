"""A study's own layers over Heimdall's (docs/audit_3/06_Plan.md, phase 4.3): the machine's and the work
dir's style.toml under a run's style; a vocabulary name declared by a tool folder; the work dir's
latex.toml; the plot code in framework/plot/."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from runner import house, labels, paths, plot, quantities, tools
from runner.errors import HepError
from support import REPO


@pytest.fixture
def roots(scratch, monkeypatch):
    work, machine = scratch / "w", scratch / "m"
    (work / "configs" / "P").mkdir(parents=True)
    (work / "hep.toml").write_text('[work]\nname = "t"\n', encoding="utf-8")
    machine.mkdir()
    for var, value in (("HEP_WORK", work), ("HEP_RECORDS", work / "records"), ("HEP_LOGS", work / "logs"), ("HEP_CACHE", work / "cache"), ("HEP_RESULTS", work / "results"),
                       ("HEP_MACHINE", machine)):
        monkeypatch.setenv(var, str(value))
    paths.reset()
    yield work, machine
    paths.reset()


def test_the_style_layers_lie_between_base_toml_and_the_run(roots):
    work, machine = roots
    (machine / "style.toml").write_text('[page]\ndpi = 150\nfont = "sans"\n', encoding="utf-8")
    (work / "style.toml").write_text('[page]\ndpi = 200\n', encoding="utf-8")
    assert plot.house_style() == {"page": {"dpi": 200, "font": "sans"}}            # the work dir's over the machine's
    (work / "style.toml").write_text('[page]\ndip = 200\n', encoding="utf-8")
    with pytest.raises(HepError, match="no key 'page.dip'") as caught:
        plot.house_style()
    assert str(work / "style.toml") in str(caught.value.where)


def test_a_folder_declares_a_quantity_and_it_binds_without_a_key(roots):
    work, _ = roots
    shutil.copytree(REPO / "framework" / "tools" / "exec", work / "tools" / "fit", ignore=shutil.ignore_patterns("__pycache__"))
    (work / "tools" / "fit" / "quantities.toml").write_text(
        'window = { key = "window", shape = ["float", "float"], unit = "GeV", doc = "the fit window" }\n', encoding="utf-8")
    paths.reset()
    entry = quantities.vocabulary()["window"]
    assert entry["shape"] == ["float", "float"] and entry["declared"].endswith("tools/fit/quantities.toml")
    shown = "\n".join(house.explain("window"))
    assert "declared by" in shown and "the fit window" in shown and "fit {'key': 'window'" in shown
    assert "window" not in quantities.shipped_vocabulary()                        # Heimdall's stays Heimdall's


def test_a_declaration_may_not_redefine_heimdalls_words(roots):
    work, _ = roots
    folder = work / "tools" / "fit"
    shutil.copytree(REPO / "framework" / "tools" / "exec", folder, ignore=shutil.ignore_patterns("__pycache__"))
    (folder / "quantities.toml").write_text('sqrts = { key = "e", shape = "float" }\n', encoding="utf-8")
    paths.reset()
    with pytest.raises(HepError, match="declares 'sqrts', which Heimdall's vocabulary has"):
        quantities.vocabulary()


def test_the_work_dirs_latex_toml_adds_to_heimdalls(roots):
    work, _ = roots
    shipped = labels.latex()
    table = next(name for name, value in shipped.items() if isinstance(value, dict))
    (work / "latex.toml").write_text(f'[{table}]\nmyword = "my"\n', encoding="utf-8")
    mine = labels.latex()
    assert mine[table]["myword"] == "my" and set(shipped[table]) <= set(mine[table])
    (work / "latex.toml").write_text('[nope]\nx = "y"\n', encoding="utf-8")
    with pytest.raises(HepError, match=r"latex.toml has no table \[nope\]"):
        labels.latex()


def test_the_plot_code_is_in_framework_plot():
    assert (REPO / "framework" / "plot" / "mpl" / "backend.py").is_file()
    assert not (REPO / "framework" / "tools" / "mpl").exists() and not (REPO / "framework" / "tools" / "figures").exists()
    assert plot.backend("mpl") is not None


def test_a_declared_quantity_reaches_its_tool_in_a_run(roots):
    """04 §6's row: [quantities.window] binds to the folder that declared it, with no key or target."""
    import os
    import subprocess
    from support import HEP
    work, _ = roots
    shutil.copytree(REPO / "framework" / "tools" / "exec", work / "tools" / "fit", ignore=shutil.ignore_patterns("__pycache__"))
    (work / "tools" / "fit" / "quantities.toml").write_text(
        'window = { config = "cuts.window", shape = ["float", "float"], doc = "the fit window" }\n', encoding="utf-8")
    script = work / "copy.py"
    script.write_text('#!/usr/bin/env python3\nimport sys\nopen(sys.argv[2], "w").write(open(sys.argv[1]).read())\n',
                      encoding="utf-8")
    script.chmod(0o755)
    (work / "configs" / "P" / "c.toml").write_text(f"""[run]
name = "c"
project = "P"
configuration = "one"
event_count = 1
threads = 1

[run.cfgs.one]
tools  = ["fit"]
sweeps = ["window"]

[tools.fit]
tool        = "fit"
executable  = "{script}"
arguments   = ["{{partial:output}}"]
output_file = "config.txt"

[quantities.window]
values = [[1.0, 2.0], [3.0, 4.0]]
tags   = ["low", "high"]
""", encoding="utf-8")
    done = subprocess.run([str(HEP), "run", "P/c", "--plain"], cwd=work, capture_output=True, text=True, timeout=300,
                          env={k: v for k, v in os.environ.items() if k != "HEP_CONFIGS"})
    assert done.returncode == 0, done.stdout + done.stderr
    written = sorted(tomllib.loads(p.read_text())["cuts"]["window"] for p in (work / "results").rglob("config.txt"))
    assert written == [[1.0, 2.0], [3.0, 4.0]]
