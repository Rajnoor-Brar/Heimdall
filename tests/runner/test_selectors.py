"""Tools chosen by a quantity (V19) and compared in one configuration (task F): a varied value no tool of a
point reads (V151); one pdf for every generator (V152)."""

from __future__ import annotations

import shutil

import pytest

from runner import config, quantities, sweep, tools
from runner.errors import HepError

from helpers import parse, raw

OTHER = {"tool": "exec", "executable": "/bin/true", "output_file": "events.hepmc"}     # a generator that reads no pdf


def plan_all(data: dict, scratch) -> dict:
    run = parse(data, scratch)
    conf = run.configuration(None)
    master = quantities.load_master(run.project, run.master_toml)
    return {p.name: tools.plan_point(run, conf, p, master) for p in sweep.points(run, conf)}


def test_a_varied_value_no_tool_of_the_point_reads_is_refused(scratch):
    data = raw(run__cfgs__one__tools=[["@gen", "rivet"]], run__cfgs__one__sweeps=["gen", "pdf"], tools__other=OTHER,
               quantities__gen={"values": ["pythia", "other"], "tags": ["py", "ot"]})
    with pytest.raises(HepError, match=r"ot_MSTW08lo: \[quantities.pdf\] is varied, but no tool of this point reads it "
                                       r"\(other, rivet\)") as refused:
        plan_all(data, scratch)
    assert "a configuration of its own" in refused.value.hint


def test_a_fixed_value_one_alternative_does_not_read_is_accepted(scratch):
    data = raw(run__cfgs__one__tools=[["@gen", "rivet"]], run__cfgs__one__sweeps=["gen"], tools__other=OTHER,
               quantities__gen={"values": ["pythia", "other"], "tags": ["py", "ot"]}, static={"pdf": "MSTW08lo"})
    plans = plan_all(data, scratch)
    assert plans["ot"].consumers["pdf"] == [] and [m.tag for m in plans["py"].consumers["pdf"]] == ["pythia"]


SWITCH = """[run]
project = "Demo"
name    = "switch"
run     = "all"
events  = 10
threads = 1
chain   = [["@gen", "rivet"]]

[tools.first]
uses   = "pythia"
card   = "ep.cmnd"
output = "events.hepmc"

[tools.other]
uses   = "pythia"
card   = "ep.cmnd"
output = "events.hepmc"

[tools.rivet]
input    = "events.hepmc"
analyses = ["photo_eic"]
output   = "jets.yoda"

[quantities.gen]
points = [{ tag = "p1", value = "first" }, { tag = "p2", value = "other" }]

[quantities.mpi]                      # one switch, each generator (each table) its own field
fields = { a = { first = "PartonLevel:MPI" }, b = { other = "PartonLevel:ISR" } }
points = [{ tag = "on", a = "on", b = "on" }, { tag = "off", a = "off", b = "off" }]

[cfgs.all]
vary = ["gen", "mpi"]
"""


def test_a_compound_s_fields_are_read_one_a_generator(scratch):
    """V180: a varied compound (its fields entangled) is read on a point when one of its fields is: each
    generator takes its own field of one switch, and the points still differ by it."""
    path = scratch / "switch.toml"
    path.write_text(SWITCH, encoding="utf-8")
    run = config.load(str(path))
    conf = run.configuration("all")
    master = quantities.load_master(run.project, run.master_toml)
    by = {p.name: tools.plan_point(run, conf, p, master) for p in sweep.points(run, conf)}
    assert sorted(by) == ["p1_off", "p1_on", "p2_off", "p2_on"]
    assert [m.tag for m in by["p1_on"].consumers["mpi"]] == ["first"] and by["p1_on"].consumers["mpi_b"] == []
    assert [m.tag for m in by["p2_off"].consumers["mpi_b"]] == ["other"] and by["p2_off"].consumers["mpi"] == []
    from runner import record
    for planned in by.values():
        tools.finalise(planned, 12345)
    assert len({record.identity(by[n]) for n in by}) == 4                     # each differs by the switch
    assert "PartonLevel:MPI = off" in card_of(by["p1_off"], "first") and "PartonLevel:ISR = on" in card_of(by["p2_on"], "other")


def test_a_set_naming_a_compound_names_all_its_fields(scratch):
    """V186: curves = { mpi = "all" } names the compound mpi, its later field (mpi_b) too: one page of both settings,
    not a page per value of mpi_b, which varies with mpi and was taken for an axis the set leaves out."""
    path = scratch / "switch.toml"
    path.write_text(SWITCH, encoding="utf-8")
    run = config.load(str(path))
    points = sweep.points(run, run.configuration("all"))
    spec, = sweep.set_entries({"few": {"pages": {"gen": "p1"}, "curves": {"mpi": "all"}}}, "w")
    sweep.check_set(run, spec, points)
    cells, notes = sweep.set_cells(run, points, spec)
    assert [c.key for c in cells] == ["p1"] and notes == []
    assert [m.name for m in cells[0].members] == ["p1_on", "p1_off"] and cells[0].labelled == [["mpi"]]
    by_page, notes = sweep.set_cells(run, points, sweep.set_entries({"m": {"curves": {"gen": "all"}}}, "w")[0])
    assert [c.key for c in by_page] == ["on", "off"]                         # mpi left out: it pages, once


# ── one pdf for every generator (V152) ────────────────────────────────────────────────────────

PDFS = """[run]
project = "Demo"
name    = "pdfs"
run     = "all"
events  = 10
threads = 1
chain   = [["@gen", "rivet"]]

[tools.pythia]
card   = "ep.cmnd"
output = "events.hepmc"

[tools.sherpa]
card   = "ep.sherpa.yaml"
output = "events.hepmc"

[tools.herwig]
card   = "dis_ep.herwig.in"
output = "events.hepmc"

[tools.rivet]
input    = "events.hepmc"
analyses = ["photo_eic"]
output   = "jets.yoda"

[quantities.gen]
points = [{ tag = "py8", value = "pythia" }, { tag = "sh3", value = "sherpa" }, { tag = "hw7", value = "herwig" }]

[quantities.energies]
fixed  = "18x275"
points = [{ tag = "18x275", value = [275, 18] }]

[quantities.pdf]
points = [{ tag = "mstw", value = "MSTW2008lo68cl" }, { tag = "nnpdf", value = "LHAPDF6:NNPDF23_lo_as_0130_qed" }]

[cfgs.all]
vary = ["gen", "pdf"]
"""


def card_of(plan, tag: str) -> list[str]:
    return plan.writes[plan.rendered[tag].card_combined].splitlines()


@pytest.mark.skipif(not (shutil.which("Herwig") and shutil.which("Sherpa")), reason="gjallarhorn: Herwig and Sherpa")
def test_one_pdf_quantity_feeds_every_generator_in_its_own_spelling(scratch):
    path = scratch / "pdfs.toml"
    path.write_text(PDFS, encoding="utf-8")
    try:
        run = config.load(str(path))
        conf = run.configuration("all")
        master = quantities.load_master(run.project, run.master_toml)
        by = {p.name: tools.plan_point(run, conf, p, master) for p in sweep.points(run, conf)}
        for planned in by.values():
            tools.finalise(planned, 12345)                          # the cards written out
    except HepError as error:
        if "repository" not in error.message and "heimdall build" not in (error.hint or ""):
            raise
        pytest.skip(error.message)                                   # Herwig's repository: heimdall build
    assert "PDF:pSet = LHAPDF6:MSTW2008lo68cl" in card_of(by["py8_mstw"], "pythia")
    assert "PDF:pSet = LHAPDF6:NNPDF23_lo_as_0130_qed" in card_of(by["py8_nnpdf"], "pythia")
    sherpa = "\n".join(card_of(by["sh3_nnpdf"], "sherpa"))
    assert "NNPDF23_lo_as_0130_qed" in sherpa and "LHAPDF6:" not in sherpa
    herwig = card_of(by["hw7_mstw"], "herwig")
    for name in ("HardLOPDF", "ShowerLOPDF", "MPIPDF", "RemnantPDF"):           # one value, every key
        assert f"set /Herwig/Partons/{name}:PDFName MSTW2008lo68cl" in herwig


# ── a selector's value may be a piece of chain (V153) ─────────────────────────────────────────

PIECES = """[run]
project = "Demo"
name    = "pieces"
run     = "all"
events  = 10
threads = 1
chain   = CHAIN

[tools.a]
uses       = "exec"
executable = "/bin/true"
output     = "a.dat"

[tools.b]
uses       = "exec"
executable = "/bin/true"
output     = "b.dat"

[tools.c]
uses       = "exec"
executable = "/bin/true"
output     = "c.dat"

[tools.e]
uses       = "exec"
executable = "/bin/true"
output     = "e.dat"

[tools.d]
uses       = "exec"
executable = "/bin/true"
output     = "d.dat"

[quantities.var]
points = POINTS

[cfgs.all]
vary = ["var"]
"""


def pieces(scratch, chain: str, points: str) -> dict:
    path = scratch / "pieces.toml"
    path.write_text(PIECES.replace("CHAIN", chain).replace("POINTS", points), encoding="utf-8")
    run = config.load(str(path))
    conf = run.configuration("all")
    master = quantities.load_master(run.project, run.master_toml)
    return {p.name: tools.plan_point(run, conf, p, master) for p in sweep.points(run, conf)}


def tags(plan) -> list[list[str]]:
    return [[step.tag for step in group] for group in plan.groups]


def test_a_piece_of_chain_is_spliced_where_its_selector_stands(scratch):
    by = pieces(scratch, '["@var", "d"]', '[{ tag = "split", value = ["a", ["b", "c"]] }, { tag = "seq", value = ["e", "c"] },'
                                          ' { tag = "one", value = "e" }, { tag = "none", value = [] }]')
    assert tags(by["split"]) == [["a"], ["b", "c"], ["d"]]                 # ["A", ["B", "C"], "D"]
    assert tags(by["seq"]) == [["e"], ["c"], ["d"]]
    assert tags(by["one"]) == [["e"], ["d"]] and tags(by["none"]) == [["d"]]


STREAM = PIECES.split("[tools.a]")[0].replace("CHAIN", '["@var"]') + """[tools.pythia]
card   = "ep.cmnd"
output = "events.hepmc"

[tools.rivet]
input    = "events.hepmc"
analyses = ["photo_eic"]
output   = "jets.yoda"

[quantities.var]
points = [{ tag = "together", value = [["pythia", "rivet"]] }, { tag = "after", value = ["pythia", "rivet"] }]

[cfgs.all]
vary = ["var"]
"""


def test_each_point_s_chain_infers_its_own_interfaces(scratch):
    path = scratch / "stream.toml"
    path.write_text(STREAM, encoding="utf-8")
    run = config.load(str(path))
    conf = run.configuration("all")
    master = quantities.load_master(run.project, run.master_toml)
    by = {p.name: tools.plan_point(run, conf, p, master) for p in sweep.points(run, conf)}
    assert tags(by["together"]) == [["pythia", "rivet"]] and by["together"].prelim.get("fifo") == ["events.hepmc"]
    assert tags(by["after"]) == [["pythia"], ["rivet"]] and "fifo" not in by["after"].prelim   # a file, read later


def test_inside_a_group_a_piece_s_tags_join_it(scratch):
    by = pieces(scratch, '[["@var", "a"], "b"]', '[{ tag = "none", value = [] }, { tag = "one", value = "e" }]')
    assert tags(by["none"]) == [["a"], ["b"]]                              # streamed pairs: test_each_point_s_chain…
    assert tags(by["one"]) == [["e", "a"], ["b"]]


@pytest.mark.parametrize("chain, points, message", [
    ('[["@var", "d"]]', '[{ tag = "deep", value = ["a", ["b"]] }]', "puts a group inside the group of @var"),
    ('["@var", "d"]', '[{ tag = "deep", value = ["a", [["b"]]] }]', "nests a group two deep"),
    ('["@var", "d"]', '[{ tag = "twice", value = ["e", "d"] }]', "'d' is twice in the chain"),
    ('["@var", "d"]', '[{ tag = "ok", value = "e" }, { tag = "typo", value = ["e", "cc"] }]', "'cc' is not a"),
    ('[["@var"], ["d"]]', '[{ tag = "empty", value = [[]] }]', "holds an empty group"),
    ('["@var", "d"]', '[{ tag = "num", value = 3 }]', "a selector's value is a tool tag or a list"),
])
def test_a_piece_that_makes_no_valid_chain_is_refused_with_the_file(scratch, chain, points, message):
    with pytest.raises(HepError, match=message) as refused:
        pieces(scratch, chain, points)
    assert "[quantities.var]" in refused.value.where


def test_a_value_no_point_runs_is_checked_too(scratch):
    text = '[{ tag = "ok", value = "e" }, { tag = "typo", value = ["cc"] }]'
    path = scratch / "pieces.toml"
    path.write_text(PIECES.replace("CHAIN", '["@var", "d"]').replace("POINTS", text)
                    .replace('vary = ["var"]', 'fixed = { var = "ok" }'), encoding="utf-8")
    with pytest.raises(HepError, match="'cc' is not a"):
        config.load(str(path))


# ── points that set several quantities at once (V154) ─────────────────────────────────────────

PT0 = {"values": [3.0, 3.4], "tags": ["p30", "p34"], "key": {"pythia": "MultipartonInteractions:pT0Ref"}}


def listed(rows: list, **changes) -> dict:
    return raw(run__cfgs__one__tools=[["@gen", "rivet"]], tools__other=OTHER, quantities__pdf=None,
               quantities__gen={"values": ["pythia", "other"], "tags": ["py", "ot"]}, quantities__pt0ref=PT0,
               run__cfgs__one__sweeps=[{"points": rows}], **changes)


def test_listed_points_set_some_quantities_each(scratch):
    rows = [{"gen": "py", "pt0ref": "p30"}, {"gen": "py", "pt0ref": "#2"}, {"gen": "ot"}]
    plans = plan_all(listed(rows), scratch)                      # ot sets no pt0ref, so V151 is satisfied
    assert list(plans) == ["py_p30", "py_p34", "ot"]
    assert plans["ot"].point.choice == {"gen": 1} and "pt0ref" not in plans["ot"].values
    tools.finalise(plans["py_p34"], 1)
    card = plans["py_p34"].writes[plans["py_p34"].rendered["pythia"].card_combined]
    assert "MultipartonInteractions:pT0Ref = 3.4" in card.splitlines()


@pytest.mark.parametrize("rows, sweeps, message", [
    ([{"gen": "py"}, {"gen": "py"}], None, "listed points 1 and 2 are the same point"),
    ([{"gen": "py", "pt0": "p30"}], None, "sets 'pt0', which is not a"),
    ([{"gen": "py", "pt0ref": "p31"}], None, "'p31' is not a value of"),
    ([{"gen": "py"}], ["gen"], "'gen' is swept twice"),
    ([], None, "lists combinations"),
])
def test_listed_points_are_checked_with_the_file(scratch, rows, sweeps, message):
    data = listed(rows)
    if sweeps:
        data["run"]["cfgs"]["one"]["sweeps"] = sweeps + data["run"]["cfgs"]["one"]["sweeps"]
    with pytest.raises(HepError, match=message):
        parse(data, scratch)


def test_a_page_axis_may_be_one_quantity_of_listed_points(scratch):
    from runner import plot, record
    rows = [{"gen": "py", "pt0ref": "p30"}, {"gen": "py", "pt0ref": "p34"}, {"gen": "ot"}]
    run = parse(listed(rows, run__cfgs__one__plot_points=["gen"]), scratch)
    conf = run.configuration(None)
    pages_, curves = plot.axes_of(conf)
    assert pages_ == [["gen"]] and curves == [["pt0ref"]]
    points = sweep.points(run, conf)
    assert {k: [p.name for p in v] for k, v in sweep.pages(conf, points).items()} == {((0,),): ["py_p30", "py_p34"], ((1,),): ["ot"]}
    master = quantities.load_master(run.project, run.master_toml)
    plans = [tools.plan_point(run, conf, p, master) for p in points]
    assert [p["page"] for p in record.points_manifest(plans, run, conf)["points"]] == [["py"], ["py"], ["ot"]]
    with pytest.raises(HepError, match="plot_points names 'pt0ref', which listed point 3 leaves out"):
        parse(listed(rows, run__cfgs__one__plot_points=["pt0ref"]), scratch)
    with pytest.raises(HepError, match="names pt0ref, a quantity of listed points"):
        plot.check_figures(parse(listed(rows, plot={"band": ["pt0ref"]}), scratch), conf)


COUPLED = """[run]
project = "Demo"
name    = "coupled"
run     = "all"
events  = 10
threads = 1
chain   = [["@gen", "@ana"]]

TOOLS
[quantities.setup]                 # the user's example: [A,E] [B,E] [B,G] [C,F]
fields = { gen = "gen", ana = "ana" }
points = [
  { tag = "AE", gen = "a", ana = "e" },
  { tag = "BE", gen = "b", ana = "e" },
  { tag = "BG", gen = "b", ana = "g" },
  { tag = "CF", gen = "c", ana = "f" },
]

[cfgs.all]
vary = VARY
"""


@pytest.mark.parametrize("vary, names", [('["setup"]', ["AE", "BE", "BG", "CF"]),
                                          ('[{ points = [{ setup = "BG" }, { setup = "#1" }] }]', ["BG", "AE"])])
def test_coupled_selectors_choose_their_tools_together(scratch, vary, names):
    tables = "".join(f'[tools.{t}]\nuses       = "exec"\nexecutable = "/bin/true"\noutput     = "{t}.dat"\n\n' for t in "abcefg")
    path = scratch / "coupled.toml"
    path.write_text(COUPLED.replace("TOOLS", tables).replace("VARY", vary), encoding="utf-8")
    run = config.load(str(path))
    conf = run.configuration("all")
    master = quantities.load_master(run.project, run.master_toml)
    by = {p.name: tags(tools.plan_point(run, conf, p, master)) for p in sweep.points(run, conf)}
    pairs = {"AE": [["a", "e"]], "BE": [["b", "e"]], "BG": [["b", "g"]], "CF": [["c", "f"]]}
    assert by == {name: pairs[name] for name in names}            # a listed row naming a compound sets every field
