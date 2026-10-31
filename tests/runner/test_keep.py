"""What a run keeps beyond records/ and results/ (V149): little by default; `keep` words from the command line,
the work dir's heimdall.toml and the machine's machine.toml say more."""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import plan, raw
from runner import execute, paths
from runner.errors import HeimdallError


def test_the_keep_words_come_from_three_places(scratch, monkeypatch):
    work = scratch / "Study"
    work.mkdir()
    (work / "heimdall.toml").write_text('[work]\n\n[run]\nkeep = ["work"]\n', encoding="utf-8")
    machine = scratch / "Himinbjorg"
    machine.mkdir()
    (machine / "machine.toml").write_text('[run]\nkeep = ["journal"]\n', encoding="utf-8")
    monkeypatch.setenv("HEIMDALL_WORK", str(work))
    monkeypatch.setenv("HEIMDALL_MACHINE", str(machine))
    paths.reset()
    assert paths.keep() == {"work", "journal"}
    paths.ask_keep(["logs", "cache"])
    assert paths.keep() == {"work", "journal", "logs", "cache"} and paths.keeping("cache")
    with pytest.raises(HeimdallError, match="nothing called 'caches' to keep") as unknown:
        paths.ask_keep(["caches"])
    assert "'cache'" in unknown.value.hint
    (work / "heimdall.toml").write_text('[work]\n\n[run]\nkeep = 3\n', encoding="utf-8")
    with pytest.raises(HeimdallError, match=r"\[run\] keep: a list of words"):
        paths.work_meta(work)


def test_a_finished_point_keeps_its_cards_and_configs(scratch, monkeypatch):
    monkeypatch.setenv("HEIMDALL_RECORDS", str(scratch / "records"))              # this test's own
    _, _, point = plan(raw(), scratch)
    out = point.out
    assert out.parent == point.folders.logs                                  # records/<run>/logs/<point> (V157)
    for name in ("cards/pythia.cmnd", "config/rivet.toml", "commands.sh", "context.toml", "events.hepmc", "shards/1/x.yoda",
                 ".lock", "empty/"):
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        if not name.endswith("/"):
            (out / name).write_text("x", encoding="utf-8")
    execute._tidy(point)
    assert sorted(p.name for p in out.iterdir()) == [".lock", "cards", "commands.sh", "config", "context.toml"]   # V187
    (out / "rivet.log").write_text("the last lines\n", encoding="utf-8")
    (out / "events.hepmc").write_text("x", encoding="utf-8")
    paths.ask_keep(["work"])
    execute._tidy(point)
    assert (out / "events.hepmc").exists()                                  # kept: the whole folder
    paths.ask_keep([])
    execute._tidy(point)
    assert sorted(p.name for p in out.iterdir()) == [".lock", "cards", "commands.sh", "config", "context.toml",
                                                     "rivet.log"]                                 # a log written stays


def test_a_points_commands_are_written_as_its_tools_were_given_them(scratch, monkeypatch):
    """V187: commands.sh, beside the cards: HEIMDALL_CONTEXT, the FIFOs, each group's tools (together, joined by them),
    each command line exactly its argv (shell-quoted), with its own folder and environment."""
    import shlex
    monkeypatch.setenv("HEIMDALL_RECORDS", str(scratch / "records"))
    _, _, point = plan(raw(), scratch)
    execute.prepare(point)
    script = point.out / execute.COMMANDS_FILE
    text = script.read_text(encoding="utf-8")
    assert script.stat().st_mode & 0o111 and text.startswith("#!/bin/bash\n")
    assert f"export HEIMDALL_CONTEXT={shlex.quote(str(point.out / 'context.toml'))}" in text
    fifo = point.interfaces["events.hepmc"].path
    assert f"mkfifo {shlex.quote(str(fifo))}" in text
    lines = text.splitlines()
    group = lines.index("# group 1: pythia, rivet")
    for step, line in zip(point.groups[0], lines[group + 1:group + 3]):
        assert line.endswith(" &") and shlex.split(line[:-2]) == [f"{k}={v}" for k, v in step.env.items()] + step.argv
    assert lines[group + 3] == "wait"


def test_the_drawings_working_files_are_the_caches(scratch, monkeypatch):
    """V164: the page documents and the drawing's working files are .cache/<P>/plots/<name>/<NN_cfg>/, rebuilt on
    demand and kept; records/ holds none of them, and heimdall clean does not take them for a tool's caches."""
    from runner import tools
    errand, configuration, made = plan(raw(), scratch)
    assert made.folders.pages == paths.cache_root() / "Demo" / "plots" / made.folders.record.relative_to(paths.records_root() / "Demo")
    assert not made.folders.pages.is_relative_to(paths.records_root())
    assert made.folders.statistics == made.folders.results / "statistics"
    assert tools.run_folders(errand, configuration) == made.folders
