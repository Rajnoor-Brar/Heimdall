"""Detached runs end to end (V183): a real worker started by --detach or by a live terminal run, followed by
heimdall watch, stopped by heimdall stop, Ctrl-C, or left by d; the registry's entry each time (V182)."""

from __future__ import annotations

import json
import os
import pty
import select
import signal
import stat
import subprocess
import time
from pathlib import Path

import pytest

from support import HEIMDALL, WORK, env

pytestmark = pytest.mark.slow

SLEEPY = """#!/usr/bin/env python3
import sys, time, tomllib
config = tomllib.load(open(sys.argv[1], "rb"))
time.sleep(config.get("sleep", 0))
sys.exit(config.get("quantities", {}).get("fail", 0))
"""


def config_of(scratch: Path, sleep: float, fails=(0, 1, 0, 0)) -> Path:
    script = scratch / "sleepy.py"
    script.write_text(SLEEPY, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    config = scratch / "det.toml"
    config.write_text(f"""\
[errand]
name          = "det"
assignment    = "Demo"
configuration = "one"
event_count   = 1
parallelism   = 2

[errand.cfgs.one]
sweeps = ["fail"]
tools  = ["sleepy"]

[tools.sleepy]
tool       = "exec"
executable = "{script}"
consumes   = ["fail"]

[tools.sleepy.config]
sleep = {sleep}

[quantities.fail]
values = {list(fails)}
tags   = {[f"p{i}" for i in range(len(fails))]}
""", encoding="utf-8")
    return config


@pytest.fixture
def where(scratch):
    """A registry of its own; any worker still alive at the end is killed."""
    environment = dict(env(scratch), HEIMDALL_RUNS=str(scratch / "runs"))
    yield scratch, environment
    for path in (scratch / "runs").glob("*.json"):
        pid = json.loads(path.read_text(encoding="utf-8")).get("pid")
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, TypeError):
            pass
    subprocess.run(["pkill", "-KILL", "-f", str(scratch / "sleepy.py")], capture_output=True)   # tools: their own sessions


def heimdall(environment, *args, timeout=120):
    return subprocess.run([str(HEIMDALL), *map(str, args)], cwd=WORK, env=environment, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def entries(scratch: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((scratch / "runs").glob("*.json"))]


def wait_until(test, timeout=60.0):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if (got := test()):
            return got
        time.sleep(0.2)
    raise AssertionError("timed out")


def test_detach_returns_once_started_and_watch_follows_it_to_its_verdict(where):
    scratch, environment = where
    started = time.monotonic()
    done = heimdall(environment, "run", config_of(scratch, 3), "--detach")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "running in the background" in done.stdout and time.monotonic() - started < 30
    (entry,) = entries(scratch)
    assert entry["detached"] and Path(entry["log"]).is_file() and "finished" not in entry
    listed = heimdall(environment, "runs").stdout
    assert listed.startswith("running") and entry["id"] in listed
    watched = heimdall(environment, "watch", "--pid", entry["pid"], "--plain", timeout=180)
    assert watched.returncode == 0 and "3 done, 1 failed" in watched.stdout, watched.stdout
    (entry,) = entries(scratch)
    assert (entry["code"], entry["verdict"]) == (1, "failed") and entry["records"]
    assert " ── ok after " in Path(entry["log"]).read_text(encoding="utf-8")


def test_stop_ends_a_detached_run_as_ctrl_c_would(where):
    scratch, environment = where
    assert heimdall(environment, "run", config_of(scratch, 60), "--detach").returncode == 0
    (entry,) = entries(scratch)
    wait_until(lambda: "point" in Path(entry["log"]).read_text(encoding="utf-8") or True)
    done = heimdall(environment, "stop", "--pid", entry["pid"])
    assert done.returncode == 0 and "stopped: stopped" in done.stdout, done.stdout + done.stderr
    (entry,) = entries(scratch)
    assert entry["code"] == 6 and not list((scratch / "records").glob("Demo/det/*/points/*/.complete"))
    assert not subprocess.run(["pgrep", "-f", str(scratch / "sleepy.py")], capture_output=True).stdout


def test_a_detached_run_that_does_not_plan_says_why(where):
    scratch, environment = where
    config = config_of(scratch, 0)
    config.write_text(config.read_text(encoding="utf-8").replace('tools  = ["sleepy"]', 'tools  = ["sleepless"]'),
                      encoding="utf-8")
    done = heimdall(environment, "run", config, "--detach")
    assert done.returncode == 2 and "sleepless" in done.stderr, done.stdout + done.stderr


def test_a_plain_run_is_recorded_too(where):
    scratch, environment = where
    done = heimdall(environment, "run", config_of(scratch, 0, fails=(0,)), "--plain")
    assert done.returncode == 0, done.stdout
    (entry,) = entries(scratch)
    assert (entry["code"], entry["detached"], entry["log"]) == (0, False, None)


def at_a_terminal(environment, *args):
    """heimdall on a pseudo-terminal: (pid, master fd, the text so far getter)."""
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(WORK)
        os.execve(str(HEIMDALL), [str(HEIMDALL), *map(str, args)], {**environment, "TERM": "xterm"})   # rich draws its live view
    seen = []

    def read(wait=0.2) -> str:
        while select.select([master], [], [], wait)[0]:
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            seen.append(data.decode("utf-8", "replace"))
            wait = 0.05
        return "".join(seen)
    return pid, master, read


def test_d_leaves_a_live_run_running(where):
    scratch, environment = where
    pid, master, read = at_a_terminal(environment, "run", config_of(scratch, 30))
    entry = wait_until(lambda: entries(scratch) and entries(scratch)[0])
    wait_until(lambda: "leave it running" in read())
    os.write(master, b"d")
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0 and "left running" in read()
    os.close(master)
    worker = entries(scratch)[0]["pid"]
    os.kill(worker, 0)                                            # it goes on
    assert heimdall(environment, "stop", "--pid", worker).returncode == 0


def test_ctrl_c_at_a_live_run_stops_its_worker(where):
    scratch, environment = where
    pid, master, read = at_a_terminal(environment, "run", config_of(scratch, 30))
    wait_until(lambda: "leave it running" in read())
    os.write(master, b"\x03")                                     # the line discipline: SIGINT to the client
    _, status = os.waitpid(pid, 0)
    read()
    os.close(master)
    assert os.waitstatus_to_exitcode(status) == 6
    (entry,) = entries(scratch)
    assert entry["code"] == 6 and entry["verdict"] == "stopped"
