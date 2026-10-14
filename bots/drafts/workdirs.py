"""The work dirs this machine knows: <machine root>/workdirs.toml (rank 1; docs/05_Commands_and_Tools.md §2).

`heimdall recognise` records a work dir there under a title, its hep.toml's [work] name (else its folder's
name), and `bifrost <title>` goes to it. `heimdall setup` records the work dir it makes. One table per title:

    ["Study"]
    path = "/home/me/Github/Study"
    recognised = "2026-10-14"

`$HEP_WORKDIRS` replaces the file (the tests point it into forge/scratch/). Standard library only: the shell
reads the titles with sed (bifrost's completion), so the file is written by hand, one title per header.
"""

from __future__ import annotations

import datetime
import json
import os
import tomllib
from pathlib import Path

from . import paths
from .errors import HepError, did_you_mean

FILE_VAR = "HEP_WORKDIRS"
#: Folders a scan does not enter: a work dir's own records and outputs, and build trees.
SKIP = {"results", "records", "logs", "build", "node_modules", "__pycache__"}
#: How deep below the folder it starts from a scan looks.
DEPTH = 4


def registry_file() -> Path:
    """$HEP_WORKDIRS, else the machine root's workdirs.toml."""
    given = os.environ.get(FILE_VAR)
    return Path(given).expanduser() if given else paths.machine_root() / "workdirs.toml"


def load() -> dict[str, dict]:
    """Every recorded title, with its path and the day it was recognised; {} before the first."""
    file = registry_file()
    if not file.is_file():
        return {}
    try:
        data = tomllib.loads(file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HepError(f"cannot read {file}: {error}", hint="fix it by hand, or remove it and recognise again")
    for title, entry in data.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise HepError(f"[\"{title}\"] has no path", where=str(file))
    return data


def save(entries: dict[str, dict]) -> Path:
    """The registry, written whole: titles in order, each a quoted header (bifrost's completion reads them)."""
    file = registry_file()
    lines = ["# workdirs.toml: the work dirs this machine knows, written by `heimdall recognise` and",
             "# `heimdall setup`; `bifrost <title>` goes to one. Edit with heimdall recognise --as / --forget."]
    for title in sorted(entries, key=str.casefold):
        entry = entries[title]
        lines += ["", f"[{json.dumps(title, ensure_ascii=False)}]", f"path = {json.dumps(entry['path'], ensure_ascii=False)}",
                  f"recognised = {json.dumps(entry.get('recognised', ''))}"]
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(file.name + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(file)
    return file


def enclosing(path: Path) -> Path | None:
    """The work dir `path` is, or is inside (Heimdall's own test fixtures are not), whatever $HEP_WORK says."""
    return paths._search(str(path.expanduser().resolve()))


def state(entry: dict) -> str:
    """Where a recorded work dir stands: "work dir", "missing" or "no longer a work dir"."""
    where = Path(entry["path"])
    return "work dir" if paths.is_work(where) else "missing" if not where.exists() else "no longer a work dir"


def record(root: Path, title: str | None = None) -> tuple[str, str]:
    """Record the work dir `root`: (its title, what happened): "recorded", "known", "renamed from <old>"
    or "moved from <old path>". A title another existing work dir holds is refused."""
    root = root.expanduser().resolve()
    title = title or paths.work_meta(root)["name"]
    if not title.strip() or "\n" in title or '"' in title:
        raise HepError(f"'{title}' cannot be a title", hint="a title is one line, without quotes: --as <title>")
    entries = load()
    held = next((t for t, e in entries.items() if Path(e["path"]) == root), None)
    if held == title:
        return title, "known"
    if title in entries:
        other = Path(entries[title]["path"])
        if paths.is_work(other):
            raise HepError(f"the title '{title}' is another work dir's: {other}", where=str(root),
                           hint=f"heimdall recognise {root} --as <another title>")
        happened = f"moved from {other}"
    else:
        happened = f"renamed from {held}" if held else "recorded"
    if held:
        del entries[held]
    entries[title] = {"path": str(root), "recognised": datetime.date.today().isoformat()}
    save(entries)
    return title, happened


def scan(start: Path, depth: int = DEPTH) -> list[Path]:
    """The work dirs at or below `start`, `depth` folders deep at most: not inside hidden folders, a work
    dir's results/, records/, logs/ or build/, Heimdall's checkout or the machine root."""
    start = start.expanduser().resolve()
    avoid = {paths.hep_root().resolve(), paths.machine_root().expanduser().resolve()}
    found: list[Path] = []

    def walk(folder: Path, left: int) -> None:
        if folder in avoid:
            return
        if paths.is_work(folder):
            found.append(folder)                                       # work dirs do not nest
            return
        if left == 0:
            return
        try:
            children = sorted((entry for entry in os.scandir(folder)
                               if entry.is_dir(follow_symlinks=False) and not entry.name.startswith(".")
                               and entry.name not in SKIP), key=lambda entry: entry.name)
        except OSError:                                                # unreadable: passed over
            return
        for child in children:
            walk(Path(child.path), left - 1)

    walk(start, depth)
    return found


def path_of(title: str) -> Path:
    """Where the work dir of `title` is (bifrost's question); an unknown title or a gone path is refused."""
    entries = load()
    if title not in entries:
        raise HepError(f"no work dir titled '{title}'",
                       hint=did_you_mean(title, entries) or ("heimdall recognise --list shows them" if entries
                                                             else "record one: heimdall recognise <work dir>"))
    where = Path(entries[title]["path"])
    if not paths.is_work(where):
        raise HepError(f"'{title}' was {where}, which is {state(entries[title])} now",
                       hint=f"heimdall recognise <its new place>, or heimdall recognise --forget {json.dumps(title)}")
    return where


def forget(title: str) -> Path:
    """Take a title out of the registry; returns where it pointed."""
    entries = load()
    if title not in entries:
        raise HepError(f"no work dir titled '{title}'", hint=did_you_mean(title, entries) or "heimdall recognise --list")
    where = Path(entries.pop(title)["path"])
    save(entries)
    return where
