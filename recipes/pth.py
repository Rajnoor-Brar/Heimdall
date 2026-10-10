#!/usr/bin/env python3
"""recipes/pth.py HEP — the venv's heimdall.pth, so `import hepkit` and `from runner import results` work
in any Python of the venv (docs/framework/01_Target.md §5.5). build_stack.py's [python] step runs it."""

import site
import sys
from pathlib import Path

Path(site.getsitepackages()[0], "heimdall.pth").write_text(f"{Path(sys.argv[1]).resolve()}/framework\n", encoding="utf-8")
