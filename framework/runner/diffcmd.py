"""`heimdall diff`: what two Runs of one Errand did differently, read from their records, nothing run.

(a) The config each ran with (a record's snapshot): the errand file key by key, `old → new`, and the other files it read (cards,
imports) by their hash, a text file's lines shown (the first `LINES`, all with `--full`). (b) Each point both Runs have, by name
(a name is its quantities' tags, so equal names are equal coordinates): the parts its identity hashed, tool by tool (card lines,
options, the binary's sha256, argv), as `heimdall run --why` says them. What a difference is not a quantity shows here.
"""

from __future__ import annotations

import difflib
import json
import tomllib
from pathlib import Path

from . import record
from .errors import HeimdallError
from .paths import records_root

#: Lines of a file's diff shown without --full.
LINES = 12


def resolve(first: str, second: str) -> tuple[Path, Path]:
    """The two records: `<A>/<E>/<R1>` and `<A>/<E>/<R2>` (or a bare `<R2>` beside the first)."""
    from .house import log_target
    one, _, _ = log_target(first)
    if "/" not in second.strip("/") and not Path(second).exists():
        second = f"{one.parent.relative_to(records_root())}/{second}"
    other, _, _ = log_target(second)
    if one == other:
        raise HeimdallError("a Run is the same as itself", hint="heimdall diff <A>/<E>/<R1> <R2>")
    if one.parent != other.parent:
        raise HeimdallError(f"{one.relative_to(records_root())} and {other.relative_to(records_root())} are Runs of different Errands",
                            hint="heimdall diff compares two Runs of one Errand")
    return one, other


def _snapshot(folder: Path) -> tuple[dict, dict]:
    """(the snapshot's `[snapshot]`, its `files` hashes); a record with none is refused naming how it gets one."""
    path = folder / "config" / record.SNAPSHOT
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise HeimdallError(f"{folder.relative_to(records_root())} has no snapshot: it ran before Runs kept their config", where=str(path)) from None
    return data.get("snapshot", {}), data.get("files", {})


def _lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def _text_diff(a: Path, b: Path, full: bool) -> list[str]:
    lines = [d for d in difflib.unified_diff(_lines(a), _lines(b), lineterm="", n=0) if not d.startswith(("---", "+++", "@@"))]
    return lines if full or len(lines) <= LINES else lines[:LINES] + [f"… and {len(lines) - LINES} more line(s) (--full)"]


def settings_diff(one: Path, two: Path) -> list[str]:
    """The errand file each ran with, key by key; the configuration and `--set`s; Heimdall's revision is not a difference."""
    (a, _), (b, _) = _snapshot(one), _snapshot(two)
    out = []
    for key in ("configuration", "sets"):
        if a.get(key) != b.get(key):
            out.append(f"{key}: {a.get(key)!r} → {b.get(key)!r}")
    names = [(a.get("config"), b.get("config"))]
    for name_a, name_b in names:
        fa, fb = one / "config" / f"{name_a}.toml", two / "config" / f"{name_b}.toml"
        if fa.is_file() and fb.is_file():
            try:
                da, db = tomllib.loads(fa.read_text(encoding="utf-8")), tomllib.loads(fb.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError:
                da = db = {}
            out += record._diff(da, db, "") if da != db else []
    return out


def files_diff(one: Path, two: Path, full: bool) -> list[dict]:
    """The other files they read (cards, imports, masters): each that one has and the other has not, or has with another hash."""
    (a, fa), (b, fb) = _snapshot(one), _snapshot(two)
    skip = {f"{a.get('config')}.toml", f"{b.get('config')}.toml"}
    out = []
    for name in sorted(set(fa) | set(fb)):
        if name in skip:
            continue
        if name not in fb:
            out.append({"file": name, "change": "only in the first", "lines": []})
        elif name not in fa:
            out.append({"file": name, "change": "only in the second", "lines": []})
        elif fa[name] != fb[name]:
            out.append({"file": name, "change": "differs", "lines": _text_diff(one / "config" / name, two / "config" / name, full)})
    return out


def _identity(folder: Path, name: str) -> dict | None:
    path = folder / "points" / name / "identity.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    record.check_format(data, path)
    data.pop("format", None)
    return data


def _points(folder: Path) -> list[str]:
    root = folder / "points"
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "identity.json").is_file()) if root.is_dir() else []


def points_diff(one: Path, two: Path, picked: list[str] | None, full: bool) -> tuple[dict, dict]:
    """({point: its parts' differences}, {"first": names only it has, "second": …}): the points both Runs have, by name;
    `picked` (names or globs) keeps some. A point with no recorded identity in either says so."""
    import fnmatch
    a, b = _points(one), _points(two)
    both = [n for n in a if n in b and (not picked or any(fnmatch.fnmatchcase(n, g) for g in picked))]
    changed = {}
    for name in both:
        old, new = _identity(one, name), _identity(two, name)
        if old is None or new is None:
            changed[name] = ["its identity was not recorded"]
            continue
        if old == new:
            continue
        lines = record._diff(record._by_tag(old), record._by_tag(new), "")
        changed[name] = lines if full or len(lines) <= LINES else lines[:LINES] + [f"… and {len(lines) - LINES} more (--full)"]
    return changed, {"first": [n for n in a if n not in b], "second": [n for n in b if n not in a]}


def diff(first: str, second: str, picked: list[str] | None = None, full: bool = False) -> dict:
    """Everything `heimdall diff` says, as data."""
    one, two = resolve(first, second)
    changed, only = points_diff(one, two, picked, full)
    both = len([n for n in _points(one) if n in _points(two)])
    return {"first": str(one.relative_to(records_root())), "second": str(two.relative_to(records_root())),
            "settings": settings_diff(one, two), "files": files_diff(one, two, full), "points": changed,
            "same_points": both - len(changed), "only": only}


def lines_of(data: dict) -> list[str]:
    out = [f"{data['first']}  →  {data['second']}", ""]
    out += ["the errand file ran with:", *(f"  {line}" for line in data["settings"])] if data["settings"] else ["the errand file: the same"]
    for item in data["files"]:
        out.append(f"file {item['file']}: {item['change']}")
        out += [f"  {line}" for line in item["lines"]]
    out.append("")
    if data["points"]:
        out.append(f"points that differ ({len(data['points'])} of {len(data['points']) + data['same_points']} both have):")
        for name, lines in data["points"].items():
            out.append(f"  {name}")
            out += [f"    {line}" for line in lines]
    else:
        out.append(f"points: {data['same_points']} both have, none differs")
    for which in ("first", "second"):
        if data["only"][which]:
            out.append(f"only in the {which}: {', '.join(data['only'][which][:8])}" + (" …" if len(data["only"][which]) > 8 else ""))
    return out


def run(args) -> int:
    data = diff(args.first, args.second, [p.strip() for p in args.points.split(",") if p.strip()] if args.points else None, args.full)
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    print("\n".join(lines_of(data)))
    return 0
