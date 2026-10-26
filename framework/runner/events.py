"""The event stream: what a run says while it runs, and who hears it (rank 1).

docs/06_Internals.md §10, audit 1 B3 (V72). The executor, the stages and the CLI emit **events** onto
one `Bus`; each is a dict with the stream's version `v`, the point and tool it is about (`""` for the run),
the time `t`, and its kind `k`:

    run    state = started (points, title, header) | finished (verdict)
    point  state = started (index, stage) | done | stopped | failed (cause, msg, res) | skipped
    tool   state = started                     exit   code, seconds, error
    phase, progress, xsec, log                  a tool's own status (src/Status.hh, or its filters)
    line   a tool's latest output line (at most twice a second per tool)
    note   a line for the point's block        say    a line of the run's
    dropped  to one watcher, last: it fell too far behind and is cut off (V181)

Runtime state stays off disk (the user, 2026-10-03), but for the run registry and a worker's log (V182,
runs.py: the user, 2026-10-23). Who hears the bus:
* the view, always (watch.py);
* the **Hub**, while the process lives: an abstract Unix socket `@hep-watch-<pid>` (no file, no path
  limit) on Linux, which `heimdall watch` finds in /proc/net/unix; elsewhere (macOS has neither) a socket
  file <tmp>/hep-watch/hep-watch-<pid>, removed when the process ends. The watcher gets a greeting, the current run's events so far
  (a tool's progress only as its latest), then every event live. A sweep of runs is one process, so
  the stream follows from run to run by itself. Only this user's processes may connect (V181:
  SO_PEERCRED on Linux, the 0700 folder elsewhere); when the run ends, every watcher gets its last
  events before the stream ends;
* the **Journal**, only with `--journal`: the same events in records/…/status.jsonl, appended run after run,
  for replay (`heimdall watch --file`) and tests;
* the **RunLog**, always (V202): records/…/run.jsonl, the run's own account, appended run after run: every event
  but a tool's latest line (`line`), and a tool's progress at most once a minute. `heimdall log RECORD` prints it
  as the plain view would; `heimdall watch --file` follows it.

A subscriber is called on the emitting thread and must not block; the Hub queues for each client and
drops a client that stops reading (it gets a `dropped` event, then the end). In a sweep of runs, each run emits through a `RunBus`, which adds
`run` (its configuration's key) to every event, since a pipelined sweep's runs overlap (V75).
"""

from __future__ import annotations

import errno
import json
import os
import queue
import socket
import struct
import sys
import tempfile
import threading
import time
from pathlib import Path

VERSION = 1
PREFIX = "hep-watch-"                     # the socket's name: PREFIX + pid
#: Abstract sockets are Linux's; elsewhere the sockets are files in one folder (a short path: 104 bytes on macOS).
ABSTRACT = sys.platform.startswith("linux")
SOCKETS = Path(tempfile.gettempdir()) / "hep-watch"


def address(name: str) -> str:
    """Where the watch socket `name` is: an abstract name on Linux, a file elsewhere."""
    return "\0" + name if ABSTRACT else str(SOCKETS / name)


def pid_of(name: str) -> int | None:
    """The pid a watch socket's name carries: hep-watch-<pid>, or hep-watch-<pid>-<n> (V181)."""
    head = name[len(PREFIX):].split("-", 1)[0] if name.startswith(PREFIX) else ""
    return int(head) if head.isdigit() else None


def namespace(kind: str) -> str:
    """This process's Linux namespace of a kind ("pid", "net"), as /proc names it; "" elsewhere."""
    try:
        return os.readlink(f"/proc/self/ns/{kind}")
    except OSError:
        return ""


class Bus:
    """Stamps events and hands them to every subscriber, in order, under one lock."""

    def __init__(self):
        self._subscribers: list = []
        self._lock = threading.Lock()

    def subscribe(self, subscriber) -> None:
        """`subscriber(event)`, or an object with `event(event)`."""
        with self._lock:
            self._subscribers.append(getattr(subscriber, "event", subscriber))

    def unsubscribe(self, subscriber) -> None:
        with self._lock:
            target = getattr(subscriber, "event", subscriber)
            self._subscribers = [s for s in self._subscribers if s != target]

    def emit(self, point: str, tool: str, message: dict) -> dict:
        event = {"v": VERSION, "point": point, "tool": tool, "t": round(time.time(), 3), **message}
        with self._lock:
            for subscriber in self._subscribers:
                subscriber(event)
        return event

    def say(self, text: str) -> None:
        self.emit("", "", {"k": "say", "msg": text})


class RunBus:
    """One run's voice on a shared bus (V75): every event it emits says which run it is of."""

    def __init__(self, bus: Bus, run: str):
        self.bus, self.run = bus, run

    def emit(self, point: str, tool: str, message: dict) -> dict:
        return self.bus.emit(point, tool, {**message, "run": self.run})

    def say(self, text: str) -> None:
        self.emit("", "", {"k": "say", "msg": text})

    def subscribe(self, subscriber) -> None:
        self.bus.subscribe(subscriber)

    def unsubscribe(self, subscriber) -> None:
        self.bus.unsubscribe(subscriber)


class Journal:
    """--journal: every event of one run in its status.jsonl, appended to what earlier runs wrote (V202). With
    `run`, only that run's events (a pipelined sweep's runs share one bus, V75)."""

    def __init__(self, path: Path, run: str | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.run = path, run
        self.handle = open(path, "a", encoding="utf-8")

    def event(self, event: dict) -> None:
        if self.run is not None and event.get("run") != self.run:
            return
        self.handle.write(json.dumps(event) + "\n")
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()


class RunLog:
    """records/…/run.jsonl (V202): a run's own account, always written, appended run after run: every event of the
    run (with `run`, that run's alone) but its tools' latest lines, and a tool's progress at most once every
    PROGRESS seconds. A write that fails is passed over: the log never stops a run."""

    PROGRESS = 60.0

    def __init__(self, path: Path, run: str | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.run = path, run
        self.handle = open(path, "a", encoding="utf-8")
        self._last: dict[tuple, float] = {}

    def event(self, event: dict) -> None:
        if self.run is not None and event.get("run") != self.run:
            return
        kind = event.get("k")
        if kind == "line":
            return
        if kind == "progress":
            key, at = (event.get("point", ""), event.get("tool", "")), event.get("t", time.time())
            if at - self._last.get(key, float("-inf")) < self.PROGRESS:
                return
            self._last[key] = at
        try:
            self.handle.write(json.dumps(event, default=str) + "\n")
            self.handle.flush()
        except (OSError, ValueError):
            pass

    def close(self) -> None:
        self.handle.close()


def last_run(path: Path) -> tuple[int, float]:
    """Where an appended events file's last run begins: the byte offset of its last `run started` and when that
    run started; (0, 0.0) when there is none."""
    offset, found = 0, (0, 0.0)
    with open(path, "rb") as handle:
        for line in handle:
            if b'"k": "run"' in line and b'"started"' in line:
                try:
                    event = json.loads(line)
                except ValueError:
                    event = {}
                if event.get("k") == "run" and event.get("state") == "started":
                    found = (offset, float(event.get("t", 0.0)))
            offset += len(line)
    return found


class Hub:
    """The watch socket of this process (V72): a greeting, the current run's events so far, then the live
    events, to every client of this user that connects. A client that falls 10,000 events behind is
    dropped, and told so (V181). The greeting says who and where: pid, uid, host, its PID namespace and
    its address, and what the CLI adds (config, run, configurations; the registry's id, log, work dir)."""

    def __init__(self, greeting: dict, name: str | None = None, *, depth: int = 10000):
        self._depth = depth
        self._kept: list[dict] = []                     # the current run's events …
        self._latest: dict[tuple, dict] = {}            # … with a tool's progress as its latest only
        self._clients: list[queue.Queue] = []
        self._dropped: set[int] = set()                 # ids of the clients cut off, still being drained
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if not ABSTRACT:
            SOCKETS.mkdir(mode=0o700, exist_ok=True)
        self.name = self._bind(name)
        self.greeting = {"k": "hello", "v": VERSION, "pid": os.getpid(), "started": round(time.time(), 3),
                         "uid": os.getuid(), "host": socket.gethostname(), "pidns": namespace("pid"),
                         "address": address(self.name), **greeting}
        self._server.listen(8)
        self._closed = False
        threading.Thread(target=self._accept, name="hep-watch-hub", daemon=True).start()

    def _bind(self, name: str | None) -> str:
        """Its name: hep-watch-<pid>, or with a suffix when another PID namespace's process of the same pid
        holds that one (two containers sharing the network, V181)."""
        names = [name] if name else [f"{PREFIX}{os.getpid()}"] + [f"{PREFIX}{os.getpid()}-{n}" for n in range(1, 10)]
        for candidate in names:
            if not ABSTRACT:
                Path(address(candidate)).unlink(missing_ok=True)    # a dead process's, with this pid
            try:
                self._server.bind(address(candidate))
                return candidate
            except OSError as error:
                if error.errno != errno.EADDRINUSE or candidate == names[-1]:
                    raise
        raise AssertionError("unreachable")

    def event(self, event: dict) -> None:
        with self._lock:
            if event.get("k") == "run" and event.get("state") == "started" and not event.get("run"):
                self._kept, self._latest = [], {}             # a single run: the new run is all a watcher needs
            if event.get("k") in ("progress", "line"):
                self._latest[(event["point"], event["tool"], event["k"])] = event
            else:
                self._kept.append(event)
            for client in list(self._clients):
                try:
                    client.put_nowait(event)
                except queue.Full:                    # it stopped reading: cut off, told when drained
                    self._clients.remove(client)
                    self._dropped.add(id(client))

    def _accept(self) -> None:
        while not self._closed:
            try:
                connection, _ = self._server.accept()
            except OSError:
                return
            if not _ours(connection):                     # another user's process (V181)
                connection.close()
                continue
            with self._lock:
                backlog = [self.greeting, *self._kept, *self._latest.values()]
                client: queue.Queue = queue.Queue(maxsize=self._depth)
                self._clients.append(client)
                thread = threading.Thread(target=self._serve, args=(connection, backlog, client), daemon=True)
                self._threads = [t for t in self._threads if t.is_alive()] + [thread]
            thread.start()

    def _serve(self, connection: socket.socket, backlog: list, client: queue.Queue) -> None:
        try:
            with connection:
                for event in backlog:
                    connection.sendall((json.dumps(event) + "\n").encode())
                while True:
                    try:
                        event = client.get(timeout=0.5)
                    except queue.Empty:
                        if id(client) in self._dropped:   # drained after being cut off: say so, then end
                            connection.sendall((json.dumps({"k": "dropped", "v": VERSION, "t": round(time.time(), 3)})
                                                + "\n").encode())
                            return
                        continue
                    if event is None:
                        return
                    connection.sendall((json.dumps(event) + "\n").encode())
        except OSError:
            pass
        finally:
            with self._lock:
                if client in self._clients:
                    self._clients.remove(client)
                self._dropped.discard(id(client))

    def close(self, linger: float = 2.0) -> None:
        """The process is ending: every client gets the end of the stream, after the events it has not been
        sent yet (at most `linger` seconds for all of them, V181)."""
        self._closed = True
        with self._lock:
            for client in self._clients:
                try:
                    client.put_nowait(None)
                except queue.Full:
                    self._dropped.add(id(client))
            threads = list(self._threads)
        deadline = time.monotonic() + linger
        for thread in threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        try:                                            # shutdown wakes the accept(); close alone does not
            self._server.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._server.close()
        except OSError:
            pass
        if not ABSTRACT:
            Path(address(self.name)).unlink(missing_ok=True)


def _ours(connection: socket.socket) -> bool:
    """Whether the connecting process is this user's (SO_PEERCRED, Linux); elsewhere the sockets' 0700
    folder keeps others out."""
    if not hasattr(socket, "SO_PEERCRED"):
        return True
    try:
        _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
    except OSError:
        return False
    return uid == os.getuid()


def hubs() -> list[str]:
    """The watch sockets on this machine: their names, from /proc/net/unix (Linux) or the sockets' folder."""
    if not ABSTRACT:
        found = []
        for path in sorted(SOCKETS.glob(PREFIX + "*")):
            pid = pid_of(path.name)
            try:
                if pid is not None:
                    os.kill(pid, 0)
            except ProcessLookupError:
                path.unlink(missing_ok=True)                # its process is gone
                continue
            except PermissionError:                         # another user's process
                pass
            found.append(path.name)
        return found
    found = []
    try:
        with open("/proc/net/unix", encoding="utf-8", errors="replace") as table:
            for line in table:
                path = line.split()[-1] if line.split() else ""
                if path.startswith("@" + PREFIX) and path[1:] not in found:
                    found.append(path[1:])
    except OSError:
        pass
    return found


def open_stream(where: str, timeout: float = 2.0) -> socket.socket:
    """A connected watch socket, by its name (hep-watch-<pid>) or its address (a greeting's, an entry's: the
    one way to a macOS socket file under another session's $TMPDIR). Blocking once connected."""
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(where if where.startswith(("\0", "/")) else address(where))
    except OSError:
        client.close()
        raise
    client.settimeout(None)
    return client


class Lines:
    """Newline-delimited JSON, decoded as the bytes come: feed() returns the events complete so far."""

    def __init__(self):
        self._buffer = b""

    def feed(self, data: bytes) -> list[dict]:
        self._buffer += data
        *complete, self._buffer = self._buffer.split(b"\n")
        out = []
        for line in complete:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out


def connect(name: str, timeout: float = 2.0):
    """A watch socket's events, as they come; the first is its greeting. Ends when the run's process does."""
    with open_stream(name, timeout) as client:
        lines = Lines()
        while True:
            data = client.recv(65536)
            if not data:
                return
            yield from lines.feed(data)


def greeting(name: str, timeout: float = 1.0) -> dict | None:
    """A watch socket's greeting, or None if it does not answer (in `timeout` seconds, the reading too)."""
    try:
        with open_stream(name, timeout) as client:
            client.settimeout(timeout)
            lines, got = Lines(), []
            while not got:
                data = client.recv(65536)
                if not data:
                    return None
                got = lines.feed(data)
            return got[0] if got[0].get("k") == "hello" else None
    except OSError:
        return None
