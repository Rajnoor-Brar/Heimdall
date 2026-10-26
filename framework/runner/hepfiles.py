"""Reading the framework's HEP files (rank 0): YODA text, and where Rivet keeps its analyses (V60).

One reader for what plot.py, labels.py and execute.py each read for themselves before: a YODA file's
objects (gzip read transparently), its /RAW twins, a counter's entries, and the Rivet data directories
(build/Rivet first, then `rivet-config --datadir`, asked once per process). The runner stays standard
library (06 §2.1): YODA's text is read with regular expressions, which is all these questions need.
"""

from __future__ import annotations

import functools
import gzip
import re
import subprocess
from pathlib import Path

from .paths import work_build

#: Not pages: Rivet's run counters, and its raw and temporary twins.
COUNTERS = ("/_XSEC", "/_EVTCOUNT")
TECHNICAL = ("/RAW/", "/TMP/")
_BEGIN = re.compile(r"^BEGIN YODA_(?:ESTIMATE1D|HISTO1D|SCATTER2D)_V\d+ (\S+)$", re.M)
_BEGIN_2D = re.compile(r"^BEGIN YODA_(?:ESTIMATE2D|HISTO2D)_V\d+ (\S+)$", re.M)


@functools.lru_cache(maxsize=64)
def _text(path: str, mtime: int) -> str:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def yoda_text(path: Path) -> str:
    """A YODA file's text, .yoda.gz included; read once per content (path and mtime)."""
    return _text(str(path), Path(path).stat().st_mtime_ns)


def objects(path: Path) -> list[str]:
    """The 1D objects that get pages: not /RAW or /TMP, not the counters, the nominal weight only (Sherpa
    writes a variation per extra weight, as /x[EXTRA__MEWeight])."""
    return [p for p in _BEGIN.findall(yoda_text(path))
            if not p.startswith(TECHNICAL) and p not in COUNTERS and not p.endswith("]")]


def objects_2d(path: Path) -> list[str]:
    """The 2D objects that get pages, as heat maps (V87): not /RAW or /TMP, the nominal weight only."""
    return [p for p in _BEGIN_2D.findall(yoda_text(path)) if not p.startswith(TECHNICAL) and not p.endswith("]")]


def base_path(path: str) -> str:
    """/photo_eic:R=0.4/d01-x01-y01 → /photo_eic/d01-x01-y01: the object without its analysis's options
    (a page is of the object; each variant is a curve on it)."""
    analysis, _, rest = path.strip("/").partition("/")
    return f"/{analysis.split(':')[0]}/{rest}"


def raw_twins(path: Path) -> set[str]:
    """The /RAW Histo1D twins a file has, whose entries App_yd2rt keeps (a ratio made in finalize has none)."""
    return set(re.findall(r"^BEGIN YODA_HISTO1D_V\d+ (/RAW/\S+)$", yoda_text(path), re.M))


_FILLABLE = re.compile(r"^BEGIN YODA_(?:HISTO[12]D|PROFILE[12]D)_V\d+ (\S+)\n(.*?)^END ", re.M | re.S)


def filled(path: Path, prefix: str = "/RAW/") -> tuple[int, int] | None:
    """(filled, all) of a YODA file's histograms and profiles under `prefix`, the nominal weight's (V195): a
    histogram is filled when a bin has entries (its rows' last column, numEntries). Counters (`_EVTCOUNT`,
    `_XSEC`) are not histograms. None when the file is not there."""
    if not Path(path).exists():
        return None
    count = full = 0
    for name, body in _FILLABLE.findall(yoda_text(path)):
        if not name.startswith(prefix) or name.endswith("]") or name.rsplit("/", 1)[-1].startswith("_"):
            continue
        count += 1
        rows = [line.split() for line in body.split("\n") if line and line[0] in "-+.0123456789"]
        full += any(row and _number(row[-1]) > 0 for row in rows)
    return full, count


def _number(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return 0.0


def entries(path: Path, obj: str) -> float | None:
    """A counter's numEntries (`/RAW/_EVTCOUNT`), from the YODA text; None when the file has none."""
    if not Path(path).exists():
        return None
    match = re.search(re.escape(obj) + r"\n.*?# sumW[^\n]*\n\S+\s+\S+\s+(\S+)", yoda_text(path), re.S)
    return float(match.group(1)) if match else None


@functools.cache
def rivet_dirs() -> tuple[Path, ...]:
    """Where analyses' .info, .plot and reference .yoda files are: build/Rivet, then Rivet's own."""
    places = [work_build() / "Rivet"]
    try:
        found = subprocess.run(["rivet-config", "--datadir"], capture_output=True, text=True, timeout=30, encoding="utf-8")
        places += [Path(p) for p in found.stdout.strip().split(":") if p]
    except (OSError, subprocess.SubprocessError):
        pass
    return tuple(places)
