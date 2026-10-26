"""What the user sees while points run (rank 4).

docs/06_Internals.md §10, V72. A view hears the run's events (events.py) and nothing else: one
reducer, `State`, turns them into points and their tools, and the views render it, the same whether the
events come from the run in this process, from its watch socket (`heimdall watch`), or from a --journal file.

* `LiveView` (rich, on a terminal): each running point under its heading and time so far, one line
  per running tool — tool, phase, a bar, the count, rate and ETA — and its last warning on a line of its
  own under it, with each finished point printed above it.
* `PlainView` (a pipe, a log file, or `--plain`): one block per point when it ends, and a progress line
  every few seconds while it runs.

**A view never blocks the run.** Everything a view prints goes through `_Screen`, one background thread:
an event only queues a line, and the screen's own clock redraws, so a terminal that stops reading
(paused, Ctrl-S) stops the display, never the run (V32).
"""

from __future__ import annotations

import json
import os
import queue
import selectors
import signal
import sys
import threading
import time
from pathlib import Path

from .status import LEVELS, ToolState, apply, clean_text


def _count(value) -> str:
    if value is None:
        return "?"
    return f"{value / 1e6:.2f}M" if value >= 1e6 else f"{value / 1e3:.1f}k" if value >= 1e4 else str(value)


def duration(seconds: float) -> str:
    """'42.3s', '4min 12s', '2h 58min 7s': how long a point or a tool took."""
    if seconds < 59.95:
        return f"{seconds:.1f}s"
    hours, rest = divmod(round(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}h {minutes}min {secs}s" if hours else f"{minutes}min {secs}s"


def finished_at(t: float) -> str:
    """'Tue 21 Oct 14:03': when a point ended, local time, for its block's heading."""
    return time.strftime("%a %d %b %H:%M", time.localtime(t))


def clock(seconds: float) -> str:
    """'00:42', '49:11', '09:47:17', '103:02:09': a running point's time so far, or an ETA; the hours
    only once there are some."""
    hours, rest = divmod(int(max(0.0, seconds)), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _eta(state) -> str:
    if state.done and state.total and state.rate:
        return clock((state.total - state.done) / state.rate)
    return ""


def progress_text(state) -> str:
    parts = [f"{state.tag}"]
    if state.phase:
        parts.append(state.phase)
    if state.done is not None:
        parts.append(f"{_count(state.done)}/{_count(state.total)}" if state.total else _count(state.done))
    if state.rate:
        parts.append(f"{state.rate:,.0f}/s")
    if _eta(state):
        parts.append(f"ETA {_eta(state)}")
    return " ".join(parts)


SHOWN = 3                                       # a block's distinct warnings (errors) shown, at most (V200)


def signals_line(name: str, said: dict[tuple[str, str], int]) -> str:
    """A block's line for what its tools warned of (or erred), V200: "   warnings: 3 (sherpa 2, rivet 1): <msg>
    (×2); <msg>", the most frequent SHOWN first; "" for none."""
    if not said:
        return ""
    total = sum(said.values())
    by_tool: dict[str, int] = {}
    for (tag, _), count in said.items():
        by_tool[tag or "run"] = by_tool.get(tag or "run", 0) + count
    first = sorted(said.items(), key=lambda kv: -kv[1])[:SHOWN]
    shown = "; ".join(f"{text[:110]}{' (×' + str(count) + ')' if count > 1 else ''}" for (_, text), count in first)
    more = " …" if len(said) > SHOWN else ""
    tools = ", ".join(f"{tag} {count}" for tag, count in by_tool.items())
    return f"   {name}: {total} ({tools}): {shown}{more}"


# ── the reducer ───────────────────────────────────────────────────────────────────────────────

class _Point:
    """One running point: its heading (prefix and name, so a view can embolden the name), when it
    started, the lines its block will carry, and its tools."""

    def __init__(self, prefix: str, name: str, started: float):
        self.prefix, self.name, self.started = prefix, name, started
        self.notes: list[str] = []
        self.failed: list[str] = []
        self.states: list[ToolState] = []
        self.last = 0.0                              # the plain view's last progress line
        self.said: dict[str, dict[tuple[str, str], int]] = {"warn": {}, "error": {}}   # (tool, message) → count (V200)

    @property
    def heading(self) -> str:
        return self.prefix + self.name


class State:
    """Events in, what to print out: `apply` returns ("title", header, title), ("say", text) and
    ("block", point, verdict, seconds, lines, finished) items. Points are numbered in the order they start, per run;
    in a sweep of runs (events with `run`, V75) a heading names its run, since a pipelined sweep's runs
    overlap and two runs have points of the same name."""

    def __init__(self):
        self.total: dict[str, int] = {}
        self.number: dict[str, int] = {}
        self.points: dict[tuple[str, str], _Point] = {}

    def _heading(self, event: dict) -> tuple[str, str]:
        name, index, run = event["point"], event.get("index", 1), event.get("run", "")
        of = f" ({run})" if run else ""
        if event.get("stage") == "combined":
            return f"── combined{of}: ", name
        if index == 0:
            return f"── post (after every point){of}", ""
        if index < 0:
            return f"── pre (before every point){of}", ""
        self.number[run] = self.number.get(run, 0) + 1
        return f"── point {self.number[run]}/{self.total.get(run) or '?'}{of}: ", name

    def _state(self, key: tuple[str, str], tag: str) -> ToolState | None:
        part = self.points.get(key)
        if part is None:
            return None
        found = next((s for s in part.states if s.tag == tag), None)
        if found is None:
            found = ToolState(point=key[1], tag=tag)
            part.states.append(found)
        return found

    def apply(self, event: dict) -> list[tuple]:
        kind, point, tag, run = event.get("k"), event.get("point", ""), event.get("tool", ""), event.get("run", "")
        key = (run, point)
        if kind == "run":
            if event.get("state") == "started":
                self.total[run], self.number[run] = event.get("points", 0), 0
                if not run:                              # a run of its own: a new start
                    self.points = {}
                return [("title", event.get("header", ""), event.get("title", ""))]
            return []
        if kind == "say":
            return [("say", event.get("msg", ""))]
        if kind == "point":
            state = event.get("state")
            if state == "started":
                prefix, name = self._heading(event)
                self.points[key] = _Point(prefix, name, event.get("t", time.time()))
                return []
            if state == "skipped":
                prefix, name = self._heading(event)
                return [("say", f"{prefix}{name}: {event.get('msg') or 'complete, skipped (--rerun to run it again)'}")]
            ended = event.get("t", time.time())
            part = self.points.pop(key, None) or _Point("── ", point, ended)
            seconds = ended - part.started
            shown = {(s.tag, s.error) for s in part.states if s.exit not in (0, None) and s.error}   # on its exit line
            errors = {k: n for k, n in part.said["error"].items() if k not in shown}
            said = [line for name, kept in (("errors", errors), ("warnings", part.said["warn"]))
                    if (line := signals_line(name, kept))]
            if state == "done":
                return [("block", part, "ok", seconds, [*part.notes, *said, f"   done → {event.get('res', '')}"], ended)]
            if state == "stopped":
                return [("block", part, "stopped", seconds, [*part.notes, *part.failed, *said,
                                                             "   partial outputs keep their .partial names"], ended)]
            blame = f" [{event['cause']}]" if event.get("cause") else ""
            return [("block", part, f"FAILED{blame}", seconds,
                     [*part.notes, *part.failed, *said, f"   {event.get('msg', '')}"], ended)]
        part = self.points.get(key)
        if kind == "note":
            if part is not None:
                part.notes.append(event.get("msg", ""))
            return []
        if kind == "tool":
            self._state(key, tag)
            return []
        tool = self._state(key, tag)
        if tool is None:
            return []
        if kind == "log" and (level := LEVELS.get(str(event.get("level", "")))):
            said = part.said[level]
            said[(tag, str(event.get("msg", "")))] = said.get((tag, str(event.get("msg", ""))), 0) + 1
        if kind == "exit":
            tool.running, tool.exit = False, event.get("code")
            verdict = "ok" if event.get("code") == 0 else f"exit {event.get('code')}"
            if tag.endswith(":prepare"):
                part.notes.append(f"   {tag}: {verdict} after {duration(event.get('seconds', 0))}")
            elif event.get("code") != 0:
                extra = f"  ({tool.error})" if tool.error else ""
                part.failed.append(f"   {tag}: {verdict} after {duration(event.get('seconds', 0))}{extra}")
            return []
        apply(tool, event)
        return []

    def running(self) -> list[_Point]:
        return list(self.points.values())


# ── the screen ────────────────────────────────────────────────────────────────────────────────

class _Screen:
    """The one thread that talks to the terminal. `line()` queues a line and `frame()` replaces the
    latest live frame; neither waits. `tick`, if given, is called on the thread every half second.
    `close()` flushes for at most `timeout` seconds: a terminal that has stopped reading cannot keep the
    process from ending."""

    def __init__(self, write, update=None, start=None, stop=None, tick=None):
        self._write, self._update, self._start, self._stop_live, self._tick = write, update, start, stop, tick
        self._lines: queue.SimpleQueue = queue.SimpleQueue()
        self._frame = None
        self._wake = threading.Event()
        self._closing = False
        self._broken = False                     # the stream went away (a closed pipe): stop writing
        self._queued = self._done = 0            # lines queued (the caller) and written (the thread)
        self._thread = threading.Thread(target=self._loop, name="hep-view", daemon=True)
        self._thread.start()

    def line(self, text: str) -> None:
        self._queued += 1
        self._lines.put(text)
        self._wake.set()

    def drain(self, timeout: float = 3.0) -> bool:
        """Wait until every queued line is written (tests, and anything reading the stream after)."""
        until = time.monotonic() + timeout
        while self._done < self._queued and time.monotonic() < until and self._thread.is_alive():
            self._wake.set()
            time.sleep(0.01)
        return self._done >= self._queued

    def frame(self, renderable) -> None:
        self._frame = renderable
        self._wake.set()

    def _call(self, function, *args) -> None:
        if function is None or self._broken:
            return
        try:
            function(*args)
        except (OSError, ValueError):
            self._broken = True

    def _loop(self) -> None:
        self._call(self._start)
        while True:
            self._wake.wait(0.5)
            self._wake.clear()
            while True:
                try:
                    text = self._lines.get_nowait()
                except queue.Empty:
                    break
                self._call(self._write, text)
                self._done += 1
            if self._tick is not None and not self._closing:
                try:
                    self._tick()
                except Exception:                # a drawing error never stops the screen
                    pass
            latest, self._frame = self._frame, None
            if latest is not None:
                self._call(self._update, latest)
            if self._closing and self._lines.empty():
                self._call(self._stop_live)
                return

    def close(self, timeout: float = 3.0) -> None:
        self._closing = True
        self._wake.set()
        self._thread.join(timeout)


# ── the views ─────────────────────────────────────────────────────────────────────────────────

class PlainView:
    """One block per point, printed when it ends: its heading with the verdict, wall time and when it
    ended, a blank line, only what needs saying (a failed tool, a prepare step) and where the results
    are, and a blank line:

        ── point 2/4: NNPDF23lo ── ok after 1min 12s at Tue 21 Oct 14:03

           done → results/Demo/validation/default/NNPDF23lo


    While a point runs, a progress line every few seconds (the live view draws a table instead)."""

    bold = False

    def __init__(self, stream=None, every: float = 5.0):
        self.stream = stream or sys.stdout
        self.every = every
        self.state = State()
        self.hint = ""
        self._lock = threading.RLock()
        self.screen = self._screen()

    def keys(self, hint: str) -> None:
        """The keys a watcher may press (V183): said once here; the live view keeps them under its frame."""
        if hint and hint != self.hint:
            self.say(hint)
        self.hint = hint

    def _screen(self) -> _Screen:
        def write(text: str) -> None:
            print(text, file=self.stream, flush=True)
        return _Screen(write, tick=self._tick)

    def event(self, event: dict) -> None:
        """A bus subscriber: never blocks (the screen thread prints)."""
        with self._lock:
            for item in self.state.apply(event):
                self._show(item)

    def say(self, text: str) -> None:
        self.screen.line(clean_text(text))       # a worker's log is saved text: no terminal clutter (V195)

    def flush(self) -> None:
        self.screen.drain()

    def end(self) -> None:
        self.screen.close()

    def _show(self, item: tuple) -> None:
        if item[0] == "title":                    # a header, then the title: its first line bold, the rest as said
            for text in item[1:]:
                for number, line in enumerate(text.split("\n") if text else []):
                    self.say(self._title(line) if number == 0 else self._text(line))
        elif item[0] == "say":
            self.say(self._text(item[1]))
        else:
            _, part, verdict, seconds, lines, ended = item
            for line in self._block(part, verdict, seconds, lines, ended):
                self.say(line)

    def _title(self, line: str) -> str:
        return line

    def _text(self, line: str) -> str:
        """A line of the run's, as this view prints it."""
        return line

    def _block(self, part: _Point, verdict: str, seconds: float, lines: list[str], ended: float) -> list[str]:
        return [f"{part.heading} ── {verdict} after {duration(seconds)} at {finished_at(ended)}", "", *lines, ""]

    def _tick(self) -> None:
        now = time.monotonic()
        with self._lock:
            for part in self.state.running():
                running = [s for s in part.states if s.running]
                if not running or now - part.last < self.every:
                    continue
                part.last = now
                line = " | ".join(progress_text(s) if (s.phase or s.done is not None) else f"{s.tag} … {s.last_line[:60]}"
                                  for s in running)
                self.say(f"   [{part.name or part.prefix.strip('─ ')}] {line}")


class LiveView(PlainView):
    """The rich version: the same blocks, and under them each running point: its heading and time so
    far, then its running tools, one line each, and a tool's last warning or error on a line of its own
    under its row (a tool with no count yet shows its last line there, dim):

        ── point 3/4: MSTW08lo ── ok after 9h 12min 4s at Tue 21 Oct 14:03

           done → results/Demo/validation/default/MSTW08lo

        point 4/4: PDF4LHC21 · 01:03:17
           pythia   generating ━━━━━━━━━━━━━━━━━━━━━━━━ 1.70M/10.00M 2,812/s 49:11
           rivet.12 analysing  ⠸                        1.70M
              ↳ WARN unvalidated analysis

    The columns line up across points; a blank line parts two running points."""

    SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    BAR = 24
    bold = True

    def __init__(self):
        from rich.console import Console
        from rich.live import Live
        self.console = Console()
        self.live = Live(console=self.console, refresh_per_second=4, transient=True)
        self.frame = 0
        super().__init__()

    def _screen(self) -> _Screen:            # rich's Live starts, prints, redraws and stops on the thread
        return _Screen(lambda text: self.console.print(text, highlight=False),
                       update=self.live.update, start=self.live.start, stop=self.live.stop, tick=self._tick)

    def _title(self, line: str) -> str:
        from rich.markup import escape
        return f"[bold]{escape(line)}[/bold]"

    def _text(self, line: str) -> str:
        """Escaped: a message's own brackets (`[quantities.pdf]`) are text, not rich's markup (V195)."""
        from rich.markup import escape
        return escape(line)

    def _block(self, part: _Point, verdict: str, seconds: float, lines: list[str], ended: float) -> list[str]:
        from rich.markup import escape
        colour = "green" if verdict == "ok" else "yellow" if verdict == "stopped" else "red"
        heading = part.prefix + (f"[bold]{part.name}[/bold]" if part.name else "")
        return [f"{heading} ── [{colour}]{verdict}[/{colour}] after {duration(seconds)} at {finished_at(ended)}", "",
                *(escape(line) for line in lines), ""]

    def _tick(self) -> None:
        with self._lock:
            self.frame += 1
            self.screen.frame(self.render())

    def keys(self, hint: str) -> None:
        self.hint = hint

    def _rows(self, states) -> list[tuple[list, tuple[str, str] | None]]:
        """A line per running tool, (tool, phase, bar, count, rate and ETA), with the note for the line
        under it: (text, style), or None."""
        from rich.markup import escape
        from rich.progress_bar import ProgressBar
        rows = []
        for s in states:
            if not s.running:
                continue
            spinner = self.SPIN[self.frame % len(self.SPIN)]
            if s.done is not None and s.total:
                bar = ProgressBar(total=s.total, completed=min(s.done, s.total), width=self.BAR)
                count = f"{_count(s.done)}/{_count(s.total)}"
            elif s.done is not None:
                bar, count = spinner, _count(s.done)
            else:
                bar, count = spinner, ""
            rate = f"{s.rate:,.0f}/s" if s.rate else ""
            note = ((s.error, "red") if s.error else (s.warning, "yellow") if s.warning
                    else (s.last_line, "dim") if s.last_line and s.done is None else None)
            rows.append(([f"[bold]{s.tag}[/bold]", escape(s.phase or ""), bar, count, f"{rate} {_eta(s)}".strip()], note))
        return rows

    def _width(self, cell) -> int:
        from rich.text import Text
        if not isinstance(cell, str):
            return self.BAR
        try:
            return Text.from_markup(cell).cell_len
        except Exception:                        # a tool's text that looks like markup
            return len(cell)

    def render(self):
        from rich.console import Group
        from rich.table import Table
        from rich.text import Text
        now = time.time()
        sections = [(f"{part.prefix.replace('── ', '')}{f'[bold]{part.name}[/bold]' if part.name else ''} · "
                     f"{clock(now - part.started)}", self._rows(part.states)) for part in self.state.running()]
        widths: list[int] = []
        for _, rows in sections:
            for row, _ in rows:
                for i, cell in enumerate(row[:-1]):      # the last column needs no width
                    if i == len(widths):
                        widths.append(0)
                    widths[i] = max(widths[i], self._width(cell))
        shown = []
        for number, (heading, rows) in enumerate(sections):
            if number:                           # a finished block ends in a blank line; two points are parted by one
                shown.append(Text(""))
            shown.append(Text.from_markup(heading))
            for row, note in rows:               # a grid per row, padded alike, so a note under it moves no column
                table = Table.grid(padding=(0, 1))
                cells = [cell + " " * (width - self._width(cell)) if isinstance(cell, str) else cell
                         for cell, width in zip(row, widths)] + row[len(widths):]
                cells[0] = "   " + cells[0]      # the tools sit under their point, like a block's lines
                table.add_row(*cells)
                shown.append(table)
                if note is not None:
                    shown.append(Text(f"      ↳ {note[0]}", style=note[1], no_wrap=True, overflow="ellipsis"))
        if self.hint:                            # the keys (V183), under everything
            if shown:
                shown.append(Text(""))
            shown.append(Text(self.hint, style="dim"))
        return Group(*shown)


def view(plain: bool = False, every: float = 5.0) -> PlainView:
    """The live view on a terminal (when rich is there), plain lines otherwise (a progress line each `every`
    seconds: a detached run's log takes one a minute)."""
    if not plain and sys.stdout.isatty():
        try:
            return LiveView()
        except ImportError:
            pass
    return PlainView(every=every)


# ── heimdall watch ─────────────────────────────────────────────────────────────────────────────────

# ── keys, and following a run's socket (V183) ──────────────────────────────────────────────────

class Keys:
    """A terminal's keys, one at a time, unechoed (cbreak: ICANON and ECHO off, so a key needs no Enter and does
    not garble the view; ISIG kept, so Ctrl-C is still SIGINT; output untouched). The terminal is put back on
    leaving, at exit, on SIGTERM (then the default), on Ctrl-Z (and set again on fg). A process killed by
    SIGKILL cannot: `reset` mends the terminal."""

    def __init__(self, source):
        self.source = source                    # a file descriptor, or a stream (stdin)
        self.fd = -1
        self._saved = None
        self._handlers: dict = {}

    def __enter__(self) -> "Keys":
        import atexit
        import termios
        self.fd = self.source if isinstance(self.source, int) else self.source.fileno()
        self._saved = termios.tcgetattr(self.fd)
        self._cbreak()
        atexit.register(self.restore)
        if threading.current_thread() is threading.main_thread():
            for signum, handler in ((signal.SIGTERM, self._on_term), (signal.SIGTSTP, self._on_stop),
                                    (signal.SIGCONT, self._on_continue)):
                self._handlers[signum] = signal.signal(signum, handler)
        return self

    def _cbreak(self) -> None:
        import termios
        mode = termios.tcgetattr(self.fd)
        mode[3] &= ~(termios.ICANON | termios.ECHO)
        mode[6][termios.VMIN], mode[6][termios.VTIME] = 1, 0
        termios.tcsetattr(self.fd, termios.TCSANOW, mode)

    def restore(self) -> None:
        import termios
        if self._saved is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)
            except (OSError, termios.error):
                pass

    def _on_term(self, signum, frame) -> None:
        self.restore()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def _on_stop(self, signum, frame) -> None:
        self.restore()
        signal.signal(signal.SIGTSTP, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTSTP)

    def _on_continue(self, signum, frame) -> None:
        signal.signal(signal.SIGTSTP, self._on_stop)
        try:
            if os.tcgetpgrp(self.fd) == os.getpgrp():
                self._cbreak()
        except OSError:
            pass

    def __exit__(self, *exc) -> None:
        self.restore()
        for signum, handler in self._handlers.items():
            signal.signal(signum, handler)
        self._saved = None


def follow(source, *, plain: bool = False, keys: int | None = None, on_key=None, on_interrupt=None, proc=None,
           hint: str = "", every: float = 5.0) -> str:
    """Drive a view from a run's watch socket (V183), with keys. `source`: a connected socket, or a callable
    giving one or None (a worker that has not opened its socket yet), tried again while `proc` lives. `keys`:
    a file descriptor to read keys from (a terminal in cbreak, or a pipe in tests), each passed to
    `on_key(key, view)`; a SIGINT here (or a Ctrl-C byte from a pipe) calls `on_interrupt(view)`. Either may
    return how following ends. Returns "ended" (the run's stream ended), "dropped" (this watcher fell behind),
    "gone" (the worker ended before it had a socket), or what a key returned ("detached")."""
    from .events import Lines
    shown = view(plain, every)
    shown.keys(hint)
    interrupted = threading.Event()
    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGINT, lambda signum, frame: interrupted.set())
    selector = selectors.DefaultSelector()
    if keys is not None:
        selector.register(keys, selectors.EVENT_READ, "keys")
    sock, lines = None, Lines()
    try:
        while True:
            if sock is None:
                sock = source() if callable(source) else source
                if sock is not None:
                    selector.register(sock, selectors.EVENT_READ, "events")
                elif proc is not None and proc.poll() is not None:
                    return "gone"
            if interrupted.is_set():
                interrupted.clear()
                if on_interrupt is not None and (outcome := on_interrupt(shown)):
                    return outcome
            for key, _ in selector.select(0.1 if sock is None else 0.25):
                if key.data == "keys":
                    pressed = os.read(keys, 1)
                    if not pressed:                       # the key source closed: keys no more
                        selector.unregister(keys)
                        keys = None
                        continue
                    if pressed == b"\x03":                 # Ctrl-C as a byte (a pipe, a raw terminal)
                        interrupted.set()
                        continue
                    if on_key is not None and (outcome := on_key(pressed.decode("utf-8", "replace"), shown)):
                        return outcome
                    continue
                data = sock.recv(65536)
                if not data:
                    return "ended"
                for event in lines.feed(data):
                    if event.get("k") == "dropped":
                        return "dropped"
                    if event.get("k") != "hello":
                        shown.event(event)
    except OSError as error:
        shown.say(f"the run's watch socket went away ({error})")
        return "ended"
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT, previous)
        selector.close()
        if sock is not None:
            sock.close()
        shown.end()


def socket_of(pid: int):
    """A callable for follow(): the watch socket of process `pid` once it has one, else None."""
    from .events import hubs, open_stream, pid_of

    def connect():
        for name in hubs():
            if pid_of(name) == pid:
                try:
                    return open_stream(name, timeout=1.0)
                except OSError:
                    return None
        return None
    return connect


def started(pid: int, proc, timeout: float | None = None) -> dict | None:
    """--detach (V183): wait until worker `pid` has said its run started (its greeting, or None when it ended
    first)."""
    from .events import Lines
    connect = socket_of(pid)
    until = None if timeout is None else time.monotonic() + timeout
    hello, sock = None, None
    while sock is None:
        if proc.poll() is not None or (until is not None and time.monotonic() > until):
            return None
        sock = connect()
        if sock is None:
            time.sleep(0.1)
    with sock:
        lines = Lines()
        while True:
            data = sock.recv(65536)
            if not data:
                return hello if proc.poll() is None else None
            for event in lines.feed(data):
                if event.get("k") == "hello":
                    hello = event
                elif event.get("k") == "run" and event.get("state") in ("started", "finished"):
                    return hello


def tail(path: Path, lines: int = 40) -> list[str]:
    """A log's last lines."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def follow_events(events, *, plain: bool = False) -> int:
    """Drive a view from an iterator of events (a watch socket's) until it ends."""
    shown = view(plain)
    try:
        for event in events:
            if event.get("k") != "hello":
                shown.event(event)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        shown.say(f"the run's watch socket went away ({error})")
    finally:
        shown.end()
    return 0


def follow_file(journal: Path, *, plain: bool = False, idle_exit: float = 0.0) -> int:
    """`heimdall watch --file`: a --journal run's status.jsonl, followed until the run says it finished (or
    `idle_exit` seconds of silence). A run of a sweep of runs names the next one's journal when it
    finishes: follow on to it."""
    shown = view(plain)
    offset, last = 0, time.monotonic()
    try:
        while True:
            size = journal.stat().st_size if journal.exists() else 0
            if size < offset:                     # the next run began the file afresh
                offset = 0
            if size > offset:
                with open(journal, encoding="utf-8") as handle:
                    handle.seek(offset)
                    chunk = handle.read()
                complete = chunk[:chunk.rfind("\n") + 1]
                offset += len(complete.encode("utf-8"))
                last = time.monotonic()
                for line in complete.splitlines():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    shown.event(event)
                    if event.get("k") == "run" and event.get("state") == "finished":
                        if not event.get("next"):
                            return 0
                        journal, offset = Path(event["next"]), 0
                        break
            if idle_exit and time.monotonic() - last > idle_exit:
                shown.say(f"no status for {idle_exit:.0f} s; leaving")
                return 0
            time.sleep(0.25)
    except KeyboardInterrupt:
        return 0
    finally:
        shown.end()
