"""`heimdall migrate` (V79): run TOMLs and cards rewritten in today's forms, by line, comments kept."""

from __future__ import annotations

import argparse
import tomllib

import pytest

from runner import cli, config, migrate, tools
from runner.errors import HeimdallError

OLD = """\
[errand]
name        = "sw"
assignment  = "Demo"
event_count = 1
sweep_runs  = true                 # every configuration but c

[errand.a]
tools  = ["jets"]
sweeps = ["cut"]

[errand.c]
swept  = false
tools  = ["jets"]
sweeps = ["cut"]

[tools.jets]
tool       = "custom"
consumes   = ["cut"]
executable = "python3"             # the interpreter

[quantities.cut]
values = [4.0, 5.0]
labels = ["E_{T} > 4 GeV",
          "E_{T} > 5 GeV"]         # thresholds

[plot]
title = "#sqrt{s} = 318 GeV"
"""


def test_a_toml_is_rewritten_line_by_line(scratch):
    path = scratch / "sw.toml"
    path.write_text(OLD, encoding="utf-8")
    run = config.load(str(path), strict=False)
    new = migrate.toml_text(OLD, run, run.project)
    assert 'sweep_runs  = ["a"] # every configuration but c' in new
    assert "swept" not in new
    assert 'executable = "path:python3" # the interpreter' in new
    assert 'labels = ["$E_{T}$ > 4 GeV", "$E_{T}$ > 5 GeV"] # thresholds' in new
    assert "title = '$\\sqrt{s}$ = 318 GeV'" in new
    new = migrate.cfgs_text(new)                                    # V98: [errand.a] → [errand.cfgs.a]
    assert "[errand.cfgs.a]" in new and "[errand.cfgs.c]" in new
    path.write_text(new, encoding="utf-8")
    config.load(str(path))                                          # it reads strictly now


def test_long_arrays_wrap_under_their_bracket():
    text = migrate._wrapped("labels = ", "[" + ", ".join(f'"label number {n}"' for n in range(8)) + "]", "", width=60)
    lines = text.splitlines()
    assert len(lines) > 1 and all(len(l) <= 60 for l in lines) and lines[1].startswith(" " * len("labels = ["))


def test_a_card_loses_the_lines_the_runner_sets():
    folder = tools.folders()["pythia"]
    card = "! a comment\nMain:numberOfEvents = 100\nPDF:pSet = 13\nRandom:seed = 0   ! time\n"
    assert migrate.card_text(card, folder) == "! a comment\nPDF:pSet = 13\n"


def test_the_command_diffs_then_applies(scratch, capsys):
    path = scratch / "sw.toml"
    path.write_text(OLD, encoding="utf-8")
    with pytest.raises(HeimdallError, match=r"configurations are \[errand.cfgs.<cfg>\] now"):
        config.load(str(path))
    assert cli.cmd_migrate(argparse.Namespace(configs=[str(path)], apply=False)) == 0
    shown = capsys.readouterr().out
    assert "-swept  = false" in shown and "+[errand.cfgs.a]" in shown and "(a dry run" in shown
    assert path.read_text(encoding="utf-8") == OLD
    assert cli.cmd_migrate(argparse.Namespace(configs=[str(path)], apply=True)) == 0
    assert "migrated 1 file(s)" in capsys.readouterr().out
    config.load(str(path))
    assert cli.cmd_migrate(argparse.Namespace(configs=[str(path)], apply=False)) == 0
    assert "nothing to migrate" in capsys.readouterr().out


FIGURES = """\
[errand]
name    = "fig"
configuration = "a"
event_count = 1
assignment = "Demo"

[errand.a]
tools  = ["jets"]
sweeps = []

[tools.jets]
tool       = "custom"
executable = "path:python3"

[plot]
ratio = true

[plot.object."d04-*"]              # the tails
logy = true

[plot.object."/photo_eic/d0[5-6]*".style]
legend.position = "top-left"

[plot.overlay.eta]
objects = ["d02-x01-y01", "d11-x01-y01"]
ratio   = true
ratio.range  = [0.8, 1.1]
ratio.limits = [0.8, 1.1]
"""


def test_the_old_figure_tables_become_figures(scratch, capsys):
    """V81: overlays and object tables as [plot.figures]; a bare style key (not TOML beside ratio = true)
    under style. The text is migrated first, so the file reads once migrated."""
    new = migrate.figure_text(FIGURES)
    assert '[plot.figures.d04]              # the tails\nobjects = ["d04-*"]\nlogy = true\n' in new
    assert '[plot.figures.d0_5_6]\nobjects = ["/photo_eic/d0[5-6]*"]\n[plot.figures.d0_5_6.style]\nlegend.position' in new
    assert '[plot.figures.eta]\nclass = "overlay"\nobjects' in new
    assert "ratio   = true\nstyle.ratio.range  = [0.8, 1.1]\nstyle.ratio.limits = [0.8, 1.1]\n" in new
    assert "legend.position" in new and "style.legend.position" not in new           # a style table already
    path = scratch / "fig.toml"
    path.write_text(FIGURES, encoding="utf-8")
    assert cli.cmd_migrate(argparse.Namespace(configs=[str(path)], apply=True)) == 0
    run = config.load(str(path))
    assert run.plot["figures"]["eta"]["style"] == {"ratio": {"range": [0.8, 1.1], "limits": [0.8, 1.1]}}
    assert run.plot["figures"]["d04"] == {"objects": ["d04-*"], "logy": True}


def test_run_defaults_move_into_run():
    """V99: its keys after [errand]'s own, its value where both set one (it was the nearer layer)."""
    text = '[errand]\nname = "x"\nthreads = 4      # all\n\n[errand.defaults]\nthreads = 8\ntools = ["a"]   # every one\n\n[errand.cfgs.a]\nsweeps = []\n'
    new = migrate.defaults_text(text)
    assert new == '[errand]\nname = "x"\nthreads = 8\ntools = ["a"]   # every one\n\n[errand.cfgs.a]\nsweeps = []\n'
    assert migrate.defaults_text(new) == new


def test_master_becomes_config(scratch):
    """V93: the table and its two keys renamed, by line; the file then reads."""
    common = scratch / "common.toml"
    common.write_text('[static]\nenergies = "27x920"\n', encoding="utf-8")
    text = OLD.replace("[errand]\n", f'[master]                           # how the file is read\ninclude     = ["{common}"]\n\n[errand]\n', 1)
    new = migrate.config_text(text)
    assert new.startswith(f'[config]                           # how the file is read\nimport     = ["{common}"]\n')
    assert migrate.config_text(new) == new


def test_the_apps_become_the_machine_roots():
    """Audit 3, phase 3.1: the compiled apps left the checkout; High-Energy's {repo} paths go straight there."""
    text = ('exe = "{heimdall}/framework/Apps/App_Pythia.exe"\nrpo = "{repo}/build/Herwig/HerwigDefaults.rpo"\n'
            'kit = "{repo}/utils/Kit.hh"\ncard = "{repo}/configs/a.cmnd"\n')
    new = migrate.placeholder_text(text)
    assert new == ('exe = "{apps}/App_Pythia.exe"\nrpo = "{apps}/Herwig/HerwigDefaults.rpo"\n'
                   'kit = "{heimdall}/src/Kit.hh"\ncard = "{work}/configs/a.cmnd"\n')
    assert migrate.placeholder_text(new) == new


def test_exports_become_generate_cards_and_custom_becomes_exec():
    """Audit 3, phase 4.2: the keys move to the configurations whose chain runs the asking table (all of
    them: [errand]); {std:<key>} names the context file's value; tool = "custom" is "exec"."""
    text = ('[errand]\nname = "x"\n\n[errand.cfgs.a]\ntools = ["probe"]\n\n[errand.cfgs.b]\ntools = [["pythia", "rivet"]]\n\n'
            '[tools.probe]\ntool = "custom"\nexecutable = "x"\narguments = ["{std:herwig_run}"]\npythia_cmnd = true\n'
            'herwig_run = true\n\n[tools.pythia]\ntool = "pythia"\n\n[tools.rivet]\ntool = "rivet"\n\n'
            '[tools.herwig]\ntool = "herwig"\n')
    new = migrate.exports_text(migrate.formerly_text(text))
    data = tomllib.loads(new)
    assert data["tools"]["probe"]["tool"] == "exec" and "pythia_cmnd" not in data["tools"]["probe"]
    assert data["tools"]["probe"]["arguments"] == ["{context:herwig.run}"]
    assert data["errand"]["cfgs"]["a"]["generate_cards"] == ["pythia", "herwig:run"]
    assert "generate_cards" not in data["errand"]["cfgs"]["b"] and "generate_cards" not in data["errand"]
    assert migrate.exports_text(new) == new
    every = text.replace('tools = [["pythia", "rivet"]]', 'tools = ["probe"]')
    assert tomllib.loads(migrate.exports_text(every))["errand"]["generate_cards"] == ["pythia", "herwig:run"]


def test_a_work_dir_from_before_the_rename_takes_heimdalls_names(scratch, monkeypatch, capsys):
    """I-109, V213: `heimdall migrate --names`: hep.toml → heimdall.toml, and the old names in the work dir's own
    files (configs, cards, modules, Makefile, editor settings); what runs made is left alone; a dry run writes
    nothing."""
    work = scratch / "old"
    files = {
        "hep.toml": '# hep.toml — the marker\n[work]\nname = "old"\n',
        "Makefile": "ifndef HEP\n$(error HEP is not set)\nendif\ninclude $(HEP)/framework/work.mk\n",
        "configs/P/a.toml": '# $HEP/docs/04\n[tools.x]\nprogram = ["{hep}/framework/x.py"]\n',
        "configs/P/a.sin": "# hep: beam_structure = pdf_builtin, epa\nmodel = SM\n",
        "modules/P/m.py": 'import os\nimport hepkit\npath = os.environ["HEP_CONTEXT"]\nrun = hepkit.Status()\n',
        ".vscode/settings.json": '{"workbench.colorTheme": "HEP Contrast Light", "workbench.iconTheme": "hep-icons"}\n',
        "results/P/r/c/plot.toml": "# {hep} as a run wrote it\n",
    }
    for name, text in files.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text, encoding="utf-8")
    monkeypatch.delenv("HEIMDALL_WORK", raising=False)
    monkeypatch.chdir(work / "configs")
    assert migrate.old_marker() == work.resolve()
    args = argparse.Namespace(names=True, apply=False)
    assert cli.cmd_migrate(args) == 0
    said = capsys.readouterr().out
    assert "6 file(s) to rewrite, the marker to rename (a dry run" in said and "+program = [\"{heimdall}/framework/x.py\"]" in said
    assert (work / "hep.toml").is_file() and not (work / "heimdall.toml").exists()
    args.apply = True
    assert cli.cmd_migrate(args) == 0
    assert not (work / "hep.toml").exists()
    assert (work / "heimdall.toml").read_text(encoding="utf-8").startswith("# heimdall.toml — the marker")
    assert (work / "Makefile").read_text(encoding="utf-8") == \
        "ifndef HEIMDALL\n$(error HEIMDALL is not set)\nendif\ninclude $(HEIMDALL)/framework/work.mk\n"
    assert (work / "configs/P/a.sin").read_text(encoding="utf-8").startswith("# heimdall: beam_structure")
    assert (work / "modules/P/m.py").read_text(encoding="utf-8") == \
        'import os\nimport heimdallkit\npath = os.environ["HEIMDALL_CONTEXT"]\nrun = heimdallkit.Status()\n'
    assert "Heimdall Contrast Light" in (work / ".vscode/settings.json").read_text(encoding="utf-8")
    assert (work / "results/P/r/c/plot.toml").read_text(encoding="utf-8") == files["results/P/r/c/plot.toml"]
    assert cli.cmd_migrate(args) == 0 and "nothing to migrate" in capsys.readouterr().out


ERRAND_OLD = """\
# study.toml — the configuration named in [run] (a), a [run.cfgs.<cfg>] each; `--set run.threads=2` for less
[config]
import = [{ from = "common", only = ["quantities", "run.cfgs.b", "run.cfgs.c"] }]
drop   = ["run.cfgs.c"]

[run]
name          = "s"
project       = "P"
configuration = "a"
event_count   = 1

[run.cfgs.a]                  # the first
tools = ["x"]

# [run.cfgs.later]
# tools = ["x"]

[tools.x]
tool       = "exec"
executable = "path:true"

[report]
title = "{project} · {run} · {configuration}"
"""
COMMON_OLD = """\
[run]
name    = "common"
project = "P"

[run.cfgs.b]
tools = ["x"]

[run.cfgs.c]
tools = ["x"]

[quantities.q]
values = [1]
"""
DOCUMENT_OLD = """\
# A run's plot document
[source]
config = "P/study"
configuration = "a"
run = "s"
project = "P"
folder = "P/s/01_a"

[axes]
vary = []
"""


def test_a_work_dir_in_the_names_before_i112_takes_errand_and_assignment(scratch, monkeypatch, capsys):
    """I-112: `heimdall migrate --names` rewrites [run] → [errand] and [run].project → [errand].assignment in the
    work dir's configs (headers, commented ones, keys, an import's only and drop, a title's placeholders, --set in
    a comment), in its scripts (--set run.x), in each record's snapshot (its files, their digests, its --set
    overrides) and each point's provenance (its overrides), and [source]'s project and run in its plot documents;
    a module's source is left (its programs' identity). A dry run writes nothing; --apply makes it read; again,
    nothing to migrate."""
    import hashlib
    import json
    work = scratch / "old112"
    snapshot = ('# A run\'s snapshot (V158)\n[snapshot]\nconfig = "P/study"\nconfiguration = "a"\nsets = ["run.threads=2", '
                f'"static.q=1"]\n\n[files]\n"P/study.toml" = "{hashlib.sha256(ERRAND_OLD.encode()).hexdigest()}"\n')
    files = {
        "heimdall.toml": '[work]\nname = "old112"\n',
        "go.sh": "heimdall run P/study --set run.threads=8 --set=run.event_count=5\n",
        "configs/P/study.toml": ERRAND_OLD,
        "configs/P/common.toml": COMMON_OLD,
        "modules/P/m.cc": "// heimdall run P/study --set run.threads=8\n",
        "records/P/s/01_a/config/P/study.toml": ERRAND_OLD,
        "records/P/s/01_a/config/snapshot.toml": snapshot,
        "records/P/s/01_a/points/q-1/provenance.json": json.dumps({"point": "q-1", "run": "s", "project": "P",
                                                                   "sets": ["run.threads=2"]}, indent=1),
        "results/P/s/01_a/plot.toml": DOCUMENT_OLD,
    }
    for name, text in files.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text, encoding="utf-8")
    monkeypatch.delenv("HEIMDALL_WORK", raising=False)
    monkeypatch.chdir(work)
    args = argparse.Namespace(names=True, apply=False)
    assert cli.cmd_migrate(args) == 0
    said = capsys.readouterr().out
    assert "7 file(s) to rewrite (a dry run" in said and "+[errand]\n" in said and "+assignment    = \"P\"\n" in said
    assert (work / "configs/P/study.toml").read_text(encoding="utf-8") == ERRAND_OLD
    args.apply = True
    assert cli.cmd_migrate(args) == 0
    capsys.readouterr()
    new = (work / "configs/P/study.toml").read_text(encoding="utf-8")
    assert new.startswith("# study.toml — the configuration named in [errand] (a), an [errand.cfgs.<cfg>] each; "
                          "`--set errand.threads=2`")
    assert 'import = [{ from = "common", only = ["quantities", "errand.cfgs.b", "errand.cfgs.c"] }]\ndrop   = ["errand.cfgs.c"]\n' in new
    assert '[errand]\nname          = "s"\nassignment    = "P"\n' in new and "[errand.cfgs.a]               # the first" in new
    assert "# [errand.cfgs.later]" in new and 'title = "{assignment} · {errand} · {configuration}"' in new
    assert "[run" not in (work / "configs/P/common.toml").read_text(encoding="utf-8")
    assert (work / "go.sh").read_text(encoding="utf-8") == "heimdall run P/study --set errand.threads=8 --set=errand.event_count=5\n"
    assert (work / "modules/P/m.cc").read_text(encoding="utf-8") == files["modules/P/m.cc"]
    kept = (work / "records/P/s/01_a/config/P/study.toml").read_text(encoding="utf-8")
    assert kept == new
    meta = tomllib.loads((work / "records/P/s/01_a/config/snapshot.toml").read_text(encoding="utf-8"))
    assert meta["snapshot"]["sets"] == ["errand.threads=2", "static.q=1"]
    assert meta["files"]["P/study.toml"] == hashlib.sha256(kept.encode("utf-8")).hexdigest()
    assert (work / "records/P/s/01_a/config/snapshot.toml").read_text(encoding="utf-8").startswith("# A run's snapshot")
    provenance = json.loads((work / "records/P/s/01_a/points/q-1/provenance.json").read_text(encoding="utf-8"))
    assert provenance == {"point": "q-1", "run": "s", "project": "P", "sets": ["errand.threads=2"]}
    source = tomllib.loads((work / "results/P/s/01_a/plot.toml").read_text(encoding="utf-8"))["source"]
    assert source == {"config": "P/study", "configuration": "a", "errand": "s", "assignment": "P", "folder": "P/s/01_a"}
    monkeypatch.setenv("HEIMDALL_CONFIGS", str(work / "configs"))
    run = config.load("P/study")
    assert (run.project, run.name, sorted(run.configurations)) == ("P", "s", ["a", "b"])
    assert cli.cmd_migrate(args) == 0 and "nothing to migrate" in capsys.readouterr().out


def test_the_plain_migration_reads_the_names_before_i112_first():
    """`heimdall migrate` rewrites [run] → [errand] before its older forms (V98's [run.<cfg>], V99's [run.defaults]),
    so a file of any age comes out in today's names."""
    old = '[run]\nname = "x"\nproject = "P"\nthreads = 4\n\n[run.defaults]\nthreads = 8\n\n[run.a]\ntools = ["t"]\n'
    new = migrate.defaults_text(migrate.cfgs_text(migrate.errand_text(old)))
    assert new == '[errand]\nname = "x"\nassignment = "P"\nthreads = 8\n\n[errand.cfgs.a]\ntools = ["t"]\n'
    assert migrate.errand_text(new) == new
