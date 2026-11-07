"""The points library's layout, index, links and lock (points-library P3): a Run's points/<name> links into
records/<A>/library/<key16>, so every reader keeps its paths, and one entry serves the Runs that link it."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os

import pytest

from runner import cli, house, record, results
from runner.errors import HeimdallError
from runner.paths import records_root, results_root

from test_lifecycle import finished, planned, trees  # noqa: F401  (the fixture)


def pooled(name="Demo/jets", key="pdf"):
    """A configuration's plans with each generation point given its library key, as phase 4's planning does."""
    p = planned(name, key)
    for plan in p.every:
        plan.library = record.library_key(plan)
    return p


def test_a_library_point_links_relatively_into_the_assignments_library(trees):
    p = pooled()
    plan = p.every[0]
    assert record.link_library(plan) is True and record.link_library(plan) is False       # again: nothing to do
    link = plan.folders.points / plan.point.name
    assert link.is_symlink() and os.readlink(link) == f"../../../library/{plan.library[:16]}"
    assert link.resolve() == (records_root() / "Demo" / "library" / plan.library[:16]).resolve()
    assert os.readlink(plan.res) == f"../../../library/{plan.library[:16]}"
    assert plan.res.resolve() == (results_root() / "Demo" / "library" / plan.library[:16]).resolve()
    assert plan.folders.library_records == records_root() / "Demo" / "library"


def test_a_point_complete_through_its_link_is_complete_for_every_run_with_its_key(trees):
    first = pooled().every[0]
    record.link_library(first)
    assert not record.is_complete(first)
    finished(first)                                                   # writes through the links
    record.write_atomic(record.complete_marker(first), record.marker_text(first) + "\n")
    assert (record.library_entry(first) / ".complete").read_text(encoding="utf-8").strip() == first.library
    assert record.is_complete(first) and record.recorded_identity(first) == first.identity
    other = pooled("Demo/jets", "pdf").every[0]                      # another Run's plan of the same point
    other.identity = "0" * 64                                         # … with another name's identity
    assert record.is_complete(other)                                  # the key is what the entry is complete for
    other.library = "f" * 64
    assert not record.is_complete(other)                              # another key: not


def test_a_name_that_changed_physics_is_relinked_and_a_folder_of_the_runs_own_is_refused(trees):
    p = pooled()
    plan = p.every[0]
    record.link_library(plan)
    old = plan.library
    plan.library = "a" * 64
    assert record.link_library(plan) is True and os.readlink(plan.folders.points / plan.point.name).endswith("a" * 16)
    assert (records_root() / "Demo" / "library" / old[:16]).is_dir()      # the old entry stays
    mine = p.every[1]
    (mine.folders.points / mine.point.name).mkdir(parents=True)
    (mine.folders.points / mine.point.name / "provenance.json").write_text("{}", encoding="utf-8")
    with pytest.raises(HeimdallError, match="folder of this Run's own"):
        record.link_library(mine)
    empty = p.every[2]
    (empty.folders.points / empty.point.name).mkdir(parents=True)
    assert record.link_library(empty) is True                          # an empty one is replaced


def test_one_lock_serves_every_run_of_an_entry(trees):
    plan = pooled().every[0]
    other = pooled().every[0]
    assert record.lock_file(plan) == record.library_entry(plan) / ".lock" != plan.out / ".lock"
    lock, second = record.PointLock(plan), record.PointLock(other)
    assert lock.acquire() and not second.acquire()
    assert record.holder(other) is not None
    lock.release()
    assert second.acquire()
    second.release()


def test_the_index_folds_its_lines_and_passes_over_a_cut_one(trees):
    p = pooled()
    plan, errand = p.every[0], p.errand
    record.index_note(plan, errand, "created")
    record.index_note(plan, errand, "used")
    path = record.library_index_file("Demo")
    path.write_text(path.read_text(encoding="utf-8") + '{"kind": "used", "key"\n', encoding="utf-8")      # a write cut short
    record.index_note(plan, errand, "rerun")
    entry = record.library_entries("Demo")[plan.library]
    assert entry["first_run"] == entry["runs"][0] == str(plan.folders.record.relative_to(records_root()))
    assert entry["events"] == plan.events and entry["seed"] == plan.seed and entry["reruns"] == 1
    assert entry["coordinates"]["pdf"] == plan.point.name and set(entry["coordinates"]) >= {"pdf"}
    assert len(record.library_entries("Demo")) == 1 and record.library_entries("Nowhere") == {}


def test_the_manifest_names_the_library_and_its_key_is_the_identity_it_holds(trees):
    p = pooled()
    plan = p.every[0]
    record.link_library(plan)
    finished(plan)
    record.write_atomic(record.complete_marker(plan), record.marker_text(plan) + "\n")
    made = record.points_manifest([plan], p.errand, p.configuration)
    entry = made["points"][0]
    assert entry["library"] == plan.library[:16] and entry["identity"] == plan.library and entry["complete"] is True
    assert "library" not in record.points_manifest([planned("Demo/jets", "pdf").every[0]], p.errand, p.configuration)["points"][0]


def test_every_reader_passes_through_a_linked_point(trees):
    p = pooled()
    plan = p.every[0]
    record.link_library(plan)
    finished(plan)
    record.write_atomic(record.complete_marker(plan), record.marker_text(plan) + "\n")
    (plan.res / "x.yoda").write_text("BEGIN YODA_HISTO1D_V2 /A\nEND YODA_HISTO1D_V2\n", encoding="utf-8")
    manifest = record.points_manifest(p.every, p.errand, p.configuration)
    record.write_atomic(p.every[0].folders.manifest, json.dumps(manifest))
    assert house.status([p], {})[0].endswith(f"1 complete, {len(p.every) - 1} to run")         # status
    shown = house.show_data(plan.folders.record, plan.point.name)                              # show
    assert shown["state"] == "complete" and shown["products"] == ["jets.root", "jets.yoda"]
    assert house.point_log(plan.folders.record, plan.point.name)[0].startswith(f"{plan.point.name}:")          # log
    loaded = {pt.name: pt for pt in results.load("Demo/jets", "pdf")}[plan.point.name]         # results.load
    assert loaded.complete and loaded.identity == plan.library
    from runner import plot
    members = {m.point.name: m for m in plot.recorded(p.errand, p.configuration)}               # plot.recorded
    assert members[plan.point.name].recorded == members[plan.point.name].identity == plan.library


def test_a_page_document_of_a_planned_library_point_reads_back_complete(trees):
    from runner import plotdoc
    p = pooled()
    plan = p.every[0]
    record.link_library(plan)
    finished(plan)
    record.write_atomic(record.complete_marker(plan), record.marker_text(plan) + "\n")
    (plan.res / "x.yoda").write_text("BEGIN YODA_HISTO1D_V2 /A\nEND YODA_HISTO1D_V2\n", encoding="utf-8")
    plan.interfaces = {}
    entry = plotdoc._member(plan)
    assert entry["identity"] == plan.library


# ── library = true | "only" (P4) ─────────────────────────────────────────────────────────────────────

import re
from pathlib import Path

from runner import paths


class Said:
    def __init__(self):
        self.lines = []

    def say(self, text):
        self.lines.append(text)


@pytest.fixture
def lib_configs(trees):
    """Demo/lib_a and Demo/lib_b: Demo/jets with `library = true`, the second under other names (errand, pdf tags)."""
    configs = Path(paths.configs_root()) / "Demo"
    text = (configs / "jets.toml").read_text(encoding="utf-8")
    first = re.sub(r'^name\s*=\s*"jets"', 'name = "lib_a"\nlibrary = true', text, count=1, flags=re.M)
    second = re.sub(r'^name\s*=\s*"jets"', 'name = "lib_b"\nlibrary = true', text, count=1, flags=re.M)
    for tag in ("MSTW08lo", "NNPDF23lo", "NNPDF23nlo", "PDF4LHC21"):
        second = second.replace(f'tag = "{tag}"', f'tag = "x_{tag}"').replace(f'fixed  = "{tag}"', f'fixed  = "x_{tag}"')
    (configs / "lib_a.toml").write_text(first, encoding="utf-8")
    (configs / "lib_b.toml").write_text(second, encoding="utf-8")
    yield
    for name in ("lib_a", "lib_b"):
        (configs / f"{name}.toml").unlink(missing_ok=True)


def test_the_setting_is_true_false_or_only(lib_configs):
    from runner import config
    assert config.load("Demo/lib_a").configuration("pdf").library is True
    assert config.load("Demo/jets").configuration("pdf").library is False
    bad = Path(paths.configs_root()) / "Demo" / "lib_a.toml"
    bad.write_text(bad.read_text(encoding="utf-8").replace("library = true", 'library = "yes"'), encoding="utf-8")
    with pytest.raises(HeimdallError, match="library must be one of"):
        config.load("Demo/lib_a")


def test_two_errands_plan_one_physics_as_one_library_point(lib_configs):
    a, b = planned("Demo/lib_a", "pdf"), planned("Demo/lib_b", "pdf")
    assert [p.library for p in a.every] == [p.library for p in b.every] and all(p.library for p in a.every)
    assert [p.point.name for p in b.every] == [f"x_{p.point.name}" for p in a.every]
    assert planned("Demo/jets", "pdf").every[0].library == ""


def test_a_point_the_first_errand_made_is_complete_for_the_second_with_the_seed_it_had(lib_configs):
    first = planned("Demo/lib_a", "pdf").every[0]
    record.link_library(first)
    finished(first)                                                       # provenance seed 1
    record.write_atomic(record.complete_marker(first), record.marker_text(first) + "\n")
    second = planned("Demo/lib_b", "pdf")
    hit = second.every[0]
    assert record.is_complete(hit) and hit.seed == 1 and hit.seed_kept
    assert not any(record.is_complete(p) for p in second.every[1:])
    assert not (hit.folders.points / hit.point.name).exists()             # planning wrote nothing
    assert "from the library" not in "".join(record.why(hit))


def test_a_run_links_its_pooled_points_notes_the_library_and_names_who_a_rerun_replaces(lib_configs):
    first = planned("Demo/lib_a", "pdf")
    a = first.every[0]
    record.link_library(a)
    finished(a)
    record.write_atomic(record.complete_marker(a), record.marker_text(a) + "\n")
    record.index_note(a, first.errand, "created")
    second = planned("Demo/lib_b", "pdf")
    said = Said()
    cli.pool_points(second.every, second.errand, False, said)
    hit = second.every[0]
    assert (hit.folders.points / hit.point.name).is_symlink() and hit.res.is_symlink()
    assert said.lines == [f"   note: 1 point(s) come from the library, not run again (first made by "
                           f"{a.folders.record.relative_to(records_root())})"]
    assert second.every[1].folders.points.joinpath(second.every[1].point.name).is_symlink()            # a miss is linked too
    entry = record.library_entries("Demo")[hit.library]
    assert entry["runs"] == [str(a.folders.record.relative_to(records_root())), str(hit.folders.record.relative_to(records_root()))]
    said = Said()
    cli.pool_points(second.every, second.errand, True, said)
    assert said.lines == [f"   note: --rerun replaces the library point {hit.point.name} for every Run that links it: "
                          f"{a.folders.record.relative_to(records_root())}"]


def test_plan_and_why_say_what_the_library_gives(lib_configs, capsys):
    a = planned("Demo/lib_a", "pdf").every[0]
    record.link_library(a)
    finished(a)
    record.write_atomic(record.complete_marker(a), record.marker_text(a) + "\n")
    record.index_note(a, planned("Demo/lib_a", "pdf").errand, "created")
    assert cli.main(["run", "Demo/lib_b", "pdf", "--why"]) == 0
    assert f"x_{a.point.name}   from the library (first by {a.folders.record.relative_to(records_root())})" in capsys.readouterr().out
    assert cli.main(["run", "Demo/lib_b", "pdf", "--plan"]) == 0
    assert f"complete; library {a.library[:16]}, first by" in capsys.readouterr().out


def test_an_only_run_removes_its_links_and_never_an_entry(lib_configs):
    p = planned("Demo/lib_a", "pdf")
    for plan in p.every:
        record.link_library(plan)
    finished(p.every[0])
    record.unlink_run(p.every)
    for plan in p.every:
        assert not (plan.folders.points / plan.point.name).exists() and not plan.res.exists()
    assert not p.every[0].folders.points.exists()
    assert (record.library_entry(p.every[0]) / "provenance.json").is_file()      # the entry stays


def test_clean_removes_a_runs_link_into_the_library_and_never_the_entry(lib_configs):
    p = planned("Demo/lib_a", "pdf")
    plan = p.every[0]
    record.link_library(plan)
    finished(plan)
    gone = p.every[1]
    record.link_library(gone)
    record.link_library(plan)
    # a Run that no longer plans its second point: its link is a target of `clean --records`, its entry is not
    narrower = dataclasses.replace(p, every=[plan], plans=[plan])
    outs, _ = house.clean_targets([narrower], False, records=True)
    link = gone.folders.points / gone.point.name
    assert link in outs and plan.folders.points / plan.point.name not in outs
    house.remove(outs)
    assert not link.exists() and not link.is_symlink()
    assert record.library_entry(gone).is_dir() and (record.library_entry(plan) / "provenance.json").is_file()
