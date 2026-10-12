#!/usr/bin/env python3
"""recipes/build_stack.py — build the HEP stack from source into Heimdall, as packages.toml and settings.toml say.

    python3 recipes/build_stack.py                          # the core stack into this Heimdall
    python3 recipes/build_stack.py packages=all cores=8     # everything, 8 compilers at once
    python3 recipes/build_stack.py packages="rivet pythia8" root.release=6.40.06
    python3 recipes/build_stack.py --config my.toml         # settings, and package changes, from a file
    python3 recipes/build_stack.py --list                   # each package: release, needs, state
    python3 recipes/build_stack.py --toolkits               # the toolkits: named sets for a kind of work
    python3 recipes/build_stack.py packages=@bsm-recast     # a toolkit (toolkits.toml), with what it needs
    python3 recipes/build_stack.py packages=@gpu-sim        # an isolated toolkit: its own C++20 stack in stacks/gpu-sim/
    python3 recipes/build_stack.py --dry-run > build.sh     # the whole build as a bash script; nothing is run
    python3 recipes/build_stack.py --dry-run --resume       # … only what this prefix still lacks
    python3 recipes/build_stack.py --check-urls             # ask every chosen package's URLs; nothing is downloaded
    python3 recipes/build_stack.py --sha256                 # the checksums of the archives in stash/, as recipe lines
    python3 recipes/build_stack.py --rebuild thepeg         # build it again, and what depends on it (Herwig)
    python3 recipes/build_stack.py --rebuild-broken         # after an OS upgrade: what links a library that is gone
    python3 recipes/build_stack.py thepeg.extra+=--foo env.CXXFLAGS="…"   # append to a list; one variable

A key=value sets; key+=value appends to a list. A list value is split like a shell line (quote an item
with spaces: thepeg.extra+="'LDFLAGS=-L/x -lc++'"), or on commas when it has no spaces.

A setting is a key of settings.toml, given as key=value; a package's key as <package>.<key>=value.
Where things go (docs/framework/01_Target.md §2): archives and their sources in stash/, build trees
and logs in forge/, installs in stack/, the Python environment in env/venv/.
A toolkit (toolkits.toml, and your own in toolkits.d/*.toml) is a named set of packages. One that
changes the C++ standard is isolated: it builds a whole stack of its own in stacks/<toolkit>/
(installs, build trees, venv), loaded by stacks/<toolkit>/setup.sh; stash/ is shared.
A finished package is stamped (stack/.stamps/<name>-<release>, holding a digest of the recipe it was
built with) and skipped after, so a rerun resumes; --rebuild <package> builds it again, with what
depends on it. A package installed some other way (its probe file there, no stamp) is used as it is.
A recipe changed since a package was built is named, not rebuilt on its own. Every tarball is fetched before the first build, so a
dead link stops the run at once: each package's url may be a list (mirrors, tried in order), a
download resumes and retries, and an archive is kept only when it is one (a web page or a cut-off
file is refused, and a sha256 is checked when the recipe gives one). Each package logs to
forge/logs/<name>.log.

Linux and macOS (recipes/platforms/mac/ adds Homebrew and mac.toml). Standard library only: Python
3.11+ (tomllib), or an older Python with tomli.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import hashlib
import json
import threading
import http.client
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NoReturn

try:
    import tomllib
except ModuleNotFoundError:                                        # Python < 3.11
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        sys.exit("build_stack.py reads TOML: it needs Python 3.11+, or the tomli package")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent                                                 # Heimdall: recipes/ is in it
FIELDS = {"release", "url", "sha256", "kind", "needs", "group", "install", "probe", "args", "extra", "optional",
          "patch", "strip", "env", "pre", "post", "cores", "status", "how", "apt", "verify"}
KINDS = ("autotools", "cmake", "unpack", "none", "external")
#: packages = "all": the lab PC's set. Group "toolkit" joins only by name or by toolkit (@name).
ALL_GROUPS = ("core", "extra")
#: The toolkits: the standard presets, then the user's own (one file each, any name).
TOOLKITS = HERE / "toolkits.toml"
TOOLKITS_D = HERE / "toolkits.d"
KIT_FIELDS = {"description", "packages", "note", "isolated", "settings", "override"}
#: Settings that change the ABI: a toolkit that changes one must be isolated (a stack of its own).
ABI = ("cxx_std", "opt_flags")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
MAC = sys.platform == "darwin"
TARBALLS = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")
#: What an archive's first bytes are: gzip, bzip2, xz, zip. A web page starts with "<".
MAGIC = (b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00", b"PK\x03\x04")
#: A download's patience: attempts per URL, seconds between them (doubling), and a read's timeout.
ATTEMPTS, BACKOFF, TIMEOUT = 5, 3, 60

#: stacks/<toolkit>/setup.sh: an isolated stack's loader (`quit` the default environment first).
STACK_SETUP = """#!/bin/bash
# stacks/{stack}/setup.sh — the isolated stack of toolkit @{stack} (C++{cxx_std}), written by recipes/build_stack.py.
# Load it instead of Heimdall's setup.sh, in a shell of its own (or after `quit`): its ABI differs.
HEP_STACK_REQUEST={stack} source "{prefix}/setup.sh"
"""

#: env/machine.sh: this machine's lines from settings.toml's setup_extra; setup.sh (tracked) sources it.
MACHINE = """# env/machine.sh — this machine's lines for setup.sh, written by recipes/build_stack.py from
# settings.toml's setup_extra (not in git).
"""


COLOUR = sys.stderr.isatty() and not os.environ.get("NO_COLOR")


def die(message: str) -> NoReturn:
    sys.exit(f"\033[31merror: {message}\033[0m" if COLOUR else f"error: {message}")


def say(message: str) -> None:
    print(f"\033[1m==> {message}\033[0m" if COLOUR else f"==> {message}", file=sys.stderr, flush=True)


# ── the files and the command line ─────────────────────────────────────────────────────────────

def read(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        die(f"cannot read {path}: {error.strerror}")
    except tomllib.TOMLDecodeError as error:
        die(f"{path}: {error}")


def coerce(text: str, like):
    """A command-line value, as the type of the value it replaces."""
    if isinstance(like, bool):
        return text.lower() in ("1", "true", "yes", "on")
    if isinstance(like, int):
        try:
            return int(text)
        except ValueError:
            die(f"'{text}' is not a number")
    if isinstance(like, list):
        return text.split(",") if "," in text and " " not in text else shlex.split(text)
    return text


def merge(settings: dict, packages: dict, extra: dict) -> None:
    """A --config file: its settings replace, its [package] tables change or add packages."""
    for key, value in extra.items():
        if key in settings:
            if isinstance(settings[key], dict):
                settings[key].update(value)
            else:
                settings[key] = value
        elif isinstance(value, dict):
            packages.setdefault(key, {}).update(value)
        else:
            die(f"--config: no setting '{key}' (settings.toml)")


def options(argv: list[str]) -> tuple[str, dict, dict]:
    settings, packages = read(HERE / "settings.toml"), read(HERE / "packages.toml")
    mode, given = "build", []
    args = iter(argv)
    for arg in args:
        if arg in ("-h", "--help"):
            print(__doc__.split("\n", 1)[1].rstrip())
            sys.exit(0)
        elif arg in ("-n", "--dry-run"):
            mode = "script"
        elif arg == "--resume":
            settings["_resume"] = True
        elif arg == "--check-urls":
            mode = "urls"
        elif arg == "--sha256":
            mode = "sha256"
        elif arg == "--verify":
            mode = "verify"
        elif arg == "--quick":
            settings["_quick"] = True
        elif arg == "--rebuild-broken":
            settings["_rebuild_broken"] = True
        elif arg == "--rebuild":
            settings.setdefault("_rebuild", []).extend(next(args, "").replace(",", " ").split()
                                                       or die("--rebuild needs a package"))
        elif arg == "--list":
            mode = "list"
        elif arg == "--toolkits":
            mode = "toolkits"
        elif arg == "--config":
            file = Path(next(args, "") or die("--config needs a file"))
            merge(settings, packages, read(file))
            settings.setdefault("_configs", []).append(str(file))
        elif "=" in arg:
            key, text = arg.split("=", 1)
            given.append((key[:-1], text, "+=") if key.endswith("+") else (key, text, "="))
            if key == "packages":
                settings["_packages_given"] = True
        else:
            die(f"unknown argument '{arg}' (see --help)")
    wanted = next((text for key, text, _ in reversed(given) if key == "packages"), settings["packages"])
    apply_toolkits(wanted, settings, packages)                     # the toolkits' own settings, then …
    for key, text, op in given:                                    # after --config: the command line wins
        parts = key.split(".")
        if parts[0] == "env" and len(parts) == 2:                  # env.VAR=…: one variable of the build
            settings["env"][parts[1]] = text
            continue
        if len(parts) == 3 and parts[1] == "env":                  # <package>.env.VAR=…
            if parts[0] not in packages:
                die(f"no package '{parts[0]}' (packages.toml)")
            packages[parts[0]].setdefault("env", {})[parts[2]] = text
            continue
        if len(parts) == 1:
            if key.startswith("_") or key not in settings or isinstance(settings[key], dict):
                die(f"no setting '{key}' (settings.toml)")
            target, field = settings, key
        elif len(parts) == 2 and parts[0] in packages:
            if parts[1] not in FIELDS or parts[1] == "env":
                die(f"a package has no key '{parts[1]}' (packages.toml says which)")
            target, field = packages[parts[0]], parts[1]
        else:
            die(f"no package '{parts[0]}' (packages.toml)" if len(parts) == 2 else f"no such key '{key}'")
        old = target.get(field, "")
        if op == "+=":
            current = shlex.split(old) if isinstance(old, str) else list(old)
            target[field] = current + coerce(text, [])
        else:
            target[field] = coerce(text, old)
    for name, p in packages.items():
        if unknown := sorted(set(p) - FIELDS):
            die(f"[{name}] has no key {', '.join(unknown)}")
        if p.get("kind") not in KINDS:
            die(f"[{name}].kind must be one of {', '.join(KINDS)}")
        if p["kind"] not in ("none", "external") and not p.get("url"):
            die(f"[{name}] has no url")
        if p["kind"] == "external" and not p.get("how"):
            die(f"[{name}] is external: it needs a 'how' (where it comes from)")
        for other in [*p.get("needs", []), *p.get("optional", {})]:
            if other not in packages:
                die(f"[{name}] names '{other}', which is not a package")
        if "verify" in p and (wrong := checker().problems(name, p["verify"])):
            die("; ".join(wrong))
    return mode, settings, packages


# ── placeholders ───────────────────────────────────────────────────────────────────────────────

def probe(command: list[str]) -> str:
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()


def ram_kb() -> int:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // 1024    # Linux and macOS
    except (ValueError, OSError):
        return 8_000_000


def context(s: dict) -> dict:
    """The placeholders every package sees: the settings, and what follows from them."""
    prefix = Path(s["prefix"] or REPO).expanduser().resolve()     # "": this Heimdall
    stack = s.get("_stack", "")                                   # an isolated toolkit's: stacks/<it>/
    base = prefix / "stacks" / stack if stack else prefix
    python = shutil.which(s["python"]) or die(f"no {s['python']}: install Python 3, or set python=")
    py = probe([python, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"])
    cores = s["cores"] or (len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity")   # Linux: the
                           else os.cpu_count() or 4)                                       # CPUs it may use
    machine = os.uname().machine
    return {**s, "prefix": str(prefix), "inst": str(base / "stack"),
            "venv": str(base / "venv" if stack else prefix / "env" / "venv"),
            "stash": str(prefix / "stash"), "forge": str(base / "forge"), "stack": stack,
            "venv_prompt": f"HEP-{stack}" if stack else "HEP",
            "cores": cores, "root_cores": s["root_cores"] or max(1, min(cores, ram_kb() // 3_000_000)),
            "python": python, "py": py, "pyxy": py.replace(".", ""),
            "pyinc": probe([python, "-c", "import sysconfig; print(sysconfig.get_paths()['include'])"]),
            "cxxflags": f"{s['opt_flags']} -std=c++{s['cxx_std']}", "arch": {"x86_64": "x64"}.get(machine, machine),
            "machine": machine, "dylib": "dylib" if MAC else "so",
            "repo": str(REPO), "cmake_prefix": ""}                   # filled in main(): every install folder


def scope(name: str, p: dict, c: dict) -> dict:
    """A package's own placeholders on top of the run's."""
    release = str(p.get("release", ""))
    return {**c, "release": release, "series": release.rpartition(".")[0] or release,
            "src": f"{c['stash']}/{name}", "build": f"{c['forge']}/{name}",
            "install": f"{c['inst']}/{p.get('install', name)}"}


def expand(text: str, k: dict) -> str:
    def one(match: re.Match) -> str:
        if match[1] not in k and match[1] not in os.environ:      # an environment variable: {HOMEBREW_PREFIX}
            die(f"no placeholder {{{match[1]}}} (in '{text}')")
        value = k.get(match[1], os.environ.get(match[1]))
        return " ".join(map(str, value)) if isinstance(value, list) else str(value)
    return PLACEHOLDER.sub(one, str(text))


def words(items: list[str], k: dict) -> list[str]:
    """Arguments: each item one word, but an item that is only a list placeholder gives its words."""
    out = []
    for item in items:
        whole = PLACEHOLDER.fullmatch(item)
        if whole and isinstance(k.get(whole[1]), list):
            out += [expand(value, k) for value in k[whole[1]]]
        else:
            out.append(expand(item, k))
    return out


# ── the packages ───────────────────────────────────────────────────────────────────────────────

def stamp(name: str, p: dict, c: dict) -> Path:
    return Path(c["inst"], ".stamps", name + (f"-{p['release']}" if p.get("release") else ""))


def building(name: str, p: dict, c: dict) -> Path:
    """The marker of a build under way: left behind, it says the last attempt did not finish."""
    return stamp(name, p, c).with_name(stamp(name, p, c).name + ".building")


def digest(name: str, p: dict, c: dict) -> str:
    """What a package's build depends on, hashed: its recipe (not where it is downloaded from), the
    ABI, and the lists it installs. Kept in its stamp; a different one means the recipe changed."""
    recipe = {k: p.get(k) for k in ("release", "kind", "args", "extra", "optional", "patch", "strip", "env",
                                     "pre", "post", "install")}
    recipe["abi"] = [c["cxx_std"], c["opt_flags"]]
    for key, owner in (("python_packages", "python"), ("pdf_sets", "pdfsets"), ("ufo_models", "ufo-models")):
        if name == owner:
            recipe[key] = c.get(key)
    if p.get("patch") and (REPO / p["patch"]).is_file():
        recipe["patch_sha256"] = sha256_of(REPO / p["patch"])
    return hashlib.sha256(json.dumps(recipe, sort_keys=True, default=str).encode()).hexdigest()[:16]


def state(name: str, p: dict, c: dict) -> str:
    """built | changed (the recipe differs from the one it was built with) | built (no digest) (stamped
    before digests) | failed (an attempt did not finish) | installed (some other way) | "" (absent)."""
    file = stamp(name, p, c)
    if file.exists():
        kept = file.read_text(encoding="utf-8").strip() if file.stat().st_size else ""
        return "built (no digest)" if not kept else "built" if kept == digest(name, p, c) else "changed"
    if building(name, p, c).exists():
        return "failed"
    marker = p.get("probe", "{install}")
    return "installed" if marker and Path(expand(marker, scope(name, p, c))).exists() else ""


def present(name: str, p: dict, c: dict) -> bool:
    """Built here (stamped), or installed some other way (its probe file is there, and no attempt of
    ours failed in it). A dry run without --resume sees an empty prefix: it prints the whole build."""
    if c.get("fresh"):
        return False
    return state(name, p, c) not in ("", "failed")


def urls_of(name: str, p: dict, c: dict) -> list[str]:
    """A package's URLs: one, or a list of mirrors tried in order."""
    given = p["url"] if isinstance(p["url"], list) else [p["url"]]
    return [expand(url, scope(name, p, c)) for url in given]


def tarball(name: str, p: dict, c: dict) -> tuple[Path, str]:
    """Where the archive goes, and its first URL (the others are mirrors: urls_of)."""
    url = urls_of(name, p, c)[0]
    ending = next((end for end in TARBALLS if any(u.endswith(end) for u in urls_of(name, p, c))), ".tar")
    return Path(c["stash"], f"{name}-{p.get('release', '')}{ending}"), url


def toolkits() -> dict:
    """The toolkits: toolkits.toml's presets and the user's toolkits.d/*.toml (recipes/README.md §6).
    A name defined twice is refused, so a custom toolkit never silently replaces a preset."""
    kits: dict = {}
    for file in [TOOLKITS, *sorted(TOOLKITS_D.glob("*.toml"))] if TOOLKITS_D.is_dir() else [TOOLKITS]:
        for name, kit in read(file).items():
            if name in kits:
                die(f"toolkit '{name}' is defined twice: {kits[name]['_file']} and {file.name}")
            if not isinstance(kit, dict):
                die(f"{file.name}: '{name}' is not a [toolkit] table")
            if unknown := sorted(set(kit) - KIT_FIELDS):
                die(f"{file.name}: [{name}] has no key {', '.join(unknown)} (toolkits.toml's header says which)")
            kits[name] = {**kit, "_file": file.name}
    return kits


def kits_in(want: list[str], kits: dict, seen: tuple[str, ...] = ()) -> list[str]:
    """The toolkits a packages value names, with the ones they name in turn."""
    out: list[str] = []
    for word in want:
        if word.startswith("@") and word[1:] in kits and word[1:] not in seen:
            out += [word[1:], *kits_in(kits[word[1:]].get("packages", []), kits, (*seen, word[1:]))]
    return list(dict.fromkeys(out))


def apply_toolkits(wanted, settings: dict, packages: dict) -> None:
    """The requested toolkits' settings and package overrides. A toolkit that changes the ABI
    (cxx_std, opt_flags) must be isolated, and a run builds at most one isolated stack."""
    kits = toolkits()
    named = kits_in(wanted.split() if isinstance(wanted, str) else list(wanted), kits)
    isolated = [k for k in named if kits[k].get("isolated")]
    if len(isolated) > 1:
        die(f"one isolated stack per run: {', '.join('@' + k for k in isolated)}")
    settings["_stack"] = isolated[0] if isolated else ""
    for name in named:
        kit = kits[name]
        for key, value in kit.get("settings", {}).items():
            if key not in settings or isinstance(settings[key], dict):
                die(f"toolkit @{name}: no setting '{key}' (settings.toml)")
            if key in ABI and value != settings[key] and not kit.get("isolated"):
                die(f"toolkit @{name} changes {key}: it must be isolated (isolated = true), "
                    "or its packages would share an install with another ABI")
            settings[key] = value
        for package, fields in kit.get("override", {}).items():
            if package not in packages:
                die(f"toolkit @{name}: no package '{package}' to override")
            if unknown := sorted(set(fields) - FIELDS):
                die(f"toolkit @{name}: a package has no key {', '.join(unknown)}")
            packages[package].update(fields)


def chosen_of(want: list[str], packages: dict, kits: dict, seen: tuple[str, ...] = ()) -> list[str]:
    """Names, "core", "all" and @toolkits, expanded to package names (a toolkit may name another)."""
    out: list[str] = []
    for word in want:
        if word == "core":
            out += [n for n, p in packages.items() if p.get("group", "core") == "core"]
        elif word == "all":
            out += [n for n, p in packages.items() if p.get("group", "core") in ALL_GROUPS]
        elif word.startswith("@"):
            kit = word[1:]
            if kit not in kits:
                die(f"no toolkit '{kit}'; there are: {' '.join(kits)} (--toolkits)")
            if kit in seen:
                die("the toolkits go round: " + " → ".join([*seen, kit]))
            out += chosen_of(kits[kit].get("packages", []), packages, kits, (*seen, kit))
        elif word in packages:
            out.append(word)
        else:
            die(f"no package '{word}'; there are: {' '.join(packages)}")
    return list(dict.fromkeys(out))


def checker():
    """recipes/verify.py: a package's checks, and the scan for libraries that no longer resolve."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("heimdall_verify", HERE / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checks(name: str, p: dict, c: dict, env: dict[str, str], quick: bool = False, slow_ok: bool = True) -> list:
    """A package's [[verify]] rows (recipes/verify.py)."""
    k = scope(name, p, c)
    return checker().run(name, p.get("verify", []), lambda text: expand(text, k), f"{c['venv']}/bin/python",
                         env, quick=quick, slow_ok=slow_ok)


def doctor_rows(packages: dict, c: dict, env: dict[str, str], quick: bool = False) -> list:
    """--verify (and `hep doctor`): every installed package's checks, then each install folder's scan."""
    rows, scanned = [], set()
    v = checker()
    for name, p in packages.items():
        if p["kind"] == "external" or state(name, p, c) in ("", "failed"):
            continue
        rows += checks(name, p, c, env, quick=quick)
        folder = scope(name, p, c)["install"]
        if p["kind"] != "none" and folder not in scanned:          # each install folder once (ThePEG and Herwig share one)
            scanned.add(folder)
            n, lost = v.scan(Path(folder))
            if n:
                rows.append((name, f"libraries ({Path(folder).name}/)", "FAIL" if lost else "ok",
                             " ".join(lost)[:140] if lost else f"{n} files"))
    return rows


def broken(packages: dict, c: dict) -> dict[str, list[str]]:
    """The installed packages whose programs or libraries need a library that no longer resolves (an OS
    upgrade replaced it), each with what is missing. Packages sharing a folder (ThePEG, Herwig) go
    together."""
    v, out, seen = checker(), {}, {}
    for name, p in packages.items():
        if p["kind"] in ("none", "external") or state(name, p, c) in ("", "failed"):
            continue
        folder = scope(name, p, c)["install"]
        if folder not in seen:
            seen[folder] = v.scan(Path(folder))[1]
        if seen[folder]:
            out[name] = seen[folder]
    return out


def record_links(name: str, p: dict, c: dict) -> None:
    """Beside a package's stamp, the libraries from outside the stack its binaries link, so a later OS
    upgrade can be traced to what it took away (<stamp>.libs: one line each)."""
    v, folder, found = checker(), Path(scope(name, p, c)["install"]), set()
    for sub in ("bin", "lib", "lib64"):
        for path in sorted((folder / sub).rglob("*")) if (folder / sub).is_dir() else []:
            if len(found) > 400 or path.is_symlink() or not path.is_file() or not v.is_binary(path):
                continue
            for line in v.links_of(str(path)).splitlines():
                words = line.replace("=>", " ").split()
                lib = next((w for w in words if w.startswith("/")), "")
                if lib and not lib.startswith((c["inst"], c["prefix"], "/System/", "/usr/lib/system/")):
                    found.add(lib)
    stamp(name, p, c).with_name(stamp(name, p, c).name + ".libs").write_text(
        "".join(f"{lib}\n" for lib in sorted(found)), encoding="utf-8")


def rebuild_set(names: list[str], packages: dict, c: dict) -> list[str]:
    """--rebuild: the packages named, and every installed package that needs one of them, in turn."""
    for name in names:
        if name not in packages:
            die(f"--rebuild: no package '{name}'")
    out = list(dict.fromkeys(names))
    grew = True
    while grew:
        grew = False
        for name, p in packages.items():
            if name not in out and state(name, p, c) and set(p.get("needs", [])) & set(out):
                out.append(name)
                grew = True
    return out


def plan(s: dict, packages: dict, c: dict) -> tuple[list[str], list[str]]:
    """The packages to go through, in build order, and those of them added because others need them."""
    want = s["packages"].split() if isinstance(s["packages"], str) else list(s["packages"])
    rebuild = s.get("_rebuild", [])
    if rebuild and not s.get("_packages_given"):                    # --rebuild alone: only those, and theirs
        want = []
    chosen = chosen_of(want, packages, toolkits()) + [n for n in rebuild_set(rebuild, packages, c) if n not in want]
    chosen = list(dict.fromkeys(chosen))
    order: list[str] = []

    def visit(name: str, chain: list[str]) -> None:
        if name in order:
            return
        if name in chain:
            die("the needs go round: " + " → ".join([*chain, name]))
        for need in packages[name].get("needs", []):
            if need in chosen or not present(need, packages[need], c):
                visit(need, [*chain, name])
        for other in packages[name].get("optional", {}):           # an optional one in the run goes first,
            if other in chosen:                                    # so its flags apply (YODA after HDF5)
                visit(other, [*chain, name])
        order.append(name)

    for name in packages:                                          # the file's order, needs first
        if name in chosen:
            visit(name, [])
    return order, [n for n in order if n not in chosen]


#: The lines of a failed step's log worth showing first: the errors, not the warnings around them.
ERRORS = re.compile(r"(error:|Error \d+|fatal error|CMake Error|undefined reference to|No such file or directory"
                    r"|command not found|\*\*\* \[|Traceback|Abort trap|Segmentation fault)")
PERCENT = re.compile(r"\[\s*(\d+)%\]")


def minutes(seconds: float) -> str:
    seconds = int(seconds)
    return (f"{seconds // 3600}h {seconds % 3600 // 60:02d}min" if seconds >= 3600
            else f"{seconds // 60}min {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s")


def log_tail(path: Path, lines: int) -> list[str]:
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 16384))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if line.strip()][-lines:]


class Progress:
    """On a terminal: a status line for the step under way and a three-line window on its log,
    redrawn twice a second and cleared when the step ends. Elsewhere: nothing."""
    SPIN = "|/-\\"

    def __init__(self, shell: "Shell", step: str):
        self.shell, self.step, self.drawn, self.done = shell, step, 0, threading.Event()
        self.live = sys.stderr.isatty() and not os.environ.get("HEP_PLAIN")
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def __enter__(self):
        if self.live:
            self.thread.start()
        return self

    def __exit__(self, *exc):
        self.done.set()
        if self.live:
            self.thread.join()
            self.clear()

    def clear(self):
        if self.drawn:
            sys.stderr.write(f"\x1b[{self.drawn}F\x1b[J")
            sys.stderr.flush()
            self.drawn = 0

    def loop(self):
        tick = 0
        while not self.done.wait(0.5):
            width = shutil.get_terminal_size((100, 20)).columns - 2
            tail = log_tail(self.shell.log, 40)
            pct = next((m[1] + "%" for line in reversed(tail) if (m := PERCENT.search(line))), "")
            s = self.shell
            head = (f"  {self.SPIN[tick % 4]} [{s.position}] {s.name}: {self.step}  "
                    f"{minutes(time.monotonic() - s.started)}" + (f"  {pct}" if pct else ""))
            lines = [head[:width], *("    │ " + line[: width - 6] for line in tail[-3:])]
            self.clear()
            sys.stderr.write("\n".join(lines) + "\n")
            sys.stderr.flush()
            self.drawn = len(lines)
            tick += 1


def failure_excerpt(log: Path) -> str:
    """A failed step's log, as much as helps: its first error lines with a line of context, then its end."""
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [i for i, line in enumerate(lines) if ERRORS.search(line) and "warning" not in line.lower()]
    shown: list[str] = []
    seen: set[int] = set()
    for i in hits[:12]:
        for j in range(max(0, i - 1), min(len(lines), i + 2)):
            if j not in seen:
                seen.add(j)
                shown.append(lines[j])
    end = lines[-15:]
    if shown:
        return "\n".join(["the first errors:", *("  " + line for line in shown), "", "the log's end:",
                          *("  " + line for line in end)])
    return "\n".join(["the log's end:", *("  " + line for line in end)])


class Shell:
    """Runs the build's commands, each into its package's log; for --dry-run, prints them as bash."""

    def __init__(self, script: bool, env: dict[str, str]):
        self.script, self.env, self.name, self.log = script, env, "setup", Path(os.devnull)
        self.position, self.started = "", time.monotonic()

    def run(self, argv: list[str], cwd: str | None = None, env: dict[str, str] | None = None) -> None:
        if self.script:
            line = " ".join([*(f"{key}={shlex.quote(value)}" for key, value in (env or {}).items()),
                             shlex.join(argv)])
            print(f"cd {shlex.quote(cwd)} && {line}" if cwd else line)
            return
        step = " ".join(Path(argv[0]).name.split()[:1] + [a for a in argv[1:3] if a.startswith("-") or a in
                                                           ("install", "--build", "--install")])
        with open(self.log, "a", encoding="utf-8") as log:
            log.write(f"+ {shlex.join(argv)}\n")
            log.flush()
            with Progress(self, step):
                try:
                    code = subprocess.run(argv, cwd=cwd, env={**self.env, **(env or {})}, stdin=subprocess.DEVNULL,
                                          stdout=log, stderr=subprocess.STDOUT).returncode
                except OSError as error:
                    log.write(f"{error}\n")
                    code = 127
        if code:
            print(failure_excerpt(self.log), file=sys.stderr)
            die(f"{self.name}: '{shlex.join(argv)}' failed; the whole log is {self.log}")


def sha256_of(file: Path) -> str:
    digest = hashlib.sha256()
    with open(file, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def archive_problem(file: Path, sha256: str = "", full: bool = True) -> str | None:
    """Why a file is not the archive it should be, or None. `full`: also list it (tar -t), which
    reads it whole and so finds a cut-off file."""
    if not file.is_file() or not file.stat().st_size:
        return "empty or missing"
    head = file.open("rb").read(512)
    if head.lstrip()[:1] == b"<" or b"<html" in head.lower():
        return "the server sent a web page, not the archive"
    if not head.startswith(MAGIC):
        return f"not an archive (it starts with {head[:8]!r})"
    if sha256 and sha256_of(file) != sha256.lower():
        return f"sha256 differs from the recipe's ({sha256[:12]}…)"
    if full:
        listing = (["unzip", "-tq", str(file)] if head.startswith(b"PK") else ["tar", "-tf", str(file)])
        check = subprocess.run(listing, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if check.returncode:
            return "cut off or damaged: " + (check.stderr.strip().splitlines() or ["tar -t failed"])[-1]
    return None


def download(file: Path, url: str) -> str | None:
    """One URL into `file`, resuming a partial .part and retrying; None, or why it failed."""
    part = file.with_name(file.name + ".part")
    error = "no attempt"
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(BACKOFF * 2 ** (attempt - 1))
        have = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": "build_stack.py"} | ({"Range": f"bytes={have}-"} if have else {})
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                resumed = have and response.status == 206
                with open(part, "ab" if resumed else "wb") as out:
                    shutil.copyfileobj(response, out, 1 << 20)
                expected = response.headers.get("Content-Length")
                if expected and part.stat().st_size < int(expected) + (have if resumed else 0):
                    raise http.client.IncompleteRead(b"", int(expected))
            part.replace(file)
            return None
        except urllib.error.HTTPError as failure:
            if failure.code == 416 and part.exists():              # a range past the end: the .part is whole
                part.replace(file)
                return None
            error = f"HTTP {failure.code} {failure.reason}"
            if failure.code in (403, 404, 410):                    # no point retrying a missing file
                break
        except (OSError, ValueError, http.client.HTTPException) as failure:   # IncompleteRead included
            error = f"{type(failure).__name__}: {failure}"
    return error


def fetch(items: list[tuple[Path, list[str], str]], shell: Shell) -> None:
    """Every archive the run needs, four at a time, before anything is built: kept only when it is
    one (archive_problem). An archive already there is checked the same way, and fetched again when
    it is not one."""
    if shell.script:
        for file, urls, sha256 in items:
            f = shlex.quote(str(file))
            tries = " || ".join(f"curl -fL -C - --retry 5 --retry-all-errors -o {f}.part {shlex.quote(u)}"
                                for u in urls)
            check = (f" && echo {shlex.quote(sha256)}' '{f}.part | sha256sum -c -" if sha256 else "")
            print(f"[ -s {f} ] || {{ {{ {tries}; }} && tar -tf {f}.part > /dev/null{check} && mv {f}.part {f}; }}")
        return
    todo = []
    for file, urls, sha256 in items:
        if file.exists() and (problem := archive_problem(file, sha256)):
            say(f"{file.name}: {problem}; fetching it again")
            file.unlink()
        if not file.exists():
            todo.append((file, urls, sha256))
    if not todo:
        return
    say(f"downloading {len(todo)} archive{'s' if len(todo) > 1 else ''}")

    def get(item: tuple[Path, list[str], str]) -> str | None:
        file, urls, sha256 = item
        reasons = []
        for url in urls:
            if failure := download(file, url):
                reasons.append(f"{url}: {failure}")
                continue
            if problem := archive_problem(file, sha256):
                reasons.append(f"{url}: {problem}")
                file.unlink()
                file.with_name(file.name + ".part").unlink(missing_ok=True)
                continue
            return None
        return f"{file.name}: " + "; ".join(reasons)

    with ThreadPoolExecutor(4) as pool:
        if errors := [error for error in pool.map(get, todo) if error]:
            die("downloads failed (set <package>.url=…, or put the archive in stash/ yourself):\n  "
                + "\n  ".join(errors))


def check_urls(order: list[str], packages: dict, c: dict) -> None:
    """--check-urls: each chosen package's URLs asked for their headers (nothing downloaded), and what
    answered: an archive, a web page, or nothing."""
    bad = 0
    for name in order:
        p = packages[name]
        if p["kind"] in ("none", "external"):
            continue
        answered = False
        for url in urls_of(name, p, c):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "build_stack.py", "Range": "bytes=0-511"})
                with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                    head = response.read(512)
                    kind = ("web page" if head.lstrip()[:1] == b"<" else "archive" if head.startswith(MAGIC)
                            else "unknown content")
                    size = response.headers.get("Content-Range", "").rpartition("/")[2] or "?"
            except urllib.error.HTTPError as failure:
                kind, size = f"HTTP {failure.code}", "-"
            except (OSError, ValueError, http.client.HTTPException) as failure:
                kind, size = type(failure).__name__, "-"
            ok = kind == "archive"
            answered |= ok
            size = size if size not in ("0", "") else "?"
            print(f"{'ok  ' if ok else 'dead'} {name:13} {kind:15} {size:>11}  {url}")
        if not answered:
            bad += 1
            print(f"BAD  {name}: no URL answers with an archive")
    if bad:
        die(f"{bad} package(s) cannot be downloaded: set <package>.url=…")


def build(name: str, p: dict, c: dict, shell: Shell, have: set[str]) -> None:
    k = scope(name, p, c)
    kind = p["kind"]
    if kind != "none":
        into = k["install"] if kind == "unpack" else k["src"]      # afresh, so a failed try leaves nothing
        shell.run(["rm", "-rf", into])
        shell.run(["mkdir", "-p", into])
        shell.run(["tar", "xf", str(tarball(name, p, c)[0]), "-C", into, f"--strip-components={p.get('strip', 1)}"])
    if p.get("patch"):
        shell.run(["patch", "-d", k["src"], "-p0", "-i", str(REPO / expand(p["patch"], k))])
    env = {key: expand(value, k) for key, value in p.get("env", {}).items()}
    where = {"unpack": k["install"], "none": c["prefix"]}.get(kind, k["src"])
    for text in p.get("pre", []):
        shell.run(words(shlex.split(text), k), where, env)
    extra = p.get("extra", [])
    args = words([*p.get("args", []), *(shlex.split(extra) if isinstance(extra, str) else extra)], k)
    for other, extra in p.get("optional", {}).items():
        if other in have:
            args += words(extra, k)
    jobs = f"-j{expand(str(p.get('cores', '{cores}')), k)}"                 # make's and cmake's: compilers at once
    if kind == "autotools":
        shell.run(["./configure", f"--prefix={k['install']}", *args], k["src"], env)
        shell.run(["make", jobs], k["src"], env)
        shell.run(["make", "install"], k["src"], env)
    elif kind == "cmake":
        shell.run(["cmake", "-S", k["src"], "-B", k["build"], f"-DCMAKE_INSTALL_PREFIX={k['install']}",
                   "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_CXX_STANDARD={c['cxx_std']}", *args], env=env)
        shell.run(["cmake", "--build", k["build"], jobs], env=env)
        shell.run(["cmake", "--install", k["build"]], env=env)
    for text in p.get("post", []):
        shell.run(words(shlex.split(text), k), where, env)


def system(s: dict, c: dict, shell: Shell, extra: list[str] = ()) -> None:
    """apt_packages and the chosen packages' own (`apt`), through sudo when not root; stamped like a
    package, by what it installed: a run that adds packages installs again."""
    wanted = list(dict.fromkeys([*s["apt_packages"], *extra]))
    done = Path(c["inst"], ".stamps", "system" + (f"-{len(wanted)}" if extra else ""))
    if done.exists():
        say("system packages: done already")
        return
    if not shutil.which("apt-get"):
        die("no apt-get: install settings.toml's apt_packages (under this system's names), then system=false")
    sudo = [] if os.geteuid() == 0 else ["sudo"]
    say("system packages (apt)")
    shell.name, shell.log = "system", Path(c["forge"], "logs", "system.log")
    if sudo and not shell.script and subprocess.run(["sudo", "-v"]).returncode:    # its prompt, not in the log
        die("sudo failed: run as root, or install the system packages and set system=false")
    shell.run([*sudo, "apt-get", "update"])
    shell.run([*sudo, "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y",
               "--no-install-recommends", *wanted])
    if not shell.script:
        done.touch()


def environment(s: dict, c: dict, packages: dict) -> tuple[dict[str, list[str]], dict[str, str]]:
    """The build's paths (each install's bin/, lib/ and Python directory; the venv first) and [env]."""
    dirs = dict.fromkeys(f"{c['inst']}/{p.get('install', n)}" for n, p in packages.items() if p["kind"] != "none")
    paths = {"PATH": [f"{c['venv']}/bin", *(f"{d}/bin" for d in dirs)],
             "DYLD_LIBRARY_PATH" if MAC else "LD_LIBRARY_PATH": [f"{d}/lib" for d in dirs],
             "PYTHONPATH": [*(f"{d}/lib/python{c['py']}/site-packages" for d in dirs),
                            *(f"{d}/lib" for d in dirs)]}             # ROOT's and Pythia's modules sit in lib/
    return paths, {key: expand(value, c) for key, value in s["env"].items()}


#: The user's environment the build keeps: the rest (ROOTSYS, LD_LIBRARY_PATH, PYTHONPATH, another
#: stack's paths, a venv or conda) never reaches a configure script (docs/audit_3/01_Process.md C).
KEEP_ENV = ("HOME", "USER", "LOGNAME", "SHELL", "TERM", "TMPDIR", "LANG", "TZ", "DISPLAY", "SSH_AUTH_SOCK",
            "http_proxy", "https_proxy", "no_proxy", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
            "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE",
            "CC", "CXX", "FC", "F77", "SUDO_ASKPASS")
KEEP_PREFIXES = ("LC_", "HOMEBREW_", "XDG_")
#: Programs that mark another HEP stack's bin/ on PATH: such an entry is left out of the build's PATH.
FOREIGN = ("root-config", "thisroot.sh", "rivet-config", "yoda-config", "pythia8-config", "lhapdf-config",
           "fastjet-config", "HepMC3-config", "geant4-config")
#: System folders that may hold such a program (Homebrew's formulae): kept, and the preflight warns.
SYSTEM_BINS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin", "/opt/homebrew/bin")


def clean_environment(c: dict) -> tuple[dict[str, str], list[str]]:
    """The user's environment, cleaned for the build: what KEEP_ENV keeps, and PATH without another
    stack's bin/ or the active venv's. Returns it, and what was left out (to say once)."""
    env = {k: v for k, v in os.environ.items() if k in KEEP_ENV or k.startswith(KEEP_PREFIXES)}
    dropped = sorted(k for k in ("ROOTSYS", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH",
                                 "PYTHONPATH", "CMAKE_PREFIX_PATH", "PKG_CONFIG_PATH", "CPATH", "LIBRARY_PATH",
                                 "VIRTUAL_ENV", "CONDA_PREFIX", "LHAPDF_DATA_PATH") if os.environ.get(k))
    own = c["inst"]
    venv = os.environ.get("VIRTUAL_ENV", "")
    kept = []
    for entry in os.environ.get("PATH", "").split(":"):
        if not entry or entry in kept:
            continue
        foreign = (venv and entry.startswith(venv)) or (os.environ.get("CONDA_PREFIX") and entry.startswith(os.environ["CONDA_PREFIX"]))
        if not foreign and entry not in SYSTEM_BINS and not entry.startswith(own):
            foreign = any(Path(entry, name).exists() for name in FOREIGN)
        if foreign or entry.startswith(own):                       # the stack's own come first, from paths
            dropped.append(f"PATH:{entry}")
            continue
        kept.append(entry)
    env["PATH"] = ":".join(kept)
    return env, dropped


def preflight(s: dict, c: dict, order: list[str]) -> None:
    """What will cause trouble, said before anything is downloaded (docs/audit_3/01_Process.md C, H)."""
    if MAC and not any(Path(f).name == "mac.toml" for f in s.get("_configs", [])):
        die("on macOS, build through recipes/platforms/mac/build.sh (Homebrew's packages and mac.toml): "
            f"bash recipes/platforms/mac/build.sh {' '.join(sys.argv[1:])}".rstrip())
    notes = []
    if os.environ.get("ROOTSYS"):
        notes.append(f"ROOTSYS={os.environ['ROOTSYS']} is set by your shell: the build leaves it out "
                     "(remove it from your shell's startup file, or ROOT's own builds may trip on it)")
    if shutil.which("brew"):
        listed = subprocess.run(["brew", "list", "--formula", "-1"], capture_output=True, text=True).stdout.split()
        clash = sorted(set(listed) & {"root", "hepmc3", "fastjet", "lhapdf", "pythia", "yoda", "rivet", "herwig",
                                       "thepeg", "sherpa", "geant4", "delphes"})
        if clash:
            notes.append(f"Homebrew has HEP formulae of its own ({' '.join(clash)}): their headers sit in "
                         "the build's search path; `brew uninstall` them, or expect mixed versions")
    free = shutil.disk_usage(Path(c["prefix"]) if Path(c["prefix"]).exists() else Path.home()).free / 2**30
    if free < 25 and not c.get("fresh"):
        notes.append(f"{free:.0f} GB free where the stack goes: the core needs about 20 GB while building")
    for note in notes:
        say(f"preflight: {note}")


def show(order: list[str], packages: dict, c: dict) -> None:
    """Each package: built here (stamped) or installed otherwise, and whether this run builds it."""
    print(f"{'package':13} {'release':10} {'group':8} {'state':18} {'this run':9} needs")
    rebuild = set(c.get("rebuild", []))
    for name, p in packages.items():
        now = "external" if p["kind"] == "external" else state(name, p, c)
        run = ("rebuild" if name in rebuild else "build" if name in order and now in ("", "failed")
               and p["kind"] != "external" else "")
        flag = " (recipe not yet proven by a build)" if p.get("status") == "new" else ""
        print(f"{name:13} {str(p.get('release', '—')):10} {p.get('group', 'core'):8} {now:18} {run:9} "
              f"{' '.join(p.get('needs', []))}{flag}")


def show_toolkits(packages: dict) -> None:
    """The toolkits, each with what it is for and its packages."""
    for name, kit in toolkits().items():
        names = chosen_of(kit.get("packages", []), packages, toolkits())
        print(f"@{name:15} {kit.get('description', '')}")
        print(f"{'':16} {' '.join(names)}")
        if kit.get("note"):
            print(f"{'':16} note: {kit['note']}")


def machine_text(c: dict) -> str:
    """env/machine.sh: settings.toml's setup_extra lines (macOS: DYLD_LIBRARY_PATH, the GNU tools)."""
    return MACHINE + "".join(expand(line, c) + "\n" for line in c["setup_extra"])


def main(argv: list[str]) -> None:
    mode, s, packages = options(argv)
    c = context(s)
    if mode == "toolkits":
        show_toolkits(packages)
        return
    script = mode == "script"
    c["fresh"] = script and not s.get("_resume")                  # a dry run prints the whole build
    if s.get("_rebuild_broken"):                                  # after an OS upgrade
        damage = broken(packages, c)
        for name, lost in damage.items():
            say(f"{name}: needs {', '.join(lost)}")
        if not damage:
            say("nothing is broken: every program and library of the stack resolves")
        s["_rebuild"] = [*s.get("_rebuild", []), *damage]
        if not s["_rebuild"]:
            return
    c["rebuild"] = rebuild_set(s.get("_rebuild", []), packages, c) if s.get("_rebuild") else []
    order, added = plan(s, packages, c)
    if mode == "list":
        show(order, packages, c)
        return
    if mode == "urls":
        check_urls(order, packages, c)
        return
    if mode == "verify":                                           # in the environment the user works in
        if not os.environ.get("HEP_ENV_LOADED"):
            say("Heimdall's environment is not loaded here: the checks see only what this shell has")
        rows = doctor_rows(packages, c, dict(os.environ), quick=bool(s.get("_quick")))
        for row in rows:
            print("\t".join(row))
        if any(row[2] == "FAIL" for row in rows):
            sys.exit(1)
        return
    if mode == "sha256":                                           # for the recipes: what this machine downloaded
        for name in order:
            file = tarball(name, packages[name], c)[0] if packages[name]["kind"] not in ("none", "external") else None
            if file and file.is_file() and not archive_problem(file, full=False):
                print(f'[{name}]   # {file.name}\nsha256 = "{sha256_of(file)}"\n')
        return
    c["cmake_prefix"] = ";".join(dict.fromkeys(f"{c['inst']}/{p.get('install', n)}" for n, p in packages.items()
                                               if p["kind"] not in ("none", "external")))
    if not script:
        preflight(s, c, order)
    paths, fixed = environment(s, c, packages)
    env, dropped = clean_environment(c)
    if dropped and not script:
        say("the build leaves out of your environment: " + ", ".join(dropped))
    for key, items in paths.items():
        env[key] = ":".join([*items, *([env[key]] if env.get(key) else [])])
    shell = Shell(script, {**env, **fixed})
    prefix = Path(c["prefix"])
    folders = [prefix / "stash", Path(c["forge"], "logs"), Path(c["inst"], ".stamps"), Path(c["venv"]).parent]
    if script:
        print("#!/usr/bin/env bash\n# The HEP stack's build, as `build_stack.py --dry-run` printed it"
              + (" (--resume: what this prefix still lacks)." if not c["fresh"] else ": the whole build, for a fresh\n"
                 "# prefix (it reads no stamps, and writes only the C++ standard's).") + "\nset -euo pipefail")
        print("# the build's own environment: another stack's variables never reach a configure script")
        print("unset ROOTSYS LD_LIBRARY_PATH DYLD_LIBRARY_PATH PYTHONPATH CMAKE_PREFIX_PATH PKG_CONFIG_PATH CPATH "
              "LIBRARY_PATH VIRTUAL_ENV CONDA_PREFIX LHAPDF_DATA_PATH")
        print("mkdir -p " + " ".join(shlex.quote(str(f)) for f in folders))
        for key, items in paths.items():
            print(f'export {key}={shlex.quote(":".join(items))}"${{{key}:+:${key}}}"')
        for key, value in fixed.items():
            print(f"export {key}={shlex.quote(value)}")
    else:
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
    std = Path(c["inst"], ".stamps", "cxx_std")                     # the stack's C++ standard: framework/rules.mk reads it
    if script:
        print(f"echo {c['cxx_std']} > {shlex.quote(str(std))}")
    elif std.is_file() and std.read_text(encoding="utf-8").strip() != str(c["cxx_std"]):
        die(f"the stack in {c['inst']} is C++{std.read_text(encoding='utf-8').strip()}; a C++{c['cxx_std']} build "
            "would mix ABIs in one install: use an isolated toolkit (stacks/<name>/), or another prefix")
    else:
        std.write_text(f"{c['cxx_std']}\n", encoding="utf-8")
    say(f"HEP stack → {prefix}: {' '.join(order)}" + (f"  (added, as needed: {' '.join(added)})" if added else ""))
    say(f"C++{c['cxx_std']} {c['opt_flags']}, {c['cores']} cores (ROOT {c['root_cores']})"
        + (", dry run: nothing is run" if script else ""))
    if s["system"]:
        system(s, c, shell, [a for n in order for a in packages[n].get("apt", [])])
    todo = [n for n in order if c["fresh"] or n in c["rebuild"] or state(n, packages[n], c) in ("", "failed")]
    for n in order:
        if not c["fresh"] and n not in todo and state(n, packages[n], c) == "changed":
            say(f"{n}: its recipe changed since it was built: --rebuild {n} applies it")
    fetch([(tarball(n, packages[n], c)[0], urls_of(n, packages[n], c), packages[n].get("sha256", ""))
           for n in todo if packages[n]["kind"] not in ("none", "external")], shell)
    have = {n for n, p in packages.items() if present(n, p, c)} | set(order)
    for name in order:
        p = packages[name]
        label = name + (f" {p['release']}" if p.get("release") else "")
        if p["kind"] == "external":                                 # never built here: where it comes from
            say(f"{label}: external ({'there' if present(name, p, c) else 'not there'}): {expand(p['how'], c)}")
            continue
        if name not in todo:
            say(f"{label}: done already" + (" (installed, not by this script)" if state(name, p, c) == "installed" else ""))
            continue
        position = f"{todo.index(name) + 1}/{len(todo)}"
        say(f"[{position}] {label}" + ("  (a recipe not yet proven by a build)" if p.get("status") == "new" else ""))
        shell.name, shell.log = name, Path(c["forge"], "logs", f"{name}.log")
        shell.position, shell.started = position, time.monotonic()
        if script:
            print(f"\n# == {label}")
        else:
            for older, newer in ((2, 1), (1, 0)):                      # keep the last two attempts' logs
                src = shell.log.with_name(f"{name}.log" + (f".{newer}" if newer else ""))
                if src.exists() and src.stat().st_size:
                    src.replace(shell.log.with_name(f"{name}.log.{older}"))
            shell.log.write_text("", encoding="utf-8")
            stamp(name, p, c).unlink(missing_ok=True)
            building(name, p, c).touch()
        build(name, p, c, shell, have)
        if not script and s["verify"] and p.get("verify"):
            rows = checks(name, p, c, {**shell.env}, slow_ok=False)
            for _, check, result, note in rows:
                say(f"{label}: check {check}: {result}" + (f" ({note})" if note and result != "ok" else ""))
            if bad := [row for row in rows if row[2] in ("FAIL", "MISSING")]:
                die(f"{label} is built but cannot do what its recipe checks ({', '.join(r[1] for r in bad)}): "
                    f"see the lines above; the log is {shell.log} (verify=false skips the checks)")
        if not script:
            stamp(name, p, c).write_text(digest(name, p, c) + "\n", encoding="utf-8")
            building(name, p, c).unlink(missing_ok=True)
            if p["kind"] not in ("none", "external"):
                record_links(name, p, c)
            say(f"{label}: done in {minutes(time.monotonic() - shell.started)}")
    machine = prefix / "env" / "machine.sh"                        # setup.sh itself is tracked
    if c["setup_extra"]:
        if script:
            print(f"\ncat > {shlex.quote(str(machine))} <<'EOF'\n{machine_text(c)}EOF")
        else:
            machine.write_text(machine_text(c), encoding="utf-8")
    load = prefix / "setup.sh"
    if c["stack"]:                                                 # an isolated stack: its own loader
        load = prefix / "stacks" / c["stack"] / "setup.sh"
        text = STACK_SETUP.format(stack=c["stack"], cxx_std=c["cxx_std"], prefix=prefix)
        if script:
            print(f"\ncat > {shlex.quote(str(load))} <<'EOF'\n{text}EOF")
        else:
            load.write_text(text, encoding="utf-8")
    say(f"done: source {load}")


if __name__ == "__main__":
    main(sys.argv[1:])
