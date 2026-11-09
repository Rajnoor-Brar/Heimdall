"""The run TOML's third form (runner/v3.py): read as the second's, so a
study written either way is the same run, the same points and the same identities."""

from __future__ import annotations

from pathlib import Path

import re
import pytest

from runner import config, quantities, sweep, tools
from runner.errors import HeimdallError
from helpers import plans_of

V2 = """[errand]
name          = "pair"
assignment    = "Demo"
configuration = "single"
event_count   = 10
threads       = 1

[errand.cfgs.single]
sweeps = []
tools  = [["pythia", "rivet"], "yd2rt"]

[errand.cfgs.pdf]
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

V3 = """[errand]
assignment = "Demo"
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
    """The errand file in scratch, with the fixture's cards beside it (a bare name is beside the file naming it)."""
    import shutil
    from runner.paths import configs_root
    path = scratch / name
    path.write_text(text, encoding="utf-8")
    for card in (configs_root() / "Demo").iterdir():
        if card.suffix != ".toml" and card.is_file() and not (scratch / card.name).exists():
            shutil.copy(card, scratch / card.name)
    return str(path)


def load(scratch: Path, text: str, name: str = "run.toml") -> config.Errand:
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
    errand = load(scratch, V3)
    assert errand.tools["rivet"].input == ["events.hepmc"] and errand.tools["yd2rt"].input == ["jets.yoda"]
    assert errand.tools["pythia"].tool == "pythia" and errand.tools["pythia"].baseconfig == ["ep.cmnd"]


def test_interfaces_are_inferred_from_the_chain(scratch):
    """Same group: a FIFO; a later group: a product, or a scratch file when the producer says keep = false."""
    text = V3.replace('chain   = [["pythia", "rivet"], "yd2rt"]', 'chain   = ["pythia", "rivet", "yd2rt"]')
    text = text.replace('output = "events.hepmc"            # a FIFO: rivet reads it in the same group',
                        'output = "events.hepmc"\nkeep   = false')
    errand = load(scratch, text)
    assert errand.configuration("single").prelim == {"files": ["events.hepmc"]}      # scratch, in the point's folder
    errand = load(scratch, text.replace("keep   = false", ""))
    assert errand.configuration("single").prelim == {}                              # a product: results/


def test_a_compound_quantity_sweeps_its_fields_together(scratch):
    """doc:errand-file example 2: one row per point, a value per field; the points are named by its tags."""
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
    errand, conf, points, plans = plans_of(written(scratch, text), "nuclei")
    assert [p.name for p in points] == ["p", "Au"]                                    # not p_p_p
    assert errand.quantities["collision_npdf"].silent and not errand.quantities["energies"].silent
    card = plans[1].rendered["pythia"].card_lines
    assert "PDF:nPDFBeamA = 1000791970" in card and "PDF:useHardNPDFA = on" in card
    assert "Beams:eA = 100" in card and "Beams:eB = 9" in card


def test_events_as_a_list_make_one_configuration_per_count(scratch):
    errand = load(scratch, V3.replace('[cfgs.pdf]\nvary = ["pdf"]', '[cfgs.pdf]\nvary   = ["pdf"]\nevents = [100, 2500]'))
    assert errand.runs("pdf") == ["pdf_100", "pdf_2.5k"]
    assert [errand.configurations[k].event_count for k in errand.runs("pdf")] == [100, 2500]
    assert errand.configurations["pdf_2.5k"].label == "pdf_2.5k"
    with pytest.raises(HeimdallError, match="several configurations, one per event count"):
        errand.configuration("pdf")


def test_beams_are_one_quantity(scratch):
    text = V3.replace('''[quantities.energies]
fixed  = "18x275"
points = [{ tag = "18x275", value = [275, 18], label = "18x275 GeV" }]''', '''[quantities.beams]
fixed  = "ep275"
points = [{ tag = "ep275", label = "18x275 GeV e-p", a = { id = 2212, energy = 275 }, b = { id = 11, energy = 18 } }]''')
    errand = load(scratch, text)
    assert errand.quantities["beams"].values == [[2212, 11]] and errand.quantities["energies"].values == [[275, 18]]
    assert errand.configuration("single").static == {"beams": "ep275", "energies": "ep275", "pdf": "MSTW08lo"}


def test_the_seed_is_one_key(scratch):
    errand = load(scratch, V3.replace("threads = 1\n", "threads = 1\nseed    = 7\n", 1))
    assert (errand.configuration("single").seed_type, errand.configuration("single").manual_seed) == ("manual", 7)


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
    with pytest.raises(HeimdallError, match=message):
        load(scratch, text)


def test_a_v2_file_stays_v2(scratch):
    """For one release: a file without v3's tables, or one that says [file] schema = 2."""
    assert load(scratch, V2).form == 2
    assert load(scratch, "[file]\nschema = 2\n\n" + V2, "said.toml").form == 2


def test_an_imported_tool_table_merges_key_by_key(scratch):
    """doc:errand-file: a v3 file changes one key of an imported tool, not the whole table (v2 replaced it)."""
    common = scratch / "common.toml"
    common.write_text(V3.replace('[cfgs.single]\ndescription = "One run at the fixed point"\n', "")
                      .replace('[cfgs.pdf]\nvary = ["pdf"]\n', ""), encoding="utf-8")
    mine = f'[file]\nimport = ["{common}"]\n\n[errand]\nassignment = "Demo"\nname = "mine"\nrun = "one"\n\n' \
           '[tools.rivet]\nanalyses = ["photo_eic:R=0.7"]\n\n[cfgs.one]\nvary = ["pdf"]\n'
    errand = load(scratch, mine, "mine.toml")
    assert errand.form == 3 and errand.tools["rivet"].extra["analyses"] == ["photo_eic:R=0.7"]
    assert errand.tools["rivet"].output_file == ["jets.yoda"] and errand.tools["rivet"].input == ["events.hepmc"]


def test_the_card_shows_where_each_line_comes_from(scratch, capsys):
    from runner import cli
    path = written(scratch, V3)
    assert cli.main(["run", path, "pdf", "--plan", "--card", "pythia", "--points", "NNPDF23lo"]) == 0
    shown = capsys.readouterr().out
    assert "pythia's card for point NNPDF23lo" in shown
    assert "← [quantities.pdf] = NNPDF23lo, over ep.cmnd:" in shown
    assert "← the runner (the seed)" in shown and "!" not in shown


def _identities(errand) -> dict:
    from runner import record
    master = quantities.load_master(errand.assignment, errand.master_toml)
    out = {}
    for key, conf in errand.configurations.items():
        plans = [tools.plan_point(errand, conf, p, master) for p in sweep.points(errand, conf)]
        out[key] = [(p.point.name, conf.prelim, record.identity(p)) for p in plans]
    return out


def test_every_fixture_config_is_its_v2_text_in_v3():
    """06_Plan's phase-6 row: the fixture's configs were migrated by heimdall migrate --v3; their v2 texts
    (tests/reference/v2_configs/, in the older names: read through heimdall migrate --names' errand_text)
    and they plan every point to the same name and identity, and the v2 text migrates to the file as it is."""
    from runner import house, migrate
    from support import REPO
    for name in house.config_names():
        v2 = migrate.errand_text((REPO / "tests" / "reference" / "v2_configs" / f"{name}.toml").read_text(encoding="utf-8"))
        v2 = re.sub(r'(backend\s*=\s*\["root", )"yoda"\]', r'\1"mpl"]', v2)    # the retired backend: the reference stays as it was written
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
    (('analyses = ["photo_eic"]', 'analyses = ["photo_eic"]\nthreads  = 4'), "'threads' belongs in \\[errand\\] \\(or a configuration\\)"),
    (('[cfgs.pdf]\nvary = ["pdf"]', '[cfgs.pdf]\nvary = ["pdf"]\nformats = ["png"]'), "'formats' belongs in \\[plot\\]"),
    (('analyses = ["photo_eic"]', 'analyses = ["photo_eic"]\nvary = ["pdf"]'), "'vary' belongs in a configuration"),
])
def test_a_key_in_the_wrong_table_names_its_table(scratch, change, message):
    """doc:plots, 06_Plan's row: `threads = 4` in a tool table says where threads goes."""
    with pytest.raises(HeimdallError) as caught:
        plans_of(written(scratch, V3.replace(*change)), "pdf")
    assert caught.value.hint and __import__("re").search(message, caught.value.hint), caught.value.hint


def test_heimdall_check_names_tool_tables_nothing_uses(scratch):
    from runner import house
    errand = load(scratch, V3.replace("[tools.yd2rt]", '[tools.spare]\nuses = "yd2rt"\ninput = "rivet"\noutput = "x.root"\n\n[tools.yd2rt]'))
    assert house.unused_tools(errand) == ["[tools.spare] is defined but no configuration runs it or names it in generate_cards"]
    assert house.unused_tools(load(scratch, V3)) == []


def test_the_editor_schemas_take_the_fixture_and_catch_a_typo():
    """run.schema.json (v2) and run.v3.schema.json take every fixture config; a shipped tool's table
    is closed in v3, so a misspelt key is flagged in the editor."""
    jsonschema = pytest.importorskip("jsonschema")
    import json
    import tomllib
    from support import REPO
    from runner import schema
    v2, v3 = schema.json_schema(), schema.json_schema_v3()
    for path in (REPO / "tests" / "fixtures" / "work" / "configs").rglob("*.toml"):
        assert not list(jsonschema.Draft7Validator(v3).iter_errors(tomllib.loads(path.read_text(encoding="utf-8")))), path.name
    from runner import migrate
    for path in (REPO / "tests" / "reference" / "v2_configs").rglob("*.toml"):              # in today's names
        assert not list(jsonschema.Draft7Validator(v2).iter_errors(tomllib.loads(migrate.errand_text(path.read_text(encoding="utf-8"))))), path.name
    wrong = tomllib.loads(V3.replace('analyses = ["photo_eic"]', 'analysis = ["photo_eic"]'))
    assert any("analysis" in e.message for e in jsonschema.Draft7Validator(v3).iter_errors(wrong))
    for name in ("run.schema.json", "run.v3.schema.json"):                     # make schema keeps them current
        assert json.loads((REPO / "framework" / "schema" / name).read_text(encoding="utf-8")) == (v2 if "v3" not in name else v3), name


# ── serials and "default" (6.3) ────────────────────────────────────────────────────────────────────────

def _planned(path: str, key: str, sets=(), rerun: bool = False):
    import argparse
    from runner import cli
    return cli.build_plans(argparse.Namespace(config=path, set=list(sets), points=None, rerun=rerun, only=None), key)


@pytest.fixture
def trees_of_its_own(scratch, monkeypatch):
    """records/, logs/ and results/ of this test alone: a folder's number depends on what is on disk."""
    monkeypatch.setenv("HEIMDALL_RECORDS", str(scratch / "records"))
    monkeypatch.setenv("HEIMDALL_CACHE", str(scratch / "cache"))
    monkeypatch.setenv("HEIMDALL_RESULTS", str(scratch / "results"))
    return scratch


def _complete(planned) -> None:
    """Each point as a finished run leaves it: its .complete marker, holding its identity."""
    from runner import record
    for plan in planned.plans:
        plan.out.mkdir(parents=True, exist_ok=True)
        record.write_atomic(record.complete_marker(plan), plan.identity + "\n")


def test_the_runner_numbers_a_folder_without_a_serial(scratch, trees_of_its_own):
    """doc:errand-file: no serial, so the runner picks the number: the newest folder made from these inputs; a change
    gets a new number and never overwrites; undoing the change finds its folder again."""
    path = written(scratch, V3.replace('name    = "pair"', 'name    = "numbered"'), "numbered.toml")
    first = _planned(path, "pdf")
    assert first.configuration.serial == 1 and first.plans[0].folders.record.name == "01_pdf"
    assert "the first" in first.configuration.serial_note
    _complete(first)
    assert _planned(path, "pdf").configuration.serial == 1                     # made from these inputs
    changed = _planned(path, "pdf", sets=["errand.events=20"])                     # --set in v3's own names
    assert changed.configuration.event_count == 20 and changed.configuration.serial == 2
    assert "01 holds other inputs" in changed.configuration.serial_note
    _complete(changed)
    assert _planned(path, "pdf").configuration.serial == 1                     # the change undone: its folder
    assert _planned(path, "pdf", sets=["errand.events=20"]).configuration.serial == 2


def test_a_set_serial_refuses_to_overwrite_other_inputs(scratch, trees_of_its_own, capsys):
    """doc:errand-file: a serial the file sets keeps its folder, and a changed configuration is refused there, with
    the bump as the hint; --rerun says to overwrite. A v2 file runs as ever."""
    import argparse
    from runner import cli
    path = written(scratch, V3.replace('name    = "pair"', 'name    = "kept"\nserial  = 3'), "kept.toml")
    _complete(_planned(path, "pdf"))
    same = _planned(path, "pdf")
    assert same.configuration.serial == 3 and not same.configuration.serial_auto and cli.overwrites(same) == []
    changed = _planned(path, "pdf", sets=["errand.events=20"])
    with pytest.raises(HeimdallError, match="would overwrite them") as error:
        cli.refuse_overwrites(changed, argparse.Namespace(rerun=False))
    assert "serial = 4" in error.value.hint and "--rerun" in error.value.hint and "[errand]" in error.value.where
    cli.refuse_overwrites(changed, argparse.Namespace(rerun=True))
    cli.refuse_overwrites(changed, argparse.Namespace(rerun=False), frozenset({"post", "plot"}))   # no point runs
    cli.print_plan(changed.errand, changed.configuration, changed.plans, pre_plan=changed.pre)
    assert "running refuses to overwrite them (serial = 4, or --rerun)" in capsys.readouterr().out
    v2 = written(scratch, V2.replace('name          = "pair"', 'name          = "kept2"\nserial        = 3'), "kept2.toml")
    _complete(_planned(v2, "pdf"))
    assert cli.overwrites(_planned(v2, "pdf", sets=["errand.event_count=20"])) == []


def test_a_numbered_folder_is_one_configurations(scratch):
    text = V3 + '\n[cfgs.other]\nfolder = "pdf"\nserial = 1\nvary   = ["pdf"]\n'
    with pytest.raises(HeimdallError, match="'pdf' and 'other' would both write Demo/pair/NN_pdf"):
        load(scratch, text)
    with pytest.raises(HeimdallError, match="would both write Demo/pair/01_pdf"):                 # either form
        twice = V2.replace("[errand.cfgs.pdf]", "[errand.cfgs.pdf]\nserial = 1").replace(
            "[prelim]", '[errand.cfgs.other]\nlabel  = "pdf"\nserial = 1\nsweeps = ["pdf"]\ntools  = ["pythia"]\n\n[prelim]')
        load(scratch, twice, "two.toml")


def test_default_is_the_layer_below_and_native_the_tools_own(scratch):
    """doc:errand-file: in v3, [plot] y_gutter = "default" is as if absent (the schema's 0.5); "native" is the drawing
    tool's own, at any level: v2's [plot]-level "default", which the migration rewrites so."""
    from runner import migrate, plot
    assert "y_gutter" not in load(scratch, V3 + '\n[plot]\ny_gutter = "default"\n').plot
    assert load(scratch, V3 + '\n[plot]\ny_gutter = "native"\n').plot["y_gutter"] == "native"
    assert plot.chosen("y_gutter", 0.5, "tool's", ({}, {"y_gutter": "native"})) == "tool's"
    assert plot.chosen("y_gutter", 0.5, "tool's", ({"y_gutter": "native"}, {"y_gutter": 0.3})) == "tool's"
    assert plot.chosen("y_gutter", 0.5, "tool's", ({"y_gutter": "default"}, {"y_gutter": 0.3})) == 0.3
    assert 'y_gutter = "native"' in migrate.v3_text(V2 + '\n[plot]\ny_gutter = "default"\n')
    with pytest.raises(HeimdallError, match="'threads' must be"):
        load(scratch, V3.replace("threads = 1", 'threads = "native"'))


def test_an_imports_only_and_drop_take_v3_names(scratch):
    """A v3 file names what it takes and drops of an import in its own names: cfgs.<name>, file.vars."""
    common = written(scratch, V3, "shared.toml")
    mine = f'[file]\nimport = [{{ from = "{common}", only = ["cfgs.pdf", "tools", "quantities", "errand.chain"] }}]\n\n' \
           '[errand]\nassignment = "Demo"\nname = "taker"\nrun = "pdf"\nevents = 10\n'
    errand = load(scratch, mine, "taker.toml")
    assert list(errand.configurations) == ["pdf"] and errand.configuration("pdf").sweeps == ["pdf"]
    dropping = f'[file]\nimport = ["{common}"]\ndrop = ["cfgs.single"]\n\n[errand]\nassignment = "Demo"\nname = "dropper"\nrun = "pdf"\n'
    assert "single" not in load(scratch, dropping, "dropper.toml").configurations
    with pytest.raises(HeimdallError, match="drop names"):
        load(scratch, dropping.replace("cfgs.single", "cfgs.singel"), "dropper.toml")


def test_a_commented_out_configuration_is_migrated_to_uncomment():
    """A configuration commented out in a v2 file stays one to uncomment in v3: header and keys renamed."""
    from runner import migrate
    text = V2 + '\n# [errand.cfgs.pthatmin]\n# serial      = 7\n# sweeps      = ["pdf"]\n# static      = { energies = "18x275" }\n'
    new = migrate.v3_text(text)
    assert '# [cfgs.pthatmin]' in new and '# vary        = ["pdf"]' in new and '# fixed       = { energies' in new
    assert "# serial      = 7" in new and "[errand.cfgs" not in new



def test_an_input_is_its_producer_only_where_they_run_together():
    """A table no configuration runs beside its producer (one an importer takes alone) keeps the file's
    name, which whatever the importer runs may write."""
    from runner import migrate
    text = V2 + '\n[tools.late]\ntool        = "yd2rt"\ninput       = "jets.yoda"\noutput_file = "late.root"\n'
    new = migrate.v3_text(text)
    yd2rt = new[new.index("[tools.yd2rt]"):].split("\n\n")[0]
    late = new[new.index("[tools.late]"):].split("\n\n")[0]
    assert '"rivet"' in yd2rt and "jets.yoda" not in yd2rt                        # it runs with rivet
    assert '"jets.yoda"' in late and '"rivet"' not in late                         # it runs with nothing here
