"""Detachable runs (task L): the Ctrl-C ladder and SIGHUP (V181); the worker, --detach, stop and the watch keys
(V183) are added as they are built."""

from __future__ import annotations

import os
import signal
import time
from types import SimpleNamespace
import pytest

from runner import cli, execute


@pytest.fixture
def handlers():
    """The signal handlers a test changes, put back after it."""
    kept = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    yield
    for signum, handler in kept.items():
        signal.signal(signum, handler)


def _signalled(signum):
    os.kill(os.getpid(), signum)
    time.sleep(0.05)                                    # the handler runs between bytecodes


def test_the_first_signal_stops_cleanly_the_second_hard(handlers, monkeypatch):
    """V181: Ctrl-C, SIGTERM or SIGHUP: the first asks the points to end cleanly, the second for a hard stop (the
    tools killed at once); SIGHUP (the terminal gone) also sends the output to /dev/null."""
    quiet = []
    monkeypatch.setattr(cli, "_quiet", lambda: quiet.append(True))
    stopper = execute.Stopper()
    previous = cli.catch_signals(stopper)
    assert set(previous) == {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
    _signalled(signal.SIGTERM)
    assert stopper.requested and not stopper.hard
    _signalled(signal.SIGHUP)
    assert stopper.hard and quiet == [True]


def test_an_ignored_sighup_stays_ignored(handlers):
    """nohup heimdall run …: the run began with SIGHUP ignored, and a closed terminal does not stop it."""
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    stopper = execute.Stopper()
    assert signal.SIGHUP not in cli.catch_signals(stopper)
    _signalled(signal.SIGHUP)
    assert not stopper.requested and signal.getsignal(signal.SIGHUP) is signal.SIG_IGN


def test_ctrl_c_before_a_run_catches_it_exits_6(monkeypatch, capsys):
    """V181: a KeyboardInterrupt while a command plans (before the run's own handler) is a stop, not a traceback."""
    def interrupted(args):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "cmd_status", interrupted)
    assert cli.main(["status"]) == 6
    assert "stopped" in capsys.readouterr().err


def test_the_command_line_is_kept_as_typed():
    """V181: what the user typed, --plain included: a worker's own command line."""
    args = cli.parse(["run", "jets", "--plain", "pdf", "--points", "1"])
    assert args.argv == ["run", "jets", "--plain", "pdf", "--points", "1"] and args.plain


# ── the worker, --detach, stop, the keys (V183) ──────────────────────────────────────────────────

import subprocess
import sys
from pathlib import Path

from runner import house, runs, watch
from runner.errors import HeimdallError

FRAMEWORK = Path(__file__).resolve().parents[2] / "framework"
#: A worker of the real type: a process with a real Hub, which ends its run on SIGINT (exit 6), as a run does.
FAKE = r"""
import os, signal, sys, time
sys.path.insert(0, sys.argv[1])
from runner.events import Hub
hub = Hub({"config": sys.argv[2], "configurations": ["one"], "id": None, "work": sys.argv[3]})
asked = []
signal.signal(signal.SIGINT, lambda s, f: asked.append(s))
stamp = lambda **e: {"v": 1, "point": "", "tool": "", "t": time.time(), **e}
hub.event(stamp(k="run", state="started", points=1, title="fake run"))
print("ready", flush=True)
until = time.monotonic() + 60
while not asked and time.monotonic() < until:
    time.sleep(0.05)
hub.event(stamp(k="run", state="finished", verdict="stopped"))
hub.close()
sys.exit(6)
"""


@pytest.fixture
def fake(tmp_path):
    """Start fake workers; each is killed if a test leaves it running."""
    started = []

    def start(config="/w/configs/P/a.toml", work="/w"):
        script = tmp_path / "fake.py"
        script.write_text(FAKE, encoding="utf-8")
        proc = subprocess.Popen([sys.executable, str(script), str(FRAMEWORK), config, work], stdout=subprocess.PIPE,
                                text=True, encoding="utf-8")
        assert proc.stdout.readline().strip() == "ready"
        started.append(proc)
        return proc
    yield start
    for proc in started:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


class Tty:
    def __init__(self, tty=True, fd=0):
        self._tty, self._fd = tty, fd

    def isatty(self):
        return self._tty

    def fileno(self):
        return self._fd


def test_a_live_run_is_a_terminal_in_its_foreground(monkeypatch):
    """V183: a worker is started only for a run at a terminal, in its foreground, not --plain, not a worker, not
    in a Slurm job, and not with HEIMDALL_DETACH=never."""
    monkeypatch.setattr(os, "tcgetpgrp", lambda fd: os.getpgrp())
    plain = SimpleNamespace(plain=False, worker=None)
    assert cli.live(plain, Tty(), Tty(), {})
    assert not cli.live(plain, Tty(False), Tty(), {}) and not cli.live(plain, Tty(), Tty(False), {})
    assert not cli.live(SimpleNamespace(plain=True, worker=None), Tty(), Tty(), {})
    assert not cli.live(SimpleNamespace(plain=False, worker="x"), Tty(), Tty(), {})
    for environ in ({"HEIMDALL_DETACH": "never"}, {"SLURM_JOB_ID": "1"}, {runs.CLUSTER_VAR: "s"}):
        assert not cli.live(plain, Tty(), Tty(), environ)
    monkeypatch.setattr(os, "tcgetpgrp", lambda fd: os.getpgrp() + 1)            # `heimdall run … &`
    assert not cli.live(plain, Tty(), Tty(), {})


def test_a_worker_is_the_command_again_in_a_session_of_its_own(monkeypatch, tmp_path):
    seen = {}

    class Popen:
        def __init__(self, argv, **kwargs):
            seen.update(argv=argv, **kwargs)
    monkeypatch.setattr(runs.subprocess, "Popen", Popen)
    runs.spawn(["run", "Demo/jets", "--detach"], "ID", tmp_path / "ID.log")
    assert seen["argv"][:4] == [sys.executable, "-X", "utf8", "-u"] and seen["argv"][4].endswith("framework/bin/run")
    assert seen["argv"][5:] == ["run", "Demo/jets", "--detach", "--worker", "ID"]
    assert seen["start_new_session"] and seen["stdin"] is subprocess.DEVNULL and seen["close_fds"]


def test_detach_refuses_what_runs_nothing(capsys):
    for extra in (["--plan"], ["--why"], ["--show-config"], ["--only", "plot"]):
        assert cli.main(["run", "Demo/jets", "single", "--detach", *extra]) == 2
        assert "--detach starts a job in the background" in capsys.readouterr().err


def test_the_worker_flag_is_hidden():
    from runner import docs
    assert "--worker" not in cli.parser()._subparsers._group_actions[0].choices["run"].format_help()
    assert "--worker" not in docs.commands() and "==SUPPRESS==" not in docs.commands()


def test_stop_finds_one_of_your_runs_and_waits_for_it(fake, capsys):
    proc = fake()
    assert cli.main(["stop", "--pid", str(proc.pid)]) == 0
    assert proc.wait(10) == 6
    out = capsys.readouterr().out
    assert f"stopping pid {proc.pid}" in out and "it has ended" in out


def test_stop_refuses_none_several_and_another_namespace(fake, monkeypatch, capsys):
    """Named by neither config nor pid, stop looks only at this work dir's runs: never at another work dir's (a
    study's run of hours on the same machine)."""
    from runner.paths import work_root
    assert cli.main(["stop", "--pid", "1"]) == 2 and "no running job to stop" in capsys.readouterr().err
    elsewhere = fake()
    assert cli.main(["stop"]) == 2 and "no running job to stop" in capsys.readouterr().err and elsewhere.poll() is None
    here = str(work_root())
    one, two = fake(config=f"{here}/configs/P/a.toml", work=here), fake(config=f"{here}/configs/P/a.toml", work=here)
    assert cli.main(["stop"]) == 2
    err = capsys.readouterr().err
    assert "2 jobs match" in err and f"pid {one.pid}" in err and f"pid {two.pid}" in err and f"pid {elsewhere.pid}" not in err
    monkeypatch.setattr("runner.events.namespace", lambda kind: "pid:[1]")
    assert cli.main(["stop", "--pid", str(one.pid)]) == 2 and "another PID namespace" in capsys.readouterr().err
    assert one.poll() is None


def test_follow_takes_keys_from_a_pipe(fake):
    """d returns "detached"; a Ctrl-C byte calls on_interrupt; the stream's end returns "ended"."""
    proc = fake()
    read, write = os.pipe()
    os.write(write, b"xd")
    pressed = []
    got = watch.follow(watch.socket_of(proc.pid), plain=True, keys=read,
                       on_key=lambda k, shown: pressed.append(k) or ("detached" if k == "d" else None), proc=proc)
    assert got == "detached" and pressed == ["x", "d"] and proc.poll() is None
    asked = []
    os.write(write, b"\x03")
    got = watch.follow(watch.socket_of(proc.pid), plain=True, keys=read, proc=proc,
                       on_interrupt=lambda shown: asked.append(True) or os.kill(proc.pid, signal.SIGINT))
    assert got == "ended" and asked == [True] and proc.wait(10) == 6
    os.close(read)
    os.close(write)


@pytest.fixture
def keys(monkeypatch):
    """`heimdall watch` as on a terminal, its keys from a pipe: write them to the fd it gives."""
    read, write = os.pipe()

    class Keys:
        def __init__(self, fd):
            self.fd = read

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None
    monkeypatch.setattr(cli, "live", lambda args, *a, **k: True)
    monkeypatch.setattr(watch, "Keys", Keys)
    yield write
    os.close(read)
    os.close(write)


@pytest.fixture
def interrupts(monkeypatch):
    """The SIGINTs this process sends (to the fake run), each still sent."""
    sent, real = [], os.kill

    def kill(pid, signum):
        if signum == signal.SIGINT:
            sent.append(pid)
        real(pid, signum)
    monkeypatch.setattr(os, "kill", kill)
    return sent


def test_watch_d_and_ctrl_c_detach_and_q_stops_the_run(fake, keys):
    """V183: in `heimdall watch`, d and Ctrl-C leave; q asks the run to stop cleanly."""
    proc = fake()
    os.write(keys, b"d")
    assert cli.main(["watch", "--pid", str(proc.pid), "--plain"]) == 0 and proc.poll() is None
    os.write(keys, b"\x03")
    assert cli.main(["watch", "--pid", str(proc.pid), "--plain"]) == 0 and proc.poll() is None
    os.write(keys, b"q")
    assert cli.main(["watch", "--pid", str(proc.pid), "--plain"]) == 0 and proc.wait(10) == 6


def test_watch_a_real_sigint_detaches(fake, keys):
    """Ctrl-C at the watching terminal is a SIGINT to `heimdall watch` itself: it leaves, the run goes on."""
    import threading
    proc = fake()
    timer = threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGINT))
    timer.start()
    try:
        assert cli.main(["watch", "--pid", str(proc.pid), "--plain"]) == 0
    finally:
        timer.cancel()
    assert proc.poll() is None


def test_watch_the_old_keys_s_and_y_stop_nothing(fake, keys, interrupts):
    proc = fake()
    os.write(keys, b"syd")
    assert cli.main(["watch", "--pid", str(proc.pid), "--plain"]) == 0 and proc.poll() is None and interrupts == []


def test_watch_a_second_q_is_no_hard_stop(fake, keys, interrupts, capsys):
    """The first q stops the run cleanly; a second sends nothing, and names the hard stop's command."""
    proc = fake()
    os.write(keys, b"qqd")
    assert cli.main(["watch", "--pid", str(proc.pid), "--plain"]) == 0 and proc.wait(10) == 6
    assert interrupts == [proc.pid]
    assert f"already stopping; heimdall stop --pid {proc.pid} asks again: a hard stop" in capsys.readouterr().out


def test_watch_function_and_arrow_keys_are_no_letters(fake, keys, interrupts):
    """F2 (ESC O Q), an arrow (ESC [ A), F5 (ESC [ 1 5 ~), the Linux console's F2 (ESC [ [ B), Alt-q: no q among
    them stops the run; the d after them leaves."""
    proc = fake()
    os.write(keys, b"\x1bOQ\x1b[A\x1b[15~\x1b[[B\x1bqd")
    assert cli.main(["watch", "--pid", str(proc.pid), "--plain"]) == 0 and proc.poll() is None and interrupts == []


def test_watch_q_refuses_to_signal_another_pid_namespace(fake, keys, interrupts, monkeypatch, capsys):
    monkeypatch.setattr("runner.events.namespace", lambda kind: "pid:[another]")
    proc = fake()
    os.write(keys, b"qd")
    assert cli.main(["watch", "--pid", str(proc.pid), "--plain"]) == 0 and proc.poll() is None and interrupts == []
    assert "not stopped: its process is another PID namespace's" in capsys.readouterr().out


def test_keys_set_cbreak_and_put_the_terminal_back():
    import termios
    master, slave = os.openpty()
    try:
        before = termios.tcgetattr(slave)
        with watch.Keys(slave):
            mode = termios.tcgetattr(slave)
            assert not mode[3] & termios.ICANON and not mode[3] & termios.ECHO and mode[3] & termios.ISIG
            assert mode[1] & termios.OPOST == before[1] & termios.OPOST
        assert termios.tcgetattr(slave) == before
    finally:
        os.close(master)
        os.close(slave)


def test_watch_with_no_run_names_the_last_one(capsys):
    run_id = runs.new_id()
    runs.begin(run_id, {"config": "/w/configs/P/a.toml", "configurations": ["one"], "log": "/l/a.log"})
    runs.finish(run_id, 0)
    assert cli.main(["watch", "--pid", "1"]) == 2
    err = capsys.readouterr().err
    assert "no running job to watch with pid 1" in err and run_id in err and "/l/a.log" in err
