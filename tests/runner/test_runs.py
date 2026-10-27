"""The run registry (V182): an entry per run in $HEIMDALL_RUNS, its state, pruning, a read-only root, and `heimdall runs`."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from runner import cli, house, runs
from runner.events import Hub


def test_an_entry_says_who_where_and_how_it_ended():
    run_id = runs.new_id()
    assert runs.begin(run_id, {"config": "/w/configs/P/a.toml", "configurations": ["one"], "work": "/w"}) == run_id
    entry = runs.entry(run_id)
    assert (entry["pid"], entry["uid"], entry["host"], entry["kind"]) == (os.getpid(), os.getuid(), runs.host(), "run")
    assert entry["pstart"] == runs.started_at(os.getpid()) and runs.state(entry) == "running"
    assert runs.update(run_id, records=["/r/a"]) and runs.finish(run_id, 6)
    entry = runs.entry(run_id)
    assert (entry["code"], entry["verdict"], entry["records"]) == (6, "stopped", ["/r/a"]) and runs.state(entry) == "stopped"
    assert not list(runs.folder().glob("*.tmp")) and [e["id"] for e in runs.entries()] == [run_id]


def test_ids_are_unique_and_a_log_is_reserved_once():
    ids = {runs.new_id(0) for _ in range(50)}
    assert len(ids) > 40 and all(i.startswith(time.strftime("%Y%m%d-%H%M%S", time.localtime(0))) for i in ids)
    run_id = runs.new_id()
    assert runs.reserve(run_id, ".log") == runs.folder() / f"{run_id}.log" and runs.reserve(run_id, ".log") is None


def test_a_read_only_registry_writes_nothing(tmp_path, monkeypatch):
    """An Apptainer image's machine root: every write a no-op, and a worker's log in <tmp>/heimdall-runs-<uid>/."""
    locked = tmp_path / "runs"
    locked.mkdir()
    locked.chmod(0o555)
    monkeypatch.setenv(runs.DIR_VAR, str(locked))
    try:
        run_id = runs.new_id()
        assert runs.begin(run_id, {}) is None and not runs.finish(run_id, 0) and runs.entries() == []
        log = runs.log_file(run_id)
        assert log.parent.name == f"heimdall-runs-{os.getuid()}" and not log.is_relative_to(locked)
        log.touch()                                    # as spawn opens it: the worker then names this one
        assert runs.log_of(run_id) == log
        log.unlink()
    finally:
        locked.chmod(0o755)
    assert list(locked.iterdir()) == []


def test_old_entries_and_their_logs_leave_after_thirty_days():
    now = time.time()
    old, unfinished, fresh = runs.new_id(), runs.new_id(), runs.new_id()
    for run_id in (old, unfinished, fresh):
        runs.begin(run_id, {})
        (runs.folder() / f"{run_id}.log").write_text("log\n", encoding="utf-8")
    runs.finish(old, 0)
    for run_id, fields in ((old, {"finished": now - 31 * 86400}), (unfinished, {"started": now - 31 * 86400})):
        runs.update(run_id, **fields)
    orphan = runs.folder() / "lonely.log"
    orphan.write_text("x\n", encoding="utf-8")
    os.utime(orphan, (now - 40 * 86400,) * 2)
    assert [e["id"] for e in runs.entries(now)] == [fresh]
    assert sorted(p.name for p in runs.folder().iterdir()) == [f"{fresh}.json", f"{fresh}.log"]


def test_an_entry_never_names_what_is_deleted():
    """V191: an entry whose id names another path (`../x`) is not read, and pruning deletes only `<id>.log`
    beside an entry it read: never a path an entry's content gives."""
    outside = runs.folder().parent / "x.log"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("keep me\n", encoding="utf-8")
    forged = runs.new_id()
    runs.folder().mkdir(parents=True, exist_ok=True)
    (runs.folder() / f"{forged}.json").write_text(json.dumps({"id": "../x", "uid": os.getuid(), "finished": 1.0}),
                                                  encoding="utf-8")
    (runs.folder() / "not-an-id.json").write_text(json.dumps({"id": "not-an-id", "uid": os.getuid()}), encoding="utf-8")
    try:
        assert runs.entries() == []
        assert outside.read_text(encoding="utf-8") == "keep me\n" and (runs.folder() / f"{forged}.json").exists()
    finally:
        outside.unlink()


def test_another_users_entries_are_neither_listed_nor_pruned():
    """V191 (task L: own runs only): an entry of another uid is not listed, not pruned, and not stopped."""
    theirs = runs.new_id()
    runs.folder().mkdir(parents=True, exist_ok=True)
    (runs.folder() / f"{theirs}.json").write_text(json.dumps({"id": theirs, "uid": os.getuid() + 1, "kind": "run",
                                                              "started": 1.0, "finished": 2.0}), encoding="utf-8")
    mine = runs.new_id()
    runs.begin(mine, {})
    assert [e["id"] for e in runs.entries()] == [mine]
    assert {e["id"] for e in runs.entries(mine=False)} == {mine, theirs}
    assert (runs.folder() / f"{theirs}.json").exists()           # 30 days old and more, but not ours to prune


def test_state_tells_lost_from_unknowable():
    """A process gone (or its pid reused, or the machine restarted) is "lost"; another host's or another PID
    namespace's is not guessed at."""
    child = subprocess.Popen(["true"])
    child.wait()
    base = {**runs.here(), "id": "x", "started": time.time()}
    assert runs.state({**base, "pid": child.pid}) == "lost"
    assert runs.state({**base, "pstart": "1"}) == "lost"                          # this pid, another process
    assert runs.state({**base, "boot": "another-boot"}) == "lost"
    assert runs.state({**base, "host": "elsewhere"}) == "on elsewhere"
    assert runs.state({**base, "pidns": "pid:[1]"}) == "in another PID namespace"
    assert runs.state({**base, "netns": "net:[1]"}, live={}) == "running (not reachable from here)"
    assert runs.state({**base, "kind": "cluster"}) == "submitted"


def test_a_cluster_job_records_nothing_its_submission_does(monkeypatch):
    monkeypatch.setenv(runs.CLUSTER_VAR, "20261023-0000")
    assert runs.begin(runs.new_id(), {}) is None
    assert runs.begin(runs.new_id(), {"kind": "cluster"}) is not None


def test_the_recorder_keeps_the_record_folders_and_verdicts():
    recorder = runs.Recorder()
    for event in ({"k": "run", "state": "started", "record": "/r/01_a", "run": "a"},
                  {"k": "point", "state": "done"},
                  {"k": "run", "state": "finished", "verdict": "done", "run": "a"},
                  {"k": "run", "state": "started", "record": "/r/01_a"}):
        recorder.event(event)
    assert recorder.records == ["/r/01_a"] and recorder.verdicts == {"a": "done"}


def test_heimdall_runs_lists_running_then_recent(capsys):
    """Running first (an unrecorded live socket too: a run from inside an image), then the registry's days."""
    done = runs.new_id(time.time() - 3600)
    runs.begin(done, {"config": "/w/configs/P/a.toml", "configurations": ["one"], "work": "/w", "log": "/l/x.log"})
    runs.finish(done, 0)
    hub = Hub({"config": "/w/configs/P/b.toml", "configurations": ["two"], "work": "/w"}, name=f"heimdall-watch-{os.getpid()}-9")
    try:
        assert cli.main(["runs"]) == 0
    finally:
        hub.close()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "running" and "running (unrecorded)" in out[1] and "P/b · two" in out[1]
    assert f"heimdall watch --pid {os.getpid()}" in out[2]
    ended = out.index("the last 30 days")
    assert done in out[ended + 1] and "done" in out[ended + 1] and "P/a · one" in out[ended + 1]
    assert out[ended + 2].strip() == "log /l/x.log"


def test_clean_waits_only_for_a_run_of_its_own_work_dir(monkeypatch):
    """V182: another work dir's run (the user's study, going for hours) does not hold clean or migrate back."""
    from runner.paths import work_root
    monkeypatch.setattr(house, "live_runs", lambda *a, **k: [("x", {"pid": 1, "work": "/elsewhere", "config": "/elsewhere/c.toml"}),
                                                               ("y", {"pid": 2, "config": "/old/run/c.toml"})])
    assert house.runs_here(work_root()) == []
    monkeypatch.setattr(house, "live_runs", lambda *a, **k: [("z", {"pid": 3, "config": str(work_root() / "configs/P/c.toml")})])
    assert [h["pid"] for h in house.runs_here(work_root())] == [3]


def test_a_run_records_itself(scratch):
    """cmd_run writes its entry: begun with its config and command line, finished with its code, verdict and
    record folders."""
    from helpers import raw
    import tomli_w
    config = scratch / "configs" / "Demo"
    config.mkdir(parents=True)
    data = raw(run__cfgs__one__tools=[["true"]], tools={"true": {"tool": "exec", "executable": "/bin/true"}},
               prelim={}, quantities={})
    (config / "rec.toml").write_text(tomli_w.dumps(data), encoding="utf-8")
    os.environ["HEIMDALL_CONFIGS"] = str(scratch / "configs")
    try:
        code = cli.main(["run", str(config / "rec.toml"), "--plain", "--rerun"])        # its point runs, however it last ran
    finally:
        os.environ.pop("HEIMDALL_CONFIGS", None)
    (entry,) = runs.entries()
    assert entry["config"].endswith("rec.toml") and entry["argv"][:2] == ["run", str(config / "rec.toml")]
    assert (entry["code"], entry["verdict"]) == (code, runs.VERDICTS[code]) and entry["records"]
    assert entry["detached"] is False and entry["log"] is None
    assert entry["counts"] == {"done": 1, "failed": 0, "stopped": 0, "warned": 0}          # its points (V202)
    told = (Path(entry["records"][0]) / "run.jsonl").read_text(encoding="utf-8").splitlines()   # the run's own log
    assert json.loads(told[0])["state"] == "started" and json.loads(told[-1])["state"] == "finished"
