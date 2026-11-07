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
