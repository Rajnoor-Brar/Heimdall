"""recipes/verify.py — what a built package can do, checked: the `verify` entries of packages.toml, and a
scan of every program and library for libraries that no longer resolve (docs/audit_3/01_Process.md E, I).

build_stack.py runs a package's checks right after it installs it; `hep doctor` runs them all. Standard
library only, like build_stack.py. Each check gives one row: (package, check, result, note), with result
ok, MISSING, FAIL or n/a.

A verify entry (`[[<package>.verify]]` in packages.toml) has a `name` and one of:
  command = "…"     a command line (split like a shell's); ok when it exits 0, its output matches
                    `expect` (a regular expression) when given, and holds every word of `has`
  python  = "…"     Python code run by the venv's interpreter; the same `expect` and `has`
  files   = [glob]  each pattern matches at least one file
  links   = [glob]  the programs and libraries they match link every name in `has` (ldd, otool -L)
and `slow = true` for a run that takes minutes (skipped by --quick, and after a build).
Every string takes the placeholders of build_stack.py ({install}, {inst}, {dylib}, {venv}, {pdf_sets} …).
"""

from __future__ import annotations

import glob
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

KINDS = ("command", "python", "files", "links")
#: Libraries a module gets from the program that loads it: a Python extension's libpython comes from the
#: interpreter that imports it (a standalone CPython has none on disk), so it is not "unresolved".
PROVIDED = re.compile(r"libpython\d")
KEYS = {"name", "expect", "has", "slow", *KINDS}
MAC = sys.platform == "darwin"
Row = tuple[str, str, str, str]


def problems(name: str, entries) -> list[str]:
    """What is wrong with a package's verify entries (build_stack.py refuses a recipe with any)."""
    out = []
    if not isinstance(entries, list):
        return [f"[{name}].verify must be a list of tables ([[{name}.verify]])"]
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("name"):
            out.append(f"[[{name}.verify]]: every entry needs a name")
            continue
        if unknown := sorted(set(entry) - KEYS):
            out.append(f"[[{name}.verify]] {entry['name']}: no key {', '.join(unknown)}")
        if sum(kind in entry for kind in KINDS) != 1:
            out.append(f"[[{name}.verify]] {entry['name']}: give exactly one of {', '.join(KINDS)}")
    return out


def _output(argv: list[str], env: dict[str, str], cwd: str, timeout: float) -> tuple[int, str]:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=cwd, timeout=timeout,
                              stdin=subprocess.DEVNULL)
        return done.returncode, (done.stdout + done.stderr)
    except FileNotFoundError:
        return 127, f"{argv[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout:.0f} s"
    except OSError as error:
        return 126, str(error)


def links_of(path: str) -> str:
    argv = ["otool", "-L", path] if MAC else ["ldd", path]
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def unresolved(path: str) -> list[str]:
    """The libraries a binary needs that do not resolve: ldd's "not found"; on macOS an absolute path
    not on disk, outside the system's shared cache."""
    text = links_of(path)
    if MAC:
        out = []
        for line in text.splitlines()[1:]:
            lib = line.strip().split(" ")[0]
            if lib and not lib.startswith(("/usr/lib/", "/System/", "@")) and not os.path.exists(lib):
                out.append(lib)
        return [lib for lib in out if not PROVIDED.search(lib)]
    return [line.split()[0] for line in text.splitlines() if "not found" in line and not PROVIDED.search(line)]


def is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            head = handle.read(4)
    except OSError:
        return False
    return head == b"\x7fELF" or head in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf")


def scan(folder: Path, limit: int = 800) -> tuple[int, list[str]]:
    """Every program and library under a package's bin/, lib/ and lib64/: how many were checked, and
    each unresolved library with the first file that needs it."""
    checked, missing = 0, {}
    for sub in ("bin", "lib", "lib64"):
        root = folder / sub
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if checked >= limit:
                break
            if path.is_symlink() or not path.is_file() or not is_binary(path):
                continue
            checked += 1
            for lib in unresolved(str(path)):
                missing.setdefault(lib, path.name)
    return checked, [f"{lib} ({who})" for lib, who in missing.items()]


def run(package: str, entries: list[dict], expand: Callable[[str], str], python: str, env: dict[str, str],
        quick: bool = False, slow_ok: bool = True) -> list[Row]:
    """A package's checks, as rows. `expand` fills a string's placeholders; `python` is the venv's."""
    rows: list[Row] = []
    env = {**env, "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryDirectory(prefix="hep-verify-") as scratch:
        for entry in entries:
            name = entry["name"]
            if entry.get("slow") and (quick or not slow_ok):
                rows.append((package, name, "n/a", "slow: skipped (--quick)" if quick else "slow: hep doctor runs it"))
                continue
            if "files" in entry:
                lost = [pattern for pattern in entry["files"] if not glob.glob(expand(pattern))]
                rows.append((package, name, "MISSING" if lost else "ok", " ".join(Path(p).name for p in lost)))
                continue
            if "links" in entry:
                patterns = entry["links"] if isinstance(entry["links"], list) else [entry["links"]]
                found = [path for pattern in patterns for path in glob.glob(expand(pattern))]
                text = "\n".join(links_of(path) for path in found)
                lost = [word for word in entry.get("has", []) if word.lower() not in text.lower()]
                rows.append((package, name, "MISSING" if lost or not found else "ok",
                             ("not linked: " + " ".join(lost)) if lost else "" if found else "no file matches"))
                continue
            argv = ([python, "-c", expand(entry["python"])] if "python" in entry
                    else [expand(word) for word in shlex.split(entry["command"])])
            code, out = _output(argv, env, scratch, 900 if entry.get("slow") else 120)
            if code:
                lines = [line for line in out.strip().splitlines() if line.strip()]
                why = next((line for line in lines if re.search(r"error|not found|cannot|no such", line, re.I)),
                           lines[-1] if lines else f"exit {code}")
                rows.append((package, name, "FAIL", why.strip()[:110]))
                continue
            words = set(out.split())
            wanted = [word for item in entry.get("has", []) for word in expand(item).split()]
            lost = [word for word in wanted if word not in words]
            if lost:
                rows.append((package, name, "MISSING", " ".join(lost)[:110]))
            elif entry.get("expect") and not re.search(entry["expect"], out, re.M):
                last = (out.strip().splitlines() or [""])[-1]
                rows.append((package, name, "FAIL", f"expected /{entry['expect']}/, got: {last.strip()[:80]}"))
            else:
                first = (out.strip().splitlines() or [""])[0].strip()
                rows.append((package, name, "ok", first[:80] if name == "version" else ""))
    return rows
