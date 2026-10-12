"""`hep doctor`: what this machine's stack and Heimdall can do, checked (docs/audit_3/06_Plan.md, phase 2).

The packages' checks are their recipes' (`[[packages.<name>.verify]]` in recipes/toolkits/, run by
recipes/verify.py through recipes/build_stack.py), with a scan of every program and library for
libraries that no longer resolve. Heimdall's own rows follow: the system, where things are, and the
framework's apps. Nothing here names a tool: what a package must do is in its recipe.

`--record` writes this machine's summary to recipes/support/<platform>-<host>.toml, the support
matrix's rows; `--matrix` prints the matrix from every file there.
"""

from __future__ import annotations

import datetime
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from . import plugins
from .paths import apps_dir, find_work, hep_root

RESULTS = ("ok", "MISSING", "FAIL", "n/a")


def builder():
    return plugins.load(hep_root() / "recipes" / "build_stack.py", "build_stack")


def loaded(bs):
    """The recipes, settings and placeholders of the stack this shell has loaded: the machine root's, or an
    isolated toolkit's ($HEP_STACK), with that toolkit's changes."""
    stack = os.environ.get("HEP_STACK", "")
    _, settings, packages = bs.options([f"packages=@{stack}"] if stack else [])
    return settings, packages, bs.context(settings)


def stack_status() -> list[str]:
    """`hep status --stack`: every recipe installed in the loaded stack (its release, its state, its
    folder), then the libraries a module may require (env/stack.toml) with their versions."""
    bs = builder()
    _, packages, c = loaded(bs)
    out = [f"the stack: {c['inst']}" + (f" (@{c['stack']}, C++{c['cxx_std']})" if c["stack"] else ""),
           f"  {'package':13} {'release':10} {'state':18} folder"]
    for name, p in packages.items():
        now = "" if p.get("kind") == "external" else bs.state(name, p, c)
        if now:
            folder = "venv" if name == "python" else p.get("install", name) if p.get("kind") != "none" else "-"
            release = "?" if now == "installed" else str(p.get("release", "—"))   # not built here: below
            out.append(f"  {name:13} {release:10} {now:18} {folder}")
    if len(out) == 2:
        out.append("  (nothing installed: python3 recipes/build_stack.py)")
    if any(" installed " in line for line in out[2:]):
        out.append("  (installed: there, but not built by build_stack.py here; its version is below, or in hep doctor)")
    out += ["", "libraries a module may require (env/stack.toml), and the programs' versions:"]
    out += ["  " + line for line in plugins.load(hep_root() / "env" / "stack.py", "stack").versions()]
    return out


def first_line(argv: list[str]) -> str:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return ((out.stdout or out.stderr).strip().splitlines() or [""])[0][:70]


def system_rows() -> list[tuple[str, str, str, str]]:
    if sys.platform == "darwin":
        os_name = f"macOS {platform.mac_ver()[0]}"
    else:
        try:
            os_name = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines()
                           if "=" in line).get("PRETTY_NAME", "Linux").strip('"')
        except OSError:
            os_name = platform.system()
    rows = [("system", "os", "ok", f"{os_name} {platform.machine()}")]
    for program in ("c++", "gfortran", "cmake", "make"):
        rows.append(("system", program, "ok", first_line([program, "--version"])) if shutil.which(program)
                    else ("system", program, "MISSING", "not on PATH"))
    rows.append(("system", "python", "ok", f"{platform.python_version()} ({sys.executable})"))
    return rows


def heimdall_rows() -> list[tuple[str, str, str, str]]:
    work = find_work()
    rows = [("heimdall", "where", "ok", f"hep={hep_root()} work={work or '-'}")]
    if not os.environ.get("HEP_ENV_LOADED"):
        rows.append(("heimdall", "environment", "MISSING", "not loaded: source setup.sh (or launch.sh on macOS)"))
    apps = sorted(apps_dir().glob("*.exe")) if apps_dir().is_dir() else []
    rows.append(("heimdall", "framework apps", "ok" if apps else "n/a",
                 f"{len(apps)} built" if apps else "not built yet: hep build --framework"))
    return rows


def report(quick: bool = False) -> list[tuple[str, str, str, str]]:
    bs = builder()
    _, packages, c = loaded(bs)
    return [*system_rows(), *bs.doctor_rows(packages, c, dict(os.environ), quick=quick), *heimdall_rows()]


def render(rows: list[tuple[str, str, str, str]], colour: bool) -> list[str]:
    paint = {"ok": "32", "MISSING": "33", "FAIL": "31", "n/a": "2"}
    width = max(len(r[1]) for r in rows) if rows else 10
    out, last = [], None
    for package, check, result, note in rows:
        if package != last:
            out.append(f"{package}")
            last = package
        shown = f"\033[{paint[result]}m{result:7}\033[0m" if colour else f"{result:7}"
        out.append(f"  {check:{width}}  {shown}  {note}".rstrip())
    counts = {r: sum(1 for row in rows if row[2] == r) for r in RESULTS}
    out.append("")
    out.append("summary: " + ", ".join(f"{name} {counts[name]}" for name in RESULTS))
    return out


def support_file() -> Path:
    system = "macos" if sys.platform == "darwin" else (platform.system().lower() or "unknown")
    host = platform.node().split(".")[0] or "machine"
    return hep_root() / "recipes" / "support" / f"{system}-{host}.toml"


def record(rows: list[tuple[str, str, str, str]]) -> Path:
    """This machine's row of the support matrix: when, what, and what did not pass."""
    revision = first_line(["git", "-C", str(hep_root()), "rev-parse", "--short", "HEAD"])
    versions = {package: note for package, check, result, note in rows if check == "version" and result == "ok"}
    lines = [f"# {support_file().name} — `hep doctor --record` on this machine; the support matrix's row (recipes/README.md)",
             f'date     = "{datetime.date.today().isoformat()}"',
             f'platform = "{next((n for p, c, r, n in rows if c == "os"), "")}"',
             f'heimdall = "{revision}"',
             "counts   = { " + ", ".join(f'"{r}" = {sum(1 for row in rows if row[2] == r)}' for r in RESULTS) + " }",
             "", "[versions]", *(f'{package} = "{text}"' for package, text in versions.items()),
             "", "[problems]",
             *(f'"{package}: {check}" = "{result}: {note}"'.replace("\\", "/")
               for package, check, result, note in rows if result in ("MISSING", "FAIL"))]
    path = support_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def matrix() -> list[str]:
    files = sorted((hep_root() / "recipes" / "support").glob("*.toml"))
    if not files:
        return ["no machine has recorded its checks yet: hep doctor --record"]
    out = [f"{'machine':28} {'date':11} {'heimdall':9} {'ok':>4} {'FAIL':>5} {'MISSING':>8}  platform"]
    for file in files:
        data = tomllib.loads(file.read_text(encoding="utf-8"))
        counts = data.get("counts", {})
        out.append(f"{file.stem:28} {data.get('date', ''):11} {data.get('heimdall', ''):9} {counts.get('ok', 0):>4} "
                   f"{counts.get('FAIL', 0):>5} {counts.get('MISSING', 0):>8}  {data.get('platform', '')}")
        for problem, text in data.get("problems", {}).items():
            out.append(f"{'':28} {problem}: {text}"[:160])
    return out


def main(quick: bool = False, record_it: bool = False, show_matrix: bool = False) -> int:
    if show_matrix:
        for line in matrix():
            print(line)
        return 0
    rows = report(quick=quick)
    for line in render(rows, sys.stdout.isatty() and not os.environ.get("NO_COLOR")):
        print(line)
    if record_it:
        print(f"recorded: {record(rows)}")
    return 1 if any(row[2] == "FAIL" for row in rows) else 0
