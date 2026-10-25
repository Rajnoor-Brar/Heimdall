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
"""

from __future__ import annotations

import getpass
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .paths import machine_root

DIR_VAR = "HEP_RUNS"
VERSION = 1
KEEP_DAYS = 30
#: A Heimdall cluster job's environment (V184): its submission is recorded, not each job.
CLUSTER_VAR = "HEP_CLUSTER_JOB"
#: What a run's exit code says, in a listing and in an entry.
VERDICTS = {0: "done", 1: "failed", 2: "not run", 6: "stopped"}


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


def _namespace(kind: str) -> str:
    try:
        return os.readlink(f"/proc/self/ns/{kind}")
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


def log_file(run_id: str) -> Path:
    """A detached worker's log: in the registry, else (a read-only machine root) <tmp>/hep-runs-<uid>/."""
    reserved = reserve(run_id, ".log")
    if reserved is not None:
        return reserved
    fallback = Path(tempfile.gettempdir()) / f"hep-runs-{os.getuid()}"
    fallback.mkdir(mode=0o700, exist_ok=True)
    return fallback / f"{run_id}.log"


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


def entries(now: float | None = None) -> list[dict]:
    """Every entry, newest first, after pruning those KEEP_DAYS old."""
    prune(now)
    found = []
    for path in sorted(folder().glob("*.json")) if folder().is_dir() else ():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("id"):
            found.append(data)
    return sorted(found, key=lambda e: e.get("started", 0), reverse=True)


def prune(now: float | None = None) -> None:
    """Entries finished KEEP_DAYS ago (or begun KEEP_DAYS ago and never finished: a process killed), and their
    logs; a log with no entry, by its age."""
    now = time.time() if now is None else now
    edge = now - KEEP_DAYS * 86400
    where = folder()
    if not where.is_dir():
        return
    try:
        for path in where.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (data.get("finished") or data.get("started") or now) < edge:
                path.unlink(missing_ok=True)
                (where / f"{data.get('id', path.stem)}.log").unlink(missing_ok=True)
        for log in where.glob("*.log"):
            if not log.with_suffix(".json").exists() and log.stat().st_mtime < edge:
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
    """A bus subscriber: the record folders a run wrote and each run's verdict, in memory, for its entry."""

    def __init__(self):
        self.records: list[str] = []
        self.verdicts: dict[str, str] = {}

    def event(self, event: dict) -> None:
        if event.get("k") != "run":
            return
        if event.get("state") == "started" and event.get("record") and event["record"] not in self.records:
            self.records.append(event["record"])
        elif event.get("state") == "finished":
            self.verdicts[event.get("run") or ""] = event.get("verdict", "")
