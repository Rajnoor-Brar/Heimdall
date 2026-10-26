"""Status: the fd protocol, the filter rules, the event bus and its listeners, and `heimdall watch` (V72)."""

from __future__ import annotations

import io
import json
import os
import time

import pytest

from runner.events import Bus, Hub, Journal, connect, greeting, hubs
from runner.status import Reader, ToolState
from runner.watch import PlainView, follow_events, follow_file

RIVET_RULES = [
    {"match": r"^Event (?P<done>\d+) \(", "emit": "progress"},
    {"match": r"^Reading events from", "emit": "phase", "phase": "analysing"},
    {"match": r"WARN .*unvalidated", "emit": "ignore"},
    {"match": r"\bWARN\b", "emit": "warn"},
    {"match": r"^Broken (?P<done>x)", "emit": "progress"},        # a rule whose group is not a number
]


def heard(bus: Bus) -> list[dict]:
    events: list[dict] = []
    bus.subscribe(events.append)
    return events


def test_filter_rules_turn_lines_into_status():
    state = ToolState("p", "rivet")
    reader = Reader(state, fd=None, out=None, rules=RIVET_RULES, bus=None)
    for line in ("Reading events from 'x'", "Rivet: WARN Analysis 'a' is unvalidated", "Event 100 (0:00:01)"):
        reader.output(line)
    assert (state.phase, state.done, state.warning) == ("analysing", 100, "")
    reader.output("Rivet: WARN something real")
    assert state.warning.endswith("something real") and state.done == 100
    reader.output("Broken x")                                           # a bad rule never raises
    assert state.last_line == "Broken x"


SHERPA_LINES = [                                                   # as Sherpa 3.0.5 prints them (L31)
    "Initialization of framework underway ...",
    "Starting the calculation at 17:52:56. Lean back and enjoy ... .",
    "  Event 1 ( 0s elapsed / 0s left ) -> ETA: Tue Oct 20 06:18  ",
    "Event_Handler::GenerateStandardPerturbativeEvent(): Four momentum not conserved. Rejecting event.",
    "\x1b[34mDecay_Handler_Base::TreatInitialBlob\x1b[0m:(\x1b[32m\"Initial particle Delta(1232)- not onshell\"\x1b[0m)",
    "  Event 10000 ( 45.2s elapsed / 9035.1s left ) -> ETA: Tue Oct 21 14:03    XS = 42090.7 pb +- ( 92.1025 pb = 0 % )  ",
]


def test_sherpas_counter_gives_a_bar_a_rate_and_its_cross_section():
    """BATCH_MODE 23's one line per print (the folder's display arguments), its noise ignored, its colours out."""
    from runner import tools
    state = ToolState("p", "sherpa")
    reader = Reader(state, fd=None, out=None, rules=tools.folders()["sherpa"].filters, bus=None, total=10_000_000)
    reader.output(SHERPA_LINES[0])
    assert state.phase == "initialising"
    reader.output(SHERPA_LINES[1])
    assert state.phase == "integrating"
    for line in SHERPA_LINES[2:]:
        reader.output(line)
    assert (state.phase, state.done, state.total, state.warning, state.error) == ("generating", 10_000, 10_000_000, "", "")
    assert state.rate == pytest.approx(10_000 / 45.2) and state.xsec == (42090.7, 92.1025)
    assert "\x1b" not in "".join(text for _, text in reader.tail)


def test_sherpas_default_counter_is_read_too():
    """A card that overrides the display arguments: Sherpa's own two lines, redrawn in place (ESC[1A)."""
    from runner import tools
    state = ToolState("p", "sherpa")
    reader = Reader(state, fd=None, out=None, rules=tools.folders()["sherpa"].filters, bus=None, total=10_000_000)
    reader.output("  Event 1600000 ( 2h 58m 30s elapsed / 15h 37m 11s left ) -> ETA: Wed Oct 21 00:54  ")
    reader.output("  XS = 42090.7 pb +- ( 92.1025 pb = 0 % )  \x1b[1A")
    assert state.done == 1_600_000 and state.rate == pytest.approx(1_600_000 / 10710) and state.xsec == (42090.7, 92.1025)
    reader.output("Terminator_Object_Handler::HandleSignal: Signal (2) caught. ")
    assert state.error.startswith("Terminator_Object_Handler")


@pytest.mark.parametrize("text, seconds", [("45.2s", 45.2), ("1.23457e+06s", 1234570.0), ("17086", 17086.0),
                                           ("2h 58m 30s", 10710.0), ("1d 3h", 97200.0), ("0s", 0.0),
                                           ("0:00:01", 1.0), ("4min 2s", 242.0), ("soon", None), ("2h x", None)])
def test_durations_are_read_as_programs_print_them(text, seconds):
    from runner.status import seconds_of
    assert seconds_of(text) == seconds


def test_a_rate_is_measured_from_the_first_count_when_the_line_gives_none(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("runner.status.time.monotonic", lambda: now[0])
    state = ToolState("p", "rivet")
    reader = Reader(state, fd=None, out=None, rules=RIVET_RULES[:1], bus=None, total=1000)
    reader.output("Event 100 (0:00:01)")
    assert (state.done, state.total, state.rate) == (100, 1000, None)
    now[0] = 104.0
    reader.output("Event 500 (0:00:05)")
    assert state.rate == pytest.approx(100.0)


def test_a_tools_output_pipe_is_read_on_its_own_thread_with_unfinished_lines_waiting(scratch):
    read, write = os.pipe()
    state = ToolState("p", "rivet")
    reader = Reader(state, fd=None, out=read, rules=RIVET_RULES, bus=None, log=scratch / "rivet.log")
    os.write(write, b"Reading events from 'x'\nEvent 100 (0:00:01)\nEvent 2")
    os.write(write, b"00 (0:00:02)\r")                                 # \r: a progress counter's line
    os.close(write)
    reader.join()
    assert (state.phase, state.done) == ("analysing", 200)
    assert not (scratch / "rivet.log").exists()                          # nothing on disk until it ends (V201)
    reader.write_digest(scratch / "rivet.log", {"tag": "rivet"})
    assert (scratch / "rivet.log").read_text(encoding="utf-8").splitlines()[-1] == "Event 200 (0:00:02)"


def test_logs_keeps_every_line_as_it_comes(scratch):
    read, write = os.pipe()
    reader = Reader(ToolState("p", "rivet"), fd=None, out=read, rules=[], bus=None, log=scratch / "rivet.log", keep=True)
    os.write(write, b"one\ntwo\n")
    os.close(write)
    reader.join()
    assert (scratch / "rivet.log").read_text(encoding="utf-8") == "one\ntwo\n"


def test_the_fd_protocol_keeps_unknown_kinds_and_every_message_is_an_event(scratch):
    read, write = os.pipe()
    bus = Bus()
    events = heard(bus)
    journal = Journal(scratch / "status.jsonl")
    bus.subscribe(journal)
    state = ToolState("p", "pythia")
    reader = Reader(state, fd=read, out=None, rules=[], bus=bus)
    os.write(write, b'{"t": 1, "k": "phase", "phase": "generating"}\n{"t": 2, "k": "progress", "done": 5, '
                    b'"total": 10, "rate": 2.5}\n{"t": 3, "k": "novel", "x": 1}\nnot json\n{"t": 4, "k": "xs')
    os.write(write, b'ec", "value_pb": 7.0, "err_pb": 0.5, "final": true}\n')
    os.close(write)
    reader.join()
    assert (state.phase, state.done, state.total, state.rate) == ("generating", 5, 10, 2.5)
    assert state.xsec == (7.0, 0.5)
    journal.close()
    assert [e["k"] for e in events] == ["phase", "progress", "novel", "xsec"]
    assert all(e["v"] == 1 and e["point"] == "p" and e["tool"] == "pythia" for e in events)
    kinds = [json.loads(line)["k"] for line in (scratch / "status.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds == ["phase", "progress", "novel", "xsec"]


def run_events():
    return [
        {"point": "", "tool": "", "k": "run", "state": "started", "points": 1, "title": "watching new"},
        {"point": "a", "tool": "", "k": "point", "state": "started", "index": 1, "t": 100.0},
        {"point": "a", "tool": "pythia", "k": "tool", "state": "started"},
        {"point": "a", "tool": "pythia", "k": "progress", "done": 3, "total": 4},
        {"point": "a", "tool": "pythia", "k": "exit", "code": 0, "seconds": 1.5},
        {"point": "a", "tool": "", "k": "point", "state": "done", "t": 171.8, "res": "results/a"},
        {"point": "", "tool": "", "k": "say", "msg": "1 done, 0 failed, 0 skipped"},
        {"point": "", "tool": "", "k": "run", "state": "finished", "verdict": "1 done"},
    ]


def test_watch_follows_a_journal_and_stops_when_the_run_finishes(scratch, monkeypatch):
    journal = scratch / "status.jsonl"
    journal.write_text("".join(json.dumps(line) + "\n" for line in run_events()), encoding="utf-8")
    captured = io.StringIO()
    monkeypatch.setattr("runner.watch.view", lambda plain=False: PlainView(stream=captured))
    assert follow_file(journal, plain=True) == 0
    text = captured.getvalue()
    assert "watching new" in text and "── point 1/1: a ── ok after 1min 12s" in text and "1 done, 0 failed" in text
    assert "pythia: ok" not in text                                     # a tool that did its job says nothing


def test_the_watch_socket_sends_the_run_so_far_then_every_event_live(monkeypatch):
    """V72: no file on disk; a watcher that joins late gets the current run (a tool's progress as its
    latest only), then the rest as it happens, and the stream ends with the process's hub."""
    import threading
    bus = Bus()
    hub = Hub({"config": "c.toml", "configurations": ["one"]}, name=f"hep-watch-test-{os.getpid()}")
    bus.subscribe(hub)
    events = run_events()
    for event in events[:2]:
        bus.emit(event["point"], event["tool"], {k: v for k, v in event.items() if k not in ("point", "tool")})
    for done in range(1, 4):
        bus.emit("a", "pythia", {"k": "progress", "done": done, "total": 4})
    assert hub.name in hubs() and greeting(hub.name)["config"] == "c.toml"
    captured = io.StringIO()
    monkeypatch.setattr("runner.watch.view", lambda plain=False: PlainView(stream=captured))
    stream = connect(hub.name)
    hello, first, second, latest = next(stream), next(stream), next(stream), next(stream)
    assert hello["k"] == "hello" and (first["k"], second["k"]) == ("run", "point") and latest["done"] == 3
    rest = threading.Thread(target=follow_events, args=(stream,), kwargs={"plain": True})
    rest.start()
    for event in events[4:]:
        bus.emit(event["point"], event["tool"], {k: v for k, v in event.items() if k not in ("point", "tool")})
    hub.close()
    rest.join(5)
    assert not rest.is_alive() and "1 done, 0 failed" in captured.getvalue()


def _reader(sock, got: list):
    """Every event a raw watcher receives, until the end of its stream."""
    from runner.events import Lines
    lines = Lines()
    while True:
        data = sock.recv(65536)
        if not data:
            return
        got.extend(lines.feed(data))


def test_a_closing_hub_sends_every_watcher_its_last_events_first():
    """V181: close() waits for what each watcher has not been sent yet, so the verdict is never lost."""
    import threading
    from runner.events import open_stream
    hub = Hub({}, name=f"hep-watch-test-{os.getpid()}-close")
    sock, got = open_stream(hub.name), []
    reader = threading.Thread(target=_reader, args=(sock, got))
    reader.start()
    time.sleep(0.2)                                              # its backlog sent, it is a live client
    for n in range(5000):
        hub.event({"k": "progress", "point": "a", "tool": "t", "done": n})
    hub.event({"k": "run", "state": "finished", "verdict": "done", "point": "", "tool": ""})
    hub.close()
    reader.join(10)
    sock.close()
    assert not reader.is_alive() and got[0]["k"] == "hello" and got[-1]["k"] == "run" and len(got) == 5002


def test_a_watcher_that_falls_behind_is_told_and_cut_off():
    """V181: a client too far behind is dropped; once what it was queued is sent, it gets `dropped` and the
    end of its stream (it never hangs), while the run goes on."""
    import socket as socketmod
    from runner.events import open_stream
    hub = Hub({}, name=f"hep-watch-test-{os.getpid()}-slow", depth=5)
    sock = open_stream(hub.name)
    sock.setsockopt(socketmod.SOL_SOCKET, socketmod.SO_RCVBUF, 4096)
    time.sleep(0.2)
    for n in range(3000):                                        # nothing read: its socket and queue fill
        hub.event({"k": "line", "point": "a", "tool": "t", "line": "x" * 500, "n": n})
    got = []
    sock.settimeout(10)
    _reader(sock, got)
    sock.close()
    assert got[-1]["k"] == "dropped" and len(got) < 3001
    hub.event({"k": "say", "msg": "still running", "point": "", "tool": ""})   # the hub goes on
    assert greeting(hub.name)["k"] == "hello"
    hub.close()


def test_a_hub_names_itself_by_its_pid_and_says_who_it_is():
    """V181: hep-watch-<pid>, or with a suffix when that name is taken; the greeting carries uid, host, PID
    namespace and address, so watch, stop and runs can tell whose it is and reach it."""
    import socket as socketmod
    from runner.events import address, namespace, pid_of
    first = Hub({"config": "c.toml"})
    second = Hub({"config": "c.toml"})
    try:
        assert first.name == f"hep-watch-{os.getpid()}" and second.name == f"hep-watch-{os.getpid()}-1"
        assert pid_of(first.name) == pid_of(second.name) == os.getpid() and pid_of("hep-watch-x") is None
        hello = greeting(second.name)
        assert (hello["uid"], hello["host"], hello["pidns"]) == (os.getuid(), socketmod.gethostname(), namespace("pid"))
        assert hello["address"] == address(second.name) and second.name in hubs()
    finally:
        first.close()
        second.close()


def test_another_users_watcher_is_refused(monkeypatch):
    """V181: SO_PEERCRED: a connection from another uid is closed before it hears anything."""
    import socket as socketmod
    if not hasattr(socketmod, "SO_PEERCRED"):
        pytest.skip("SO_PEERCRED is Linux's; elsewhere the sockets' folder is the user's alone")
    hub = Hub({}, name=f"hep-watch-test-{os.getpid()}-peer")
    real = os.getuid()
    monkeypatch.setattr("runner.events.os.getuid", lambda: real + 1)
    try:
        assert greeting(hub.name) is None
    finally:
        monkeypatch.undo()
        hub.close()


def test_lines_are_decoded_as_the_bytes_come():
    from runner.events import Lines
    lines = Lines()
    assert lines.feed(b'{"k": "a"}\n{"k"') == [{"k": "a"}]
    assert lines.feed(b': "b"}\nnot json\n') == [{"k": "b"}] and lines.feed(b"") == []


def test_a_point_is_one_block_when_it_ends():
    """── point 2/4: NNPDF23lo ── ok after 1min 12s at <when>, a blank line, where the results are, a blank
    line (the user's layout, 2026-10-21)."""
    out = io.StringIO()
    view, bus = PlainView(stream=out), Bus()
    bus.subscribe(view)
    bus.emit("", "", {"k": "run", "state": "started", "points": 4})
    bus.emit("MSTW08lo", "", {"k": "point", "state": "skipped", "index": 1})
    bus.emit("NNPDF23lo", "", {"k": "point", "state": "started", "index": 2})
    bus.emit("NNPDF23lo", "pythia", {"k": "exit", "code": 0, "seconds": 71.6})
    bus.emit("NNPDF23lo", "sherpa:prepare", {"k": "exit", "code": 0, "seconds": 3.0})
    bus.emit("NNPDF23lo", "", {"k": "point", "state": "done", "res": "results/x/NNPDF23lo", "t": 1792591380.0})
    view.flush()                                                       # the view writes on its own thread (V32)
    lines = out.getvalue().splitlines()
    assert lines[0] == "── point 1/4: MSTW08lo: complete, skipped (--rerun to run it again)"
    assert lines[1].startswith("── point 2/4: NNPDF23lo ── ok after ")
    assert lines[1].endswith(" at " + time.strftime("%a %d %b %H:%M", time.localtime(1792591380.0)))
    assert lines[2:] == ["", "   sherpa:prepare: ok after 3.0s", "   done → results/x/NNPDF23lo", ""]
    bus.emit("NNPDF23lo", "", {"k": "point", "state": "started", "index": 2})
    bus.emit("NNPDF23lo", "rivet", {"k": "log", "level": "error", "msg": "boom"})
    bus.emit("NNPDF23lo", "rivet", {"k": "exit", "code": 1, "seconds": 2.0})
    bus.emit("NNPDF23lo", "", {"k": "point", "state": "failed", "cause": "rivet", "msg": "rivet exited 1"})
    view.end()
    tail = out.getvalue().splitlines()[6:]
    assert "── FAILED [rivet] after" in tail[0] and " at " in tail[0]
    assert tail[1:] == ["", "   rivet: exit 1 after 2.0s  (boom)", "   rivet exited 1", ""]


def test_a_terminal_that_stops_reading_never_stops_the_run():
    """V32: the supervisor calls the view from its poll loop. A stream nobody reads (a paused terminal
    tab, Ctrl-S) fills after 64 kB; the view's calls must still return at once, and end() must not
    wait on it for more than its timeout."""
    import os
    import time
    read_end, write_end = os.pipe()
    stream = os.fdopen(write_end, "w")
    view = PlainView(stream=stream)
    started = time.monotonic()
    for i in range(5000):                                            # ~1 MB: far past the pipe's buffer
        view.say(f"line {i:05d} " + "x" * 200)
    assert time.monotonic() - started < 1.0
    started = time.monotonic()
    view.end()                                                        # gives up after its timeout
    assert time.monotonic() - started < 5.0
    os.close(read_end)                                                # the writer thread gets EPIPE and stops


@pytest.mark.parametrize("seconds, shown", [(3.04, "3.0s"), (59.9, "59.9s"), (59.96, "1min 0s"), (71.8, "1min 12s"),
                                            (3599.6, "1h 0min 0s"), (10687.2, "2h 58min 7s")])
def test_durations_are_seconds_then_minutes_then_hours(seconds, shown):
    from runner.watch import duration
    assert duration(seconds) == shown


@pytest.mark.parametrize("seconds, shown", [(3.7, "00:03"), (72, "01:12"), (3599.9, "59:59"), (3600, "01:00:00"),
                                            (35237, "09:47:17"), (370929, "103:02:09"), (-1, "00:00")])
def test_a_running_clock_is_mm_ss_then_hh_mm_ss(seconds, shown):
    from runner.watch import clock
    assert clock(seconds) == shown


def test_the_live_view_puts_each_running_point_over_its_tools():
    """The point's heading and time so far (a finished block ends in a blank line), then its tools
    under it, their columns lined up across points; a blank line between two points; a tool's warning
    on a line of its own under its row, and the last line of a tool with no count yet."""
    pytest.importorskip("rich")
    import time
    from rich.console import Console
    from runner.watch import LiveView
    view, bus = LiveView(), Bus()
    bus.subscribe(view)
    try:
        bus.emit("", "", {"k": "run", "state": "started", "points": 4})
        for index, name in ((1, "a"), (2, "b")):
            bus.emit(name, "", {"k": "point", "state": "skipped", "index": index})
        for index, name in ((3, "MSTW08lo"), (4, "PDF4LHC21")):
            bus.emit(name, "", {"k": "point", "state": "started", "index": index})
        view.state.points[("", "PDF4LHC21")].started = time.time() - 35237   # (run, point): a run of its own
        bus.emit("MSTW08lo", "pythia", {"k": "phase", "phase": "init"})
        bus.emit("PDF4LHC21", "pythia", {"k": "phase", "phase": "generating"})
        bus.emit("PDF4LHC21", "pythia", {"k": "progress", "done": 1_700_000, "total": 10_000_000, "rate": 2812})
        bus.emit("PDF4LHC21", "rivet.12", {"k": "phase", "phase": "analysing"})
        bus.emit("PDF4LHC21", "rivet.12", {"k": "progress", "done": 1_700_000})
        bus.emit("PDF4LHC21", "rivet.12", {"k": "log", "level": "warn", "msg": "WARN Analysis 'x' is unvalidated"})
        bus.emit("MSTW08lo", "pythia", {"k": "line", "msg": "reading the PDF set"})
        out = io.StringIO()
        Console(file=out, width=120).print(view.render())
    finally:
        view.end()
    lines = [line.rstrip() for line in out.getvalue().splitlines()]
    assert lines[0].startswith("point 3/4: MSTW08lo · 00:0")
    assert lines[1].startswith("   pythia   init ") and lines[2] == "      ↳ reading the PDF set"
    assert lines[3] == "" and lines[4].startswith("point 4/4: PDF4LHC21 · 09:47:1")
    assert lines[5].startswith("   pythia   generating ") and lines[5].endswith("1.70M/10.00M 2,812/s 49:11")
    assert lines[6].startswith("   rivet.12 analysing  ") and lines[6].endswith("1.70M")
    assert lines[7] == "      ↳ WARN Analysis 'x' is unvalidated"
    assert lines[5].index("1.70M") == lines[6].index("1.70M") and lines[1].index("init") == lines[5].index("generating")
