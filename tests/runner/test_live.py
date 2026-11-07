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

from runner import cli, execute, house, paths, record, runs


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
    """The first line of each block of the live list: `[N] host | title | P/<name> [c]`."""
    return [line for line in out.splitlines() if line.startswith("[")]


def names(out: str) -> list[str]:
    """The configs' names of the blocks, in order, which tell the entries apart (their ids are not on a live block)."""
    return [Path(line.split(" | ")[2].split()[0]).stem for line in heads(out)]


def test_runs_lists_the_live_ones_indexed_in_the_order_they_began(capsys, mixed):
    assert cli.main(["runs"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "live"
    assert [line.split()[0] for line in heads(out)] == ["[1]", "[2]", "[3]", "[4]"]
    assert names(out) == ["e", "b", "a", "old"]               # again, pause, running, old
    for gone in ("done", "forgotten", "resumed", "stopped"):
        assert mixed[gone] not in out
    assert "    paused · " in out and "    heimdall runs --resume 2 · heimdall runs --forget 2" in out
    assert out.count("    running · ") == 3
    listed = [e["id"] for e, _ in house.live_entries(runs.entries(), [])]
    assert listed == [mixed["again"], mixed["pause"], mixed["running"], mixed["old"]]   # what -i and --resume take


def test_the_history_says_a_pause_was_resumed_or_forgotten(capsys, mixed):
    assert cli.main(["runs", "--10"]) == 0
    out = capsys.readouterr().out
    assert "    paused, resumed · " in out and "    paused, forgotten · " in out and "    stopped · " in out
    first = lambda run_id: next(line for line in out.splitlines() if run_id in line.split(" | ")[0])      # noqa: E731
    assert first(mixed["done"]).startswith(f"{mixed['done']} ")                  # each by its id; no index: not live
    assert first(mixed["pause"]).startswith(f"[2] {mixed['pause']} ")             # a live one keeps its index


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
    assert "b" not in names(cli_out(capsys))                         # it left the live list
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
    assert "b" in names(cli_out(capsys))


def test_a_listing_is_plain_without_a_terminal_or_with_plain_or_no_color(capsys, mixed, monkeypatch):
    assert cli.main(["runs"]) == 0
    assert "\x1b[" not in capsys.readouterr().out                 # not a terminal: plain
    monkeypatch.setattr(house, "wants_colour", house.wants_colour)
    class Tty:
        isatty = staticmethod(lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    assert house.wants_colour(Tty())
    assert not house.wants_colour(Tty(), plain=True)
    monkeypatch.setenv("NO_COLOR", "1")
    assert not house.wants_colour(Tty())
    monkeypatch.setenv("NO_COLOR", "")                             # set and empty: colour stays (no-color.org)
    assert house.wants_colour(Tty())
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "dumb")
    assert not house.wants_colour(Tty())


def test_a_coloured_listing_carries_its_codes_and_says_the_same_words(mixed):
    plain = house.runs_listing(runs.entries(), [], {}, now=time.time())
    tinted = house.runs_listing(runs.entries(), [], {}, now=time.time(), color=True)
    strip = lambda line: __import__("re").sub(r"\x1b\[[0-9;]*m", "", line)          # noqa: E731
    assert [strip(line) for line in tinted] == plain
    out = "\n".join(tinted)
    assert "\x1b[1m[1]\x1b[0m" in out                              # the index, bold
    assert "\x1b[32mrunning\x1b[0m" in out and "\x1b[33mpaused\x1b[0m" in out        # green, yellow
    assert "\x1b[36mheimdall runs --resume 2 · heimdall runs --forget 2\x1b[0m" in out     # commands cyan
    assert "\x1b[36mheimdall watch -i 3 · heimdall stop -i 3\x1b[0m" in out


def test_each_state_has_its_colour_and_a_finished_one_its_again():
    entry = {"id": "20261026-120000-pp-abcd", "kind": "run", "started": 0.0, "finished": 10.0, "config": "/w/configs/P/a.toml",
             "configurations": ["c"]}
    for verdict, code in (("failed", "31"), ("stopped", "35"), ("done", "2")):
        lines = house.runs_listing([{**entry, "verdict": verdict}], [], {}, now=20.0, limit=5, color=True)
        assert f"\x1b[{code}m{verdict}\x1b[0m" in "\n".join(lines)
        again = "heimdall runs --again 20261026-120000-pp-abcd"
        assert (again in "\n".join(lines)) == (verdict != "done")
    assert house.paint("x", "grey", True) == "\x1b[90mx\x1b[0m" and house.paint("x", "grey", False) == "x"


def test_state_keeps_the_runs_in_those_states_and_an_unknown_one_is_refused(capsys, mixed):
    assert cli.main(["runs", "--10", "--state", "paused,stopped"]) == 0
    out = capsys.readouterr().out
    states = [line.split()[0] for line in out.splitlines() if line.startswith("    ") and " · " in line and line[4].islower()
              and line.split()[0].rstrip(",") in house.RUN_STATES]
    assert states and set(s.rstrip(",") for s in states) <= {"paused", "stopped"}
    assert "running" not in out and "    done" not in out
    assert cli.main(["runs", "--state", "paused"]) == 0                       # the live list: [N] stays the live number
    out = capsys.readouterr().out
    assert [line.split()[0] for line in heads(out)] == ["[2]"] and names(out) == ["b"]
    assert cli.main(["runs", "--state", "failed"]) == 0
    assert capsys.readouterr().out == "no failed runs here\n"
    assert cli.main(["runs", "--state", "sleeping"]) == 2
    assert "the states: running, paused, failed" in capsys.readouterr().err


def test_the_first_line_is_cut_to_the_width_and_never_loses_its_index():
    entry = {"id": "20261026-120000-pp-abcd", "kind": "run", "started": 0.0, "config": "/w/configs/Demo/a_long_name.toml",
             "configurations": ["one", "two", "three"], "work": "/w", "pid": os.getpid(), "pstart": runs.started_at(os.getpid()),
             "host": runs.host()}
    (head, *_), = [house.runs_listing([entry], [], {"/w": "A study with a title"}, now=5.0, width=30)[1:2]]
    assert len(head) == 30 and head.startswith("[1] ") and head.endswith("…")
    colored = house.runs_listing([entry], [], {}, now=5.0, width=30, color=True)[1]
    assert colored.startswith("\x1b[1m[1]\x1b[0m ")


def test_a_run_records_its_parallelism_and_its_failures_as_it_goes(monkeypatch):
    monkeypatch.setattr(runs.Recorder, "EVERY", 0.0)
    run_id = runs.new_id()
    runs.begin(run_id, {})
    recorder = runs.Recorder(run_id)
    recorder.event({"k": "run", "state": "started", "points": 3, "parallelism": 4})
    recorder.event({"k": "point", "point": "a", "state": "started", "index": 1})
    recorder.event({"k": "point", "point": "a", "state": "failed", "cause": "x", "msg": "m"})
    got = runs.entry(run_id)
    assert (got["parallelism"], got["points_failed"], got["points_completed"]) == (4, 1, 1)
    lines = house.runs_listing([{**got, "kind": "run", "started": 1.0, "config": "/w/configs/P/a.toml", "work": "/w",
                                 "pid": os.getpid(), "pstart": runs.started_at(os.getpid()), "host": runs.host()}], [], {}, now=5.0)
    assert lines[4] == "    running · 0 of 4 at once · 1/3 (1 failed)"


def test_stop_i_stops_the_nth_live_run_and_refuses_a_pause(capsys, mixed, monkeypatch):
    assert cli.main(["stop", "-i", "2"]) == 2                      # [2] is the pause
    assert "[2] is paused: heimdall runs --resume 2" in capsys.readouterr().err
    assert cli.main(["stop", "-i", "9"]) == 2
    assert "no live job [9]" in capsys.readouterr().err
    assert cli.main(["stop", "-i", "3", "--pid", "4"]) == 2
    assert "-i names the job itself" in capsys.readouterr().err
    hello = {"k": "hello", "pid": os.getpid(), "config": "/w/configs/P/a.toml", "configurations": ["c"], "id": mixed["running"]}
    monkeypatch.setattr(house, "live_runs", lambda config=None, configuration=None, pid=None:
                        [("heimdall-watch-x", hello)] if pid in (None, os.getpid()) else [])
    signalled = []
    real = os.kill
    monkeypatch.setattr(os, "kill", lambda pid, sig: signalled.append((pid, sig)) if sig else real(pid, sig))
    assert cli.main(["stop", "-i", "3", "--no-wait"]) == 0
    assert signalled == [(os.getpid(), __import__("signal").SIGINT)] and "stopping pid" in capsys.readouterr().out


def test_the_log_is_a_link_only_with_colour_and_its_text_is_the_same():
    entry = {"id": "20261026-120000-pp-abcd", "kind": "run", "started": 0.0, "finished": 10.0, "verdict": "done",
             "config": "/w/configs/P/a.toml", "configurations": ["c"], "host": "lab", "log": "/runs/a b.log"}
    plain = house.runs_listing([entry], [], {}, now=20.0, limit=5)
    assert plain[-1] == "    log /runs/a b.log" and not any("\x1b" in line for line in plain)
    tinted = house.runs_listing([entry], [], {}, now=20.0, limit=5, color=True)
    assert tinted[-1] == "    log \x1b]8;;file://lab/runs/a%20b.log\x1b\\\x1b[2m/runs/a b.log\x1b[0m\x1b]8;;\x1b\\"
    assert house.link("x", "h", "relative", True) == "x" and house.link("x", "h", "/p", False) == "x"


@pytest.fixture
def failed_run(mixed, scratch):
    """A finished, failed run with its record's config snapshot, its checkout and work dir there."""
    work = scratch / "work"
    work.mkdir(exist_ok=True)
    run_id = entry(time.time() - 7200, name="z", argv=["run", "P/z", "c", "--worker", "x", "--rerun"])
    saved = snapshot(run_id, "01_saved", config_name="P/z")
    runs.update(run_id, work=str(work), checkout=str(paths.heimdall_root()), records=[str(saved)])
    runs.finish(run_id, 1, verdict="failed")
    return run_id


def test_again_runs_a_failed_runs_command_from_its_snapshot_and_leaves_its_entry(capsys, failed_run, monkeypatch):
    monkeypatch.delenv(runs.RESUMES_VAR, raising=False)         # what an earlier test's worker left in the process is no part of this
    launched = []
    monkeypatch.setattr(runs, "relaunch", lambda command, cwd, env: launched.append((command, cwd, env))
                        or subprocess.CompletedProcess(command, 0))
    assert cli.main(["runs", "--again", failed_run]) == 0
    (command, cwd, env), = launched
    assert command[0].endswith("framework/bin/heimdall") and command[1:3] == ["run", "P/z"] and command[-1] == "--detach"
    assert "--worker" not in command and "--rerun-since" in command and "--rerun" not in command
    assert cwd == runs.entry(failed_run)["work"] and env[paths.CONFIGS_VAR].endswith("01_saved/config")
    assert env[runs.ID_VAR] != failed_run and runs.RESUMES_VAR not in env
    assert "resumed_by" not in runs.entry(failed_run)                # a finished run's entry is left as it is
    out = capsys.readouterr().out
    assert f"running again {failed_run}" in out and "run again as" in out
    assert cli.main(["runs", "--again", failed_run[-4:]]) == 0          # the tail of the id names it too
    assert len(launched) == 2


def test_again_refuses_a_run_that_goes_a_pause_and_what_is_not_there(capsys, mixed, failed_run, monkeypatch):
    launched = []
    monkeypatch.setattr(runs, "relaunch", lambda *args: launched.append(args))
    assert cli.main(["runs", "--again", "3"]) == 2                                     # [3] runs
    assert "[3] is running, not finished: only a run that ended is run again" in capsys.readouterr().err
    assert cli.main(["runs", "--again", "2"]) == 2                                     # [2] is the pause
    assert "[2] is paused, not finished: heimdall runs --resume 2" in capsys.readouterr().err
    assert cli.main(["runs", "--again", mixed["running"]]) == 2
    assert "[3] is running, not finished" in capsys.readouterr().err                       # by its id: the same run
    assert cli.main(["runs", "--again", "no-such-run"]) == 2
    assert "no run 'no-such-run'" in capsys.readouterr().err
    runs.update(failed_run, records=[])
    assert cli.main(["runs", "--again", failed_run]) == 2
    assert "has no recorded config snapshot" in capsys.readouterr().err
    assert launched == []


def test_again_says_when_its_command_failed_and_marks_nothing(capsys, failed_run, monkeypatch):
    monkeypatch.setattr(runs, "relaunch", lambda command, cwd, env: subprocess.CompletedProcess(command, 2))
    assert cli.main(["runs", "--again", failed_run]) == 2
    assert "not run again: its command exited 2" in capsys.readouterr().err


def test_i_prints_the_block_off_a_terminal_and_names_the_keys_that_fit(capsys, mixed, failed_run):
    assert cli.main(["runs", "-i", "2"]) == 0                       # not a terminal: the block alone
    out = capsys.readouterr().out
    assert out.startswith("run\n[2] ") and "paused" in out and "heimdall runs --resume 2" in out and "type " not in out
    assert cli.act_on("3", {}, key_reader=lambda: "q") == 0
    assert "w watch · s stop · j set jobs · q leave" in capsys.readouterr().out
    assert cli.act_on("2", {}, key_reader=lambda: "q") == 0
    assert "r resume · f forget · q leave" in capsys.readouterr().out
    assert cli.act_on(failed_run, {}, key_reader=lambda: "q") == 0
    assert "a run again · q leave" in capsys.readouterr().out
    assert cli.act_on(mixed["done"], {}, key_reader=lambda: "q") == 0
    assert "nothing to do with a run that is done" in capsys.readouterr().out


def test_an_action_needs_its_word_typed_and_anything_else_cancels(capsys, mixed, failed_run, monkeypatch):
    asked = []
    assert cli.act_on("2", {}, key_reader=lambda: "f", line_reader=lambda text: asked.append(text) or "yes") == 0
    assert asked == ["type forget to forget it (anything else cancels): "]
    assert "cancelled: forget not done" in capsys.readouterr().out and runs.paused(runs.entry(mixed["pause"]))
    assert cli.act_on("2", {}, key_reader=lambda: "f", line_reader=lambda text: "forget") == 0
    assert "forgotten: [2]" in capsys.readouterr().out and not runs.paused(runs.entry(mixed["pause"]))
    assert cli.act_on("2", {}, key_reader=lambda: "x") == 0                                 # a key that does not fit
    assert "'x' is not one of: w s j q" in capsys.readouterr().out       # [2] is now the running one
    launched = []
    monkeypatch.setattr(runs, "relaunch", lambda command, cwd, env: launched.append(command) or subprocess.CompletedProcess(command, 0))
    assert cli.act_on(failed_run, {}, key_reader=lambda: "a", line_reader=lambda text: "run again") == 0
    assert launched == [] and "cancelled: run again not done" in capsys.readouterr().out
    assert cli.act_on(failed_run, {}, key_reader=lambda: "a", line_reader=lambda text: "again") == 0
    assert len(launched) == 1


def test_the_stop_and_resume_keys_do_what_the_commands_do(capsys, mixed, monkeypatch):
    stopped, resumed = [], []
    monkeypatch.setattr(cli, "cmd_stop", lambda args: stopped.append((args.index, args.pid)) or 0)
    monkeypatch.setattr(cli, "resume_run", lambda index: resumed.append(index) or 0)
    assert cli.act_on("3", {}, key_reader=lambda: "s", line_reader=lambda text: "stop") == 0
    assert cli.act_on("2", {}, key_reader=lambda: "r", line_reader=lambda text: "resume") == 0
    assert (stopped, resumed) == ([(3, None)], [2])
    watched = []
    monkeypatch.setattr(cli, "cmd_watch", lambda args: watched.append(args.index) or 0)
    assert cli.act_on("3", {}, key_reader=lambda: "w") == 0                                 # watching asks for no word
    assert watched == [3]


def test_a_control_request_is_read_whole_and_a_bad_one_says_what_is_wrong():
    run_id = runs.new_id()
    assert runs.write_control(run_id, 3, by=77)
    got = runs.read_control(run_id)
    assert (got["parallelism"], got["by"]) == (3, 77) and isinstance(got["at"], float)
    assert not list(runs.folder().glob("*.tmp")) and runs.control_file(run_id).name == f"{run_id}.control.json"
    assert run_id not in [e["id"] for e in runs.entries()]            # a control file is no entry
    for text, said in (("", "is not JSON"), ("[1]", "no parallelism"), ('{"parallelism": 0}', "no parallelism of at least 1"),
                       ('{"parallelism": "4"}', "no parallelism"), ('{"parallelism": true}', "no parallelism")):
        runs.control_file(run_id).write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match=said):
            runs.read_control(run_id)
    runs.control_file(run_id).unlink()
    with pytest.raises(ValueError, match="there is no"):
        runs.read_control(run_id)


def test_a_request_applied_changes_the_cap_the_entry_and_tells_the_views(monkeypatch):
    from runner.events import Bus
    from runner.watch import State
    monkeypatch.setattr(runs.Recorder, "EVERY", 0.0)
    run_id = entry(time.time(), name="a")
    bus, heard = Bus(), []
    bus.subscribe(type("Listener", (), {"event": staticmethod(lambda event: heard.append(event))})())
    stopper = execute.Stopper()
    recorder = runs.Recorder(run_id)
    recorder.event({"k": "run", "state": "started", "points": 4, "parallelism": 1, "cores": 2})
    assert runs.entry(run_id)["parallelism"] == 1 and runs.entry(run_id)["point_cores"] == 2
    cli.apply_control(stopper, run_id, bus, recorder)                 # nothing asked: a note, nothing changed
    assert stopper.parallelism is None and "ignored: there is no" in heard[-1]["msg"]
    runs.write_control(run_id, 3, by=42)
    cli.apply_control(stopper, run_id, bus, recorder)
    assert stopper.cap(1) == 3 and runs.entry(run_id)["parallelism"] == 3
    assert heard[-1] == {"k": "parallelism", "from": 1, "to": 3, "by": 42, "point": "", "tool": ""} or \
        {k: heard[-1][k] for k in ("k", "from", "to", "by")} == {"k": "parallelism", "from": 1, "to": 3, "by": 42}
    assert State().apply(heard[-1]) == [("say", "   3 points at once now (was 1)")]
    runs.write_control(run_id, 10 ** 6)
    cli.apply_control(stopper, run_id, bus, recorder)
    assert stopper.cap(1) == 3 and "more than the 256" in heard[-1]["msg"]       # refused: the cap stays


def test_sigusr2_makes_a_worker_read_its_request_on_a_thread_of_its_own(monkeypatch):
    import signal
    from runner.events import Bus
    run_id = entry(time.time(), name="a")
    bus, heard = Bus(), []
    bus.subscribe(type("Listener", (), {"event": staticmethod(lambda event: heard.append(event))})())
    stopper = execute.Stopper()
    previous = signal.getsignal(signal.SIGUSR2)
    try:
        cli.catch_control(stopper)
        cli.control_thread(stopper, run_id, bus, None)
        runs.write_control(run_id, 2)
        os.kill(os.getpid(), signal.SIGUSR2)
        deadline = time.time() + 5
        while stopper.parallelism is None and time.time() < deadline:
            time.sleep(0.02)
    finally:
        signal.signal(signal.SIGUSR2, previous)
    assert stopper.parallelism == 2 and any(e.get("k") == "parallelism" and e["to"] == 2 for e in heard)


@pytest.fixture
def goes(mixed, monkeypatch):
    """The running one [3] as this process (so it is alive), os.kill faked: what was signalled is in `sent`."""
    sent = []
    real = os.kill
    monkeypatch.setattr(os, "kill", lambda pid, sig: sent.append((pid, sig)) if sig else real(pid, sig))
    runs.update(mixed["running"], parallelism=1, point_cores=2)
    return sent


def test_jobs_writes_the_request_and_signals_the_worker(capsys, mixed, goes):
    import signal
    assert cli.main(["runs", "-i", "3", "--jobs", "4"]) == 0
    assert goes == [(os.getpid(), signal.SIGUSR2)]
    assert runs.read_control(mixed["running"])["parallelism"] == 4
    out = capsys.readouterr()
    assert "[3]" in out.out and "points at once 1 → 4" in out.out
    assert "4 at once × ~2 core(s) a point is more than the" in out.err or (os.cpu_count() or 1) >= 8


def test_jobs_is_refused_for_what_is_not_a_running_job_here(capsys, mixed, goes):
    for argv, said in ((["runs", "--jobs", "4"], "--jobs changes one running job: name it"),
                       (["runs", "-i", "3", "--jobs", "0"], "a number from 1 to 256"),
                       (["runs", "-i", "3", "--jobs", "9999"], "a number from 1 to 256"),
                       (["runs", "-i", "2", "--jobs", "2"], "is paused, not running"),
                       (["runs", "-i", mixed["stopped"], "--jobs", "2"], "is stopped, not running")):
        assert cli.main(argv) == 2, argv
        assert said in capsys.readouterr().err, argv
    runs.update(mixed["running"], kind="cluster")
    assert cli.main(["runs", "-i", "3", "--jobs", "2"]) == 2
    assert "cluster submission" in capsys.readouterr().err
    runs.update(mixed["running"], kind="run", pidns="pid:[1]")
    assert cli.main(["runs", "-i", "3", "--jobs", "2"]) == 2
    assert "another PID namespace's" in capsys.readouterr().err
    runs.update(mixed["running"], pidns=runs.here()["pidns"], uid=os.getuid() + 1)           # another user's: not in this user's list
    assert cli.main(["runs", "-i", mixed["running"], "--jobs", "2"]) == 2
    assert f"no run '{mixed['running']}'" in capsys.readouterr().err
    assert goes == [] and not runs.control_file(mixed["running"]).exists()      # nothing was written or signalled


def test_the_j_key_asks_for_a_number_and_does_what_jobs_does(capsys, mixed, goes):
    assert cli.act_on("3", {}, key_reader=lambda: "j", line_reader=lambda text: "x") == 0
    assert "cancelled: 'x' is no number" in capsys.readouterr().out and goes == []
    assert cli.act_on("3", {}, key_reader=lambda: "j", line_reader=lambda text: "3") == 0
    assert runs.read_control(mixed["running"])["parallelism"] == 3 and len(goes) == 1


def test_a_spawned_worker_ignores_sigusr2_until_its_handler_is_in():
    import signal
    previous = signal.getsignal(signal.SIGUSR2)
    try:
        runs._pause_ignored()
        assert signal.getsignal(signal.SIGUSR2) == signal.SIG_IGN and signal.getsignal(signal.SIGUSR1) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGUSR2, previous)
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)
