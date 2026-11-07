"""Live runs by index: `heimdall runs` lists the running and the paused runs, each
with an index [N] in the order they began (a resumed run in its pause's place); `heimdall watch -i N` follows the Nth,
refused for a paused one; `heimdall runs --resume N` starts a paused run's own command again, detached, in its work
dir, by its checkout's heimdall; `--forget N` drops a pause from the list. The registry is the tests' scratch one."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from runner import cli, house, paths, record, runs


def entry(started: float, **fields) -> str:
    """A recorded run of this process (so a running one is alive), begun at `started`."""
    run_id = runs.new_id(started)
    runs.begin(run_id, {"config": f"/w/configs/P/{fields.pop('name', 'a')}.toml", "configurations": ["c"], "work": "/w",
                        "started": started, **fields})
    return run_id


def paused(started: float, **fields) -> str:
    run_id = entry(started, **fields)
    runs.finish(run_id, 6, state="paused")
    return run_id


def snapshot(run_id: str, attempt: str, config_name: str = "P/b") -> Path:
    folder = paths.records_root() / "P" / run_id / attempt
    config = folder / "config" / f"{config_name}.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("[errand]\n", encoding="utf-8")
    (folder / "config" / record.SNAPSHOT).write_text(
        f'[snapshot]\nconfig = "{config_name}"\nconfiguration = "c"\n', encoding="utf-8")
    return folder


@pytest.fixture
def no_sockets(monkeypatch):
    """No watch socket answers: the live runs are the registry's alone."""
    monkeypatch.setattr(house, "live_runs", lambda config=None, configuration=None, pid=None: [])


@pytest.fixture
def mixed(no_sockets):
    """Running, paused, finished, forgotten and resumed entries, and one as a runner before pausing wrote it."""
    t0 = time.time() - 3600
    ids = {"resumed": paused(t0 - 600, name="e"),
           "pause": paused(t0, name="b", argv=["run", "P/b", "c", "--worker", "x"]),
           "done": entry(t0 + 100, name="c"),
           "forgotten": paused(t0 + 200, name="d"),
           "running": entry(t0 + 300, name="a")}
    runs.finish(ids["done"], 0)
    runs.update(ids["forgotten"], forgotten=t0 + 250)
    ids["again"] = entry(t0 + 400, name="e")                    # the resumed one's run: in its place
    runs.update(ids["resumed"], resumed_by=ids["again"])
    old = runs.new_id(t0 + 500)                                 # an old runner's entry: no state, progress or counts
    (runs.folder() / f"{old}.json").write_text(json.dumps(
        {"v": 1, "id": old, "kind": "run", **runs.here(), "started": t0 + 500, "config": "/w/configs/P/old.toml",
         "run": "old", "configurations": ["c"], "argv": ["run", "P/old"], "work": "/w", "checkout": "/x",
         "detached": True, "log": None}), encoding="utf-8")
    stopped = runs.new_id(t0 + 550)
    (runs.folder() / f"{stopped}.json").write_text(json.dumps(
        {"v": 1, "id": stopped, "kind": "run", **runs.here(), "started": t0 + 550, "finished": t0 + 560, "code": 6,
         "verdict": "stopped", "config": "/w/configs/P/old.toml", "configurations": ["c"]}), encoding="utf-8")
    ids["old"], ids["stopped"] = old, stopped
    return ids


def heads(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("  [")]


def test_runs_lists_the_live_ones_indexed_in_the_order_they_began(capsys, mixed):
    assert cli.main(["runs"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "live"
    assert [line.split()[:2] for line in heads(out)] == [["[1]", mixed["again"]], ["[2]", mixed["pause"]],
                                                         ["[3]", mixed["running"]], ["[4]", mixed["old"]]]
    for gone in ("done", "forgotten", "resumed", "stopped"):
        assert mixed[gone] not in out
    assert "· paused  ·" in out and "      heimdall runs --resume 2 · heimdall runs --forget 2" in out
    assert out.count("· running  ·") == 3
    listed = [e["id"] for e, _ in house.live_entries(runs.entries(), [])]
    assert listed == [mixed["again"], mixed["pause"], mixed["running"], mixed["old"]]   # what -i and --resume take


def test_the_history_says_a_pause_was_resumed_or_forgotten(capsys, mixed):
    assert cli.main(["runs", "--10"]) == 0
    out = capsys.readouterr().out
    assert "· paused, resumed  ·" in out and "· paused, forgotten  ·" in out and "· stopped  ·" in out
    assert not heads(out)                                     # indices are the live list's alone


def test_no_live_runs(capsys, no_sockets):
    assert cli.main(["runs"]) == 0
    assert capsys.readouterr().out.startswith("no live runs on this machine: none running, none paused")


def test_watch_i_follows_the_nth_live_run(capsys, mixed, monkeypatch):
    hello = {"k": "hello", "pid": os.getpid(), "config": "/w/configs/P/a.toml", "configurations": ["c"]}
    name = f"heimdall-watch-{os.getpid()}-1"
    monkeypatch.setattr(house, "live_runs", lambda config=None, configuration=None, pid=None:
                        [(name, hello)] if pid in (None, os.getpid()) else [])
    connected = []

    def connect(where: str, timeout: float = 2.0):            # events.connect's shape: a generator of events
        connected.append(where)
        yield hello
        yield {"k": "log", "msg": "from the run"}

    monkeypatch.setattr(cli, "connect", connect)
    assert cli.main(["watch", "-i", "3", "--plain"]) == 0
    assert connected == [name]


@pytest.mark.parametrize(("argv", "said"), [
    (["watch", "-i", "2"], "heimdall: [2] is paused: heimdall runs --resume 2"),
    (["watch", "-i", "9"], "heimdall: no live job [9]: there are 4"),
    (["watch", "--index", "0"], "heimdall: no live job [0]: there are 4"),
    (["watch", "-i", "1", "--pid", "7"], "heimdall: -i names the job itself"),
])
def test_watch_i_refuses_a_pause_and_an_index_out_of_range(capsys, mixed, argv, said):
    assert cli.main(argv) == 2
    err = capsys.readouterr().err
    assert err.startswith(said)
    if "there are" in said:                                   # the live ones listed
        assert f"[2] {mixed['pause']}  P/b · c · paused" in err and f"[4] {mixed['old']}" in err


def test_resume_starts_its_own_command_detached_in_its_work_dir(capsys, mixed, monkeypatch, scratch):
    work = scratch / "work"
    work.mkdir()
    (work / "heimdall.toml").write_text('[work]\nname = "resume-test"\n', encoding="utf-8")
    first = snapshot(mixed["pause"], "01_first")
    latest = snapshot(mixed["pause"], "02_latest", config_name="P/b.v2")
    live = work / "configs" / "P" / "b.v2.toml"
    live.parent.mkdir(parents=True)
    live.write_text("[errand]\n", encoding="utf-8")
    monkeypatch.setenv(paths.WORK_VAR, str(work))
    runs.update(mixed["pause"], work=str(work), checkout=str(paths.heimdall_root()),
                records=[str(first), str(latest)],
                argv=["run", "/w/configs/P/live.toml", "c", "--worker", "x"])
    launched = []

    def relaunch(command: list[str], cwd: str, env: dict) -> subprocess.CompletedProcess:
        launched.append((command, cwd, env))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runs, "relaunch", relaunch)
    assert cli.main(["runs", "--resume", "2"]) == 0
    ((command, cwd, env),) = launched
    assert command == [str(paths.heimdall_root() / "framework" / "bin" / "heimdall"), "run", "P/b.v2", "c", "--detach"]
    assert cwd == str(work) and env["HEIMDALL_WORK"] == str(work) and runs.ID.fullmatch(env[runs.ID_VAR])
    assert env[paths.CONFIGS_VAR] == str(latest / "config")
    assert str(first) not in env[paths.CONFIGS_VAR]
    assert paths.config_file(command[2]) == live
    with paths.configs_at(Path(env[paths.CONFIGS_VAR])):
        assert paths.config_file(command[2]) == latest / "config" / "P" / "b.v2.toml"
    after = runs.entry(mixed["pause"])
    assert after["resumed_by"] == env[runs.ID_VAR] and after["state"] == "paused"
    assert mixed["pause"] not in "".join(heads(cli_out(capsys)))      # it left the live list
    assert runs.ID_VAR not in os.environ


def test_resume_refuses_a_pause_without_a_snapshot(capsys, mixed, monkeypatch, scratch):
    work = scratch / "work"
    work.mkdir()
    runs.update(mixed["pause"], work=str(work), checkout=str(paths.heimdall_root()), records=[])
    launched = []
    monkeypatch.setattr(runs, "relaunch", lambda *args: launched.append(args))

    assert cli.main(["runs", "--resume", "2"]) == 2
    assert "has no recorded config snapshot" in capsys.readouterr().err
    assert launched == [] and runs.paused(runs.entry(mixed["pause"]))


def cli_out(capsys) -> str:
    capsys.readouterr()
    assert cli.main(["runs"]) == 0
    return capsys.readouterr().out


def test_resume_refuses_a_running_one_and_keeps_a_pause_whose_command_failed(capsys, mixed, monkeypatch, scratch):
    monkeypatch.setattr(runs, "relaunch", lambda command, cwd, env: subprocess.CompletedProcess(command, 2))
    assert cli.main(["runs", "--resume", "3"]) == 2
    assert capsys.readouterr().err.startswith("heimdall: [3] is running, not paused: only a paused job is resumed")
    saved = snapshot(mixed["pause"], "01_saved")
    runs.update(mixed["pause"], work=str(scratch), checkout=str(paths.heimdall_root()), records=[str(saved)])
    assert cli.main(["runs", "--resume", "2"]) == 2
    assert "[2] stays paused" in capsys.readouterr().err
    assert runs.paused(runs.entry(mixed["pause"]))
    runs.update(mixed["pause"], checkout=str(scratch / "gone"))
    assert cli.main(["runs", "--resume", "2"]) == 2
    assert "'s Heimdall is not there" in capsys.readouterr().err


def test_forget_drops_a_pause_and_keeps_its_entry(capsys, mixed):
    assert cli.main(["runs", "--forget", "3"]) == 2                # a running one
    assert "is running, not paused" in capsys.readouterr().err
    assert cli.main(["runs", "--forget", "2"]) == 0
    assert (runs.folder() / f"{mixed['pause']}.json").is_file() and runs.entry(mixed["pause"])["forgotten"]
    listed = [e["id"] for e, _ in house.live_entries(runs.entries(), [])]
    assert listed == [mixed["again"], mixed["running"], mixed["old"]]


def test_again_is_its_argv_without_the_worker_detached():
    assert runs.again({"argv": ["run", "P/b", "--worker", "20261101-000000-h-abcd", "--plain", "--detach"]}) == \
        ["run", "P/b", "--plain", "--detach"]
    assert runs.again({"argv": ["run", "P/b", "c", "--worker=x", "--set", "errand.events=5"]}) == \
        ["run", "P/b", "c", "--set", "errand.events=5", "--detach"]
    assert runs.again({"argv": ["cluster", "P/b"]}) == [] and runs.again({}) == []


def test_a_detached_run_takes_the_id_it_is_given(monkeypatch, capsys):
    """--resume names its new run's id ($HEIMDALL_RUN_ID): the detached worker is spawned with it, and the variable
    is not handed on; an id already used is not taken."""
    given = runs.new_id()
    spawned = []

    def spawn(argv: list[str], run_id: str, log: Path) -> subprocess.Popen:
        spawned.append((run_id, os.environ.get(runs.ID_VAR)))
        return subprocess.Popen(["true"])

    monkeypatch.setattr(runs, "spawn", spawn)
    for taken in (True, False):
        monkeypatch.setenv(runs.ID_VAR, given)
        if not taken:
            runs.begin(given, {})
        assert cli.main(["run", "Demo/jets", "single", "--detach"]) == 0     # the worker ended before its run began
        assert (spawned[-1][0] == given) is taken and spawned[-1][1] is None


def test_again_keeps_what_a_paused_rerun_completed():
    """The review's 3: a resumed --rerun job reruns what was complete before the paused job began, not what it did."""
    assert runs.again({"argv": ["run", "P/b", "--rerun"], "started": 1700000000.5}) == \
        ["run", "P/b", "--rerun-since", "1700000000.5", "--detach"]
    assert runs.again({"argv": ["run", "P/b", "--rerun-since", "1600000000.0", "--rerun"], "started": 1700000000.5}) == \
        ["run", "P/b", "--rerun-since", "1600000000.0", "--detach"]


def test_a_resume_that_never_runs_leaves_its_pause_live(capsys, mixed, monkeypatch, scratch):
    """The review's 2: the resumed job's worker fails while it plans (exit 2): it clears `resumed_by`, so the pause
    stays live and can be resumed again."""
    runs.update(mixed["pause"], work=str(scratch), checkout=str(paths.heimdall_root()))
    saved = snapshot(mixed["pause"], "01_saved")
    runs.update(mixed["pause"], records=[str(saved)])

    def relaunch(command: list[str], cwd: str, env: dict) -> subprocess.CompletedProcess:
        assert runs.entry(mixed["pause"])["resumed_by"] == env[runs.ID_VAR]       # marked before it starts
        monkeypatch.setenv(runs.RESUMES_VAR, env[runs.RESUMES_VAR])
        assert cli.main(["run", str(scratch / "no-such.toml"), "--worker", env[runs.ID_VAR]]) == 2
        assert runs.RESUMES_VAR not in os.environ
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runs, "relaunch", relaunch)
    assert cli.main(["runs", "--resume", "2"]) == 0
    assert runs.paused(runs.entry(mixed["pause"]))
    assert mixed["pause"] in "".join(heads(cli_out(capsys)))

