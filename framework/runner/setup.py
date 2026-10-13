"""`hep setup` and `hep where`: make a work dir, and say which Heimdall and work dir a shell sees (rank 5).

docs/framework/01_Target.md §4–§5 (D3, D14). What a work dir gets is framework/templates/work/: a
new file there is a template edit, never a code change. In the template, `{{name}}`, `{{revision}}`,
`{{date}}`, `{{P}}` and `{{p}}` are filled in; nothing else is touched (JSON keeps its braces).

    hep setup <dir> [--project P] [--git] [--adopt] [--name N]
    hep where [--hep | --work]
"""

from __future__ import annotations

import datetime
import os
import site
import subprocess
import sys
from pathlib import Path

from .errors import HepError
from .paths import MARKER_FILE, STACK_VAR, find_work, hep_root, is_work, machine_root, stack_dir, work_meta

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "work"
STARTER = "starter"
#: The key folders every work dir has (framework/01 §4.1).
FOLDERS = ("configs", "modules", "datasets", "results", "records", "reports", "build")


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


def _gitignore_missing(existing: Path, template: Path) -> list[str]:
    have = {line.strip() for line in existing.read_text(encoding="utf-8").splitlines()}
    return [line for line in template.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#") and line.strip() not in have]


def setup(target: Path, *, project: str | None = None, git: bool = False, adopt: bool = False,
          name: str | None = None, out=print) -> list[str]:
    """Lay the template down in `target`; never overwrite. Returns what was added (paths relative to it)."""
    target = target.expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise HepError(f"{target} is a file", hint="hep setup makes a work dir: give a folder")
    if target.is_dir() and any(target.iterdir()) and not is_work(target) and not adopt:
        raise HepError(f"{target} is not empty and not a work dir",
                       hint="give an empty or new folder, or --adopt to make a work dir of this one")
    if not TEMPLATE.is_dir():
        raise HepError(f"no work-dir template at {TEMPLATE}")
    if project is not None and (not project or "/" in project or project.startswith(("_", "."))):
        raise HepError(f"'{project}' is not a project name", hint="a folder name: letters, digits, - and _")
    values = {"name": name or target.name, "revision": revision(), "date": datetime.date.today().isoformat(),
              "P": project or "", "p": (project or "").lower()}
    target.mkdir(parents=True, exist_ok=True)
    added: list[str] = []

    def put(src: Path, rel: Path) -> None:
        dest = target / rel
        if dest.exists():
            if adopt and rel.name == ".gitignore":
                missing = _gitignore_missing(dest, src)
                if missing:
                    out(f"kept .gitignore; the template's lines it lacks: {' '.join(missing)}")
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
    if project:
        p = values["p"]
        put(TEMPLATE / STARTER / "run.toml", Path("configs") / project / f"{p}.toml")
        put(TEMPLATE / STARTER / "run.cmnd", Path("configs") / project / f"{p}.cmnd")
        if not (target / "modules" / project).is_dir():
            (target / "modules" / project).mkdir(parents=True)
            added.append(f"modules/{project}/")
            out(f"added modules/{project}/")
    if git:
        _commit(target, [a for a in added if not a.endswith("/")], values)
    return added


def _commit(target: Path, files: list[str], values: dict[str, str]) -> None:
    def run(*args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=target, capture_output=True, text=True)
    if not (target / ".git").exists() and run("init", "-q").returncode:
        raise HepError(f"git init failed in {target}")
    if not files:
        return
    run("add", "--", *files)
    done = run("commit", "-q", "-m", f"hep setup: the work dir {values['name']} (Heimdall {values['revision'][:12] or 'unknown'})")
    if done.returncode:
        raise HepError(f"git commit failed in {target}: {done.stderr.strip() or done.stdout.strip()}",
                       hint="set git's user.name and user.email, then commit the added files yourself")


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
