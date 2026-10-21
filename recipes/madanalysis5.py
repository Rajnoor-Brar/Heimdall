#!/usr/bin/env python3
"""recipes/madanalysis5.py MA5 RELEASE CORES [key=value …] — MadAnalysis 5 made ready where it is unpacked,
as MadGraph's `install MadAnalysis5` makes its own copy (README.md §3). build_stack.py's madanalysis5 step
runs it with the venv's Python; standard library only, then MadAnalysis 5's own code.

- version.txt, which MadAnalysis 5's interpreter reads to start (MadGraph starts it so) and its GitHub
  tarball lacks;
- the key=value pairs into madanalysis/input/installation_options.dat (its file for what it would
  otherwise detect: zlib_includes and zlib_libs from the base, whose compiler cannot use the system's
  /usr/include; root_bin_path, fastjet_bin_path), an absolute path that is not there left out (zlib's
  /include without a base);
- SampleAnalyzer compiled, on CORES compilers (it would take every core).
"""

from __future__ import annotations

import multiprocessing
import os
import re
import sys
from pathlib import Path


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        sys.exit(__doc__)
    ma5, release, cores = Path(argv[0]).resolve(), argv[1], int(argv[2])
    date = re.search(r'^date\s*=\s*"(.*)"', (ma5 / "bin" / "ma5").read_text(encoding="utf-8"), re.M)
    (ma5 / "version.txt").write_text(f"MA5 version {release}\nDate {date[1] if date else ''}\n", encoding="utf-8")
    options = ma5 / "madanalysis" / "input" / "installation_options.dat"
    pairs = [pair.partition("=") for pair in argv[3:]]
    lines = [f"{key} = {value}" for key, _, value in pairs
             if value and not (value.startswith("/") and not Path(value).exists())]
    with options.open("a", encoding="utf-8") as out:
        out.write("\n# set by Heimdall's recipes/madanalysis5.py\n" + "".join(f"{line}\n" for line in lines))
    os.environ["MA5_BASE"] = str(ma5)
    sys.path.insert(0, str(ma5))
    multiprocessing.cpu_count = lambda: cores                     # its compilers at once (it asks, else all)
    from madanalysis.interpreter.ma5_interpreter import MA5Interpreter
    try:                                                           # a failed step calls sys.exit() (status 0)
        MA5Interpreter(str(ma5), LoggerLevel=20, no_compilation=True).compile()
    except SystemExit:
        pass
    if not list((ma5 / "tools" / "SampleAnalyzer" / "Lib").glob("libprocess_for_ma5.*")):   # its core library
        sys.exit("madanalysis5.py: SampleAnalyzer did not compile (tools/SampleAnalyzer/*/compilation*.log)")


if __name__ == "__main__":
    main(sys.argv[1:])
