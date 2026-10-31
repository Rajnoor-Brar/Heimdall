"""A run TOML's [heimdall] (V188, V190): the preference switches it gives the commands that read it, the command
line over them; modes, targets, selections and the study's own settings refused, with why."""

from __future__ import annotations

import pytest

from runner import cli
from runner.errors import HeimdallError

FILE = """[file]
schema = 3
{extra}
[errand]
name    = "f"
assignment = "Demo"

[heimdall]
journal = true
keep    = ["work"]

[heimdall.run]
rerun = true
wait  = true

[heimdall.plot]
replot = true
"""


def written(tmp_path, text: str, name: str = "f.toml") -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def flagged(argv: list[str]):
    args = cli.parse(argv)
    return args, cli.config_flags(args)


def test_a_file_gives_the_command_its_preferences_and_the_command_line_wins(tmp_path):
    path = written(tmp_path, FILE.format(extra=""))
    args, given = flagged(["run", path])
    assert (args.journal, args.keep, args.rerun, args.wait) == (True, ["work"], True, True)
    assert given == ["--journal", "--keep work", "--rerun", "--wait"]
    args, given = flagged(["run", path, "--keep", "logs"])
    assert args.keep == ["logs"] and "--keep work" not in given
    args, _ = flagged(["plot", path])
    assert args.replot and not hasattr(args, "rerun")                       # plot's own switch; run's left to run


def test_an_import_gives_its_flags_the_file_its_own_over_them(tmp_path):
    common = written(tmp_path, '[file]\nschema = 3\n\n[heimdall]\nplain = true\njournal = false\n', "common.toml")
    path = written(tmp_path, FILE.format(extra=f'import = ["{common}"]'))
    args, _ = flagged(["run", path])
    assert args.plain and args.journal                                       # the file's journal over the import's


def test_every_option_is_a_preference_or_says_why_it_is_not():
    """Each option of a command that reads a config is a preference a file may set, or has its reason."""
    dests = {action.dest for options in cli._options().values() for action in options.values()}
    assert set(cli.PREFERENCES) <= dests
    assert not dests - set(cli.PREFERENCES) - set(cli.NOT_PREFERENCES)


@pytest.mark.parametrize("table, message", [
    ('[heimdall]\njournl = true\n', "no command that reads a config has that option"),
    ('[heimdall.run]\ndraw = "x"\n', "heimdall run has no such option"),
    ('[heimdall.runs]\nplain = true\n', "no such command reads a config"),
    ('[heimdall]\njournal = "yes"\n', "is a switch: true or false"),
    ('[heimdall.run]\nset = ["errand.events=1"]\n', "heimdall run has no such option"),
    ('[heimdall.run]\nplan = true\n', "a mode"),
    ('[heimdall.cluster]\ncancel = true\n', "a mode"),
    ('[heimdall.watch]\npid = 12\n', "a target"),
    ('[heimdall.run]\npoints = "1"\n', "a selection"),
    ('[heimdall]\nsets = "totality"\n', "a selection"),
    ('[heimdall.run]\nno-plot = true\n', r"the study's own setting"),
])
def test_what_heimdall_refuses(tmp_path, table, message):
    path = written(tmp_path, f'[file]\nschema = 3\n\n[errand]\nname = "f"\nassignment = "Demo"\n\n{table}')
    with pytest.raises(HeimdallError, match=message):
        flagged(["run", path])


def test_the_study_s_own_settings_point_to_run(tmp_path):
    path = written(tmp_path, '[file]\nschema = 3\n\n[errand]\nname = "f"\nassignment = "Demo"\n\n[heimdall]\nno-stats = true\n')
    with pytest.raises(HeimdallError) as caught:
        flagged(["run", path])
    assert "[errand] stats = false" in caught.value.hint
