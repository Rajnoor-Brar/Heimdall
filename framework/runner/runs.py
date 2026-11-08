"""The run registry (rank 1, V182): what runs on this machine now, and what ran in the last 30 days.

The user, 2026-10-23: "heimdall can keep track of runs and jobs being run in Himinbjorg". One small JSON file a
run (and a cluster submission), `<Himinbjorg>/runs/<id>.json` ($HEIMDALL_RUNS), beside a detached worker's log
`<id>.log`: who (host, pid, uid, user, its PID and network namespaces, the boot, the pid's start time), where
(the work dir, the checkout, the config, its configurations, the command line), when (started, finished),
how it ended (exit code, verdict) and the record folders it wrote. `heimdall runs` lists them; `heimdall
watch` and `heimdall stop` find a run's socket through them.

The one exception to "runtime state stays off disk" (V72): the user's ask. Each entry has one writer at a
time (the run's own process; its client only when the worker died by a signal), written whole through a
temporary file of its own and a rename. A Himinbjorg that cannot be written (an Apptainer image's) records
nothing, silently: every write is a no-op. Finished entries leave after KEEP_DAYS, their logs with them.

Own entries only (task L's decision): `entries` reads and `prune` removes this user's alone, so on a machine
root several accounts share, nobody lists or deletes another's. An entry's name is its id, and only a name of
`new_id`'s shape is read: what an entry file says never names a path (V191).
"""

from __future__ import annotations

import getpass
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .events import namespace as _namespace
from .paths import himinbjorg

DIR_VAR = "HEIMDALL_RUNS"
VERSION = 1
KEEP_DAYS = 30
#: A Heimdall cluster job's environment (V184): its submission is recorded, not each job.
CLUSTER_VAR = "HEIMDALL_CLUSTER_JOB"
#: What a run's exit code says, in a listing and in an entry; a pause also exits 6, its entry's state "paused".
VERDICTS = {0: "done", 1: "failed", 2: "not run", 6: "stopped"}
#: An entry's id, as new_id makes it: <YYYYmmdd-HHMMSS>-<host>-<4 hex>. Nothing else is read as one.
ID = re.compile(r"\d{8}-\d{6}-[A-Za-z0-9_-]+-[0-9a-f]{4}")
#: The id a detached run takes when it is given one: `heimdall runs --resume` names its new run so, and the
#: paused entry points at it (`resumed_by`).
ID_VAR = "HEIMDALL_RUN_ID"
#: The paused entry a resumed job resumes: marked `resumed_by` before it starts, and cleared again by its
#: worker when the job never runs (a config error: exit 2), so the pause stays live.
RESUMES_VAR = "HEIMDALL_RESUMES"


def folder() -> Path:
    """Where the entries are: $HEIMDALL_RUNS, else <Himinbjorg>/runs."""
    given = os.environ.get(DIR_VAR)
    return Path(given).expanduser() if given else himinbjorg() / "runs"


def host() -> str:
    return socket.gethostname().split(".")[0]


def new_id(now: float | None = None) -> str:
    """<YYYYmmdd-HHMMSS>-<host>-<4 hex>: sorted by when, unique on a shared Himinbjorg."""
    return f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}-{host()}-{secrets.token_hex(2)}"


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def started_at(pid: int) -> str:
    """A pid's start time in clock ticks since boot (Linux /proc/<pid>/stat, field 22): a pid reused by another
    process has another. "" where there is no /proc."""
    text = _read(f"/proc/{pid}/stat")
    fields = text[text.rfind(")") + 2:].split() if ")" in text else []
    return fields[19] if len(fields) > 19 else ""


def user() -> str:
    try:
        return getpass.getuser()
    except (KeyError, OSError):
        return str(os.getuid())


def here(pid: int | None = None) -> dict:
    """Who and where a process of this machine is."""
    pid = pid or os.getpid()
    return {"host": host(), "pid": pid, "uid": os.getuid(), "user": user(), "pidns": _namespace("pid"),
            "netns": _namespace("net"), "boot": _read("/proc/sys/kernel/random/boot_id"), "pstart": started_at(pid)}


def _write(path: Path, data: dict) -> bool:
    """One entry, whole: a temporary file of this process and thread, then a rename. False when it cannot be
    written (a read-only Himinbjorg)."""
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        temporary.replace(path)
        return True
    except OSError:
        temporary.unlink(missing_ok=True) if temporary.parent.is_dir() else None
        return False


def reserve(run_id: str, suffix: str) -> Path | None:
    """`<id><suffix>` created empty, only if it is not there (O_EXCL); None when it is, or cannot be."""
    path = folder() / f"{run_id}{suffix}"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))
        return path
    except OSError:
        return None


def _fallback() -> Path:
    """Where a worker's log goes when the registry cannot be written: <tmp>/heimdall-runs-<uid>/ (0700)."""
    return Path(tempfile.gettempdir()) / f"heimdall-runs-{os.getuid()}"


def log_file(run_id: str) -> Path:
    """A detached worker's log: in the registry, else (a read-only Himinbjorg) <tmp>/heimdall-runs-<uid>/."""
    reserved = reserve(run_id, ".log")
    if reserved is not None:
        return reserved
    _fallback().mkdir(mode=0o700, exist_ok=True)
    return _fallback() / f"{run_id}.log"


def log_of(run_id: str) -> Path | None:
    """The log a worker's parent opened for it (log_file): the registry's, else the fallback's; None when
    neither is there. What the worker names in its entry and its greeting."""
    for place in (folder() / f"{run_id}.log", _fallback() / f"{run_id}.log"):
        if place.is_file():
            return place
    return None


def entry(run_id: str) -> dict | None:
    try:
        return json.loads((folder() / f"{run_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def control_file(run_id: str) -> Path:
    """`<id>.control.json` beside the entry: what `heimdall runs -i N --jobs M` asks a running worker (the entry keeps its
    one writer, the run)."""
    return folder() / f"{run_id}.control.json"


def write_control(run_id: str, parallelism: int, by: int | None = None) -> bool:
    """The request, whole and atomically: `{"parallelism": M, "by": pid, "at": time}`. False when it cannot be written."""
    return _write(control_file(run_id), {"parallelism": parallelism, "by": by or os.getpid(), "at": round(time.time(), 3)})


def read_control(run_id: str) -> dict:
    """The request a worker was signalled for; ValueError (saying what is wrong) when it is missing, not JSON, or its
    `parallelism` is no whole number of at least 1."""
    try:
        data = json.loads(control_file(run_id).read_text(encoding="utf-8"))
    except OSError:
        raise ValueError(f"there is no {control_file(run_id).name}") from None
    except ValueError:
        raise ValueError(f"{control_file(run_id).name} is not JSON") from None
    count = data.get("parallelism") if isinstance(data, dict) else None
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError(f"{control_file(run_id).name} has no parallelism of at least 1 (it has {count!r})")
    return data


def begin(run_id: str, fields: dict) -> str | None:
    """A run begins: its entry written (this process's who and where, `fields` over them), the old ones pruned.
    The id, or None when nothing could be written."""
    if cluster_job() and fields.get("kind", "run") == "run":
        return None
    data = {"v": VERSION, "id": run_id, "kind": "run", **here(), "started": round(time.time(), 3), **fields}
    if not _write(folder() / f"{run_id}.json", data):
        return None
    prune()
    return run_id


def update(run_id: str | None, **fields) -> bool:
    """Fields over a run's entry (its record folders as they come, a cluster's state)."""
    if run_id is None or (got := entry(run_id)) is None:
        return False
    return _write(folder() / f"{run_id}.json", {**got, **fields})


def finish(run_id: str | None, code: int, verdict: str | None = None, state: str | None = None, **fields) -> bool:
    """A run ended: its exit code and verdict, when; `state` what it ended as when its code does not say it (a pause,
    "paused": exit 6 as a stop), its verdict too unless one is given."""
    return update(run_id, code=code, verdict=verdict or state or VERDICTS.get(code, f"exit {code}"),
                  finished=round(time.time(), 3), **({"state": state} if state else {}), **fields)


def _own(paths, mine: bool):
    """(path, entry) of each entry file: named by an id of new_id's shape, holding that id, and (`mine`) this
    user's, by the entry and by the file."""
    for path in paths:
        if not ID.fullmatch(path.stem):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            owner = path.stat().st_uid
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("id") != path.stem:
            continue
        if mine and (data.get("uid") != os.getuid() or owner != os.getuid()):
            continue
        yield path, data


def entries(now: float | None = None, mine: bool = True) -> list[dict]:
    """The entries, newest first, after pruning those KEEP_DAYS old: this user's (`mine`), else everyone's."""
    prune(now)
    found = [data for _, data in _own(sorted(folder().glob("*.json")) if folder().is_dir() else (), mine)]
    return sorted(found, key=lambda e: e.get("started", 0), reverse=True)


def prune(now: float | None = None) -> None:
    """This user's entries finished KEEP_DAYS ago (or begun KEEP_DAYS ago and never finished: a process
    killed), and their logs, `<id>.log` beside them; a log of this user's with no entry, by its age."""
    now = time.time() if now is None else now
    edge = now - KEEP_DAYS * 86400
    where = folder()
    if not where.is_dir():
        return
    try:
        for path, data in list(_own(where.glob("*.json"), mine=True)):
            if (data.get("finished") or data.get("started") or now) < edge:
                path.unlink(missing_ok=True)
                path.with_suffix(".log").unlink(missing_ok=True)
                control_file(path.stem).unlink(missing_ok=True)
        for log in where.glob("*.log"):
            info = log.stat()
            if info.st_uid == os.getuid() and not log.with_suffix(".json").exists() and info.st_mtime < edge:
                log.unlink(missing_ok=True)
    except OSError:
        pass


def ended(pid: int) -> bool:
    """Whether process `pid` has ended: gone, or a zombie its parent has not reaped yet."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    text = _read(f"/proc/{pid}/stat")
    return ")" in text and text[text.rfind(")") + 2:].split()[:1] == ["Z"]


def alive(data: dict) -> bool | None:
    """Whether an entry's process still runs: True, False, or None when this process cannot tell (another
    host, another PID namespace)."""
    me = here()
    if data.get("host") != me["host"]:
        return None
    if data.get("boot") and me["boot"] and data["boot"] != me["boot"]:
        return False                                    # the machine has restarted since
    if data.get("pidns") and me["pidns"] and data["pidns"] != me["pidns"]:
        return None
    pid = data.get("pid")
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:                             # another user's process: the pid reused, unless it started
        return bool(data.get("pstart")) and started_at(int(pid)) == data["pstart"]      # when the run's did
    except (TypeError, ValueError):
        return None
    return not data.get("pstart") or started_at(int(pid)) == data["pstart"]


def state(data: dict, live: dict | None = None) -> str:
    """What an entry says now: when it ended, its state ("paused") or else its verdict, and whether a pause was resumed
    or forgotten since; running; "lost" (its process is gone, it never said how it ended); or why this process
    cannot tell. `live`: pid → greeting of the sockets this process sees."""
    if data.get("kind") == "cluster":
        return data.get("verdict") or "submitted"
    if data.get("finished") is not None:
        ended = f"{data.get('state') or data.get('verdict') or VERDICTS.get(data.get('code'), 'ended')}"
        return f"{ended}, resumed" if data.get("resumed_by") else f"{ended}, forgotten" if data.get("forgotten") else ended
    running = alive(data)
    if running is False:
        return "lost"
    if data.get("queued") and running:                  # a waiting worker (cli.wait_turn): held when its predecessor was stopped
        return "held" if data.get("held") else "queued"
    if running is None:
        return f"on {data.get('host')}" if data.get("host") != host() else "in another PID namespace"
    if live is not None and data.get("pid") not in live and data.get("netns") != _namespace("net"):
        return "running (not reachable from here)"
    return "running"


#: A queued run's worker looks at its predecessor's entry this often, in seconds (cli.wait_turn).
QUEUE_POLL = 5.0


def queue_file(run_id: str) -> Path:
    """`<id>.queue.json` beside the entry: what `heimdall runs --dispatch` or `--forget` asks a queued run's waiting
    worker (cli.wait_turn reads it; the entry keeps its one writer)."""
    return folder() / f"{run_id}.queue.json"


def ask_queue(run_id: str, what: str) -> bool:
    """A queued run asked to start now ("dispatch") or to leave its queue ("forget"), whole and atomically."""
    return _write(queue_file(run_id), {"ask": what, "by": os.getpid(), "at": round(time.time(), 3)})


def queue_asked(run_id: str) -> str | None:
    """What a queued run was asked ("dispatch", "forget"), or None."""
    try:
        data = json.loads(queue_file(run_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data.get("ask") if isinstance(data, dict) and data.get("ask") in ("dispatch", "forget") else None


def queue_of(entries: list[dict], queue: str) -> list[dict]:
    """A queue's runs in their order: its head (no predecessor among them; the run the queue is named after, which
    may not say it), then each run queued to the one before. A run dispatched out of it heads a queue of its own,
    and those queued to it follow it there."""
    members = [e for e in entries if e.get("queue") == queue or (e.get("id") == queue and not e.get("queue"))]
    ids = {e.get("id") for e in members}
    after: dict[str, list[dict]] = {}
    for e in members:
        after.setdefault(e.get("queued_to") if e.get("queued_to") in ids else "", []).append(e)
    out, seen = [], set()

    def walk(at: str) -> None:
        for e in sorted(after.get(at, []), key=lambda e: (e.get("started") or 0, e.get("id", ""))):
            if e.get("id") not in seen:
                seen.add(e.get("id"))
                out.append(e)
                walk(e.get("id"))

    walk("")
    return out + [e for e in members if e.get("id") not in seen]


def paused(data: dict) -> bool:
    """Whether an entry is a pause still live: a run that ended paused, neither resumed nor forgotten since."""
    return data.get("kind", "run") == "run" and data.get("finished") is not None and data.get("state") == "paused" \
        and not data.get("resumed_by") and not data.get("forgotten")


def again(data: dict) -> list[str]:
    """A paused run's own command again, detached: its argv as typed, without a worker's `--worker <id>` and
    a `--detach`, then `--detach`; a `--rerun` becomes `--rerun-since <its start>`, so the points the paused job
    completed are not run again (one already resumed keeps its first start). [] when the entry holds no `heimdall
    run` command."""
    argv = [str(arg) for arg in data.get("argv") or []]
    if argv[:1] != ["run"]:
        return []
    out, skip = [], False
    since = any(arg == "--rerun-since" or arg.startswith("--rerun-since=") for arg in argv)
    for arg in argv:
        if skip:
            skip = False
        elif arg in ("--worker", "--queued-to"):             # a queue's place is not run again
            skip = True
        elif arg == "--rerun" and not since and data.get("started"):
            out += ["--rerun-since", repr(float(data["started"]))]
        elif not arg.startswith(("--worker=", "--queued-to=")) and arg != "--detach" and not (arg == "--rerun" and since):
            out.append(arg)
    return [*out, "--detach"]


def relaunch(command: list[str], cwd: str, env: dict) -> subprocess.CompletedProcess:
    """A paused run's command started again, from `cwd` with `env`, and waited for: as `--detach`, it returns
    once its run has started, saying so on this process's output."""
    return subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, check=False)


def spawn(argv: list[str], run_id: str, log: Path) -> subprocess.Popen:
    """A detached run's worker (V183): the command as typed, again, with --worker <id> (which a typed --detach
    gives way to), by this checkout's framework/bin/run and this Python, in a session of its own (no terminal:
    closing one does not end it), reading nothing, its output in `log`."""
    entry = Path(__file__).resolve().parents[1] / "bin" / "run"
    with open(log, "ab") as out:
        return subprocess.Popen([sys.executable, "-X", "utf8", "-u", str(entry), *argv, "--worker", run_id],
                                start_new_session=True, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                close_fds=True, preexec_fn=_pause_ignored)


def _pause_ignored() -> None:
    """In a worker before it runs: SIGUSR1 (a `p`) ignored until its own handler is in (cli.catch_pause),
    never its default death; an ignored signal stays ignored across exec, a handled one does not reach its tools."""
    signal.signal(signal.SIGUSR1, signal.SIG_IGN)
    signal.signal(signal.SIGUSR2, signal.SIG_IGN)               # a `--jobs` the same way (cli.catch_control)


def cluster_job() -> bool:
    """Whether this process is one of Heimdall's cluster jobs (V184): those are recorded by their submission."""
    return bool(os.environ.get(CLUSTER_VAR))


class Recorder:
    """A bus subscriber: the record folders a run wrote, each run's verdict and its points' counts (V202: done,
    failed, stopped, done with warnings), in memory, for its entry; and, while the run lives, its progress in the
    entry: the configuration points ended (done, failed, stopped or skipped) of those planned, and those running.
    Only a sweep's configuration points count, not its pre, post or combined stages (their events carry `stage`).
    The entry is kept in memory and written at most every EVERY seconds, and at each run's start and end; the
    run's own finish writes the last state (`progress`)."""

    #: Seconds between two writes of the progress: the bus waits on a subscriber.
    EVERY = 2.0

    def __init__(self, run_id: str | None = None, configuration_serials: dict | None = None,
                 configuration_labels: dict | None = None):
        self.run_id = run_id
        self.configuration_serials = dict(configuration_serials or {})
        self.configuration_labels = dict(configuration_labels or {})
        self.configuration_tags: dict[str, str] = {}         # a configuration → its folder's tag (V223)
        self.parallelism: int | None = None                 # points at once, as the latest run began (not in an identity)
        self.point_cores = 0                                # the most cores a point of any run keeps busy
        self.records: list[str] = []
        self.verdicts: dict[str, str] = {}
        self.tally = Tally()
        self.totals: dict[str, int] = {}                    # a run (its sweep key) → its points planned
        self.planned: set[str] = set()                      # the runs whose total was given up front (plan)
        self.ended: set[tuple[str, str]] = set()            # (run, point) of the points ended
        self.active: set[tuple[str, str]] = set()           # … and of those running
        self._kept: dict | None = None                      # the entry as last written
        self._written = 0.0                                 # when (time.monotonic)
        self._timer: threading.Timer | None = None
        self._closed = False
        self._lock = threading.Lock()

    def set_parallelism(self, count: int) -> None:
        """A live `--jobs`: the entry says it at once."""
        with self._lock:
            self.parallelism = count
        self._save(now=True)

    def plan(self, totals: dict[str, int]) -> None:
        """Each run's points planned, before the first starts (a sweep's key, "" for one run): the total is the
        whole command's from the start, not only of the runs begun so far."""
        with self._lock:
            self.totals.update(totals)
            self.planned.update(totals)
        self._save(now=True)

    def progress(self) -> dict:
        """The entry's progress fields: points ended, of the total (None until planned), and running now."""
        return {"points_completed": len(self.ended), "points_total": sum(self.totals.values()) if self.totals else None,
                "active_parallel_points": len(self.active),
                "points_failed": sum(len(r["failed"]) for r in self.tally.runs.values()),
                **({"parallelism": self.parallelism} if self.parallelism is not None else {}),
                **({"point_cores": self.point_cores} if self.point_cores else {}),
                "configuration_serials": self.configuration_serials,
                **({"configuration_tags": self.configuration_tags} if self.configuration_tags else {}),
                **({"records": list(self.records)} if self.records else {})}

    def counts(self) -> dict:
        """Every run's points together: done, failed, stopped, and done with warnings."""
        runs = self.tally.runs.values()
        return {"done": sum(r["done"] for r in runs), "failed": sum(len(r["failed"]) for r in runs),
                "stopped": sum(r["stopped"] for r in runs), "warned": sum(len(r["warned"]) for r in runs)}

    def _save(self, now: bool = False) -> None:
        """The progress into the entry: at once (`now`), or once EVERY seconds have passed since the last write
        (a timer writes what is left meanwhile)."""
        if self.run_id is None:
            return
        with self._lock:
            if self._closed:
                return
            wait = self._written + self.EVERY - time.monotonic()
            if now or wait <= 0:
                self._write_locked()
            elif self._timer is None:
                self._timer = threading.Timer(wait, self._flush)
                self._timer.daemon = True
                self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            self._timer = None
            if not self._closed:
                self._write_locked()

    def _write_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._kept is None:
            self._kept = entry(self.run_id)
            if self._kept is None:                          # nothing recorded (a read-only root): nothing kept
                self.run_id = None
                return
        self._kept.update(self.progress())
        _write(folder() / f"{self.run_id}.json", self._kept)
        self._written = time.monotonic()

    def close(self) -> dict:
        """No more writes of its own (the run's finish writes next): the last progress."""
        with self._lock:
            self._closed = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        return self.progress()

    def _record_serial(self, event: dict) -> None:
        """A configuration's serial as the runner chose it (doc:errand-file): the number its record folder begins with; and
        its folder's tag, when the run gave it one (V223)."""
        folder = Path(event.get("record") or "").name
        match = re.match(r"^(\d+)_", folder)
        key = event.get("run") or ""
        if key not in self.configuration_serials:
            key = next((name for name, label in sorted(self.configuration_labels.items(),
                                                       key=lambda item: len(item[1]), reverse=True)
                        if folder == label or folder.endswith(f"_{label}")), "")
        if key and match is not None:
            self.configuration_serials[key] = int(match.group(1))
        if key and event.get("tag"):
            self.configuration_tags[key] = str(event["tag"])

    def event(self, event: dict) -> None:
        self.tally.event(event)
        kind, state, key = event.get("k"), event.get("state"), event.get("run") or ""
        if kind == "point" and event.get("point") and not event.get("stage"):       # a configuration point
            point = (key, event["point"])
            with self._lock:                                # the timer's write reads them
                if point in self.ended or state not in ("started", "done", "failed", "stopped", "skipped"):
                    return
                if state == "started":
                    self.active.add(point)
                else:
                    self.active.discard(point)
                    self.ended.add(point)
            self._save()
        elif kind == "run" and state == "started":
            if event.get("record") and event["record"] not in self.records:
                self.records.append(event["record"])
            for path in event.get("library") or []:          # an `only` run's records are its library entries
                if path not in self.records:
                    self.records.append(path)
            with self._lock:
                if key not in self.planned or self.totals.get(key):     # planned again at its turn: its own count
                    self.totals[key] = int(event.get("points", 0))
                self._record_serial(event)
                if isinstance(event.get("parallelism"), int):
                    self.parallelism = event["parallelism"]
                if isinstance(event.get("cores"), int):
                    self.point_cores = max(self.point_cores, event["cores"])
            self._save(now=True)
        elif kind == "run" and state == "finished":
            self.verdicts[key] = event.get("verdict", "")
            self._save(now=True)


class Tally:
    """A bus subscriber (V200): per run (a sweep's `run` key, "" for one run), its points done, failed and stopped,
    those that ended with a warning or an error said, and each failed point's cause, for the run's verdict."""

    def __init__(self):
        self.runs: dict[str, dict] = {}

    def _run(self, key: str) -> dict:
        return self.runs.setdefault(key, {"done": 0, "failed": [], "stopped": 0, "warned": set(), "said": set()})

    def event(self, event: dict) -> None:
        kind, point, key = event.get("k"), event.get("point", ""), event.get("run") or ""
        if kind == "log" and point and event.get("level") in ("warn", "warning", "error"):
            self._run(key)["said"].add(point)
        elif kind == "point" and event.get("state") in ("done", "failed", "stopped"):
            tally = self._run(key)
            if event["state"] == "done":
                tally["done"] += 1
                if point in tally["said"]:
                    tally["warned"].add(point)
            elif event["state"] == "stopped":
                tally["stopped"] += 1
            else:
                tally["failed"].append((point, event.get("cause", ""), event.get("msg", "")))
            tally["said"].discard(point)

    def warned(self, key: str = "") -> int:
        return len(self._run(key)["warned"])

    def stopped(self, key: str = "") -> int:
        """The points stopped (a force pause's discarded ones)."""
        return self._run(key)["stopped"]

    def failures(self, key: str = "") -> list[str]:
        """The failed points, a line each: its name, the tool blamed, the message's first line."""
        rows = self._run(key)["failed"]
        width = max((len(name) for name, _, _ in rows), default=0)
        return [f"   {name:{width}s}  {f'[{cause}] ' if cause else ''}{(message.strip().splitlines() or [''])[0][:160]}"
                for name, cause, message in rows]
