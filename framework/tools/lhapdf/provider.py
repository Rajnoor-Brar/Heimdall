"""framework/tools/lhapdf/provider.py — LHAPDF as a provider: is a PDF set a tool is given installed (V60, C10).

A provider is the first of the tool categories (01 §5): it gives other tools data. A tool folder's
quantity mapping names a check, `check = "lhapdf:<form>"` (framework/tools/<tool>/quantities.toml), and the
runner calls `check(form, value, where)` at plan time, so a missing set is refused before anything runs. It
returns the value as that tool writes it (None: as given), so one spelling of a set feeds every generator (V152):
"CT14lo" and "LHAPDF6:CT14lo" are the same set.

* "bare": the bare set name, `<set>[/member]` (Sherpa's PDF_SET); a prefix is taken off.
* "set": the set's name alone (Herwig's PDFName; its member is the card's `:Member`); a prefix is taken off.
* "pythia": Pythia's PDF:pSet: an installed LHAPDF set is written "LHAPDF6:<set>[/member]"; one of Pythia's own
  sets (a number its documentation lists, PDFSelection.xml) and a grid file as written (V40: a number is
  never prefixed).
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
from pathlib import Path

from runner.errors import HeimdallError

PREFIXES = ("LHAPDF6:", "LHAPDF5:")


def data_dirs() -> list[str]:
    return [d for d in os.environ.get("LHAPDF_DATA_PATH", "").split(":") if d]


def installed(name: str) -> bool:
    return any((Path(d) / name / f"{name}.info").is_file() for d in data_dirs())


def require(name: str, where: str) -> None:
    if not installed(name):
        raise HeimdallError(f"the PDF set '{name}' is not installed", where=where,
                       hint=f"lhapdf install {name}   (searched LHAPDF_DATA_PATH: {', '.join(data_dirs()) or 'unset'})")


@functools.cache
def pythia_sets() -> tuple[int, ...]:
    """Pythia's own proton PDF sets, from its documentation (PDF:pSet's options); () when not found."""
    try:
        xmldoc = subprocess.run(["pythia8-config", "--xmldoc"], capture_output=True, text=True, timeout=30, encoding="utf-8").stdout.strip()
        text = (Path(xmldoc) / "PDFSelection.xml").read_text(encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return ()
    block = re.search(r'<word name="PDF:pSet".*?</word>', text, re.S)
    return tuple(int(v) for v in re.findall(r'<option value="(\d+)"', block.group(0))) if block else ()


def check(form: str, value, where: str):
    """Refuse a set that is not installed; return the value as the tool writes it (None: as given, V152). One
    spelling feeds every generator: "CT14lo" and "LHAPDF6:CT14lo" are the same set."""
    text = str(value)
    if form in ("bare", "set"):
        name = text.split(":", 1)[1] if text.startswith(PREFIXES) else text
        if form == "set" and "/" in name:
            raise HeimdallError(f"'{text}': this tool takes a set's name, not a member", where=where,
                           hint=f"write '{name.split('/')[0]}', and choose the member in the tool's card")
        require(name.split("/")[0], where)
        return name if name != text else None
    if form == "pythia":
        if (isinstance(value, int) and not isinstance(value, bool)) or text.isdigit():
            sets = pythia_sets()
            if sets and int(text) not in sets:
                raise HeimdallError(f"PDF:pSet = {text} is not one of Pythia's own sets", where=where,
                               hint=f"Pythia's sets: {sets[0]}–{sets[-1]} (PDFSelection.xml); an LHAPDF set by its name")
            return None                                    # Pythia's own set: never prefixed (V40)
        if text.startswith(PREFIXES):
            require(text.split(":", 1)[1].split("/")[0], where)
            return None
        if installed(text.split("/")[0]):
            return f"LHAPDF6:{text}"                       # Pythia reads a bare name as a file
        return None                                        # a grid file, as written
    raise HeimdallError(f"lhapdf has no check '{form}'", where=where, hint="bare, set or pythia")
