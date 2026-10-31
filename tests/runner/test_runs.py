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


@pytest.mark.skipif(os.getuid() == 0 or not runs.started_at(1) or os.stat("/proc/1").st_uid == os.getuid(),
                    reason="needs another user's process, readable in /proc")
def test_a_pid_reused_by_another_users_process_is_lost():
    """A pid now another user's (init's, here) is this user's run only if it started when the run did: a reused
    pid is "lost", never "in another PID namespace" and listed as running."""
    base = {**runs.here(), "id": "x", "started": time.time(), "pid": 1}
    assert runs.state({**base, "pstart": "1"}) == "lost"
    assert runs.state({**base, "pstart": ""}) == "lost"
    assert runs.state({**base, "pstart": runs.started_at(1)}) == "running"


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


def test_heimdall_runs_defaults_to_running_only_and_separates_entries(capsys, monkeypatch):
    """An unrecorded live socket (a run from inside an image) is shown, but completed entries are not."""
    done = runs.new_id(time.time() - 3600)
    runs.begin(done, {"config": "/w/configs/P/a.toml", "configurations": ["one"], "work": "/w", "log": "/l/x.log"})
    runs.finish(done, 0)
    hub = Hub({"config": "/w/configs/P/b.toml", "configurations": ["two"], "work": "/w"}, name=f"heimdall-watch-{os.getpid()}-9")
    monkeypatch.setattr(runs, "entries", lambda: [runs.entry(done)])
    monkeypatch.setattr(house, "live_runs", lambda: [(hub.name, hub.greeting)])
    try:
        assert cli.main(["runs"]) == 0
    finally:
        hub.close()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "running" and out[2].endswith("P/b · two")                 # no serial known: no NN
    assert "running (unrecorded)" in out[3]
    assert f"heimdall watch --pid {os.getpid()}" in out[4]
    assert done not in "\n".join(out) and "P/a · one" not in "\n".join(out)


@pytest.mark.parametrize(("flag", "count"), [("--5", 5), ("--10", 10), ("--20", 20), ("--50", 50)])
def test_heimdall_runs_count_flags_show_latest_entries_oldest_first(capsys, monkeypatch, flag, count):
    now = time.time()
    ids = []
    for i in range(12):
        started = now - (12 - i) * 60
        run_id = runs.new_id(started)
        runs.begin(run_id, {"config": f"/w/configs/P/run{i}.toml", "work": "/w", "started": started})
        if i < 11:
            runs.finish(run_id, 0)
        ids.append(run_id)
    monkeypatch.setattr(runs, "entries", lambda: [runs.entry(run_id) for run_id in ids])
    monkeypatch.setattr(house, "live_runs", lambda: [])

    try:
        assert cli.main(["runs", flag]) == 0
        out = capsys.readouterr().out.splitlines()
    finally:
        runs.finish(ids[-1], 0)
    listed = [line.split()[0] for line in out if line.startswith("  ") and line.split()[0] in ids]
    expected_count = min(count, len(ids))
    assert out[0] == f"latest {count} runs"
    assert listed == ids[-expected_count:]
    assert any("· running  ·" in line for line in out)
    assert any("· done  ·" in line for line in out)
    assert out.count("") == expected_count - 1


def test_heimdall_runs_uses_title_and_configuration_serial_columns():
    pid = os.getpid()
    entry = {
        **runs.here(),
        "id": "20261030-084424-pp-exphep-e17e",
        "kind": "run",
        "started": time.mktime((2026, 10, 30, 8, 44, 0, 0, 0, -1)),
        "config": "/w/configs/eic/zeus.toml",
        "configurations": ["generator_pdf"],
        "configuration_serials": {"generator_pdf": 12},
        "work": "/w",
        "pid": pid,
        "pstart": runs.started_at(pid),
        "points_completed": 3,
        "points_total": 7,
        "active_parallel_points": 2,
        "log": "/runs/20261030-084424-pp-exphep-e17e.log",
    }
    lines = house.runs_listing([entry], [], {"/w": "Brookhaven"}, now=entry["started"] + 5101)
    assert lines[1] == f"  {entry['id']:28s}  |   Brookhaven"
    assert lines[2] == "      eic/zeus · 12 generator_pdf"
    assert lines[3] == (f"      {time.strftime('%m-%d %H:%M', time.localtime(entry['started']))} "
                        "(1h 25m) · running  ·  3/7 ·  2")
    assert lines[4] == f"      pid {pid} : heimdall watch --pid {pid} · heimdall stop --pid {pid}"
    assert lines[5] == f"      log {entry['log']}"


def test_runs_recorder_persists_live_point_progress(monkeypatch):
    monkeypatch.setattr(runs.Recorder, "EVERY", 0.0)
    run_id = runs.new_id()
    runs.begin(run_id, {"points_completed": 0, "points_total": None, "active_parallel_points": 0})
    recorder = runs.Recorder(run_id)
    events = [
        {"k": "run", "state": "started", "points": 3},
        {"k": "point", "point": "a", "state": "started"},
        {"k": "point", "point": "b", "state": "started"},
        {"k": "point", "point": "a", "state": "done"},
        {"k": "point", "point": "c", "state": "started"},
    ]
    for event in events:
        recorder.event(event)
    entry = runs.entry(run_id)
    assert (entry["points_completed"], entry["points_total"], entry["active_parallel_points"]) == (1, 3, 2)


def test_the_recorder_counts_configuration_points_not_stages():
    """Pre, post and combined stages carry `stage`: only configuration points count, so a run's progress never
    ends above its total (7/3)."""
    recorder = runs.Recorder()
    recorder.plan({"": 3})
    stage = lambda name, state, **e: {"k": "point", "point": name, "state": state, **e}
    for event in (stage("pre", "started", index=-1, stage="pre"), stage("pre", "done", stage="pre"),
                  stage("a", "started", index=1), stage("a", "done"), stage("b", "skipped", index=2),
                  stage("c", "started", index=3), stage("c", "failed"), stage("c", "done"),       # ended once
                  stage("combined", "started", index=1, stage="combined"), stage("combined", "done", stage="combined"),
                  stage("post", "started", index=0, stage="post"), stage("post", "done", stage="post")):
        recorder.event(event)
    assert recorder.progress()["points_completed"] == 3 and recorder.progress()["points_total"] == 3
    assert recorder.progress()["active_parallel_points"] == 0


def test_the_pre_and_post_stages_are_planned_as_stages(scratch):
    from helpers import plan, raw
    from runner import post
    from runner.quantities import load_master
    run, configuration, point = plan(raw(run__cfgs__one__pre=[["pythia"]], run__cfgs__one__post=[["pythia"]]), scratch)
    master = load_master(run.project, run.master_toml)
    pre = post.plan_pre(run, configuration, master, [point.point])
    after = post.plan(run, configuration, master, [point])
    assert (pre.point.index, pre.point.stage, after.point.index, after.point.stage) == (-1, "pre", 0, "post")
    assert point.point.stage == ""


def test_the_total_is_planned_up_front():
    """The whole command's points from the start, not only the runs begun so far; a run planned again at its
    turn (its TOML edited) brings its own count; a run with no points to end (--only post) stays at none."""
    run_id = runs.new_id()
    runs.begin(run_id, {"points_completed": 0, "points_total": None})
    recorder = runs.Recorder(run_id)
    recorder.plan({"a": 2, "b": 3, "c": 0})
    assert runs.entry(run_id)["points_total"] == 5
    recorder.event({"k": "run", "state": "started", "points": 2, "run": "a"})
    recorder.event({"k": "run", "state": "started", "points": 4, "run": "b"})              # planned again
    recorder.event({"k": "run", "state": "started", "points": 7, "run": "c"})
    assert runs.entry(run_id)["points_total"] == 6
    assert runs.Recorder().progress()["points_total"] is None                               # nothing planned yet


def test_the_recorder_writes_at_most_every_few_seconds(monkeypatch):
    """The entry is written at a run's start and end at once, and between them at most every EVERY seconds (a
    timer writes what was left); after close, never: the run's finish writes the last state."""
    monkeypatch.setattr(runs.Recorder, "EVERY", 0.5)
    written = []
    real = runs._write
    monkeypatch.setattr(runs, "_write", lambda path, data: written.append(dict(data)) or real(path, data))
    run_id = runs.new_id()
    runs.begin(run_id, {})
    written.clear()
    recorder = runs.Recorder(run_id)
    recorder.event({"k": "run", "state": "started", "points": 3})
    assert len(written) == 1
    for name in "abc":
        recorder.event({"k": "point", "point": name, "state": "started", "index": 1})
    assert len(written) == 1 and runs.entry(run_id)["active_parallel_points"] == 0
    time.sleep(2.0)
    assert len(written) == 2 and runs.entry(run_id)["active_parallel_points"] == 3
    recorder.event({"k": "point", "point": "a", "state": "done"})
    recorder.event({"k": "run", "state": "finished", "verdict": "1 done"})
    assert runs.entry(run_id)["points_completed"] == 1
    count = len(written)
    recorder.event({"k": "point", "point": "b", "state": "done"})
    assert recorder.close() == {"points_completed": 2, "points_total": 3, "active_parallel_points": 1,
                                "configuration_serials": {}}
    time.sleep(2.0)
    assert len(written) == count and runs.entry(run_id)["points_completed"] == 1        # the timer was cancelled


def test_a_sequential_sweep_keys_each_configuration(scratch, monkeypatch):
    """--stages runs a sweep's configurations one after another, each on its own RunBus: two configurations'
    points of the same name are two points, and their pre and post stages are none. The total is the whole
    sweep's from the start, before the first run begins."""
    from helpers import raw
    import tomli_w
    config = scratch / "configs" / "Demo"
    config.mkdir(parents=True)
    check = {"tool": "exec", "executable": "/bin/true"}
    data = raw(run__sweep_runs=["a", "b"], run__configuration=None, run__cfgs__one=None, prelim=None, quantities=None,
               static=None, tools={"check": check},
               run__cfgs__a={"tools": ["check"], "pre": ["check"], "post": ["check"]}, run__cfgs__b={"tools": ["check"]})
    (config / "two.toml").write_text(tomli_w.dumps(data), encoding="utf-8")
    seen = []
    event = runs.Recorder.event

    def probe(self, message):
        if message.get("k") == "run" and message.get("state") == "started" and message.get("run") == "a":
            seen.append(runs.entry(self.run_id)["points_total"])
        return event(self, message)

    monkeypatch.setattr(runs.Recorder, "event", probe)
    os.environ["HEIMDALL_CONFIGS"] = str(scratch / "configs")
    try:
        code = cli.main(["run", str(config / "two.toml"), "--plain", "--rerun", "--stages", "pre,points,post"])
    finally:
        os.environ.pop("HEIMDALL_CONFIGS", None)
    (entry,) = runs.entries()
    assert code == 0 and set(entry["verdicts"]) == {"a", "b"}
    assert (entry["points_completed"], entry["points_total"], entry["active_parallel_points"]) == (2, 2, 0)
    assert seen == [2]                                                    # planned up front, not as runs start


def test_heimdall_runs_takes_no_abbreviated_count():
    """--1 is no --10: the counts are four options, never abbreviated."""
    with pytest.raises(SystemExit) as stopped:
        cli.main(["runs", "--1"])
    assert stopped.value.code == 2


def test_runs_recorder_captures_runner_assigned_output_serial():
    run_id = runs.new_id()
    initial_serials = {"generator_pdf": None}
    runs.begin(run_id, {"configuration_serials": initial_serials})
    recorder = runs.Recorder(run_id, initial_serials, {"generator_pdf": "generator_pdf"})
    recorder.event({"k": "run", "state": "started",
                    "record": "/work/records/eic/zeus/03_generator_pdf"})
    assert runs.entry(run_id)["configuration_serials"] == {"generator_pdf": 3}


def test_heimdall_runs_historical_entry_uses_null_counts_without_active_count():
    entry = {"id": "20261026-120000-pp-abcd", "kind": "run", "started": 0.0, "finished": 10.0,
             "verdict": "done", "config": "/w/configs/eic/zeus.toml", "configurations": ["generator_pdf"]}
    lines = house.runs_listing([entry], [], {}, now=20.0, limit=5)
    when = time.strftime("%m-%d %H:%M", time.localtime(0))
    assert lines[3] == f"      {when} (0m) · done  ·  NULL/NULL"
    assert all("active_parallel_points" not in line for line in lines)


@pytest.mark.parametrize(("flag", "days", "expected"), [
    ("--week", 7, {"day1", "day6", "day7"}),
    ("--month", 28, {"day1", "day6", "day7", "day8", "day27", "day28"}),
])
def test_heimdall_runs_period_flags_show_all_states_in_the_period(capsys, monkeypatch, flag, days, expected):
    now = time.time()
    entries = []
    for label, age in (("day1", 1), ("day6", 6), ("day7", 7), ("day8", 8),
                       ("day27", 27), ("day28", 28), ("day29", 29)):
        started = now - age * 86400 + 1
        entries.append({"id": label, "kind": "run", "started": started, "finished": started + 10,
                        "verdict": "failed" if label == "day6" else "done", "config": f"/w/configs/P/{label}.toml",
                        "work": "/w"})
    monkeypatch.setattr(runs, "entries", lambda: entries)
    monkeypatch.setattr(house, "live_runs", lambda: [])

    assert cli.main(["runs", flag]) == 0
    out = capsys.readouterr().out.splitlines()
    listed = [line.split()[0] for line in out if line.startswith("  ") and line.split()[0] in {e["id"] for e in entries}]
    assert out[0] == f"runs from the last {days} days"
    assert set(listed) == expected
    assert listed == sorted(expected, key=lambda run_id: int(run_id.removeprefix("day")), reverse=True)
    assert out.count("") == len(expected) - 1


def test_heimdall_runs_period_and_count_flags_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["runs", "--week", "--10"])
    assert error.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


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
