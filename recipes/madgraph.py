#!/usr/bin/env python3
"""recipes/madgraph.py — MadGraph pointed at the stack, and its loop libraries built in its tree, as
`install <tool>` at its prompt would (README.md §3). build_stack.py's madgraph and madanalysis5 steps run it;
standard library only.

  madgraph.py configure MG key=value …   set those options in MG/input/mg5_configuration.txt: an option's
                                          line, commented or not, is replaced, else one is added. A value
                                          that is an absolute path is set only when the path exists (a
                                          package not built here stays MadGraph's default), and said
  madgraph.py loop-tools MG [QCDLOOP]     Ninja (with OneLOop) and COLLIER into MG/HEPTools from the tarballs
                                          MadGraph ships (vendor/), through its own offline installer;
                                          CutTools and IREGI compiled in vendor/; MG/QCDLoop linked to
                                          QCDLOOP (the qcdloop recipe's install), where `install QCDLoop`
                                          puts it
  madgraph.py noplugin DIR …              aMC@NLO's Pythia 8.3 driver compiled with -DNOPLUGIN, in the
                                          MCatNLO makefiles under DIR (MadGraph's Template/, or a process
                                          folder's MCatNLO/): it includes two of Pythia's plugin headers, and
                                          in 8.318 each defines the same PYTHIA8_PLUGIN_VERSIONS functions
                                          ("redefinition of CHECK_COMPATIBLE_VERSION"). The macros only
                                          register classes for Pythia's plugin loader, which it does not use
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def configure(mg: Path, pairs: list[str]) -> None:
    card = mg / "input" / "mg5_configuration.txt"
    if not card.exists():                                          # MadGraph not built here: nothing to tell
        print(f"madgraph.py: no {card}: skipped")
        return
    text = card.read_text(encoding="utf-8")
    for pair in pairs:
        key, _, value = pair.partition("=")
        if value.startswith("/") and not Path(value).exists():
            print(f"madgraph.py: {key} left as it is ({value} is not there)")
            continue
        line = f"{key} = {value}"
        pattern = re.compile(rf"^#* *{re.escape(key)} *=.*$", re.M)
        text, n = pattern.subn(line.replace("\\", "\\\\"), text, count=1)
        if not n:
            text = text.rstrip("\n") + f"\n{line}\n"
        print(f"madgraph.py: {line}")
    card.write_text(text, encoding="utf-8")


def loop_tools(mg: Path, qcdloop: str | None) -> None:
    vendor, heptools = mg / "vendor", mg / "HEPTools"
    heptools.mkdir(exist_ok=True)
    subprocess.run(["tar", "xzf", str(vendor / "OfflineHEPToolsInstaller.tar.gz")], cwd=heptools, check=True)
    installer = heptools / "HEPToolsInstallers" / "HEPToolInstaller.py"
    common = [f"--prefix={heptools}", f"--mg5_path={mg}"]          # --mg5_path: the installer reads its version
    for tool, tarballs in (("ninja", ("ninja", "oneloop")), ("collier", ("collier",))):
        given = [f"--{name}_tarball={vendor / name}.tar.gz" for name in tarballs]
        subprocess.run([sys.executable, str(installer), tool, *common, *given], cwd=heptools, check=True)
    subprocess.run(["make", "-j1"], cwd=vendor / "CutTools", check=True)      # libcts.a, as a first loop output
    subprocess.run(["make"], cwd=vendor / "IREGI" / "src", check=True)        # would; -j1 as MadGraph runs it
    if qcdloop:
        link = mg / "QCDLoop"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(qcdloop)


def noplugin(folders: list[Path]) -> None:
    rule = re.compile(r"^(Pythia83:.*?\n)(\t.*?\$\(CXX\) \$\(CXXFLAGS\))(?! -DNOPLUGIN)", re.M | re.S)
    for folder in folders:
        for makefile in sorted(folder.glob("**/srcPythia8/Makefile*")):
            text = makefile.read_text(encoding="utf-8")
            new, n = rule.subn(r"\1\2 -DNOPLUGIN", text)
            if n:
                makefile.write_text(new, encoding="utf-8")
                print(f"madgraph.py: {makefile}: Pythia83 with -DNOPLUGIN")


def main(argv: list[str]) -> None:
    if len(argv) < 2 or argv[0] not in ("configure", "loop-tools", "noplugin"):
        sys.exit(__doc__)
    mg = Path(argv[1])
    if argv[0] == "configure":
        configure(mg, argv[2:])
    elif argv[0] == "noplugin":
        noplugin([Path(a) for a in argv[1:]])
    else:
        loop_tools(mg, argv[2] if len(argv) > 2 else None)


if __name__ == "__main__":
    main(sys.argv[1:])
