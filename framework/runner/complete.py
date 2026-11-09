"""Tab completion (rank 5, tab-complete): `heimdall __complete CWORD WORD…`, which env/complete.bash asks on every TAB.

The walk reads the argument parser, so a command or an option cannot be missing from it; what an argument takes is its
*kind*, said once in `KINDS`, and an argument that completes nothing (free text) is in `FREE`. A test fails for a positional or
a value-taking option that is in neither. Each kind is a small function over a reader that exists already (`house.config_names`,
`config.load`, a folder of records/ or results/, the run registry, the schema).

It writes nothing and says nothing: the run registry is globbed and not pruned (`runs.entries()` prunes), a `HeimdallError`
or an `OSError` gives no candidates, and what a reader prints goes nowhere. Outside a work dir the path kinds give nothing,
and the commands and options still complete.

The answer is the candidates one a line, then a last line that starts with a colon, the directive: `:plain`, `:nospace` (the
candidates end in `/` and the word goes on), `:files:<pattern>` (bash completes files and folders, those that match
`<pattern>`; empty: all) or `:dirs`. It takes the parser as an argument and never imports `cli`.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import tomllib
from pathlib import Path

from .errors import HeimdallError

#: Commands that are retired stubs: they complete nothing, and are not offered.
RETIRED = ("stats", "deck")

#: What a command's own argv is, where its parser says only "the rest" (`heimdall stack …`).
REST = {"stack": ("build", "list", "status", "doctor")}

#: (command, dest) → the kind of what that positional or option takes.
KINDS = {
    **{(c, "config"): "errand" for c in ("run", "status", "watch", "stop", "cluster")},
    ("plot", "config"): "drawing", ("clean", "config"): "errand_file",
    **{(c, "configuration"): "configuration" for c in ("run", "plot", "status", "watch", "stop", "cluster")},
    ("check", "configs"): "errand_file", ("migrate", "configs"): "errand_file",
    ("ls", "assignment"): "assignment", ("setup", "assignment"): "assignment",
    ("show", "target"): "deep", ("log", "target"): "deep",
    ("tag", "target"): "record", ("diff", "first"): "record", ("diff", "second"): "record_or_run",
    ("migrate", "snapshot"): "record", ("migrate", "plot_docs"): "record", ("migrate", "source"): "errand_file",
    ("plot", "style_sync"): "errand_file",
    ("score", "target"): "result", ("report", "names"): "recipe", ("report", "init"): "result",
    ("report", "output"): "dir",
    ("records", "scope"): "scope", ("library", "scope"): "scope",
    ("reproduce", "provenance"): "provenance", ("overlay", "files"): "data_file", ("overlay", "style"): "file",
    ("explain", "key"): "schema_key", ("tools", "what"): "tool", ("help", "topic"): "command",
    ("setup", "dir"): "dir", ("recognise", "path"): "dir",
    ("plot", "plot_file"): "file", ("watch", "file"): "file",
    **{("runs", d): "run" for d in ("dispatch", "forget", "again", "resume_queue", "index")},
    ("run", "queued_to"): "run_going", ("watch", "pid"): "pid", ("stop", "pid"): "pid",
    ("runs", "state"): "states",
}

#: Arguments of free text or of a number: nothing completes them.
FREE = {
    ("run", "card"), ("run", "points"), ("run", "worker"), ("run", "sweep_member"), ("run", "set"), ("run", "tag"),
    ("run", "rerun_since"), ("run", "stages"), ("run", "keep"),
    ("plot", "draw_sets"), ("plot", "page_points"), ("plot", "keep"), ("plot", "set"),
    ("score", "set_name"), ("score", "by"), ("score", "baseline"),
    ("overlay", "output"), ("overlay", "labels"), ("overlay", "objects"), ("overlay", "formats"),
    ("status", "set"), ("clean", "set"), ("check", "set"), ("migrate", "set"), ("cluster", "points"), ("cluster", "set"),
    ("cluster", "keep"), ("diff", "points"), ("watch", "index"), ("stop", "index"),
    ("runs", "resume"), ("runs", "jobs"), ("log", "attempt"), ("show", "attempt"),
    ("setup", "old_project"), ("setup", "name"), ("setup", "example"),
    ("tag", "words"), ("tools", "package"), ("tools", "runs"), ("tools", "source"),
    ("build", "targets"), ("build", "jobs"), ("bifrost", "packages"), ("bifrost", "toolkit"),
    ("image", "settings"), ("image", "name"),
    ("recognise", "title"), ("recognise", "forget"), ("recognise", "path_of"),
}

#: The command names, set by `complete` for the kind that offers them.
NAMES: list[str] = []

#: The folders of a work dir `heimdall cd` knows; env/complete.bash answers `cd` itself.
CD_DIRS = ("configs", "modules", "results", "records", "logs")

#: The files a path kind completes by their name.
PATTERNS = {"errand": "*.toml", "provenance": "provenance.json", "data": "@(*.yoda|*.yoda.gz|*.root)"}


def answer(parser: argparse.ArgumentParser, argv: list[str]) -> int:
    """`heimdall __complete CWORD WORD…`: print the candidates and the directive; always 0, whatever goes wrong."""
    try:
        cword = int(argv[0])
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            found, directive = complete(parser, cword, argv[1:])
    except Exception:                                                 # a completer never shows a traceback
        found, directive = [], "plain"
    for line in found:
        print(line)
    print(":" + directive)
    return 0


def complete(parser: argparse.ArgumentParser, cword: int, words: list[str]) -> tuple[list[str], str]:
    """The candidates for word number `cword` of the command line (0 is `heimdall`), `words` being what follows `heimdall`,
    and the directive (`plain`, `nospace`, `files:<pattern>`, `dirs`)."""
    current = words[cword - 1] if 0 < cword <= len(words) else ""
    before = words[:max(cword - 1, 0)]
    commands = _commands(parser)
    NAMES[:] = [c for c in commands if c not in RETIRED]
    position = next((i for i, w in enumerate(before) if not w.startswith("-")), None)
    if position is None:
        if current.startswith("-"):
            return _with(_options(parser), current), "plain"
        return _with(NAMES, current), "plain"
    command = before[position]
    if command in RETIRED or command not in commands:
        return [], "plain"
    try:
        return _argument(command, commands[command], before[position + 1:], current)
    except (HeimdallError, OSError, ValueError, KeyError, tomllib.TOMLDecodeError):   # a reader that cannot: nothing to offer
        return [], "plain"


def _commands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _options(parser: argparse.ArgumentParser) -> list[str]:
    return [o for a in parser._actions if a.help != argparse.SUPPRESS for o in a.option_strings if o.startswith("--")]


def _takes_value(action: argparse.Action) -> bool:
    return action.option_strings != [] and action.nargs != 0


def _with(words, current: str) -> list[str]:
    return sorted(w for w in words if w.startswith(current))


def parts_of(command_parser: argparse.ArgumentParser) -> tuple[dict, list]:
    """(option string → action, the positionals in order) of a command's parser."""
    options = {o: a for a in command_parser._actions for o in a.option_strings}
    positionals = [a for a in command_parser._actions if not a.option_strings and not isinstance(a, argparse._SubParsersAction)]
    return options, positionals


def _argument(command: str, command_parser: argparse.ArgumentParser, before: list[str], current: str) -> tuple[list[str], str]:
    """The word being typed, after the command and the `before` words that follow it."""
    if command in REST:
        return (_with(REST[command], current), "plain") if not before else ([], "plain")
    options, positionals = parts_of(command_parser)
    given: set[str] = set()
    typed: list[str] = []                                    # the positional words so far
    open_option = None                                       # the option whose values the word being typed may be
    for word in before:
        if word.startswith("-") and word != "-":
            name, equals, _ = word.partition("=")
            action = options.get(name)
            open_option = action if action is not None and _takes_value(action) and not equals else None
            if action is not None:
                given.add(action.dest)
        elif open_option is None:
            typed.append(word)
        elif open_option.nargs not in ("*", "+"):
            open_option = None                               # the option's one value
    if open_option is not None and not current.startswith("-"):
        return _value(command, open_option, typed, current)
    if current.startswith("-"):
        shown = [o for a in command_parser._actions if a.help != argparse.SUPPRESS
                 and (a.dest not in given or isinstance(a, argparse._AppendAction)) for o in a.option_strings if o.startswith("--")]
        return _with(shown, current), "plain"
    if not positionals:
        return [], "plain"
    action = positionals[min(len(typed), len(positionals) - 1)]
    if len(typed) >= len(positionals) and action.nargs not in ("*", "+"):
        return [], "plain"
    return _value(command, action, typed, current)


def _value(command: str, action: argparse.Action, typed: list[str], current: str) -> tuple[list[str], str]:
    """What an argument or an option's value takes: its choices, or its kind."""
    if action.choices:
        return _with([str(c) for c in action.choices], current), "plain"
    kind = KINDS.get((command, action.dest))
    if kind is None:
        return [], "plain"
    return KIND[kind](current, typed, command)


# ── the readers ─────────────────────────────────────────────────────────────────────────────────

def _dirs(path: Path) -> list[str]:
    """The names of the folders (and links to them) in `path`, hidden ones and the points library left out."""
    try:
        with os.scandir(path) as found:
            return sorted(e.name for e in found if not e.name.startswith(".") and e.name != "library" and e.is_dir())
    except OSError:
        return []


def _configs() -> list[str]:
    from .house import config_names
    return config_names()


def _tree(root: Path, depth: int) -> list[str]:
    """Every folder `depth` levels below `root`, as `a/b/c`."""
    found = [""]
    for _ in range(depth):
        found = [f"{base}/{name}" if base else name for base in found for name in _dirs(root / base)]
    return found


def _records() -> Path:
    from .paths import records_root
    return records_root()


def _results() -> Path:
    from .paths import results_root
    return results_root()


def _levels(names: list[str], current: str) -> tuple[list[str], str]:
    """`names` (paths with `/`) one level at a time: the names below what is typed up to its last `/`, a name that goes on
    ending in `/`; a name that is both a place and has more below is offered both ways."""
    head = current[:current.rfind("/") + 1]
    found: set[str] = set()
    for name in names:
        if not name.startswith(current):
            continue
        segment, slash, _ = name[len(head):].partition("/")
        found.add(head + segment + slash)
        if slash and name == head + segment:
            found.add(head + segment)
    return sorted(found), "nospace" if any(f.endswith("/") for f in found) else "plain"


def _is_path(current: str) -> bool:
    return current.startswith(("./", "../", "/", "~"))


# ── the kinds ───────────────────────────────────────────────────────────────────────────────────

def errand(current: str, typed: list[str], command: str, drawing: bool = False, with_runs: bool = True) -> tuple[list[str], str]:
    """An errand file, `<A>/<E>`; after `<A>/<E>/` that Errand's Runs from records/ (and, for a drawing, results/ too)."""
    if _is_path(current):
        return [], "files:" + PATTERNS["errand"]
    if with_runs and current.count("/") >= 2:
        assignment, errand_, _ = current.split("/", 2)
        runs: set[str] = set()
        for root in (_records(),) + ((_results(),) if drawing else ()):
            runs.update(f"{assignment}/{errand_}/{r}" for r in _dirs(root / assignment / errand_))
        return _with(runs, current), "plain"
    return _levels(_configs(), current)


def errand_file(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return errand(current, typed, command, with_runs=False)


def drawing(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return errand(current, typed, command, drawing=True)


def assignment(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    from .paths import configs_root
    return _with(_dirs(configs_root()), current), "plain"


def record(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """A Run, `<A>/<E>/<R>`, from records/."""
    if _is_path(current):
        return [], "dirs"
    return _levels(_tree(_records(), 3), current)


def record_or_run(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """A Run, or the bare `<R>` of the first Run's Errand."""
    found, directive = record(current, typed, command)
    if typed and "/" not in current and typed[0].count("/") >= 2:
        assignment_, errand_ = typed[0].split("/")[:2]
        found = sorted(set(found) | set(_with(_dirs(_records() / assignment_ / errand_), current)))
    return found, directive


def deep(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """A Run, then `/<point>` from its points/, then `/<tag>` from the tool logs of that point."""
    if _is_path(current):
        return [], "dirs"
    segments = current.split("/")
    if len(segments) < 4:
        return _levels(_tree(_records(), 3) + [r + "/" for r in _tree(_records(), 3)], current)
    base = _records().joinpath(*segments[:3])
    if len(segments) == 4:
        found = {f"{'/'.join(segments[:3])}/{p}{s}" for p in _dirs_or_links(base / "points") for s in ("", "/")}
        return _with(found, current), "nospace"
    found = {f"{'/'.join(segments[:4])}/{n[:-4]}" for n in _files(base / "logs" / segments[3], ".log")}
    return _with(found, current), "plain"


def _dirs_or_links(path: Path) -> list[str]:
    try:
        return sorted(e for e in os.listdir(path) if not e.startswith("."))
    except OSError:
        return []


def _files(path: Path, suffix: str) -> list[str]:
    return [n for n in _dirs_or_links(path) if n.endswith(suffix) and not n.endswith(".full" + suffix)]


def result(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """An Errand's results, `<A>/<E>`, or a Run's, `<A>/<E>/<R>`."""
    if _is_path(current):
        return [], "dirs"
    return _levels(_tree(_results(), 2) + _tree(_results(), 3), current)


def scope(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """`<A>`, `<A>/<E>` or `<A>/<E>/<R>` of records/."""
    return _levels(_tree(_records(), 1) + _tree(_records(), 2) + _tree(_records(), 3), current)


def recipe(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """A report recipe (`<A>/<E>.toml`) or a source under results/."""
    if _is_path(current):
        return [], "files:" + PATTERNS["errand"]
    from .report import recipes
    return _levels(recipes() + _tree(_results(), 2) + _tree(_results(), 3), current)


def configuration(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """The configurations of the errand already typed: a config name, or a Run of it, or a file."""
    if not typed or not typed[0]:
        return [], "plain"
    from . import config
    name = typed[0]
    if not _is_path(name):
        name = "/".join(name.split("/")[:2])
    names = config.load(name, strict=False).configurations
    return _with([str(n) for n in names], current), "plain"


def provenance(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return [], "files:" + PATTERNS["provenance"]


def data_file(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return [], "files:" + PATTERNS["data"]


def file(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return [], "files:"


def directory(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return [], "dirs"


def schema_key(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """A schema table, then `<table>.<key>`."""
    from . import schema
    from .house import TABLES
    if "." not in current:
        return _with([t + "." for t in TABLES], current), "nospace"
    table, _, _ = current.partition(".")
    if table not in TABLES:
        return [], "plain"
    return _with([f"{table}.{key}" for key in schema.keys(TABLES[table])], current), "plain"


def tool(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    from .paths import tool_chains
    return _with([*tool_chains(), "new"], current), "plain"


def command_name(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return _with(NAMES, current), "plain"


def states(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """The run states, after the last comma too."""
    from . import runs
    head, comma, last = current.rpartition(",")
    return sorted(head + comma + s for s in runs.STATES if s.startswith(last)), "plain"


def _registry():
    """The entries as the registry holds them, newest first, read and never pruned (`runs.entries()` writes)."""
    from . import runs
    found = [entry for _, entry in runs._own(sorted(runs.folder().glob("*.json")), True)]
    return sorted(found, key=lambda e: e.started or 0, reverse=True)


def run(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    """A run's id. A live `[N]` is not offered: the numbering takes the sockets and Slurm's queue."""
    return _with([e.id for e in _registry()], current), "plain"


def run_going(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return _with([e.id for e in _registry() if e.finished is None], current), "plain"


def pid(current: str, typed: list[str], command: str) -> tuple[list[str], str]:
    return _with([str(e.pid) for e in _registry() if e.finished is None and e.pid], current), "plain"


#: kind → what answers it.
KIND = {"errand": errand, "errand_file": errand_file, "drawing": drawing, "assignment": assignment, "record": record,
        "record_or_run": record_or_run, "deep": deep, "result": result, "scope": scope, "recipe": recipe,
        "configuration": configuration, "provenance": provenance, "data_file": data_file, "file": file, "dir": directory,
        "schema_key": schema_key, "tool": tool, "command": command_name, "states": states, "run": run,
        "run_going": run_going, "pid": pid}
