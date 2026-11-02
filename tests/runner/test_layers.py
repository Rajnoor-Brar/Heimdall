"""Layers (V56): [errand] for every configuration (V99, was [errand.defaults]), extends, [errand.cfgs.<cfg>] (V98), [config].import (V93), "default" in a child, sweeping events, --show-config."""

from __future__ import annotations

from pathlib import Path

import pytest
import tomli_w

from runner import cli, config
from runner.errors import HeimdallError

from helpers import parse, plan, raw


def configurations(**tables) -> dict:
    """raw() with [errand.cfgs.one] replaced by these configurations ([errand.configuration] = the first);
    `errand` adds keys to [errand] itself, which every configuration starts from (V99)."""
    data = raw()
    data["errand"].update(tables.pop("errand", {}))
    data["errand"]["cfgs"] = tables
    data["errand"]["configuration"] = next(iter(tables))
    return data



def used(data: dict, *more: str) -> dict:
    """A file written from raw() whose pdf (and `more`) a configuration uses: a quantity nothing uses is
    refused."""
    data.setdefault("static", {}).setdefault("pdf", "MSTW08lo")
    for name in more:
        data["static"].setdefault(name, "#1")
    return data

def test_run_gives_every_configuration_its_keys_and_their_own_win(scratch):
    errand = parse(configurations(errand={"tools": [["pythia", "rivet"]], "event_count": 50},
                                  a={}, b={"event_count": 7}), scratch)
    a, b = errand.configurations["a"], errand.configurations["b"]
    assert a.tools == b.tools == [["pythia", "rivet"]] and (a.event_count, b.event_count) == (50, 7)
    assert a.origins["event_count"] == "[errand]" and b.origins["event_count"] == "[errand.cfgs.b]"
    assert a.origins["tools"] == "[errand]"


def test_extends_takes_the_parents_keys_but_not_its_folder_or_title(scratch):
    errand = parse(configurations(base={"tools": [["pythia", "rivet"]], "sweeps": ["pdf"], "label": "PDFs", "event_count": 9},
                                  big={"extends": "base", "event_count": 900}), scratch)
    big = errand.configurations["big"]
    assert big.sweeps == ["pdf"] and big.event_count == 900 and big.tools == [["pythia", "rivet"]]
    assert big.label == "big" and big.title == "big"                  # its own label and title
    assert big.origins["sweeps"] == "[errand.cfgs.base]"


def test_extends_chains_and_refuses_a_circle_or_a_missing_parent(scratch):
    chained = parse(configurations(a={"tools": [["pythia", "rivet"]], "threads": 3}, b={"extends": "a"}, c={"extends": "b"}),
                    scratch)
    assert chained.configurations["c"].threads == 3
    with pytest.raises(HeimdallError, match="round in a circle"):
        parse(configurations(a={"extends": "b", "tools": [["pythia"]]}, b={"extends": "a"}), scratch)
    with pytest.raises(HeimdallError, match="not a configuration") as caught:
        parse(configurations(a={"tools": [["pythia", "rivet"]]}, b={"extends": "aa"}), scratch)
    assert "'a'" in caught.value.hint


def test_run_cannot_set_a_configurations_own_keys_and_run_defaults_is_gone(scratch):
    """V99: label, title and extends are each configuration's own; [errand.defaults] is refused, read
    leniently (heimdall migrate's) as keys of [errand], and `defaults` may now name a configuration."""
    with pytest.raises(HeimdallError, match="unknown key 'label'"):
        parse(configurations(errand={"label": "x"}, a={"tools": [["pythia", "rivet"]]}), scratch)
    data = raw(errand__defaults={"threads": 3})
    with pytest.raises(HeimdallError, match=r"\[errand.defaults\] is \[errand\] now") as error:
        parse(data, scratch)
    assert "heimdall migrate" in error.value.hint
    assert config.parse(data, scratch / "t.toml", strict=False).configuration(None).threads == 3
    assert "defaults" in parse(configurations(defaults={"tools": [["pythia", "rivet"]]}), scratch).configurations


def test_default_in_a_child_is_the_next_layers_value(scratch):
    errand = parse(configurations(errand={"threads": 4}, a={"tools": [["pythia", "rivet"]], "threads": "default"}), scratch)
    assert errand.configurations["a"].threads == 4 and errand.configurations["a"].origins["threads"] == "[errand]"


def test_static_merges_through_the_layers_and_default_at_the_top_unsets(scratch):
    data = configurations(a={"tools": [["pythia", "rivet"]], "static": {"pdf": "NNPDF23lo"}},
                          b={"extends": "a", "static": {"pdf": "default"}})
    errand = parse(data, scratch)
    assert errand.configurations["b"].static == {"pdf": "NNPDF23lo"}   # "default" keeps the parent's
    data = raw(static={"pdf": "default"})
    assert parse(data, scratch).configuration(None).static == {}       # at the top: not set at all


def test_a_configurations_prelim_replaces_the_files_whole(scratch):
    errand = parse(configurations(a={"tools": [["pythia", "rivet"]], "prelim": {"files": ["x.hepmc"]}}), scratch)
    assert errand.configurations["a"].prelim == {"files": ["x.hepmc"]}   # no FIFO inherited: its chain's own


def test_include_gives_tables_and_the_file_wins(scratch):
    common = scratch / "common.toml"
    common.write_text(tomli_w.dumps({
        "quantities": {"energies": {"values": [[275, 18]], "tags": ["18x275"]},
                       "pdf": {"values": ["LHAPDF6:MSTW2008lo68cl"], "tags": ["old"]}},
        "plot": {"ratio": True, "y_gutter": 2.0},
        "errand": {"event_count": 33},
    }), encoding="utf-8")
    data = used(raw(config={"import": [str(common)]}, plot={"y_gutter": 0.3}))
    del data["errand"]["event_count"]
    path = scratch / "run.toml"
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    errand = config.load(str(path))
    assert errand.quantities["energies"].tags == ["18x275"]             # from the include
    assert errand.quantities["pdf"].tags == ["MSTW08lo", "NNPDF23lo"]   # the file's own, whole: nothing of "old"
    assert errand.plot["ratio"] is True and errand.plot["y_gutter"] == 0.3   # tables deep, the file's keys win
    assert errand.configuration(None).event_count == 33
    assert errand.included == {"quantities.energies": "common.toml"}


def test_imports_nest_depth_first_and_say_where_from(scratch):
    """V94: an imported file's own imports come first; the file over it wins; origins name the path."""
    inner = scratch / "inner.toml"
    inner.write_text(tomli_w.dumps({"quantities": {"energies": {"values": [[275, 18]], "tags": ["18x275"]}},
                                    "plot": {"ratio": True, "y_gutter": 2.0}}), encoding="utf-8")
    middle = scratch / "middle.toml"
    middle.write_text(tomli_w.dumps({"config": {"import": str(inner)}, "plot": {"y_gutter": 1.0}}), encoding="utf-8")
    path = scratch / "run.toml"
    path.write_text(tomli_w.dumps(used(raw(config={"import": str(middle)}))), encoding="utf-8")
    errand = config.load(str(path))
    assert errand.quantities["energies"].tags == ["18x275"] and errand.plot == {"ratio": True, "y_gutter": 1.0}
    assert errand.included == {"quantities.energies": "middle.toml ← inner.toml"}


def test_an_import_circle_is_refused(scratch):
    a, b = scratch / "a.toml", scratch / "b.toml"
    a.write_text(tomli_w.dumps(raw(errand__name="a", config={"import": str(b)})), encoding="utf-8")
    b.write_text(tomli_w.dumps({"config": {"import": str(a)}}), encoding="utf-8")
    with pytest.raises(HeimdallError, match="imports go round in a circle: a.toml → b.toml → a.toml"):
        config.load(str(a))


def test_a_file_that_imports_has_its_own_location(scratch):
    """V94, V100: [errand].name and project are never imported; a run may share an imported run's name (its
    results beside the other's), but no folder: a configuration's NN_label is its own."""
    other = scratch / "other.toml"
    other.write_text(tomli_w.dumps(raw(errand__serial=2)), encoding="utf-8")
    path = scratch / "run.toml"
    path.write_text(tomli_w.dumps({"config": {"import": str(other)}, "errand": {"assignment": "Demo"}}), encoding="utf-8")
    with pytest.raises(HeimdallError, match=r"sets its own \[errand\].name"):
        config.load(str(path))
    beside = {"config": {"import": str(other)}, "errand": {"assignment": "Demo", "name": "t", "serial": 3}}
    path.write_text(tomli_w.dumps(beside), encoding="utf-8")
    assert set(config.load(str(path)).configurations) == {"one"}                 # t/03_one beside t/02_one
    beside["errand"]["serial"] = 2
    path.write_text(tomli_w.dumps(beside), encoding="utf-8")
    with pytest.raises(HeimdallError, match=r"\[errand.cfgs.one\] and other.toml's \[errand.cfgs.one\] would both write Demo/t/02_one"):
        config.load(str(path))


def test_another_projects_file_brings_its_cards_and_plans_the_same(scratch, monkeypatch):
    """V94: `<Project>/<name>`; its bare card paths stay its project's, so its points keep their identities."""
    import shutil
    from runner import quantities, record, sweep, tools
    from runner.paths import configs_root
    fixtures = configs_root()
    root = scratch / "configs"
    (root / "Other").mkdir(parents=True)
    (root / "Demo").mkdir()
    shutil.copy(fixtures / "Demo" / "ep.cmnd", root / "Other" / "ep.cmnd")
    monkeypatch.setenv("HEIMDALL_CONFIGS", str(root))
    (root / "Other" / "other.toml").write_text(tomli_w.dumps(used(raw(errand__name="other", errand__assignment="Other"))), encoding="utf-8")
    (root / "Demo" / "mine.toml").write_text(tomli_w.dumps(
        {"config": {"import": "Other/other"}, "errand": {"name": "mine", "assignment": "Demo"}}), encoding="utf-8")

    def identity(name):
        errand = config.load(name)
        conf = errand.configuration(None)
        plan = tools.plan_point(errand, conf, sweep.points(errand, conf)[0], quantities.load_master(errand.assignment, errand.master_toml))
        return errand, record.identity(plan)

    theirs, mine = identity("Other/other"), identity("Demo/mine")
    assert mine[0].tools["pythia"].baseconfig == [str(root / "Other" / "ep.cmnd")]
    assert mine[0].included["tools.pythia"] == "other.toml" and mine[0].assignment == "Demo"
    assert mine[1] == theirs[1]



def test_bare_names_are_beside_the_file_naming_them(scratch, monkeypatch):
    """A card, an import or a master named bare is beside the file that names it, not rederived from <A>: an
    errand file in configs/Demo/sub/ finds its card and its import there, and an imported file of another
    folder keeps its own cards; the points plan as the fixture's do, so no identity moves."""
    import shutil
    from runner import quantities, record, sweep, tools
    from runner.paths import configs_root
    fixtures = configs_root()
    root = scratch / "configs"
    sub = root / "Demo" / "sub"
    sub.mkdir(parents=True)
    shutil.copy(fixtures / "Demo" / "ep.cmnd", sub / "ep.cmnd")
    monkeypatch.setenv("HEIMDALL_CONFIGS", str(root))
    (sub / "common.toml").write_text(tomli_w.dumps({"plot": {"y_gutter": 1.5}}), encoding="utf-8")
    (sub / "mine.toml").write_text(tomli_w.dumps(used(raw(errand__name="mine", errand__assignment="Demo",
                                                          config={"import": "common"}))), encoding="utf-8")
    errand = config.load("Demo/sub/mine")
    assert errand.folder == sub and errand.plot["y_gutter"] == 1.5
    from runner.paths import resolve
    assert resolve(errand.tools["pythia"].baseconfig[0], "baseconfig", assignment="Demo", folder=errand.folder) == sub / "ep.cmnd"
    (root / "Demo" / "top.toml").write_text(tomli_w.dumps(
        {"config": {"import": "Demo/sub/mine"}, "errand": {"name": "top", "assignment": "Demo"}}), encoding="utf-8")
    top = config.load("Demo/top")
    assert top.tools["pythia"].baseconfig == [str(sub / "ep.cmnd")]          # the imported file's own card

    def identity(errand):
        conf = errand.configuration(None)
        return record.identity(tools.plan_point(errand, conf, sweep.points(errand, conf)[0],
                                                quantities.load_master(errand.assignment, errand.master_toml, errand.folder)))
    monkeypatch.setenv("HEIMDALL_CONFIGS", str(fixtures))
    fixture = config.load(str(sub / "mine.toml"))
    assert identity(errand) == identity(top) == identity(fixture)

def _other(scratch) -> Path:
    """A run with two configurations, a figure and an extra quantity, to import parts of."""
    data = raw(errand__name="other", errand__cfgs__two={"tools": [["pythia", "rivet"]], "event_count": 99},
               quantities__energies={"values": [[275, 18]], "tags": ["18x275"]},
               plot={"ratio": True, "figures": {"tails": {"objects": ["d04-*"]}, "keep": {"objects": ["d05-*"]}}})
    path = scratch / "other.toml"
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path


def test_an_import_may_take_only_some_of_a_file(scratch):
    """V95: `only` keeps those sections or dotted keys; one the file has not is refused, with the nearest."""
    other = _other(scratch)
    path = scratch / "run.toml"
    mine = {"errand": {"name": "mine", "assignment": "Demo", "configuration": "two"}}
    path.write_text(tomli_w.dumps({**mine, "config": {"import": [{"from": str(other), "only": ["errand.cfgs.two", "quantities", "tools", "prelim"]}]}}),
                    encoding="utf-8")
    errand = config.load(str(path))
    assert set(errand.configurations) == {"two"} and errand.configuration(None).event_count == 99
    assert not errand.plot and set(errand.quantities) == {"pdf", "energies"}
    path.write_text(tomli_w.dumps({**mine, "config": {"import": [{"from": str(other), "only": ["errand.cfgs.tow"]}]}}), encoding="utf-8")
    with pytest.raises(HeimdallError, match="only names 'errand.cfgs.tow', which other.toml has not") as error:
        config.load(str(path))
    assert "two" in error.value.hint


def test_drop_takes_out_what_an_import_gave(scratch):
    """V95: before this file's tables; a drop that names nothing is refused, and so is one with no import."""
    other = _other(scratch)
    path = scratch / "run.toml"
    mine = {"errand": {"name": "mine", "assignment": "Demo"}}
    path.write_text(tomli_w.dumps({**mine, "config": {"import": str(other), "drop": ["errand.cfgs.two", "plot.figures.tails", "quantities.energies"]}}),
                    encoding="utf-8")
    errand = config.load(str(path))
    assert set(errand.configurations) == {"one"} and set(errand.plot["figures"]) == {"keep"} and "energies" not in errand.quantities
    assert "quantities.energies" not in errand.included and errand.included["errand.cfgs.one"] == "other.toml"
    path.write_text(tomli_w.dumps({**mine, "config": {"import": str(other), "drop": ["plot.figures.tials"]}}), encoding="utf-8")
    with pytest.raises(HeimdallError, match="drop names 'plot.figures.tials', which no import gave") as error:
        config.load(str(path))
    assert "tails" in error.value.hint
    path.write_text(tomli_w.dumps(raw(config={"drop": ["errand.cfgs.one"]})), encoding="utf-8")
    with pytest.raises(HeimdallError, match="this file imports nothing"):
        config.load(str(path))


def _written(scratch, data, name="run.toml") -> str:
    path = scratch / name
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return str(path)


def test_vars_are_said_once_and_keep_their_type(scratch):
    """V96: a whole-value var keeps its type, an inline one is text; --set reaches them; the file plans as
    if written out (the run it parses to is the same)."""
    data = raw(config={"vars": {"events": 500, "ana": "photo_eic", "cuts": [4.0, 5.0]}},
               errand__event_count="{var:events}", tools__rivet__analyses=["{var:ana}"],
               quantities__cut={"values": "{var:cuts}", "target": "rivet/photo_eic", "key": "ETMIN"},
               plot={"title": "{var:ana}: {var:events} events"})
    errand = config.load(_written(scratch, used(data, "cut")))
    assert errand.configuration(None).event_count == 500 and errand.tools["rivet"].extra["analyses"] == ["photo_eic"]
    assert errand.quantities["cut"].values == [4.0, 5.0] and errand.plot["title"] == "photo_eic: 500 events"
    written = raw(errand__event_count=500, quantities__cut={"values": [4.0, 5.0], "target": "rivet/photo_eic", "key": "ETMIN"},
                  plot={"title": "photo_eic: 500 events"})
    plain = config.load(_written(scratch, used(written, "cut"), "plain.toml"))
    assert (plain.quantities["cut"].values, plain.plot) == (errand.quantities["cut"].values, errand.plot)
    assert config.load(_written(scratch, data), sets=["config.vars.events=7"]).configuration(None).event_count == 7


def test_a_configuration_may_have_its_own_vars_and_data(scratch):
    """V179: [cfgs.<name>] vars, over [file.vars], and data, in place of [plot.data]: the file read for that
    configuration (config.for_configuration, or load(…, configuration=)) runs its own analysis and draws its own
    data; read for another, it is refused where it would plan or write a plot document."""
    from runner import tools
    data = raw(config={"vars": {"ana": "photo_eic"}}, tools__rivet__analyses=["{var:ana}"],
               tools__rivet__output_file="{var:ana}.yoda",
               plot={"data": {"file": "./photo.yoda", "legend": "photo", "map": {"d01-x01-y01": "/REF/A/d01-x01-y01"}}},
               errand__cfgs__dis={"tools": [["pythia", "rivet"]], "vars": {"ana": "dis_eic"},
                               "data": {"file": "./dis.yoda", "legend": "dis", "map": {"d01-x01-y01": "/REF/B/d01-x01-y01"}}},
               errand__cfgs__more={"extends": "dis", "event_count": 20})
    path = _written(scratch, used(data))
    errand = config.load(path)                                                 # read for one, the default
    assert errand.tools["rivet"].extra["analyses"] == ["photo_eic"] and errand.plot["data"]["legend"] == "photo"
    assert config.for_configuration(errand, "one") == (errand, errand.configuration("one"))
    dis, conf = config.for_configuration(errand, "dis")
    assert dis is not errand and conf.key == "dis" and dis.tools["rivet"].output_file == ["dis_eic.yoda"]
    assert dis.plot["data"]["legend"] == "dis" and dis.plot["data"]["map"]["d01-x01-y01"] == "/REF/B/d01-x01-y01"
    more = config.load(path, configuration="more")                             # through what it extends
    assert more.tools["rivet"].extra["analyses"] == ["dis_eic"] and more.applied == more.configuration("more").own
    point = __import__("runner.sweep", fromlist=["points"]).points(errand, errand.configuration("dis"))[0]
    with pytest.raises(HeimdallError, match="sets its own vars and data, and this file was read for another"):
        tools.plan_point(errand, errand.configuration("dis"), point, {})


def test_a_var_is_checked(scratch):
    with pytest.raises(HeimdallError, match=r"\{var:evnts\} is not in \[config.vars\]") as error:
        config.load(_written(scratch, raw(config={"vars": {"events": 5}}, errand__event_count="{var:evnts}")))
    assert "events" in error.value.hint
    with pytest.raises(HeimdallError, match="is a list: it can only be a whole value"):
        config.load(_written(scratch, raw(config={"vars": {"l": [1, 2]}}, plot={"title": "a {var:l}"})))


def test_an_imported_file_takes_the_importers_vars(scratch):
    """V96: a shared file written with parameters; the file that imports it gives them."""
    shared = _written(scratch, {"tools": {"rivet": {"tool": "rivet", "input": "events.hepmc", "analyses": ["{var:ana}"],
                                                    "output_file": "{var:ana}.yoda"}}}, "shared.toml")
    data = used(raw(config={"import": shared, "vars": {"ana": "photo_eic"}}))
    del data["tools"]["rivet"]
    errand = config.load(_written(scratch, data))
    assert errand.tools["rivet"].extra["analyses"] == ["photo_eic"] and errand.tools["rivet"].output_file == ["photo_eic.yoda"]


def test_meta_versions_warn_and_never_refuse(scratch, monkeypatch):
    """V97: the stack a file was run with; a different version is a warning, a misspelt package an error."""
    from runner import tools
    monkeypatch.setattr(tools, "_stack_version", {"pythia8": "8.317", "rivet": "rivet v4.1.3", "onnx": ""}.get)
    errand = parse(raw(config={"meta": {"author": "me", "versions": {"pythia8": "8.317", "rivet": "4.1", "onnx": "1.20"}}}), scratch)
    assert tools.meta_notes(errand) == ["t.toml was run with onnx 1.20; the stack gives no version of it to compare"]
    errand = parse(raw(config={"meta": {"versions": {"pythia8": "8.312", "rivet": "4.1.3"}}}), scratch)
    assert tools.meta_notes(errand) == ["t.toml was run with pythia8 8.312; the stack has 8.317 (it runs anyway, at your own risk)"]
    with pytest.raises(HeimdallError, match="'pythia' is not a package of env/stack.toml") as error:
        parse(raw(config={"meta": {"versions": {"pythia": "8.317"}}}), scratch)
    assert "pythia8" in error.value.hint
    with pytest.raises(HeimdallError, match="version is a string"):
        parse(raw(config={"meta": {"versions": {"pythia8": 8.317}}}), scratch)


def test_an_imported_files_vars_come_with_the_part_taken(scratch):
    """V101: `only` keeps the file's [config.vars], under the importer's, so its tables' {var:…} resolve."""
    shared = _written(scratch, {"config": {"vars": {"ana": "photo_eic", "out": "photo"}},
                                "tools": {"rivet": {"tool": "rivet", "input": "events.hepmc", "analyses": ["{var:ana}"],
                                                    "output_file": "{var:out}.yoda"}}}, "shared.toml")
    data = used(raw(config={"import": [{"from": shared, "only": ["tools.rivet"]}], "vars": {"out": "mine"}}))
    del data["tools"]["rivet"]
    errand = config.load(_written(scratch, data))
    assert errand.tools["rivet"].extra["analyses"] == ["photo_eic"] and errand.tools["rivet"].output_file == ["mine.yoda"]


def test_master_is_config_now(scratch):
    """V93 (break and migrate): [master] is refused with what to write."""
    with pytest.raises(HeimdallError, match=r"\[master\] is \[config\] now") as error:
        parse(raw(master={"master_toml": "m.toml"}), scratch)
    assert "heimdall migrate" in error.value.hint


def test_events_swept_as_a_quantity_set_each_points_count(scratch):
    data = raw(errand__cfgs__one__sweeps=["events"], quantities__events={"values": [100, 2500], "tags": ["e100", "e2500"]})
    _, _, small = plan(data, scratch, point=0)
    _, _, large = plan(data, scratch, point=1)
    assert (small.events, large.events) == (100, 2500)
    assert "Main:numberOfEvents = 2500" in large.writes[large.rendered["pythia"].card_combined]
    assert small.identity != large.identity if small.identity else True


def test_show_config_says_where_each_value_came_from(scratch):
    errand = parse(configurations(errand={"tools": [["pythia", "rivet"]]}, a={"event_count": 5}), scratch)
    lines = cli.show_config(errand, ["a"])
    assert any(l.split()[0] == "tools" and l.endswith("[errand]") for l in lines[1:])
    assert any(l.split()[0] == "event_count" and l.endswith("[errand.cfgs.a]") for l in lines[1:])
    assert any(l.split()[0] == "parallelism" and l.endswith("default") for l in lines[1:])
    assert any(l.split()[0] == "label" and l.endswith("default") for l in lines[1:])
