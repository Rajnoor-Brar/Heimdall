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
from runner.errors import HepError


@pytest.fixture
def trees(scratch, monkeypatch):
    monkeypatch.setenv("HEP_RECORDS", str(scratch / "records"))
    monkeypatch.setenv("HEP_CACHE", str(scratch / "cache"))
    monkeypatch.setenv("HEP_RESULTS", str(scratch / "results"))
    monkeypatch.delenv("HEP_CONFIGS", raising=False)
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
    record.write_atomic(record.manifest_file(p.every), json.dumps(record.points_manifest(p.every, p.run, p.configuration)))
    record.write_snapshot(p.run, p.configuration, p.every)
    return p


def test_a_snapshot_holds_what_the_run_read(trees):
    p = recorded_run("Demo/jets", "pdf", ["run.events=300"])
    folder = p.every[0].folders.config
    assert sorted(str(f.relative_to(folder)) for f in folder.rglob("*") if f.is_file()) == \
        ["Demo/ep.cmnd", "Demo/jets.toml", "snapshot.toml"]
    meta = tomllib.loads((folder / record.SNAPSHOT).read_text(encoding="utf-8"))
    assert meta["snapshot"]["config"] == "Demo/jets" and meta["snapshot"]["configuration"] == "pdf"
    assert meta["snapshot"]["sets"] == ["run.events=300"] and set(meta["files"]) == {"Demo/jets.toml", "Demo/ep.cmnd"}
    assert (folder / "Demo" / "jets.toml").read_bytes() == p.run.path.read_bytes()


def test_a_record_plans_to_the_identities_its_points_ran_with(trees, monkeypatch):
    """The snapshot's cards are where configs/ was: Pythia's argv names them, and the identity reads them as
    {work}/configs/… (identity_texts), so `heimdall run RECORD` finds every point complete."""
    p = recorded_run("Demo/jets", "pdf", ["run.events=300"])
    rel = str(p.every[0].folders.record.relative_to(paths.records_root()))
    args = argparse.Namespace(command="run", config=rel, configuration=None, set=[])
    monkeypatch.setenv("HEP_CONFIGS", os.environ.get("HEP_CONFIGS", ""))      # opened() sets it: undone after
    assert cli.opened(args) == p.every[0].folders.record
    assert (args.config, args.configuration, args.set) == ("Demo/jets", "pdf", ["run.events=300"])
    assert paths.configs_root() == p.every[0].folders.config
    again = planned(args.config, args.configuration, args.set)
    assert again.run.path.is_relative_to(p.every[0].folders.config)
    assert [plan.identity for plan in again.every] == [plan.identity for plan in p.every]
    assert all(record.is_complete(plan) for plan in again.every)
    assert record.write_snapshot(again.run, again.configuration, again.every) is None     # its own: nothing written


def test_a_record_is_named_by_its_folder_or_a_path(trees):
    p = recorded_run("Demo/jets", "pdf")
    folder = p.every[0].folders.record
    rel = str(folder.relative_to(paths.records_root()))
    assert record.record_of(rel) == folder
    assert record.record_of(str(p.every[0].folders.results)) == folder                  # results/'s twin
    assert record.record_of(str(folder / "points")) == folder
    assert record.record_of("Demo/jets") is None and record.record_of("Demo/x/y.toml") is None
    (folder / "config" / record.SNAPSHOT).unlink()
    with pytest.raises(HepError, match="has no snapshot") as refused:
        record.record_of(rel)
    assert "heimdall migrate --snapshot" in refused.value.hint


def test_a_record_is_drawn_as_it_was_recorded(trees):
    """plot.recorded: points.json's points, complete when their .complete holds the identity it names; no
    tool is planned. A point since run with other inputs is not the record's."""
    p = recorded_run("Demo/jets", "pdf")
    members = plot.recorded(p.run, p.configuration)
    assert [m.point.name for m in members] == [plan.point.name for plan in p.every]
    assert [m.yoda for m in members] == [plot.yoda_of(plan) for plan in p.every]
    assert plot.drawable(members) == (members, [])
    record.write_atomic(record.complete_marker(p.every[1]), "another identity\n")
    assert [m.point.name for m in plot.drawable(plot.recorded(p.run, p.configuration))[0]] == \
        [plan.point.name for plan in p.every if plan is not p.every[1]]


def test_the_live_config_draws_recorded_points_and_names_those_that_changed(trees):
    """A point complete with another identity than today's plan (a card changed, a stack rebuilt) is drawn
    as recorded, and named; one never complete is not drawn."""
    recorded_run("Demo/jets", "pdf")
    now = planned("Demo/jets", "pdf", ["run.events=999"])                 # another identity for every point
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
    with pytest.raises(HepError, match="is there already"):
        cli.migrate_snapshot(args)


def test_a_snapshot_holds_every_file_the_run_imports(scratch, monkeypatch):
    """An import with no [run] of its own (a project's common.toml) is copied too, with what it imports:
    found on a real study's work dir, whose snapshot missed its common.toml at first."""
    work = scratch / "w"
    (work / "configs" / "P").mkdir(parents=True)
    (work / "hep.toml").write_text('[work]\nname = "t"\n', encoding="utf-8")
    for var, value in (("HEP_WORK", work), ("HEP_RECORDS", work / "records"), ("HEP_CACHE", work / "cache"),
                       ("HEP_RESULTS", work / "results")):
        monkeypatch.setenv(var, str(value))
    monkeypatch.delenv("HEP_CONFIGS", raising=False)
    paths.reset()
    try:
        configs = work / "configs" / "P"
        (configs / "base.toml").write_text('[file]\nschema = 3\n\n[quantities.q]\npoints = [{ tag = "a", value = 1 }, '
                                           '{ tag = "b", value = 2 }]\n', encoding="utf-8")
        (configs / "common.toml").write_text('[file]\nschema = 3\nimport = ["base"]\n\n[tools.x]\nuses = "exec"\n'
                                             'executable = "path:true"\nconsumes = ["q"]\n', encoding="utf-8")
        (configs / "run.toml").write_text('[file]\nschema = 3\nimport = ["common"]\n\n[run]\nname = "r"\nproject = "P"\n'
                                          'run = "c"\nevents = 1\nchain = ["x"]\n\n'
                                          '[cfgs.c]\nvary = ["q"]\n', encoding="utf-8")
        from runner import config
        run = config.load("P/run")
        assert run.imported == [(configs / "common.toml").resolve(), (configs / "base.toml").resolve()]
        p = planned("P/run", "c")
        folder = record.write_snapshot(p.run, p.configuration, p.every)
        assert sorted(str(f.relative_to(folder)) for f in folder.rglob("*.toml")) == \
            ["P/base.toml", "P/common.toml", "P/run.toml", "snapshot.toml"]
    finally:
        paths.reset()
