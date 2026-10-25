"""A run TOML's [heimdall] (V188): the flags it gives the commands that read it, the command line over them."""

from __future__ import annotations

import pytest

from runner import cli
from runner.errors import HepError

FILE = """[file]
schema = 3
{extra}
[run]
name    = "f"
project = "Demo"

[heimdall]
journal = true
keep    = ["work"]

[heimdall.run]
points = "1"
rerun  = true

[heimdall.plot]
sets = "totality"
"""


def written(tmp_path, text: str, name: str = "f.toml") -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def flagged(argv: list[str]):
    args = cli.parse(argv)
    return args, cli.config_flags(args)


def test_a_file_gives_the_command_its_flags_and_the_command_line_wins(tmp_path):
    path = written(tmp_path, FILE.format(extra=""))
    args, given = flagged(["run", path])
    assert (args.journal, args.keep, args.points, args.rerun) == (True, ["work"], "1", True)
    assert given == ["--journal", "--keep work", "--points 1", "--rerun"]
    args, given = flagged(["run", path, "--points", "2", "--keep", "logs"])
    assert (args.points, args.keep) == ("2", ["logs"]) and "--points 1" not in given
    args, _ = flagged(["plot", path])
    assert args.draw_sets == "totality" and not hasattr(args, "rerun")     # plot's own --sets; run's left to run


def test_an_import_gives_its_flags_the_file_its_own_over_them(tmp_path):
    common = written(tmp_path, '[file]\nschema = 3\n\n[heimdall]\nplain = true\njournal = false\n', "common.toml")
    path = written(tmp_path, FILE.format(extra=f'import = ["{common}"]'))
    args, _ = flagged(["run", path])
    assert args.plain and args.journal                                       # the file's journal over the import's


@pytest.mark.parametrize("table, message", [
    ('[heimdall]\njournl = true\n', "no command that reads a config has that option"),
    ('[heimdall.run]\nsets = "x"\n', "heimdall run has no such option"),
    ('[heimdall.runs]\nplain = true\n', "no such command reads a config"),
    ('[heimdall]\njournal = "yes"\n', "is a switch: true or false"),
    ('[heimdall.run]\nset = ["run.events=1"]\n', "heimdall run has no such option"),
])
def test_what_heimdall_refuses(tmp_path, table, message):
    path = written(tmp_path, f'[file]\nschema = 3\n\n[run]\nname = "f"\nproject = "Demo"\n\n{table}')
    with pytest.raises(HepError, match=message):
        flagged(["run", path])
