"""A configuration folder's tag (I-113 T1–T2, V223): where it comes from (`--tag` over the one its record has over
its configuration's `tag` key), where it is kept (records/<run>/tag, the truth, and its plot document's
[source].tag), `heimdall tag` showing, setting and clearing it, the refusals, and what shows it (`heimdall runs`,
`heimdall status`). A tag is never part of a point's identity."""

from __future__ import annotations

import os
import tomllib

import pytest

from helpers import parse, raw
from runner import cli, config, house, record, runs, tools
from runner.errors import HeimdallError
from runner.paths import records_root, results_root

TRUE = {"true": {"tool": "exec", "executable": "/bin/true"}}


def study(scratch, name: str = "tagged", **changes):
    """configs/Demo/<name>.toml: one point of /bin/true, its configuration `one` (folder Demo/<name>/one), whose
    records and results an earlier session left are gone first."""
    import shutil
    import tomli_w
    for root in (records_root(), results_root()):
        shutil.rmtree(root / "Demo" / name, ignore_errors=True)
    folder = scratch / "configs" / "Demo"
    folder.mkdir(parents=True, exist_ok=True)
    data = raw(run__name=name, run__cfgs__one__tools=[["true"]], tools=TRUE, prelim={}, quantities={}, **changes)
    path = folder / f"{name}.toml"
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def configs(scratch):
    os.environ["HEIMDALL_CONFIGS"] = str(scratch / "configs")
    yield scratch
    os.environ.pop("HEIMDALL_CONFIGS", None)


def run(path, *more) -> int:
    return cli.main(["run", str(path), "--plain", *more])


def kept(name: str = "tagged") -> tuple[str | None, str | None]:
    """The folder's tag as its record holds it, and as its plot document's [source] does."""
    rel = f"Demo/{name}/one"
    document = results_root() / rel / "plot.toml"
    source = tomllib.loads(document.read_text(encoding="utf-8"))["source"] if document.is_file() else {}
    return record.run_tag(records_root() / rel), source.get("tag")


def test_a_tag_is_a_short_name():
    for good in ("nlo", "run2.v1", "pdf+scale", "A_b-3", "x" * 40):
        assert config.check_tag(good) == good
    for bad in ("", "two words", "x" * 41, "nlo/2", "é", 3):
        with pytest.raises(HeimdallError, match="letters, digits, '.', '_', '\\+' and '-', at most 40"):
            config.check_tag(bad, "--tag")


def test_a_configuration_inherits_its_tag_and_a_bad_one_is_refused(scratch):
    assert parse(raw(run__tag="lo"), scratch).configuration("one").tag == "lo"
    assert parse(raw(run__tag="lo", run__cfgs__one__tag=""), scratch).configuration("one").tag == ""    # "": none
    assert parse(raw(run__cfgs__one__tag="nlo"), scratch).configuration("one").tag == "nlo"
    assert parse(raw(), scratch).configuration("one").tag == ""
    with pytest.raises(HeimdallError) as error:
        parse(raw(run__cfgs__one__tag="n lo"), scratch)
    assert "[run.cfgs.one].tag" in str(error.value.where)


def test_a_tag_moves_no_identity(scratch):
    """record.identity hashes what decides a result: a tag is none of it."""
    from runner import quantities, sweep

    def identities(data):
        run_ = parse(data, scratch)
        conf = run_.configuration("one")
        master = quantities.load_master(run_.project, run_.master_toml)
        return [record.identity(tools.plan_point(run_, conf, p, master)) for p in sweep.points(run_, conf)]

    assert identities(raw(run__cfgs__one__tag="nlo")) == identities(raw())


def test_the_tag_comes_from_the_flag_else_the_folder_else_the_configuration(configs):
    path = study(configs, run__cfgs__one__tag="cfg")
    assert run(path, "--rerun") == 0
    assert kept() == ("cfg", "cfg")                                     # the configuration's key, the first time
    assert cli.main(["tag", "Demo/tagged/one", "mine"]) == 0
    assert kept() == ("mine", "mine")
    assert run(path) == 0
    assert kept() == ("mine", "mine")                                   # run again: the folder keeps its own
    assert run(path, "--tag", "flag") == 0
    assert kept() == ("flag", "flag")                                   # --tag over both
    (entry, *_) = sorted(runs.entries(), key=lambda e: e.get("started") or 0, reverse=True)
    assert entry["configuration_tags"] == {"one": "flag"}               # the registry carries it


def test_an_untagged_run_writes_no_tag(configs):
    path = study(configs, "plain")
    assert run(path, "--rerun") == 0
    assert kept("plain") == (None, None)
    assert not (records_root() / "Demo/plain/one" / record.TAG_FILE).exists()
    (entry,) = runs.entries()
    assert "configuration_tags" not in entry


def test_a_plan_says_the_tag_and_writes_none(configs, capsys):
    path = study(configs, "planned", run__tag="lo")
    assert run(path, "--plan", "--tag", "nlo") == 0
    assert "tag: nlo (--tag)" in capsys.readouterr().out
    assert run(path, "--plan") == 0
    assert "tag: lo ([run])" in capsys.readouterr().out
    assert record.run_tag(records_root() / "Demo/planned/one") is None


def test_a_bad_flag_is_refused_before_anything_runs(configs, capsys):
    path = study(configs, "refused")
    assert run(path, "--tag", "no good") == 2
    assert "is not a tag" in capsys.readouterr().err
    assert not (records_root() / "Demo/refused").exists() and not runs.entries()


def test_heimdall_tag_shows_sets_and_clears(configs, capsys):
    path = study(configs, "shown")
    assert run(path, "--rerun") == 0
    capsys.readouterr()
    assert cli.main(["tag", "Demo/shown/one"]) == 0
    assert capsys.readouterr().out == "Demo/shown/one has no tag\n"
    assert cli.main(["tag", str(results_root() / "Demo/shown/one"), "v1"]) == 0     # a path under results/ too
    assert capsys.readouterr().out == "Demo/shown/one: tagged v1\n"
    assert kept("shown") == ("v1", "v1")
    assert cli.main(["tag", "Demo/shown/one", "v2"]) == 0
    assert capsys.readouterr().out == "Demo/shown/one: tagged v2 (was v1)\n"
    assert cli.main(["tag", "Demo/shown/one"]) == 0
    assert capsys.readouterr().out == "Demo/shown/one: v2\n"
    document = (results_root() / "Demo/shown/one/plot.toml").read_text(encoding="utf-8")
    assert document.startswith("# A run's plot document")                 # rewritten whole, its header kept
    assert cli.main(["tag", "Demo/shown/one", "--clear"]) == 0
    assert capsys.readouterr().out == "Demo/shown/one: its tag v2 removed\n"
    assert kept("shown") == (None, None)
    assert run(path) == 0
    assert kept("shown") == (None, None)                                  # nothing gives it one again


def test_heimdall_tag_refuses(configs, capsys):
    path = study(configs, "refusals")
    assert run(path, "--rerun") == 0
    capsys.readouterr()
    for argv, said in ((["tag", "Demo/refusals/one", "a b"], "is not a tag"),
                       (["tag", "Demo/refusals/one", "x", "--clear"], "one or the other"),
                       (["tag", "Demo/refusals/one/single", "x"], "names a point"),
                       (["tag", "Demo/refusals/none", "x"], "no record Demo/refusals/none"),
                       (["tag", "Demo/refusals"], "names no record")):
        assert cli.main(argv) == 2, argv
        assert said in capsys.readouterr().err, argv
    assert record.run_tag(records_root() / "Demo/refusals/one") is None


def test_a_tag_without_a_plot_document_is_the_records(configs):
    path = study(configs, "nodoc")
    assert run(path, "--rerun") == 0
    (results_root() / "Demo/nodoc/one/plot.toml").unlink()
    assert cli.main(["tag", "Demo/nodoc/one", "kept"]) == 0
    assert record.run_tag(records_root() / "Demo/nodoc/one") == "kept"
    assert not (results_root() / "Demo/nodoc/one/plot.toml").exists()


def test_runs_and_status_show_the_tag(configs, capsys):
    entry = {"id": "20261031-1200-ab", "config": "/w/configs/Demo/t.toml", "work": "/w", "configurations": ["one", "two"],
             "configuration_serials": {"one": 2}, "configuration_tags": {"one": "nlo"}, "started": 1.0, "finished": 2.0,
             "code": 0, "pid": 1, "host": runs.host()}
    lines = house.runs_listing([entry], [], {}, now=3.0, limit=5)
    assert "      Demo/t · 02 one [nlo], two" in lines
    path = study(configs, "status", run__cfgs__one__tag="lo")
    assert run(path, "--rerun") == 0
    capsys.readouterr()
    assert cli.main(["status", str(path)]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("status · one [lo] (Demo/status/one): 1 complete")
