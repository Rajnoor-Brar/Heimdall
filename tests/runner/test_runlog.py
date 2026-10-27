"""A run's own account (V202, I-106 step L4): records/…/run.jsonl, always written and appended (every event but a
tool's latest line, its progress once a minute); `heimdall log` printing a record, a point and a tool; `heimdall
watch --file` from an appended file's last run; the worker's pace; the registry's counts."""

from __future__ import annotations

import json

import pytest

from runner import cli, house, paths, runs
from runner.events import Bus, Journal, RunLog, last_run
from runner.paths import records_root


@pytest.fixture
def trees(scratch, monkeypatch):
    for var, name in (("HEIMDALL_RECORDS", "records"), ("HEIMDALL_CACHE", "cache"), ("HEIMDALL_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    return scratch


def lines_of(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_the_run_log_keeps_every_event_but_lines_and_progress_once_a_minute(scratch):
    path = scratch / "run.jsonl"
    log = RunLog(path)
    for event in ({"k": "line", "point": "p", "tool": "pythia", "msg": "x", "t": 0.0},
                  {"k": "progress", "point": "p", "tool": "pythia", "done": 1, "t": 0.0},
                  {"k": "progress", "point": "p", "tool": "pythia", "done": 2, "t": 30.0},
                  {"k": "progress", "point": "p", "tool": "rivet", "done": 2, "t": 30.0},
                  {"k": "progress", "point": "p", "tool": "pythia", "done": 3, "t": 61.0},
                  {"k": "say", "msg": "hello", "t": 62.0}):
        log.event(event)
    log.close()
    kept = lines_of(path)
    assert [(e["k"], e.get("tool"), e.get("done")) for e in kept] == [
        ("progress", "pythia", 1), ("progress", "rivet", 2), ("progress", "pythia", 3), ("say", None, None)]
    again = RunLog(path, run="b")                                              # appended; a sweep's run: its own
    again.event({"k": "say", "msg": "other run", "run": "a"})
    again.event({"k": "say", "msg": "mine", "run": "b"})
    again.close()
    assert [e.get("msg") for e in lines_of(path)][-2:] == ["hello", "mine"]


def test_the_journal_appends_and_watch_starts_at_the_last_run(scratch):
    path = scratch / "status.jsonl"
    for title in ("first", "second"):
        journal = Journal(path)
        journal.event({"k": "run", "state": "started", "title": title, "t": 1.0 if title == "first" else 2.0})
        journal.event({"k": "run", "state": "finished", "verdict": "done"})
        journal.close()
    offset, when = last_run(path)
    with open(path, "rb") as handle:
        handle.seek(offset)
        assert json.loads(handle.readline())["title"] == "second" and when == 2.0
    assert last_run(scratch / "status.jsonl") != (0, 0.0)


def test_the_recorder_counts_a_runs_points(scratch):
    recorder, bus = runs.Recorder(), Bus()
    bus.subscribe(recorder)
    bus.emit("a", "rivet", {"k": "log", "level": "warn", "msg": "w"})
    for point, state in (("a", "done"), ("b", "done"), ("c", "failed"), ("d", "stopped")):
        bus.emit(point, "", {"k": "point", "state": state})
    assert recorder.counts() == {"done": 2, "failed": 1, "stopped": 1, "warned": 1}


def test_runs_lists_an_entrys_counts():
    entry = {"id": "20261026-120000-pp-abcd", "kind": "run", "started": 0.0, "finished": 10.0, "code": 1,
             "verdict": "failed", "config": "/w/configs/eic/zeus.toml", "configurations": ["generator_pdf"],
             "counts": {"done": 14, "failed": 2, "stopped": 0, "warned": 5}}
    line = house.runs_listing([entry], [], {}, now=20.0)[1]
    assert line.endswith("14 done (5 with warnings), 2 failed")


def test_a_worker_logs_progress_every_ten_minutes_unless_told_otherwise():
    assert paths.LOG_DEFAULTS["worker_every"] == 600 == paths.log_settings()["worker_every"]


def record_with(scratch) -> str:
    """A record by hand: its run.jsonl, a point's attempts and digests, an earlier attempt's in history/."""
    record = records_root() / "Demo" / "jets" / "01_single"
    events = [{"k": "run", "state": "started", "points": 1, "title": "jets · 01  ·  single"},
              {"k": "point", "point": "p1", "state": "started", "index": 1},
              {"k": "log", "point": "p1", "tool": "pythia", "level": "warn", "msg": "careful"},
              {"k": "point", "point": "p1", "state": "failed", "cause": "pythia", "msg": "pythia exited with exit code 3"},
              {"k": "say", "msg": "0 done, 1 failed, 0 skipped"}, {"k": "run", "state": "finished", "verdict": "x"}]
    (record).mkdir(parents=True)
    (record / "run.jsonl").write_text("".join(json.dumps({"v": 1, "t": 1.0, "point": "", "tool": "", **e}) + "\n"
                                              for e in events), encoding="utf-8")
    logs, points = record / "logs" / "p1", record / "points" / "p1"
    (logs / "history" / "1").mkdir(parents=True)
    points.mkdir(parents=True)
    (logs / "pythia.log").write_text("# tag pythia · attempt 2\nnow\n", encoding="utf-8")
    (logs / "pythia.full.log").write_text("all of it\n", encoding="utf-8")
    (logs / "history" / "1" / "pythia.log").write_text("# tag pythia · attempt 1\nthen\n", encoding="utf-8")
    attempts = [{"v": 1, "n": n, "finished": "2026-10-26T10:00:00+00:00", "verdict": "failed", "cause": "failed",
                 "blamed": "pythia", "tools": {"pythia": {"exit": 3}}} for n in (1, 2)]
    (points / "attempts.jsonl").write_text("".join(json.dumps(a) + "\n" for a in attempts), encoding="utf-8")
    return "Demo/jets/01_single"


def test_heimdall_log_prints_a_record_a_point_and_a_tool(trees, capsys):
    name = record_with(trees)
    assert cli.main(["log", name]) == 0
    out = capsys.readouterr().out
    assert "jets · 01  ·  single" in out and "── point 1/1: p1 ── FAILED [pythia]" in out
    assert "   warnings: 1 (pythia 1): careful" in out and "0 done, 1 failed, 0 skipped" in out
    assert cli.main(["log", f"{name}/p1"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "p1: 2 attempt(s) recorded" and out[1].split()[:2] == ["1", "2026-10-26"]
    assert out[1].endswith("pythia failed (exit code 3)") and "── logs/p1/pythia.log" in out and "now" in out
    assert cli.main(["log", f"{name}/p1/pythia", "--attempt", "1"]) == 0
    assert capsys.readouterr().out.splitlines() == ["# tag pythia · attempt 1", "then"]
    assert cli.main(["log", f"{name}/p1/pythia", "--full"]) == 0
    assert capsys.readouterr().out == "all of it\n"
    assert cli.main(["log", str(records_root() / name / "logs" / "p1" / "pythia.log")]) == 0         # by its path
    assert capsys.readouterr().out.startswith("# tag pythia · attempt 2")
    assert cli.main(["log", str(records_root() / name / "logs" / "p1" / "pythia.full.log")]) == 0
    assert capsys.readouterr().out == "all of it\n"
    assert cli.main(["log", f"{name}/p1/pythia", "--attempt", "7"]) == 2
    assert "no logs of attempt 7 kept" in capsys.readouterr().err
