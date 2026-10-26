"""Status from running tools: the standard protocol and the stdout filter rules (rank 3).

docs/06_Internals.md §22 and docs/06_Internals.md §10.

* A tool with status = "standard" writes JSON lines to $HEP_STATUS_FD (src/Status.hh); a tool's
  output, its control sequences out, is matched against its filters.toml rules (progress, xsec, phase,
  warn, error, ignore). A rule never fails a run: the exit code does that. A progress line without a total
  takes the events the tool makes or reads; its rate is done / elapsed when the line says how long, else
  measured from the first count.
* Both are read from pipes by one thread per tool (V72), so a tool that prints fast never waits on a
  full pipe, and nothing of it is on disk unless asked: the last TAIL lines are kept in memory and
  written to the point's <tag>.log only when the tool fails; `--logs` writes every line as it comes.
* Nothing saved holds a terminal's clutter (V195): every line is cleaned (`clean`) before it is matched,
  shown or written, and a line a bare carriage return rewrote (a counter) is saved at its last state.
* Every message goes onto the run's event bus (events.py), tagged with its point and tool.
"""

from __future__ import annotations

import collections
import json
import os
import re
import selectors
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

TAIL = 200                       # a failed tool's last lines, written beside its point (V72)
LINE_EVERY = 0.5                 # seconds between a tool's `line` events
#: A terminal's escape sequences: a CSI (colours, cursor moves: Sherpa's ESC[1A and ESC[?25h), an OSC (a window
#: title), a character set's choice (ESC(B) and the two-character ones. Taken out of every line shown, matched or
#: saved (V195).
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b[()*+][0-9A-Za-z]|\x1b[@-_=>78]")
#: The control characters left after them: no saved text holds them either. A tab stays.
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean(line: str) -> str:
    """One line as it is shown, matched and saved: its escape sequences and control characters out."""
    return CONTROL.sub("", ANSI.sub("", line))


def clean_text(text: str) -> str:
    """Several lines (a command's captured output) cleaned: each line as `clean` leaves it, and a line a bare
    carriage return rewrote at its last state, as a terminal shows it."""
    return "\n".join(clean(line.removesuffix("\r").rsplit("\r", 1)[-1]) for line in text.split("\n"))
#: A duration as programs print it: "45.2s", "1.2e+06s", "17086", "2h 58m 30s", "1d 3h", "0:00:01".
_UNITS = {"d": 86400, "h": 3600, "m": 60, "min": 60, "s": 1}


def seconds_of(text: str) -> float | None:
    """A printed duration in seconds, or None when it is not one."""
    text = text.strip()
    try:
        return float(text.rstrip("s").strip())
    except ValueError:
        pass
    if re.fullmatch(r"\d+(?::\d{1,2}){1,2}", text):
        total = 0.0
        for part in text.split(":"):
            total = total * 60 + int(part)
        return total
    parts = re.findall(r"([\d.]+)\s*(d|h|min|m|s)\b", text)
    if not parts or "".join(f"{n}{u}" for n, u in parts) != re.sub(r"\s+", "", text):
        return None
    return sum(float(n) * _UNITS[u] for n, u in parts)


@dataclass
class ToolState:
    """What the watch view shows for one tool of one point."""
    point: str
    tag: str
    phase: str = ""
    done: int | None = None
    total: int | None = None
    rate: float | None = None
    xsec: tuple[float, float] | None = None
    warning: str = ""
    error: str = ""
    last_line: str = ""
    last_activity: float = field(default_factory=time.monotonic)
    running: bool = True
    exit: int | None = None


class Reader:
    """One process's status pipe (standard) and output pipe, read on a thread of its own until both end."""

    def __init__(self, state: ToolState, *, fd: int | None, out: int | None, rules: list[dict], bus,
                 log: Path | None = None, keep: bool = False, total: int | None = None):
        self.state = state
        self.total = total                # the events a tool makes or reads, when its lines do not say
        self._first: tuple[float, int] | None = None   # (when, count) of its first progress line: the rate
        self.rules = [(re.compile(r["match"]), r) for r in rules]
        self.bus = bus
        self.log, self.keep = log, keep
        self.tail: collections.deque = collections.deque(maxlen=TAIL)
        self._fds = [f for f in (fd, out) if f is not None]
        self._status_fd, self._out_fd = fd, out
        self._partial = {f: b"" for f in self._fds}
        self._line_at = 0.0
        if keep and log is not None:
            log.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(log, "ab") if keep and log is not None else None
        self._thread = threading.Thread(target=self._loop, name=f"hep-read-{state.tag}", daemon=True)
        if self._fds:
            self._thread.start()

    def _emit(self, message: dict) -> None:
        apply(self.state, message)
        if self.bus is not None:
            self.bus.emit(self.state.point, self.state.tag, message)

    def _loop(self) -> None:
        selector = selectors.DefaultSelector()
        for fd in self._fds:
            selector.register(fd, selectors.EVENT_READ)
        open_fds = set(self._fds)
        while open_fds:
            for key, _ in selector.select(timeout=1.0):
                try:
                    chunk = os.read(key.fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    selector.unregister(key.fd)
                    open_fds.discard(key.fd)
                    self._lines(key.fd, b"", final=True)
                    continue
                self.state.last_activity = time.monotonic()
                self._lines(key.fd, chunk)
        selector.close()
        for fd in self._fds:
            try:
                os.close(fd)
            except OSError:
                pass
        if self._handle is not None:
            self._handle.close()

    def _lines(self, fd: int, chunk: bytes, final: bool = False) -> None:
        data = self._partial[fd] + chunk
        if fd == self._status_fd:
            *lines, self._partial[fd] = data.split(b"\n")
            for line in lines:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict) and "k" in message:
                    self._emit(message)
            return
        held = b""
        if final and data.endswith(b"\r"):              # a counter the tool left on its line: its last state
            data = data[:-1] + b"\n"
        elif data.endswith(b"\r"):                      # a \r\n the read cut in two waits for its \n
            data, held = data[:-1], b"\r"
        pieces = re.split(rb"(\r\n|\r|\n)", data)       # line, its end, line, its end, …, the unfinished rest
        self._partial[fd] = pieces.pop() + held
        if final and self._partial[fd]:
            pieces += [self._partial[fd], b"\n"]
            self._partial[fd] = b""
        for raw, end in zip(pieces[::2], pieces[1::2]):
            self.output(raw.decode("utf-8", "replace"), rewritten=end == b"\r")   # \r: a counter, rewritten
        if self._handle is not None:
            self._handle.flush()

    def output(self, text: str, rewritten: bool = False) -> None:
        """One line the tool printed, cleaned: the whole log (`--logs`), the tail, the latest line, and its
        filter rules, the first that matches. A line a carriage return `rewritten` (a counter's) is matched
        and shown, and neither saved nor kept: the log and the tail keep the state a terminal shows."""
        text = clean(text)
        if self._handle is not None and not rewritten:
            self._handle.write(text.encode("utf-8") + b"\n")
        if text.strip():
            if not rewritten:
                self.tail.append(text)
            self.state.last_line = text.strip()[:200]
            now = time.monotonic()
            if self.bus is not None and now - self._line_at >= LINE_EVERY:
                self._line_at = now
                self.bus.emit(self.state.point, self.state.tag, {"k": "line", "msg": self.state.last_line})
        for pattern, rule in self.rules:
            match = pattern.search(text)
            if match is None:
                continue
            self._rule(rule, match, text)
            break

    def join(self, timeout: float = 2.0) -> None:
        """Wait for the pipes to end (a child that keeps the tool's stdout open is not waited for)."""
        if self._thread.is_alive():
            self._thread.join(timeout)

    def keep_tail(self) -> Path | None:
        """A failed tool: its last lines to its <tag>.log (unless --logs wrote them all already)."""
        if self.log is None or self.keep:
            return self.log
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.log.write_text("".join(f"{line}\n" for line in self.tail), encoding="utf-8")
        return self.log

    def _rule(self, rule: dict, match: re.Match, text: str) -> None:
        """A matched rule's message. A progress rule may also capture `total`, `elapsed` (a duration: the
        rate is done / elapsed; otherwise it is measured from the first count on), `xsec` and `xsec_err`
        (pb); any rule may name a `phase` to enter when it matches."""
        emit = rule.get("emit", "ignore")
        try:
            groups = match.groupdict()
            if rule.get("phase") and emit != "phase" and self.state.phase != rule["phase"]:
                self._emit({"k": "phase", "phase": rule["phase"]})
            if emit == "progress":
                done = int(groups["done"].replace(",", "").replace(" ", ""))
                message = {"k": "progress", "done": done}
                if groups.get("total"):
                    message["total"] = int(groups["total"].replace(",", ""))
                elif self.total:
                    message["total"] = self.total
                elapsed = seconds_of(groups["elapsed"]) if groups.get("elapsed") else None
                now = time.monotonic()
                if elapsed is not None and elapsed > 0:
                    message["rate"] = done / elapsed
                elif self._first is None:
                    self._first = (now, done)
                elif now > self._first[0] and done > self._first[1]:
                    message["rate"] = (done - self._first[1]) / (now - self._first[0])
                self._emit(message)
                if groups.get("xsec"):
                    self._xsec(groups)
            elif emit == "xsec":
                self._xsec(groups)
            elif emit == "phase":
                self._emit({"k": "phase", "phase": rule.get("phase") or match.groupdict().get("phase") or match.group(0)})
            elif emit in ("warn", "error"):
                self._emit({"k": "log", "level": emit, "msg": text.strip()[:300]})
        except (KeyError, ValueError, AttributeError, TypeError, ZeroDivisionError):
            pass                                                     # a rule never fails a run

    def _xsec(self, groups: dict) -> None:
        message = {"k": "xsec", "value_pb": float(groups["xsec"])}
        if groups.get("xsec_err"):
            message["err_pb"] = float(groups["xsec_err"])
        self._emit(message)


def apply(state: ToolState, message: dict) -> None:
    state.last_activity = time.monotonic()
    kind = message.get("k")
    if kind == "phase":
        state.phase = str(message.get("phase", ""))
    elif kind == "progress":
        state.done = message.get("done", state.done)
        state.total = message.get("total", state.total)
        state.rate = message.get("rate", state.rate)
    elif kind == "xsec":
        state.xsec = (message.get("value_pb"), message.get("err_pb"))
    elif kind == "log":
        if message.get("level") == "error":
            state.error = str(message.get("msg", ""))
        elif message.get("level") in ("warn", "warning"):
            state.warning = str(message.get("msg", ""))
    elif kind == "line":
        state.last_line = str(message.get("msg", ""))
