"""A run's snapshot and its record (V158): records/<run>/config/ holds the config a run ran with; a record names
where a config goes (`heimdall run|plot|status <P>/<run>/<NN_cfg>`), plans to the identities its points ran with,
and its pages are drawn as it recorded them, whatever the config says today."""

from __future__ import annotations

import argparse
import json
import os
import tomllib

import pytest

from runner import cli, paths, plot, record
from runner.errors import HeimdallError


@pytest.fixture
def trees(scratch, monkeypatch):
    monkeypatch.setenv("HEIMDALL_RECORDS", str(scratch / "records"))
    monkeypatch.setenv("HEIMDALL_CACHE", str(scratch / "cache"))
    monkeypatch.setenv("HEIMDALL_RESULTS", str(scratch / "results"))
    monkeypatch.delenv("HEIMDALL_CONFIGS", raising=False)
    return scratch


def planned(name: str, key: str, sets=()):
    return cli.build_plans(argparse.Namespace(config=name, set=list(sets), points=None, rerun=False, only=None), key)


def finished(plan) -> None:
    """A point as a completed run leaves it: its YODA and its records."""
    plan.res.mkdir(parents=True, exist_ok=True)
    plot.yoda_of(plan).write_text("# a YODA\n", encoding="utf-8")
    record.write_atomic(record.complete_marker(plan), plan.identity + "\n")


def recorded_run(name: str, key: str, sets=()):
    """A configuration run and recorded: its points.json, its points complete, its snapshot."""
    p = planned(name, key, sets)
    for plan in p.every:
        finished(plan)
    record.write_atomic(record.manifest_file(p.every), json.dumps(record.points_manifest(p.every, p.errand, p.configuration)))
    record.write_snapshot(p.errand, p.configuration, p.every)
    return p


def test_a_snapshot_holds_what_the_run_read(trees):
    p = recorded_run("Demo/jets", "pdf", ["errand.events=300"])
    folder = p.every[0].folders.config
    assert sorted(str(f.relative_to(folder)) for f in folder.rglob("*") if f.is_file()) == \
        ["Demo/ep.cmnd", "Demo/jets.toml", "snapshot.toml"]
    meta = tomllib.loads((folder / record.SNAPSHOT).read_text(encoding="utf-8"))
    assert meta["snapshot"]["config"] == "Demo/jets" and meta["snapshot"]["configuration"] == "pdf"
    assert meta["snapshot"]["sets"] == ["errand.events=300"] and set(meta["files"]) == {"Demo/jets.toml", "Demo/ep.cmnd"}
    assert (folder / "Demo" / "jets.toml").read_bytes() == p.errand.path.read_bytes()


def test_a_record_plans_to_the_identities_its_points_ran_with(trees, monkeypatch):
    """The snapshot's cards are where configs/ was: Pythia's argv names them, and the identity reads them as
    {work}/configs/… (identity_texts), so `heimdall run RECORD` finds every point complete."""
    p = recorded_run("Demo/jets", "pdf", ["errand.events=300"])
    rel = str(p.every[0].folders.record.relative_to(paths.records_root()))
    args = argparse.Namespace(command="run", config=rel, configuration=None, set=[])
    monkeypatch.setenv("HEIMDALL_CONFIGS", os.environ.get("HEIMDALL_CONFIGS", ""))      # opened() sets it: undone after
    assert cli.opened(args) == p.every[0].folders.record
    assert (args.config, args.configuration, args.set) == ("Demo/jets", "pdf", ["errand.events=300"])
    assert paths.configs_root() == p.every[0].folders.config
    again = planned(args.config, args.configuration, args.set)
    assert again.errand.path.is_relative_to(p.every[0].folders.config)
    assert [plan.identity for plan in again.every] == [plan.identity for plan in p.every]
    assert all(record.is_complete(plan) for plan in again.every)
    assert record.write_snapshot(again.errand, again.configuration, again.every) is None  # its own: nothing written


def test_a_record_is_named_by_its_folder_or_a_path(trees):
    p = recorded_run("Demo/jets", "pdf")
    folder = p.every[0].folders.record
    rel = str(folder.relative_to(paths.records_root()))
    assert record.record_of(rel) == folder
    assert record.record_of(str(p.every[0].folders.results)) == folder                  # results/'s twin
    assert record.record_of(str(folder / "points")) == folder
    assert record.record_of("Demo/jets") is None and record.record_of("Demo/x/y.toml") is None
    (folder / "config" / record.SNAPSHOT).unlink()
    with pytest.raises(HeimdallError, match="has no snapshot") as refused:
        record.record_of(rel)
    assert "heimdall migrate --snapshot" in refused.value.hint


def test_a_record_is_drawn_as_it_was_recorded(trees):
    """plot.recorded: points.json's points, complete when their .complete holds the identity it names; no
    tool is planned. A point since run with other inputs is not the record's."""
    p = recorded_run("Demo/jets", "pdf")
    members = plot.recorded(p.errand, p.configuration)
    assert [m.point.name for m in members] == [plan.point.name for plan in p.every]
    assert [m.yoda for m in members] == [plot.yoda_of(plan) for plan in p.every]
    assert plot.drawable(members) == (members, [])
    record.write_atomic(record.complete_marker(p.every[1]), "another identity\n")
    assert [m.point.name for m in plot.drawable(plot.recorded(p.errand, p.configuration))[0]] == \
        [plan.point.name for plan in p.every if plan is not p.every[1]]


def test_the_live_config_draws_recorded_points_and_names_those_that_changed(trees):
    """A point complete with another identity than today's plan (a card changed, a stack rebuilt) is drawn
    as recorded, and named; one never complete is not drawn."""
    recorded_run("Demo/jets", "pdf")
    now = planned("Demo/jets", "pdf", ["errand.events=999"])                 # another identity for every point
    record.complete_marker(now.every[0]).unlink()
    drawn, other = plot.drawable(now.every)
    assert [p.point.name for p in drawn] == [p.point.name for p in now.every[1:]] and other == drawn


def test_migrate_gives_an_old_record_a_snapshot(trees, capsys):
    """A record that ran before snapshots: the config its points.json names is copied in, and each recorded
    point said to have the same identity under it."""
    p = recorded_run("Demo/jets", "pdf")
    rel = str(p.every[0].folders.record.relative_to(paths.records_root()))
    import shutil
    shutil.rmtree(p.every[0].folders.config)
    args = argparse.Namespace(snapshot=rel, source=None, set=[], apply=False)
    assert cli.migrate_snapshot(args) == 0
    out = capsys.readouterr().out
    assert f"{len(p.every)} of {len(p.every)} recorded point(s) have the same identity under it" in out
    assert (p.every[0].folders.config / record.SNAPSHOT).is_file()
    with pytest.raises(HeimdallError, match="is there already"):
        cli.migrate_snapshot(args)


def test_a_snapshot_holds_every_file_the_run_imports(scratch, monkeypatch):
    """An import with no [errand] of its own (a project's common.toml) is copied too, with what it imports:
    found on a real study's work dir, whose snapshot missed its common.toml at first."""
    work = scratch / "w"
    (work / "configs" / "P").mkdir(parents=True)
    (work / "heimdall.toml").write_text('[work]\nname = "t"\n', encoding="utf-8")
    for var, value in (("HEIMDALL_WORK", work), ("HEIMDALL_RECORDS", work / "records"), ("HEIMDALL_CACHE", work / "cache"),
                       ("HEIMDALL_RESULTS", work / "results")):
        monkeypatch.setenv(var, str(value))
    monkeypatch.delenv("HEIMDALL_CONFIGS", raising=False)
    paths.reset()
    try:
        configs = work / "configs" / "P"
        (configs / "base.toml").write_text('[file]\nschema = 3\n\n[quantities.q]\npoints = [{ tag = "a", value = 1 }, '
                                           '{ tag = "b", value = 2 }]\n', encoding="utf-8")
        (configs / "common.toml").write_text('[file]\nschema = 3\nimport = ["base"]\n\n[tools.x]\nuses = "exec"\n'
                                             'executable = "path:true"\nconsumes = ["q"]\n', encoding="utf-8")
        (configs / "run.toml").write_text('[file]\nschema = 3\nimport = ["common"]\n\n[errand]\nname = "r"\nassignment = "P"\n'
                                          'run = "c"\nevents = 1\nchain = ["x"]\n\n'
                                          '[cfgs.c]\nvary = ["q"]\n', encoding="utf-8")
        from runner import config
        errand = config.load("P/run")
        assert errand.imported == [(configs / "common.toml").resolve(), (configs / "base.toml").resolve()]
        p = planned("P/run", "c")
        folder = record.write_snapshot(p.errand, p.configuration, p.every)
        assert sorted(str(f.relative_to(folder)) for f in folder.rglob("*.toml")) == \
            ["P/base.toml", "P/common.toml", "P/run.toml", "snapshot.toml"]
    finally:
        paths.reset()



def test_an_errand_file_given_by_path_takes_what_is_beside_it(scratch, monkeypatch):
    """An errand file outside configs/ (./elsewhere/run.toml) goes into its snapshot under its assignment, and the
    files beside it it read (its import) beside it, so a run from the record finds them where it did."""
    work = scratch / "w"
    elsewhere = work / "elsewhere"
    elsewhere.mkdir(parents=True)
    (work / "configs").mkdir()
    (work / "heimdall.toml").write_text('[work]\nname = "t"\n', encoding="utf-8")
    for var, value in (("HEIMDALL_WORK", work), ("HEIMDALL_RECORDS", work / "records"), ("HEIMDALL_CACHE", work / "cache"),
                       ("HEIMDALL_RESULTS", work / "results")):
        monkeypatch.setenv(var, str(value))
    monkeypatch.delenv("HEIMDALL_CONFIGS", raising=False)
    paths.reset()
    try:
        (elsewhere / "common.toml").write_text('[file]\nschema = 3\n\n[quantities.q]\npoints = [{ tag = "a", value = 1 }]\n\n'
                                               '[tools.x]\nuses = "exec"\nexecutable = "path:true"\nconsumes = ["q"]\n',
                                               encoding="utf-8")
        (elsewhere / "run.toml").write_text('[file]\nschema = 3\nimport = ["common"]\n\n[errand]\nname = "r"\nassignment = "P"\n'
                                            'run = "c"\nevents = 1\nchain = ["x"]\n\n[cfgs.c]\nvary = ["q"]\n', encoding="utf-8")
        p = planned(str(elsewhere / "run.toml"), "c")
        folder = record.write_snapshot(p.errand, p.configuration, p.every)
        assert sorted(str(f.relative_to(folder)) for f in folder.rglob("*.toml")) == \
            ["P/common.toml", "P/run.toml", "snapshot.toml"]
    finally:
        paths.reset()

def test_heimdall_plot_takes_a_record_or_a_config_to_its_document(trees, capsys, monkeypatch):
    """V165: a record without a plot document gets one, from its snapshot, the first time it is drawn; then the
    record, and its config, name that document."""
    from runner import plotdoc
    p = recorded_run("Demo/jets", "pdf")
    rel = str(p.every[0].folders.record.relative_to(paths.records_root()))
    monkeypatch.setenv("HEIMDALL_CONFIGS", os.environ.get("HEIMDALL_CONFIGS", ""))
    args = argparse.Namespace(command="plot", config=rel, configuration=None, set=[])
    cli.opened(args)
    (target,) = cli.documents_of(args)
    assert target == p.every[0].folders.results / plotdoc.FILE and "from its snapshot" in capsys.readouterr().out
    assert plotdoc.find(rel) == target and plotdoc.find(str(p.every[0].folders.results)) == target
    monkeypatch.delenv("HEIMDALL_CONFIGS")
    assert cli.documents_of(argparse.Namespace(command="plot", config="Demo/jets", configuration="pdf", set=[])) == [target]
    doc, kept, members = plotdoc.load(target)
    assert kept.key == "pdf" and len(members) == len(p.every) and plot.drawable(members)[0] == members


def test_migrate_writes_the_plot_documents_records_lack(trees, capsys):
    from runner import plotdoc
    p = recorded_run("Demo/jets", "pdf")
    args = argparse.Namespace(plot_docs=[], apply=False)
    assert cli.migrate_plot_docs(args) == 0 and "would  write" in capsys.readouterr().out
    assert not (p.every[0].folders.results / plotdoc.FILE).exists()
    args.apply = True
    assert cli.migrate_plot_docs(args) == 0
    assert f"({len(p.every)} complete member(s))" in capsys.readouterr().out
    assert cli.migrate_plot_docs(args) == 0 and "there" in capsys.readouterr().out


def test_style_sync_takes_the_configs_plot_into_the_documents(trees, capsys):
    """V166: `heimdall plot <P>/<name>/<cfg> --style-sync CONFIG`: the document's [plot] becomes the config's, what
    the run knows untouched; --plan writes nothing; <P>/<name> syncs each of its runs."""
    import tomllib
    from runner import plotdoc
    p = recorded_run("Demo/jets", "pdf")
    rel = str(p.every[0].folders.record.relative_to(paths.records_root()))
    assert cli.migrate_plot_docs(argparse.Namespace(plot_docs=[], apply=True)) == 0
    target = p.every[0].folders.results / plotdoc.FILE
    plotdoc.write_chosen(target, {**plotdoc.load(target)[0].plot, "title": "mine"}, {})
    members = tomllib.loads(target.read_text(encoding="utf-8"))["members"]
    capsys.readouterr()
    args = argparse.Namespace(command="plot", config=rel, configuration=None, set=[], style_sync="Demo/jets", plan=True,
                              replot=False, plot_file=None, page_points=None)
    assert cli.cmd_plot(args) == 0
    assert f"would sync {rel}: [plot].title" in capsys.readouterr().out and plotdoc.load(target)[0].plot["title"] == "mine"
    args.plan = False
    assert cli.cmd_plot(args) == 0 and "title" not in plotdoc.load(target)[0].plot
    assert tomllib.loads(target.read_text(encoding="utf-8"))["members"] == members
    capsys.readouterr()
    assert cli.cmd_plot(argparse.Namespace(**{**vars(args), "config": "Demo/jets"})) == 0
    assert f"same    {rel}" in capsys.readouterr().out


def test_style_sync_takes_the_configs_score(trees, capsys):
    """A document's [score] is the config's after --style-sync, as its [plot] and [stats] are, and --plan names it."""
    from runner import plotdoc
    p = recorded_run("Demo/jets", "pdf")
    rel = str(p.every[0].folders.record.relative_to(paths.records_root()))
    assert cli.migrate_plot_docs(argparse.Namespace(plot_docs=[], apply=True)) == 0
    target = p.every[0].folders.results / plotdoc.FILE
    doc = plotdoc.load(target)[0]
    plotdoc.write_chosen(target, doc.plot, doc.stats, score={"mean": "linear"})
    assert plotdoc.load(target)[0].score == {"mean": "linear"}
    capsys.readouterr()
    args = argparse.Namespace(command="plot", config=rel, configuration=None, set=[], style_sync="Demo/jets", plan=True,
                              replot=False, plot_file=None, page_points=None)
    assert cli.cmd_plot(args) == 0
    assert f"would sync {rel}: [score]" in capsys.readouterr().out and plotdoc.load(target)[0].score == {"mean": "linear"}
    args.plan = False
    assert cli.cmd_plot(args) == 0 and plotdoc.load(target)[0].score == {}


def test_an_event_count_is_a_tag():
    from runner.plotdoc import count_tag
    assert [count_tag(n) for n in (10_000_000, 100_000, 10_000, 1_500_000, 2_000_000_000, 500, 1234)] == \
        ["10M", "100k", "10k", "1.5M", "2G", "500", "1234"]


def test_a_sync_keeps_a_runs_own_totality(trees, capsys):
    """V167, V171 (found moving a real study): --style-sync takes the config's [plot] and picks, but the totality
    set is the run's own, from its document's axes (the plot_points it ran with), not today's config's."""
    import tomllib
    import tomli_w
    from runner import plotdoc, sweep
    p = recorded_run("Demo/jets", "pdf")
    rel = str(p.every[0].folders.record.relative_to(paths.records_root()))
    assert cli.migrate_plot_docs(argparse.Namespace(plot_docs=[], apply=True)) == 0
    target = p.every[0].folders.results / plotdoc.FILE
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    data["axes"]["plot_points"] = ["pdf"]                       # as if it had run with other plot_points
    data["plot"]["title"] = "mine"
    target.write_text(tomli_w.dumps(data), encoding="utf-8")
    args = argparse.Namespace(command="plot", config=rel, configuration=None, set=[], style_sync="Demo/jets", plan=False,
                              replot=False, plot_file=None, page_points=None)
    assert cli.cmd_plot(args) == 0
    doc, kept, members = plotdoc.load(target)
    assert "title" not in doc.plot and doc.plot["sets"]["totality"] == sweep.totality(kept, members) == {"pages": {"pdf": "all"}}


def test_a_documents_quantities_are_points_and_an_older_one_is_upgraded(trees, capsys):
    """V172: [quantities.<q>] points = [{ tag, value, label }], as a run TOML's; a document with the parallel lists
    reads the same, and migrate --plot-docs --apply rewrites it as points, nothing else changed."""
    import tomllib
    import tomli_w
    from runner import plotdoc
    p = recorded_run("Demo/jets", "pdf")
    assert cli.migrate_plot_docs(argparse.Namespace(plot_docs=[], apply=True)) == 0
    target = p.every[0].folders.results / plotdoc.FILE
    text = target.read_text(encoding="utf-8")
    assert "[[quantities." not in text and '\npoints = [\n  { tag = "MSTW08lo", value = ' in text      # inline, a point a line
    headers = [line for line in text.splitlines() if line.startswith("[")]
    assert not any(h.endswith((".choice]", ".values]", ".texts]")) or h.startswith("[plot.sets.totality.") for h in headers)
    assert "[plot.sets.totality]" in headers and headers[-1].startswith("[members.")                   # V173: members last
    assert "\nchoice = { pdf = " in text and "\nvalues = { " in text
    member = text[text.index("[members."):].split("\n\n")[0].splitlines()
    keys = [line.split(" = ")[0] for line in member[1:]]
    assert keys[:3] == ["index", "identity", "complete"] and keys.index("yoda") < keys.index("choice") < keys.index("values")
    data = tomllib.loads(text)
    rows = data["quantities"]["pdf"]["points"]
    assert all(set(r) <= {"tag", "value", "label", "style"} for r in rows) and [r["tag"] for r in rows][:1] == ["MSTW08lo"]
    before = plotdoc.load(target)[0].quantities["pdf"]
    data["quantities"]["pdf"] = {"values": [r["value"] for r in rows], "tags": [r["tag"] for r in rows],
                                 "labels": [r["label"] for r in rows]}
    target.write_text(tomli_w.dumps(data), encoding="utf-8")                # the lists, and every table a header
    assert plotdoc.needs_upgrade(target)
    old = plotdoc.load(target)[0].quantities["pdf"]
    assert (old.values, old.tags, old.labels) == (before.values, before.tags, before.labels)
    capsys.readouterr()
    assert cli.migrate_plot_docs(argparse.Namespace(plot_docs=[], apply=True)) == 0
    assert "upgraded 1" in capsys.readouterr().out
    again = tomllib.loads(target.read_text(encoding="utf-8"))
    assert again["quantities"]["pdf"]["points"] == rows and again["members"] == data["members"]
    assert not plotdoc.needs_upgrade(target) and target.read_text(encoding="utf-8") == text


def test_a_document_loaded_into_other_folders_reads_its_own_and_draws_there(trees, capsys, monkeypatch):
    """plotdoc.load(path, folders) gives members that draw into those folders, each still with its YODA
    and its completeness from the document's own (the report draws a source's pages without writing to it)."""
    from runner import plotdoc
    from runner.tools import RunFolders
    p = recorded_run("Demo/jets", "pdf")
    rel = str(p.every[0].folders.record.relative_to(paths.records_root()))
    monkeypatch.setenv("HEIMDALL_CONFIGS", os.environ.get("HEIMDALL_CONFIGS", ""))       # cli.opened points it at the snapshot
    args = argparse.Namespace(command="plot", config=rel, configuration=None, set=[])
    cli.opened(args)
    (target,) = cli.documents_of(args)
    elsewhere = RunFolders("Demo", trees / "away" / "records", trees / "away" / "results", trees / "away" / "cache")
    _, _, own = plotdoc.load(target)
    _, _, moved = plotdoc.load(target, folders=elsewhere)
    assert [m.yoda for m in moved] == [m.yoda for m in own] and all(m.yoda.is_file() for m in moved)
    assert [m.recorded for m in moved] == [m.recorded for m in own] == [m.identity for m in own]
    assert {m.folders for m in moved} == {elsewhere} and {m.folders for m in own} == {p.every[0].folders}
