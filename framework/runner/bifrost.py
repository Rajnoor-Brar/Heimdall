"""`bifrost`: the environment's packages, and the shell's way in (rank 5; doc:environment, V144).

    bifrost                         the state: the base, the packages you added, the shell's block
    bifrost <pkg>…                  conda-forge packages into the base ("gsl=2.8", "gsl 2.8.*")
    bifrost -python <pkg>…          PyPI packages, by their pip names
    bifrost --drop [-python] <pkg>… take them out
    bifrost -c|-conda <tool>…       a recipe ready-made from conda-forge (what it needs too)
    bifrost -b|-build <tool>…       a recipe built here; -b@<toolkit>: with that toolkit's changes
    bifrost --shell install|remove  gjallarhorn and bifrost in ~/.bashrc and ~/.zshrc (runner/shellrc.py)

What is added is recorded in Himinbjorg's machine.toml ([settings] base_packages, base_pypi; its
comments kept), so a later build keeps it and another machine can be given the same; then the base is made
again (recipes/build_stack.py --base: pixi). On a Himinbjorg made before the base (base = "system"),
-python packages go into the venv with pip, recorded in python_packages.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import datetime
import shutil

from . import paths, plugins, shellrc, workdirs
from .errors import HeimdallError, did_you_mean

KEYS = {False: "base_packages", True: "base_pypi"}


def builder():
    return plugins.load(paths.heimdall_root() / "recipes" / "build_stack.py", "build_stack")


def loaded():
    """build_stack.py, this machine's settings and recipes (what the base holds read as ready-made), its context."""
    bs = builder()
    _, settings, packages = bs.options([f"machine={paths.himinbjorg()}"])
    return bs, settings, packages, bs.context(settings)


# ── machine.toml, edited in place ─────────────────────────────────────────────────────────────────

def spec_of(word: str) -> str:
    """A package as the command line gives it, as base.toml writes one: "gsl=2.8" → "gsl 2.8.*"; "gsl>=2.8",
    "gsl 2.8.*" and "gsl" as they are. A PyPI spec keeps its operator: "iminuit>=2.30" → "iminuit >=2.30"."""
    word = word.strip()
    if " " in word:
        return re.sub(r"\s+", " ", word)
    name, op, version = re.match(r"([A-Za-z0-9_.\-]+)\s*(==|=|>=|<=|!=|~=|>|<)?\s*(.*)", word).groups()
    if not op:
        return name
    if op == "=":                                          # conda's own: 2.8 means 2.8.*
        return f"{name} {version}" + ("" if "*" in version or version.count(".") >= 2 else ".*")
    return f"{name} {op}{version}"


def name_of(spec: str) -> str:
    return re.split(r"[\s=<>!~]", spec.strip(), maxsplit=1)[0]


def set_list(text: str, key: str, values: list[str]) -> str:
    """machine.toml's text with [settings] `key` set to `values`, everything else as it was: the key's lines
    replaced where they are, else one line put under [settings], else a [settings] table at the end (the
    template's is a comment)."""
    line = f"{key} = [{', '.join(json.dumps(v) for v in values)}]"
    lines = text.splitlines()
    header = next((i for i, l in enumerate(lines) if re.match(r"\s*\[settings\]\s*(#.*)?$", l)), None)
    if header is None:
        return text.rstrip("\n") + ("\n\n" if text.strip() else "") + f"[settings]\n{line}\n"
    end = next((i for i in range(header + 1, len(lines)) if re.match(r"\s*\[", lines[i])), len(lines))
    at = next((i for i in range(header + 1, end) if re.match(rf"\s*{re.escape(key)}\s*=", lines[i])), None)
    if at is None:
        lines.insert(header + 1, line)
    else:
        stop, depth = at, 0
        for stop in range(at, end):                          # a list may span lines: to its closing bracket
            depth += lines[stop].split("#")[0].count("[") - lines[stop].split("#")[0].count("]")
            if depth <= 0:
                break
        comment = re.search(r"\]\s*(#.*)$", lines[stop])
        lines[at:stop + 1] = [line + (f"   {comment.group(1)}" if comment else "")]
    return "\n".join(lines) + "\n"


def set_key(text: str, table: str, key: str, value: str) -> str:
    """machine.toml's text with `[<table>] key = "value"`, everything else as it was: the key's line replaced
    where it is, else put under the table's header, else the table added at the end."""
    line = f"{key} = {json.dumps(value)}"
    lines = text.splitlines()
    header = next((i for i, l in enumerate(lines) if re.match(rf"\s*\[{re.escape(table)}\]\s*(#.*)?$", l)), None)
    if header is None:
        return text.rstrip("\n") + ("\n\n" if text.strip() else "") + f"[{table}]\n{line}\n"
    end = next((i for i in range(header + 1, len(lines)) if re.match(r"\s*\[", lines[i])), len(lines))
    at = next((i for i in range(header + 1, end) if re.match(rf"\s*{re.escape(key)}\s*=", lines[i])), None)
    if at is None:
        lines.insert(header + 1, line)
    else:
        comment = re.search(r"\"\s*(#.*)$", lines[at])
        lines[at] = line + (f"   {comment.group(1)}" if comment else "")
    return "\n".join(lines) + "\n"


def recorded(key: str, root: Path | None = None) -> list[str]:
    file = (root or paths.himinbjorg()) / "machine.toml"
    if not file.is_file():
        return []
    try:
        return list(tomllib.loads(file.read_text(encoding="utf-8")).get("settings", {}).get(key, []))
    except tomllib.TOMLDecodeError as error:
        raise HeimdallError(f"cannot read {file}: {error}", hint="fix it by hand first") from None


def record(key: str, values: list[str], root: Path | None = None) -> Path:
    """[settings] `key` = values in Himinbjorg's machine.toml (made from the template when missing)."""
    file = (root or paths.himinbjorg()) / "machine.toml"
    text = file.read_text(encoding="utf-8") if file.is_file() else \
        (paths.heimdall_root() / "recipes" / "machine.template.toml").read_text(encoding="utf-8")
    new = set_list(text, key, values)
    if tomllib.loads(new).get("settings", {}).get(key) != values:      # never write what does not read back
        raise HeimdallError(f"could not set {key} in {file}", hint=f"set [settings] {key} by hand")
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(new, encoding="utf-8")
    return file


# ── adding and dropping ───────────────────────────────────────────────────────────────────────────

def refusals(specs: list[str], packages: dict, bs, c: dict) -> None:
    """A conda-forge package whose recipe the stack has built would be a second copy of it (conda-forge's
    beside the stack's): refused, naming the recipe's way to take it ready-made. One the stack has not built
    is welcome: the base holding it, a later build takes the recipe as ready-made."""
    built = {bs.conda_name(p): name for name, p in packages.items()
             if p.get("conda") and not bs.ready_made(p)
             and (bs.stamp(name, p, c).exists() or Path(c["inst"], p.get("install", name)).exists())}
    for spec in specs:
        if name_of(spec) in built:
            recipe = built[name_of(spec)]
            raise HeimdallError(f"{name_of(spec)} is {recipe}'s, which the stack builds from source: two of it would clash",
                           hint=f"take {recipe} ready-made instead: python3 recipes/build_stack.py {recipe}.from=conda-forge "
                                f"(or an @…-conda toolkit)")


def update_base() -> int:
    """The base made again from the settings (build_stack.py --base: pixi solves and installs); its say lines
    go to stderr. Tests replace this."""
    builder().main(["--base"])
    return 0


def build(argv: list[str]) -> None:
    """build_stack.py with these arguments (its say lines on stderr; it dies with SystemExit). Tests replace this."""
    builder().main(argv)


def pip(venv: Path, specs: list[str], drop: bool) -> None:
    """base = "system": pip in the venv. Tests replace this."""
    argv = [str(venv / "bin" / "python"), "-m", "pip", "uninstall" if drop else "install", *(["-y"] if drop else []),
            *(s.replace(" ", "") for s in specs)]
    if subprocess.run(argv).returncode:
        raise HeimdallError(f"pip {'uninstall' if drop else 'install'} failed", hint=" ".join(argv))


def change(words: list[str], python: bool, drop: bool, out=print) -> int:
    """bifrost [--drop] [-python] <pkg>…: machine.toml, then the base (or the venv)."""
    if not words:
        raise HeimdallError("which packages?", hint="bifrost <conda-forge package>…, or bifrost -python <PyPI package>…")
    bs, settings, packages, c = loaded()
    specs = [spec_of(w) for w in words]
    system = settings["base"] != "conda"
    if system and not python:
        raise HeimdallError("this Himinbjorg has no conda base (base = \"system\": apt or Homebrew, and a venv)",
                       hint="a system package with apt (or brew); a Python one: bifrost -python <pkg>")
    key = "python_packages" if system else KEYS[python]
    have = recorded(key)                     # machine.toml's own: its lists append to settings.toml's
    if drop:
        gone = {name_of(s) for s in specs}
        missing = sorted(gone - {name_of(h) for h in have})
        if missing:
            raise HeimdallError(f"not among {key}: {', '.join(missing)}", hint="bifrost lists what you added")
        now = [h for h in have if name_of(h) not in gone]
    else:
        if not python:
            recipe = next((name_of(s) for s in specs if name_of(s) in packages), None)
            if recipe and not held(bs, recipe, packages[recipe], c):
                raise HeimdallError(f"{recipe} is a tool's recipe: say how it comes",
                               hint=f"bifrost -c {recipe} (ready-made from conda-forge) or bifrost -b {recipe} (built here)")
            refusals(specs, packages, bs, c)
            ready = {bs.conda_name(p): name for name, p in packages.items() if p.get("conda") and bs.ready_made(p)
                     and bs.conda_name(p) in c["conda_meta"]}
            for spec in [s for s in specs if name_of(s) in ready]:
                out(f"{name_of(spec)}: in the base already, as the recipe {ready[name_of(spec)]} (ready-made)")
                specs.remove(spec)
            if not specs:
                return 0
        names = {name_of(s): s for s in specs}
        now = [h for h in have if name_of(h) not in names] + list(names.values())
    file = record(key, now)
    out(f"{file}: {key} = {now}")
    if system:
        pip(Path(c["venv"]), specs, drop)
        return 0
    try:
        update_base()
    except (SystemExit, Exception) as failure:              # build_stack.py dies with SystemExit
        record(key, have)                                    # never leave a list the base cannot take
        raise HeimdallError(f"the base could not be made with {', '.join(specs)}: machine.toml's {key} is as it was",
                       hint=("pixi's reason is above (forge/logs/base.log); a PyPI package? bifrost -python <pkg>"
                             if not python else "pixi's reason is above (forge/logs/base.log)")) from failure
    if not drop:
        env = Path(c["base"])
        meta = bs.conda_meta(env)
        for spec in specs:
            name = name_of(spec)
            version = pypi_version(env, name) if python else meta.get(name, "").split("-")[0]
            out(f"{name} {version or '?'}: in the base")
    return 0


# ── tools: a recipe ready-made or built (-c, -b) ──────────────────────────────────────────────────

FLAG = re.compile(r"-{1,2}(c|conda|b|build)(?:@([\w.-]+))?")


def flags(words: list[str]) -> list[str]:
    """bifrost's -c|-conda and -b|-build[@toolkit] as argparse's --conda, --build [--toolkit KIT] (cli.parse)."""
    out = []
    for word in words:
        found = FLAG.fullmatch(word)
        if not found:
            out.append(word)
        elif found[1] in ("c", "conda"):
            if found[2]:
                raise HeimdallError(f"{word}: a toolkit goes with -b", hint="bifrost -b@<toolkit> <tool>")
            out.append("--conda")
        else:
            out += ["--build", *(["--toolkit", found[2]] if found[2] else [])]
    return out


def built_here(bs, name: str, p: dict, c: dict) -> bool:
    return bs.stamp(name, p, c).exists() or Path(c["inst"], p.get("install", name)).exists()


def held(bs, name: str, p: dict, c: dict) -> bool:
    return bs.ready_made(p) and bool(p.get("conda")) and bs.conda_name(p) in c["conda_meta"]


def cost(switching: list[str], packages: dict, bs, c: dict) -> list[str]:
    """What switching packages between built and ready-made costs: the recorded points of the recognised work
    dirs that ran their tools (new binaries: new identities and seeds), and what is built on them."""
    from . import tools as toolsmod
    names = set(switching)
    runs = {n for n, f in toolsmod.folders().items() if names & set(f.get("tool", "packages", []))}
    points = {}
    for title, entry in workdirs.load().items():
        root = Path(entry["path"])
        if not paths.is_work(root):
            continue
        count = 0
        for record in (root / "records").rglob("provenance.json"):
            try:
                steps = json.loads(record.read_text(encoding="utf-8")).get("tools", [])
            except (OSError, json.JSONDecodeError):
                continue
            count += any(s.get("tool") in runs or names & set(s.get("packages", {})) for s in steps)
        if count:
            points[title] = count
    out = [f"switching {', '.join(sorted(names))} changes the programs of: {', '.join(sorted(runs)) or 'no tool folder'}"]
    out.append(f"{sum(points.values())} recorded point(s) ran them ({', '.join(f'{t}: {n}' for t, n in points.items())}): "
               "they will run again, with new identities and seeds" if points else
               "no recorded point of a recognised work dir ran them (heimdall recognise --list)")
    linked = sorted(n for n in names if n in plugins.load(paths.heimdall_root() / "env" / "stack.py", "stack").entries())
    if linked:
        out.append(f"Heimdall's apps and the module programs that require {', '.join(linked)} rebuild on their next build")
    return out


def tools(names: list[str], conda: bool, toolkit: str = "", yes: bool = False, out=print, ask=None) -> int:
    """bifrost -c|-b[@toolkit] <tool>…: the machine's choice recorded in machine.toml ([packages.<tool>] from),
    then build_stack.py with those tools. A switch of an installed package says what it costs and asks."""
    if not names:
        raise HeimdallError("which tools?", hint="bifrost -c <tool> (from conda-forge) or bifrost -b <tool> (built); "
                                            "heimdall tools lists the tools and their packages")
    bs, settings, packages, c = loaded()
    unknown = [n for n in names if n not in packages]
    if unknown:
        raise HeimdallError(f"no recipe {', '.join(unknown)}", hint=did_you_mean(unknown[0], packages)
                       or "python3 recipes/build_stack.py --list; your own go in Himinbjorg's recipes.toml")
    if conda and settings["base"] != "conda":
        raise HeimdallError("this Himinbjorg has no conda base (base = \"system\"): nothing is taken ready-made",
                       hint=f"bifrost -b {' '.join(names)}")
    choice: dict[str, str] = {}                                    # package → "conda-forge" | "source"
    if conda:
        def take(name: str, asked: bool) -> None:
            p = packages[name]
            if name in choice or held(bs, name, p, c):
                return
            if not p.get("conda"):
                if asked:
                    raise HeimdallError(f"conda-forge carries no {name}", hint=f"bifrost -b {name}")
                return                                             # (python: the base's own)
            choice[name] = "conda-forge"
            for need in p.get("needs", []):
                take(need, False)
        for name in names:
            take(name, True)
        extra = [n for n in choice if n not in names]
        if extra:
            out(f"what {', '.join(names)} need{'s' if len(names) == 1 else ''} from conda-forge too: {', '.join(extra)}")
    else:
        for name in names:
            if bs.ready_made(packages[name]):
                choice[name] = "source"
        needing = {q: [n for n in choice if n in packages[q].get("needs", [])] for q in packages
                   if q not in choice and held(bs, q, packages[q], c)}
        for q, needs in needing.items():
            if needs:
                raise HeimdallError(f"{q}, ready-made, brings conda-forge's {', '.join(needs)}: building it here would make two",
                               hint=f"build {q} too: bifrost -b {' '.join([*names, q])}")
    switching = [n for n, how in choice.items()
                 if (how == "conda-forge" and built_here(bs, n, packages[n], c)) or (how == "source" and held(bs, n, packages[n], c))]
    if switching:
        for line in cost(switching, packages, bs, c):
            out(line)
        if not yes:
            if ask is None:
                raise HeimdallError("a switch between built and ready-made reruns points and rebuilds: it asks first",
                               hint="run it in a terminal, or add --yes")
            if ask("go ahead? [y/N] ").strip().lower() not in ("y", "yes"):
                out("nothing changed")
                return 1
    file = paths.himinbjorg() / "machine.toml"
    before = file.read_text(encoding="utf-8") if file.is_file() else None
    text = before if before is not None else \
        (paths.heimdall_root() / "recipes" / "machine.template.toml").read_text(encoding="utf-8")
    for name, how in choice.items():
        text = set_key(text, f"packages.{name}", "from", how)
        if tomllib.loads(text).get("packages", {}).get(name, {}).get("from") != how:
            raise HeimdallError(f"could not set [packages.{name}] from in {file}", hint=f"set from = \"{how}\" by hand")
    retired: list[tuple[Path, Path]] = []
    rebuild: list[str] = []
    try:
        if choice:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
            out(f"{file}: " + ", ".join(f"[packages.{n}] from = \"{h}\"" for n, h in choice.items()))
        gone = {n for n, h in choice.items() if h == "conda-forge" and built_here(bs, n, packages[n], c)}
        if gone:                                                   # the stack's copy goes aside: one of each
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            aside = Path(c["forge"]) / "retired"
            for name in sorted(gone):
                p = packages[name]
                for src in [Path(c["inst"], p.get("install", name)),
                            *bs.stamp(name, p, c).parent.glob(bs.stamp(name, p, c).name + "*")]:
                    if src.exists():
                        dst = aside / f"{stamp}-{src.name}"
                        aside.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(dst))
                        retired.append((src, dst))
            out(f"set aside in {aside}: " + ", ".join(dst.name for _, dst in retired))
            on = set(gone)                                         # what was built on them is built again
            for name, p in packages.items():
                if name not in on and built_here(bs, name, p, c) and not bs.ready_made(p) and on & set(p.get("needs", [])):
                    on.add(name)
                    rebuild.append(name)
        words = [f"{n}@{toolkit}" if toolkit else n for n in names]
        build([f"packages={' '.join(words + rebuild)}", *(["--rebuild", " ".join(rebuild)] if rebuild else [])])
    except (SystemExit, Exception) as failure:
        if before is None:
            file.unlink(missing_ok=True)
        elif choice:
            file.write_text(before, encoding="utf-8")
        for src, dst in reversed(retired):                         # put back what was set aside
            if dst.exists() and not src.exists():
                shutil.move(str(dst), str(src))
        raise HeimdallError(f"bifrost {'-c' if conda else '-b'} {' '.join(names)} failed: machine.toml and the stack are as "
                       "they were", hint="the build's reason is above (forge/logs/)") from failure
    return 0


# ── what is there ─────────────────────────────────────────────────────────────────────────────────

def pypi_version(env: Path, name: str) -> str:
    """A PyPI package's installed version in the base, from its dist-info folder; "" when absent."""
    wanted = re.sub(r"[-_.]+", "_", name).lower()
    for info in env.glob("lib/python*/site-packages/*.dist-info"):
        stem, _, version = info.name[:-len(".dist-info")].rpartition("-")
        if re.sub(r"[-_.]+", "_", stem).lower() == wanted:
            return version
    return ""


def state() -> list[str]:
    """The base, what you added (with the versions installed), and the shell's block in each rc file."""
    bs, settings, packages, c = loaded()
    out = [bs.base_line(c).replace("base:    ", f"{'the base:':17} ", 1)]
    if settings["base"] == "conda":
        env = Path(c["base"])
        for python, key in KEYS.items():
            specs = recorded(key)
            shown = []
            for spec in specs:
                name = name_of(spec)
                version = (pypi_version(env, name) if python else c["conda_meta"].get(name, "").split("-")[0])
                shown.append(f"{name} {version or '(not installed yet: bifrost makes the base again)'}")
            out.append(f"{key + ':':17} " + (", ".join(shown) if shown else "none (bifrost " + ("-python " if python else "")
                                                                          + "<pkg> adds one)"))
    else:
        mine = recorded("python_packages")
        out.append(f"{'python_packages:':17} " + (", ".join(mine) + " (yours, in the venv by pip)" if mine
                                                  else "none of yours (bifrost -python <pkg> adds one)"))
    from .doctor import stack_rows
    rows = stack_rows()
    out.append(f"{'the tools:':17} " + (", ".join(f"{r['package']} {r['version']} ({r['how']})" for r in rows
                                                     if r["package"] != "python") or "none installed yet"))
    want = {shell: shellrc.block(shell, paths.heimdall_root(), paths.himinbjorg()) for shell in ("bash", "zsh")}
    for shell, file in shellrc.rc_files(Path.home(), os.environ.get("SHELL", "")):
        status = shellrc.status(file, want[shell])
        out.append(f"{'the shell:':17} {file}: " + {"installed": "gjallarhorn and bifrost",
                                                     "another": "another checkout's or Himinbjorg's block "
                                                                "(bifrost --shell install points it here)",
                                                     "absent": "no gjallarhorn (bifrost --shell install)"}[status])
    return out


def shell(action: str, out=print) -> int:
    """bifrost --shell install|remove: the block in ~/.bashrc and ~/.zshrc."""
    home = Path.home()
    for name, file in shellrc.rc_files(home, os.environ.get("SHELL", "")):
        if action == "install":
            happened = shellrc.install(file, shellrc.block(name, paths.heimdall_root(), paths.himinbjorg()))
            out(f"{file}: {happened}" + (" (a new shell has gjallarhorn and bifrost)" if happened != "unchanged" else ""))
        elif shellrc.remove(file):
            out(f"{file}: removed")
    return 0


def main(args) -> int:
    if args.conda or args.build:
        if args.python or args.drop or args.shell or (args.conda and args.build):
            raise HeimdallError("-c and -b take tools alone", hint="bifrost -c <tool>…, or bifrost -b[@toolkit] <tool>…")
        ask = input if sys.stdin.isatty() else None
        return tools(args.packages, conda=args.conda, toolkit=args.toolkit or "", yes=args.yes, ask=ask)
    if args.toolkit:
        raise HeimdallError("--toolkit goes with -b", hint="bifrost -b@<toolkit> <tool>")
    if args.shell:
        if args.packages:
            raise HeimdallError("--shell takes no packages", hint="bifrost --shell install|remove")
        return shell(args.shell)
    if args.packages:
        return change(args.packages, python=args.python, drop=args.drop)
    if args.drop or args.python:
        raise HeimdallError("which packages?", hint="bifrost [--drop] [-python] <pkg>…")
    for line in state():
        print(line)
    return 0


if __name__ == "__main__":                                  # not a module to run; framework/bin/bifrost is
    sys.exit("run bifrost (framework/bin/bifrost) or heimdall bifrost")
