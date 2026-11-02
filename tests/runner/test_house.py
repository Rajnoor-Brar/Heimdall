"""Housekeeping (V74): `heimdall ls`, `heimdall explain`, `heimdall status`, `heimdall clean`, and `heimdall overlay` split from
`heimdall plot`. Everything under the test's own output/ and results/."""

from __future__ import annotations

import argparse

import pytest

from runner import cli, house, record
from runner.errors import HeimdallError


@pytest.fixture
def trees(scratch, monkeypatch):
    monkeypatch.setenv("HEIMDALL_RECORDS", str(scratch / "records"))
    monkeypatch.setenv("HEIMDALL_CACHE", str(scratch / "cache"))
    monkeypatch.setenv("HEIMDALL_RESULTS", str(scratch / "results"))
    return scratch


def planned(name: str, key: str):
    return cli.build_plans(argparse.Namespace(config=name, set=[], points=None, rerun=False, only=None), key)


def test_ls_lists_every_configuration_and_marks_what_runs():
    lines = house.ls("Demo")
    assert "Demo/jets   run jets" in lines
    assert any(line.startswith("  * pdf ") for line in lines)                 # [errand].configuration
    assert any(line.startswith("    single ") for line in lines)
    with pytest.raises(HeimdallError, match="no errand file"):
        house.ls("NoSuchAssignment")


@pytest.mark.parametrize("key, shown", [
    ("plot.y_gutter", "default  0.5"), ("[plot].normalise", "choices  area, false"),
    ("quantities.pdf.styles", "(a table each)"), ("errand.cfgs.one.event_count", "[configuration].event_count"),
    ("event_count", "[errand].event_count"), ("tools.rivet.shards", "min      1"),
    ("plot.band", "(<q> envelope)"),                                          # V90: a key's notes
    ("errand.events", "events per point"), ("tools.pythia.card", "type "), ("cfgs", "[cfgs.<name>]"),
    ("tools.rivet.analyses", "kind     list, required"), ("style.page.dpi", "default  300"),
    ("machine.toml", "[cluster]"), ("report", "report.section.pages"), ("static", "fixed")])  # every table and name
def test_explain_reads_the_schema(key, shown):
    assert any(shown in line for line in house.explain(key))


def test_explain_takes_errand_and_refuses_run():
    """`heimdall explain errand.events`; `run.events` and `[run]` say what they are now."""
    assert any("events per point" in line for line in house.explain("errand.events"))
    for key, hint in (("run.threads", "heimdall explain errand.threads"), ("[run]", "heimdall explain errand")):
        with pytest.raises(HeimdallError, match=r"\[run\] is now \[errand\]") as caught:
            house.explain(key)
        assert caught.value.hint == hint


def test_explain_suggests_a_near_key():
    with pytest.raises(HeimdallError) as error:
        house.explain("plot.yguter")
    assert "y_gutter" in error.value.hint


def test_status_says_what_each_point_is(trees):
    p = planned("Demo/jets", "pdf")
    first, second, third = p.every[:3]
    second.out.mkdir(parents=True)
    (second.out / "cards").mkdir()                                      # begun, not done
    record.record_dir(third).mkdir(parents=True)
    record.complete_marker(third).write_text("an older identity\n", encoding="utf-8")     # complete once, since changed
    lines = house.status([p], {})
    assert lines[0].startswith("jets · pdf (Demo/jets/01_pdf): 1 stale, 1 incomplete, 2 to run")
    states = {line.split()[0]: line[27:37].strip() for line in lines[1:]}     # "  <name:24> <state:10> …"
    assert states[first.point.name] == "to run" and states[second.point.name] == "incomplete"
    assert states[third.point.name] == "stale"
    assert house.status([p], {str(p.errand.path): ["pdf"]})[0].endswith("[running]")


def test_clean_takes_only_what_no_plan_uses_and_never_results(trees):
    p = planned("Demo/jets", "single")
    point = p.every[0]
    base_out, base_res = point.out.parent, point.res.parent            # records/<run>/logs, results/<run>/points
    (base_out / "oldtag" / "cards").mkdir(parents=True)                 # a point a quantity's tags no longer make
    (base_res / "oldtag").mkdir(parents=True)
    point.res.mkdir(parents=True)
    (point.res / "jets.partial.yoda").write_text("x", encoding="utf-8")                  # an attempt's leftover
    (point.res / "jets.yoda").write_text("kept", encoding="utf-8")
    point.folders.pages.mkdir(parents=True)
    old_run = trees / "records" / "Demo" / "old" / "01_x"
    (old_run / "logs" / "a").mkdir(parents=True)
    (old_run / "points" / "a").mkdir(parents=True)
    orphan_record = point.folders.points / "oldtag"                    # a point's records no plan has
    orphan_record.mkdir(parents=True)
    (point.folders.record / "cluster" / "20261013-1200").mkdir(parents=True)
    targets, kept = house.clean_targets([p], everything=False)
    assert set(targets) == {base_out / "oldtag", point.res / "jets.partial.yoda"}       # records/: never by default
    with_records, _ = house.clean_targets([p], everything=False, records=True)
    assert set(with_records) == set(targets) | {orphan_record}                          # never cluster/
    assert kept == [base_res / "oldtag"]
    everything, _ = house.clean_targets([p], everything=True)
    assert old_run / "logs" in everything and old_run / "points" not in everything     # another run's logs only
    assert (point.res / "jets.yoda") not in everything
    house.remove(targets)
    assert not (base_out / "oldtag").exists() and (point.res / "jets.yoda").read_text(encoding="utf-8") == "kept"
    assert (base_res / "oldtag").exists() and point.folders.pages.exists()


def test_clean_asks_unless_told(trees, monkeypatch, capsys):
    p = planned("Demo/jets", "single")
    (p.every[0].out.parent / "oldtag").mkdir(parents=True)
    args = argparse.Namespace(config="Demo/jets", dry_run=False, yes=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(HeimdallError, match="not deleted"):
        cli.cmd_clean(args)
    assert (p.every[0].out.parent / "oldtag").exists()
    args.dry_run = True
    assert cli.cmd_clean(args) == 0 and "(dry run)" in capsys.readouterr().out
    args.dry_run, args.yes = False, True
    assert cli.cmd_clean(args) == 0 and not (p.every[0].out.parent / "oldtag").exists()


def test_plot_takes_a_config_and_overlay_takes_files():
    with pytest.raises(HeimdallError, match="overlaid by heimdall overlay"):
        cli.cmd_plot(argparse.Namespace(config="a.yoda", configuration=None, set=[]))
    with pytest.raises(HeimdallError, match="is not a YODA or ROOT file"):
        cli.cmd_overlay(argparse.Namespace(files=["a.yoda", "notes.txt"], output=None, labels=None, objects=[],
                                           formats="png", ratio=False, style=None))


def test_results_load_reads_the_manifest(trees):
    """V77: runner.results reads points.json, plans nothing."""
    import json
    from runner import results
    p = planned("Demo/jets", "pdf")
    from runner import record
    path = record.manifest_file(p.every)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record.points_manifest(p.every, p.errand, p.configuration), default=str), encoding="utf-8")
    points = results.load("Demo/jets", "pdf")
    assert [q.name for q in points] == [q.point.name for q in p.every]
    first = points[0]
    assert first.values["pdf"].tag == "MSTW08lo" and first.values["pdf"].swept and not first.complete
    assert first.yoda() == p.every[0].res / "jets.yoda"
    assert set(results.runs("Demo/jets")) == {"pdf"}
    with pytest.raises(HeimdallError, match="no results yet"):
        results.load("Demo/jets", "single")


def test_reproduce_refuses_a_setup_that_changed(trees, capsys):
    """V77: a provenance whose identity is not today's plan's is a different point."""
    import json
    p = planned("Demo/jets", "single")
    point = p.every[0]
    record.record_dir(point).mkdir(parents=True)
    record.provenance_file(point).write_text(json.dumps({
        "config_file": str(p.errand.path), "configuration": "single", "point": point.point.name, "run": "jets",
        "project": "Demo", "identity": "0" * 64, "seed": 1, "sets": []}), encoding="utf-8")
    with pytest.raises(HeimdallError, match="not reproduced"):
        cli.cmd_reproduce(argparse.Namespace(provenance=str(record.record_dir(point)), anyway=False, plain=True))
    assert "changed since it ran" in capsys.readouterr().out
