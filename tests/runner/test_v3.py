"""The run TOML's third form (docs/audit_3/06_Plan.md, phase 6; runner/v3.py): read as the second's, so a
study written either way is the same run, the same points and the same identities."""

from __future__ import annotations

from pathlib import Path

import pytest

from runner import config, quantities, sweep, tools
from runner.errors import HepError
from helpers import plans_of

V2 = """[run]
name          = "pair"
project       = "Demo"
configuration = "single"
event_count   = 10
threads       = 1

[run.cfgs.single]
sweeps = []
tools  = [["pythia", "rivet"], "yd2rt"]

[run.cfgs.pdf]
sweeps = ["pdf"]
tools  = [["pythia", "rivet"], "yd2rt"]

[prelim]
fifo = ["events.hepmc"]

[static]
energies = "18x275"
pdf      = "MSTW08lo"

[tools.pythia]
tool        = "pythia"
baseconfig  = "ep.cmnd"
output_file = "events.hepmc"

[tools.rivet]
tool        = "rivet"
input       = "events.hepmc"
analyses    = ["photo_eic"]
output_file = "jets.yoda"

[tools.yd2rt]
tool        = "yd2rt"
input       = "jets.yoda"
output_file = "jets.root"

[quantities.energies]
values = [[275, 18]]
tags   = ["18x275"]
labels = ["18x275 GeV"]

[quantities.pdf]
values = ["LHAPDF6:MSTW2008lo68cl", "LHAPDF6:NNPDF23_lo_as_0130_qed"]
tags   = ["MSTW08lo", "NNPDF23lo"]
labels = ["MSTW 2008 LO", "NNPDF 2.3 LO"]
"""

V3 = """[run]
project = "Demo"
name    = "pair"
run     = "single"
events  = 10
threads = 1
chain   = [["pythia", "rivet"], "yd2rt"]

[tools.pythia]
card   = "ep.cmnd"
output = "events.hepmc"            # a FIFO: rivet reads it in the same group

[tools.rivet]
input    = "pythia"               # by its producer
analyses = ["photo_eic"]
output   = "jets.yoda"

[tools.yd2rt]
input  = "rivet"
output = "jets.root"

[quantities.energies]
fixed  = "18x275"
points = [{ tag = "18x275", value = [275, 18], label = "18x275 GeV" }]

[quantities.pdf]
fixed  = "MSTW08lo"
points = [
  { tag = "MSTW08lo",  value = "LHAPDF6:MSTW2008lo68cl",         label = "MSTW 2008 LO" },
  { tag = "NNPDF23lo", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO" },
]

[cfgs.single]
description = "One run at the fixed point"

[cfgs.pdf]
vary = ["pdf"]
"""


def written(scratch: Path, text: str, name: str = "run.toml") -> str:
    path = scratch / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def load(scratch: Path, text: str, name: str = "run.toml") -> config.RunConfig:
    return config.load(written(scratch, text, name))


@pytest.mark.parametrize("cfg", ["single", "pdf"])
def test_the_v3_file_is_the_v2_file(scratch, cfg):
    """Every point: the same name, interfaces and identity, so v3 reruns nothing that v2 ran."""
    _, conf2, points2, plans2 = plans_of(written(scratch, V2, "v2.toml"), cfg)
    run3, conf3, points3, plans3 = plans_of(written(scratch, V3, "v3.toml"), cfg)
    assert run3.form == 3 and [p.name for p in points3] == [p.name for p in points2]
    assert conf3.prelim == conf2.prelim == {"fifo": ["events.hepmc"]}
    assert conf3.static == conf2.static and conf3.tools == conf2.tools
    assert [p.identity for p in plans3] == [p.identity for p in plans2]


def test_an_input_names_its_producer(scratch):
    run = load(scratch, V3)
    assert run.tools["rivet"].input == ["events.hepmc"] and run.tools["yd2rt"].input == ["jets.yoda"]
    assert run.tools["pythia"].tool == "pythia" and run.tools["pythia"].baseconfig == ["ep.cmnd"]


def test_interfaces_are_inferred_from_the_chain(scratch):
    """Same group: a FIFO; a later group: a product, or a scratch file when the producer says keep = false."""
    text = V3.replace('chain   = [["pythia", "rivet"], "yd2rt"]', 'chain   = ["pythia", "rivet", "yd2rt"]')
    text = text.replace('output = "events.hepmc"            # a FIFO: rivet reads it in the same group',
                        'output = "events.hepmc"\nkeep   = false')
    run = load(scratch, text)
    assert run.configuration("single").prelim == {"files": ["events.hepmc"]}         # scratch, in the point's folder
    run = load(scratch, text.replace("keep   = false", ""))
    assert run.configuration("single").prelim == {}                                 # a product: results/


def test_a_compound_quantity_sweeps_its_fields_together(scratch):
    """03 §6 example 2: one row per point, a value per field; the points are named by its tags."""
    text = V3.replace('[cfgs.pdf]\nvary = ["pdf"]', '''[cfgs.nuclei]
vary = ["collision"]

[quantities.collision]
fields = { energies = "energies", nucleus = { pythia = "PDF:nPDFBeamA" }, npdf = { pythia = "PDF:useHardNPDFA" } }
points = [
  { tag = "p",  label = "p",  energies = [130, 9], nucleus = 2212,       npdf = false },
  { tag = "Au", label = "Au", energies = [100, 9], nucleus = 1000791970, npdf = true },
]''')
    text = text.replace('''[quantities.energies]
fixed  = "18x275"
points = [{ tag = "18x275", value = [275, 18], label = "18x275 GeV" }]
''', "")
    run, conf, points, plans = plans_of(written(scratch, text), "nuclei")
    assert [p.name for p in points] == ["p", "Au"]                                    # not p_p_p
    assert run.quantities["collision_npdf"].silent and not run.quantities["energies"].silent
    card = plans[1].rendered["pythia"].card_lines
    assert "PDF:nPDFBeamA = 1000791970" in card and "PDF:useHardNPDFA = on" in card
    assert "Beams:eA = 100" in card and "Beams:eB = 9" in card


def test_events_as_a_list_make_one_configuration_per_count(scratch):
    run = load(scratch, V3.replace('[cfgs.pdf]\nvary = ["pdf"]', '[cfgs.pdf]\nvary   = ["pdf"]\nevents = [100, 2500]'))
    assert run.runs("pdf") == ["pdf_100", "pdf_2.5k"]
    assert [run.configurations[k].event_count for k in run.runs("pdf")] == [100, 2500]
    assert run.configurations["pdf_2.5k"].label == "pdf_2.5k"
    with pytest.raises(HepError, match="several configurations, one per event count"):
        run.configuration("pdf")


def test_beams_are_one_quantity(scratch):
    text = V3.replace('''[quantities.energies]
fixed  = "18x275"
points = [{ tag = "18x275", value = [275, 18], label = "18x275 GeV" }]''', '''[quantities.beams]
fixed  = "ep275"
points = [{ tag = "ep275", label = "18x275 GeV e-p", a = { id = 2212, energy = 275 }, b = { id = 11, energy = 18 } }]''')
    run = load(scratch, text)
    assert run.quantities["beams"].values == [[2212, 11]] and run.quantities["energies"].values == [[275, 18]]
    assert run.configuration("single").static == {"beams": "ep275", "energies": "ep275", "pdf": "MSTW08lo"}


def test_the_seed_is_one_key(scratch):
    run = load(scratch, V3.replace("threads = 1\n", "threads = 1\nseed    = 7\n", 1))
    assert (run.configuration("single").seed_type, run.configuration("single").manual_seed) == ("manual", 7)


@pytest.mark.parametrize("change, message", [
    (("[cfgs.single]", "[static]\npdf = \"MSTW08lo\"\n\n[cfgs.single]"), r"\[static\] is the v2 form"),
    (('card   = "ep.cmnd"', 'tool = "pythia"\ncard   = "ep.cmnd"'), "'tool' is the v2 form"),
    (('card   = "ep.cmnd"', 'baseconfig = "ep.cmnd"'), "'baseconfig' is the v2 form: this file is v3, where it is card"),
    (('vary = ["pdf"]', 'sweeps = ["pdf"]'), "'sweeps' is the v2 form: this file is v3, where it is vary"),
    (('fixed  = "MSTW08lo"\n', 'fixed  = "MSTW08lo"\ntags = ["x"]\n'), "'tags' is the v2 form"),
    (('[cfgs.pdf]\nvary = ["pdf"]', '[cfgs.pdf]\nvary = []'), "'pdf' is declared but neither varied nor fixed"),
])
def test_the_v2_forms_are_refused_with_their_v3_names(scratch, change, message):
    text = V3.replace(*change)
    if "neither varied" in message:
        text = text.replace('[quantities.pdf]\nfixed  = "MSTW08lo"\n', "[quantities.pdf]\n")
    with pytest.raises(HepError, match=message):
        load(scratch, text)


def test_a_v2_file_stays_v2(scratch):
    """For one release: a file without v3's tables, or one that says [file] schema = 2."""
    assert load(scratch, V2).form == 2
    assert load(scratch, "[file]\nschema = 2\n\n" + V2, "said.toml").form == 2


def test_an_imported_tool_table_merges_key_by_key(scratch):
    """03 §6: a v3 file changes one key of an imported tool, not the whole table (v2 replaced it)."""
    common = scratch / "common.toml"
    common.write_text(V3.replace('[cfgs.single]\ndescription = "One run at the fixed point"\n', "")
                      .replace('[cfgs.pdf]\nvary = ["pdf"]\n', ""), encoding="utf-8")
    mine = f'[file]\nimport = ["{common}"]\n\n[run]\nproject = "Demo"\nname = "mine"\nrun = "one"\n\n' \
           '[tools.rivet]\nanalyses = ["photo_eic:R=0.7"]\n\n[cfgs.one]\nvary = ["pdf"]\n'
    run = load(scratch, mine, "mine.toml")
    assert run.form == 3 and run.tools["rivet"].extra["analyses"] == ["photo_eic:R=0.7"]
    assert run.tools["rivet"].output_file == ["jets.yoda"] and run.tools["rivet"].input == ["events.hepmc"]


def test_the_card_shows_where_each_line_comes_from(scratch, capsys):
    from runner import cli
    path = written(scratch, V3)
    assert cli.main(["run", path, "pdf", "--plan", "--card", "pythia", "--points", "NNPDF23lo"]) == 0
    shown = capsys.readouterr().out
    assert "pythia's card for point NNPDF23lo" in shown
    assert "← [quantities.pdf] = NNPDF23lo" in shown and "ep.cmnd:" in shown and "set again below" in shown
    assert "← the runner (seeds, the footer)" in shown


def _identities(run) -> dict:
    from runner import record
    master = quantities.load_master(run.project, run.master_toml)
    out = {}
    for key, conf in run.configurations.items():
        plans = [tools.plan_point(run, conf, p, master) for p in sweep.points(run, conf)]
        out[key] = [(p.point.name, conf.prelim, record.identity(p)) for p in plans]
    return out


def test_every_fixture_config_is_its_v2_text_in_v3():
    """06_Plan's phase-6 row: the fixture's configs were migrated by hep migrate --v3; their v2 texts
    (tests/reference/v2_configs/) and they plan every point to the same name and identity, and the v2
    text migrates to the file as it is."""
    from runner import house, migrate
    from support import REPO
    for name in house.config_names():
        v2 = (REPO / "tests" / "reference" / "v2_configs" / f"{name}.toml").read_text(encoding="utf-8")
        mine = _identities(config.load(name))
        theirs = _identities(config.load(name, text=v2))
        assert {k: [(n, i) for n, _, i in v] for k, v in mine.items()} == \
               {k: [(n, i) for n, _, i in v] for k, v in theirs.items()}, name
        assert migrate.v3_text(config.config_file(name).read_text(encoding="utf-8")) == \
               config.config_file(name).read_text(encoding="utf-8"), name           # v3 stays as it is


def test_the_migration_says_each_fact_once(scratch):
    from runner import migrate
    new = migrate.v3_text(V2)
    assert new.count("chain") == 1 and "[prelim]" not in new and "[static]" not in new and "tool " not in new
    assert 'fixed  = "MSTW08lo"' in new and 'input       = "pythia"' in new and "[cfgs.pdf]" in new


@pytest.mark.parametrize("change, message", [
    (('analyses = ["photo_eic"]', 'analyses = ["photo_eic"]\nthreads  = 4'), "'threads' belongs in \\[run\\] \\(or a configuration\\)"),
    (('[cfgs.pdf]\nvary = ["pdf"]', '[cfgs.pdf]\nvary = ["pdf"]\nformats = ["png"]'), "'formats' belongs in \\[plot\\]"),
    (('analyses = ["photo_eic"]', 'analyses = ["photo_eic"]\nvary = ["pdf"]'), "'vary' belongs in a configuration"),
])
def test_a_key_in_the_wrong_table_names_its_table(scratch, change, message):
    """03 §3, 06_Plan's row: `threads = 4` in a tool table says where threads goes."""
    with pytest.raises(HepError) as caught:
        plans_of(written(scratch, V3.replace(*change)), "pdf")
    assert caught.value.hint and __import__("re").search(message, caught.value.hint), caught.value.hint
