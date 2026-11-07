"""The points library's layout, index, links and lock (points-library P3): a Run's points/<name> links into
records/<A>/library/<key16>, so every reader keeps its paths, and one entry serves the Runs that link it."""

from __future__ import annotations

import argparse
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
    link = record.record_dir(plan)
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
    assert record.link_library(plan) is True and os.readlink(record.record_dir(plan)).endswith("a" * 16)
    assert (records_root() / "Demo" / "library" / old[:16]).is_dir()      # the old entry stays
    mine = p.every[1]
    record.record_dir(mine).mkdir(parents=True)
    (record.record_dir(mine) / "provenance.json").write_text("{}", encoding="utf-8")
    with pytest.raises(HeimdallError, match="folder of this Run's own"):
        record.link_library(mine)
    empty = p.every[2]
    record.record_dir(empty).mkdir(parents=True)
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
