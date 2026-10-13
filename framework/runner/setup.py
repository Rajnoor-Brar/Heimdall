"""`hep setup` and `hep where`: make a work dir, and say which Heimdall and work dir a shell sees (rank 5).

docs/framework/01_Target.md §4–§5 (D3, D14). What a work dir gets is framework/templates/work/: a
new file there is a template edit, never a code change. In the template, `{{name}}`, `{{revision}}`,
`{{date}}`, `{{P}}` and `{{p}}` are filled in; nothing else is touched (JSON keeps its braces).

    hep setup <dir> [--project P] [--git[=new]] [--adopt] [--name N]
    hep setup <dir> --refresh [--yes]
    hep where [--hep | --work]

A work dir may be made in a git repository (U67): a fresh one (only .git/ and a hosting site's
README, LICENSE, .gitignore) needs no --adopt; its own README.md and CLAUDE.md are kept, Heimdall's
guide going beside them as HEIMDALL.md, and its .gitignore gains a marked block of the template's
lines. `--git` commits the added files only, in the repository the folder is in (a nested one only
with --git=new). `datasets.toml` lists the large reference files, fetched here with their sha256
checked (U23); `--refresh` brings the framework's own files up to today's template (U28).
"""

from __future__ import annotations

import datetime
import difflib
import hashlib
import os
import re
import shutil
import site
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

from .errors import HepError
from .paths import MARKER_FILE, STACK_VAR, find_work, hep_root, is_work, machine_root, stack_dir, work_meta

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "work"
STARTER = "starter"
#: A fresh repository's own entries (git init, or a hosting site's new repo): a folder holding only
#: these (and LICENSE*) is empty enough to become a work dir without --adopt (U67).
FRESH = (".git", "README.md", "README", "COPYING", ".gitignore", ".gitattributes", ".github")
#: The guide's names: a repository's own are kept, and Heimdall's goes in GUIDE beside them.
GUIDES = ("README.md", "CLAUDE.md")
GUIDE = "HEIMDALL.md"
#: The marked block of ignores hep setup keeps in a .gitignore that is not the template's.
BLOCK, BLOCK_END = "# Heimdall (hep setup): what the runner and the build make", "# /Heimdall"
MANIFEST = "datasets.toml"
#: `hep setup --example <name>` (U63): a working project of the tests' own work dir, which the suite
#: keeps running, copied into the user's: name → (its project, what it says to run first).
EXAMPLES = {"jets": ("Demo", "Demo/jets single")}
EXAMPLE_WORK = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "work"
#: The key folders every work dir has (framework/01 §4.1).
FOLDERS = ("configs", "modules", "datasets", "decks", "results", "records", "reports", "build")


def revision(root: Path | None = None) -> str:
    """Heimdall's git revision, or "" when it is not a repo or its tracked files changed."""
    root = root or hep_root()

    def git(*args) -> str:
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    if not (root / ".git").exists() or git("status", "--porcelain", "--untracked-files=no"):
        return ""
    return git("rev-parse", "HEAD")


def _fill(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def _blocked(path: Path, wanted: list[str]) -> list[str]:
    """`wanted` ignore lines kept in the file's marked block (made or brought up to date), the rest of the
    file untouched. Returns the lines the block holds now ([] when the file has them all already)."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    if BLOCK in lines:
        start = lines.index(BLOCK)
        end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == BLOCK_END), len(lines) - 1)
        lines = lines[:start] + lines[end + 1:]
    have = {line.strip() for line in lines}
    missing = [line for line in wanted if line.strip() not in have]
    while lines and not lines[-1].strip():
        lines.pop()
    new = lines + ([*([""] if lines else []), BLOCK, *missing, BLOCK_END] if missing else [])
    text = "\n".join(new) + ("\n" if new else "")
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return missing


def _ignores(template: Path) -> list[str]:
    return [line.strip() for line in template.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def _fresh(target: Path) -> bool:
    """A fresh repository: .git/, and only its hosting site's files (README, LICENSE*, .gitignore,
    .gitattributes, .github/)."""
    return (target / ".git").exists() and all(e.name in FRESH or e.name.startswith("LICENSE") for e in target.iterdir())


def _heimdalls(path: Path) -> bool:
    """A guide hep setup wrote (README.md, CLAUDE.md), not the repository's own."""
    return "heimdall work dir" in path.read_text(encoding="utf-8", errors="replace").lower()


def toplevel(folder: Path) -> Path | None:
    """The git repository a folder is in (its top), or None."""
    try:
        done = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=folder, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(done.stdout.strip()).resolve() if done.returncode == 0 and done.stdout.strip() else None


def _guide(values: dict[str, str], readme: bool, claude: bool) -> str:
    """HEIMDALL.md: the template's README, and its CLAUDE.md's rules for coding agents, for a repository
    that keeps its own."""
    parts = [_fill((TEMPLATE / "README.md").read_text(encoding="utf-8"), values)] if readme else \
        [f"# {values['name']}: Heimdall\n\nA Heimdall work dir (made by `hep setup` on {values['date']}).\n"]
    if claude:
        body = _fill((TEMPLATE / "CLAUDE.md").read_text(encoding="utf-8"), values).split("\n", 1)[-1].strip()
        parts.append("## For coding agents\n\n" + body + "\n")
    return "\n".join(p.rstrip() + "\n" for p in parts)


def setup(target: Path, *, project: str | None = None, git: bool = False, adopt: bool = False,
          name: str | None = None, out=print, example: str | None = None) -> list[str]:
    """Lay the template down in `target`; never overwrite. Returns what was added (paths relative to it)."""
    target = target.expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise HepError(f"{target} is a file", hint="hep setup makes a work dir: give a folder")
    if target.is_dir() and any(target.iterdir()) and not is_work(target) and not adopt and not _fresh(target):
        raise HepError(f"{target} is not empty and not a work dir",
                       hint="give an empty or new folder (a fresh git repository is one), or --adopt to make a work dir of this one")
    if not TEMPLATE.is_dir():
        raise HepError(f"no work-dir template at {TEMPLATE}")
    if project is not None and (not project or "/" in project or project.startswith(("_", "."))):
        raise HepError(f"'{project}' is not a project name", hint="a folder name: letters, digits, - and _")
    values = {"name": name or target.name, "revision": revision(), "date": datetime.date.today().isoformat(),
              "P": project or "", "p": (project or "").lower()}
    making = not is_work(target)                                    # not completing a work dir: making one
    target.mkdir(parents=True, exist_ok=True)
    added: list[str] = []
    changed: list[str] = []                                         # files of the user's that hep setup added to
    theirs: list[str] = []                                          # the repository's own guides, kept

    def put(src: Path, rel: Path) -> None:
        dest = target / rel
        if rel == Path(".gitignore") and dest.exists():
            missing = _blocked(dest, _ignores(src))
            if missing:
                changed.append(".gitignore")
                out(f"merged .gitignore: {' '.join(missing)} (a marked block)")
            return
        if making and rel in (Path(g) for g in GUIDES) and dest.exists() and not _heimdalls(dest):
            theirs.append(rel.name)
            out(f"kept {rel} (the repository's own); Heimdall's guide is {GUIDE}")
            return
        if dest.exists():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_fill(src.read_text(encoding="utf-8"), values), encoding="utf-8")
        added.append(str(rel))
        out(f"added {rel}")

    for src in sorted(TEMPLATE.rglob("*")):
        rel = src.relative_to(TEMPLATE)
        if src.is_file() and rel.parts[0] != STARTER:
            put(src, rel)
    for folder in FOLDERS:
        if not (target / folder).is_dir():
            (target / folder).mkdir()
            added.append(folder + "/")
            out(f"added {folder}/")
    if example is not None:
        added += _example(target, example, out)
    if theirs and not (target / GUIDE).exists():
        (target / GUIDE).write_text(_guide(values, "README.md" in theirs, "CLAUDE.md" in theirs), encoding="utf-8")
        added.append(GUIDE)
        out(f"added {GUIDE}")
    if project:
        p = values["p"]
        put(TEMPLATE / STARTER / "run.toml", Path("configs") / project / f"{p}.toml")
        put(TEMPLATE / STARTER / "run.cmnd", Path("configs") / project / f"{p}.cmnd")
        if not (target / "modules" / project).is_dir():
            (target / "modules" / project).mkdir(parents=True)
            added.append(f"modules/{project}/")
            out(f"added modules/{project}/")
    for name in fetch_datasets(target, out):
        if name not in changed:
            changed.append(name)
    if git:
        _commit(target, [a for a in added if not a.endswith("/")] + changed, values,
                new=git == "new", out=out)
    return added


def _example(target: Path, name: str, out=print) -> list[str]:
    """The example's project: its configs/, modules/ and the datasets they read, never over a file."""
    if name not in EXAMPLES:
        from .errors import did_you_mean
        raise HepError(f"no example '{name}'", hint=did_you_mean(name, EXAMPLES) or f"examples: {', '.join(EXAMPLES)}")
    project = EXAMPLES[name][0]
    added = []
    sources = [EXAMPLE_WORK / "configs" / project, EXAMPLE_WORK / "modules" / project, EXAMPLE_WORK / "datasets"]
    for root in sources:
        for src in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            rel = src.relative_to(EXAMPLE_WORK)
            dest = target / rel
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            added.append(str(rel))
    out(f"added the example '{name}': configs/{project}/, modules/{project}/, datasets/ ({len(added)} files)")
    return added


def _commit(target: Path, files: list[str], values: dict[str, str], new: bool = False, out=print) -> None:
    """`--git` (U67): the files hep setup added or merged, committed alone (`git commit -- <paths>`: what
    the user had staged stays staged), in the repository the folder is in; `git init` first when it is
    in none. Inside a larger repository, a repository of its own only with --git=new."""
    def run(*args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=target, capture_output=True, text=True)
    top = toplevel(target)
    if top is None or (new and top != target):
        if top is not None:
            out(f"warning: {target} is in the repository {top}; --git=new makes it a repository of its own, nested")
        if run("init", "-q").returncode:
            raise HepError(f"git init failed in {target}")
    elif top != target:
        out(f"committing in the repository {top}, which {target.name}/ is in (--git=new for one of its own)")
    if not files:
        return
    run("add", "--", *files)
    done = run("commit", "-q", "-m", f"hep setup: the work dir {values['name']} (Heimdall {values['revision'][:12] or 'unknown'})",
               "--", *files)
    if done.returncode:
        raise HepError(f"git commit failed in {target}: {done.stderr.strip() or done.stdout.strip()}",
                       hint="set git's user.name and user.email, then commit the added files yourself")


def next_steps(target: Path, added: list[str], project: str | None, git, example: str | None = None) -> list[str]:
    """What to type next (5.3, 7.2): the commands that take the new work dir to a first page (an
    example's) or a first plan, and git's when --git was not given in a repository."""
    here = os.path.relpath(target, Path.cwd())
    lines = ["next:", *([f"  cd {here}"] if here != "." else [])]
    if example:
        first = EXAMPLES[example][1]
        lines += ["  hep build                      # its module programs and Rivet plugins",
                  f"  hep check {first.split()[0]}", f"  hep run {first}         # then open results/…/plots/root/index.html"]
    elif project:
        name = f"{project}/{project.lower()}"
        lines += [f"  hep check {name}", f"  hep run {name} --plan"]
    else:
        lines += ["  hep setup . --project <Project>     # a starter run TOML and card"]
    files = [a for a in added if not a.endswith("/")]
    if not git and toplevel(target) is not None and files:
        lines += [f"  git add -- {' '.join(files[:6])}{' …' if len(files) > 6 else ''}",
                  '  git commit -m "hep setup" -- <the same paths>    # or: hep setup --git, next time']
    return lines


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_datasets(target: Path, out=print) -> list[str]:
    """datasets.toml (U23): `[files."<name>"] url = …, sha256 = …`, each fetched into datasets/<name>
    when it is not there, its sha256 checked, and kept out of git by datasets/.gitignore's marked block
    (small files are tracked as they are). Returns the files hep setup changed (the .gitignore)."""
    manifest = target / MANIFEST
    if not manifest.is_file():
        return []
    try:
        files = tomllib.loads(manifest.read_text(encoding="utf-8")).get("files", {})
    except tomllib.TOMLDecodeError as error:
        raise HepError(f"cannot read {MANIFEST}: {error}", where=str(manifest)) from None
    names = []
    for name, entry in files.items():
        where = f"{manifest}: [files.\"{name}\"]"
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or not isinstance(entry, dict) or not {"url", "sha256"} <= set(entry):
            raise HepError("a dataset is a name under datasets/ with a url and a sha256", where=where,
                           hint='[files."zeus_2012.yoda"]  url = "https://…"  sha256 = "…"')
        names.append(rel.as_posix())
        dest = target / "datasets" / rel
        if dest.is_file():
            if _sha256(dest) != entry["sha256"].lower():
                raise HepError(f"datasets/{rel} is not the file {MANIFEST} names (its sha256 differs)", where=where,
                               hint="remove it, and hep setup fetches it again; or correct the manifest")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".partial")
        try:
            with urllib.request.urlopen(entry["url"], timeout=60) as answer, partial.open("wb") as handle:
                shutil.copyfileobj(answer, handle)
        except (OSError, ValueError) as error:
            partial.unlink(missing_ok=True)
            raise HepError(f"cannot fetch datasets/{rel}: {error}", where=where) from None
        if _sha256(partial) != entry["sha256"].lower():
            partial.unlink()
            raise HepError(f"datasets/{rel} arrived with another sha256: not kept", where=where,
                           hint="the file at the url changed, or the manifest's sha256 is wrong")
        partial.replace(dest)
        out(f"fetched datasets/{rel} ({dest.stat().st_size / 1e6:.1f} MB)")
    ignore = target / "datasets" / ".gitignore"
    return ["datasets/.gitignore"] if _blocked(ignore, [f"/{n}" for n in names]) else []


#: The framework's own files of a work dir, which --refresh brings up to today's template (U28).
REFRESHED = ("Makefile", "README.md", "CLAUDE.md", GUIDE)


def refresh(target: Path, *, yes: bool = False, out=print, ask=None) -> int:
    """`hep setup <dir> --refresh` (U28): each framework-written file (the Makefile, .vscode/, Heimdall's
    README.md and CLAUDE.md or HEIMDALL.md) that differs from today's template, as a diff, then written
    (asked on a terminal unless --yes); the .gitignore's marked block brought up to date. The user's
    files are never touched: a README or CLAUDE.md that is not Heimdall's stays. Returns how many changed."""
    target = target.expanduser().resolve()
    if not is_work(target):
        raise HepError(f"{target} is not a work dir", hint="hep setup <dir> makes one")
    meta = work_meta(target)
    values = {"name": meta["name"], "revision": revision(), "date": datetime.date.today().isoformat(), "P": "", "p": ""}
    changes: dict[Path, str] = {}
    for src in sorted(TEMPLATE.rglob("*")):
        rel = src.relative_to(TEMPLATE)
        if not src.is_file() or rel.parts[0] == STARTER or rel.name in (".gitignore", MARKER_FILE):
            continue
        dest = target / rel
        if rel.name in GUIDES and dest.exists() and not _heimdalls(dest):
            continue                                                 # the repository's own
        old = dest.read_text(encoding="utf-8") if dest.exists() else ""
        if (found := re.search(r"on (\d{4}-\d{2}-\d{2})", old)):  # when it was made stays as it was
            values = {**values, "date": found.group(1)}
        new = _fill(src.read_text(encoding="utf-8"), values)
        if dest.exists() and old != new:
            changes[dest] = new
    guide = target / GUIDE
    if guide.exists():
        theirs = [g for g in GUIDES if (target / g).exists() and not _heimdalls(target / g)]
        old = guide.read_text(encoding="utf-8")
        if (found := re.search(r"on (\d{4}-\d{2}-\d{2})", old)):
            values = {**values, "date": found.group(1)}
        new = _guide(values, "README.md" in theirs, "CLAUDE.md" in theirs)
        if old != new:
            changes[guide] = new
    for path, new in changes.items():
        old = path.read_text(encoding="utf-8")
        rel = path.relative_to(target)
        out("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}")).rstrip("\n"))
    if changes and not yes:
        if ask is None:
            raise HepError(f"{len(changes)} file(s) differ from today's template: not written", hint="--yes writes them")
        if ask(f"write these {len(changes)}? [y/N] ").strip().lower() not in ("y", "yes"):
            out("nothing written")
            return 0
    for path, new in changes.items():
        path.write_text(new, encoding="utf-8")
        out(f"refreshed {path.relative_to(target)}")
    gitignore = target / ".gitignore"
    if gitignore.exists() and BLOCK in gitignore.read_text(encoding="utf-8").splitlines():
        if (missing := _blocked(gitignore, _ignores(TEMPLATE / ".gitignore"))):
            out(f"merged .gitignore: {' '.join(missing)}")
    if not changes:
        out("the framework's files are today's template's")
    return len(changes)


def expects_warning(work: Path) -> str:
    """A warning when the work dir was made by a Heimdall this one does not contain (framework/01 §4.2), or "".

    Warned about, never enforced, as [config.meta] is (V97); no revision, or no git, is no warning."""
    expects = work_meta(work)["expects"]
    root = hep_root()
    if not expects or not (root / ".git").exists():
        return ""
    try:                                                            # its commits that HEAD lacks: none, if an ancestor
        done = subprocess.run(["git", "rev-list", "--max-count=1", expects, "^HEAD"], cwd=root,
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    if done.returncode == 0 and not done.stdout.strip():
        return ""
    return (f"warning: {work.name} was made by Heimdall {expects[:12]}, which {root} does not contain "
            "(an older Heimdall, or one without those commits): git pull there")


def _pth_problem(hep: Path) -> str:
    """What is wrong with the venv's heimdall.pth (framework/01 §5.5), or ""."""
    for folder in site.getsitepackages():
        pth = Path(folder, "heimdall.pth")
        if pth.is_file():
            named = Path(pth.read_text(encoding="utf-8").strip())
            return "" if named == hep / "framework" else f"{pth} names {named}, not {hep / 'framework'}"
    return "the venv has no heimdall.pth (recipes/pth.py writes it): `import hepkit` needs it"


def where(which: str | None = None, out=print, err=None) -> int:
    """Three lines (hep=…, work=…, machine=…), or one path for --hep / --work; 2 when the one asked for is
    not there."""
    err = err or (lambda line: print(line, file=sys.stderr))
    hep = hep_root()
    work = find_work()
    if which == "hep":
        out(str(hep))
        return 0
    if which == "work":
        if work is None:
            err("not inside a work dir (hep setup <dir> makes one)")
            return 2
        out(str(work))
        return 0
    stack = os.environ.get(STACK_VAR, "")
    out(f"hep={hep} {revision(hep)[:12] or '(uncommitted changes)'}" + (f" (stack: {stack})" if stack else ""))
    out(f"work={work if work else '-'}")
    out(f"machine={machine_root()}" + (f" (stack: {stack_dir()})" if stack else ""))
    if problem := _pth_problem(hep):
        err(f"warning: {problem}")
    return 0


__all__ = ["FOLDERS", "MARKER_FILE", "TEMPLATE", "expects_warning", "revision", "setup", "where"]
