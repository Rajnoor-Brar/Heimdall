"""The run registry (rank 1, V182): what runs on this machine now, and what ran in the last 30 days.

The user, 2026-10-23: "heimdall can keep track of runs and jobs being run in Himinbjorg". One small JSON file a
run (and a cluster submission), `<machine root>/runs/<id>.json` ($HEP_RUNS), beside a detached worker's log
`<id>.log`: who (host, pid, uid, user, its PID and network namespaces, the boot, the pid's start time), where
(the work dir, the checkout, the config, its configurations, the command line), when (started, finished),
how it ended (exit code, verdict) and the record folders it wrote. `heimdall runs` lists them; `heimdall
watch` and `heimdall stop` find a run's socket through them.

The one exception to "runtime state stays off disk" (V72): the user's ask. Each entry has one writer at a
time (the run's own process; its client only when the worker died by a signal), written whole through a
temporary file of its own and a rename. A machine root that cannot be written (an Apptainer image's) records
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
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .events import namespace as _namespace
from .paths import machine_root

DIR_VAR = "HEP_RUNS"
VERSION = 1
KEEP_DAYS = 30
#: A Heimdall cluster job's environment (V184): its submission is recorded, not each job.
CLUSTER_VAR = "HEP_CLUSTER_JOB"
#: What a run's exit code says, in a listing and in an entry.
VERDICTS = {0: "done", 1: "failed", 2: "not run", 6: "stopped"}
#: An entry's id, as new_id makes it: <YYYYmmdd-HHMMSS>-<host>-<4 hex>. Nothing else is read as one.
ID = re.compile(r"\d{8}-\d{6}-[A-Za-z0-9_-]+-[0-9a-f]{4}")


def folder() -> Path:
    """Where the entries are: $HEP_RUNS, else <machine root>/runs."""
    given = os.environ.get(DIR_VAR)
    return Path(given).expanduser() if given else machine_root() / "runs"


def host() -> str:
    return socket.gethostname().split(".")[0]


def new_id(now: float | None = None) -> str:
    """<YYYYmmdd-HHMMSS>-<host>-<4 hex>: sorted by when, unique on a shared machine root."""
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
    written (a read-only machine root)."""
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
    """Where a worker's log goes when the registry cannot be written: <tmp>/hep-runs-<uid>/ (0700)."""
    return Path(tempfile.gettempdir()) / f"hep-runs-{os.getuid()}"


def log_file(run_id: str) -> Path:
    """A detached worker's log: in the registry, else (a read-only machine root) <tmp>/hep-runs-<uid>/."""
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


def finish(run_id: str | None, code: int, verdict: str | None = None, **fields) -> bool:
    """A run ended: its exit code and verdict, when."""
    return update(run_id, code=code, verdict=verdict or VERDICTS.get(code, f"exit {code}"),
                  finished=round(time.time(), 3), **fields)


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
    except (PermissionError, TypeError, ValueError):
        return None
    return not data.get("pstart") or started_at(int(pid)) == data["pstart"]


def state(data: dict, live: dict | None = None) -> str:
    """What an entry says now: its verdict when it ended; running; "lost" (its process is gone, it never said
    how it ended); or why this process cannot tell. `live`: pid → greeting of the sockets this process sees."""
    if data.get("kind") == "cluster":
        return data.get("verdict") or "submitted"
    if data.get("finished") is not None:
        return f"{data.get('verdict') or VERDICTS.get(data.get('code'), 'ended')}"
    running = alive(data)
    if running is False:
        return "lost"
    if running is None:
        return f"on {data.get('host')}" if data.get("host") != host() else "in another PID namespace"
    if live is not None and data.get("pid") not in live and data.get("netns") != _namespace("net"):
        return "running (not reachable from here)"
    return "running"


def spawn(argv: list[str], run_id: str, log: Path) -> subprocess.Popen:
    """A detached run's worker (V183): the command as typed, again, with --worker <id> (which a typed --detach
    gives way to), by this checkout's framework/bin/run and this Python, in a session of its own (no terminal:
    closing one does not end it), reading nothing, its output in `log`."""
    entry = Path(__file__).resolve().parents[1] / "bin" / "run"
    with open(log, "ab") as out:
        return subprocess.Popen([sys.executable, "-X", "utf8", "-u", str(entry), *argv, "--worker", run_id],
                                start_new_session=True, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                close_fds=True)


def cluster_job() -> bool:
    """Whether this process is one of Heimdall's cluster jobs (V184): those are recorded by their submission."""
    return bool(os.environ.get(CLUSTER_VAR))


class Recorder:
    """A bus subscriber: the record folders a run wrote, each run's verdict and its points' counts (V202: done,
    failed, stopped, done with warnings), in memory, for its entry."""

    def __init__(self):
        self.records: list[str] = []
        self.verdicts: dict[str, str] = {}
        self.tally = Tally()

    def counts(self) -> dict:
        """Every run's points together: done, failed, stopped, and done with warnings."""
        runs = self.tally.runs.values()
        return {"done": sum(r["done"] for r in runs), "failed": sum(len(r["failed"]) for r in runs),
                "stopped": sum(r["stopped"] for r in runs), "warned": sum(len(r["warned"]) for r in runs)}

    def event(self, event: dict) -> None:
        self.tally.event(event)
        if event.get("k") != "run":
            return
        if event.get("state") == "started" and event.get("record") and event["record"] not in self.records:
            self.records.append(event["record"])
        elif event.get("state") == "finished":
            self.verdicts[event.get("run") or ""] = event.get("verdict", "")


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

    def failures(self, key: str = "") -> list[str]:
        """The failed points, a line each: its name, the tool blamed, the message's first line."""
        rows = self._run(key)["failed"]
        width = max((len(name) for name, _, _ in rows), default=0)
        return [f"   {name:{width}s}  {f'[{cause}] ' if cause else ''}{(message.strip().splitlines() or [''])[0][:160]}"
                for name, cause, message in rows]
