#!/usr/bin/env python3
"""Every old document and manual section has a destination; every section code cites maps to a page. Run from the repo."""
import fnmatch, re, subprocess, tomllib
from pathlib import Path

TAG = "docs/pre-rebuild"
M = tomllib.loads(Path(".plans/docs_rebuild/salvage.toml").read_text(encoding="utf-8"))
show = lambda f: subprocess.check_output(["git", "show", f"{TAG}:{f}"], text=True, encoding="utf-8")
files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", TAG, "docs", ".plans",
                                 "recipes/README.md", "recipes/platforms/mac/README.md"], text=True).split()
bad = []
for f in files:
    if not f.endswith(".md"):
        continue
    if m := re.match(r"docs/(0\d)_", f):
        body = re.sub(r"^```.*?^```", "", show(f), flags=re.M | re.S)
        for n in re.findall(r"^## (\d+)\.", body, re.M) or ["0"]:
            if n not in M["sections"][m.group(1)]:
                bad.append(f"{f} §{n}")
    elif not any(fnmatch.fnmatch(f, pat) for pat in M["files"]):
        bad.append(f)
    else:
        for pat, row in M["files"].items():
            if fnmatch.fnmatch(f, pat) and row["to"] == ["wipe"] and not row.get("why"):
                bad.append(f"{f}: wiped with no reason")

cited = set()
code = subprocess.check_output("git ls-files framework src recipes env tests Makefile gjallarhorn.sh launch.sh".split(), text=True).split()
for f in code:
    if f.startswith(("tests/reference", "tests/fixtures")) or not Path(f).is_file():
        continue
    try:
        text = Path(f).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    cited |= set(re.findall(r"docs/(0[0-7])_[A-Za-z_]+\.md(?: §(\d+))?", text))
    cited |= set(re.findall(r"(?<![\w/.§])(0[1-7]) §(\d+)", text))
for page, sec in sorted(cited):
    if sec and sec not in M["sections"][page]:
        bad.append(f"cited: {page} §{sec}")

dest = sorted({d for s in M["sections"].values() for v in s.values() for d in v} |
              {d for r in M["files"].values() for d in r["to"]})
print(f"{len(files)} files, {len(cited)} cited sections, {len(dest)} destinations")
print("\n".join(dest))
print("UNCOVERED:\n  " + "\n  ".join(bad) if bad else "all covered")
raise SystemExit(bool(bad))
