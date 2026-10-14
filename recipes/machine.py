#!/usr/bin/env python3
"""recipes/machine.py — the machine root: what this machine built, apart from Heimdall's checkout
(docs/audit_3/02_Organisation.md §3). Standard library only: it runs before any environment exists.

    python3 recipes/machine.py where              # the machine root and its folders
    python3 recipes/machine.py adopt [--dry-run]  # a checkout that still holds its stack: moved under the root

The machine root is $HEP_MACHINE, else ~/Himinbjorg. `adopt` makes it from a checkout of the old
layout (stack/, env/venv/, framework/Apps/, stash/, env/machine.sh inside Heimdall):
* what can move does: Heimdall's compiled apps (their libraries are found by absolute paths, not by
  where they are), the downloads, this machine's shell lines;
* what cannot move is linked: the stack and the venv carry their own absolute paths (rpaths, *-config
  scripts, the venv's interpreter), so they stay where they are and the root links to them. A link
  that was already a link (the lab PC's stack → ~/HEP/install) is linked to its target.
Nothing is rebuilt and nothing is deleted. A stack that stays inside the checkout this way is still
destroyed by `git clean -x` there; a rebuild into the root (build_stack.py) ends that.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def root() -> Path:
    return Path(os.environ.get("HEP_MACHINE") or "~/Himinbjorg").expanduser()


#: A new root's machine.toml: every table, commented out (build_stack.py writes the same).
TEMPLATE = REPO / "recipes" / "machine.template.toml"


def adopt(dry: bool) -> int:
    target = root()
    plan: list[tuple[str, Path, Path]] = []                      # (move | link | copy, from, to)
    for old, new, how in ((REPO / "stack", target / "stack", "link"),
                          (REPO / "env" / "venv", target / "venv", "link"),
                          (REPO / "stacks", target / "stacks", "link"),
                          (REPO / "framework" / "Apps", target / "apps", "move"),
                          (REPO / "stash", target / "forge" / "downloads", "move"),
                          (REPO / "env" / "machine.sh", target / "machine.sh", "move")):
        if not (old.exists() or old.is_symlink()):
            continue
        if new.exists() or new.is_symlink():
            print(f"keep   {new} (already there; {old} left as it is)")
            continue
        if old.is_symlink():                                       # a link already: link to what it names
            plan.append(("link", old.resolve(), new))
            plan.append(("unlink", old, old))
        else:
            plan.append((how, old, new))
    if not plan:
        print(f"nothing to adopt in {REPO}" + (f"; the machine root is {target}" if target.exists() else ""))
        return 0
    for how, old, new in plan:
        print(f"{how:6} {old}" + ("" if how == "unlink" else f" → {new}"))
    if dry:
        print("(dry run: nothing done)")
        return 0
    target.mkdir(parents=True, exist_ok=True)
    if not (target / "machine.toml").exists():
        (target / "machine.toml").write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    for how, old, new in plan:
        if how == "unlink":
            old.unlink()
            continue
        new.parent.mkdir(parents=True, exist_ok=True)
        if how == "link":
            new.symlink_to(old, target_is_directory=old.is_dir())
        else:
            shutil.move(str(old), str(new))
    print(f"adopted into {target}; load Heimdall again (source {REPO}/setup.sh, or launch.sh on macOS)")
    if any(how == "link" and REPO in old.parents for how, old, _ in plan):
        print("note: the stack still lives inside the checkout (linked from the root): `git clean -x` there "
              "would delete it; a rebuild into the root ends that")
    return 0


def where() -> int:
    r = root()
    print(f"machine root  {r}{'' if r.exists() else '  (not made yet)'}")
    for name in ("base", "stack", "venv", "apps", "forge", "stacks", "machine.toml", "machine.sh"):
        path = r / name
        state = ("→ " + str(path.resolve())) if path.is_symlink() else ("" if path.exists() else "(none)")
        print(f"  {name:12} {state}")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "adopt":
        return adopt("--dry-run" in argv or "-n" in argv)
    if argv[0] == "where":
        return where()
    print(f"unknown command '{argv[0]}': where, adopt", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
