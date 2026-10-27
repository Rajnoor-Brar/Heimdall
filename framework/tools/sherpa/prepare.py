"""framework/tools/sherpa/prepare.py — Sherpa's prepare step (tool.toml [prepare]): the integration, with
Amegic's compile in between when the card uses Amegic. Run in the cache entry, as
`python3 prepare.py <Sherpa's argv…>`; Sherpa's output passes through unchanged (filters.toml reads it).

* Amegic writes C++ for its processes on Sherpa's first run, copies `makelibs` beside it and stops with exit 0
  ("Source code created in … Run './makelibs' there to compile."). Then this compiles (`./makelibs -j N`, N
  from $HEIMDALL_MAKELIBS_JOBS, default 1: every point of a sweep may be compiling at once) and runs Sherpa again,
  until a run asks for no more (at most PASSES runs). A card without Amegic is one run, as before.
* Sherpa also exits 0 when it sets up no process at all ("No hard process found": the process's incoming
  particles do not match the beams, say). A run that ends without asking to compile and without its Results
  ends here with an `Error:` line and exit 3; Sherpa's reason is in the lines above, which the folder's
  filters.toml reads (its `reason` rules: the runner quotes the last in the failure, V203).
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
from pathlib import Path

PASSES = 4
JOBS_VAR = "HEIMDALL_MAKELIBS_JOBS"
COMPILE = re.compile(r"Run '\./makelibs'")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def run(argv: list[str]) -> tuple[int, bool]:
    """One command, its output passed through as it comes (a progress line ended by a carriage return too: the
    runner reads activity from it); its exit code, and whether Sherpa asked for Amegic's compile."""
    asked = False
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, pending = sys.stdout.buffer, b""

    def scan(lines: list[bytes]) -> None:
        nonlocal asked
        for raw in lines:
            if COMPILE.search(ANSI.sub("", raw.decode("utf-8", errors="replace"))):
                asked = True

    fd = process.stdout.fileno()
    while chunk := os.read(fd, 65536):
        out.write(chunk)
        out.flush()
        *lines, pending = re.split(rb"[\r\n]", pending + chunk)
        scan(lines)
    scan([pending])
    process.stdout.close()
    return process.wait(), asked


def code_of(returncode: int) -> int:
    """A child's exit as this process's: a signal N as 128+N, as a shell would."""
    return 128 - returncode if returncode < 0 else returncode


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: prepare.py <Sherpa argv…>", file=sys.stderr)
        return 2
    # Stopping is the runner's: it signals the whole process group, Sherpa included. This process waits for
    # Sherpa to end and passes its exit on, rather than dying first and leaving its output half read.
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: None)
    results = Path.cwd() / "Results.zip"
    for _ in range(PASSES):
        code, compile_asked = run(argv)
        if code != 0:
            return code_of(code)
        if not compile_asked:
            if results.exists():
                return 0
            print("Error: Sherpa ended without its Results: it set up no process (its reason is in the lines above)",
                  flush=True)
            return 3
        jobs = os.environ.get(JOBS_VAR, "1")
        print(f"prepare.py: compiling Amegic's processes (./makelibs -j {jobs}), then Sherpa again", flush=True)
        code, _ = run(["bash", "./makelibs", "-j", jobs])
        if code != 0:
            print(f"Error: ./makelibs failed (exit {code_of(code)})", flush=True)
            return code_of(code)
    print(f"Error: Sherpa still asked for compiling after {PASSES} runs", flush=True)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
