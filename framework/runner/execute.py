"""Running a point: [prelim], the tool groups, supervision, the checks (rank 3).

docs/06_Internals.md §11. A FIFO chain fails in two ways a single process does not,
and both are handled here by construction:

* **Deadlock at open (L8).** A FIFO blocks until both ends are open. If the writer dies before
  opening, the reader waits for ever and gets no SIGPIPE. So each tool runs in its own process
  group. The first nonzero exit is the cause, and after a grace period the rest of the group gets
  SIGTERM, then SIGKILL. A tool silent for `stall_after` seconds (no output, status or heartbeat)
  counts as failed.
* **A partial result that looks complete.** If the generator dies mid-stream, Rivet sees end of file
  and exits 0. So a consumer's event count is checked against the producer's sidecar, and a product
  keeps its `.partial` name until every check has passed. `.complete` is written last.

Attribution: the cause is the first process to exit nonzero before the runner sent any signal. A
SIGPIPE death is a consequence (its reader went away), never the cause: the reader is blamed, even
when both exits are seen in the same poll (found by P1's failure injection).

**Points at once** (`parallelism = K`, V36): `run_points` runs up to K points on threads of their
own, each through the same `run_point`. Nothing of a point is shared with another (its folder holds
its FIFOs, logs and products), except the event bus (locked) and a prepare cache entry, which one
point at a time may fill (`_prepare_lock`: a lock in this process and flock across processes).

**What is said** goes onto the run's event bus (events.py, V72): a point's and a tool's start and end,
and every status message. A tool's output is read from a pipe (status.Reader); only a failed tool's last
lines reach the point's <tag>.log (records/<A>/<E>/<R>/logs/<point>/), unless `logs` (--logs) keeps every tool's whole log.

**Logs** (V201): each tool's <tag>.log is its digest, written at its end however it ended (status.Reader); with
`logs` its whole output is <tag>.full.log. A new attempt first moves the last one's logs, with a copy of its cards,
into the point's history/<n>/ (`rotate`), the newest `[run] log` digests (9) keeping their digests and cards and
the newest `full` (3) their whole logs.

**What is kept** (V200): every attempt, however it ends (done, failed, stopped, a [prelim] failure; pre, post and
combined stages too), appends a line to the point's attempts.jsonl (record.append_attempt): its verdict, its
cause (the tool to blame and how: failed, stalled, timeout, count, missing, stopped, prelim) and each tool's
exit, stall (its phase, last line, how long silent and since when), warnings, errors and what it reported
(its `summary`, its last σ). A complete point's provenance.json carries its tools' warnings and reports too.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import hepfiles
from .errors import HeimdallError
from .paths import keeping, log_settings, placeholders, portable
from .record import (LOCK_FILE, PointLock, append_attempt, attempts, card_hashes, complete_marker, held_by, holder,
                     is_complete, now, stale, provenance, provenance_file, write_atomic, write_identity)
from .status import Reader, ToolState, clean_text, digest
from .tools import CONTEXT_FILE, PointPlan, Step, expand

GRACE = 2.0                  # after the first failure, before the rest of the group is asked to stop
TERM_GRACE = 5.0             # after SIGTERM, before SIGKILL
POLL = 0.2


class Stopper:
    """Set by the CLI's signal handlers; the supervisor turns it into the stop ladder. `hard` (a second
    Ctrl-C, V181): the tools are killed at once, not after the ladder's graces; the stop is still recorded.
    `pausing` (a `p`, SIGUSR1, I-115): no point, stage or run is begun any more, the running points run to their
    end; a second `p` is a force pause, `requested` and `hard` as a hard stop. `paused`: the run ends as a pause
    (a stop after it, a `q`, clears it)."""

    def __init__(self):
        self.requested = False
        self.hard = False
        self.pausing = False
        self.paused = False

    @property
    def halted(self) -> bool:
        """Nothing more is begun: a stop or a pause."""
        return self.requested or self.pausing


@dataclass
class ToolResult:
    tag: str
    exit: int | None = None
    seconds: float = 0.0
    cause: str = ""                      # failed | stalled | timeout | stopped | count | missing
    message: str = ""
    stall: dict | None = None            # a stall's context: phase, last line, silent (s), since (V200)
    warnings: dict = field(default_factory=dict)    # message → [count, first line] (status.Reader.signals)
    errors: dict = field(default_factory=dict)
    reported: dict = field(default_factory=dict)    # its summary and last σ (status.Reader.reported)
    cache: str = ""                      # a prepare step a cache entry held: the entry

    def kept(self) -> dict:
        """What an attempt keeps of it (V200): only what it has."""
        out = {"exit": self.exit, "seconds": round(self.seconds, 3)}
        for key in ("cause", "message", "stall", "warnings", "errors", "reported", "cache"):
            if value := getattr(self, key):
                out[key] = value
        return out


@dataclass
class PointResult:
    ok: bool
    stopped: bool = False
    held: bool = False                   # another session runs it (U66): skipped, neither done nor failed
    cause: str = ""                      # the tag to blame
    message: str = ""
    tools: dict[str, ToolResult] = field(default_factory=dict)


class _Quiet:
    """A bus no one hears (tests, and a caller that wants no events)."""

    def emit(self, point, tool, message):
        return message


def _bus(bus):
    return bus if bus is not None else _Quiet()


class Budget:
    """Cores shared by the runs of a pipelined sweep (V75): a point takes its cores while it runs; one
    that needs more than is free waits, unless nothing is running (a point bigger than the budget runs
    alone)."""

    def __init__(self, total: int):
        self.total, self.used = max(1, total), 0
        self._lock = threading.Lock()

    def take(self, count: int) -> bool:
        with self._lock:
            if self.used and self.used + count > self.total:
                return False
            self.used += count
            return True

    def give(self, count: int) -> None:
        with self._lock:
            self.used = max(0, self.used - count)


def run_points(plans: list[PointPlan], errand, configuration, *, bus=None, stopper: Stopper,
               rerun: bool, logs: bool = False, budget: Budget | None = None,
               started_all=None, wait_held: bool = False) -> tuple[int, int, bool]:
    """Every point not already complete, `configuration.parallelism` at a time, in order: (done,
    failed, halted). A stop (Ctrl-C) starts nothing more and stops the running points through
    their groups' stop ladder; a pause (I-115) starts nothing more and lets them end, and the run then ends
    halted however many were left (its later stages wait for the rerun). An error of the runner itself is
    raised once the running points have ended. In a pipelined sweep (V75) a point also waits for its cores in the shared `budget`, and
    `started_all()` is called once every point has started (the next run may then start). A point another
    session runs is skipped, or with `wait_held` waited for (U66)."""
    bus = _bus(bus)
    todo = []
    for plan in plans:
        if not stale(plan, rerun):
            bus.emit(plan.point.name, "", {"k": "point", "state": "skipped", "index": plan.point.index,
                                           **({"stage": plan.point.stage} if plan.point.stage else {})})
        else:
            todo.append(plan)
    signalled = False

    def all_started() -> None:
        nonlocal signalled
        if not signalled and started_all is not None:
            signalled = True
            started_all()

    done = failed = 0
    stopped = False
    at_once = max(1, configuration.parallelism)
    if at_once == 1 and budget is None:
        for i, plan in enumerate(todo):
            if stopper.halted:
                all_started()
                return done, failed, True
            if i == len(todo) - 1:
                all_started()
            result = run_point(plan, errand, configuration, bus=bus, stopper=stopper, logs=logs, wait=wait_held)
            if result.stopped or stopper.requested:
                return done, failed, True
            failed += not result.ok and not result.held
            done += result.ok
        all_started()
        return done, failed, stopper.pausing
    error: BaseException | None = None
    held: dict = {}                                   # a running point's future → the cores it took
    with ThreadPoolExecutor(max_workers=at_once, thread_name_prefix="heimdall-point") as pool:
        running: set = set()
        while todo or running:
            while todo and len(running) < at_once and not stopper.halted and error is None:
                plan = todo[0]
                need = cores(plan) if budget is not None else 0
                if budget is not None and not budget.take(need):
                    break                             # its cores are another run's for now
                todo.pop(0)
                future = pool.submit(run_point, plan, errand, configuration, bus=bus, stopper=stopper, logs=logs, wait=wait_held)
                held[future] = need
                running.add(future)
            if not todo:
                all_started()
            if not running:
                if todo and not stopper.halted and error is None:
                    time.sleep(POLL)                  # waiting for the budget
                    continue
                break
            finished, running = wait(running, timeout=0.5, return_when=FIRST_COMPLETED)   # SIGINT gets in
            for future in finished:
                if budget is not None:
                    budget.give(held.pop(future, 0))
                try:
                    result = future.result()
                except BaseException as caught:          # the runner's own error, not a tool's
                    error = error or caught
                    continue
                stopped |= result.stopped
                failed += not result.ok and not result.stopped and not result.held
                done += result.ok
    all_started()
    if error is not None:
        raise error
    return done, failed, stopped or stopper.halted


def cores(plan: PointPlan) -> int:
    """About how many cores a point keeps busy, for the plan's note: its busiest group, where a
    generator counts its threads, a table's own `cores` what it says, an integrated program (a program
    with a config file, in a point whose context has a generator that does not run as a process of its
    own: generate_cards) the generator's threads and one more, anything else one (V60: no tool named)."""
    busiest = 0
    integrated = any(s.group < 0 and s.folder.get("tool", "produces_events") for s in plan.rendered.values())
    for group in plan.groups:
        count = 0
        for step in group:
            if step.folder.get("tool", "produces_events"):
                count += plan.threads
            elif step.tool.cores:
                count += step.tool.cores
            elif integrated and step.folder.get("tool", "config_file"):
                count += plan.threads + 1
            else:
                count += 1
        busiest = max(busiest, count)
    return max(busiest, 1)


def auto_parallelism(plans: list[PointPlan]) -> int:
    """`parallelism = "auto"` (V75): as many points at once as the machine's cores hold, by the
    costliest point's cores (at least one)."""
    each = max((cores(p) for p in plans), default=1)
    return max(1, (os.cpu_count() or 1) // each)


_PREPARE_LOCKS: dict[Path, threading.Lock] = {}
_PREPARE_GUARD = threading.Lock()


@contextmanager
def _prepare_lock(directory: Path):
    """One point at a time in a prepare cache entry: a lock per entry in this process, and flock on
    <entry>.lock beside it across processes (two heimdall runs), so the entry's own folder stays the tool's."""
    with _PREPARE_GUARD:
        lock = _PREPARE_LOCKS.setdefault(directory, threading.Lock())
    with lock:
        directory.parent.mkdir(parents=True, exist_ok=True)
        with open(directory.with_name(directory.name + ".lock"), "w", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


# ── the count check ────────────────────────────────────────────────────────────────────────────

def read_count(path: Path, reader: str) -> float | None:
    """`yoda:/RAW/_EVTCOUNT` → the counter's numEntries, read from the YODA text;
    `json:events` → that key of the product's report, <product>.json (the module kit writes it);
    `root:Delphes` → that tree's entries (uproot, imported only here: the runner is stdlib otherwise)."""
    kind, _, obj = reader.partition(":")
    if kind == "root":
        try:
            import uproot
            with uproot.open(path) as file:
                return float(file[obj].num_entries)
        except Exception:                        # no uproot, no file, no tree: no count
            return None
    if kind == "json":
        try:
            return float(json.loads(report_of(path).read_text(encoding="utf-8"))[obj])
        except (OSError, ValueError, KeyError, TypeError):
            return None
    if kind != "yoda":
        return None
    return hepfiles.entries(path, obj)


def report_of(product: Path) -> Path:
    return product.with_name(product.name + ".json")


# ── [prelim] ───────────────────────────────────────────────────────────────────────────────────

#: A point's commands, beside its cards (V187): each tool's command line as it was run, for the record.
COMMANDS_FILE = "commands.sh"


def commands_text(plan: PointPlan) -> str:
    """The commands a point's tools are given (V187), as a shell script in the point's working folder: the
    context every tool reads, the FIFOs, each prepare step, then each group's tools (run together, joined by
    the FIFOs), with the folder and environment each runs in. What the runner adds besides (its status pipe,
    HEIMDALL_STATUS_FD) is left out. For the record, and to run a tool again by hand."""
    q = shlex.quote

    def command(step: Step, argv: list[str], cwd: Path | None) -> str:
        env = "".join(f"{key}={q(value)} " for key, value in step.env.items())
        line = env + " ".join(q(str(a)) for a in argv)
        return f"(cd {q(str(cwd))} && {line})" if cwd is not None and cwd != plan.out else line

    lines = ["#!/bin/bash",
             f"# {plan.point.name}: the commands heimdall gave its tools (V187). A group's tools run together,",
             "# joined by the FIFOs below; heimdall's status pipe (HEIMDALL_STATUS_FD) is left out.",
             "set -euo pipefail", f"cd {q(str(plan.out))}",
             f"export HEIMDALL_CONTEXT={q(str(plan.out / CONTEXT_FILE))}      # every tool's card and config"]
    fifos = [i.path for i in plan.interfaces.values() if i.kind == "fifo"]
    if fifos:
        lines += ["", "# the FIFOs", *(f"rm -f {q(str(path))} && mkfifo {q(str(path))}" for path in fifos)]
    for step in (s for group in plan.groups for s in group if s.prepare_argv):
        lines += ["", f"# {step.tag}: its prepare step (once per card: cached in {step.prepare_dir})",
                  command(step, step.prepare_argv, step.prepare_dir)]
    for number, group in enumerate(plan.groups, 1):
        lines += ["", f"# group {number}: {', '.join(s.tag for s in group)}"]
        lines += [command(s, s.argv, s.cwd) + (" &" if len(group) > 1 else "") for s in group]
        if len(group) > 1:
            lines.append("wait")
    return "\n".join(lines) + "\n"


HISTORY = "history"                  # a point's earlier attempts' logs and cards (V201)


def full_of(log: Path) -> Path:
    """A digest's whole log (V201): <tag>.log → <tag>.full.log, <tag>.prepare.log → <tag>.prepare.full.log."""
    return log.with_name(log.name.removesuffix(".log") + ".full.log")


def rotate(plan: PointPlan, digests: int, full: int) -> Path | None:
    """An attempt begins (V201): the last one's logs (*.log: digests, whole logs, prelim.log) move into the point's
    history/<n>/ with a copy of its cards/, n being that attempt's number (attempts.jsonl), or for a record that
    has none, the next free one; then the `digests` newest folders keep their digests and cards, the `full`
    newest their whole logs, and older ones go. The folder, or None when there was nothing to keep."""
    logs = sorted(p for p in plan.out.glob("*.log") if p.is_file()) if plan.out.is_dir() else []
    if not logs:
        return None
    history = plan.out / HISTORY
    taken = [int(p.name) for p in history.iterdir() if p.is_dir() and p.name.isdigit()] if history.is_dir() else []
    number = len(attempts(plan))
    if number < 1 or number in taken:
        number = max(taken, default=0) + 1
    target = history / str(number)
    target.mkdir(parents=True)
    for log in logs:
        log.replace(target / log.name)
    if (plan.out / "cards").is_dir():
        shutil.copytree(plan.out / "cards", target / "cards")
    folders = sorted((p for p in history.iterdir() if p.is_dir() and p.name.isdigit()), key=lambda p: -int(p.name))
    for place, folder in enumerate(folders):
        if place >= digests:
            shutil.rmtree(folder)
        elif place >= full:
            for whole in folder.glob("*.full.log"):
                whole.unlink()
    return target


def prepare(plan: PointPlan, logs: bool = False, attempt: int = 0) -> None:
    for directory in (plan.out, plan.res):        # a log is made by what writes it (V149)
        directory.mkdir(parents=True, exist_ok=True)
    settings = log_settings()
    rotate(plan, settings["digests"], settings["full"])          # the last attempt's logs into history/ (V201)
    marker = complete_marker(plan)
    if marker.exists():
        marker.unlink()                  # an attempt is under way: whatever was complete no longer is
    for path, text in plan.writes.items():
        write_atomic(path, text)
    if plan.groups:                      # V187: what its tools are given, kept with its cards
        write_atomic(plan.out / COMMANDS_FILE, commands_text(plan))
        (plan.out / COMMANDS_FILE).chmod(0o755)
    for step in plan.rendered.values():  # a product left by an earlier attempt must not pass for this one's
        for final, partial in step.products:
            final.parent.mkdir(parents=True, exist_ok=True)          # a shard's is under records/…/logs/<point>/shards/
            for path in (final, partial, report_of(final), report_of(partial)):
                path.unlink(missing_ok=True)
    for interface in plan.interfaces.values():
        if interface.kind == "fifo":
            if interface.path.exists() or interface.path.is_symlink():
                if not stat.S_ISFIFO(interface.path.stat().st_mode):
                    raise HeimdallError(f"{interface.path} exists and is not a FIFO", hint="remove it")
                interface.path.unlink()  # fresh per attempt
            os.mkfifo(interface.path)
        elif interface.kind == "file" and interface.name in plan.prelim.get("files", []):
            interface.path.touch(exist_ok=True)
    said: list[str] = []
    for command in plan.prelim.get("commands", []):
        context = {**placeholders(), "out": str(plan.out), "res": str(plan.res),
                   "file:": {n: str(i.path) for n, i in plan.interfaces.items()}}
        argv = [x for a in command for x in ([expand(str(a), context, "[prelim].commands")])]
        done = subprocess.run(argv, cwd=plan.out, capture_output=True, text=True, encoding="utf-8")
        said += clean_text(f"$ {' '.join(argv)}\n{done.stdout}{done.stderr}").rstrip("\n").split("\n")
        if done.returncode != 0:
            _prelim_log(plan, said, logs, attempt, settings, done.returncode)
            raise HeimdallError(f"[prelim] command failed ({done.returncode}): {' '.join(argv)}",
                           where=str(plan.out / "prelim.log"))
    if said:
        _prelim_log(plan, said, logs, attempt, settings, 0)


def _prelim_log(plan: PointPlan, lines: list[str], logs: bool, attempt: int, settings: dict, code: int) -> None:
    """[prelim]'s output (V201): prelim.log its digest, prelim.full.log the whole of it with `logs`."""
    numbered = list(enumerate(lines, 1))
    header = {"tag": "prelim", "attempt": attempt or "", "exit": code}
    (plan.out / "prelim.log").write_text(digest(numbered[:settings["head"]], numbered[-settings["tail"]:] if settings["tail"] else [],
                                                [], 0, len(lines), 0, header), encoding="utf-8")
    if logs:
        (plan.out / "prelim.full.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── one group ──────────────────────────────────────────────────────────────────────────────────

@dataclass
class _Running:
    step: Step
    process: subprocess.Popen
    state: ToolState
    reader: Reader
    fd: int | None
    started: float
    exited_at: float | None = None
    begun: str = ""                      # when it started, for its digest's header


def _signal(entry: _Running, sig: int) -> None:
    try:
        os.killpg(entry.process.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def events_of(plan: PointPlan, step: Step) -> int | None:
    """The events a tool makes or reads, for its progress bar when its own lines do not say: a producer
    of events makes the point's; a consumer reads them all, unless a producer deals them among shards."""
    folder, tool = step.folder, step.tool
    consumes = tool.consumes_events if tool.consumes_events is not None else folder.get("tool", "consumes_events", False)
    if folder.get("tool", "produces_events") or (consumes and not plan.deal):
        return plan.events or None
    return None


def run_group(plan: PointPlan, group: list[Step], *, bus, stopper: Stopper,
              results: dict[str, ToolResult], logs: bool = False, attempt: int = 0) -> tuple[bool, str, str]:
    """Run one group to the end. Returns (ok, blamed tag, message). Each tool's digest is written at its end
    (V201)."""
    bus = _bus(bus)
    running: list[_Running] = []
    settings = log_settings()
    for step in group:
        step.log.parent.mkdir(parents=True, exist_ok=True)
        out_read, out_write = os.pipe()
        env = dict(os.environ)
        env.update(step.env)
        env["HEIMDALL_CONTEXT"] = str(plan.out / CONTEXT_FILE)         # every tool's card and config (04 §9.4)
        env.pop("HEIMDALL_STATUS_FD", None)
        read_fd = write_fd = None
        if step.status == "standard":
            read_fd, write_fd = os.pipe()
            env["HEIMDALL_STATUS_FD"] = str(write_fd)
        try:
            process = subprocess.Popen(step.argv, cwd=step.cwd or plan.out, env=env, stdin=subprocess.DEVNULL,
                                       stdout=out_write, stderr=subprocess.STDOUT, start_new_session=True,
                                       pass_fds=(write_fd,) if write_fd is not None else ())
        except OSError as error:
            for entry in running:
                _signal(entry, signal.SIGKILL)
            os.close(out_read)
            if read_fd is not None:
                os.close(read_fd)
            raise HeimdallError(f"cannot start {step.tag}: {error}", where=" ".join(step.argv[:2]))
        finally:
            os.close(out_write)
            if write_fd is not None:
                os.close(write_fd)
        state = ToolState(point=plan.point.name, tag=step.tag)
        bus.emit(plan.point.name, step.tag, {"k": "tool", "state": "started"})
        entry = _Running(step, process, state, Reader(state, fd=read_fd, out=out_read, rules=step.filters, bus=bus,
                                                      log=full_of(step.log) if logs and step.log else None, keep=logs,
                                                      total=events_of(plan, step), head=settings["head"],
                                                      tail=settings["tail"]),
                         read_fd, time.monotonic(), begun=now())
        running.append(entry)

    failure: tuple[str, str, str] | None = None      # (tag, cause, message)
    stall: dict | None = None
    failed_at = 0.0
    termed = killed = interrupted = False
    exits: list[_Running] = []
    while True:
        for entry in running:
            if entry.exited_at is None and entry.process.poll() is not None:
                entry.exited_at = time.monotonic()
                entry.reader.join(0.5)                # its last status and lines
                entry.state.running, entry.state.exit = False, entry.process.returncode
                exits.append(entry)
                results[entry.step.tag] = ToolResult(entry.step.tag, entry.process.returncode,
                                                     entry.exited_at - entry.started)
                bus.emit(plan.point.name, entry.step.tag, {"k": "exit", "code": entry.process.returncode,
                                                           "seconds": round(entry.exited_at - entry.started, 3)})
        alive = [e for e in running if e.exited_at is None]
        clock = time.monotonic()

        if failure is None:
            failed = [e for e in exits if e.process.returncode != 0]
            if failed:
                # A SIGPIPE death is a consequence (the reader went away), never the cause: blame the
                # first real failure, else the process that left first, even if it exited 0.
                real = [e for e in failed if e.process.returncode != -signal.SIGPIPE]
                blamed = real[0] if real else exits[0]
                piped = [e.step.tag for e in failed if e.process.returncode == -signal.SIGPIPE]
                message = f"{blamed.step.tag} exited with {_describe(blamed.process.returncode)}"
                if blamed.reader.reasons:                       # what its rules say it is down to (V203)
                    message += f": {blamed.reader.reasons[-1]}"
                if piped and blamed.step.tag not in piped:
                    message += f"; {', '.join(piped)} then lost its pipe"
                failure, failed_at = (blamed.step.tag, "failed", message), clock
        if failure is None:
            for entry in alive:
                if clock - entry.state.last_activity > entry.step.stall_after:
                    failure = (entry.step.tag, "stalled", stalled(entry.step.tag, entry.step.stall_after, entry.state, clock))
                    stall = stall_context(entry.step.stall_after, entry.state, clock)
                elif entry.step.timeout and clock - entry.started > entry.step.timeout:
                    failure = (entry.step.tag, "timeout", f"{entry.step.tag} ran past its timeout of {entry.step.timeout:.0f} s")
                if failure:
                    failed_at = clock
                    break
        if failure is None and stopper.requested:
            failure, failed_at = ("", "stopped", "stopped by the user"), clock
            for entry in alive:
                _signal(entry, signal.SIGINT)
            interrupted = True
        if stopper.hard and not killed and alive:               # a second Ctrl-C: no graces (V181)
            for entry in alive:
                _signal(entry, signal.SIGKILL)
            killed = termed = True

        if not alive:
            break
        if failure is not None:
            waited = clock - failed_at
            if not termed and waited >= GRACE:
                for entry in alive:
                    _signal(entry, signal.SIGTERM)
                termed = True
            elif termed and not killed and waited >= GRACE + TERM_GRACE:
                for entry in alive:
                    _signal(entry, signal.SIGKILL)
                killed = True
        time.sleep(POLL)

    for entry in running:
        entry.reader.join()
        kept = results.setdefault(entry.step.tag, ToolResult(entry.step.tag, entry.process.returncode))
        kept.warnings, kept.errors = entry.reader.signals("warn"), entry.reader.signals("error")
        kept.reported = entry.reader.reported()
        if entry.step.log is not None:                                                          # V201
            entry.reader.write_digest(entry.step.log, {"tag": entry.step.tag, "attempt": attempt or "",
                                                       "started": entry.begun, "exit": entry.process.returncode})
    if failure is None:
        return True, "", ""
    tag, cause, message = failure
    if tag and tag in results:
        failing = next(e for e in running if e.step.tag == tag)
        if cause == "failed" and (said := diagnose(plan, failing.step, failing.process.returncode)):
            message += f"; asked again: {said}"                         # V203
        results[tag].cause, results[tag].message = cause, message
        if cause == "stalled":
            results[tag].stall = stall
    if interrupted:
        return False, "", message
    return False, tag, message


def stalled(tag: str, after: float, state: ToolState, clock: float) -> str:
    """A stall's message (V195): how long, since when (local time), and what the tool was last doing and saying,
    so the record says where it stopped."""
    since = time.strftime("%H:%M", time.localtime(time.time() - (clock - state.last_activity)))
    doing = "; ".join(part for part in (state.phase, f'last line: "{state.last_line[:120]}"' if state.last_line else "")
                      if part)
    return f"{tag} was silent for {after:.0f} s, since {since}" + (f" ({doing})" if doing else "")


def diagnose(plan: PointPlan, step: Step, code: int | None) -> str:
    """A tool folder's [diagnose] (V203): after an exit it names (`exits`), the tool is run once more as it was,
    with one more card (`card`'s lines, a file of `ext`) after its own and its outputs moved to a scratch folder,
    for at most `timeout` seconds; `program` (the folder's placeholders, {exe} the tool's) runs in place of its
    executable, with the same arguments. Its output's digest is <tag>.diagnose.log; the lines matching `quote` (at most
    three) are returned, for the failure to quote; "" when there is none, or no [diagnose]."""
    spec = step.folder.spec.get("diagnose") or {}
    if not spec or code not in spec.get("exits", []):
        return ""
    scratch = plan.out / "diagnose"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    card = scratch / f"diagnose.{spec.get('ext', 'txt')}"
    card.write_text("\n".join(spec.get("card", [])) + "\n", encoding="utf-8")
    moved = sorted(((str(i.path), str(scratch / i.path.name)) for i in step.outputs), key=lambda pair: -len(pair[0]))

    def away(arg) -> str:                 # an output, a joined list of them (`a+b,c`) or a path made from one
        arg = str(arg)
        for path, there in moved:
            arg = arg.replace(path, there)
        return arg

    env = {**os.environ, **step.env, "HEIMDALL_CONTEXT": str(plan.out / CONTEXT_FILE)}
    env.pop("HEIMDALL_STATUS_FD", None)
    try:
        argv = [away(a) for a in step.argv] + [str(card)]
        if spec.get("program"):
            context = {**placeholders(), "exe": str(step.exe)}
            argv = [expand(str(a), context, f"{step.tag}: [diagnose].program") for a in spec["program"]] + argv[1:]
        done = subprocess.run(argv, cwd=step.cwd or plan.out,
                              env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=float(spec.get("timeout", 300)))
        text, code = (done.stdout + done.stderr).decode("utf-8", "replace"), done.returncode
    except subprocess.TimeoutExpired as late:
        text, code = ((late.stdout or b"") + (late.stderr or b"")).decode("utf-8", "replace"), None
    except OSError as error:
        text, code = f"could not run it again: {error}", None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    lines = clean_text(text).rstrip("\n").split("\n")
    pattern = re.compile(spec.get("quote", r"\bError\b"))
    quoted = list(dict.fromkeys(line.strip() for line in lines if pattern.search(line)))
    numbered = list(enumerate(lines, 1))
    settings = log_settings()
    (plan.out / f"{step.tag}.diagnose.log").write_text(
        digest(numbered[:settings["head"]], numbered[-settings["tail"]:] if settings["tail"] else [],
               [(n, line) for n, line in numbered if pattern.search(line)][:500], len(quoted), len(lines), 0,
               {"tag": f"{step.tag} (asked again: [diagnose])", "exit": code}), encoding="utf-8")
    return "; ".join(quoted[:3])


def stall_context(after: float, state: ToolState, clock: float) -> dict:
    """A stall's context for the record (V200): what the tool was doing and saying last, how long it was silent
    and since when (UTC)."""
    since = time.time() - (clock - state.last_activity)
    out = {"silent": round(after), "since": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(since))}
    if state.phase:
        out["phase"] = state.phase
    if state.last_line:
        out["last_line"] = state.last_line[:200]
    return out


def _describe(code: int) -> str:
    if code < 0:
        try:
            return f"signal {signal.Signals(-code).name}"
        except ValueError:
            return f"signal {-code}"
    return f"exit code {code}"


# ── one point ──────────────────────────────────────────────────────────────────────────────────

def run_point(plan: PointPlan, errand, configuration, *, bus=None, stopper: Stopper | None = None,
              logs: bool = False, wait: bool = False) -> PointResult:
    """One point, under its lock (U66): a point another session runs is skipped, naming who runs it,
    or (`wait`) waited for, then skipped if that session completed it."""
    bus = _bus(bus)
    stopper = stopper or Stopper()
    lock = PointLock(plan)
    stage = {"stage": plan.point.stage} if plan.point.stage else {}
    if not lock.acquire(wait=wait, stopper=stopper):
        if stopper.halted:
            return PointResult(False, stopped=stopper.requested, held=not stopper.requested)
        who = holder(plan)
        message = f"running in another session ({held_by(who)}): skipped" if who else "running in another session: skipped"
        bus.emit(plan.point.name, "", {"k": "point", "state": "skipped", "index": plan.point.index, "msg": message, **stage})
        return PointResult(False, held=True, message=message)
    try:
        if wait and is_complete(plan):                # the other session completed it meanwhile
            bus.emit(plan.point.name, "", {"k": "point", "state": "skipped", "index": plan.point.index, **stage})
            return PointResult(False, held=True)
        return _run_point(plan, errand, configuration, bus=bus, stopper=stopper, logs=logs)
    finally:
        lock.release()


def _run_point(plan: PointPlan, errand, configuration, *, bus, stopper: Stopper, logs: bool) -> PointResult:
    started = now()
    attempt = len(attempts(plan)) + 1                 # this attempt's number (V200, V201)
    results: dict[str, ToolResult] = {}
    bus.emit(plan.point.name, "", {"k": "point", "state": "started", "index": plan.point.index,
                                   **({"stage": plan.point.stage} if plan.point.stage else {})})
    try:
        prepare(plan, logs, attempt)
    except HeimdallError as error:
        result = PointResult(False, cause="prelim", message=error.render())
        _finished(plan, result, bus, started)
        return result

    ok, blamed, message = run_prepares(plan, bus=bus, stopper=stopper, results=results, logs=logs, attempt=attempt)
    if not ok:
        result = PointResult(False, stopped=stopper.requested, cause=blamed, message=message, tools=results)
        _cleanup(plan)
        _finished(plan, result, bus, started)
        return result

    for group in plan.groups:
        ok, blamed, message = run_group(plan, group, bus=bus, stopper=stopper, results=results, logs=logs,
                                        attempt=attempt)
        if not ok:
            result = PointResult(False, stopped=stopper.requested, cause=blamed, message=message, tools=results)
            _cleanup(plan)
            _finished(plan, result, bus, started)
            return result
        # a group's products are checked and take their final names before the next group reads them
        failure = _settle(group, results)
        if failure is not None:
            _cleanup(plan)
            _finished(plan, failure, bus, started)
            return failure
        for tag, note in empty_analyses(group):              # a warning, recorded (V200)
            kept = results.setdefault(tag, ToolResult(tag)).warnings
            kept[note] = [kept.get(note, [0, None])[0] + 1, None]
            bus.emit(plan.point.name, tag, {"k": "log", "level": "warn", "msg": note})

    _cleanup(plan)
    record = provenance(plan, errand, configuration, started, now(),
                        {tag: {"exit": r.exit, "seconds": round(r.seconds, 3), "note": r.message,
                               **{k: v for k, v in (("warnings", r.warnings), ("errors", r.errors),
                                                    ("reported", r.reported)) if v}}
                         for tag, r in results.items()})
    write_atomic(provenance_file(plan), json.dumps(record, indent=1, default=str) + "\n")
    write_identity(plan)                          # what it ran with, for --why (V57)
    write_atomic(complete_marker(plan), plan.identity + "\n")
    _tidy(plan)
    result = PointResult(True, tools=results)
    _finished(plan, result, bus, started)
    return result


def run_prepares(plan: PointPlan, *, bus=None, stopper: Stopper, results: dict[str, ToolResult],
                 logs: bool = False, attempt: int = 0) -> tuple[bool, str, str]:
    """[prepare] steps (Herwig's read, Sherpa's integration), each in its cache entry, before the
    groups. An entry with a `.prepared` stamp is a hit and runs nothing; the stamp is written only
    after the step exited 0 and left its marker, so an interrupted integration is redone."""
    for step in plan.rendered.values():
        if step.prepare_dir is None or not step.prepare_needed:
            continue
        tag = f"{step.tag}:prepare"
        stamp = step.prepare_dir / ".prepared"
        if stamp.exists():
            results[tag] = ToolResult(tag, exit=0, message=f"cache hit {step.prepare_dir.name}", cache=str(step.prepare_dir))
            _hit_log(results[tag], step.prepare_dir)
            _bus(bus).emit(plan.point.name, "", {"k": "note", "msg": f"   {tag}: cached ({step.prepare_dir})"})
            continue
        with _prepare_lock(step.prepare_dir):            # another point may be filling it (V36)
            if stopper.requested:
                return False, step.tag, "stopped before its prepare step"
            if stamp.exists():
                results[tag] = ToolResult(tag, exit=0, message=f"cache hit {step.prepare_dir.name}",
                                          cache=str(step.prepare_dir))
                _hit_log(results[tag], step.prepare_dir)
                _bus(bus).emit(plan.point.name, "", {"k": "note", "msg": f"   {tag}: cached, made by a point running "
                                                                         f"beside it ({step.prepare_dir})"})
                continue
            ok, blamed, message = _prepare(plan, step, tag, stamp, bus=bus, stopper=stopper, results=results, logs=logs,
                                           attempt=attempt)
            if not ok:
                return False, blamed, message
    return True, "", ""


def _hit_log(result: ToolResult, entry: Path) -> None:
    """A cache hit names the log that filled the entry, when the entry kept one (V201)."""
    if (entry / PREPARE_LOG).is_file():
        result.message += f" (its log: {entry / PREPARE_LOG})"


#: A prepare cache entry's copy of the digest of the step that filled it (V201).
PREPARE_LOG = "prepare.log"


def _prepare(plan: PointPlan, step: Step, tag: str, stamp: Path, *, bus, stopper: Stopper,
             results: dict[str, ToolResult], logs: bool = False, attempt: int = 0) -> tuple[bool, str, str]:
    """One prepare step into its (locked) cache entry; the stamp only after it exited 0 with its marker: what ran,
    how long, the card's sha256, the record and point that filled it, and the step's digest in the entry
    (prepare.log). A stamp of the older shape is a hit all the same: only its being there counts."""
    step.prepare_dir.mkdir(parents=True, exist_ok=True)
    job = replace(step, tag=tag, argv=step.prepare_argv, cwd=step.prepare_dir, inputs=[], outputs=[], products=[],
                  count_check=None, sidecar=None, sidecar_written=None, log=plan.out / f"{step.tag}.prepare.log",
                  stall_after=max(step.stall_after, 3600.0))
    ok, blamed, message = run_group(plan, [job], bus=bus, stopper=stopper, results=results, logs=logs, attempt=attempt)
    if not ok:
        return False, step.tag, message
    marker = step.folder.spec["prepare"].get("marker")
    if marker and not (step.prepare_dir / marker).exists():
        return False, step.tag, f"{tag} exited 0 but left no {marker} in {step.prepare_dir}"
    card = step.prepare_card or step.card_combined                 # the card it read: on disk, else as planned
    text = card.read_bytes() if card is not None and card.is_file() else plan.writes.get(card, "").encode("utf-8")
    sha = hashlib.sha256(text).hexdigest() if card is not None else ""
    if job.log is not None and job.log.is_file():
        shutil.copyfile(job.log, step.prepare_dir / PREPARE_LOG)
    write_atomic(stamp, json.dumps({"argv": job.argv, "finished": now(), "seconds": round(results[tag].seconds, 3),
                                    "card_sha256": sha, "record": portable(plan.folders.record) if plan.folders else "",
                                    "point": plan.point.name}, indent=1, default=str) + "\n")
    return True, "", ""


def _settle(group: list[Step], results: dict[str, ToolResult]) -> PointResult | None:
    """After a group succeeded: the count checks, then partial → final names. None when all is well."""
    for step in group:                           # [outputs] written = "requested": exit 0 means all of it
        if step.sidecar_written is not None and step.sidecar is not None:
            write_atomic(step.sidecar, json.dumps({"written": step.sidecar_written, "source": "requested",
                                                   "tool": step.tag}) + "\n")
    for step in group:
        if step.count_check is None:
            continue
        product, sidecar, reader, key = step.count_check
        counted = read_count(product, reader)
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            written = data["written_per_output"][key] if key else data["written"]   # a shard: its own share
        except (OSError, ValueError, KeyError, TypeError):
            written = None
        if counted is None or written is None or round(counted) != written:
            share = f" to {Path(key).name}" if key else ""
            message = (f"{step.tag} analysed {counted if counted is None else round(counted)} events; "
                       f"the producer wrote {written}{share} ({sidecar.name})")
            results.setdefault(step.tag, ToolResult(step.tag)).cause = "count"
            return PointResult(False, cause=step.tag, message=message, tools=results)
        results[step.tag].message = f"count ok: {written} events"
    for step in group:
        for final, partial in step.products:
            if report_of(partial).exists():          # a report travels with its product
                report_of(partial).replace(report_of(final))
            if partial.exists():
                partial.replace(final)
            elif not final.exists():
                results.setdefault(step.tag, ToolResult(step.tag)).cause = "missing"
                return PointResult(False, cause=step.tag, message=f"{step.tag} did not write {final.name}", tools=results)
    return None


def empty_analyses(group: list[Step]) -> list[tuple[str, str]]:
    """A tool folder's `[checks] filled` (V195): its products' histograms with any entry. None filled is said, never
    failed: the analysis vetoed every event the producer wrote (the count check counts what it saw). (tag, what to
    say) each: a warning of the tool's, recorded with its attempt (V200)."""
    notes = []
    for step in group:
        kind, _, prefix = str(step.folder.get("checks", "filled", "")).partition(":")
        if kind != "yoda":
            continue
        for final, _partial in step.products:
            got = hepfiles.filled(final, prefix or "/RAW/") if final.suffix == ".yoda" else None
            if got is not None and got[1] and not got[0]:
                notes.append((step.tag, f"no histogram filled (0 of {got[1]}) in {final.name}: every event was vetoed"))
    return notes


def _finished(plan: PointPlan, result: PointResult, bus, started: str = "") -> None:
    """A point ended: its attempt recorded (V200), then said."""
    verdict = "ok" if result.ok else "stopped" if result.stopped else "failed"
    blamed, cause = blame(result)
    try:
        append_attempt(plan, {"started": started, "finished": now(), "identity": plan.identity, "cards": card_hashes(plan),
                              "verdict": verdict, "cause": cause, "blamed": blamed, "message": result.message,
                              "tools": {tag: r.kept() for tag, r in result.tools.items()}})
    except OSError as error:                       # a record that cannot be written: said, never the run's end
        bus.emit(plan.point.name, "", {"k": "note", "msg": f"   its attempt could not be recorded: {error}"})
    bus.emit(plan.point.name, "", {"k": "point", "state": "done" if result.ok else verdict, "cause": result.cause,
                                   "msg": result.message, "res": str(plan.res),
                                   **({"stage": plan.point.stage} if plan.point.stage else {})})


def blame(result: PointResult) -> tuple[str, str]:
    """(the tool to blame, how it ended) for an attempt (V200): ("", "") when it went well, ("", "stopped") when
    the user stopped it, ("", "prelim") for [prelim]; a prepare step's failure blames "<tag>:prepare"."""
    if result.ok:
        return "", ""
    if result.stopped:
        return "", "stopped"
    if result.cause == "prelim":
        return "", "prelim"
    tag = result.cause
    for candidate in (f"{tag}:prepare", tag):          # a prepare step's run is under its own tag
        tool = result.tools.get(candidate)
        if tool is not None and (tool.cause or tool.exit not in (0, None)):
            return candidate, tool.cause or "failed"
    return tag, "failed"


def _tidy(plan: PointPlan) -> None:
    """A finished point's working folder keeps its cards/ and config/ and the logs written there
    (<tag>.log, V157); its scratch files, shards and what its tools left go, unless the run keeps `work`
    (V149). The lock stays: another session may hold it. Never outside its configuration's logs/."""
    if keeping("work") or plan.folders is None or plan.out.parent != plan.folders.logs or not plan.out.is_dir():
        return
    for entry in plan.out.iterdir():
        if entry.name in ("cards", "config", HISTORY, LOCK_FILE, COMMANDS_FILE, CONTEXT_FILE) or (entry.suffix == ".log" and entry.is_file()):
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink(missing_ok=True)


def _cleanup(plan: PointPlan) -> None:
    """FIFOs are removed when the point ends (04 §6); files are kept, the context file too (V187: every tool's
    card and config, the point's record)."""
    for interface in plan.interfaces.values():
        if interface.kind == "fifo" and interface.path.exists() and stat.S_ISFIFO(interface.path.stat().st_mode):
            interface.path.unlink()
