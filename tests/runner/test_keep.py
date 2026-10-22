"""What a run keeps beyond records/ and results/ (V149): little by default; `keep` words from the command line,
the work dir's hep.toml and the machine's machine.toml say more."""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import plan, raw
from runner import execute, paths, plot
from runner.errors import HepError


def test_the_keep_words_come_from_three_places(scratch, monkeypatch):
    work = scratch / "Study"
    work.mkdir()
    (work / "hep.toml").write_text('[work]\n\n[run]\nkeep = ["work"]\n', encoding="utf-8")
    machine = scratch / "Himinbjorg"
    machine.mkdir()
    (machine / "machine.toml").write_text('[run]\nkeep = ["journal"]\n', encoding="utf-8")
    monkeypatch.setenv("HEP_WORK", str(work))
    monkeypatch.setenv("HEP_MACHINE", str(machine))
    paths.reset()
    assert paths.keep() == {"work", "journal"}
    paths.ask_keep(["logs", "cache"])
    assert paths.keep() == {"work", "journal", "logs", "cache"} and paths.keeping("cache")
    with pytest.raises(HepError, match="nothing called 'caches' to keep") as unknown:
        paths.ask_keep(["caches"])
    assert "'cache'" in unknown.value.hint
    (work / "hep.toml").write_text('[work]\n\n[run]\nkeep = 3\n', encoding="utf-8")
    with pytest.raises(HepError, match=r"\[run\] keep: a list of words"):
        paths.work_meta(work)


def test_a_finished_point_keeps_its_cards_and_configs(scratch, monkeypatch):
    monkeypatch.setenv("HEP_RECORDS", str(scratch / "records"))              # this test's own
    _, _, point = plan(raw(), scratch)
    out = point.out
    assert out.parent == point.folders.logs                                  # records/<run>/logs/<point> (V157)
    for name in ("cards/pythia.cmnd", "config/rivet.toml", "events.hepmc", "shards/1/x.yoda", ".lock", "empty/"):
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        if not name.endswith("/"):
            (out / name).write_text("x", encoding="utf-8")
    execute._tidy(point)
    assert sorted(p.name for p in out.iterdir()) == [".lock", "cards", "config"]
    (out / "rivet.log").write_text("the last lines\n", encoding="utf-8")
    (out / "events.hepmc").write_text("x", encoding="utf-8")
    paths.ask_keep(["work"])
    execute._tidy(point)
    assert (out / "events.hepmc").exists()                                  # kept: the whole folder
    paths.ask_keep([])
    execute._tidy(point)
    assert sorted(p.name for p in out.iterdir()) == [".lock", "cards", "config", "rivet.log"]   # a log written stays


def test_the_plot_stage_keeps_its_page_configs(scratch, monkeypatch):
    monkeypatch.setenv("HEP_RECORDS", str(scratch / "records"))
    folder = paths.records_root() / "P" / "run" / "cfg" / "plots"
    for name in ("em/d01.toml", "em/d01.toml.ranges.json", "merged.sha256", "derived/a.yoda", "datasets/d.root",
                 "em/yoda/pages.plot"):
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("x", encoding="utf-8")
    paths.ask_keep(["cache"])
    plot.tidy(folder)
    assert (folder / "merged.sha256").exists()                              # kept: the skip markers too
    paths.ask_keep([])
    plot.tidy(folder)
    assert sorted(str(p.relative_to(folder)) for p in folder.rglob("*")) == ["em", "em/d01.toml"]
    outside = scratch / "elsewhere"
    outside.mkdir()
    (outside / "x.yoda").write_text("x", encoding="utf-8")
    plot.tidy(outside)
    assert (outside / "x.yoda").exists()                                    # never outside records/ and .cache/
