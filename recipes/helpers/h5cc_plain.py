#!/usr/bin/env python3
"""recipes/helpers/h5cc_plain.py INSTALL VERSION — write INSTALL/bin/plain-h5cc: an h5cc that answers
-show and -showconfig in the classic one-line form autotools packages parse (YODA's m4/ax_lib_hdf5.m4).

HDF5 2.x is built with CMake only, and its h5cc's answers broke YODA's link line (the Mac's build,
The plain wrapper names the same install, nothing else. Its name ends in
h5cc: ax_lib_hdf5.m4 reads the HDF5 type from the wrapper's name ("*h5cc" serial, "*h5pcc" parallel)."""

import sys
from pathlib import Path

install, version = Path(sys.argv[1]), sys.argv[2]
script = install / "bin" / "plain-h5cc"
script.write_text(f"""#!/bin/sh
# plain-h5cc — HDF5 {version} at {install}, for configure scripts (written by recipes/helpers/h5cc_plain.py)
H="{install}"
case "$1" in
  -show)       echo "cc -I$H/include -L$H/lib -lhdf5" ;;
  -showconfig) printf 'HDF5 Version: {version}\\nInstallation point: %s\\nExtra libraries: -lz\\n' "$H" ;;
  *)           exec cc -I"$H/include" -L"$H/lib" "$@" -lhdf5 ;;
esac
""", encoding="utf-8")
script.chmod(0o755)
print(f"wrote {script}")
