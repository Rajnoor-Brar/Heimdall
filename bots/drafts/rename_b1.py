"""Task B step 1: the command `hep` becomes `heimdall`; setup.sh becomes bifrost.sh; load_hep becomes bifrost.

Run from Heimdall's checkout after `git mv framework/bin/hep framework/bin/heimdall` and
`git mv setup.sh bifrost.sh`. Rewrites tracked text files outside the history; prints what it changed.
"""

import re
import subprocess
import sys
from pathlib import Path

HISTORY = ("docs/07_Record.md", "docs/audit_2/", "docs/audit_3/", "docs/reporter/", "docs/framework/01_Target.md",
           "bots/", "tests/reference/", "docs/conda/01_Assessment.md", "docs/conda/02_Design.md",
           "docs/conda/03_Plan.md")
COMMANDS = ("run|plot|overlay|deck|ls|explain|status|migrate|reproduce|clean|check|watch|cluster|setup|doctor|tools|"
            "build|make|stack|help|where|refresh|quit|cd|recognise|bifrost")
RULES = [
    (re.compile(r"framework/bin/hep\b"), "framework/bin/heimdall"),
    (re.compile(r"(?<![\w/])bin/hep\b"), "bin/heimdall"),
    (re.compile(r"\bhep_(refresh|cd|status|stash|forge|stack|help)\b"), r"heimdall_\1"),
    (re.compile(r"\bload_hep\b"), "bifrost"),
    (re.compile(r"\bcommand hep\b"), "command heimdall"),
    (re.compile(rf"(?<![\w$./-])hep(?= ({COMMANDS})\b)"), "heimdall"),
    (re.compile(r"`hep`"), "`heimdall`"),
    (re.compile(r"""(?<=["'])hep \{"""), "heimdall {"),
    (re.compile(r"--app-name=hep\b"), "--app-name=heimdall"),
    (re.compile(r'prog="hep"'), 'prog="heimdall"'),
    (re.compile(r"(?<!key4hep/)(?<!~/HEP/)(?<![\w.-])setup\.sh\b"), "bifrost.sh"),
]

files = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True).stdout.split("\0")
changed = 0
for name in files:
    if not name or name.startswith(HISTORY):
        continue
    path = Path(name)
    if not path.is_file() or path.is_symlink():
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    new = text
    for pattern, replacement in RULES:
        new = pattern.sub(replacement, new)
    if new != text:
        path.write_text(new, encoding="utf-8")
        changed += 1
        print(name)
print(f"{changed} files changed", file=sys.stderr)
