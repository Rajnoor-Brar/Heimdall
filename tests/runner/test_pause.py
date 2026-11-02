"""Pausing a run (P2): SIGUSR1 (`p` in a watch) dispatches no more points and lets the
running ones end, then the run quits without its later stages, exit 6, its entry "paused"; a second is a force
pause, the running points stopped as a hard stop stops them; a rerun resumes. Real runs of small shell-tool points
(an exec tool that waits for a file), so nothing here needs the stack's generators."""

from __future__ import annotations

import json
import os
import signal
import threading
import time
from pathlib import Path

import pytest

from runner import cli, execute, record, runs

POINT = """#!/bin/sh
# $1: the exec tool's config file; $2: the point's value of q
touch "{marks}/started.$2"
i=0
while [ ! -e "{marks}/go" ] && [ $i -lt 400 ]; do sleep 0.05; i=$((i+1)); done
"""

ERRAND = """[errand]
name          = "{name}"
assignment    = "Demo"
configuration = "c"
event_count   = 1
parallelism   = 2

[errand.cfgs.c]
sweeps = ["q"]
tools  = ["x"]

[tools.x]
tool       = "exec"
executable = "{script}"
arguments  = ["{{q:q}}"]
consumes   = ["q"]

[quantities.q]
values = ["a", "b", "c", "d"]
tags   = ["a", "b", "c", "d"]
"""


@pytest.fixture
def handlers():
    """The signal handlers a run in this process installs, put back after it."""
    kept = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGUSR1)}
    yield
    for signum, handler in kept.items():
        signal.signal(signum, handler)


@pytest.fixture
def errand(scratch, monkeypatch, handlers):
    """An errand file of four points, two at once, each waiting for marks/go (20 s at most), its trees in the
    test's scratch; returns (its path, the marks folder)."""
    for var, name in (("HEIMDALL_RECORDS", "records"), ("HEIMDALL_CACHE", "cache"), ("HEIMDALL_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    marks = scratch / "marks"
    marks.mkdir()
    script = scratch / "point.sh"
    script.write_text(POINT.format(marks=marks), encoding="utf-8")
    script.chmod(0o755)
    folder = scratch / "configs" / "Demo"
    folder.mkdir(parents=True)
    path = folder / "pause.toml"
    path.write_text(ERRAND.format(name="pause", script=script), encoding="utf-8")
    monkeypatch.setenv("HEIMDALL_CONFIGS", str(scratch / "configs"))
    return path, marks


def started(marks: Path) -> list[str]:
    return sorted(p.name.split(".", 1)[1] for p in marks.glob("started.*"))


def signal_when_running(marks: Path, presses: int, go: bool, running: int = 2) -> threading.Thread:
    """Once `running` points run, SIGUSR1 to this process `presses` times; then (`go`) let the points end."""
    def act():
        until = time.monotonic() + 30
        while len(started(marks)) < running and time.monotonic() < until:
            time.sleep(0.05)
        time.sleep(0.2)
        for _ in range(presses):
            os.kill(os.getpid(), signal.SIGUSR1)
            time.sleep(0.3)
        if go:
            (marks / "go").touch()
    thread = threading.Thread(target=act, daemon=True)
    thread.start()
    return thread


def run(path: Path) -> int:
    return cli.main(["run", str(path), "--plain"])


def plans_of(path: Path):
    return cli.build_plans(cli.parse(["run", str(path)]), "c").plans


def test_a_pause_lets_the_running_points_end_and_starts_no_more(errand, capsys):
    """P1, P2: the two running points complete, the other two are not started; exit 6, the run's verdict and the
    registry entry say paused (heimdall runs lists it so, run.jsonl and heimdall log say it); a rerun resumes,
    the complete points skipped."""
    path, marks = errand
    helper = signal_when_running(marks, presses=1, go=True)
    assert run(path) == 6
    helper.join(5)
    assert started(marks) == ["a", "b"]
    plans = plans_of(path)
    assert [record.is_complete(p) for p in plans] == [True, True, False, False]
    (entry,) = runs.entries()
    assert (entry["code"], entry["state"], entry["verdict"]) == (6, "paused", "paused") and runs.state(entry) == "paused"
    assert entry["verdicts"][""] == "paused: 2 done, 2 left; not run: plot"
    assert entry["counts"]["done"] == 2 and entry["counts"]["stopped"] == 0
    out = capsys.readouterr().out
    assert "paused: 2 done, 2 left; not run: plot" in out
    told = [json.loads(line) for line in (Path(entry["records"][0]) / "run.jsonl").read_text(encoding="utf-8").splitlines()]
    assert told[-1]["state"] == "finished" and told[-1]["verdict"] == "paused: 2 done, 2 left; not run: plot"
    assert cli.main(["log", entry["records"][0]]) == 0
    assert "paused: 2 done, 2 left" in capsys.readouterr().out
    assert cli.main(["runs", "--5"]) == 0 and "paused" in capsys.readouterr().out
    assert run(path) == 0                                        # a resume: the same command again
    assert started(marks) == ["a", "b", "c", "d"] and all(record.is_complete(p) for p in plans_of(path))
    assert runs.state(runs.entries()[0]) == "done"


def test_a_second_pause_discards_the_running_points(errand, capsys):
    """P1: a second SIGUSR1 stops the running points as a hard stop does (recorded stopped, their tools killed at
    once), none more started; the run is still paused. A rerun runs them again and completes the rest."""
    path, marks = errand
    helper = signal_when_running(marks, presses=2, go=False)
    begun = time.monotonic()
    assert run(path) == 6
    assert time.monotonic() - begun < 15                         # killed, not waited for (20 s)
    helper.join(5)
    assert started(marks) == ["a", "b"]
    plans = plans_of(path)
    assert not any(record.is_complete(p) for p in plans)
    assert [record.attempts(p)[-1]["verdict"] for p in plans[:2]] == ["stopped", "stopped"]
    assert [record.attempts(p) for p in plans[2:]] == [[], []]
    (entry,) = runs.entries()
    assert runs.state(entry) == "paused" and entry["counts"]["stopped"] == 2
    assert entry["verdicts"][""] == "paused: 0 done, 2 discarded, 2 left; not run: plot"
    (marks / "go").touch()
    assert run(path) == 0
    assert started(marks) == ["a", "b", "c", "d"] and all(record.is_complete(p) for p in plans_of(path))


def test_a_pause_one_point_at_a_time(errand):
    """The dispatcher's one-at-a-time path: the running point completes, the next is not started."""
    path, marks = errand
    path.write_text(path.read_text(encoding="utf-8").replace("parallelism   = 2", "parallelism   = 1"), encoding="utf-8")
    helper = signal_when_running(marks, presses=1, go=True, running=1)
    assert run(path) == 6
    helper.join(5)
    assert started(marks) == ["a"] and [record.is_complete(p) for p in plans_of(path)] == [True, False, False, False]
    (entry,) = runs.entries()
    assert runs.state(entry) == "paused" and entry["verdicts"][""] == "paused: 1 done, 3 left; not run: plot"


def test_a_stop_after_a_pause_is_a_stop(handlers):
    """P1: a q (SIGINT) after a p is a stop, recorded so; after a force pause it does not kill the run at once."""
    stopper = execute.Stopper()
    cli.catch_signals(stopper)
    cli.catch_pause(stopper)

    def signalled(signum):
        os.kill(os.getpid(), signum)
        time.sleep(0.05)
    signalled(signal.SIGUSR1)
    assert stopper.pausing and stopper.paused and stopper.halted and not stopper.requested
    signalled(signal.SIGINT)
    assert stopper.requested and not stopper.hard and not stopper.paused
    signalled(signal.SIGUSR1)                                    # a stop stays a stop
    assert not stopper.paused and not stopper.hard
    forced = execute.Stopper()
    cli.catch_signals(forced)
    cli.catch_pause(forced)
    signalled(signal.SIGUSR1)
    signalled(signal.SIGUSR1)
    assert forced.requested and forced.hard and forced.paused
    signalled(signal.SIGINT)                                     # a stop now, the process still alive
    assert forced.requested and not forced.paused


@pytest.mark.parametrize("stages, verdict", [([], "paused: 2 done, 2 left; not run: plot"),       # pipelined
                                            (["--stages", "points"], "paused: 2 done, 2 left")])  # one after another
def test_a_paused_sweep_begins_no_more_configurations(errand, stages, verdict):
    """P2: in a sweep of runs, pipelined or one after another, the configurations after a paused one are not
    begun."""
    path, marks = errand
    text = path.read_text(encoding="utf-8").replace('configuration = "c"\n', 'configuration = "c"\nsweep_runs    = ["c", "e"]\n')
    path.write_text(text + '\n[errand.cfgs.e]\nsweeps = ["q"]\ntools  = ["x"]\n', encoding="utf-8")
    helper = signal_when_running(marks, presses=1, go=True)
    assert cli.main(["run", str(path), "--plain", *stages]) == 6
    helper.join(5)
    (entry,) = runs.entries()
    assert runs.state(entry) == "paused" and list(entry["verdicts"]) == ["c"] and entry["verdicts"]["c"] == verdict
    assert len(entry["records"]) == 1


@pytest.mark.parametrize("sweep", [False, True])
def test_a_pause_while_it_plans_runs_nothing_and_is_paused(errand, monkeypatch, capsys, sweep):
    """The review's 1 and 6: a pause that comes while the job plans begins nothing, says so, and exits 6 recorded
    paused, a pipelined sweep's too (it began no run)."""
    path, marks = errand
    if sweep:
        text = path.read_text(encoding="utf-8").replace('configuration = "c"\n', 'configuration = "c"\nsweep_runs    = ["c", "e"]\n')
        path.write_text(text + '\n[errand.cfgs.e]\nsweeps = ["q"]\ntools  = ["x"]\n', encoding="utf-8")
    planned = cli.build_plans

    def build_plans(args, key):
        out = planned(args, key)
        os.kill(os.getpid(), signal.SIGUSR1)
        time.sleep(0.05)
        return out

    monkeypatch.setattr(cli, "build_plans", build_plans)
    assert run(path) == 6
    assert started(marks) == []
    (entry,) = runs.entries()
    assert runs.state(entry) == "paused"
    if not sweep:
        assert "paused before it began: nothing run" in capsys.readouterr().out


POST = """#!/bin/sh
touch "{marks}/post"
i=0
while [ $i -lt 400 ]; do sleep 0.05; i=$((i+1)); done
"""


def test_a_force_pause_in_post_says_what_it_left(errand, capsys):
    """The review's 4: a force pause while the post tools run is a pause whose verdict names post as not run."""
    path, marks = errand
    script = marks.parent / "post.sh"
    script.write_text(POST.format(marks=marks), encoding="utf-8")
    script.chmod(0o755)
    text = path.read_text(encoding="utf-8").replace('tools  = ["x"]\n', 'tools  = ["x"]\npost   = ["y"]\n', 1)
    path.write_text(text + f'\n[tools.y]\ntool       = "exec"\nexecutable = "{script}"\n', encoding="utf-8")
    (marks / "go").touch()

    def act():
        until = time.monotonic() + 30
        while not (marks / "post").exists() and time.monotonic() < until:
            time.sleep(0.05)
        time.sleep(0.2)
        for _ in range(2):
            os.kill(os.getpid(), signal.SIGUSR1)
            time.sleep(0.3)
    helper = threading.Thread(target=act, daemon=True)
    helper.start()
    begun = time.monotonic()
    assert run(path) == 6
    assert time.monotonic() - begun < 15
    helper.join(5)
    (entry,) = runs.entries()
    assert runs.state(entry) == "paused"
    assert entry["verdicts"][""].startswith("paused: 4 done") and entry["verdicts"][""].endswith("not run: post, plot")


def test_rerun_since_runs_again_only_what_completed_before(errand):
    """The review's 3: `--rerun-since T` (a resumed --rerun job) runs again the points complete before T and skips
    those completed since."""
    path, marks = errand
    (marks / "go").touch()
    before = time.time() - 1
    assert run(path) == 0
    for name in started(marks):
        (marks / f"started.{name}").unlink()
    assert cli.main(["run", str(path), "--plain", "--rerun-since", repr(before)]) == 0
    assert started(marks) == []
    assert cli.main(["run", str(path), "--plain", "--rerun-since", repr(time.time() + 1)]) == 0
    assert started(marks) == ["a", "b", "c", "d"]


def test_a_worker_ignores_a_pause_before_its_handler_is_in(scratch):
    """The review's 5: a `p` before the worker installs its handler is not SIGUSR1's default death."""
    import subprocess
    done = subprocess.run(["sh", "-c", "kill -USR1 $$; echo alive"], preexec_fn=runs._pause_ignored,
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0 and done.stdout.strip() == "alive"
